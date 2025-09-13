import sqlite3
import os
from datetime import datetime

# --- VERBESSERTER TEIL ---
# Wir unterscheiden jetzt explizit zwischen lokalem und Render-Betrieb.
IS_ON_RENDER = os.environ.get("RENDER")

if IS_ON_RENDER:
    # Auf Render wird der /data-Ordner von der Persistent Disk bereitgestellt.
    # Wir dürfen ihn NICHT selbst erstellen.
    DATABASE_DIR = "/data"
else:
    # Lokal erstellen wir einen Unterordner namens 'database'.
    DATABASE_DIR = "database"

DATABASE_PATH = os.path.join(DATABASE_DIR, "vouchers.db")
# --- ENDE VERBESSERTER TEIL ---

def init_db():
    """Initialisiert die Datenbank und erstellt die Tabelle, falls sie nicht existiert."""
    
    # Den Ordner nur erstellen, wenn wir lokal laufen UND er noch nicht existiert.
    if not IS_ON_RENDER and not os.path.exists(DATABASE_DIR):
        print(f"Erstelle lokalen Datenbank-Ordner unter: {DATABASE_DIR}")
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
