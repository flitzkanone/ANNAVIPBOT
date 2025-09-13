import json
from datetime import datetime

GUTSCHEINE_FILE = "gutscheine.json"

def save_gutschein(user_id: int, anbieter: str, code: str):
    """Speichert einen neuen Gutscheincode."""
    try:
        with open(GUTSCHEINE_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []

    neuer_eintrag = {
        "user_id": user_id,
        "anbieter": anbieter,
        "code": code,
        "eingeloest_am": datetime.now().isoformat()
    }
    data.append(neuer_eintrag)

    with open(GUTS_CHEINE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_all_gutscheine() -> list:
    """Lädt alle gespeicherten Gutscheine."""
    try:
        with open(GUTSCHEINE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
