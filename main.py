import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from openai import OpenAI
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import requests
import asyncio

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
BITRIX_WEBHOOK_URL = os.getenv("BITRIX_WEBHOOK_URL")

client = OpenAI(api_key=OPENAI_API_KEY)
user_state = {}

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

def user_already_registered(name):
    worksheet = connect_to_sheet()
    users = worksheet.col_values(1)
    return name in users

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
        print("✅ Bitrix:", response.status_code)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Bitrix error: {e}")
        return False

# --- Приветствие при /start ---
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_state[chat_id] = {"stage": "ask_name"}
    greeting = (
        "Привет! Я Петра, ассистентка Ольги.\n"
        "Здесь нет туров по шаблону — у нас живые приключения для умных и свободных.\n"
        "Если хочешь, помогу понять, подойдёт ли тебе такой формат, расскажу, как всё устроено и что интересного будет в ближайшее время.\n\n"
        "Можем просто поговорить 🙂\n"
        "Как тебя зовут, чтобы я знала, как обращаться?"
    )
    await update.message.reply_text(greeting)

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user = update.message.from_user
    user_message = update.message.text

    if chat_id in user_state and user_state[chat_id].get("stage") == "ask_name":
        user_name = user_message
        user_state[chat_id]["name"] = user_name
        user_state[chat_id]["stage"] = "chat"
        await update.message.reply_text(
            f"Красиво. Приятно познакомиться, {user_name} 🙂\n"
            "Что тебе рассказать о нашем пространстве? Ты можешь задать любой вопрос."
        )
        return

    user_name = user.full_name or "Telegram User"

    try:
        write_to_sheet(user_name, user_message)
    except Exception as e:
        print("Ошибка записи в таблицу:", e)

    try:
        if not user_already_registered(user_name):
            phone = "+79998887766"
            email = "telegram@user.com"
            send_to_bitrix(user_name, phone, email, user_message)
    except Exception as e:
        print("Ошибка Bitrix:", e)

    thread = client.beta.threads.create()
    client.beta.threads.messages.create(thread.id, role="user", content=user_message)
    run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=ASSISTANT_ID)

    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            break
        await asyncio.sleep(1)

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    reply = messages.data[0].content[0].text.value
    await update.message.reply_text(reply)

# --- Запуск ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling() 
