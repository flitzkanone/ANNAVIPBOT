import sqlite3
import os
from datetime import datetime

# Wichtiger Hinweis für Render.com:
# Render verwendet einen "Persistent Disk" unter /data.
# Lokal wird die DB im Unterordner /database erstellt.
DATABASE_DIR = "/data" if os.environ.get("RENDER") else "database"
DATABASE_PATH = os.path.join(DATABASE_DIR, "vouchers.db")

def init_db():
    """Initialisiert die Datenbank und erstellt die Tabelle, falls sie nicht existiert."""
    if not os.path.exists(DATABASE_DIR):
        os.makedirs(DATABASE_DIR)
        
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_voucher(provider, code, user_id):
    """Speichert einen neuen Gutscheincode in der Datenbank."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vouchers (provider, code, user_id) VALUES (?, ?, ?)",
        (provider, code, user_id)
    )
    conn.commit()
    conn.close()

def get_all_vouchers():
    """Ruft alle Gutscheine ab und sortiert sie nach Anbieter."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT provider, code, user_id FROM vouchers ORDER BY provider")
    rows = cursor.fetchall()
    conn.close()
    
    vouchers_by_provider = {}
    for provider, code, user_id in rows:
        if provider not in vouchers_by_provider:
            vouchers_by_provider[provider] = []
        vouchers_by_provider[provider].append({'code': code, 'user_id': user_id})
        
    return vouchers_by_provider
