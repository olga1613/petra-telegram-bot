import os
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

# --- Переменные среды ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Google Sheets ---
def connect_to_sheet():
    credentials_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open_by_key("1nTUc2widvcKhF_s4E0B4i74NTkWPSca4MIoROphRGs0")
    worksheet = spreadsheet.sheet1
    return worksheet

def write_to_sheet(name, text):
    worksheet = connect_to_sheet()
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    worksheet.append_row([name, text, date])

# --- Ответ Петры ---
def ask_petra(user_message):
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID
    )
    while True:
        status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if status.status == 'completed':
            break
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    reply = messages.data[0].content[0].text.value
    return reply

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    name = user.full_name or "Telegram User"
    write_to_sheet(name, text)

    reply = ask_petra(text)
    await update.message.reply_text(reply)

# --- Запуск ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    app.add_handler(handler)
    app.run_polling()
