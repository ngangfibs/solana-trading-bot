import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Import functionality from other modules
from telegram_openai_bot import OpenAIChatBot
from dexscreener_bot import DexScreenerAPI, format_token_info
from solana_wallet_bot import (
    load_wallets, save_wallets, button_handler, handle_token_operation,
    import_wallet, list_wallets, select_wallet, back_to_menu,
    add_sol, get_wallet_balance
)

# Load environment variables and setup  
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class MainBot:
    def __init__(self):
        self.chat_bot = OpenAIChatBot()
        self.dexscreener = DexScreenerAPI()
        load_wallets()  # Load existing wallets
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send initial message with mode selection."""
        keyboard = [
            [
                InlineKeyboardButton("💭 AI Chat Mode", callback_data='mode_chat'),
                InlineKeyboardButton("👛 Wallet Mode", callback_data='mode_wallet')
            ],
            [
                InlineKeyboardButton("🔍 Token Info Mode", callback_data='mode_token')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Welcome! Please select a mode:",
            reply_markup=reply_markup
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries."""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'mode_chat':
            context.user_data['mode'] = 'chat'
            await query.edit_message_text("AI Chat Mode activated! Just send me a message.")
        elif query.data == 'mode_wallet':
            await self.show_wallet_menu(update, context)
        elif query.data == 'mode_token':
            context.user_data['mode'] = 'token'
            await query.edit_message_text("Token Info Mode activated! Send me a token address to get detailed information.")
        elif query.data in ['import_wallet', 'list_wallets', 'buy_tokens', 'sell_tokens', 'swap_tokens', 'back_to_menu']:
            await button_handler(update, context)
        elif query.data.startswith('select_wallet_'):
            await select_wallet(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        mode = context.user_data.get('mode', 'chat')
        
        if mode == 'chat':
            await self.chat_bot.handle_message(update, context)
        elif mode == 'token':
            token_address = update.message.text.strip()
            if len(token_address) >= 32:
                await update.message.reply_text("Fetching token information...")
                token_info = await self.dexscreener.get_token_info(token_address)
                honeypot_result = await self.dexscreener.check_honeypot(token_address)  # Add honeypot check
                if token_info:
                    response = await format_token_info(token_info)
                    response += f"\n\nHoneypot Check: {honeypot_result}"  # Add honeypot result
                else:
                    response = "Could not fetch token information. Please check the token address and try again."
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("Please provide a valid token address.")
        else:  # wallet mode
            await handle_token_operation(update, context)

    async def show_wallet_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show wallet mode menu."""
        context.user_data['mode'] = 'wallet'
        keyboard = [
            [
                InlineKeyboardButton("Import Wallet", callback_data='import_wallet'),
                InlineKeyboardButton("List Wallets", callback_data='list_wallets')
            ],
            [
                InlineKeyboardButton("Buy Tokens", callback_data='buy_tokens'),
                InlineKeyboardButton("Sell Tokens", callback_data='sell_tokens')
            ],
            [
                InlineKeyboardButton("Swap Tokens", callback_data='swap_tokens'),
                InlineKeyboardButton("💭 Switch to Chat", callback_data='mode_chat')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            "Wallet Mode activated! What would you like to do?",
            reply_markup=reply_markup
        )

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that command. Please use the menu buttons.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Bot Help</b>\n\n"
        "• Use the menu buttons to switch between AI Chat, Wallet, and Token Info modes.\n"
        "• In Wallet Mode, you can import, list, and manage your Solana wallets.\n"
        "• In Token Info Mode, send a token address to get market data.\n"
        "• Use /start to return to the main menu at any time.",
        parse_mode="HTML"
    )

def main():
    """Start the bot."""
    bot = MainBot()
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()