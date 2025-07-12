# Solana Wallet Bot

A Telegram bot for managing Solana wallets and performing token operations.

## Features

- Create and manage multiple Solana wallets
- View wallet balances
- Buy, sell, and swap tokens
- Add SOL to wallets
- Secure private key storage

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your configuration:
```
TELEGRAM_TOKEN=your_telegram_bot_token
SOLANA_RPC_URL=your_solana_rpc_url
```

3. Run the bot:
```bash
python solana_wallet_bot.py
```

## Commands

- `/start` - Start the bot and show main menu
- `/help` - Show help message
- `/import` - Import a new wallet
- `/list` - List your wallets

## Security Notes

- Never share your private keys
- The bot stores wallet information locally in `wallets.json`
- Always verify transaction details before confirming
- Use at your own risk

## Support

For support or issues, please open an issue in the repository. 