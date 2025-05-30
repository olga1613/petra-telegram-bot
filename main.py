import os
import json
import re
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

def write_to_sheet(name, text, username, user_id):
    worksheet = connect_to_sheet()
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    worksheet.append_row([name, text, date, username or "—", str(user_id), ""])

def get_user_row_by_id(user_id):
    worksheet = connect_to_sheet()
    ids = worksheet.col_values(5)  # 5-я колонка — Telegram ID
    for index, val in enumerate(ids):
        if val == str(user_id):
            return index + 1  # gspread строки начинаются с 1
    return None

def mark_sent_to_bitrix(row_index):
    worksheet = connect_to_sheet()
    worksheet.update_cell(row_index, 6, "Да")  # 6-я колонка — отметка о Bitrix

# --- Bitrix ---
def send_to_bitrix(name, phone, email, comment, username):
    full_comment = f"Сообщение из Telegram: {comment}"
    if username:
        full_comment += f"\nНик: @{username}"

    payload = {
        "fields": {
            "NAME": name,
            "PHONE": [{"VALUE": phone}],
            "EMAIL": [{"VALUE": email}],
            "COMMENTS": full_comment,
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

# --- Извлечение имени ---
def extract_name(text):
    # Ищем первое имя с заглавной буквы, игнорируя слова типа "я", "меня зовут", "привет"
    text = text.lower()
    match = re.search(r"(?:я|меня зовут|привет|давай|это)?[\s,:-]*([А-ЯЁA-Z][а-яёa-z]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    return text.strip().split()[0].capitalize()

# --- Приветствие при /start ---
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_state[chat_id] = {"stage": "ask_name"}
    greeting = (
        "Привет! Я Петра, ассистентка Ольги.\n"
        "Здесь нет туров по шаблону — у нас живые приключения для умных и свободных.\n"
        "Если хочешь, помогу понять, подойдёт ли тебе такой формат, расскажу, как всё устроено и что интересного будет в ближайшее время.\n\n"
        "Как тебя зовут?"
    )
    await update.message.reply_text(greeting)

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user = update.message.from_user
    user_message = update.message.text
    username = user.username or "—"
    user_id = user.id

    # Извлекаем имя, если на этапе знакомства
    if chat_id in user_state and user_state[chat_id].get("stage") == "ask_name":
        user_name = extract_name(user_message)
        user_state[chat_id]["name"] = user_name
        user_state[chat_id]["stage"] = "chat"
        await update.message.reply_text(
            f"Красиво. Приятно познакомиться, {user_name} 🙂\n"
            "Что тебе рассказать о нашем пространстве? Ты можешь задать любой вопрос."
        )
        # Запись приветственного сообщения в таблицу
        try:
            write_to_sheet(user_name, user_message, username, user_id)
        except Exception as e:
            print("Ошибка записи в таблицу:", e)
        return

    user_name = user_state.get(chat_id, {}).get("name") or user.full_name or "Telegram User"

    # Всегда записываем в Google Таблицу
    try:
        write_to_sheet(user_name, user_message, username, user_id)
    except Exception as e:
        print("Ошибка записи в таблицу:", e)

    # Отправляем в Bitrix только один раз
    try:
        row_index = get_user_row_by_id(user_id)
        if row_index is not None:
            worksheet = connect_to_sheet()
            flag = worksheet.cell(row_index, 6).value
            if flag != "Да":
                send_to_bitrix(user_name, "+79998887766", "telegram@user.com", user_message, username)
                mark_sent_to_bitrix(row_index)
        else:
            send_to_bitrix(user_name, "+79998887766", "telegram@user.com", user_message, username)
            write_to_sheet(user_name, user_message, username, user_id)
            new_index = get_user_row_by_id(user_id)
            if new_index:
                mark_sent_to_bitrix(new_index)
    except Exception as e:
        print("Ошибка Bitrix:", e)

    # AI-ответ
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
