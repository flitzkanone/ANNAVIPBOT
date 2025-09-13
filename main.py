import os
import json
import random
import asyncio
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = "1974"
PAYPAL_BASE = "https://www.paypal.me/AnnaComfy972"

USER_FILE = "users.json"
VOUCHER_FILE = "vouchers.json"

ASK_PASSWORD, VOUCHER_PROVIDER, VOUCHER_CODE = range(3)

users_set = set()
vouchers = {}

# Für letzte Nachricht pro Chat (wird gelöscht, bevor neue gesendet wird)
last_message = {}

def load_users():
    global users_set
    try:
        with open(USER_FILE, "r") as f:
            users_set = set(json.load(f))
    except:
        users_set = set()

def save_users():
    with open(USER_FILE, "w") as f:
        json.dump(list(users_set), f)

def load_vouchers():
    global vouchers
    try:
        with open(VOUCHER_FILE, "r") as f:
            vouchers = json.load(f)
    except:
        vouchers = {}

def save_vouchers():
    with open(VOUCHER_FILE, "w") as f:
        json.dump(vouchers, f)

load_users()
load_vouchers()

# Bilder
klein_vorschau = ["Vorschau-klein.png", "Vorschau-klein2.png"]
gross_vorschau = ["Vorschau-gross.jpeg", "Vorschau-gross2.jpeg", "Vorschau-gross3.jpeg"]

selected_sister = None
selected_type = None

application = Application.builder().token(BOT_TOKEN).build()

# Hilfsfunktion: lösche alte Nachricht
async def delete_last(chat_id, context):
    if chat_id in last_message:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_message[chat_id])
        except:
            pass

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_set.add(update.effective_user.id)
    save_users()
    
    chat_id = update.message.chat_id
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
    msg = await q.edit_message_text("Wähle, was du sehen möchtest:", reply_markup=InlineKeyboardMarkup(keyboard))
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
    msg = await q.edit_message_text("Wähle eine Schwester für die Vorschau:", reply_markup=InlineKeyboardMarkup(keyboard))
    last_message[chat_id] = msg.message_id

async def preview_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    await delete_last(chat_id, context)
    
    bild = random.choice(klein_vorschau if q.data == "preview_small" else gross_vorschau)
    caption = "Kleine Schwester Vorschau" if q.data == "preview_small" else "Große Schwester Vorschau"
    
    msg = await context.bot.send_photo(
        chat_id=chat_id,
        photo=f"https://raw.githubusercontent.com/{os.getenv('GITHUB_USER')}/{os.getenv('GITHUB_REPO')}/main/image/{bild}",
        caption=caption,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Zurück", callback_data="preview")]])
    )
    last_message[chat_id] = msg.message_id

# --- Admin ---
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await delete_last(chat_id, context)
    await update.message.reply_text("🔒 Bitte gib das Admin-Passwort ein:")
    return ASK_PASSWORD

async def admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if update.message.text == ADMIN_PASSWORD:
        temp_msg = await update.message.reply_text("✅ Passwort korrekt! Lade Daten…")
        await asyncio.sleep(1.5)
        await delete_last(chat_id, context)
        
        user_count = len(users_set)
        msg = f"📊 Admin-Daten:\nBenutzer insgesamt: {user_count}\nGutscheine:\n"
        for provider, codes in vouchers.items():
            msg += f"- {provider}: {', '.join(codes)}\n"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Falsches Passwort! Zugriff verweigert.")
    
    return ConversationHandler.END

conv_admin = ConversationHandler(
    entry_points=[CommandHandler('admin', admin_start)],
    states={ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_password)]},
    fallbacks=[]
)

application.add_handler(conv_admin)

# --- CallbackHandler Vorschau ---
application.add_handler(CallbackQueryHandler(preview, pattern="^preview$"))
application.add_handler(CallbackQueryHandler(preview_show, pattern="^preview_(small|big)$"))

# --- Start ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(start_next, pattern="^start_next$"))

# --- Gutschein und Preise würden nach dem gleichen Prinzip implementiert werden ---
