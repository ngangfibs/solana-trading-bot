# Solana Wallet Bot User Guide

## Getting Started

1. Start the bot by sending `/start`
2. You'll see the main menu with the following options:
   - Import Wallet
   - List Wallets
   - Buy Tokens
   - Sell Tokens
   - Swap Tokens

## Managing Wallets

### Creating a New Wallet
1. Click "Import Wallet" in the main menu
2. The bot will generate a new wallet and show you:
   - Public Key (wallet address)
   - Private Key (keep this secure!)
3. The wallet will be automatically saved

### Viewing Your Wallets
1. Click "List Wallets" in the main menu
2. You'll see all your wallets with their:
   - Wallet number
   - Public Key
3. Click "Select Wallet" to choose a wallet for operations

## Token Operations

### Adding SOL to Your Wallet
1. Select a wallet from the list
2. Click "Add SOL"
3. Send SOL to the displayed address
4. Return to wallet view to see updated balance

### Buying Tokens
1. Select a wallet with sufficient SOL balance
2. Click "Buy Tokens"
3. Enter the token address and amount in SOL
   Format: `<token_address> <amount>`
4. Confirm the transaction

### Selling Tokens
1. Select a wallet with tokens to sell
2. Click "Sell Tokens"
3. Enter the token address and amount
   Format: `<token_address> <amount>`
4. Confirm the transaction

### Swapping Tokens
1. Select a wallet with tokens to swap
2. Click "Swap Tokens"
3. Enter the token addresses and amount
   Format: `<from_token_address> <to_token_address> <amount>`
4. Confirm the transaction

## Security Tips

1. Always verify:
   - Token addresses before trading
   - Transaction amounts
   - Network fees

2. Keep your private keys secure:
   - Never share them
   - Store them safely
   - Consider using a hardware wallet for large amounts

3. Be cautious of:
   - Unknown token addresses
   - Large slippage values
   - Unusual transaction requests

## Troubleshooting

### Common Issues

1. "Invalid token address"
   - Verify the token address is correct
   - Check if the token exists on Solana

2. "Insufficient balance"
   - Ensure you have enough SOL for:
     - The transaction amount
     - Network fees
   - Check your wallet balance

3. "Transaction failed"
   - Check your internet connection
   - Verify the RPC endpoint is working
   - Try again with a higher slippage

### Getting Help

If you encounter issues:
1. Check this guide
2. Verify your setup
3. Contact support if needed 