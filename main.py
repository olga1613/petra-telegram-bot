import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
BITRIX_WEBHOOK_URL = os.getenv("BITRIX_WEBHOOK_URL")

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Google Sheets ---
def connect_to_sheet():
    credentials_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
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

# --- Bitrix ---
def send_to_bitrix(name, phone, email, comment):
    payload = {
        "fields": {
            "NAME": name,
            "PHONE": [{"VALUE": phone}],
            "EMAIL": [{"VALUE": email}],
            "COMMENTS": comment,
            "SOURCE_ID": "WEB"
        }
    }
    try:
        response = requests.post(BITRIX_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка при отправке в Bitrix: {e}")

# --- AI-ответ от Петры Грей ---
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
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == 'completed':
            break
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    reply = messages.data[0].content[0].text.value
    return reply

# --- Обработка входящих сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message_text = update.message.text.strip()

    name = user.full_name or "Telegram User"
    phone = "не указан"
    email = "не указан"
    comment = message_text

    write_to_sheet(name, message_text)
    send_to_bitrix(name, phone, email, comment)

    ai_reply = ask_petra(message_text)
    await update.message.reply_text(ai_reply)

# --- Запуск бота ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    app.add_handler(handler)
    app.run_polling()
