"""
Gemeinsam genutzte Konstanten und Hilfsfunktionen für immocloud-Skripte.
Wird von immocloud_create_meters.py und immocloud_add_readings.py importiert.
"""

import csv
import getpass
import json
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

CSV_FILE   = Path(__file__).parent / "Ablesewerte_20260622-221802_semikolon.csv"
STATE_FILE = Path(__file__).parent / "meters_state.json"

BASE_URL   = "https://app.immocloud.de"
OBJECT_ID  = "68f14d32f0ad0e66f8c4068f"

# Mapping CSV-Nutzeinheit (1–8) → immocloud Unit
UNIT_MAP = {
    "1": {"id": "68f14d67f0ad0e66f8c4437f", "name": "20 - EG links"},      # EG L
    "2": {"id": "68f14d44f0ad0e66f8c42507", "name": "10 - EG rechts"},     # EG R
    "3": {"id": "68f14da0f0ad0e66f8c4755e", "name": "40 - 1. OG links"},   # 1.OG L
    "4": {"id": "68f14d8bf0ad0e66f8c46607", "name": "30 - 1. OG rechts"},  # 1.OG R
    "5": {"id": "68f173ebf0ad0e66f8dd2717", "name": "60 - 2. OG links"},   # 2.OG L
    "6": {"id": "68f17283f0ad0e66f8dce7b5", "name": "50 - 2. OG rechts"},  # 2.OG R
    "7": {"id": "68f1768bf0ad0e66f8debd13", "name": "80 - DG links"},      # DG L
    "8": {"id": "68f17583f0ad0e66f8de0ce2", "name": "70 - DG rechts"},     # DG R
}

METER_TYPE_MAP = {
    "HKVE":      "Heizung",
    "WWZ":       "Warmwasser",
    "FAM (WWZ)": "Warmwasser",
    "KWZ":       "Kaltwasser",
    "WMZ":       "Wärmemengenzähler",
}

METER_UNIT_MAP = {
    "HKVE":      "Sonstiges",  # dimensionslose HKE-Einheiten, kein kWh
    "WWZ":       "m³",
    "FAM (WWZ)": "m³",
    "KWZ":       "m³",
    "WMZ":       "MWh",
}

VERSORGER = "Meißner Stadtwerke Gmbh"

DATE_COLUMNS = [
    "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31",
    "2025-04-30", "2025-05-31", "2025-06-30", "2025-07-31",
    "2025-08-31", "2025-09-30", "2025-10-31", "2025-11-30", "2025-12-31",
]

FIRST_DATE = "2024-12-31"   # CSV-Spalte: Jahresendstand 2024 (= Anfangswert für 2025)
LAST_DATE  = "2025-12-31"   # CSV-Spalte: Jahresendstand 2025

# Spaltendatum → immocloud-Datum (Ausnahme: Vorjahressaldo wird als 01.01. eingetragen)
DATE_COLUMN_TO_IMMOCLOUD = {
    "2024-12-31": "01.01.2025",
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def iso_to_de(date_str: str) -> str:
    """YYYY-MM-DD → TT.MM.JJJJ"""
    y, m, d = date_str.split("-")
    return f"{d}.{m}.{y}"


def column_to_immocloud_date(col: str) -> str:
    """Wandelt eine CSV-Spaltenbeschriftung in das immocloud-Eingabedatum um."""
    return DATE_COLUMN_TO_IMMOCLOUD.get(col, iso_to_de(col))


def make_meter_name(raum: str, typ: str) -> str:
    typ_clean = typ.replace("FAM (WWZ)", "WWZ")
    return f"{raum}-{typ_clean}"


def make_location(stockwerk: str, lage: str, raum: str) -> str:
    parts = [p for p in [stockwerk, lage, raum] if p]
    return " ".join(parts)


def load_meters_for_unit(unit_nr: str) -> list:
    """Liest die CSV und gibt aktive Zähler der angegebenen Nutzeinheit zurück."""
    meters = []
    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if row.get("Nutzeinheit", "").strip() != unit_nr:
                continue

            geraet_nr = row.get("Geräte-Nr", "").strip()
            typ       = row.get("Typ", "").strip()
            raum      = row.get("Raum", "").strip()
            stockwerk = row.get("Stockwerk", "").strip()
            lage      = row.get("Lage", "").strip()
            einbau    = row.get("Einbau", "").strip()
            ausbau    = row.get("Ausbau", "").strip()

            if ausbau:
                print(f"  Überspringe ausgebauter Zähler {geraet_nr} (Ausbau: {ausbau})")
                continue
            if not geraet_nr:
                continue
            if typ not in METER_TYPE_MAP:
                print(f"  Überspringe unbekannter Typ '{typ}' für {geraet_nr}")
                continue

            meters.append({
                "geraet_nr":  geraet_nr,
                "typ":        typ,
                "meter_type": METER_TYPE_MAP[typ],
                "name":       make_meter_name(raum, typ),
                "location":   make_location(stockwerk, lage, raum),
                "einbau":     iso_to_de(einbau) if einbau else None,
                "unit_name":  UNIT_MAP[unit_nr]["name"],
            })

    return meters


def load_csv_value(unit_nr: str, geraet_nr: str, date_col: str) -> Optional[float]:
    """
    Liest den Wert einer Spalte für einen bestimmten Zähler aus der CSV.
    Gibt None zurück wenn kein/ungültiger Wert vorhanden.
    """
    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if row.get("Nutzeinheit", "").strip() != unit_nr:
                continue
            if row.get("Geräte-Nr", "").strip() != geraet_nr:
                continue
            raw = row.get(date_col, "").strip()
            if raw and raw not in ("[FS*]", ""):
                try:
                    return float(raw)
                except ValueError:
                    pass
    return None


def load_readings_for_unit(unit_nr: str, date_columns: list) -> dict:
    """
    Liest die CSV und gibt für jeden aktiven Zähler der Nutzeinheit die Werte
    der angegebenen Datumsspalten zurück.

    Returns:
        { geraet_nr: { "typ": "HKVE", "values": { "2025-04-30": 42.5, ... } }, ... }
    """
    result = {}
    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if row.get("Nutzeinheit", "").strip() != unit_nr:
                continue

            geraet_nr = row.get("Geräte-Nr", "").strip()
            typ       = row.get("Typ", "").strip()
            ausbau    = row.get("Ausbau", "").strip()

            if ausbau or not geraet_nr or typ not in METER_TYPE_MAP:
                continue

            values = {}
            for col in date_columns:
                raw = row.get(col, "").strip()
                if raw and raw not in ("[FS*]", ""):
                    try:
                        values[col] = float(raw)
                    except ValueError:
                        print(f"  Warnung: ungültiger Wert '{raw}' für {geraet_nr} Spalte {col}")

            result[geraet_nr] = {"typ": typ, "values": values}

    return result


# ---------------------------------------------------------------------------
# State-Datei (meters_state.json)
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Liest meters_state.json (Zähler-IDs, die Skript 1 gespeichert hat)."""
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    """Schreibt den aktuellen State nach meters_state.json."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"  State gespeichert: {STATE_FILE}")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def get_login_credentials():
    email    = input("\nE-Mail: ").strip()
    password = getpass.getpass("Passwort: ")
    return email, password


async def login(page: Page, email: str, password: str) -> None:
    print("Öffne Login-Seite...")
    await page.goto(f"{BASE_URL}/login")
    await page.wait_for_load_state("networkidle")
    await page.locator("input[type='email']").fill(email)
    await page.locator("input[type='password']").fill(password)
    await page.get_by_role("button", name="Login").click()
    print("Warte auf 2FA-Eingabe im Browser (max. 3 Minuten)...")
    print("→ Bitte den Verifizierungscode aus der E-Mail im Browser eingeben!")
    await page.wait_for_url(lambda url: "/login" not in url, timeout=180_000)
    print("Login + 2FA erfolgreich.")


# ---------------------------------------------------------------------------
# Ablesung eintragen
# ---------------------------------------------------------------------------

async def add_reading(page: Page, meter_id: str, date: str, value: float) -> None:
    """Trägt einen Zählerstand ein über /meters/{id}/readings/add."""
    print(f"    Ablesung: {date} = {value}")

    await page.goto(f"{BASE_URL}/meters/{meter_id}/readings/add")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(800)

    # pv_id_*-Inputs: nth(0) = Zählerstand, nth(1) = Datum
    # immocloud erwartet Komma als Dezimaltrennzeichen (z.B. "71,00")
    value_str = f"{value:.2f}".replace(".", ",")
    pv_inputs = page.locator("input[id^='pv_id']")

    value_field = pv_inputs.nth(0)
    await value_field.fill(value_str, force=True)

    date_field = pv_inputs.nth(1)
    await date_field.fill(date, force=True)
    # DatePicker-Panel schließen (öffnet sich nach fill und blockiert sonst den Save-Button)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(400)

    # Speichern — force=True wegen p-overlay-mask
    for btn_name in ["Speichern", "Eintragen", "Hinzufügen", "Zählerstand hinzufügen"]:
        btn = page.get_by_role("button", name=btn_name)
        if await btn.count():
            await btn.click(force=True)
            break
    else:
        await page.locator("button[type='submit']").first.click(force=True)

    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(500)
    print(f"    ✓ Ablesung {date} = {value_str} gespeichert.")
