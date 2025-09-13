import os
import json
import random
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
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- Config ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PAYPAL_BASE = "https://www.paypal.me/AnnaComfy972"
ADMIN_PASSWORD = "1974"

# --- Conversation States ---
ASK_PASSWORD, VOUCHER_PROVIDER, VOUCHER_CODE = range(3)

# --- Nutzer + Gutscheine ---
USER_FILE = "users.json"
VOUCHER_FILE = "vouchers.json"

def load_users():
    try:
        with open(USER_FILE, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(list(users), f)

def load_vouchers():
    try:
        with open(VOUCHER_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_vouchers(vouchers):
    with open(VOUCHER_FILE, "w") as f:
        json.dump(vouchers, f)

users_set = load_users()
vouchers = load_vouchers()

# --- Telegram App ---
application = Application.builder().token(BOT_TOKEN).updater(None).build()

# --- Vorschau Bilder ---
klein_vorschau = ["Vorschau-klein.png", "Vorschau-klein2.png"]
gross_vorschau = ["Vorschau-gross.jpeg", "Vorschau-gross2.jpeg", "Vorschau-gross3.jpeg"]

# --- Preisliste Bilder ---
klein_preise = ["Preisliste-klein.jpeg", "Preisliste-klein2.jpeg", "Preisliste-klein3(Haupt).jpeg"]
gross_preise = ["Preisliste-gross.jpeg", "Preisliste-gross2.jpeg", "Preisliste-gross3.jpeg"]

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_set.add(update.effective_user.id)
    save_users(users_set)
    keyboard = [
        [InlineKeyboardButton("Vorschau", callback_data="preview")],
        [InlineKeyboardButton("Preise", callback_data="prices")],
    ]
    await update.message.reply_text("Willkommen! Wähle:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Button Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # Vorschau Flow
    if data == "preview":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="preview_small")],
            [InlineKeyboardButton("Große Schwester", callback_data="preview_big")],
            [InlineKeyboardButton("Zurück", callback_data="back_main")],
        ]
        await q.edit_message_text("Wähle eine Schwester:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "preview_small":
        bild = random.choice(klein_vorschau)
        await context.bot.send_photo(
            chat_id=q.message.chat_id,
            photo=f"https://raw.githubusercontent.com/<USERNAME>/<REPO>/main/image/{bild}",
            caption="Kleine Schwester"
        )
    elif data == "preview_big":
        bild = random.choice(gross_vorschau)
        await context.bot.send_photo(
            chat_id=q.message.chat_id,
            photo=f"https://raw.githubusercontent.com/<USERNAME>/<REPO>/main/image/{bild}",
            caption="Große Schwester"
        )
    elif data == "back_main":
        keyboard = [
            [InlineKeyboardButton("Vorschau", callback_data="preview")],
            [InlineKeyboardButton("Preise", callback_data="prices")],
        ]
        await q.edit_message_text("Willkommen! Wähle:", reply_markup=InlineKeyboardMarkup(keyboard))

    # Preise Flow
    elif data == "prices":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="prices_small")],
            [InlineKeyboardButton("Große Schwester", callback_data="prices_big")],
            [InlineKeyboardButton("Zurück", callback_data="back_main")],
        ]
        await q.edit_message_text("Wähle eine Schwester:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["prices_small", "prices_big"]:
        global selected_sister
        selected_sister = "klein" if data == "prices_small" else "gross"
        keyboard = [
            [InlineKeyboardButton("Bilder", callback_data="type_images")],
            [InlineKeyboardButton("Videos", callback_data="type_videos")],
            [InlineKeyboardButton("Zurück", callback_data="prices")],
        ]
        await q.edit_message_text("Wähle Art des Angebots:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["type_images", "type_videos"]:
        global selected_type
        selected_type = "bilder" if data == "type_images" else "videos"

        # Angebot Buttons nach Schwester + Typ
        offers = []
        if selected_type == "videos" and selected_sister == "gross":
            offers = [(10, 15), (25, 25), (35, 30)]
        elif selected_type == "videos" and selected_sister == "klein":
            offers = [(10, 20), (25, 30), (35, 40)]
        elif selected_type == "bilder" and selected_sister == "gross":
            offers = [(10, 5), (25, 10), (35, 15)]
        elif selected_type == "bilder" and selected_sister == "klein":
            offers = [(10, 10), (25, 15), (35, 20)]

        keyboard = []
        for amount, price in offers:
            keyboard.append([
                InlineKeyboardButton(f"PayPal {price}€", url=f"{PAYPAL_BASE}/{price}"),
                InlineKeyboardButton("Mit Gutschein", callback_data=f"voucher_{selected_sister}_{selected_type}_{amount}")
            ])
        keyboard.append([InlineKeyboardButton("Zurück", callback_data=f"prices_{selected_sister}")])
        await q.edit_message_text("Wähle dein Angebot:", reply_markup=InlineKeyboardMarkup(keyboard))

    # Gutschein Flow
    elif data.startswith("voucher_"):
        parts = data.split("_")
        context.user_data["voucher_info"] = {"sister": parts[1], "type": parts[2], "amount": parts[3]}
        await context.bot.send_message(chat_id=q.message.chat_id, text="Gib den Anbieter des Gutscheins ein:")
        return VOUCHER_PROVIDER

# --- Gutschein Handler ---
async def voucher_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["voucher_info"]["provider"] = update.message.text
    await update.message.reply_text("Gib den Gutscheincode ein:")
    return VOUCHER_CODE

async def voucher_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = context.user_data["voucher_info"]
    provider = info["provider"]
    code = update.message.text
    if provider not in vouchers:
        vouchers[provider] = []
    vouchers[provider].append(code)
    save_vouchers(vouchers)
    await update.message.reply_text("✅ Gutschein gespeichert!")
    return ConversationHandler.END

# --- Admin ---
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bitte gib das Admin-Passwort ein:")
    return ASK_PASSWORD

async def admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == ADMIN_PASSWORD:
        count = len(users_set)
        msg = f"✅ Passwort korrekt!\nDer Bot hat bisher mit {count} Nutzern interagiert.\n\nGespeicherte Gutscheine:\n"
        for provider, codes in vouchers.items():
            msg += f"{provider}: {', '.join(codes)}\n"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Falsches Passwort! Zugriff verweigert.")
    return ConversationHandler.END

# --- Registrieren ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))

conv = ConversationHandler(
    entry_points=[CommandHandler('admin', admin_start)],
    states={
        ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_password)],
        VOUCHER_PROVIDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, voucher_provider)],
        VOUCHER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, voucher_code)]
    },
    fallbacks=[]
)
application.add_handler(conv)

# --- FastAPI Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    async with application:
        await application.start()
        yield
        await application.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    body = await request.json()
    update = Update.de_json(body, application.bot)
    await application.process_update(update)
    return Response(status_code=HTTPStatus.OK)

@app.get("/")
async def root():
    return {"status": "ok", "note": "Telegram Bot läuft"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
