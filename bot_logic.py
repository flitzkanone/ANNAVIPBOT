import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

IMAGE_DIR = 'image'

# --- Hilfsfunktionen ---

def get_random_image(prefix: str) -> str:
    """Findet ein zufälliges Bild im /image-Ordner basierend auf einem Präfix."""
    try:
        matching_files = [f for f in os.listdir(IMAGE_DIR) if f.startswith(prefix)]
        if not matching_files:
            return None
        return os.path.join(IMAGE_DIR, random.choice(matching_files))
    except FileNotFoundError:
        return None

async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bearbeitet die Nachricht, um den Chat sauber zu halten."""
    query = update.callback_query
    if query:
        await query.answer() # Bestätigt den Klick

async def show_loading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zeigt eine kurze Lade-Nachricht."""
    query = update.callback_query
    if query:
        await query.edit_message_text(text="⏳ Bitte einen Moment Geduld...")

# --- Hauptmenüs ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sendet die Willkommensnachricht mit dem Hauptmenü."""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🖼️ Vorschau ansehen", callback_data='menu_preview')],
        [InlineKeyboardButton("🛒 Preise & Pakete", callback_data='menu_prices')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Hallo {user.first_name}!\n\nWillkommen bei unserem Bot. Hier kannst du dir eine Vorschau unserer Inhalte ansehen oder direkt Pakete erwerben.",
        reply_markup=reply_markup
    )

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zeigt das Hauptmenü (wird nach 'Zurück' aufgerufen)."""
    await clear_chat(update, context)
    keyboard = [
        [InlineKeyboardButton("🖼️ Vorschau ansehen", callback_data='menu_preview')],
        [InlineKeyboardButton("🛒 Preise & Pakete", callback_data='menu_prices')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "Willkommen zurück im Hauptmenü. Was möchtest du tun?",
        reply_markup=reply_markup
    )

async def category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, menu_type: str):
    """Zeigt die Kategorie-Auswahl (kleine/große Schwester)."""
    await clear_chat(update, context)
    keyboard = [
        [
            InlineKeyboardButton("Kleine Schwester", callback_data=f'{menu_type}_ks'),
            InlineKeyboardButton("Große Schwester", callback_data=f'{menu_type}_gs')
        ],
        [InlineKeyboardButton("« Zurück zum Hauptmenü", callback_data='main_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        text="Bitte wähle eine Kategorie:",
        reply_markup=reply_markup
    )

# --- Vorschau-Logik ---

async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Sendet ein zufälliges Vorschaubild."""
    await clear_chat(update, context)
    await show_loading(update, context)

    prefix = f"{category}_vorschau_"
    image_path = get_random_image(prefix)

    # Alte Nachricht löschen, da wir jetzt ein Bild senden
    await update.callback_query.message.delete()
    
    if image_path:
        keyboard = [[InlineKeyboardButton("« Zurück zur Kategorie-Auswahl", callback_data='menu_preview')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=open(image_path, 'rb'),
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Fehler: Konnte kein Vorschaubild finden."
        )

# --- Preis- & Kauf-Logik ---

async def send_prices(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Sendet die Preisliste und die Paket-Auswahl."""
    await clear_chat(update, context)
    await show_loading(update, context)
    
    context.user_data['category'] = category # Kategorie für später speichern

    prefix = f"{category}_preis_"
    image_path = get_random_image(prefix)

    await update.callback_query.message.delete()
    
    if image_path:
        # Beispiel-Pakete. Passe die Preise und Namen hier an!
        keyboard = [
            [InlineKeyboardButton("Paket S (10 Items) - 15€", callback_data='pay_15')],
            [InlineKeyboardButton("Paket M (25 Items) - 30€", callback_data='pay_30')],
            [InlineKeyboardButton("Paket L (35 Items) - 40€", callback_data='pay_40')],
            [InlineKeyboardButton("« Zurück zur Kategorie-Auswahl", callback_data='menu_prices')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=open(image_path, 'rb'),
            caption="Wähle dein gewünschtes Paket:",
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Fehler: Konnte keine Preisliste finden."
        )

async def payment_options(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    """Zeigt die Bezahloptionen an."""
    await clear_chat(update, context)
    context.user_data['amount'] = amount

    keyboard = [
        [InlineKeyboardButton("💳 Mit PayPal bezahlen", callback_data='payment_paypal')],
        [InlineKeyboardButton("🎁 Mit Gutschein bezahlen", callback_data='payment_voucher')],
        [InlineKeyboardButton("« Zurück zur Paketauswahl", callback_data=f'prices_{context.user_data["category"]}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_caption( # .edit_message_caption für Nachrichten mit Bild
        caption=f"Du hast das Paket für {amount}€ ausgewählt. Wie möchtest du bezahlen?",
        reply_markup=reply_markup
    )

async def paypal_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generiert den PayPal-Link."""
    await clear_chat(update, context)
    amount = context.user_data.get('amount', 0)
    user_id = update.effective_user.id
    
    # ÄNDERE 'DEINPAYPALNAME' ZU DEINEM ECHTEN PAYPAL.ME NAMEN!
    paypal_link = f"https://paypal.me/DEINPAYPALNAME/{amount}" 
    
    keyboard = [
        [InlineKeyboardButton("✅ Weiter zu PayPal", url=paypal_link)],
        [InlineKeyboardButton("« Zurück", callback_data=f'pay_{amount}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_caption(
        caption=f"Klicke auf den Button, um die Zahlung abzuschließen.\n\nBitte gib als Referenz deine Telegram-ID an: `{user_id}`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def voucher_provider_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fragt nach dem Gutschein-Anbieter."""
    await clear_chat(update, context)
    amount = context.user_data.get('amount', 0)
    
    keyboard = [
        [
            InlineKeyboardButton("Amazon", callback_data='voucher_amazon'),
            InlineKeyboardButton("Paysafe", callback_data='voucher_paysafe')
        ],
        [InlineKeyboardButton("« Zurück", callback_data=f'pay_{amount}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_caption(
        caption="Welchen Gutschein möchtest du verwenden?",
        reply_markup=reply_markup
    )

async def request_voucher_code(update: Update, context: ContextTypes.DEFAULT_TYPE, provider: str):
    """Fordert den Nutzer auf, den Gutscheincode einzugeben."""
    await clear_chat(update, context)
    context.user_data['voucher_provider'] = provider
    
    # Alte Nachricht löschen und neue Textnachricht senden
    await update.callback_query.message.delete()
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Bitte sende mir jetzt deinen {provider.capitalize()}-Gutscheincode als einzelne Nachricht."
    )
    # Setze einen "State", damit der Bot weiß, dass die nächste Nachricht der Code ist
    context.user_data['state'] = 'awaiting_voucher'
