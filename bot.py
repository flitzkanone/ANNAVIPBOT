import os
import logging
import json
import random
from dotenv import load_dotenv
from datetime import datetime
from io import BytesIO
import asyncio
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Bibliothek zum Erstellen von PDFs
from fpdf import FPDF

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error, InputMediaPhoto
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
NOTIFICATION_GROUP_ID = os.getenv("NOTIFICATION_GROUP_ID")

ADMIN_PASSWORD = "1974"
BTC_WALLET = "1FcgMLNBDLiuDSDip7AStuP19sq47LJB12"
ETH_WALLET = "0xeeb8FDc4aAe71B53934318707d0e9747C5c66f6e"

PRICES = {"bilder": {10: 5, 25: 10, 35: 15}, "videos": {10: 15, 25: 25, 35: 30}}
VOUCHER_FILE = "vouchers.json"
STATS_FILE = "stats.json"
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

def load_stats():
    try:
        with open(STATS_FILE, "r") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): 
        return {"pinned_message_id": None, "total_users": [], "events": {}}

def save_stats(stats):
    with open(STATS_FILE, "w") as f: json.dump(stats, f, indent=4)

async def track_event(event_name: str, context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    stats["events"][event_name] = stats["events"].get(event_name, 0) + 1
    save_stats(stats)
    await update_pinned_summary(context)

async def track_new_user(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    is_new = False
    if user_id not in stats["total_users"]:
        stats["total_users"].append(user_id)
        save_stats(stats)
        is_new = True
        await update_pinned_summary(context)
    return is_new

async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str):
    if NOTIFICATION_GROUP_ID:
        try:
            await context.bot.send_message(chat_id=NOTIFICATION_GROUP_ID, text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Konnte Benachrichtigung nicht an Gruppe {NOTIFICATION_GROUP_ID} senden: {e}")

async def update_pinned_summary(context: ContextTypes.DEFAULT_TYPE):
    if not NOTIFICATION_GROUP_ID: return
    stats = load_stats()
    user_count = len(stats.get("total_users", []))
    events = stats.get("events", {})
    text = (
        f"📊 *Bot-Statistik Dashboard*\n"
        f"_(Letztes Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})_\n\n"
        f"👤 *Nutzer Gesamt:* {user_count}\n"
        f"🚀 *Starts insgesamt:* {events.get('start_command', 0)}\n\n"
        f"--- *Bezahl-Interesse* ---\n"
        f"💰 *PayPal Klicks:* {events.get('payment_paypal', 0)}\n"
        f"🪙 *Krypto Klicks:* {events.get('payment_crypto', 0)}\n"
        f"🎟️ *Gutschein Klicks:* {events.get('payment_voucher', 0)}\n\n"
        f"--- *Klick-Verhalten* ---\n"
        f"▪️ Vorschau (KS): {events.get('preview_ks', 0)}\n"
        f"▪️ Vorschau (GS): {events.get('preview_gs', 0)}\n"
        f"▪️ Preise (KS): {events.get('prices_ks', 0)}\n"
        f"▪️ Preise (GS): {events.get('prices_gs', 0)}\n"
        f"▪️ 'Nächstes Bild' Klicks: {events.get('next_preview', 0)}\n"
        f"▪️ Paketauswahl: {events.get('package_selected', 0)}"
    )
    pinned_id = stats.get("pinned_message_id")
    try:
        if pinned_id:
            await context.bot.edit_message_text(chat_id=NOTIFICATION_GROUP_ID, message_id=pinned_id, text=text, parse_mode='Markdown')
        else: raise error.BadRequest("Keine ID vorhanden")
    except (error.BadRequest, error.Forbidden) as e:
        logger.warning(f"Konnte Dashboard nicht bearbeiten ({e}), erstelle neu.")
        try:
            sent_message = await context.bot.send_message(chat_id=NOTIFICATION_GROUP_ID, text=text, parse_mode='Markdown')
            new_id = sent_message.message_id
            stats["pinned_message_id"] = new_id; save_stats(stats)
            await context.bot.pin_chat_message(chat_id=NOTIFICATION_GROUP_ID, message_id=new_id, disable_notification=True)
        except Exception as e_new:
            logger.error(f"Konnte Dashboard nicht erstellen/anpinnen: {e_new}")

async def restore_stats_from_pinned_message(application: Application):
    if not NOTIFICATION_GROUP_ID:
        logger.info("Keine NOTIFICATION_GROUP_ID gesetzt, Wiederherstellung übersprungen."); return
    logger.info("Versuche, Statistiken wiederherzustellen...")
    try:
        chat = await application.bot.get_chat(chat_id=NOTIFICATION_GROUP_ID)
        if not chat.pinned_message or "Bot-Statistik Dashboard" not in chat.pinned_message.text:
            logger.warning("Keine passende Dashboard-Nachricht gefunden."); return
        pinned_text = chat.pinned_message.text
        stats = load_stats()
        def extract(p, t): return int(re.search(p, t).group(1)) if re.search(p, t) else 0
        stats['events']['start_command'] = extract(r"Starts insgesamt:\s*(\d+)", pinned_text)
        stats['events']['payment_paypal'] = extract(r"PayPal Klicks:\s*(\d+)", pinned_text)
        stats['events']['payment_crypto'] = extract(r"Krypto Klicks:\s*(\d+)", pinned_text)
        stats['events']['payment_voucher'] = extract(r"Gutschein Klicks:\s*(\d+)", pinned_text)
        stats['events']['preview_ks'] = extract(r"Vorschau \(KS\):\s*(\d+)", pinned_text)
        stats['events']['preview_gs'] = extract(r"Vorschau \(GS\):\s*(\d+)", pinned_text)
        stats['events']['prices_ks'] = extract(r"Preise \(KS\):\s*(\d+)", pinned_text)
        stats['events']['prices_gs'] = extract(r"Preise \(GS\):\s*(\d+)", pinned_text)
        stats['events']['next_preview'] = extract(r"'Nächstes Bild' Klicks:\s*(\d+)", pinned_text)
        stats['events']['package_selected'] = extract(r"Paketauswahl:\s*(\d+)", pinned_text)
        stats['pinned_message_id'] = chat.pinned_message.message_id
        save_stats(stats)
        logger.info("Statistiken erfolgreich wiederhergestellt.")
    except Exception as e:
        logger.error(f"Fehler bei Wiederherstellung: {e}")

def get_media_files(schwester_code: str, media_type: str) -> list:
    matching_files = []; target_prefix = f"{schwester_code.lower()}_{media_type.lower()}"
    if not os.path.isdir(MEDIA_DIR):
        logger.error(f"Media-Verzeichnis '{MEDIA_DIR}' nicht gefunden!"); return []
    for filename in os.listdir(MEDIA_DIR):
        normalized_filename = filename.lower().lstrip('•-_ ').replace(' ', '_')
        if normalized_filename.startswith(target_prefix): matching_files.append(os.path.join(MEDIA_DIR, filename))
    return matching_files

async def cleanup_previous_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    if "messages_to_delete" in context.user_data:
        for msg_id in context.user_data["messages_to_delete"]:
            try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except error.TelegramError: pass
        del context.user_data["messages_to_delete"]

async def send_preview_message(update: Update, context: ContextTypes.DEFAULT_TYPE, schwester_code: str, is_next_click: bool = False):
    chat_id = update.effective_chat.id; image_paths = get_media_files(schwester_code, "vorschau"); image_paths.sort()
    if not image_paths:
        await context.bot.send_message(chat_id=chat_id, text="Ups! Ich konnte gerade keine passenden Inhalte finden...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="main_menu")]])); return
    index_key = f'preview_index_{schwester_code}'
    if not is_next_click:
        current_index = -1
        if index_key in context.user_data: del context.user_data[index_key]
    else: current_index = context.user_data.get(index_key, -1)
    next_index = current_index + 1
    if next_index >= len(image_paths): next_index = 0
    context.user_data[index_key] = next_index
    image_to_show_path = image_paths[next_index]
    with open(image_to_show_path, 'rb') as photo_file:
        photo_message = await context.bot.send_photo(chat_id=chat_id, photo=photo_file, protect_content=True)
    if schwester_code == 'gs': caption = f"Heyy ich bin Anna, ich bin {AGE_ANNA} Jahre alt und mache mit meiner Schwester zusammen 🌶️ videos und Bilder falls du lust hast speziele videos zu bekommen schreib mir 😏 @Anna_2008_030"
    else: caption = f"Heyy, mein name ist Luna ich bin {AGE_LUNA} Jahre alt und mache 🌶️ videos und Bilder. wenn du Spezielle wünsche hast schreib meiner Schwester für mehr.\nMeine Schwester: @Anna_2008_030"
    keyboard_buttons = [[InlineKeyboardButton("🛍️ Zu den Preisen", callback_data=f"select_schwester:{schwester_code}:prices")], [InlineKeyboardButton("🖼️ Nächstes Bild", callback_data=f"next_preview:{schwester_code}")], [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
    text_message = await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=InlineKeyboardMarkup(keyboard_buttons))
    context.user_data["messages_to_delete"] = [photo_message.message_id, text_message.message_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    is_new = await track_new_user(user.id, context)
    await track_event("start_command", context)
    if is_new and str(user.id) != ADMIN_USER_ID:
        message = f"🎉 *Neuer Nutzer gestartet!*\n\n*ID:* `{user.id}`\n*Name:* {user.first_name}\n*Zeitstempel:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await send_admin_notification(context, message)
    context.user_data.clear(); chat_id = update.effective_chat.id; await cleanup_previous_messages(chat_id, context)
    welcome_text = (
        "Herzlich Willkommen! ✨\n\n"
        "Hier kannst du eine Vorschau meiner Inhalte sehen oder direkt ein Paket auswählen. "
        "Die gesamte Bedienung erfolgt über die Buttons."
    )
    keyboard = [[InlineKeyboardButton(" Vorschau", callback_data="show_preview_options")], [InlineKeyboardButton(" Preise & Pakete", callback_data="show_price_options")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        query = update.callback_query; await query.answer()
        try: await query.edit_message_text(welcome_text, reply_markup=reply_markup)
        except error.TelegramError:
            try: await query.delete_message()
            except Exception: pass
            await context.bot.send_message(chat_id=chat_id, text=welcome_text, reply_markup=reply_markup)
    else: await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); data = query.data; chat_id = update.effective_chat.id
    if data == "download_vouchers_pdf":
        await query.answer("PDF wird erstellt...")
        vouchers = load_vouchers()
        pdf = FPDF()
        pdf.add_page(); pdf.set_font("Arial", size=16); pdf.cell(0, 10, "Gutschein Report", ln=True, align='C'); pdf.ln(10)
        pdf.set_font("Arial", 'B', size=14); pdf.cell(0, 10, "Amazon Gutscheine", ln=True); pdf.set_font("Arial", size=12)
        if vouchers.get("amazon", []):
            for code in vouchers["amazon"]: pdf.cell(0, 8, f"- {code.encode('latin-1', 'ignore').decode('latin-1')}", ln=True)
        else: pdf.cell(0, 8, "Keine vorhanden.", ln=True)
        pdf.ln(5); pdf.set_font("Arial", 'B', size=14); pdf.cell(0, 10, "Paysafe Gutscheine", ln=True); pdf.set_font("Arial", size=12)
        if vouchers.get("paysafe", []):
            for code in vouchers["paysafe"]: pdf.cell(0, 8, f"- {code.encode('latin-1', 'ignore').decode('latin-1')}", ln=True)
        else: pdf.cell(0, 8, "Keine vorhanden.", ln=True)
        pdf_buffer = BytesIO(pdf.output(dest='S').encode('latin-1')); pdf_buffer.seek(0)
        today_str = datetime.now().strftime("%Y-%m-%d")
        await context.bot.send_document(chat_id=chat_id, document=pdf_buffer, filename=f"Gutschein-Report_{today_str}.pdf", caption="Hier ist dein aktueller Gutschein-Report.")
        return
    if data in ["main_menu", "show_preview_options", "show_price_options"]:
        await cleanup_previous_messages(chat_id, context)
        try: await query.edit_message_text(text="⏳"); await asyncio.sleep(0.5)
        except Exception: pass
    if data == "main_menu": await start(update, context)
    elif data == "admin_main_menu": await show_admin_menu(update, context)
    elif data == "admin_show_vouchers": await show_vouchers_panel(update, context)
    elif data == "admin_stats_users":
        stats = load_stats(); user_count = len(stats.get("total_users", []))
        text = f"📊 *Nutzer-Statistiken*\n\nGesamtzahl der Nutzer: *{user_count}*"
        keyboard = [[InlineKeyboardButton("« Zurück zum Admin-Menü", callback_data="admin_main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "admin_stats_clicks":
        stats = load_stats(); events = stats.get("events", {})
        text = "🖱️ *Klick-Statistiken*\n\n"
        if not events: text += "Noch keine Klicks erfasst."
        else:
            for event, count in sorted(events.items()): text += f"- `{event}`: *{count}* Klicks\n"
        keyboard = [[InlineKeyboardButton("« Zurück zum Admin-Menü", callback_data="admin_main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "admin_reset_stats":
        text = "⚠️ *Bist du sicher?*\n\nDadurch werden alle Klick- und Nutzer-Statistiken unwiderruflich auf Null zurückgesetzt."
        keyboard = [[InlineKeyboardButton("✅ Ja, zurücksetzen", callback_data="admin_reset_stats_confirm")], [InlineKeyboardButton("❌ Nein, abbrechen", callback_data="admin_main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "admin_reset_stats_confirm":
        stats = load_stats()
        stats["total_users"] = []
        stats["events"] = {key: 0 for key in stats["events"]}
        save_stats(stats)
        await update_pinned_summary(context)
        await query.edit_message_text("✅ Alle Statistiken wurden zurückgesetzt.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück zum Admin-Menü", callback_data="admin_main_menu")]]))
    elif data in ["show_preview_options", "show_price_options"]:
        action = "preview" if "preview" in data else "prices"; text = "Für wen interessierst du dich?"
        keyboard = [[InlineKeyboardButton("Kleine Schwester", callback_data=f"select_schwester:ks:{action}"), InlineKeyboardButton("Große Schwester", callback_data=f"select_schwester:gs:{action}")], [InlineKeyboardButton("« Zurück", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("select_schwester:"):
        await cleanup_previous_messages(chat_id, context)
        try: await query.message.delete()
        except Exception: pass
        _, schwester_code, action = data.split(":")
        await track_event(f"{action}_{schwester_code}", context)
        if action == "preview": await send_preview_message(update, context, schwester_code, is_next_click=False)
        elif action == "prices":
            image_paths = get_media_files(schwester_code, "preis"); image_paths.sort()
            if not image_paths:
                await context.bot.send_message(chat_id=chat_id, text="Ups! Ich konnte gerade keine passenden Inhalte finden...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="main_menu")]])); return
            random_image_path = random.choice(image_paths)
            with open(random_image_path, 'rb') as photo_file:
                photo_message = await context.bot.send_photo(chat_id=chat_id, photo=photo_file, protect_content=True)
            caption = "Wähle dein gewünschtes Paket:"
            keyboard_buttons = [[InlineKeyboardButton("10 Bilder", callback_data="select_package:bilder:10"), InlineKeyboardButton("10 Videos", callback_data="select_package:videos:10")], [InlineKeyboardButton("25 Bilder", callback_data="select_package:bilder:25"), InlineKeyboardButton("25 Videos", callback_data="select_package:videos:25")], [InlineKeyboardButton("35 Bilder", callback_data="select_package:bilder:35"), InlineKeyboardButton("35 Videos", callback_data="select_package:videos:35")], [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
            text_message = await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=InlineKeyboardMarkup(keyboard_buttons))
            context.user_data["messages_to_delete"] = [photo_message.message_id, text_message.message_id]
    elif data.startswith("next_preview:"):
        await track_event("next_preview", context)
        _, schwester_code = data.split(":")
        await cleanup_previous_messages(chat_id, context)
        await send_preview_message(update, context, schwester_code, is_next_click=True)
    elif data.startswith("select_package:"):
        await track_event("package_selected", context)
        await cleanup_previous_messages(chat_id, context);
        try: await query.message.delete()
        except Exception: pass
        _, media_type, amount_str = data.split(":"); amount = int(amount_str); price = PRICES[media_type][amount]; text = f"Du hast das Paket **{amount} {media_type.capitalize()}** für **{price}€** ausgewählt.\n\nWie möchtest du bezahlen?"
        keyboard = [[InlineKeyboardButton(" PayPal", callback_data=f"pay_paypal:{media_type}:{amount}")], [InlineKeyboardButton(" Gutschein", callback_data=f"pay_voucher:{media_type}:{amount}")], [InlineKeyboardButton("🪙 Krypto", callback_data=f"pay_crypto:{media_type}:{amount}")], [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith(("pay_paypal:", "pay_voucher:", "pay_crypto:", "show_wallet:", "voucher_provider:")):
        try: await query.edit_message_text(text="⏳"); await asyncio.sleep(2)
        except Exception: pass
        user = update.effective_user; payment_type_full, media_type, amount_str = data.split(":"); amount = int(amount_str); price = PRICES[media_type][amount]
        payment_type = payment_type_full.split('_')[1]
        if payment_type == "paypal":
            await track_event("payment_paypal", context); await send_admin_notification(context, f"💰 *PayPal Klick!*\nNutzer `{user.id}` ({user.first_name}) möchte ein Paket für *{price}€* kaufen.")
            paypal_link = f"https://paypal.me/{PAYPAL_USER}/{price}"; text = (f"Super! Klicke auf den Link, um die Zahlung für **{amount} {media_type.capitalize()}** in Höhe von **{price}€** abzuschließen.\n\nGib als Verwendungszweck bitte deinen Telegram-Namen an.\n\n➡️ [Hier sicher bezahlen]({paypal_link})")
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]), parse_mode='Markdown', disable_web_page_preview=True)
        elif payment_type == "voucher":
            await track_event("payment_voucher", context); await send_admin_notification(context, f"🎟️ *Gutschein Klick!*\nNutzer `{user.id}` ({user.first_name}) möchte ein Paket für *{price}€* mit Gutschein bezahlen.")
            text = "Welchen Gutschein möchtest du einlösen?"; keyboard = [[InlineKeyboardButton("Amazon", callback_data=f"voucher_provider:amazon"), InlineKeyboardButton("Paysafe", callback_data=f"voucher_provider:paysafe")], [InlineKeyboardButton("« Zurück zur Bezahlwahl", callback_data=f"select_package:{media_type}:{amount_str}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif payment_type == "crypto":
            await track_event("payment_crypto", context); await send_admin_notification(context, f"🪙 *Krypto Klick!*\nNutzer `{user.id}` ({user.first_name}) möchte ein Paket für *{price}€* mit Krypto bezahlen.")
            text = "Bitte wähle die gewünschte Kryptowährung:"; keyboard = [[InlineKeyboardButton("Bitcoin (BTC)", callback_data=f"show_wallet:btc:{media_type}:{amount}"), InlineKeyboardButton("Ethereum (ETH)", callback_data=f"show_wallet:eth:{media_type}:{amount}")], [InlineKeyboardButton("« Zurück zur Bezahlwahl", callback_data=f"select_package:{media_type}:{amount}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif data.startswith("show_wallet:"):
            _, crypto_type, media_type, amount_str = data.split(":"); amount = int(amount_str); price = PRICES[media_type][amount]
            wallet_address = BTC_WALLET if crypto_type == "btc" else ETH_WALLET; crypto_name = "Bitcoin (BTC)" if crypto_type == "btc" else "Ethereum (ETH)"
            text = (f"Zahlung mit **{crypto_name}** für das Paket **{amount} {media_type.capitalize()}**.\n\n1️⃣ **Betrag:**\nBitte sende den exakten Gegenwert von **{price}€** in {crypto_name}.\n_(Nutze einen aktuellen Umrechner, z.B. auf Binance oder Coinbase.)_\n\n2️⃣ **Wallet-Adresse (zum Kopieren):**\n`{wallet_address}`\n\n3️⃣ **WICHTIG:**\nSchicke mir nach der Transaktion einen **Screenshot** oder die **Transaktions-ID** an **@Anna_2008_030**, damit ich deine Zahlung zuordnen kann.")
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]), parse_mode='Markdown')
        elif data.startswith("voucher_provider:"):
            _, provider = data.split(":")
            context.user_data["awaiting_voucher"] = provider
            text = f"Bitte sende mir jetzt deinen {provider.capitalize()}-Gutschein-Code als einzelne Nachricht."
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Abbrechen", callback_data="main_menu")]]))

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🔒 *Admin-Menü*\n\nWähle eine Option:"
    keyboard = [[InlineKeyboardButton("📊 Nutzer-Statistiken", callback_data="admin_stats_users")], [InlineKeyboardButton("🖱️ Klick-Statistiken", callback_data="admin_stats_clicks")], [InlineKeyboardButton("🎟️ Gutscheine anzeigen", callback_data="admin_show_vouchers")], [InlineKeyboardButton("🔄 Statistiken zurücksetzen", callback_data="admin_reset_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else: await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_vouchers_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vouchers = load_vouchers(); amazon_codes = "\n".join([f"- `{code}`" for code in vouchers.get("amazon", [])]) or "Keine"; paysafe_codes = "\n".join([f"- `{code}`" for code in vouchers.get("paysafe", [])]) or "Keine"
    text = (f"*Eingelöste Gutscheine*\n\n*Amazon:*\n{amazon_codes}\n\n*Paysafe:*\n{paysafe_codes}")
    keyboard = [[InlineKeyboardButton("📄 Vouchers als PDF laden", callback_data="download_vouchers_pdf")], [InlineKeyboardButton("« Zurück zum Admin-Menü", callback_data="admin_main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_admin_password"):
        password = update.message.text; del context.user_data["awaiting_admin_password"]
        if password == ADMIN_PASSWORD: await show_admin_menu(update, context)
        else: await update.message.reply_text("Falsches Passwort.")
    elif context.user_data.get("awaiting_voucher"):
        user = update.effective_user; provider = context.user_data.pop("awaiting_voucher"); code = update.message.text
        vouchers = load_vouchers(); vouchers[provider].append(code); save_vouchers(vouchers)
        notification_text = (f"📬 *Neuer Gutschein erhalten!*\n\n*Anbieter:* {provider.capitalize()}\n*Code:* `{code}`\n*Von Nutzer:* `{user.id}` ({user.first_name})")
        await send_admin_notification(context, notification_text)
        await update.message.reply_text("Vielen Dank! Dein Gutschein wurde übermittelt..."); await start(update, context)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_admin_password"] = True; await update.message.reply_text("Bitte gib jetzt das Admin-Passwort ein:")

async def add_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    if not ADMIN_USER_ID or user_id != ADMIN_USER_ID: await update.message.reply_text("⛔️ Du hast keine Berechtigung für diesen Befehl."); return
    if len(context.args) < 2: await update.message.reply_text("⚠️ Bitte gib den Befehl im richtigen Format an:\n`/addvoucher <anbieter> <code...>`", parse_mode='Markdown'); return
    provider = context.args[0].lower()
    if provider not in ["amazon", "paysafe"]: await update.message.reply_text("Fehler: Anbieter muss 'amazon' oder 'paysafe' sein."); return
    code = " ".join(context.args[1:]); vouchers = load_vouchers(); vouchers[provider].append(code); save_vouchers(vouchers)
    await update.message.reply_text(f"✅ Gutschein für **{provider.capitalize()}** erfolgreich hinzugefügt:\n`{code}`", parse_mode='Markdown')

async def set_summary_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    if not ADMIN_USER_ID or user_id != ADMIN_USER_ID: await update.message.reply_text("⛔️ Du hast keine Berechtigung."); return
    if str(update.effective_chat.id) != NOTIFICATION_GROUP_ID:
        await update.message.reply_text("⚠️ Dieser Befehl geht nur in der Admin-Gruppe."); return
    await update.message.reply_text("🔄 Erstelle Dashboard...")
    stats = load_stats(); stats["pinned_message_id"] = None; save_stats(stats)
    await update_pinned_summary(context)

async def main_async():
    application = Application.builder().token(BOT_TOKEN).build()
    await restore_stats_from_pinned_message(application)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("addvoucher", add_voucher))
    application.add_handler(CommandHandler("setsummary", set_summary_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    if WEBHOOK_URL:
        await application.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
        port = int(os.environ.get('PORT', 8443))
        
        class WebhookHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                self.send_response(200)
                self.end_headers()
                update = Update.de_json(json.loads(body.decode('utf-8')), application.bot)
                asyncio.run(application.process_update(update))

        httpd = HTTPServer(('0.0.0.0', port), WebhookHandler)
        logger.info(f"Bot gestartet, lauscht auf Port {port}")
        httpd.serve_forever()
    else:
        logger.info("Starte Bot im Polling-Modus")
        await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main_async())
