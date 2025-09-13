import os
import random
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")  # Passwort für Admin

# FastAPI-App (Render erwartet die Variable `app`)
app = FastAPI()

# Telegram-Bot initialisieren
bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

# Beispiel Preisliste-Bilder
preisliste_gross = ["preisliste-gross1.jpg", "preisliste-gross2.jpg", "preisliste-gross3.jpg"]

# Funktion: Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Vorschau", callback_data="vorschau")],
        [InlineKeyboardButton("Preise", callback_data="preise")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Willkommen! Wähle eine Option:", reply_markup=reply_markup)

# Funktion: CallbackQuery Handler
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Telegram-ack

    # Alte Nachricht löschen
    if query.message:
        try:
            await query.message.delete()
        except:
            pass

    if query.data == "vorschau":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="vorschau_klein")],
            [InlineKeyboardButton("Große Schwester", callback_data="vorschau_gross")],
            [InlineKeyboardButton("Zurück", callback_data="start")],
        ]
        await query.message.reply_text("Wähle eine Vorschau:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "preise":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="preise_klein")],
            [InlineKeyboardButton("Große Schwester", callback_data="preise_gross")],
            [InlineKeyboardButton("Zurück", callback_data="start")],
        ]
        await query.message.reply_text("Wähle eine Preisliste:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("preise_gross"):
        # Zufälliges Bild aus der Preisliste
        bild = random.choice(preisliste_gross)
        await query.message.reply_text(f"Hier ist die Preisliste: {bild}")

    elif query.data == "start":
        await start(update, context)

# Admin-Bereich
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Bitte gib das Admin-Passwort ein: /admin <passwort>")
        return
    if context.args[0] == ADMIN_PASSWORD:
        await update.message.reply_text("✅ Passwort korrekt! Adminbereich geöffnet.")
        # Beispiel-Daten
        daten = ["Code1", "Code2", "Code3"]
        await update.message.reply_text(f"Hier sind die Daten: {', '.join(daten)}")
    else:
        await update.message.reply_text("❌ Falsches Passwort!")

# Webhook-Route für FastAPI
@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    await application.update_queue.put(update)
    return {"ok": True}

# Handler registrieren
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(CommandHandler("admin", admin))

# Optional: Root-Endpoint für Render Healthchecks
@app.get("/")
async def root():
    return {"status": "Bot läuft!"}

# Direkt starten mit Uvicorn, falls lokal getestet
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
