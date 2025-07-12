import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from solana.rpc.commitment import Commitment
from solders.transaction import Transaction
from solana.rpc.types import TxOpts
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID
import json
import requests
import base64

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Dictionary to store user wallets
user_wallets = {}

# Solana RPC URL
SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

# Jupiter API URL for token operations
JUPITER_API_URL = "https://quote-api.jup.ag/v6"

def load_wallets():
    global user_wallets
    try:
        with open('wallets.json', 'r') as f:
            user_wallets = json.load(f)
    except FileNotFoundError:
        user_wallets = {}

def save_wallets():
    with open('wallets.json', 'w') as f:
        json.dump(user_wallets, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
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
            InlineKeyboardButton("Swap Tokens", callback_data='swap_tokens')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f'Hi {user.first_name}! I am your Solana wallet manager bot.\n\n'
        'What would you like to do?',
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'import_wallet':
        await import_wallet(update, context)
    elif query.data == 'list_wallets':
        await list_wallets(update, context)
    elif query.data.startswith('select_wallet_'):
        await select_wallet(update, context)
    elif query.data == 'back_to_menu':
        await back_to_menu(update, context)
    elif query.data == 'add_sol':
        await add_sol(update, context)
    elif query.data == 'buy_tokens':
        await buy_tokens(update, context)
    elif query.data == 'sell_tokens':
        await sell_tokens(update, context)
    elif query.data == 'swap_tokens':
        await swap_tokens(update, context)

async def buy_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token buying process."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    if user_id not in user_wallets or not user_wallets[user_id]:
        await query.edit_message_text("You need to import a wallet first!")
        return
    
    # Ask for token address (step 1)
    context.user_data['action'] = 'buy_tokens'
    context.user_data['trade_step'] = 'await_token_address'
    await query.edit_message_text(
        "Please enter the token address you want to buy:",
    )

async def sell_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token selling process with improved UI."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    if user_id not in user_wallets or not user_wallets[user_id]:
        await query.edit_message_text("You need to import a wallet first!")
        return
    
    # Ask for token address (step 1)
    context.user_data['action'] = 'sell_tokens'
    context.user_data['trade_step'] = 'await_token_address'
    await query.edit_message_text(
        "Please enter the token address you want to sell:",
    )

async def swap_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token swapping process with improved UI."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    if user_id not in user_wallets or not user_wallets[user_id]:
        await query.edit_message_text("You need to import a wallet first!")
        return
    
    # Ask for from token address (step 1)
    context.user_data['action'] = 'swap_tokens'
    context.user_data['trade_step'] = 'await_from_token_address'
    await query.edit_message_text(
        "Please enter the token address you want to swap from:",
    )

async def get_token_price(token_address: str) -> float:
    """Get the current price of a token."""
    try:
        response = requests.get(f"{JUPITER_API_URL}/price?ids={token_address}")
        if response.status_code == 200:
            data = response.json()
            return float(data.get('data', {}).get(token_address, {}).get('price', 0))
        return 0
    except Exception as e:
        logger.error(f"Error getting token price: {e}")
        return 0

async def execute_token_swap(
    client: Client,
    keypair: Keypair,
    input_token: str,
    output_token: str,
    amount: float,
    slippage: float = 1.0
) -> bool:
    """Execute a token swap using Jupiter."""
    try:
        # Get quote for the swap
        quote_url = f"{JUPITER_API_URL}/quote"
        quote_params = {
            "inputMint": input_token,
            "outputMint": output_token,
            "amount": str(int(amount * 1e9)),  # Convert to lamports
            "slippageBps": int(slippage * 100)
        }
        
        quote_response = requests.get(quote_url, params=quote_params)
        if quote_response.status_code != 200:
            return False
            
        quote_data = quote_response.json()
        
        # Get swap transaction
        swap_url = f"{JUPITER_API_URL}/swap"
        swap_data = {
            "quoteResponse": quote_data,
            "userPublicKey": str(keypair.pubkey()),
            "wrapUnwrapSOL": True
        }
        
        swap_response = requests.post(swap_url, json=swap_data)
        if swap_response.status_code != 200:
            return False
            
        swap_data = swap_response.json()
        
        # Execute the swap transaction
        transaction_bytes = base64.b64decode(swap_data['swapTransaction'])
        transaction = Transaction.from_bytes(transaction_bytes)
        
        # Get recent blockhash
        recent_blockhash = client.get_latest_blockhash().value.blockhash
        
        # Sign and send transaction
        transaction.sign(keypair)
        opts = TxOpts(skip_confirmation=False, preflight_commitment=Commitment("confirmed"))
        result = client.send_transaction(transaction, keypair, opts=opts)
        
        return result.value is not None
        
    except Exception as e:
        logger.error(f"Error executing token swap: {e}")
        return False

async def handle_token_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token operations based on user input with improved UI and token info feedback."""
    user_id = str(update.effective_user.id)
    if user_id not in user_wallets or not user_wallets[user_id]:
        await update.message.reply_text("You need to import a wallet first!")
        return
    
    action = context.user_data.get('action')
    trade_step = context.user_data.get('trade_step')
    if not action:
        await update.message.reply_text("Please select an action first!")
        return
    
    try:
        # Get the first wallet for simplicity
        wallet = user_wallets[user_id][0]
        private_key = bytes.fromhex(wallet['private_key'])
        keypair = Keypair.from_bytes(private_key)
        client = Client(SOLANA_RPC_URL)
        
        # --- BUY TOKENS ---
        if action == 'buy_tokens':
            if trade_step == 'await_token_address':
                token_address = update.message.text.strip()
                context.user_data['pending_token_address'] = token_address
                context.user_data['trade_step'] = 'await_amount'
                await update.message.reply_text(f"Enter the amount of SOL to spend on buying token {token_address}:")
                return
            elif trade_step == 'await_amount':
                amount = float(update.message.text.strip())
                token_address = context.user_data.get('pending_token_address')
                # Show token info before confirming trade
                from dexscreener_bot import DexScreenerAPI, format_token_info
                dexscreener = DexScreenerAPI()
                token_info = await dexscreener.get_token_info(token_address)
                token_data_msg = await format_token_info(token_info) if token_info else "Token info unavailable."
                await update.message.reply_text(f"Token Data:\n{token_data_msg}\n\nPlacing buy order for {amount} SOL...")
                # Execute trade
                price = await get_token_price(token_address)
                if price == 0:
                    await update.message.reply_text("Could not get token price. Please try again.")
                    context.user_data['trade_step'] = None
                    context.user_data['action'] = None
                    return
                success = await execute_token_swap(
                    client,
                    keypair,
                    "So11111111111111111111111111111111111111112",
                    token_address,
                    amount
                )
                if success:
                    await update.message.reply_text(f"Successfully bought {amount} SOL worth of token {token_address}")
                else:
                    await update.message.reply_text("Failed to execute buy order. Please try again.")
                context.user_data['trade_step'] = None
                context.user_data['action'] = None
                return
        # --- SELL TOKENS ---
        if action == 'sell_tokens':
            if trade_step == 'await_token_address':
                token_address = update.message.text.strip()
                context.user_data['pending_token_address'] = token_address
                context.user_data['trade_step'] = 'await_amount'
                await update.message.reply_text(f"Enter the amount of {token_address} to sell:")
                return
            elif trade_step == 'await_amount':
                amount = float(update.message.text.strip())
                token_address = context.user_data.get('pending_token_address')
                # Show token info before confirming trade
                from dexscreener_bot import DexScreenerAPI, format_token_info
                dexscreener = DexScreenerAPI()
                token_info = await dexscreener.get_token_info(token_address)
                token_data_msg = await format_token_info(token_info) if token_info else "Token info unavailable."
                await update.message.reply_text(f"Token Data:\n{token_data_msg}\n\nPlacing sell order for {amount} {token_address}...")
                # Execute trade
                success = await execute_token_swap(
                    client,
                    keypair,
                    token_address,
                    "So11111111111111111111111111111111111111112",
                    amount
                )
                if success:
                    await update.message.reply_text(f"Successfully sold {amount} of token {token_address}")
                else:
                    await update.message.reply_text("Failed to execute sell order. Please try again.")
                context.user_data['trade_step'] = None
                context.user_data['action'] = None
                return
        # --- SWAP TOKENS ---
        if action == 'swap_tokens':
            if trade_step == 'await_from_token_address':
                from_token = update.message.text.strip()
                context.user_data['pending_from_token'] = from_token
                context.user_data['trade_step'] = 'await_to_token_address'
                await update.message.reply_text("Enter the token address you want to swap to:")
                return
            elif trade_step == 'await_to_token_address':
                to_token = update.message.text.strip()
                context.user_data['pending_to_token'] = to_token
                context.user_data['trade_step'] = 'await_amount'
                await update.message.reply_text("Enter the amount to swap:")
                return
            elif trade_step == 'await_amount':
                amount = float(update.message.text.strip())
                from_token = context.user_data.get('pending_from_token')
                to_token = context.user_data.get('pending_to_token')
                # Show token info before confirming trade
                from dexscreener_bot import DexScreenerAPI, format_token_info
                dexscreener = DexScreenerAPI()
                token_info = await dexscreener.get_token_info(to_token)
                token_data_msg = await format_token_info(token_info) if token_info else "Token info unavailable."
                await update.message.reply_text(f"Token Data (to_token):\n{token_data_msg}\n\nPlacing swap order for {amount} from {from_token} to {to_token}...")
                # Execute trade
                success = await execute_token_swap(
                    client,
                    keypair,
                    from_token,
                    to_token,
                    amount
                )
                if success:
                    await update.message.reply_text(f"Successfully swapped {amount} from {from_token} to {to_token}")
                else:
                    await update.message.reply_text("Failed to execute swap. Please try again.")
                context.user_data['trade_step'] = None
                context.user_data['action'] = None
                return
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")
        context.user_data['trade_step'] = None
        context.user_data['action'] = None

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Available commands:\n'
        '/import - Import a new wallet\n'
        '/list - List your wallets\n'
        '/help - Show this help message'
    )

async def import_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the wallet import process."""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_wallets:
        user_wallets[user_id] = []
    
    # Generate a new wallet
    new_wallet = Keypair()
    private_key = new_wallet.secret().hex()
    public_key = str(new_wallet.pubkey())
    
    # Store the wallet
    user_wallets[user_id].append({
        'public_key': public_key,
        'private_key': private_key
    })
    save_wallets()
    
    response_text = (
        f'New wallet created!\n\n'
        f'Public Key: {public_key}\n'
        f'Private Key: {private_key}\n\n'
        '⚠️ IMPORTANT: Keep your private key secure and never share it with anyone!'
    )
    
    # Handle both command and button callback cases
    if update.callback_query:
        await update.callback_query.edit_message_text(response_text)
    else:
        await update.message.reply_text(response_text)

async def list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all wallets for the user."""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_wallets or not user_wallets[user_id]:
        response_text = 'You have no wallets stored.'
        if update.callback_query:
            await update.callback_query.edit_message_text(response_text)
        else:
            await update.message.reply_text(response_text)
        return
    
    message = 'Your wallets:\n\n'
    keyboard = []
    
    for i, wallet in enumerate(user_wallets[user_id], 1):
        message += f'Wallet {i}:\n'
        message += f'Public Key: {wallet["public_key"]}\n\n'
        # Add button for each wallet
        keyboard.append([InlineKeyboardButton(f"Select Wallet {i}", callback_data=f'select_wallet_{i}')])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data='back_to_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

async def select_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet selection."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    # Extract wallet index from callback data
    wallet_index = int(query.data.split('_')[-1]) - 1  # Convert to 0-based index
    
    if user_id not in user_wallets or wallet_index >= len(user_wallets[user_id]):
        await query.edit_message_text("Invalid wallet selection!")
        return
    
    # Store selected wallet in user context
    context.user_data['selected_wallet'] = wallet_index
    selected_wallet = user_wallets[user_id][wallet_index]
    
    # Get wallet balance
    client = Client(SOLANA_RPC_URL)
    balance = await get_wallet_balance(client, selected_wallet['public_key'])
    
    # Create keyboard for actions with selected wallet
    keyboard = [
        [InlineKeyboardButton("Add SOL", callback_data='add_sol')],
        [InlineKeyboardButton("Buy Tokens", callback_data='buy_tokens'),
         InlineKeyboardButton("Sell Tokens", callback_data='sell_tokens')],
        [InlineKeyboardButton("Swap Tokens", callback_data='swap_tokens')],
        [InlineKeyboardButton("Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Wallet {wallet_index + 1} selected!\n\n"
        f"Public Key: {selected_wallet['public_key']}\n"
        f"Balance: {balance:.4f} SOL\n\n"
        "What would you like to do with this wallet?",
        reply_markup=reply_markup
    )

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu."""
    query = update.callback_query
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
            InlineKeyboardButton("Swap Tokens", callback_data='swap_tokens')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "What would you like to do?",
        reply_markup=reply_markup
    )

async def add_sol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle adding SOL to wallet."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    if 'selected_wallet' not in context.user_data:
        await query.edit_message_text("Please select a wallet first!")
        return
    
    wallet_index = context.user_data['selected_wallet']
    selected_wallet = user_wallets[user_id][wallet_index]
    
    # Create keyboard with back button
    keyboard = [[InlineKeyboardButton("Back to Wallet", callback_data=f'select_wallet_{wallet_index + 1}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"To add SOL to your wallet:\n\n"
        f"Send SOL to this address:\n{selected_wallet['public_key']}\n\n"
        "The balance will be updated automatically when you return to the wallet view.",
        reply_markup=reply_markup
    )

async def get_wallet_balance(client: Client, public_key: str) -> float:
    """Get the SOL balance of a wallet."""
    try:
        response = client.get_balance(Pubkey.from_string(public_key))
        balance = response.value / 1e9  # Convert lamports to SOL
        return balance
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return 0.0

def main():
    """Start the bot."""
    # Load existing wallets
    load_wallets()
    
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("import", import_wallet))
    application.add_handler(CommandHandler("list", list_wallets))
    
    # Add callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Add message handler for token operations
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token_operation))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()