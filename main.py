import os
import json
import random
import asyncio
from fastapi import FastAPI, Request
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
GITHUB_USER = os.getenv("GITHUB_USER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
PAYPAL_BASE = "https://www.paypal.me/AnnaComfy972"
ADMIN_PASSWORD = "1974"

USER_FILE = "users.json"
VOUCHER_FILE = "vouchers.json"
ASK_PASSWORD, VOUCHER_PROVIDER, VOUCHER_CODE = range(3)

# --- Daten Laden ---
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
last_message = {}  # letzte Nachricht pro Chat

# --- Bilder ---
klein_vorschau = ["Vorschau-klein.png", "Vorschau-klein2.png"]
gross_vorschau = ["Vorschau-gross.jpeg", "Vorschau-gross2.jpeg", "Vorschau-gross3.jpeg"]

# --- Telegram App ---
application = Application.builder().token(BOT_TOKEN).build()

# --- Helper ---
async def delete_last(chat_id, context):
    if chat_id in last_message:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_message[chat_id])
        except:
            pass

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    users_set.add(chat_id)
    save_users(users_set)
    await delete_last(chat_id, context)

    text = (
        "Willkommen! 🛒\n\n"
        "Hier werden Inhalte von zwei Schwestern verkauft:\n"
        "• Große Schwester – Level 16\n"
        "• Kleine Schwester – Level 14\n\n"
        "Drücke 'Weiter', um fortzufahren."
    )
    keyboard = [[InlineKeyboardButton("Weiter", callback_data="start_next")]]
    msg = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    last_message[chat_id] = msg.message_id

async def start_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    await delete_last(chat_id, context)

    keyboard = [
        [InlineKeyboardButton("Vorschau", callback_data="preview")],
        [InlineKeyboardButton("Preise", callback_data="prices")]
    ]
    msg = await q.edit_message_text("Wähle:", reply_markup=InlineKeyboardMarkup(keyboard))
    last_message[chat_id] = msg.message_id

# --- Vorschau ---
async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    await delete_last(chat_id, context)

    keyboard = [
        [InlineKeyboardButton("Kleine Schwester", callback_data="preview_small")],
        [InlineKeyboardButton("Große Schwester", callback_data="preview_big")],
        [InlineKeyboardButton("Zurück", callback_data="start_next")]
    ]
    msg = await q.edit_message_text("Wähle eine Schwester:", reply_markup=InlineKeyboardMarkup(keyboard))
    last_message[chat_id] = msg.message_id

async def preview_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    await delete_last(chat_id, context)

    bild_list = klein_vorschau if q.data == "preview_small" else gross_vorschau
    bild = random.choice(bild_list)
    caption = "Kleine Schwester" if q.data == "preview_small" else "Große Schwester"

    msg = await context.bot.send_photo(
        chat_id=chat_id,
        photo=f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/image/{bild}",
        caption=caption,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Zurück", callback_data="preview")]])
    )
    last_message[chat_id] = msg.message_id

# --- Preise & Gutschein ---
async def prices_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    await delete_last(chat_id, context)

    keyboard = [
        [InlineKeyboardButton("Kleine Schwester", callback_data="prices_small")],
        [InlineKeyboardButton("Große Schwester", callback_data="prices_big")],
        [InlineKeyboardButton("Zurück", callback_data="start_next")]
    ]
    msg = await q.edit_message_text("Wähle eine Schwester:", reply_markup=InlineKeyboardMarkup(keyboard))
    last_message[chat_id] = msg.message_id

# Preise auswählen
async def offer_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    global selected_sister
    selected_sister = "klein" if q.data == "prices_small" else "gross"
    await delete_last(chat_id, context)

    keyboard = [
        [InlineKeyboardButton("Bilder", callback_data="type_images")],
        [InlineKeyboardButton("Videos", callback_data="type_videos")],
        [InlineKeyboardButton("Zurück", callback_data="prices")]
    ]
    msg = await q.edit_message_text("Wähle Art des Angebots:", reply_markup=InlineKeyboardMarkup(keyboard))
    last_message[chat_id] = msg.message_id

# Angebot Buttons
async def offer_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    global selected_type
    selected_type = "bilder" if q.data == "type_images" else "videos"
    await delete_last(chat_id, context)

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
    msg = await q.edit_message_text("Wähle dein Angebot:", reply_markup=InlineKeyboardMarkup(keyboard))
    last_message[chat_id] = msg.message_id

# Gutschein Flow
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
    chat_id = update.message.chat_id
    await delete_last(chat_id, context)
    await update.message.reply_text("🔒 Bitte gib das Admin-Passwort ein:")
    return ASK_PASSWORD

async def admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if update.message.text == ADMIN_PASSWORD:
        temp_msg = await update.message.reply_text("⏳ Lade Daten…")
        await asyncio.sleep(1)
        await delete_last(chat_id, context)
        msg = f"📊 Admin-Daten:\nBenutzer insgesamt: {len(users_set)}\nGutscheine:\n"
        for provider, codes in vouchers.items():
            msg += f"- {provider}: {', '.join(codes)}\n"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Falsches Passwort! Zugriff verweigert.")
    return ConversationHandler.END

# --- Handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(start_next, pattern="^start_next$"))
application.add_handler(CallbackQueryHandler(preview, pattern="^preview$"))
application.add_handler(CallbackQueryHandler(preview_show, pattern="^preview_(small|big)$"))
application.add_handler(CallbackQueryHandler(prices_menu, pattern="^prices$"))
application.add_handler(CallbackQueryHandler(offer_type, pattern="^prices_(small|big)$"))
application.add_handler(CallbackQueryHandler(offer_select, pattern="^type_(images|videos)$"))

conv_admin = ConversationHandler(
    entry_points=[CommandHandler('admin', admin_start)],
    states={
        ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_password)],
        VOUCHER_PROVIDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, voucher_provider)],
        VOUCHER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, voucher_code)]
    },
    fallbacks=[]
)
application.add_handler(conv_admin)

# --- FastAPI für Webhook ---
app = FastAPI()

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
    await application.bot.set_webhook(url=os.getenv("WEBHOOK_URL"))

@app.on_event("shutdown")
async def on_shutdown():
    await application.stop()
    await application.shutdown()
