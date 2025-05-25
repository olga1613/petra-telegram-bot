import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Bitrix webhook (вставлен твой готовый) ---
BITRIX_URL = "https://b24-lvtdlr.bitrix24.ru/rest/1/r58xfu33csoc2m4y/crm.lead.add.json"

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
        response = requests.post(BITRIX_URL, json=payload)
        return response.json()
    except Exception as e:
        print("Ошибка при отправке в Bitrix:", e)
        return None

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message_text = update.message.text

    name = user.full_name or "Telegram User"
    phone = "+79998887766"  # Можем позже спрашивать у пользователя
    email = "telegram@user.com"
    comment = f"Сообщение из Telegram: {message_text}"

    send_to_bitrix(name, phone, email, comment)

    await update.message.reply_text("Спасибо! Я передала твою заявку в Bitrix 💼")

# --- Запуск бота ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    app.add_handler(handler)
    app.run_polling()
