import os
import logging
import json
import random
from dotenv import load_dotenv
from datetime import datetime
from io import BytesIO

# NEU: Bibliothek zum Erstellen von PDFs
from fpdf import FPDF

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
MEDIA_DIR = "image"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Hilfsfunktionen (unverändert) ---
def load_vouchers():
    try:
        with open(VOUCHER_FILE, "r") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {"amazon": [], "paysafe": []}

def save_vouchers(vouchers):
    with open(VOUCHER_FILE, "w") as f: json.dump(vouchers, f, indent=2)

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

# --- Bot Handler-Funktionen ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (Code unverändert)
    context.user_data.clear()
    welcome_text = ( "Herzlich Willkommen! ✨\n\n...") # Gekürzt
    keyboard = [[InlineKeyboardButton(" Vorschau", callback_data="show_preview_options")], [InlineKeyboardButton(" Preise & Pakete", callback_data="show_price_options")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        query = update.callback_query; await query.answer()
        try: await query.edit_message_text(welcome_text, reply_markup=reply_markup)
        except Exception:
            await query.delete_message()
            await context.bot.send_message(chat_id=query.message.chat_id, text=welcome_text, reply_markup=reply_markup)
    else: await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); data = query.data
    
    # ##############################################################
    # NEUE FUNKTION: PDF-Download
    # ##############################################################
    if data == "download_vouchers_pdf":
        await query.answer("PDF wird erstellt...")
        
        vouchers = load_vouchers()
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=16)
        
        # Titel
        pdf.cell(0, 10, "Gutschein Report", ln=True, align='C')
        pdf.ln(10)

        pdf.set_font("Arial", size=12)
        
        # Amazon Gutscheine
        pdf.set_font("Arial", 'B', size=14)
        pdf.cell(0, 10, "Amazon Gutscheine", ln=True)
        pdf.set_font("Arial", size=12)
        if vouchers.get("amazon"):
            for code in vouchers["amazon"]:
                pdf.cell(0, 8, f"- {code}", ln=True)
        else:
            pdf.cell(0, 8, "Keine vorhanden.", ln=True)
        pdf.ln(5)

        # Paysafe Gutscheine
        pdf.set_font("Arial", 'B', size=14)
        pdf.cell(0, 10, "Paysafe Gutscheine", ln=True)
        pdf.set_font("Arial", size=12)
        if vouchers.get("paysafe"):
            for code in vouchers["paysafe"]:
                pdf.cell(0, 8, f"- {code}", ln=True)
        else:
            pdf.cell(0, 8, "Keine vorhanden.", ln=True)
        
        # PDF in den Arbeitsspeicher schreiben
        pdf_buffer = BytesIO(pdf.output(dest='S').encode('latin-1'))
        pdf_buffer.seek(0)
        
        # Heutiges Datum für den Dateinamen
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_buffer,
            filename=f"Gutschein-Report_{today_str}.pdf",
            caption="Hier ist dein aktueller Gutschein-Report."
        )
        return

    # Der restliche Code der Funktion
    try:
        if query.message.text: await query.edit_message_text(text="⏳ Bearbeite deine Anfrage...")
    except Exception: pass
    if data == "main_menu": await start(update, context)
    # ... (der ganze Rest der handle_callback_query Funktion bleibt unverändert)
    elif data in ["show_preview_options", "show_price_options"]:
        action = "preview" if "preview" in data else "prices"; text = "Für wen interessierst du dich?"
        keyboard = [[InlineKeyboardButton("Kleine Schwester", callback_data=f"select_schwester:ks:{action}"), InlineKeyboardButton("Große Schwester", callback_data=f"select_schwester:gs:{action}")], [InlineKeyboardButton("« Zurück", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("select_schwester:"):
        _, schwester_code, action = data.split(":"); media_type = "vorschau" if action == "preview" else "preis"; image_paths = get_media_files(schwester_code, media_type)
        try: await query.delete_message()
        except Exception: pass
        if not image_paths:
            await context.bot.send_message(chat_id=query.message.chat_id, text="Ups! Ich konnte gerade keine passenden Inhalte finden...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Zurück", callback_data="main_menu")]])); return
        random_image_path = random.choice(image_paths); caption = ""; keyboard_buttons = []
        if action == "preview":
            if schwester_code == 'gs': caption = f"Hey ich bin Anna, ich bin {AGE_ANNA} schreib mir gerne für mehr 😏 @Anna_2008_030."
            else: caption = f"Heyy ich bin Luna ich bin {AGE_LUNA} alt. Wenn du mehr willst schreib meiner Schwester @Anna_2008_030"
            keyboard_buttons = [[InlineKeyboardButton("🛍️ Zu den Preisen", callback_data=f"select_schwester:{schwester_code}:prices")], [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
        elif action == "prices":
            caption = "Wähle dein gewünschtes Paket:"; keyboard_buttons = [[InlineKeyboardButton("10 Bilder", callback_data="select_package:bilder:10"), InlineKeyboardButton("10 Videos", callback_data="select_package:videos:10")], [InlineKeyboardButton("25 Bilder", callback_data="select_package:bilder:25"), InlineKeyboardButton("25 Videos", callback_data="select_package:videos:25")], [InlineKeyboardButton("35 Bilder", callback_data="select_package:bilder:35"), InlineKeyboardButton("35 Videos", callback_data="select_package:videos:35")], [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
        with open(random_image_path, 'rb') as photo_file: await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo_file, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard_buttons))
    elif data.startswith("select_package:"):
        _, media_type, amount_str = data.split(":"); amount = int(amount_str); price = PRICES[media_type][amount]; text = f"Du hast das Paket **{amount} {media_type.capitalize()}** für **{price}€** ausgewählt.\n\nWie möchtest du bezahlen?"
        keyboard = [[InlineKeyboardButton(" PayPal", callback_data=f"pay_paypal:{media_type}:{amount}")], [InlineKeyboardButton(" Gutschein", callback_data=f"pay_voucher:{media_type}:{amount}")], [InlineKeyboardButton("🪙 Krypto", callback_data=f"pay_crypto:{media_type}:{amount}")], [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data="main_menu")]]
        await query.message.delete(); await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("pay_crypto:"):
        _, media_type, amount = data.split(":"); text = "Bitte wähle die gewünschte Kryptowährung:"
        keyboard = [[InlineKeyboardButton("Bitcoin (BTC)", callback_data=f"show_wallet:btc:{media_type}:{amount}"), InlineKeyboardButton("Ethereum (ETH)", callback_data=f"show_wallet:eth:{media_type}:{amount}")], [InlineKeyboardButton("« Zurück zur Bezahlwahl", callback_data=f"select_package:{media_type}:{amount}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    # ... etc.

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_admin_password"):
        password = update.message.text; del context.user_data["awaiting_admin_password"]
        if password == ADMIN_PASSWORD:
            vouchers = load_vouchers()
            amazon_codes = "\n".join([f"- `{code}`" for code in vouchers.get("amazon", [])]) or "Keine"
            paysafe_codes = "\n".join([f"- `{code}`" for code in vouchers.get("paysafe", [])]) or "Keine"
            text = (f"*Admin-Bereich*\n\n*Eingelöste Amazon-Gutscheine:*\n{amazon_codes}\n\n*Eingelöste Paysafe-Gutscheine:*\n{paysafe_codes}")
            
            # --- GEÄNDERT: Neuer Button im Admin-Bereich ---
            keyboard = [[InlineKeyboardButton("📄 Vouchers als PDF laden", callback_data="download_vouchers_pdf")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        else: await update.message.reply_text("Falsches Passwort.")
    elif context.user_data.get("awaiting_voucher"):
        # ... (unverändert)
        provider = context.user_data.pop("awaiting_voucher"); code = update.message.text; vouchers = load_vouchers(); vouchers[provider].append(code); save_vouchers(vouchers)
        await update.message.reply_text("Vielen Dank! Dein Gutschein wurde übermittelt..."); await start(update, context)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_admin_password"] = True; await update.message.reply_text("Bitte gib jetzt das Admin-Passwort ein:")

async def add_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    if not ADMIN_USER_ID or user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔️ Du hast keine Berechtigung für diesen Befehl."); return
    # ... (Rest der Funktion unverändert)
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Bitte gib den Befehl im richtigen Format an...", parse_mode='Markdown'); return
    provider = context.args[0].lower()
    if provider not in ["amazon", "paysafe"]:
        await update.message.reply_text("Fehler: Anbieter muss 'amazon' oder 'paysafe' sein."); return
    code = " ".join(context.args[1:]); vouchers = load_vouchers(); vouchers[provider].append(code); save_vouchers(vouchers)
    await update.message.reply_text(f"✅ Gutschein für **{provider.capitalize()}** erfolgreich hinzugefügt:\n`{code}`", parse_mode='Markdown')

def main() -> None:
    """Startet den Bot."""
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("addvoucher", add_voucher))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8443)),
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
