"""
Playwright-Skript: Ablesewerte aus CSV in immocloud eintragen.

Verwendung:
    python immocloud_add_readings.py <nutzeinheit> <datumsspalten> [--dry-run]

    <datumsspalten>  Kommagetrennte ISO-Daten aus der CSV-Kopfzeile.
                     Sonderfall "2024-12-31": Vorjahreswert → wird als 01.01.2025 eingetragen;
                     HKVE-Zähler erhalten dabei automatisch den Wert 0,00 (jährlicher Reset).

Beispiele:
    # Jahresanfang + Jahresende (Standardfall)
    python immocloud_add_readings.py 1 2024-12-31,2025-12-31

    # Nur Jahresendwerte für alle Einheiten
    for i in 1 2 3 4 5 6 7 8; do python immocloud_add_readings.py $i 2025-12-31; done

    # Mieterwechsel April: Auszug 31.03, Einzug 30.04, Jahresende
    python immocloud_add_readings.py 3 2025-03-31,2025-04-30,2025-12-31

Voraussetzung:
    immocloud_create_meters.py muss bereits für die Nutzeinheit gelaufen sein
    und die Zähler-IDs in meters_state.json gespeichert haben.

Abhängigkeiten:
    pip install playwright
    playwright install chromium
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page

from immocloud_common import (
    BASE_URL, UNIT_MAP, DATE_COLUMNS, FIRST_DATE,
    column_to_immocloud_date, load_readings_for_unit,
    load_state, get_login_credentials, login, add_reading,
)


# ---------------------------------------------------------------------------
# _do_readings() – Kernlogik ohne Browser-Verwaltung
# ---------------------------------------------------------------------------

async def _do_readings(page: Page, unit_nr: str, date_columns: list) -> None:
    """Trägt Ablesewerte ein. Setzt einen offenen Browser und geladenen State voraus."""
    unit_info    = UNIT_MAP[unit_nr]
    state        = load_state()
    state_meters = state[unit_nr]["meters"]
    readings_data = load_readings_for_unit(unit_nr, date_columns)

    for sm in state_meters:
        geraet_nr = sm["geraet_nr"]
        typ       = sm["typ"]
        meter_id  = sm["meter_id"]
        csv_entry = readings_data.get(geraet_nr, {})

        print(f"\n  {sm['name']} ({geraet_nr})")
        for col in date_columns:
            immocloud_date = column_to_immocloud_date(col)

            if col == FIRST_DATE and typ == "HKVE":
                value: Optional[float] = 0.0
            else:
                raw_values = csv_entry.get("values", {})
                value = raw_values.get(col)
                if value is None:
                    print(f"    {col}: kein Wert in CSV – übersprungen.")
                    continue

            await add_reading(page, meter_id, immocloud_date, value)

    print(f"\n✓ Ablesungen für Einheit {unit_nr} ({unit_info['name']}) eingetragen.")


# ---------------------------------------------------------------------------
# run() – wird von immocloud_session.py aufgerufen (Browser bereits offen)
# ---------------------------------------------------------------------------

async def run(page: Page, unit_nr: str, date_columns: list, dry_run: bool = False) -> None:
    """Trägt Ablesungen ein. Setzt einen offenen Browser voraus."""
    unit_info = UNIT_MAP[unit_nr]

    state = load_state()
    if unit_nr not in state or not state[unit_nr].get("meters"):
        raise RuntimeError(
            f"Keine Zähler für Einheit {unit_nr} in meters_state.json.\n"
            f"Bitte zuerst create_meters für Einheit {unit_nr} ausführen."
        )

    readings_data = load_readings_for_unit(unit_nr, date_columns)

    print(f"\nAblesungen Einheit {unit_nr} → {unit_info['name']}:")
    for sm in state[unit_nr]["meters"]:
        geraet_nr = sm["geraet_nr"]
        typ       = sm["typ"]
        csv_entry = readings_data.get(geraet_nr, {})
        for col in date_columns:
            immocloud_date = column_to_immocloud_date(col)
            if col == FIRST_DATE and typ == "HKVE":
                val_str = "0,00  [HKVE Reset]"
            else:
                v = csv_entry.get("values", {}).get(col)
                val_str = f"{v:.2f}" if v is not None else "(kein Wert)"
            print(f"  {sm['name']:15s} {col} → {immocloud_date} = {val_str}")

    if dry_run:
        print("[DRY-RUN] Fertig.")
        return

    await _do_readings(page, unit_nr, date_columns)


# ---------------------------------------------------------------------------
# Standalone-Hauptprogramm
# ---------------------------------------------------------------------------

async def main(unit_nr: str, date_columns: list, dry_run: bool) -> None:
    if unit_nr not in UNIT_MAP:
        print(f"Fehler: Nutzeinheit '{unit_nr}' unbekannt. Gültig: {list(UNIT_MAP.keys())}")
        sys.exit(1)

    invalid = [d for d in date_columns if d not in DATE_COLUMNS]
    if invalid:
        print(f"Fehler: Unbekannte Datumsspalten: {invalid}")
        print(f"  Gültige Spalten: {DATE_COLUMNS}")
        sys.exit(1)

    unit_info = UNIT_MAP[unit_nr]
    print("=== immocloud Ablesewerte eintragen ===")
    print(f"Nutzeinheit: {unit_nr} → {unit_info['name']}")
    print(f"Spalten:     {', '.join(date_columns)}")
    print(f"             → immocloud-Daten: {', '.join(column_to_immocloud_date(d) for d in date_columns)}")
    if dry_run:
        print("*** DRY-RUN MODUS – keine Änderungen in immocloud ***\n")

    state = load_state()
    if unit_nr not in state or not state[unit_nr].get("meters"):
        print(
            f"Fehler: Keine Zähler für Einheit {unit_nr} in meters_state.json gefunden.\n"
            f"  Bitte zuerst immocloud_create_meters.py {unit_nr} ausführen."
        )
        sys.exit(1)

    # Vorschau
    readings_data = load_readings_for_unit(unit_nr, date_columns)
    print(f"\nAblesungen (aus CSV):")
    for sm in state[unit_nr]["meters"]:
        geraet_nr = sm["geraet_nr"]
        typ       = sm["typ"]
        csv_entry = readings_data.get(geraet_nr, {})
        print(f"\n  {sm['name']} ({geraet_nr}) → meter_id={sm['meter_id']}")
        for col in date_columns:
            immocloud_date = column_to_immocloud_date(col)
            if col == FIRST_DATE and typ == "HKVE":
                print(f"    {col} → {immocloud_date} = 0,00  [HKVE Reset]")
            else:
                v = csv_entry.get("values", {}).get(col)
                if v is None:
                    print(f"    {col} → {immocloud_date} = (kein Wert in CSV, übersprungen)")
                else:
                    print(f"    {col} → {immocloud_date} = {v:.2f}")

    if dry_run:
        print("\n[DRY-RUN] Fertig.")
        return

    email, password = get_login_credentials()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context()
        page    = await context.new_page()

        try:
            await login(page, email, password)
            await _do_readings(page, unit_nr, date_columns)
        except Exception as e:
            screenshot = Path(__file__).parent / "fehler_screenshot.png"
            await page.screenshot(path=str(screenshot))
            print(f"\n✗ Fehler: {e}")
            print(f"  Screenshot: {screenshot}")
            raise
        finally:
            input("\nEnter drücken zum Schließen des Browsers...")
            await browser.close()


if __name__ == "__main__":
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run    = "--dry-run" in sys.argv

    if len(positional) < 2:
        print("Verwendung: python immocloud_add_readings.py <nutzeinheit> <datumsspalten> [--dry-run]")
        print("  <datumsspalten>  Kommagetrennt, z.B.: 2024-12-31,2025-12-31")
        print(f"  Nutzeinheiten:   {list(UNIT_MAP.keys())}")
        print(f"  Gültige Spalten: {DATE_COLUMNS}")
        sys.exit(1)

    unit_nr      = positional[0]
    date_columns = [d.strip() for d in positional[1].split(",") if d.strip()]

    asyncio.run(main(unit_nr, date_columns, dry_run))
