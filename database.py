import os
import psycopg2
from psycopg2 import sql

# Die Verbindungs-URL wird als Umgebungsvariable von Render bereitgestellt.
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """Stellt eine Verbindung zur PostgreSQL-Datenbank her."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Fehler bei der Datenbankverbindung: {e}")
        return None

def init_db():
    """Initialisiert die Datenbank und erstellt die Tabelle, falls sie nicht existiert."""
    conn = get_db_connection()
    if not conn:
        print("Konnte Datenbank nicht initialisieren, da keine Verbindung besteht.")
        return
        
    with conn.cursor() as cur:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS vouchers (
                id SERIAL PRIMARY KEY,
                provider VARCHAR(50) NOT NULL,
                code VARCHAR(255) NOT NULL,
                user_id BIGINT NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.commit()
    conn.close()
    print("Datenbanktabelle 'vouchers' ist bereit.")

def save_voucher(provider, code, user_id):
    """Speichert einen neuen Gutscheincode in der Datenbank."""
    conn = get_db_connection()
    if not conn:
        return

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vouchers (provider, code, user_id) VALUES (%s, %s, %s)",
            (provider, code, user_id)
        )
    conn.commit()
    conn.close()

def get_all_vouchers():
    """Ruft alle Gutscheine ab und sortiert sie nach Anbieter."""
    conn = get_db_connection()
    if not conn:
        return {}

    vouchers_by_provider = {}
    with conn.cursor() as cur:
        cur.execute("SELECT provider, code, user_id FROM vouchers ORDER BY provider")
        rows = cur.fetchall()
    
    conn.close()
    
    for provider, code, user_id in rows:
        provider_key = provider.upper()
        if provider_key not in vouchers_by_provider:
            vouchers_by_provider[provider_key] = []
        vouchers_by_provider[provider_key].append({'code': code, 'user_id': user_id})
        
    return vouchers_by_provider