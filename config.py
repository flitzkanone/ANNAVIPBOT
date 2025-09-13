import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus der .env-Datei (für lokale Entwicklung)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
PAYPAL_LINK = os.getenv("PAYPAL_LINK", "https://paypal.me/example")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not all([BOT_TOKEN, ADMIN_PASSWORD, ADMIN_CHAT_ID]):
    raise ValueError("Bitte setze BOT_TOKEN, ADMIN_PASSWORD und ADMIN_CHAT_ID in den Umgebungsvariablen.")
