import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Функция отправки лида в Bitrix24
def send_to_bitrix(name, phone, email, comment):
    url = "https://b24-lvtdlr.bitrix24.ru/rest/1/r58xfu33csoc2m4y/crm.lead.add.json"
    data = {
        "fields": {
            "NAME": name,
            "PHONE": [{"VALUE": phone}],
            "EMAIL": [{"VALUE": email}],
            "COMMENTS": comment,
            "SOURCE_ID": "WEB"
        }
    }

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
    except Exception as e:
        print("Ошибка при отправке в Bitrix:", e)

# Обработка входящего сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message_text = update.message.text

    name = user.full_name or "Telegram User"
    phone = "+79998887766"  # Можем позже сделать сбор через этапы
    email = "telegram@user.com"  # Можно оставить заглушкой
    comment = f"Сообщение от пользователя: {message_text}"

    send_to_bitrix(name, phone, email, comment)

    await update.message.reply_text("Спасибо! Мы свяжемся с тобой в ближайшее время 💬")

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    app.add_handler(handler)
    app.run_polling()
