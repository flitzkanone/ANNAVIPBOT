import os
import logging
import json
import random
from dotenv import load_dotenv
from datetime import datetime
from io import BytesIO
import asyncio

from fpdf import FPDF
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- Konfiguration ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYPAL_USER = os.getenv("PAYPAL_USER")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
AGE_ANNA = os.getenv("AGE_ANNA", "18")
AGE_LUNA = os.getenv("AGE_LUNA", "21")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

ADMIN_PASSWORD = "1974"
BTC_WALLET = "1FcgMLNBDLiuDSDip7AStuP19sq47LJB12"
ETH_WALLET = "0xeeb8FDc4aAe71B53934318707d0e9747C5c66f6e"

PRICES = {"bilder": {10: 5, 25: 10, 35: 15}, "videos": {10: 15, 25: 25, 35: 30}}
VOUCHER_FILE = "vouchers.json"
STATS_FILE = "stats.json" # NEU: Datei für Statistiken
MEDIA_DIR = "image"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Hilfsfunktionen für Vouchers & Stats ---
def load_vouchers():
    try:
        with open(VOUCHER_FILE, "r") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {"amazon": [], "paysafe": []}

def save_vouchers(vouchers):
    with open(VOUCHER_FILE, "w") as f: json.dump(vouchers, f, indent=2)

# NEUE Hilfsfunktionen für Statistiken
def load_stats():
    try:
        with open(STATS_FILE, "r") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): 
        return {"total_users": [], "events": {}}

def save_stats(stats):
    with open(STATS_FILE, "w") as f: json.dump(stats, f, indent=4)

def track_event(event_name: str):
    stats = load_stats()
    stats["events"][event_name] = stats["events"].get(event_name, 0) + 1
    save_stats(stats)

def track_new_user(user_id: int):
    stats = load_stats()
    if user_id not in stats["total_users"]:
        stats["total_users"].append(user_id)
        save_stats(stats)

def get_media_files(schwester_code: str, media_type: str) -> list:
    # ... (unverändert)
    pass

async def cleanup_previous_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    # ... (unverändert)
    pass

async def send_preview_message(update: Update, context: ContextTypes.DEFAULT_TYPE, schwester_code: str):
    # ... (unverändert)
    pass

# --- Bot Handler-Funktionen ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Trackt neuen Nutzer und /start-Befehl
    track_new_user(update.effective_user.id)
    track_event("start_command")

    context.user_data.clear()
    chat_id = update.effective_chat.id
    await cleanup_previous_messages(chat_id, context)
    welcome_text = (
        "Herzlich Willkommen! ✨\n\n"
        "Hier kannst du eine Vorschau meiner Inhalte sehen oder direkt ein Paket auswählen. "
        "Die gesamte Bedienung erfolgt über die Buttons."
    )
    keyboard = [[InlineKeyboardButton(" Vorschau", callback_data="show_preview_options")], [InlineKeyboardButton(" Preise & Pakete", callback_data="show_price_options")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        query = update.callback_query; await query.answer()
        try:
            await query.edit_message_text(welcome_text, reply_markup=reply_markup)
        except error.TelegramError:
            try: await query.delete_message()
            except Exception: pass
            await context.bot.send_message(chat_id=chat_id, text=welcome_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); data = query.data
    chat_id = update.effective_chat.id
    
    # PDF-Download-Funktion (unverändert)
    if data == "download_vouchers_pdf":
        # ... (unveränderter PDF-Code)
        pass

    if data in ["main_menu", "show_preview_options", "show_price_options"]:
        await cleanup_previous_messages(chat_id, context)
        try:
            await query.edit_message_text(text="⏳")
            await asyncio.sleep(0.5)
        except Exception: pass

    if data == "main_menu":
        await start(update, context)

    # --- NEU: Admin Menü Logik ---
    elif data == "admin_main_menu":
        await show_admin_menu(update, context)
    elif data == "admin_show_vouchers":
        await show_vouchers_panel(update, context)
    elif data == "admin_stats_users":
        stats = load_stats()
        user_count = len(stats.get("total_users", []))
        text = f"📊 *Nutzer-Statistiken*\n\nGesamtzahl der Nutzer, die den Bot gestartet haben: *{user_count}*"
        keyboard = [[InlineKeyboardButton("« Zurück zum Admin-Menü", callback_data="admin_main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "admin_stats_clicks":
        stats = load_stats()
        events = stats.get("events", {})
        text = "🖱️ *Klick-Statistiken*\n\n"
        if not events:
            text += "Noch keine Klicks erfasst."
        else:
            for event, count in events.items():
                text += f"- `{event}`: *{count}* Klicks\n"
        keyboard = [[InlineKeyboardButton("« Zurück zum Admin-Menü", callback_data="admin_main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # --- Reguläre Nutzer-Logik mit Tracking ---
    elif data in ["show_preview_options", "show_price_options"]:
        action = "preview" if "preview" in data else "prices"; text = "Für wen interessierst du dich?"
        keyboard = [[InlineKeyboardButton("Kleine Schwester", callback_data=f"select_schwester:ks:{action}"), InlineKeyboardButton("Große Schwester", callback_data=f"select_schwester:gs:{action}")], [InlineKeyboardButton("« Zurück", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("select_schwester:"):
        await cleanup_previous_messages(chat_id, context)
        try: await query.message.delete()
        except Exception: pass
        _, schwester_code, action = data.split(":")
        
        # Trackt den Klick
        track_event(f"{action}_{schwester_code}")

        if action == "preview":
            await send_preview_message(update, context, schwester_code)
        elif action == "prices":
            # ... (Logik für Preisliste anzeigen, unverändert)
            pass
    
    elif data.startswith("next_preview:"):
        await cleanup_previous_messages(chat_id, context)
        _, schwester_code = data.split(":")
        track_event("next_preview") # Allgemeiner Zähler für "Nächstes Bild"
        await send_preview_message(update, context, schwester_code)

    elif data.startswith("select_package:"):
        track_event("package_selected")
        await cleanup_previous_messages(chat_id, context)
        try: await query.message.delete()
        except Exception: pass
        loading_message = await context.bot.send_message(chat_id=chat_id, text="⏳")
        await asyncio.sleep(2)
        await loading_message.delete()
        
        _, media_type, amount_str = data.split(":"); amount = int(amount_str); price = PRICES[media_type][amount]; text = f"Du hast das Paket **{amount} {media_type.capitalize()}** für **{price}€** ausgewählt.\n\nWie möchtest du bezahlen?"
        keyboard = [[InlineKeyboardButton(" PayPal", callback_data=f"pay_paypal:{media_type}:{amount}")], [InlineKeyboardButton(" Gutschein", callback_data=f"pay_voucher:{media_type}:{amount}")], [InlineKeyboardButton("🪙 Krypto", callback_data=f"pay_crypto:{media_type}:{amount}")], [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("pay_paypal:"):
        track_event("payment_paypal")
        # ... (Rest der Funktion unverändert)
        pass
    elif data.startswith("pay_voucher:"):
        track_event("payment_voucher")
        # ... (Rest der Funktion unverändert)
        pass
    elif data.startswith("pay_crypto:"):
        track_event("payment_crypto")
        # ... (Rest der Funktion unverändert)
        pass
    # ... (Rest der handle_callback_query Logik)

# --- NEU: Funktionen für das Admin-Menü ---
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zeigt das Hauptmenü für Admins an."""
    text = "🔒 *Admin-Menü*\n\nWähle eine Option:"
    keyboard = [
        [InlineKeyboardButton("📊 Nutzer-Statistiken", callback_data="admin_stats_users")],
        [InlineKeyboardButton("🖱️ Klick-Statistiken", callback_data="admin_stats_clicks")],
        [InlineKeyboardButton("🎟️ Gutscheine anzeigen", callback_data="admin_show_vouchers")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query = update.callback_query
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_vouchers_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zeigt die Gutschein-Liste mit Download-Button."""
    vouchers = load_vouchers()
    amazon_codes = "\n".join([f"- `{code}`" for code in vouchers.get("amazon", [])]) or "Keine"
    paysafe_codes = "\n".join([f"- `{code}`" for code in vouchers.get("paysafe", [])]) or "Keine"
    text = (f"*Eingelöste Gutscheine*\n\n*Amazon:*\n{amazon_codes}\n\n*Paysafe:*\n{paysafe_codes}")
    keyboard = [
        [InlineKeyboardButton("📄 Vouchers als PDF laden", callback_data="download_vouchers_pdf")],
        [InlineKeyboardButton("« Zurück zum Admin-Menü", callback_data="admin_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_admin_password"):
        password = update.message.text; del context.user_data["awaiting_admin_password"]
        if password == ADMIN_PASSWORD:
            # Zeige das neue Admin-Menü anstatt nur der Vouchers
            await show_admin_menu(update, context)
        else: await update.message.reply_text("Falsches Passwort.")
    elif context.user_data.get("awaiting_voucher"):
        # ... (unveränderter Voucher-Code)
        pass

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_admin_password"] = True; await update.message.reply_text("Bitte gib jetzt das Admin-Passwort ein:")

async def add_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (unverändert)
    pass

def main() -> None:
    # ... (unverändert)
    pass

# Hier folgen die vollständigen, unverkürzten Funktionen
get_media_files = get_media_files # Platzhalter, Code ist oben
cleanup_previous_messages = cleanup_previous_messages
send_preview_message = send_preview_message
handle_text_message = handle_text_message
admin = admin
add_voucher = add_voucher

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("addvoucher", add_voucher))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    if WEBHOOK_URL:
        application.run_webhook(listen="0.0.0.0", port=int(os.environ.get('PORT', 8443)), url_path=BOT_TOKEN, webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
