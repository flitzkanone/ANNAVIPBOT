import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

import bot_logic
import admin_logic
from database import init_db, save_voucher

# Lade Umgebungsvariablen aus der .env-Datei (für lokale Entwicklung)
load_dotenv()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- Callback Query Handler (Button-Klicks) ---
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == 'main_menu':
        await bot_logic.main_menu(update, context)
    elif data == 'menu_preview':
        await bot_logic.category_menu(update, context, 'preview')
    elif data == 'menu_prices':
        await bot_logic.category_menu(update, context, 'prices')
    elif data.startswith('preview_'):
        category = data.split('_')[1] # 'ks' oder 'gs'
        await bot_logic.send_preview(update, context, category)
    elif data.startswith('prices_'):
        category = data.split('_')[1]
        await bot_logic.send_prices(update, context, category)
    elif data.startswith('pay_'):
        amount = int(data.split('_')[1])
        await bot_logic.payment_options(update, context, amount)
    elif data == 'payment_paypal':
        await bot_logic.paypal_payment(update, context)
    elif data == 'payment_voucher':
        await bot_logic.voucher_provider_selection(update, context)
    elif data.startswith('voucher_'):
        provider = data.split('_')[1]
        await bot_logic.request_voucher_code(update, context, provider)

# --- Message Handler (für Gutscheincode-Eingabe) ---
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') == 'awaiting_voucher':
        voucher_code = update.message.text
        provider = context.user_data.get('voucher_provider', 'Unbekannt')
        user_id = update.effective_user.id
        
        # Gutschein speichern
        save_voucher(provider, voucher_code, user_id)
        
        await update.message.reply_text(
            "Vielen Dank! Dein Gutschein wurde übermittelt und wird überprüft. "
            "Du wirst kontaktiert, sobald er bestätigt ist."
        )
        # State zurücksetzen
        context.user_data['state'] = None
    else:
        # Optional: Standardantwort für unerwartete Texteingaben
        await update.message.reply_text("Bitte benutze die Buttons, um mit mir zu interagieren.")


def main():
    """Startet den Bot."""
    print("Bot wird gestartet...")
    
    # Datenbank initialisieren
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Befehle registrieren
    app.add_handler(CommandHandler("start", bot_logic.start))
    app.add_handler(CommandHandler("admin", admin_logic.admin_panel))

    # Button-Klicks registrieren
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    # Nachrichten-Handler für Gutscheincodes
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Bot starten
    app.run_polling()
    print("Bot wurde gestoppt.")

if __name__ == '__main__':
    main()
