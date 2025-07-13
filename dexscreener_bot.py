import os
import logging
import httpx  
import json   
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from asyncio import sleep

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DexScreenerAPI:
    BASE_URL = "https://api.dexscreener.com/latest"

    @staticmethod
    async def get_token_info(token_address: str, retries=3) -> dict:
        """Fetch token information from DexScreener API with retry logic."""
        endpoints = [
            f"{DexScreenerAPI.BASE_URL}/dex/pairs/solana/{token_address}",
            f"{DexScreenerAPI.BASE_URL}/dex/search/?q={token_address}",
            f"{DexScreenerAPI.BASE_URL}/dex/tokens/{token_address}"
        ]
        
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    for endpoint in endpoints:
                        logger.info(f"Trying endpoint: {endpoint}")
                        response = await client.get(endpoint)
                        
                        if response.status_code == 429:
                            wait_time = 2 ** attempt
                            logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                            await sleep(wait_time)
                            continue
                            
                        if response.status_code == 200:
                            data = response.json()
                            if data and isinstance(data, dict) and 'pairs' in data and data['pairs']:
                                return data
                                
                    await sleep(1)  # Brief pause between retries
                    
            except Exception as e:
                logger.error(f"Error fetching token info: {str(e)}")
                if attempt < retries - 1:
                    await sleep(1)
                    
        return None

    @staticmethod
    async def check_honeypot(token_address: str) -> str:
        """Check if a token is a honeypot using the dexscreener API and heuristics."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{DexScreenerAPI.BASE_URL}/dex/pairs/solana/{token_address}")
                if response.status_code != 200:
                    return "Could not fetch token info for honeypot check."
                    
                data = response.json()
                if not data or 'pairs' not in data or not data['pairs']:
                    return "No trading pairs found for this token."
                    
                pair = data['pairs'][0]
                warning_signs = []
                
                # Check buy/sell tax
                buy_tax = float(pair.get('buyTax', 0))
                sell_tax = float(pair.get('sellTax', 0))
                
                if buy_tax > 10:
                    warning_signs.append(f"High buy tax: {buy_tax}%")
                if sell_tax > 10:
                    warning_signs.append(f"High sell tax: {sell_tax}%")
                
                # Check liquidity
                liquidity = pair.get('liquidity', {}).get('usd', 0)
                if float(liquidity) < 1000:  # Less than $1000 liquidity
                    warning_signs.append(f"Very low liquidity: ${liquidity}")
                
                # Check if LP is locked
                if not pair.get('liquidity', {}).get('locked', False):
                    warning_signs.append("Liquidity is not locked")
                
                if warning_signs:
                    return f"⚠️ Potential risks detected:\n• " + "\n• ".join(warning_signs)
                return "✅ No obvious risks detected (always DYOR)"
                
        except Exception as e:
            logger.error(f"Error checking honeypot: {str(e)}")
            return "Error occurred during honeypot check."

async def format_token_info(token_info: dict) -> str:
    """Format token information for Telegram message"""
    if not token_info or 'pairs' not in token_info or not token_info['pairs']:
        return "Could not find token information."
    
    pair = token_info['pairs'][0]  # Get the first trading pair
    
    # Format market cap and liquidity values with 3 significant figures
    def format_number(value, suffix=''):
        try:
            num = float(value)
            if num >= 1e9:  # Billions
                return f"${num/1e9:.3g}B{suffix}"
            elif num >= 1e6:  # Millions
                return f"${num/1e6:.3g}M{suffix}"
            elif num >= 1e3:  # Thousands
                return f"${num/1e3:.3g}K{suffix}"
            else:
                return f"${num:.3g}{suffix}"
        except (ValueError, TypeError):
            return "N/A"

   
    fdv = format_number(pair.get('fdv', 0))
    liq = format_number(pair.get('liquidity', {}).get('usd', 0))
    price = format_number(pair.get('priceUsd', 'N/A'), '')
    volume = format_number(pair.get('volume', {}).get('h24', 'N/A'))
    
   
    try:
        price_change_24h = f"{float(pair.get('priceChange', {}).get('h24', 0)):.3g}"
        price_change_15m = f"{float(pair.get('priceChange', {}).get('m15', 0)):.3g}"
        trend_emoji = "📈" if float(price_change_15m) > 0 else "📉" if float(price_change_15m) < 0 else "➡️"
    except (ValueError, TypeError):
        price_change_24h = 'N/A'
        price_change_15m = 'N/A'
        trend_emoji = "➡️"
    
    return f"""💊 {pair.get('baseToken', {}).get('name', 'Unknown')} ({pair.get('url', 'N/A')})
🌐 {pair.get('chainId', 'Solana')} @ {pair.get('dexId', 'Unknown')}
💰 USD: {price}\n
💎 FDV: {fdv}\n
💦 Liq: {liq}\n
📊 Vol: {volume} ⋅ Age: {pair.get('pairCreatedAt', 'Unknown')}\n
{trend_emoji} 15m: {price_change_15m}%\n
📈 24h: {price_change_24h}%\n
👥 Holders: {pair.get('holdersCount', 'N/A')}\n
🔒 LP Locked: {'Yes' if pair.get('liquidity', {}).get('locked', False) else 'No'}"""

async def handle_token_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle token address queries"""
    message_text = update.message.text
    
    # Check if the message contains a token address
    if not message_text or len(message_text) < 32:
        await update.message.reply_text("Please provide a valid Solana token address.")
        return
        
    token_address = message_text.strip()
    await update.message.reply_text("Fetching token information...")
    
    dexscreener = DexScreenerAPI()
    token_info = await dexscreener.get_token_info(token_address)
    honeypot_result = await dexscreener.check_honeypot(token_address)
    if token_info:
        response = await format_token_info(token_info)
    else:
        response = "Could not fetch token information. Please check the token address and try again."
    response += f"\n\nHoneypot Check: {honeypot_result}"
    await update.message.reply_text(response)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Welcome! Send me a Solana token address to get detailed information about the token."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Send me a Solana token address and I'll fetch its market data from DexScreener!"
    )

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token_query))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
