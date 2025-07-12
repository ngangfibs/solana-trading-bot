import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

class OpenAIChatBot:
    def __init__(self):
        self.max_tokens = 500

    async def handle_message(self, update: Update, context: CallbackContext) -> None:
        user_message = update.message.text
        try:
            # Example: Compose the prompt for OpenAI
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful crypto assistant. who is a concise and always write in at most 6 sentences  "
                        "When the user asks about a token, use the following real-time token data from DexScreener API to answer accurately and concisely. "
                        "If the user asks about a token, always include the latest price, liquidity, 24h volume, and DEX link from the provided data. "
                        "If the user asks something else, answer normally."
                        "\n\n"
                        "Token Data:\n"
                        "{DexScreenerAPI.BASE_URL}/search/?q={token_address}" 
                    )
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ]
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=self.max_tokens,
            )
            reply = response['choices'][0]['message']['content']
        except Exception as e:
            reply = f"Error: {str(e)}"
        await update.message.reply_text(reply)

class TelegramBot:
    def __init__(self, token: str, chat_bot: OpenAIChatBot):
        self.application = Application.builder().token(token).build()
        self.chat_bot = chat_bot

    async def start(self, update: Update, context: CallbackContext) -> None:
        await update.message.reply_text("Hello! I am your AI assistant. Ask me anything!")

    def run(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.chat_bot.handle_message))
        self.application.run_polling()

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        print("Error: Missing TELEGRAM_TOKEN or OPENAI_API_KEY in environment variables.")
    else:
        chat_bot = OpenAIChatBot()
        telegram_bot = TelegramBot(TELEGRAM_TOKEN, chat_bot)
        telegram_bot.run()