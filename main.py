import os
import json
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
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
GITHUB_USER = os.getenv("GITHUB_USER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
PAYPAL_BASE = "https://www.paypal.me/AnnaComfy972"
ADMIN_PASSWORD = "1974"

# --- Conversation States ---
START_STEP, ASK_PASSWORD, VOUCHER_PROVIDER, VOUCHER_CODE = range(4)

# --- Nutzer + Gutscheine ---
USER_FILE = "users.json"
VOUCHER_FILE = "vouchers.json"

def load_users():
    try:
        with open(USER_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(list(users), f)

def load_vouchers():
    try:
        with open(VOUCHER_FILE, "r") as f:
            return json.load(f)
    except:
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

# --- /start Schritt 1 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_set.add(update.effective_user.id)
    save_users(users_set)
    text = (
        "Willkommen! 🛒\n\n"
        "Hier werden Inhalte von zwei Schwestern verkauft:\n"
        "• Große Schwester – Level 16\n"
        "• Kleine Schwester – Level 14\n\n"
        "Drücke 'Weiter', um fortzufahren."
    )
    keyboard = [[InlineKeyboardButton("Weiter", callback_data="start_next")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return START_STEP

# --- Start Schritt 2: Vorschau / Preise ---
async def start_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    keyboard = [
        [InlineKeyboardButton("Vorschau", callback_data="preview")],
        [InlineKeyboardButton("Preise", callback_data="prices")],
    ]
    await q.edit_message_text("Wähle, was du sehen möchtest:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# --- Button Handler für Vorschau / Preise / Gutschein ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # Vorschau Auswahl
    if data == "preview":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="preview_small")],
            [InlineKeyboardButton("Große Schwester", callback_data="preview_big")],
            [InlineKeyboardButton("Zurück", callback_data="start_next")],
        ]
        await q.edit_message_text("Wähle eine Schwester für die Vorschau:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "preview_small":
        bild = random.choice(klein_vorschau)
        await context.bot.send_photo(
            chat_id=q.message.chat_id,
            photo=f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/image/{bild}",
            caption="Kleine Schwester Vorschau"
        )

    elif data == "preview_big":
        bild = random.choice(gross_vorschau)
        await context.bot.send_photo(
            chat_id=q.message.chat_id,
            photo=f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/image/{bild}",
            caption="Große Schwester Vorschau"
        )

    # Preise Auswahl
    elif data == "prices":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="prices_small")],
            [InlineKeyboardButton("Große Schwester", callback_data="prices_big")],
            [InlineKeyboardButton("Zurück", callback_data="start_next")],
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

# --- Gutschein Flow ---
async def voucher_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    context.user_data["voucher_info"] = {"sister": parts[1], "type": parts[2], "amount": parts[3]}
    
    keyboard = [
        [InlineKeyboardButton("Amazon", callback_data="voucher_provider_Amazon")],
        [InlineKeyboardButton("PaySafe", callback_data="voucher_provider_PaySafe")],
    ]
    await q.edit_message_text("Wähle den Anbieter des Gutscheins:", reply_markup=InlineKeyboardMarkup(keyboard))
    return VOUCHER_PROVIDER

async def voucher_provider_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    provider = q.data.split("_")[-1]
    context.user_data["voucher_info"]["provider"] = provider
    await context.bot.send_message(q.message.chat_id, f"Gib jetzt den Gutscheincode für {provider} ein:")
    return VOUCHER_CODE

async def voucher_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = context.user_data["voucher_info"]
    provider = info["provider"]
    code = update.message.text
    if provider not in vouchers:
        vouchers[provider] = []
    vouchers[provider].append(code)
    save_vouchers(vouchers)
    await update.message.reply_text(f"✅ Gutschein für {provider} gespeichert!")
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

# --- Handler registrieren ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(CallbackQueryHandler(voucher_start, pattern=r'^voucher_'))

conv = ConversationHandler(
    entry_points=[CommandHandler('admin', admin_start),
                  CallbackQueryHandler(voucher_start, pattern=r'^voucher_')],
    states={
        START_STEP: [CallbackQueryHandler(start_next, pattern="start_next")],
        ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_password)],
        VOUCHER_PROVIDER: [CallbackQueryHandler(voucher_provider_choice, pattern=r'^voucher_provider_')],
        VOUCHER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, voucher_code)],
    },
    fallbacks=[]
)
application.add_handler(conv)

# --- FastAPI + Webhook ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await application.bot.set_webhook(url=f"{WEBHOOK_URL.rstrip('/')}/webhook")
    async with application:
        await application.start()
        yield
        await application.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    body = await request.json()
    update = Update.de_json(body, application.bot)
    await application.update_queue.put(update)
    return Response(status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
