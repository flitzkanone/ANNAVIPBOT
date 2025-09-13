import os
import random
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# --- ENV ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")
PAYPAL_LINKS = {
    "10_bilder": "https://paypal.me/deinlink10",
    "20_bilder": "https://paypal.me/deinlink20",
    "30_bilder": "https://paypal.me/deinlink30",
    "10_videos": "https://paypal.me/deinlink10v",
    "20_videos": "https://paypal.me/deinlink20v",
    "30_videos": "https://paypal.me/deinlink30v",
}

# --- Bilderlisten ---
vorschau_klein = ["vorschau-klein1.jpg", "vorschau-klein2.jpg"]
vorschau_gross = ["vorschau-gross1.jpg", "vorschau-gross2.jpg"]
preisliste_klein = ["preisliste-klein1.jpg", "preisliste-klein2.jpg"]
preisliste_gross = ["preisliste-gross1.jpg", "preisliste-gross2.jpg", "preisliste-gross3.jpg"]

# --- FastAPI ---
app = FastAPI()

# --- Telegram Application ---
application = ApplicationBuilder().token(BOT_TOKEN).build()

# --- Helper Functions ---
def create_menu(buttons: list[list[InlineKeyboardButton]]):
    return InlineKeyboardMarkup(buttons)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Vorschau", callback_data="vorschau")],
        [InlineKeyboardButton("Preise", callback_data="preise")],
    ]
    if update.message:
        await update.message.reply_text("Willkommen! Wähle eine Option:", reply_markup=create_menu(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text("Willkommen! Wähle eine Option:", reply_markup=create_menu(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # --- Hauptbuttons ---
    if query.data == "vorschau":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="vorschau_klein")],
            [InlineKeyboardButton("Große Schwester", callback_data="vorschau_gross")],
            [InlineKeyboardButton("Zurück", callback_data="start")],
        ]
        await query.edit_message_text("Wähle eine Vorschau:", reply_markup=create_menu(keyboard))

    elif query.data == "preise":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="preise_klein")],
            [InlineKeyboardButton("Große Schwester", callback_data="preise_gross")],
            [InlineKeyboardButton("Zurück", callback_data="start")],
        ]
        await query.edit_message_text("Wähle eine Preisliste:", reply_markup=create_menu(keyboard))

    # --- Vorschau ---
    elif query.data == "vorschau_klein":
        bild = random.choice(vorschau_klein)
        keyboard = [[InlineKeyboardButton("Zurück", callback_data="vorschau")]]
        await query.edit_message_text(f"Hier ist die Vorschau: {bild}", reply_markup=create_menu(keyboard))
    elif query.data == "vorschau_gross":
        bild = random.choice(vorschau_gross)
        keyboard = [[InlineKeyboardButton("Zurück", callback_data="vorschau")]]
        await query.edit_message_text(f"Hier ist die Vorschau: {bild}", reply_markup=create_menu(keyboard))

    # --- Preisliste ---
    elif query.data == "preise_klein":
        bild = random.choice(preisliste_klein)
        keyboard = [
            [InlineKeyboardButton("10 Bilder", callback_data="10_bilder")],
            [InlineKeyboardButton("20 Bilder", callback_data="20_bilder")],
            [InlineKeyboardButton("30 Bilder", callback_data="30_bilder")],
            [InlineKeyboardButton("10 Videos", callback_data="10_videos")],
            [InlineKeyboardButton("20 Videos", callback_data="20_videos")],
            [InlineKeyboardButton("30 Videos", callback_data="30_videos")],
            [InlineKeyboardButton("Zurück", callback_data="preise")],
        ]
        await query.edit_message_text(f"Preisliste Kleine Schwester: {bild}", reply_markup=create_menu(keyboard))

    elif query.data == "preise_gross":
        bild = random.choice(preisliste_gross)
        keyboard = [
            [InlineKeyboardButton("10 Bilder", callback_data="10_bilder")],
            [InlineKeyboardButton("20 Bilder", callback_data="20_bilder")],
            [InlineKeyboardButton("30 Bilder", callback_data="30_bilder")],
            [InlineKeyboardButton("10 Videos", callback_data="10_videos")],
            [InlineKeyboardButton("20 Videos", callback_data="20_videos")],
            [InlineKeyboardButton("30 Videos", callback_data="30_videos")],
            [InlineKeyboardButton("Zurück", callback_data="preise")],
        ]
        await query.edit_message_text(f"Preisliste Große Schwester: {bild}", reply_markup=create_menu(keyboard))

    # --- PayPal / Gutscheine ---
    elif query.data in PAYPAL_LINKS:
        keyboard = [
            [InlineKeyboardButton("Mit Gutschein zahlen", callback_data=f"gutschein_{query.data}")],
            [InlineKeyboardButton("Zurück", callback_data="preise")],
        ]
        await query.edit_message_text(f"Hier ist dein PayPal-Link: {PAYPAL_LINKS[query.data]}", reply_markup=create_menu(keyboard))

    elif query.data.startswith("gutschein_"):
        item = query.data.replace("gutschein_", "")
        keyboard = [
            [InlineKeyboardButton("Amazon", callback_data=f"gutschein_input_{item}_amazon")],
            [InlineKeyboardButton("Paysafe", callback_data=f"gutschein_input_{item}_paysafe")],
            [InlineKeyboardButton("Zurück", callback_data="preise")],
        ]
        await query.edit_message_text("Wähle den Anbieter des Gutscheins:", reply_markup=create_menu(keyboard))

# --- Admin ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Falsches Passwort oder fehlt!")
        return
    await update.message.reply_text("✅ Passwort korrekt! Adminbereich geöffnet.")

# --- Telegram Handler registrieren ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(CommandHandler("admin", admin))

# --- Webhook für Render ---
@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
    await application.update_queue.put(update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"status": "Bot läuft!"}
