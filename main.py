# main.py
# Minimaler Telegram Bot (python-telegram-bot v20 style) mit FastAPI Webhook
# Env vars needed: BOT_TOKEN, WEBHOOK_URL (z.B. https://your-app.onrender.com), optional PAYPAL_LINK

import os
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
import uvicorn

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# --- Konfig (aus Umgebungsvariablen laden) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN fehlt. Setze die Umgebungsvariable BOT_TOKEN.")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL fehlt. Setze die Umgebungsvariable WEBHOOK_URL (z.B. https://meinservice.onrender.com).")
WEBHOOK_URL = WEBHOOK_URL.rstrip("/")  # ohne abschließenden Slash

PAYPAL_LINK = os.getenv("PAYPAL_LINK", "https://www.paypal.com/")  # optional, kann durch eigenes ersetzt werden

# --- Telegram Application (ohne Updater, da Webhook) ---
application = Application.builder().updater(None).token(BOT_TOKEN).build()

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Vorschau", callback_data="preview")],
        [InlineKeyboardButton("Kaufen (PayPal)", url=PAYPAL_LINK)],
    ]
    await update.message.reply_text("Willkommen! Wähle:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if q.data == "preview":
        await q.edit_message_text("Das ist die Vorschau ✅")

# Registriere Handler
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))

# --- FastAPI Lifespan: set webhook + start/stop PTB application ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setze Telegram Webhook (Telegram schickt nun Updates an: WEBHOOK_URL + /webhook)
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    # Start the PTB application context (initialisiert intern z.B. http-Clients)
    async with application:
        await application.start()
        yield
        await application.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Endpoint für Telegram (POST)."""
    body = await request.json()
    update = Update.de_json(body, application.bot)
    # PTB verarbeitet das Update (Handler werden aufgerufen)
    await application.process_update(update)
    return Response(status_code=HTTPStatus.OK)

@app.get("/")
async def root():
    return {"status": "ok", "note": "Telegram bot läuft (FastAPI)"}  # einfache Health-Route

# Nur für lokale Tests (nicht nötig in Render/Gunicorn)
if __name__ == "__main__":
    # Zum lokalen Testen: uvicorn main:app --reload
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
