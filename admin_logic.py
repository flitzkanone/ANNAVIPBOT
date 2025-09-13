import os
from telegram import Update
from telegram.ext import ContextTypes
from database import get_all_vouchers

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "default_password")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verwaltet den Zugang zum Admin-Bereich."""
    try:
        password = context.args[0]
    except (IndexError, ValueError):
        await update.message.reply_text("Bitte gib das Passwort an. Beispiel: /admin meinpasswort")
        return

    if password == ADMIN_PASSWORD:
        await update.message.reply_text("✅ Passwort korrekt. Lade die eingelösten Gutscheine...")
        
        vouchers = get_all_vouchers()
        
        if not vouchers:
            await update.message.reply_text("Bisher wurden keine Gutscheine eingelöst.")
            return
            
        response_message = "**--- Eingelöste Gutscheine ---**\n\n"
        
        for provider, items in vouchers.items():
            response_message += f"**{provider.upper()}:**\n"
            for item in items:
                response_message += f"- Code: `{item['code']}` | User-ID: `{item['user_id']}`\n"
            response_message += "\n"
            
        await update.message.reply_text(response_message, parse_mode='Markdown')
        
    else:
        await update.message.reply_text("❌ Falsches Passwort.")