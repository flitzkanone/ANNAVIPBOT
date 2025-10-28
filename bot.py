import os
import logging
import json
import random
from dotenv import load_dotenv
from datetime import datetime, timedelta
from io import BytesIO
import asyncio
import re
from math import ceil

from fpdf import FPDF
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error, InputMediaPhoto, InputMediaVideo, User
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.helpers import escape_markdown

# --- Konfiguration ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYPAL_USER = os.getenv("PAYPAL_USER")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
NOTIFICATION_GROUP_ID = os.getenv("NOTIFICATION_GROUP_ID")
TELEGRAM_USERNAME = os.getenv("TELEGRAM_USERNAME", "ANNASPICY")

AGE_ANNA = os.getenv("AGE_ANNA", "18")
PREVIEW_CAPTION = os.getenv("PREVIEW_CAPTION", "Hier ist eine Vorschau. Ich bin {age_anna} Jahre alt. Klicke auf 'Nächstes Medium' für mehr.")

BTC_WALLET = "1FcgMLNBDLiuDSDip7AStuP19sq47LJB12"
ETH_WALLET = "0xeeb8FDc4aAe71B53934318707d0e9747C5c66f6e"

PRICES = {
    "bilder": {10: 5, 25: 10, 35: 15},
    "videos": {10: 15, 25: 25, 35: 30},
    "livecall": {10: 10, 15: 15, 20: 20, 30: 30, 60: 50, 120: 80},
    "treffen": {60: 200, 120: 300, 240: 400, 1440: 600, 2880: 800}
}
VOUCHER_FILE = "vouchers.json"
STATS_FILE = "stats.json"
MEDIA_DIR = "image"
DISCOUNT_MSG_HEADER = "--- BOT DISCOUNT DATA (DO NOT DELETE) ---"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Hilfsfunktionen ---
def load_vouchers():
    try:
        with open(VOUCHER_FILE, "r") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {"amazon": []}

def save_vouchers(vouchers):
    with open(VOUCHER_FILE, "w") as f: json.dump(vouchers, f, indent=2)

def load_stats():
    try:
        with open(STATS_FILE, "r") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": {}, "admin_logs": {}, "events": {}}

def save_stats(stats):
    with open(STATS_FILE, "w") as f: json.dump(stats, f, indent=4)

def ensure_user_in_stats(user_id: int, stats: dict) -> dict:
    user_id_str = str(user_id)
    if user_id_str not in stats.get("users", {}):
        stats.setdefault("users", {})[user_id_str] = {
            "first_start": datetime.now().isoformat(),
            "last_start": datetime.now().isoformat(),
            "discount_sent": False,
            "preview_clicks": 0,
            "payments_initiated": [],
            "banned": False,
            "paypal_offer_sent": False
        }
        save_stats(stats)
    return stats

async def save_discounts_to_telegram(context: ContextTypes.DEFAULT_TYPE):
    if not NOTIFICATION_GROUP_ID: return
    stats = load_stats(); discounts_to_save = {}
    for user_id, user_data in stats.get("users", {}).items():
        if "discounts" in user_data: discounts_to_save[user_id] = user_data["discounts"]
    json_string = json.dumps(discounts_to_save, indent=2); message_text = f"{DISCOUNT_MSG_HEADER}\n<tg-spoiler>{json_string}</tg-spoiler>"; discount_message_id = stats.get("discount_message_id")
    try:
        if discount_message_id: await context.bot.edit_message_text(chat_id=NOTIFICATION_GROUP_ID, message_id=discount_message_id, text=message_text, parse_mode='HTML')
        else: raise error.BadRequest("No discount message ID found")
    except error.BadRequest:
        logger.warning("Discount message not found or invalid, creating a new one.")
        try:
            sent_message = await context.bot.send_message(chat_id=NOTIFICATION_GROUP_ID, text=message_text, parse_mode='HTML')
            stats["discount_message_id"] = sent_message.message_id; save_stats(stats)
        except Exception as e: logger.error(f"Could not create a new discount persistence message: {e}")

async def load_discounts_from_telegram(application: Application):
    if not NOTIFICATION_GROUP_ID: return
    try:
        stats = load_stats()
        discount_message_id = stats.get("discount_message_id")
        if not discount_message_id: return
        message = await application.bot.get_message(chat_id=NOTIFICATION_GROUP_ID, message_id=discount_message_id)
        json_match = re.search(r'<tg-spoiler>(.*)</tg-spoiler>', message.text_html, re.DOTALL)
        if not json_match: return
        discounts_data = json.loads(json_match.group(1)); users_updated = 0
        for user_id, discounts in discounts_data.items():
            if user_id in stats["users"]: stats["users"][user_id]["discounts"] = discounts; users_updated += 1
        if users_updated > 0: save_stats(stats); logger.info(f"Successfully restored discounts for {users_updated} users.")
    except Exception as e: logger.error(f"An unexpected error occurred during discount restore: {e}")

async def track_event(event_name: str, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if str(user_id) == ADMIN_USER_ID: return
    stats = load_stats(); stats["events"][event_name] = stats["events"].get(event_name, 0) + 1; save_stats(stats)

def is_user_banned(user_id: int) -> bool:
    stats = load_stats(); user_data = stats.get("users", {}).get(str(user_id), {}); return user_data.get("banned", False)

def get_discounted_price(base_price: int, discount_data: dict, package_key: str) -> int:
    if not discount_data: return -1
    discount_type = discount_data.get("type")

    if discount_type == "percent":
        value = discount_data.get("value", 0); new_price = base_price * (1 - value / 100); return ceil(new_price)
    elif discount_type == "euro_packages":
        packages = discount_data.get("packages", {});
        if package_key in packages: return max(1, base_price - packages[package_key])
    elif discount_type == "percent_packages":
        packages = discount_data.get("packages", {});
        if package_key in packages: value = packages[package_key]; new_price = base_price * (1 - value / 100); return ceil(new_price)
    return -1

def get_package_button_text(media_type: str, amount: int, user_id: int) -> str:
    stats = load_stats(); user_data = stats.get("users", {}).get(str(user_id), {}); base_price = PRICES[media_type][amount]; package_key = f"{media_type}_{amount}"

    duration_text = ""
    if media_type == "livecall":
        if amount < 60: duration_text = f"{amount} Min"
        else: duration_text = f"{amount//60} Std"
    elif media_type == "treffen":
        if amount == 60: duration_text = "1 Stunde"
        elif amount == 120: duration_text = "2 Stunden"
        elif amount == 240: duration_text = "4 Stunden"
        elif amount == 1440: duration_text = "1 Tag"
        elif amount == 2880: duration_text = "2 Tage"
    else:
        duration_text = f"{amount} {media_type.capitalize()}"

    if media_type not in ["livecall", "treffen"]:
        discount_price = get_discounted_price(base_price, user_data.get("discounts"), package_key)
        if discount_price != -1:
            return f"{duration_text} ~{base_price}~{discount_price}€ ✨"

    return f"{duration_text} {base_price}€"

async def check_user_status(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    if str(user_id) == ADMIN_USER_ID: return "admin", False, None
    stats = load_stats()
    user_id_str = str(user_id)
    now = datetime.now()

    if user_id_str not in stats.get("users", {}):
        stats = ensure_user_in_stats(user_id, stats)
        return "new", True, stats["users"][user_id_str]

    user_data = stats["users"][user_id_str]
    last_start_dt = datetime.fromisoformat(user_data.get("last_start"))

    if now - last_start_dt > timedelta(hours=24):
        return "returning", True, user_data

    return "active", False, user_data

async def send_or_update_admin_log(context: ContextTypes.DEFAULT_TYPE, user: User, event_text: str = ""):
    if not NOTIFICATION_GROUP_ID or str(user.id) == ADMIN_USER_ID: return
    try:
        user_id_str = str(user.id); stats = load_stats(); admin_logs = stats.get("admin_logs", {}); user_data = stats.get("users", {}).get(user_id_str, {}); log_message_id = admin_logs.get(user_id_str, {}).get("message_id")
        user_mention = f"[{escape_markdown(user.first_name, version=2)}](tg://user?id={user.id})"; discount_emoji = "💸" if user_data.get("discount_sent") or "discounts" in user_data else ""; banned_emoji = "🚫" if user_data.get("banned") else ""
        first_start_str = "N/A"
        if user_data.get("first_start"): first_start_str = datetime.fromisoformat(user_data["first_start"]).strftime('%Y-%m-%d %H:%M')
        preview_clicks = user_data.get("preview_clicks", 0); payments = user_data.get("payments_initiated", []); payments_str = "\n".join(f"   • {p}" for p in payments) if payments else "   • Keine"
        base_text = (f"👤 *Nutzer-Aktivität* {discount_emoji}{banned_emoji}\n\n" f"*Nutzer:* {user_mention} (`{user.id}`)\n" f"*Erster Start:* `{first_start_str}`\n\n" f"🖼️ *Vorschau-Klicks:* {preview_clicks}/25\n\n" f"💰 *Bezahlversuche*\n{payments_str}")
        final_text = f"{base_text}\n\n`Letzte Aktion: {event_text}`".strip()
        if log_message_id: await context.bot.edit_message_text(chat_id=NOTIFICATION_GROUP_ID, message_id=log_message_id, text=final_text, parse_mode='Markdown')
        else:
            sent_message = await context.bot.send_message(chat_id=NOTIFICATION_GROUP_ID, text=final_text, parse_mode='Markdown')
            admin_logs.setdefault(user_id_str, {})["message_id"] = sent_message.message_id; stats["admin_logs"] = admin_logs; save_stats(stats)
    except error.BadRequest as e:
        if "chat not found" in str(e).lower(): logger.warning(f"Admin log group '{NOTIFICATION_GROUP_ID}' not found.")
        elif "message to edit not found" in str(e): logger.warning(f"Admin log for user {user.id} not found.")
        else: logger.error(f"BadRequest on admin log for user {user.id}: {e}")
    except error.TelegramError as e:
        if 'message is not modified' not in str(e): logger.warning(f"Temporary error updating admin log for user {user.id}: {e}")

def get_media_files(media_type: str, purpose: str) -> list:
    matching_files = []
    if media_type == 'combined' and purpose == 'vorschau':
        for mt in ['bilder', 'videos']:
            target_prefix = f"{mt.lower()}_{purpose.lower()}"
            if not os.path.isdir(MEDIA_DIR): continue
            for filename in os.listdir(MEDIA_DIR):
                normalized_filename = filename.lower().lstrip('•-_ ').replace(' ', '_')
                if normalized_filename.startswith(target_prefix): matching_files.append(os.path.join(MEDIA_DIR, filename))
    else:
        target_prefix = f"{media_type.lower()}_{purpose.lower()}"
        if not os.path.isdir(MEDIA_DIR): return []
        for filename in os.listdir(MEDIA_DIR):
            normalized_filename = filename.lower().lstrip('•-_ ').replace(' ', '_')
            if normalized_filename.startswith(target_prefix): matching_files.append(os.path.join(MEDIA_DIR, filename))
    matching_files.sort()
    return matching_files

# NEU: Umfassendes System zur Nachrichtenbereinigung
async def cleanup_bot_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Löscht alle vom Bot in diesem Chat gesendeten Nachrichten, die verfolgt wurden."""
    if 'tracked_message_ids' in context.chat_data:
        message_ids = context.chat_data['tracked_message_ids']
        for msg_id in message_ids:
            try:
                await context.bot.delete_message(chat_id, msg_id)
            except error.TelegramError:
                pass # Nachricht wurde möglicherweise schon vom Nutzer gelöscht
        context.chat_data['tracked_message_ids'] = []
    # Lösche auch alte, nicht verfolgte Nachrichten-IDs zur Sicherheit
    context.chat_data.pop('media_message_id', None)
    context.chat_data.pop('control_message_id', None)


async def send_tracked_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, **kwargs):
    """Sendet eine Nachricht und speichert ihre ID zum späteren Löschen."""
    message = await context.bot.send_message(chat_id=chat_id, **kwargs)
    if 'tracked_message_ids' not in context.chat_data:
        context.chat_data['tracked_message_ids'] = []
    context.chat_data['tracked_message_ids'].append(message.message_id)
    return message

async def send_tracked_photo(context: ContextTypes.DEFAULT_TYPE, chat_id: int, **kwargs):
    """Sendet ein Foto und speichert seine ID zum späteren Löschen."""
    message = await context.bot.send_photo(chat_id=chat_id, **kwargs)
    if 'tracked_message_ids' not in context.chat_data:
        context.chat_data['tracked_message_ids'] = []
    context.chat_data['tracked_message_ids'].append(message.message_id)
    return message

async def send_tracked_video(context: ContextTypes.DEFAULT_TYPE, chat_id: int, **kwargs):
    """Sendet ein Video und speichert seine ID zum späteren Löschen."""
    message = await context.bot.send_video(chat_id=chat_id, **kwargs)
    if 'tracked_message_ids' not in context.chat_data:
        context.chat_data['tracked_message_ids'] = []
    context.chat_data['tracked_message_ids'].append(message.message_id)
    return message
# NEU ENDE

# ÜBERARBEITET: Vorschau-Funktion für getrennte Nachrichten
async def send_preview_message(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str, start_index: int = 0):
    chat_id = update.effective_chat.id
    await cleanup_bot_messages(chat_id, context)

    media_paths = get_media_files(media_type, "vorschau")
    if media_type == 'combined': random.shuffle(media_paths)

    context.user_data['preview_gallery'] = media_paths

    if not media_paths:
        msg = await send_tracked_message(context, chat_id=chat_id, text="Ups! Ich konnte gerade keine passenden Inhalte finden...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="main_menu")]]))
        return

    start_index = start_index % len(media_paths)
    context.user_data[f'preview_index_{media_type}'] = start_index
    media_path = media_paths[start_index]
    file_extension = os.path.splitext(media_path)[1].lower()

    media_message = None
    try:
        with open(media_path, 'rb') as media_file:
            if file_extension in ['.jpg', '.jpeg', '.png']:
                media_message = await send_tracked_photo(context, chat_id=chat_id, photo=media_file, protect_content=True)
            elif file_extension in ['.mp4', '.mov', '.m4v']:
                media_message = await send_tracked_video(context, chat_id=chat_id, video=media_file, protect_content=True, supports_streaming=True)
            else:
                return # Unbekannter Dateityp

        # Speichere die ID der Mediennachricht, um sie später zu bearbeiten
        context.chat_data['media_message_id'] = media_message.message_id

        # Sende die Steuerung als separate Nachricht
        caption = PREVIEW_CAPTION.format(age_anna=AGE_ANNA)
        keyboard = [
            [InlineKeyboardButton("🖼️ Nächstes Medium", callback_data=f"next_preview:{media_type}")],
            [InlineKeyboardButton("🛍️ Preise & Pakete", callback_data="show_price_options")],
            [InlineKeyboardButton("📞 Live Call", callback_data="live_call_menu")],
            [InlineKeyboardButton("📅 Treffen buchen", callback_data="treffen_menu")],
            [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]
        ]
        await send_tracked_message(context, chat_id=chat_id, text=caption, reply_markup=InlineKeyboardMarkup(keyboard))

    except error.TelegramError as e:
        logger.error(f"Error sending preview file {media_path}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    await cleanup_bot_messages(chat_id, context)

    if is_user_banned(user.id):
        await send_tracked_message(context, chat_id=chat_id, text="Du bist von der Nutzung dieses Bots ausgeschlossen.")
        return

    try:
        stats_before = load_stats()
        user_data_before = stats_before.get("users", {}).get(str(user.id))
        last_start_before = user_data_before.get("last_start") if user_data_before else None

        status, should_notify, user_data = await check_user_status(user.id, context)
        await track_event("start_command", context, user.id)

        if last_start_before and not user_data.get("discount_sent"):
            last_start_dt = datetime.fromisoformat(last_start_before)
            if datetime.now() - last_start_dt > timedelta(hours=2):
                stats = load_stats()
                stats["users"][str(user.id)]["discounts"] = {"type": "percent", "value": 10}
                stats["users"][str(user.id)]["discount_sent"] = True
                save_stats(stats)
                await save_discounts_to_telegram(context)

                discount_notification_text = ("🎁 Wir haben dich vermisst! 🎁\n\n"
                                              "Als Willkommensgruß erhältst du einen exklusiven **10% Rabatt** auf alle Pakete!\n\n"
                                              "PLUS: Unser **2-für-1 PayPal-Angebot** gilt weiterhin für dich. Nutze die Chance!")
                discount_notification_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💸 Zu meinen exklusiven Preisen 💸", callback_data="show_price_options")]])
                await send_tracked_message(context, chat_id=chat_id, text=discount_notification_text, reply_markup=discount_notification_keyboard, parse_mode='Markdown')
                return

        if should_notify:
            event_text = "Bot gestartet (neuer Nutzer)" if status == "new" else "Bot erneut gestartet"
            await send_or_update_admin_log(context, user, event_text=event_text)

    except Exception as e:
        logger.error(f"Error in start admin logic for user {user.id}: {e}")

    stats = load_stats()
    stats = ensure_user_in_stats(user.id, stats)
    stats["users"][str(user.id)]["last_start"] = datetime.now().isoformat()
    save_stats(stats)

    welcome_text = ( "Herzlich Willkommen! ✨\n\n" "Hier kannst du eine Vorschau meiner Inhalte sehen oder direkt ein Paket auswählen. " "Die gesamte Bedienung erfolgt über die Buttons.")
    keyboard = [
        [InlineKeyboardButton("🖼️ Vorschau", callback_data="show_preview:combined")],
        [InlineKeyboardButton("🛍️ Bilder & Videos", callback_data="show_price_options")],
        [InlineKeyboardButton("📞 Live Call", callback_data="live_call_menu")],
        [InlineKeyboardButton("📅 Treffen buchen", callback_data="treffen_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Im Start wird immer eine neue Nachricht gesendet
    await send_tracked_message(context, chat_id=chat_id, text=welcome_text, reply_markup=reply_markup)


async def show_prices_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    await cleanup_bot_messages(chat_id, context)

    await track_event("prices_viewed", context, user.id)
    await send_or_update_admin_log(context, user, event_text="Schaut sich die Preise an")

    caption = "Wähle dein gewünschtes Paket:"
    keyboard = get_price_keyboard(user.id)

    media_paths = get_media_files("videos", "preis")
    if media_paths:
        random_media_path = random.choice(media_paths)
        try:
            with open(random_media_path, 'rb') as media_file:
                await send_tracked_video(
                    context,
                    chat_id=chat_id,
                    video=media_file,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    protect_content=True,
                    supports_streaming=True
                )
        except error.TelegramError as e:
            logger.error(f"Could not send price video {random_media_path}: {e}")
            await send_tracked_message(context, chat_id=chat_id, text=caption, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await send_tracked_message(context, chat_id=chat_id, text=caption, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_treffen_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    buchung = context.user_data.get('treffen_buchung', {})
    chat_id = update.effective_chat.id
    
    # Hier wird die Bereinigung vor der finalen Zusammenfassung durchgeführt
    await cleanup_bot_messages(chat_id, context)

    if not all(k in buchung for k in ['duration', 'date', 'location']):
        text = "Ein Fehler ist aufgetreten. Bitte beginne die Buchung erneut."
        keyboard = [[InlineKeyboardButton("« Zum Treffen-Menü", callback_data="treffen_menu")]]
        await send_tracked_message(context, chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    duration = buchung['duration']
    duration_text = get_package_button_text('treffen', duration, user.id).split(' ')[0] + " " + get_package_button_text('treffen', duration, user.id).split(' ')[1]
    full_price = PRICES['treffen'][duration]
    deposit = ceil(full_price / 4)
    cash_price = full_price * 0.9

    summary_text = (
        f"📅 **Deine Terminanfrage:**\n\n"
        f"**Dauer:** {duration_text}\n"
        f"**Datum:** {buchung['date']}\n"
        f"**Ort:** {buchung['location']}\n\n"
        f"**Gesamtpreis:** {full_price}€\n"
        f"**Barzahler-Rabatt (10%):** -{full_price * 0.1:.2f}€\n"
        f"**Neuer Endpreis (bei Barzahlung):** **{cash_price:.2f}€**\n\n"
        f"Zur Verifizierung ist eine **Anzahlung von 25% ({deposit}€)** erforderlich. "
        f"Diese deckt meine Reisekosten und dient als beidseitige Sicherheit. Der Restbetrag wird in bar beim Treffen bezahlt."
    )
    keyboard = [
        [InlineKeyboardButton("🤔 Warum diese Anzahlung?", callback_data="treffen_info_anzahlung_summary")],
        [InlineKeyboardButton(f"💸 Anzahlung ({deposit}€) per PayPal", callback_data=f"pay_paypal:treffen:{duration}")],
        [InlineKeyboardButton(f"🎟️ Anzahlung ({deposit}€) per Gutschein", callback_data=f"pay_voucher:treffen:{duration}")],
        [InlineKeyboardButton(f"🪙 Anzahlung ({deposit}€) per Krypto", callback_data=f"pay_crypto:treffen:{duration}")],
        [InlineKeyboardButton("« Buchung abbrechen", callback_data="treffen_menu")]
    ]

    await send_tracked_message(context, chat_id=chat_id, text="Status: ✅ Dein Wunschtermin ist verfügbar!")
    await send_tracked_message(context, chat_id=chat_id, text=summary_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    user = update.effective_user

    stats = load_stats()
    stats = ensure_user_in_stats(user.id, stats)
    user_data = stats["users"][str(user.id)]

    if is_user_banned(user.id):
        await query.answer("Du bist von der Nutzung dieses Bots ausgeschlossen.", show_alert=True)
        return

    if data == "main_menu":
        await start(update, context)
        return

    # ÜBERARBEITET: Vollständige Admin-Handler-Logik
    if data.startswith("admin_"):
        if str(user.id) != ADMIN_USER_ID:
            await query.answer("⛔️ Keine Berechtigung.", show_alert=True)
            return

        # Hauptmenü und Statistiken
        if data == "admin_main_menu": await show_admin_menu(update, context)
        elif data == "admin_stats_users":
            await query.edit_message_text(f"Gesamtzahl der Nutzer: {len(stats.get('users', {}))}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="admin_main_menu")]]))
        elif data == "admin_stats_clicks":
            events = stats.get("events", {})
            text = "Klick-Statistiken:\n" + "\n".join(f"- {key}: {value}" for key, value in events.items())
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="admin_main_menu")]]))
        
        # Gutscheine
        elif data == "admin_show_vouchers": await show_vouchers_panel(update, context)
        
        # Nutzerverwaltung
        elif data == "admin_user_manage": await show_user_management_menu(update, context)
        elif data == "admin_user_ban_start":
            context.user_data['awaiting_user_id_for_sperren'] = True
            await query.edit_message_text("Bitte gib die Nutzer-ID der Person ein, die du sperren möchtest.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Abbrechen", callback_data="admin_user_manage")]]))
        elif data == "admin_user_unban_start":
            context.user_data['awaiting_user_id_for_entsperren'] = True
            await query.edit_message_text("Bitte gib die Nutzer-ID der Person ein, die du entsperren möchtest.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Abbrechen", callback_data="admin_user_manage")]]))
        elif data == "admin_preview_limit_start":
            context.user_data['awaiting_user_id_for_preview_limit'] = True
            await query.edit_message_text("Bitte gib die Nutzer-ID ein, deren Vorschau-Limit du verwalten möchtest.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Abbrechen", callback_data="admin_user_manage")]]))
        elif data.startswith("admin_preview_"):
            _, action, user_id_str = data.split(":")
            await execute_manage_preview_limit(update, context, user_id_str, action)

        # ... (weitere admin-handler hier einfügen, falls nötig) ...
        return

    if data.startswith("show_preview:"):
        _, media_type = data.split(":")
        if user_data.get("preview_clicks", 0) >= 25:
            await query.answer("Du hast dein Vorschau-Limit von 25 Klicks bereits erreicht.", show_alert=True)
            return
        await track_event(f"preview_{media_type}", context, user.id)
        await send_or_update_admin_log(context, user, event_text="Schaut sich Vorschau an")
        await send_preview_message(update, context, media_type)

    elif data == "show_price_options":
        await show_prices_page(update, context)

    elif data == "live_call_menu":
        await cleanup_bot_messages(chat_id, context)
        text = "📞 Wähle die gewünschte Dauer für deinen Live Call:"
        keyboard = []
        row = []
        for duration, price in PRICES['livecall'].items():
            duration_text = f"{duration} Min" if duration < 60 else f"{duration//60} Std"
            row.append(InlineKeyboardButton(f"{duration_text} - {price}€", callback_data=f"select_package:livecall:{duration}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        keyboard.append([InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")])
        await send_tracked_message(context, chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "treffen_menu":
        await cleanup_bot_messages(chat_id, context)
        text = "📅 Wähle die gewünschte Dauer für dein Treffen:"
        keyboard = []
        row = []
        for duration in sorted(PRICES['treffen'].keys()):
            button_text = get_package_button_text('treffen', duration, user.id)
            row.append(InlineKeyboardButton(button_text, callback_data=f"select_treffen_duration:{duration}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🤔 Warum eine Anzahlung?", callback_data="treffen_info_anzahlung_menu")])
        keyboard.append([InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")])
        await send_tracked_message(context, chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["treffen_info_anzahlung_menu", "treffen_info_anzahlung_summary"]:
        text = (
            "🤔 **Warum eine kleine Anzahlung?** 🤔\n\n"
            "Ganz einfach: Sie ist eine kleine Sicherheit für uns beide! 🤝\n\n"
            "1️⃣ **Für dich:** Dein Termin ist damit fest für dich geblockt und niemand kann ihn dir wegschnappen. 🔒\n"
            "2️⃣ **Für mich:** Sie hilft mir, meine Anreise zu planen ✈️ und schützt mich vor Spaßbuchungen. So weiß ich, dass du es auch wirklich ernst meinst. 😊\n\n"
            "Den großen Rest zahlst du dann ganz entspannt und diskret in bar, wenn wir uns sehen. 💸"
        )
        if data == "treffen_info_anzahlung_menu":
            keyboard = [[InlineKeyboardButton("« Verstanden & zurück", callback_data="treffen_menu")]]
        else:
            keyboard = [[InlineKeyboardButton("« Verstanden & zurück zur Zahlung", callback_data="back_to_treffen_summary")]]
        
        # Da wir die Nachricht bearbeiten, müssen wir sie nicht erneut tracken
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    elif data == "back_to_treffen_summary":
        await show_treffen_summary(update, context)
        return

    elif data.startswith("select_treffen_duration:"):
        _, duration_str = data.split(":")
        context.user_data['treffen_buchung'] = {'duration': int(duration_str)}
        context.user_data['awaiting_input'] = 'treffen_date'
        text = "📅 Bitte gib dein Wunschdatum ein (z.B. `24.12`):"
        await query.edit_message_text(text, parse_mode='Markdown')
        return

    # ÜBERARBEITET: Logik für die Vorschau mit getrennten Nachrichten
    elif data.startswith("next_preview:"):
        if user_data.get("preview_clicks", 0) >= 25:
            await query.answer("Vorschau-Limit erreicht!", show_alert=True)
            await cleanup_bot_messages(chat_id, context)
            limit_text = "Du hast dein Vorschau-Limit von 25 Klicks erreicht. Sieh dir jetzt die Preise an, um mehr zu sehen!"
            limit_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Preise ansehen", callback_data="show_price_options")],
                [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]
            ])
            await send_tracked_message(context, chat_id, text=limit_text, reply_markup=limit_keyboard)
            return

        stats["users"][str(user.id)]["preview_clicks"] = user_data.get("preview_clicks", 0) + 1
        save_stats(stats)
        await track_event("next_preview", context, user.id)
        _, media_type = data.split(":")
        await send_or_update_admin_log(context, user, event_text=f"Nächstes Medium ({media_type})")

        media_paths = context.user_data.get('preview_gallery', [])
        if not media_paths: return

        index_key = f'preview_index_{media_type}'
        current_index = context.user_data.get(index_key, 0)
        next_index = (current_index + 1) % len(media_paths)
        context.user_data[index_key] = next_index

        media_path = media_paths[next_index]
        media_message_id = context.chat_data.get("media_message_id")
        
        if not media_message_id: # Fallback, falls etwas schiefgeht
            await send_preview_message(update, context, media_type, start_index=next_index)
            return

        try:
            with open(media_path, 'rb') as media_file:
                is_video = any(media_path.lower().endswith(ext) for ext in ['.mp4', '.mov', '.m4v'])
                new_media = InputMediaVideo(media=media_file) if is_video else InputMediaPhoto(media=media_file)
                await context.bot.edit_message_media(chat_id=chat_id, message_id=media_message_id, media=new_media)
        except error.BadRequest as e:
            if "message is not modified" in str(e): pass
            else: # Medientyp hat sich wahrscheinlich geändert, Nachricht neu senden
                await send_preview_message(update, context, media_type, start_index=next_index)
        except Exception: # Generischer Fallback
            await send_preview_message(update, context, media_type, start_index=next_index)
    
    elif data.startswith("select_package:"):
        await track_event("package_selected", context, user.id)
        _, media_type, amount_str = data.split(":")
        amount = int(amount_str)
        
        await cleanup_bot_messages(chat_id, context)

        if media_type == "livecall":
            await send_tracked_message(context, chat_id, text="✅ Ich bin für deinen Call verfügbar!")
            price = PRICES[media_type][amount]
            price_str = f"*{price}€*"
            text = (f"Du hast einen **Live Call** für **{amount} Minuten** für {price_str} ausgewählt.\n\n"
                    f"Bitte schließe die Bezahlung ab und melde dich danach bei **@{TELEGRAM_USERNAME}** mit einem Screenshot deiner Zahlung, um alles Weitere zu klären.")
            keyboard = [
                [InlineKeyboardButton(f"💸 {price}€ per PayPal", callback_data=f"pay_paypal:{media_type}:{amount}")],
                [InlineKeyboardButton(f"🎟️ {price}€ per Gutschein", callback_data=f"pay_voucher:{media_type}:{amount}")],
                [InlineKeyboardButton(f"🪙 {price}€ per Krypto", callback_data=f"pay_crypto:{media_type}:{amount}")],
                [InlineKeyboardButton("« Zurück", callback_data="live_call_menu")]
            ]
            await send_tracked_message(context, chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return

        base_price = PRICES[media_type][amount]
        package_key = f"{media_type}_{amount}"
        price = get_discounted_price(base_price, user_data.get("discounts"), package_key)
        if price == -1: price = base_price
        price_str = f"~{base_price}€~ *{price}€* (Rabatt)" if price != base_price else f"*{price}€*"
        
        text = f"Du hast das Paket **{amount} {media_type.capitalize()}** für {price_str} ausgewählt.\n\nWie möchtest du bezahlen?"
        if not user_data.get("paypal_offer_sent"):
            text += "\n\n🔥 *PayPal-Aktion: Kaufe 1, erhalte 2!* 🔥"
            stats["users"][str(user.id)]["paypal_offer_sent"] = True; save_stats(stats)
            
        keyboard = [[InlineKeyboardButton(" PayPal", callback_data=f"pay_paypal:{media_type}:{amount}")], [InlineKeyboardButton(" Gutschein (Amazon)", callback_data=f"pay_voucher:{media_type}:{amount}")], [InlineKeyboardButton("🪙 Krypto", callback_data=f"pay_crypto:{media_type}:{amount}")], [InlineKeyboardButton("« Zurück zu den Preisen", callback_data="show_price_options")]]
        await send_tracked_message(context, chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def update_payment_log(payment_method: str, price_val: int, package_info: str):
        stats_log = load_stats(); user_data_log = stats_log.get("users", {}).get(str(user.id))
        if user_data_log:
            payment_info = f"{payment_method} ({package_info}): {price_val}€"
            if payment_info not in user_data_log.get("payments_initiated", []):
                user_data_log.setdefault("payments_initiated", []).append(payment_info); save_stats(stats_log)
        await send_or_update_admin_log(context, user, event_text=f"Bezahlmethode '{payment_method}' für {price_val}€ gewählt")

    if data.startswith(("pay_paypal:", "pay_voucher:", "pay_crypto:")):
        _, media_type, amount_str = data.split(":")
        amount = int(amount_str)
        
        # Diese Nachricht wird bearbeitet, also muss sie nicht getrackt oder gecleant werden
        original_message = query.message

        if media_type == "livecall":
            price = PRICES[media_type][amount]
            package_info_text = f"{amount} Min Live Call"
        elif media_type == "treffen":
            price = ceil(PRICES[media_type][amount] / 4)
            duration_text = get_package_button_text('treffen', amount, user.id).split(' ')[0] + " " + get_package_button_text('treffen', amount, user.id).split(' ')[1]
            package_info_text = f"Anzahlung Treffen ({duration_text})"
        else:
            base_price = PRICES[media_type][amount]
            package_key = f"{media_type}_{amount}"
            price = get_discounted_price(base_price, user_data.get("discounts"), package_key)
            if price == -1: price = base_price
            package_info_text = f"{amount} {media_type.capitalize()}"

        if data.startswith("pay_paypal:"):
            await track_event(f"payment_{media_type}", context, user.id)
            await update_payment_log("PayPal", price, package_info_text)
            
            if NOTIFICATION_GROUP_ID:
                try:
                    user_mention = f"[{escape_markdown(user.first_name, version=2)}](tg://user?id={user.id})"
                    admin_notification_text = (f"💸 *PayPal-Zahlung für {package_info_text}* 💸\n\n" f"Nutzer {user_mention} (`{user.id}`) hat die Zahlung über *{price}€* eingeleitet.")
                    await context.bot.send_message(chat_id=NOTIFICATION_GROUP_ID, text=admin_notification_text, parse_mode='Markdown')
                except error.BadRequest as e:
                    logger.error(f"Could not send PayPal notification to group {NOTIFICATION_GROUP_ID}: {e}")

            paypal_link = f"https://paypal.me/{PAYPAL_USER}/{price}"
            text = (f"Super! Klicke auf den Link, um die Zahlung für **{package_info_text}** in Höhe von **{price}€** abzuschließen.\n\n" f"Gib als Verwendungszweck bitte deinen Telegram-Namen an.\n\n" f"➡️ [Hier sicher bezahlen]({paypal_link})\n\n")
            if media_type in ["livecall", "treffen"]: text += f"📲 *Melde dich danach bei @{TELEGRAM_USERNAME} mit einem Screenshot deiner Zahlung!*"
            
            back_button_data = "back_to_treffen_summary" if media_type == "treffen" else (f"select_package:{media_type}:{amount}" if media_type == "livecall" else "show_price_options")
            keyboard = [[InlineKeyboardButton("« Zurück zur Auswahl", callback_data=back_button_data)]]
            await original_message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown', disable_web_page_preview=True)
        
        elif data.startswith("pay_voucher:"):
            await track_event(f"payment_{media_type}", context, user.id); await update_payment_log("Gutschein", price, package_info_text)
            context.user_data["awaiting_voucher"] = "amazon"
            text = "Bitte sende mir jetzt deinen Amazon-Gutschein-Code als einzelne Nachricht."
            back_button_data = "back_to_treffen_summary" if media_type == "treffen" else (f"select_package:{media_type}:{amount}" if media_type == "livecall" else "show_price_options")
            keyboard = [[InlineKeyboardButton("Abbrechen", callback_data=back_button_data)]]
            await original_message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif data.startswith("pay_crypto:"):
            await track_event(f"payment_{media_type}", context, user.id); await update_payment_log("Krypto", price, package_info_text); text = "Bitte wähle die gewünschte Kryptowährung:"; keyboard = [[InlineKeyboardButton("Bitcoin (BTC)", callback_data=f"show_wallet:btc:{media_type}:{amount}"), InlineKeyboardButton("Ethereum (ETH)", callback_data=f"show_wallet:eth:{media_type}:{amount}")], [InlineKeyboardButton("« Zurück zur Paketauswahl", callback_data=f"select_package:{media_type}:{amount}")]]; await original_message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("show_wallet:"):
        _, crypto_type, media_type, amount_str = data.split(":")
        amount = int(amount_str)
        if media_type == "livecall": price = PRICES[media_type][amount]
        elif media_type == "treffen": price = ceil(PRICES[media_type][amount] / 4)
        else:
            base_price = PRICES[media_type][amount]
            package_key = f"{media_type}_{amount}"
            price = get_discounted_price(base_price, user_data.get("discounts"), package_key)
            if price == -1: price = base_price

        wallet_address = BTC_WALLET if crypto_type == "btc" else ETH_WALLET; crypto_name = "Bitcoin (BTC)" if crypto_type == "btc" else "Ethereum (ETH)"; text = (f"Zahlung mit **{crypto_name}** für **{price}€**.\n\nBitte sende den Betrag an die folgende Adresse und bestätige es hier, sobald du fertig bist:\n\n`{wallet_address}`"); keyboard = [[InlineKeyboardButton("« Zurück zur Krypto-Wahl", callback_data=f"pay_crypto:{media_type}:{amount}")]]; await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

def get_price_keyboard(user_id: int):
    return [
        [InlineKeyboardButton(get_package_button_text("bilder", 10, user_id), callback_data="select_package:bilder:10"), InlineKeyboardButton(get_package_button_text("videos", 10, user_id), callback_data="select_package:videos:10")],
        [InlineKeyboardButton(get_package_button_text("bilder", 25, user_id), callback_data="select_package:bilder:25"), InlineKeyboardButton(get_package_button_text("videos", 25, user_id), callback_data="select_package:videos:25")],
        [InlineKeyboardButton(get_package_button_text("bilder", 35, user_id), callback_data="select_package:bilder:35"), InlineKeyboardButton(get_package_button_text("videos", 35, user_id), callback_data="select_package:videos:35")],
        [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]
    ]

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) != ADMIN_USER_ID:
        await update.message.reply_text("⛔️ Du hast keine Berechtigung für diesen Befehl.")
        return
    await show_admin_menu(update, context)

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🔒 *Admin-Menü*\n\nWähle eine Option:"
    keyboard = [
        [InlineKeyboardButton("📊 Nutzer-Statistiken", callback_data="admin_stats_users"), InlineKeyboardButton("🖱️ Klick-Statistiken", callback_data="admin_stats_clicks")],
        [InlineKeyboardButton("🎟️ Gutscheine", callback_data="admin_show_vouchers")],
        [InlineKeyboardButton("👤 Nutzer verwalten", callback_data="admin_user_manage")]
        # Platz für weitere Admin-Buttons
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Wenn der Befehl /admin getippt wird, Nachricht bereinigen und Menü neu senden
    if update.message:
        await cleanup_bot_messages(update.effective_chat.id, context)
        await send_tracked_message(context, update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
    # Wenn es ein Callback ist, die bestehende Nachricht bearbeiten
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_user_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👤 *Nutzerverwaltung*\n\nWähle eine Aktion aus:"
    keyboard = [
        [InlineKeyboardButton("🚫 Nutzer sperren", callback_data="admin_user_ban_start")],
        [InlineKeyboardButton("✅ Nutzer entsperren", callback_data="admin_user_unban_start")],
        [InlineKeyboardButton("🖼️ Vorschau-Limit anpassen", callback_data="admin_preview_limit_start")],
        [InlineKeyboardButton("« Zurück", callback_data="admin_main_menu")]
    ]
    await query_or_message_edit(update, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_vouchers_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vouchers = load_vouchers()
    amazon_codes = "\n".join([f"- `{code}`" for code in vouchers.get("amazon", [])]) or "Keine"
    text = f"*Eingelöste Gutscheine*\n\n*Amazon:*\n{amazon_codes}"
    keyboard = [
        [InlineKeyboardButton("📄 Vouchers als PDF laden", callback_data="download_vouchers_pdf")],
        [InlineKeyboardButton("« Zurück zum Admin-Menü", callback_data="admin_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query_or_message_edit(update, text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text_input = update.message.text
    chat_id = update.effective_chat.id

    # Admin-Eingaben für Nutzerverwaltung etc.
    if str(user.id) == ADMIN_USER_ID:
        if context.user_data.get('awaiting_user_id_for_sperren'):
            await handle_admin_user_management_input(update, context, "sperren")
            return
        if context.user_data.get('awaiting_user_id_for_entsperren'):
            await handle_admin_user_management_input(update, context, "entsperren")
            return
        if context.user_data.get('awaiting_user_id_for_preview_limit'):
            await handle_admin_preview_limit_input(update, context)
            return

    if context.user_data.get('awaiting_input') == 'treffen_date':
        buchung = context.user_data.get('treffen_buchung', {})
        if re.match(r"^\d{1,2}\.\d{1,2}$", text_input):
            buchung['date'] = text_input
            context.user_data['treffen_buchung'] = buchung
            context.user_data['awaiting_input'] = 'treffen_location'
            await query_or_message_edit(update, text="📍 Und an welchem Ort (z.B. Stadt)?")
        else:
            await update.message.reply_text("Das Format ist ungültig. Bitte gib das Datum als `TT.MM` an.")
        return

    if context.user_data.get('awaiting_input') == 'treffen_location':
        buchung = context.user_data.get('treffen_buchung', {})
        buchung['location'] = text_input
        context.user_data['awaiting_input'] = None
        await show_treffen_summary(update, context)
        return

    if context.user_data.get("awaiting_voucher"):
        provider = context.user_data.pop("awaiting_voucher")
        code = text_input
        vouchers = load_vouchers()
        vouchers.setdefault(provider, []).append(code)
        save_vouchers(vouchers)
        notification_text = (f"📬 *Neuer Gutschein erhalten!* 📬\n\n" f"*Anbieter:* {provider.capitalize()}\n" f"*Code:* `{code}`\n" f"*Von Nutzer:* {escape_markdown(user.first_name, version=2)} (`{user.id}`)\n\n" f"⚠️ *AKTION ERFORDERLICH:* Bitte Code prüfen und den Nutzer manuell freischalten.")
        if NOTIFICATION_GROUP_ID: await context.bot.send_message(chat_id=NOTIFICATION_GROUP_ID, text=notification_text, parse_mode='Markdown')
        await send_or_update_admin_log(context, user, event_text=f"Gutschein '{provider}' eingereicht (wartet auf Prüfung)")
        
        await cleanup_bot_messages(chat_id, context)
        user_confirmation_text = ("✅ Vielen Dank! Dein Gutschein wurde erfolgreich übermittelt.\n\n" "Die manuelle Überprüfung dauert in der Regel **10-20 Minuten**. " "Sobald dein Code verifiziert ist, melde ich mich bei dir und du erhältst Zugriff auf deine Inhalte. " "Bitte habe einen Moment Geduld.")
        user_confirmation_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]])
        await send_tracked_message(context, chat_id, text=user_confirmation_text, reply_markup=user_confirmation_keyboard, parse_mode='Markdown')

async def handle_admin_user_management_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    user_id_to_manage = update.message.text
    context.user_data[f'awaiting_user_id_for_{action}'] = False
    
    if not user_id_to_manage.isdigit():
        await update.message.reply_text("⚠️ Ungültige ID. Bitte gib eine numerische Nutzer-ID ein.")
        return
        
    stats = load_stats()
    if user_id_to_manage not in stats.get("users", {}):
        await update.message.reply_text(f"⚠️ Nutzer mit der ID `{user_id_to_manage}` nicht gefunden.")
        return
        
    stats["users"][user_id_to_manage]["banned"] = True if action == "sperren" else False
    save_stats(stats)
    
    verb = "gesperrt" if action == "sperren" else "entsperrt"
    await update.message.reply_text(f"✅ Nutzer `{user_id_to_manage}` wurde erfolgreich *{verb}*.")
    await show_admin_menu(update, context)

async def handle_admin_preview_limit_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['awaiting_user_id_for_preview_limit'] = False
    user_id_to_manage = update.message.text
    
    if not user_id_to_manage.isdigit():
        await update.message.reply_text("⚠️ Ungültige ID. Bitte gib eine numerische Nutzer-ID ein.")
        return
        
    stats = load_stats()
    if user_id_to_manage not in stats.get("users", {}):
        await update.message.reply_text(f"⚠️ Nutzer mit der ID `{user_id_to_manage}` nicht gefunden.")
        return
        
    current_clicks = stats['users'][user_id_to_manage].get('preview_clicks', 0)
    text = f"Nutzer `{user_id_to_manage}` hat aktuell *{current_clicks}* Vorschau-Klicks.\n\nWas möchtest du tun?"
    keyboard = [
        [InlineKeyboardButton("Auf 0 zurücksetzen", callback_data=f"admin_preview_reset:{user_id_to_manage}")],
        [InlineKeyboardButton("Um 25 erhöhen", callback_data=f"admin_preview_increase:{user_id_to_manage}")],
        [InlineKeyboardButton("❌ Abbrechen", callback_data="admin_user_manage")]
    ]
    # Admin-Interaktionen bearbeiten die Nachricht, um den Chat sauber zu halten
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def execute_manage_preview_limit(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, action: str):
    stats = load_stats()
    user_data = stats.get("users", {}).get(user_id)
    if not user_data:
        await query_or_message_edit(update, f"Fehler: Nutzer {user_id} nicht gefunden.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="admin_user_manage")]]))
        return
        
    current_clicks = user_data.get('preview_clicks', 0)
    if action == 'reset':
        new_clicks = 0
    else: # 'increase'
        new_clicks = current_clicks + 25
        
    stats["users"][user_id]['preview_clicks'] = new_clicks
    save_stats(stats)
    
    text = f"✅ Vorschau-Limit für Nutzer `{user_id}` wurde auf *{new_clicks}* Klicks angepasst."
    await query_or_message_edit(update, text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="admin_user_manage")]]))

async def query_or_message_edit(update, text, **kwargs):
    """Bearbeitet eine Nachricht, egal ob sie von einem Callback oder einer Textnachricht stammt."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, **kwargs)
    # Wenn die ursprüngliche Aktion eine Textnachricht war, können wir sie nicht bearbeiten.
    # In diesem Fall senden wir eine neue Nachricht, die dann im nächsten Schritt bereinigt wird.
    elif update.message:
        await send_tracked_message(update.message.get_bot(), chat_id=update.effective_chat.id, text=text, **kwargs)

async def post_init(application: Application):
    await load_discounts_from_telegram(application)

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    if WEBHOOK_URL:
        port = int(os.environ.get("PORT", 8443))
        logger.info(f"Starting bot in webhook mode on port {port}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        logger.info("Starting bot in polling mode")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
