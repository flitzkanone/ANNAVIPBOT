import os
import logging
import json
import random
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Lade Umgebungsvariablen für lokale Entwicklung aus .env Datei
load_dotenv()

# --- Konfiguration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYPAL_USER = os.getenv("PAYPAL_USER")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
AGE_ANNA = os.getenv("AGE_ANNA", "18")
AGE_LUNA = os.getenv("AGE_LUNA", "21")

# Admin-Passwort ist fest im Code hinterlegt
ADMIN_PASSWORD = "1974"

# Preise sind fest im Code hinterlegt
PRICES = {
    "bilder": { 10: 5, 25: 10, 35: 15 },
    "videos": { 10: 15, 25: 25, 35: 30 },
}

# --- Pfad-Definitionen ---
VOUCHER_FILE = "vouchers.json"
MEDIA_DIR = "image"

# --- Logging einrichten ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Hilfsfunktionen (unverändert) ---
def load_vouchers():
    try:
        with open(VOUCHER_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"amazon": [], "paysafe": []}

def save_vouchers(vouchers):
    with open(VOUCHER_FILE, "w") as f:
        json.dump(vouchers, f, indent=2)

def get_media_files(schwester_code: str, media_type: str) -> list:
    matching_files = []
    target_prefix = f"{schwester_code.lower()}_{media_type.lower()}"
    if not os.path.isdir(MEDIA_DIR):
        logger.error(f"Media-Verzeichnis '{MEDIA_DIR}' nicht gefunden!")
        return []
    for filename in os.listdir(MEDIA_DIR):
        normalized_filename = filename.lower().lstrip('•-_ ').replace(' ', '_')
        if normalized_filename.startswith(target_prefix):
            matching_files.append(os.path.join(MEDIA_DIR, filename))
    return matching_files

# --- Handler-Funktionen ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Setzt den Nutzer-Zustand zurück, falls er z.B. bei der Passworteingabe war
    context.user_data.clear()
    
    welcome_text = (
        "Herzlich Willkommen! ✨\n\n"
        "Hier kannst du eine Vorschau meiner Inhalte sehen oder direkt ein Paket auswählen. "
        "Die gesamte Bedienung erfolgt über die Buttons."
    )
    keyboard = [
        [InlineKeyboardButton(" Vorschau", callback_data="show_preview_options")],
        [InlineKeyboardButton(" Preise & Pakete", callback_data="show_price_options")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(welcome_text, reply_markup=reply_markup)
        except Exception:
            await query.delete_message()
            await context.bot.send_message(
                chat_id=query.message.chat_id, 
                text=welcome_text, 
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# ... (handle_callback_query bleibt größtenteils gleich) ...
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        if query.message.text:
            await query.edit_message_text(text="⏳ Bearbeite deine Anfrage...")
    except Exception:
        pass
    if data == "main_menu":
        await start(update, context)
    elif data in ["show_preview_options", "show_price_options"]:
        action = "preview" if "preview" in data else "prices"
        text = "Für wen interessierst du dich?"
        keyboard = [
            [
                InlineKeyboardButton("Kleine Schwester", callback_data=f"select_schwester:ks:{action}"),
                InlineKeyboardButton("Große Schwester", callback_data=f"select_schwester:gs:{action}"),
            ],
            [InlineKeyboardButton("« Zurück", callback_data="main_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("select_schwester:"):
        _, schwester_code, action = data.split(":")
        media_type = "vorschau" if action == "preview" else "preis"
        image_paths = get_media_files(schwester_code, media_type)
        await query.delete_message()
        if not image_paths:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Ups! Ich konnte gerade keine passenden Inhalte finden. Bitte versuche es später erneut.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="main_menu")]])
            )
            return
        random_image_path = random.choice(image_paths)
        caption = ""
        keyboard_buttons = []
        if action == "preview":
            if schwester_code == 'gs':
                caption = f"Hey ich bin Anna, ich bin {AGE_ANNA} schreib mir gerne für mehr 😏 @Anna_2008_030."
            else:
                caption = f"Heyy ich bin Luna ich bin {AGE_LUNA} alt. Wenn du mehr willst schreib meiner Schwester @Anna_2008_030"
            keyboard_buttons = [[InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
        elif action == "prices":
            caption = "Wähle dein gewünschtes Paket:"
            keyboard_buttons = [
                [
                    InlineKeyboardButton("10 Bilder", callback_data="select_package:bilder:10"),
                    InlineKeyboardButton("10 Videos", callback_data=f"select_package:videos:10"),
                ],
                [
                    InlineKeyboardButton("25 Bilder", callback_data="select_package:bilder:25"),
                    InlineKeyboardButton("25 Videos", callback_data=f"select_package:videos:25"),
                ],
                [
                    InlineKeyboardButton("35 Bilder", callback_data="select_package:bilder:35"),
                    InlineKeyboardButton("35 Videos", callback_data=f"select_package:videos:35"),
                ],
                [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")],
            ]
        with open(random_image_path, 'rb') as photo_file:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo_file,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard_buttons)
            )
    elif data.startswith("select_package:"):
        _, media_type, amount_str = data.split(":")
        amount = int(amount_str)
        price = PRICES[media_type][amount]
        text = f"Du hast das Paket **{amount} {media_type.capitalize()}** für **{price}€** ausgewählt.\n\nWie möchtest du bezahlen?"
        keyboard = [
            [InlineKeyboardButton(" PayPal", callback_data=f"pay_paypal:{media_type}:{amount}")],
            [InlineKeyboardButton(" Gutschein", callback_data=f"pay_voucher:{media_type}:{amount}")],
            [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")],
        ]
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif data.startswith("pay_paypal:"):
        _, media_type, amount_str = data.split(":")
        amount = int(amount_str)
        price = PRICES[media_type][amount]
        paypal_link = f"https://paypal.me/{PAYPAL_USER}/{price}"
        text = (f"Super! Klicke auf den Link, um die Zahlung für **{amount} {media_type.capitalize()}** in Höhe von **{price}€** abzuschließen.\n\n"
                f"Gib als Verwendungszweck bitte deinen Telegram-Namen an.\n\n"
                f"➡️ [Hier sicher bezahlen]({paypal_link})")
        keyboard = [[InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown', disable_web_page_preview=True)
    elif data.startswith("pay_voucher:"):
        text = "Welchen Gutschein möchtest du einlösen?"
        keyboard = [
            [InlineKeyboardButton("Amazon", callback_data="voucher_provider:amazon"),
             InlineKeyboardButton("Paysafe", callback_data="voucher_provider:paysafe")],
            [InlineKeyboardButton("« Zurück", callback_data="show_price_options")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("voucher_provider:"):
        _, provider = data.split(":")
        context.user_data["awaiting_voucher"] = provider
        text = f"Bitte sende mir jetzt deinen {provider.capitalize()}-Gutscheincode als einzelne Nachricht."
        keyboard = [[InlineKeyboardButton("Abbrechen", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ##############################################################
# GEÄNDERT: Neue Funktion, die auf Texteingaben reagiert
# ##############################################################
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bearbeitet Texteingaben für verschiedene Zustände (Admin-Login, Gutschein)."""
    
    # Zustand 1: Bot wartet auf das Admin-Passwort
    if context.user_data.get("awaiting_admin_password"):
        password = update.message.text
        # Wichtig: Zustand sofort zurücksetzen, egal ob Passwort richtig oder falsch war
        del context.user_data["awaiting_admin_password"]

        if password == ADMIN_PASSWORD:
            vouchers = load_vouchers()
            amazon_codes = "\n".join([f"- `{code}`" for code in vouchers.get("amazon", [])]) or "Keine"
            paysafe_codes = "\n".join([f"- `{code}`" for code in vouchers.get("paysafe", [])]) or "Keine"
            text = (f"*Admin-Bereich*\n\n"
                    f"*Eingelöste Amazon-Gutscheine:*\n{amazon_codes}\n\n"
                    f"*Eingelöste Paysafe-Gutscheine:*\n{paysafe_codes}")
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text("Falsches Passwort.")

    # Zustand 2: Bot wartet auf einen Gutscheincode
    elif context.user_data.get("awaiting_voucher"):
        provider = context.user_data.pop("awaiting_voucher")
        code = update.message.text
        
        vouchers = load_vouchers()
        vouchers[provider].append(code)
        save_vouchers(vouchers)
        
        await update.message.reply_text(
            "Vielen Dank! Dein Gutschein wurde übermittelt und wird geprüft. "
            "Ich melde mich bei dir, sobald er verifiziert ist. ✨"
        )
        # Nach erfolgreicher Eingabe zurück zum Startmenü
        await start(update, context)

# ##############################################################
# GEÄNDERT: Die /admin Funktion startet nur noch den Login-Prozess
# ##############################################################
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Startet den Admin-Login, indem der Bot nach dem Passwort fragt."""
    context.user_data["awaiting_admin_password"] = True
    await update.message.reply_text("Bitte gib jetzt das Admin-Passwort ein:")


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Befehle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    
    # Button-Klicks
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Texteingaben (reagiert jetzt auf Admin-Passwort UND Gutscheine)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8443)),
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
        logger.info(f"Bot started in webhook mode on {WEBHOOK_URL}")
    else:
        application.run_polling()
        logger.info("Bot started in polling mode for local development")

if __name__ == "__main__":
    main()
