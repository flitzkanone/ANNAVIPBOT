import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")  # z.B. "1234"

# Beispiel-Daten
vorschau_klein = ["vorschau-klein1.jpg", "vorschau-klein2.jpg"]
vorschau_gross = ["vorschau-gross1.jpg", "vorschau-gross2.jpg"]
preisliste_klein = ["preisliste-klein1.jpg", "preisliste-klein2.jpg", "preisliste-klein3.jpg"]
preisliste_gross = ["preisliste-gross1.jpg", "preisliste-gross2.jpg", "preisliste-gross3.jpg"]

paypal_links = {
    "10bilder": "https://paypal.me/deinlink10bilder",
    "20bilder": "https://paypal.me/deinlink20bilder",
    "10videos": "https://paypal.me/deinlink10videos"
}

# Session-Speicher für letzte Nachricht
last_message = {}

async def delete_last_message(chat_id, context: ContextTypes.DEFAULT_TYPE):
    if chat_id in last_message:
        try:
            await context.bot.delete_message(chat_id, last_message[chat_id])
        except:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await delete_last_message(chat_id, context)
    text = (
        "👋 Willkommen!\n"
        "Hier verkauft Anna Inhalte. Level der Leute:\n"
        "• Kleine Schwester\n"
        "• Große Schwester"
    )
    keyboard = [[InlineKeyboardButton("Weiter ➡️", callback_data="weiter")]]
    msg = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    last_message[chat_id] = msg.message_id

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    await delete_last_message(chat_id, context)

    if query.data == "weiter":
        keyboard = [
            [InlineKeyboardButton("Vorschau", callback_data="vorschau")],
            [InlineKeyboardButton("Preise", callback_data="preise")]
        ]
        msg = await query.message.reply_text("Wähle aus:", reply_markup=InlineKeyboardMarkup(keyboard))
        last_message[chat_id] = msg.message_id

    elif query.data == "vorschau":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="vorschau_klein")],
            [InlineKeyboardButton("Große Schwester", callback_data="vorschau_gross")],
            [InlineKeyboardButton("⬅️ Zurück", callback_data="weiter")]
        ]
        msg = await query.message.reply_text("Vorschau wählen:", reply_markup=InlineKeyboardMarkup(keyboard))
        last_message[chat_id] = msg.message_id

    elif query.data == "preise":
        keyboard = [
            [InlineKeyboardButton("Kleine Schwester", callback_data="preise_klein")],
            [InlineKeyboardButton("Große Schwester", callback_data="preise_gross")],
            [InlineKeyboardButton("⬅️ Zurück", callback_data="weiter")]
        ]
        msg = await query.message.reply_text("Preise wählen:", reply_markup=InlineKeyboardMarkup(keyboard))
        last_message[chat_id] = msg.message_id

    elif query.data.startswith("vorschau_"):
        if query.data == "vorschau_klein":
            image = random.choice(vorschau_klein)
        else:
            image = random.choice(vorschau_gross)
        keyboard = [[InlineKeyboardButton("⬅️ Zurück", callback_data="vorschau")]]
        msg = await query.message.reply_text(f"⏳ Lade Bild…")
        last_message[chat_id] = msg.message_id
        await asyncio.sleep(1)
        await delete_last_message(chat_id, context)
        msg = await query.message.reply_text(f"[Bild: {image}]", reply_markup=InlineKeyboardMarkup(keyboard))
        last_message[chat_id] = msg.message_id

    elif query.data.startswith("preise_"):
        if query.data == "preise_klein":
            image = random.choice(preisliste_klein)
        else:
            image = random.choice(preisliste_gross)
        keyboard = [[InlineKeyboardButton("⬅️ Zurück", callback_data="preise")]]
        msg = await query.message.reply_text(f"[Preisliste: {image}]", reply_markup=InlineKeyboardMarkup(keyboard))
        last_message[chat_id] = msg.message_id

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await delete_last_message(chat_id, context)
    if len(context.args) == 0:
        msg = await update.message.reply_text("Bitte Passwort eingeben: /admin <passwort>")
        last_message[chat_id] = msg.message_id
        return
    if context.args[0] == ADMIN_PASSWORD:
        msg = await update.message.reply_text("✅ Passwort korrekt! Hier sind die Daten:\n• Beispiel 1\n• Beispiel 2")
    else:
        msg = await update.message.reply_text("❌ Passwort falsch!")
    last_message[chat_id] = msg.message_id

async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await delete_last_message(chat_id, context)
    code = update.message.text
    msg = await update.message.reply_text(f"⏳ Prüfe Code: {code}")
    last_message[chat_id] = msg.message_id
    await asyncio.sleep(1)
    await delete_last_message(chat_id, context)
    msg = await update.message.reply_text(f"✅ Code {code} akzeptiert!")
    last_message[chat_id] = msg.message_id

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("admin", admin_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, code_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
