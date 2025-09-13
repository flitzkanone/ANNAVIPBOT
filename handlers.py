import logging
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes

import data_manager
import config

# Logging einrichten
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Hilfsfunktionen ---

def get_random_media(path):
    """Wählt eine zufällige Mediendatei aus einem Ordner."""
    try:
        files = [os.path.join(path, f) for f in os.listdir(path) if not f.startswith('.')]
        return random.choice(files) if files else None
    except FileNotFoundError:
        return None

# --- Startmenü ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sendet das Startmenü."""
    keyboard = [
        [InlineKeyboardButton("🖼️ Vorschau", callback_data="menu_vorschau")],
        [InlineKeyboardButton("💰 Preise & Kaufen", callback_data="menu_preise")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Willkommen! Was möchtest du tun?", reply_markup=reply_markup)

# --- Callback-Handler (Button-Klicks) ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Verarbeitet alle Button-Klicks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]

    if action == "menu":
        if data[1] == "start":
            keyboard = [
                [InlineKeyboardButton("🖼️ Vorschau", callback_data="menu_vorschau")],
                [InlineKeyboardButton("💰 Preise & Kaufen", callback_data="menu_preise")],
            ]
            await query.edit_message_text("Willkommen! Was möchtest du tun?", reply_markup=InlineKeyboardMarkup(keyboard))
        elif data[1] == "vorschau":
            await show_schwester_selection(query, "vorschau")
        elif data[1] == "preise":
            await show_schwester_selection(query, "preise")

    elif action == "vorschau":
        schwester_typ = data[1]
        await send_random_preview(query, schwester_typ)

    elif action == "preise":
        schwester_typ = data[1]
        await send_pricelist_and_options(query, schwester_typ)
        
    elif action == "anzahl":
        _, schwester_typ, anzahl = data
        await show_payment_options(query, schwester_typ, anzahl)

    elif action == "payment":
        _, methode, schwester_typ, anzahl = data
        if methode == "paypal":
            await query.edit_message_text(f"Hier ist dein PayPal-Link: {config.PAYPAL_LINK}\n\nBitte sende nach der Zahlung einen Screenshot an den Admin.", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Zurück", callback_data=f"preise_{schwester_typ}")]]))
        elif methode == "gutschein":
            await show_voucher_provider_selection(query, schwester_typ, anzahl)
            
    elif action == "gutschein":
        _, anbieter, schwester_typ, anzahl = data
        # Speichere den Zustand für die nächste Nachricht des Nutzers
        context.user_data['gutschein_context'] = {'anbieter': anbieter, 'produkt': f'{schwester_typ}_{anzahl}'}
        await query.edit_message_text(f"Bitte sende jetzt deinen {anbieter.capitalize()}-Gutscheincode als Nachricht in diesen Chat.")


async def show_schwester_selection(query, menu_type):
    """Zeigt die Auswahl zwischen kleiner und großer Schwester."""
    keyboard = [
        [InlineKeyboardButton("Kleine Schwester", callback_data=f"{menu_type}_kleine")],
        [InlineKeyboardButton("Große Schwester", callback_data=f"{menu_type}_grosse")],
        [InlineKeyboardButton("⬅️ Zurück zum Start", callback_data="menu_start")],
    ]
    await query.edit_message_text("Bitte wähle aus:", reply_markup=InlineKeyboardMarkup(keyboard))


async def send_random_preview(query, schwester_typ):
    """Sendet ein zufälliges Vorschaubild/Video."""
    folder = f"media/{schwester_typ}_schwester/vorschau"
    media_file = get_random_media(folder)
    
    keyboard = [[InlineKeyboardButton("⬅️ Zurück", callback_data="menu_vorschau")]]
    
    if media_file:
        # Alte Nachricht löschen, um den Chat sauber zu halten
        await query.delete_message()
        if media_file.lower().endswith(('.jpg', '.jpeg', '.png')):
            await query.message.reply_photo(photo=open(media_file, 'rb'), reply_markup=InlineKeyboardMarkup(keyboard))
        elif media_file.lower().endswith('.mp4'):
            await query.message.reply_video(video=open(media_file, 'rb'), reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.edit_message_text("Keine Vorschau verfügbar.", reply_markup=InlineKeyboardMarkup(keyboard))


async def send_pricelist_and_options(query, schwester_typ):
    """Sendet Preisliste und danach die Mengen-Auswahl."""
    folder = f"media/{schwester_typ}_schwester/preise"
    pricelist_file = get_random_media(folder)
    
    if pricelist_file:
        await query.delete_message() # Alte Nachricht löschen
        await query.message.reply_photo(photo=open(pricelist_file, 'rb'))
    
    keyboard = [
        [
            InlineKeyboardButton("10 Bilder/Videos", callback_data=f"anzahl_{schwester_typ}_10"),
            InlineKeyboardButton("20 Bilder/Videos", callback_data=f"anzahl_{schwester_typ}_20"),
            InlineKeyboardButton("30 Bilder/Videos", callback_data=f"anzahl_{schwester_typ}_30"),
        ],
        [InlineKeyboardButton("⬅️ Zurück", callback_data="menu_preise")],
    ]
    await query.message.reply_text("Wähle die gewünschte Anzahl:", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_payment_options(query, schwester_typ, anzahl):
    """Zeigt die Bezahloptionen an."""
    keyboard = [
        [InlineKeyboardButton("💳 PayPal", callback_data=f"payment_paypal_{schwester_typ}_{anzahl}")],
        [InlineKeyboardButton("🎁 Gutschein", callback_data=f"payment_gutschein_{schwester_typ}_{anzahl}")],
        [InlineKeyboardButton("⬅️ Zurück", callback_data=f"preise_{schwester_typ}")],
    ]
    await query.edit_message_text(f"Du hast ausgewählt: {schwester_typ.replace('_', ' ').capitalize()} Schwester, {anzahl} Bilder/Videos.\nWie möchtest du bezahlen?", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_voucher_provider_selection(query, schwester_typ, anzahl):
    """Zeigt die Auswahl des Gutschein-Anbieters."""
    keyboard = [
        [InlineKeyboardButton("Amazon", callback_data=f"gutschein_amazon_{schwester_typ}_{anzahl}")],
        [InlineKeyboardButton("Paysafe", callback_data=f"gutschein_paysafe_{schwester_typ}_{anzahl}")],
        [InlineKeyboardButton("⬅️ Zurück", callback_data=f"anzahl_{schwester_typ}_{anzahl}")],
    ]
    await query.edit_message_text("Welchen Gutschein möchtest du verwenden?", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Text-Handler (für Gutscheincodes) ---

async def handle_gutschein_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Verarbeitet die Eingabe des Gutscheincodes."""
    if 'gutschein_context' in context.user_data:
        user_id = update.message.from_user.id
        code = update.message.text
        anbieter = context.user_data['gutschein_context']['anbieter']
        
        # Code speichern
        data_manager.save_gutschein(user_id, anbieter, code)
        
        # Nutzer benachrichtigen
        await update.message.reply_text("Danke! Dein Code wurde an den Admin weitergeleitet und wird überprüft.")
        
        # Admin benachrichtigen
        admin_info = (f" neuer Gutschein erhalten!\n"
                      f"Anbieter: {anbieter.capitalize()}\n"
                      f"Code: `{code}`\n"
                      f"Von User: `{user_id}`")
        try:
            await context.bot.send_message(chat_id=config.ADMIN_CHAT_ID, text=admin_info, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Konnte Admin-Nachricht nicht senden: {e}")
            
        # Zustand löschen
        del context.user_data['gutschein_context']


# --- Admin-Bereich ---

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Zeigt den Admin-Bereich nach Passwort-Eingabe."""
    if not context.args:
        await update.message.reply_text("Bitte gib ein Passwort an: /admin <passwort>")
        return

    password = context.args[0]
    if password == config.ADMIN_PASSWORD:
        gutscheine = data_manager.get_all_gutscheine()
        if not gutscheine:
            await update.message.reply_text("Bisher wurden keine Gutscheine eingelöst.")
            return
            
        response = "--- Eingelöste Gutscheine ---\n\n"
        # Sortiere nach Anbieter
        gutscheine_by_anbieter = {}
        for g in gutscheine:
            anbieter = g.get('anbieter', 'Unbekannt')
            if anbieter not in gutscheine_by_anbieter:
                gutscheine_by_anbieter[anbieter] = []
            gutscheine_by_anbieter[anbieter].append(g)

        for anbieter, codes in gutscheine_by_anbieter.items():
            response += f"--- {anbieter.upper()} ---\n"
            for code in codes:
                response += f"Code: {code['code']} (User: {code['user_id']} am {code['eingeloest_am']})\n"
            response += "\n"

        # Antwort in Chunks senden, falls sie zu lang wird
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i:i + 4096])
    else:
        await update.message.reply_text("Falsches Passwort.")
