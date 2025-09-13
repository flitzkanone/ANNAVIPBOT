import os
import json
import random
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# --- Config / Env Variables ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GITHUB_USER = os.getenv("GITHUB_USER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
PAYPAL_BASE = "https://www.paypal.me/AnnaComfy972"
ADMIN_PASSWORD = "1974"

# --- Conversation States ---
ASK_PASSWORD, VOUCHER_PROVIDER, VOUCHER_CODE = range(3)

# --- User + Voucher Data ---
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

# --- Vorschau Bilder ---
klein_vorschau = ["Vorschau-klein.png", "Vorschau-klein2.png"]
gross_vorschau = ["Vorschau-gross.jpeg", "Vorschau-gross2.jpeg", "Vorschau-gross3.jpeg"]

# --- Preisliste Bilder ---
klein_preise = ["Preisliste-klein.jpeg", "Preisliste-klein2.jpeg", "Preisliste-klein3(Haupt).jpeg"]
gross_preise = ["Preisliste-gross.jpeg", "Preisliste-gross2.jpeg", "Preisliste-gross3.jpeg"]

# --- Telegram Application ---
application = Application.builder().token(BOT_TOKEN).build()

# --- FastAPI App ---
app = FastAPI()

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_set.add(update.effective_user.id)
    save_users(users_set)

    keyboard = [[InlineKeyboardButton("▶ Weiter", callback_data="start_next")]]
    await update.message.reply_text(
        "Willkommen!\nHier werden Inhalte von kleinen (14) und großen Schwestern (16) verkauft.\n\nDrücke Weiter, um fortzufahren.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Button Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # Alte Nachricht löschen
    try:
        await q.message.delete()
    except:
        pass

    data = q.data

    # Start weiter
    if data == "start_next":
        keyboard = [
            [InlineKeyboardButton("Vorschau", callback_data="preview")],
            [InlineKeyboardButton("Preise", callback_data="prices")]
        ]
        await context.bot.send_message(chat_id=q.message.chat_id, text="Wähle:", reply_markup=InlineKeyboardMarkup(keyboard))

    # Vorschau
    elif data == "preview":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="preview_small")],
            [InlineKeyboardButton("Große Schwester", callback_data="preview_big")],
            [InlineKeyboardButton("⬅ Zurück", callback_data="start_next")]
        ]
        await context.bot.send_message(chat_id=q.message.chat_id, text="Wähle eine Schwester:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "preview_small":
        bild = random.choice(klein_vorschau)
        keyboard = [[InlineKeyboardButton("⬅ Zurück", callback_data="preview")]]
        await context.bot.send_photo(
            chat_id=q.message.chat_id,
            photo=f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/image/{bild}",
            caption="Kleine Schwester",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "preview_big":
        bild = random.choice(gross_vorschau)
        keyboard = [[InlineKeyboardButton("⬅ Zurück", callback_data="preview")]]
        await context.bot.send_photo(
            chat_id=q.message.chat_id,
            photo=f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/image/{bild}",
            caption="Große Schwester",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Preise
    elif data == "prices":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="prices_small")],
            [InlineKeyboardButton("Große Schwester", callback_data="prices_big")],
            [InlineKeyboardButton("⬅ Zurück", callback_data="start_next")]
        ]
        await context.bot.send_message(chat_id=q.message.chat_id, text="Wähle eine Schwester:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["prices_small", "prices_big"]:
        context.user_data["selected_sister"] = "klein" if data=="prices_small" else "gross"
        keyboard = [
            [InlineKeyboardButton("Bilder", callback_data="type_images")],
            [InlineKeyboardButton("Videos", callback_data="type_videos")],
            [InlineKeyboardButton("⬅ Zurück", callback_data="prices")]
        ]
        await context.bot.send_message(chat_id=q.message.chat_id, text="Wähle Art des Angebots:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["type_images", "type_videos"]:
        sister = context.user_data["selected_sister"]
        typ = "bilder" if data=="type_images" else "videos"

        # Angebote
        offers = []
        if typ=="videos" and sister=="gross": offers = [(10,15),(25,25),(35,30)]
        elif typ=="videos" and sister=="klein": offers = [(10,20),(25,30),(35,40)]
        elif typ=="bilder" and sister=="gross": offers = [(10,5),(25,10),(35,15)]
        elif typ=="bilder" and sister=="klein": offers = [(10,10),(25,15),(35,20)]

        keyboard = [[InlineKeyboardButton(f"PayPal {p}€", url=f"{PAYPAL_BASE}/{p}"),
                     InlineKeyboardButton("Mit Gutschein", callback_data=f"voucher_{sister}_{typ}_{a}")]
                    for a,p in offers]
        keyboard.append([InlineKeyboardButton("⬅ Zurück", callback_data="prices_"+sister)])
        await context.bot.send_message(chat_id=q.message.chat_id, text="Wähle dein Angebot:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("voucher_"):
        parts = data.split("_")
        context.user_data["voucher_info"] = {"sister": parts[1], "type": parts[2], "amount": parts[3]}
        await context.bot.send_message(chat_id=q.message.chat_id, text="Gib den Anbieter des Gutscheins ein: ⏳")
        return VOUCHER_PROVIDER

# --- Gutschein Flow ---
async def voucher_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["voucher_info"]["provider"] = update.message.text
    await update.message.reply_text("Gib den Gutscheincode ein: ⏳")
    return VOUCHER_CODE

async def voucher_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = context.user_data["voucher_info"]
    provider = info["provider"]
    code = update.message.text
    if provider not in vouchers: vouchers[provider] = []
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
        await update.message.reply_text("❌ Falsches Passwort!")
    return ConversationHandler.END

# --- Registrieren ---
application.add_handler(CommandHandler("start", start))
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
application.add_handler(CallbackQueryHandler(button_handler))

# --- FastAPI Webhook ---
@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
    await application.update_queue.put(update)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=WEBHOOK_URL)

@app.on_event("shutdown")
async def on_shutdown():
    await application.stop()
    await application.shutdown()
