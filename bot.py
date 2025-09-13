import os
import logging
import random
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# Lade Umgebungsvariablen aus einer .env Datei (für lokale Entwicklung)
load_dotenv()

# --- Konfiguration ---
# Für Render: Setze diese als "Environment Variables" im Render-Dashboard
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
PAYPAL_USERNAME = os.getenv("PAYPAL_USERNAME") # Dein PayPal.me Benutzername
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0)) # Optional: Deine Telegram Chat ID für Benachrichtigungen

# Logging einrichten, um Fehler zu sehen
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Pfade zu den Medien ---
BASE_DATA_PATH = "data"
PATHS = {
    "ks_vorschau": os.path.join(BASE_DATA_PATH, "ks_vorschau"),
    "gs_vorschau": os.path.join(BASE_DATA_PATH, "gs_vorschau"),
    "ks_preis": os.path.join(BASE_DATA_PATH, "ks_preis"),
    "gs_preis": os.path.join(BASE_DATA_PATH, "gs_preis"),
}

# --- Datenbank-Setup für Gutscheine ---
DB_FILE = os.path.join(BASE_DATA_PATH, "gutscheine.db")

def init_db():
    """Erstellt die Datenbanktabelle, falls sie nicht existiert."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gutscheine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anbieter TEXT NOT NULL,
            code TEXT NOT NULL,
            datum TEXT NOT NULL,
            user_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_voucher(anbieter, code, user_id):
    """Speichert einen eingelösten Gutschein in der Datenbank."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    datum = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO gutscheine (anbieter, code, datum, user_id) VALUES (?, ?, ?, ?)",
        (anbieter, code, datum, user_id)
    )
    conn.commit()
    conn.close()
    logger.info(f"Gutschein '{code}' von Anbieter '{anbieter}' gespeichert.")

# --- Hilfsfunktionen ---

async def delete_last_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Löscht die letzte vom Bot gesendete Nachricht, um die UI sauber zu halten."""
    if 'last_message_id' in context.user_data:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data['last_message_id'])
        except Exception as e:
            logger.warning(f"Konnte alte Nachricht nicht löschen: {e}")

def get_random_image_path(category_key: str) -> str | None:
    """Wählt ein zufälliges Bild aus einem Ordner."""
    directory = PATHS.get(category_key)
    if not directory or not os.path.exists(directory):
        return None
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    if not files:
        return None
    return os.path.join(directory, random.choice(files))

# --- Bot-Handler ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler für den /start Befehl. Zeigt das Hauptmenü an."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    await delete_last_message(context, chat_id)

    keyboard = [
        [InlineKeyboardButton("🖼️ Vorschau", callback_data="main_preview")],
        [InlineKeyboardButton("💰 Preise", callback_data="main_prices")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"Hallo {user.first_name}!\n\n"
        "Willkommen beim Verkaufs- & Vorschau-Bot. ✨\n\n"
        "Wähle eine Option, um zu starten:"
    )
    
    message = await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    context.user_data['last_message_id'] = message.message_id

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Zeigt das Hauptmenü nach einem Klick auf 'Zurück'."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    await delete_last_message(context, chat_id)

    keyboard = [
        [InlineKeyboardButton("🖼️ Vorschau", callback_data="main_preview")],
        [InlineKeyboardButton("💰 Preise", callback_data="main_prices")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = "Du bist zurück im Hauptmenü. Wähle eine Option:"
    
    message = await context.bot.send_message(chat_id=chat_id, text=welcome_text, reply_markup=reply_markup)
    context.user_data['last_message_id'] = message.message_id
    
async def show_sister_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Zeigt die Auswahl zwischen 'kleiner' und 'großer' Schwester."""
    query = update.callback_query
    await query.answer()
    
    # "main_preview" -> "preview", "main_prices" -> "prices"
    base_callback = query.data.split('_')[1] 

    keyboard = [
        [
            InlineKeyboardButton("Kleine Schwester", callback_data=f"{base_callback}_ks"),
            InlineKeyboardButton("Große Schwester", callback_data=f"{base_callback}_gs"),
        ],
        [InlineKeyboardButton("⬅️ Zurück zum Hauptmenü", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Für wen interessierst du dich?", reply_markup=reply_markup)

async def show_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Zeigt entweder eine Vorschau oder eine Preisliste."""
    query = update.callback_query
    await query.answer("⏳ Lade Inhalt...")
    chat_id = query.message.chat_id
    
    await delete_last_message(context, chat_id)

    # z.B. "preview_ks" -> 'preview', 'ks'
    action, sister = query.data.split('_')
    
    # z.B. 'preview_ks'
    category_key = f"{sister}_{action}"
    image_path = get_random_image_path(category_key)
    
    if not image_path:
        message = await context.bot.send_message(chat_id=chat_id, text="Fehler: Keine Bilder in dieser Kategorie gefunden.")
        context.user_data['last_message_id'] = message.message_id
        return

    # Buttons je nach Kontext (Vorschau oder Preise)
    if action == "preview":
        keyboard = [[InlineKeyboardButton("⬅️ Zurück", callback_data="main_preview")]]
        caption = "Hier ist eine zufällige Vorschau."
    elif action == "prices":
        keyboard = [
            [
                InlineKeyboardButton("Paket 1 (10€)", callback_data="buy_10"),
                InlineKeyboardButton("Paket 2 (25€)", callback_data="buy_25"),
                InlineKeyboardButton("Paket 3 (35€)", callback_data="buy_35"),
            ],
            [InlineKeyboardButton("⬅️ Zurück", callback_data="main_prices")],
        ]
        caption = "Hier ist die Preisliste. Wähle dein Paket:"
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Zurück zum Hauptmenü", callback_data="main_menu")]]
        caption = ""

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    with open(image_path, 'rb') as photo:
        message = await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, reply_markup=reply_markup)
    context.user_data['last_message_id'] = message.message_id
    
async def show_payment_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Zeigt die Bezahloptionen an."""
    query = update.callback_query
    await query.answer()

    amount = query.data.split('_')[1] # 'buy_10' -> '10'
    paypal_link = f"https://paypal.me/{PAYPAL_USERNAME}/{amount}EUR"

    keyboard = [
        [InlineKeyboardButton("💳 PayPal", url=paypal_link)],
        [InlineKeyboardButton("🎁 Gutschein", callback_data=f"voucher_{amount}")],
        [InlineKeyboardButton("⬅️ Zurück zu den Preisen", callback_data="main_prices")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(f"Du hast Paket für {amount}€ gewählt.\nBitte wähle deine Bezahlmethode:", reply_markup=reply_markup)

# --- Conversation Handler für Gutscheine ---
CHOOSE_PROVIDER, ENTER_CODE = range(2)

async def start_voucher_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Startet den Prozess zur Gutscheineingabe."""
    query = update.callback_query
    await query.answer()
    
    amount = query.data.split('_')[1]
    context.user_data['voucher_amount'] = amount

    keyboard = [
        [
            InlineKeyboardButton("Amazon", callback_data="provider_amazon"),
            InlineKeyboardButton("Paysafe", callback_data="provider_paysafe"),
        ],
        [InlineKeyboardButton("Abbrechen", callback_data="cancel_voucher")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text("Welchen Anbieter möchtest du nutzen?", reply_markup=reply_markup)
    return CHOOSE_PROVIDER

async def handle_provider_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Speichert den Anbieter und fragt nach dem Code."""
    query = update.callback_query
    await query.answer()

    provider = query.data.split('_')[1]
    context.user_data['voucher_provider'] = provider

    await query.edit_message_text(f"Okay, du hast {provider.capitalize()} gewählt.\n\nBitte sende mir jetzt den Gutscheincode als Nachricht.")
    return ENTER_CODE

async def handle_voucher_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Verarbeitet den eingegebenen Gutscheincode."""
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    code = update.message.text
    provider = context.user_data.get('voucher_provider', 'Unbekannt')
    amount = context.user_data.get('voucher_amount', '0')

    await delete_last_message(context, chat_id)
    
    # Speichere den Gutschein
    save_voucher(provider, code, user_id)
    
    # Informiere den Nutzer
    success_text = (
        "✅ Vielen Dank!\n\nDein Gutscheincode wurde übermittelt und wird so schnell wie möglich geprüft. "
        "Du wirst kontaktiert, sobald die Prüfung abgeschlossen ist."
    )
    message = await update.message.reply_text(success_text)
    context.user_data['last_message_id'] = message.message_id
    
    # Optional: Benachrichtige den Admin
    if ADMIN_CHAT_ID:
        admin_text = (
            f"🔔 Neuer Gutschein erhalten!\n\n"
            f"Anbieter: {provider.capitalize()}\n"
            f"Betrag: {amount}€\n"
            f"Code: `{code}`\n"
            f"User ID: `{user_id}`"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logger.error(f"Konnte Admin-Benachrichtigung nicht senden: {e}")

    # Beende die Konversation
    context.user_data.pop('voucher_provider', None)
    context.user_data.pop('voucher_amount', None)
    return ConversationHandler.END

async def cancel_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bricht die Gutscheineingabe ab."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("Gutscheineingabe abgebrochen.")
    
    # Zeige das Hauptmenü wieder an, um den Nutzer nicht im Leeren zu lassen
    await main_menu_callback(update, context)
    
    return ConversationHandler.END

# --- Admin-Funktionen ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler für den /admin Befehl."""
    if not context.args or context.args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("Passwort falsch oder nicht angegeben.")
        return

    await update.message.reply_text("✅ Admin-Zugang erfolgreich. Lade Gutscheine...")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT anbieter, code, datum, user_id FROM gutscheine ORDER BY anbieter, datum DESC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Bisher wurden keine Gutscheine eingelöst.")
        return
    
    # Gruppiere Gutscheine nach Anbieter
    vouchers_by_provider = {}
    for anbieter, code, datum, user_id in rows:
        if anbieter not in vouchers_by_provider:
            vouchers_by_provider[anbieter] = []
        vouchers_by_provider[anbieter].append(f"- `{code}` (User: {user_id} am {datum})")
    
    # Formatiere die Ausgabe
    response_text = "📜 **Eingelöste Gutscheine**\n\n"
    for anbieter, codes in vouchers_by_provider.items():
        response_text += f"**{anbieter.capitalize()}**:\n"
        response_text += "\n".join(codes)
        response_text += "\n\n"
    
    # Sende die Liste (ggf. in mehreren Nachrichten, falls sie zu lang wird)
    for i in range(0, len(response_text), 4096):
        await update.message.reply_text(response_text[i:i+4096], parse_mode=ParseMode.MARKDOWN_V2)

def main() -> None:
    """Startet den Bot."""
    if not all([TELEGRAM_TOKEN, ADMIN_PASSWORD, PAYPAL_USERNAME]):
        logger.error("Wichtige Umgebungsvariablen fehlen! (TELEGRAM_TOKEN, ADMIN_PASSWORD, PAYPAL_USERNAME)")
        return
        
    init_db()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Conversation Handler für Gutscheine
    voucher_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_voucher_payment, pattern=r'^voucher_\d+$')],
        states={
            CHOOSE_PROVIDER: [CallbackQueryHandler(handle_provider_choice, pattern=r'^provider_(amazon|paysafe)$')],
            ENTER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_voucher_code)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_voucher, pattern='^cancel_voucher$'),
            CommandHandler('start', start) # Erlaube Neustart jederzeit
        ],
    )

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    
    # Callback Query Handlers
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(show_sister_choice, pattern=r'^main_(preview|prices)$'))
    application.add_handler(CallbackQueryHandler(show_content, pattern=r'^(preview|prices)_(ks|gs)$'))
    application.add_handler(CallbackQueryHandler(show_payment_options, pattern=r'^buy_\d+$'))
    
    # Gutschein-Prozess
    application.add_handler(voucher_conv_handler)
    
    # Starte den Bot
    logger.info("Bot wird gestartet...")
    application.run_polling()

if __name__ == "__main__":
    main()
