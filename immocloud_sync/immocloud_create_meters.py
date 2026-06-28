"""
Playwright-Skript: Zähler in immocloud anlegen.

Verwendung:
    python immocloud_sync/immocloud_create_meters.py <nutzeinheit> --csv <pfad/zur/csv>
    python immocloud_sync/immocloud_create_meters.py 1 --csv export/Ablesewerte.csv --dry-run

Die angelegten Zähler-IDs werden in der State-Datei gespeichert,
damit immocloud_add_readings.py darauf zugreifen kann.

Abhängigkeiten:
    pip install playwright
    playwright install chromium
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page

from immocloud_common import (
    BASE_URL, UNIT_MAP, METER_UNIT_MAP,
    VERSORGER, load_meters_for_unit,
    load_state, save_state, get_login_credentials, login,
)


# ---------------------------------------------------------------------------
# Zähler anlegen
# ---------------------------------------------------------------------------

async def select_via_keyboard(page: Page, option_text: str) -> None:
    """Öffnet das aktuell fokussierte PrimeVue Select via Space und wählt per Text."""
    await page.keyboard.press("Space")
    await page.wait_for_timeout(400)
    try:
        await page.wait_for_selector(".p-select-overlay, .p-listbox", timeout=3_000)
    except Exception:
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(400)
    option = page.locator(".p-select-option, .p-listbox-option").filter(has_text=option_text)
    if await option.count():
        await option.first.click(force=True)
    else:
        for _ in range(10):
            focused = await page.evaluate("() => document.activeElement?.textContent?.trim()")
            if focused == option_text:
                await page.keyboard.press("Enter")
                break
            await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(300)


async def create_meter(page: Page, meter: dict, dry_run: bool) -> Optional[str]:
    """
    Legt einen Zähler in immocloud an und gibt die neue Meter-ID zurück.
    Trägt keine Ablesewerte ein — das übernimmt immocloud_add_readings.py.
    """
    print(f"\n  Zähler: {meter['name']} | Nr: {meter['geraet_nr']} | Typ: {meter['meter_type']}")
    print(f"    Einheit: {meter['unit_name']} | Lage: {meter['location']}")

    if dry_run:
        print("    [DRY-RUN] Kein Klick.")
        return None

    # Zur Zähler-Übersicht und dann Neu-Formular
    await page.goto(f"{BASE_URL}/meters")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(500)
    await page.get_by_role("button", name="Neuen Zähler anlegen", exact=True).click()
    await page.wait_for_url(f"{BASE_URL}/meters/add", timeout=10_000)
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)

    # --- Objekt / Einheit: PrimeVue TreeSelect ---
    tree_select = page.locator(".meter-form-content [data-pc-name='treeselect']").first
    if not await tree_select.count():
        tree_select = page.locator(".meter-form-content .p-treeselect").first
    label_container = tree_select.locator(".p-treeselect-label-container")
    await label_container.wait_for(state="visible", timeout=5_000)
    await label_container.click(force=True)
    await page.wait_for_selector(".p-treeselect-overlay, .p-tree", timeout=5_000)
    await page.wait_for_timeout(600)

    # Objekt aufklappen → Einheiten sichtbar
    toggle = page.locator(".p-tree-node-toggle-button").first
    if await toggle.count():
        await toggle.click(force=True, timeout=2_000)
        await page.wait_for_timeout(400)

    # Einheit anklicken.
    # has_text ist Substring-Match: der Elternknoten (Gebäude) enthält alle Kinder-Texte
    # und würde als .first matchen → .last wählt den innersten (Blatt-)Knoten.
    unit_node = page.locator(".p-treeselect-overlay li").filter(has_text=meter["unit_name"])
    if not await unit_node.count():
        unit_node = page.locator(".p-tree li").filter(has_text=meter["unit_name"])
    if not await unit_node.count():
        available = await page.locator(".p-treeselect-overlay li").all_text_contents()
        raise RuntimeError(
            f"Einheit '{meter['unit_name']}' nicht im Tree-Panel gefunden. "
            f"Vorhandene Einträge: {available}"
        )
    await unit_node.last.click(force=True)
    await page.wait_for_timeout(500)
    try:
        await page.wait_for_selector(".p-treeselect-overlay", state="detached", timeout=3_000)
    except Exception:
        pass
    await page.wait_for_timeout(300)

    form = page.locator(".meter-form-content")

    # --- Zählernummer ---
    nr_input = form.locator("input#v-73")
    if not await nr_input.count():
        nr_input = form.get_by_label("Zählernummer")
    if not await nr_input.count():
        nr_input = form.locator("input[type='text']:not([role='combobox'])").first
    await nr_input.fill(meter["geraet_nr"])
    await nr_input.press("Tab")
    await page.wait_for_timeout(300)

    # --- Zählertyp ---
    await select_via_keyboard(page, meter["meter_type"])
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(300)

    # --- Maßeinheit ---
    unit_of_measure = METER_UNIT_MAP.get(meter["typ"], "")
    if unit_of_measure:
        await select_via_keyboard(page, unit_of_measure)
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(200)

    # --- Zählername ---
    name_field = form.locator("input#v-84")
    if not await name_field.count():
        name_field = form.get_by_label("Zählername")
    if await name_field.count():
        await name_field.fill(meter["name"])

    # --- Lage ---
    lage_field = form.locator("input#v-87")
    if not await lage_field.count():
        lage_field = form.get_by_label("Lage des Zählers im Gebäude")
    if await lage_field.count():
        await lage_field.fill(meter["location"])

    # --- Versorger ---
    versorger_field = form.locator("input#v-95")
    if not await versorger_field.count():
        versorger_field = form.get_by_label("Versorger")
    if await versorger_field.count():
        await versorger_field.fill(VERSORGER)

    # --- Speichern ---
    await page.get_by_role("button", name="Zähler anlegen", exact=True).click(force=True)
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # Meter-ID aus URL extrahieren: /meters/{id}
    current_url = page.url
    meter_id = current_url.rstrip("/").split("/")[-1]
    if meter_id == "add" or not meter_id:
        raise RuntimeError(f"Zähler-Anlage fehlgeschlagen, URL: {current_url}")

    print(f"    ✓ Zähler angelegt. ID: {meter_id}")
    return meter_id


# ---------------------------------------------------------------------------
# run() – wird von immocloud_session.py aufgerufen (Browser bereits offen)
# ---------------------------------------------------------------------------

async def run(page: Page, unit_nr: str, csv_file: Path, state_file: Path, dry_run: bool = False) -> None:
    """Legt alle Zähler einer Nutzeinheit an. Setzt einen offenen Browser voraus."""
    unit_info = UNIT_MAP[unit_nr]

    meters = load_meters_for_unit(unit_nr, csv_file)
    if not meters:
        print("Keine aktiven Zähler in der CSV gefunden.")
        return

    print(f"\nGefundene aktive Zähler ({len(meters)}):")
    for m in meters:
        print(f"  {m['name']:15s} | {m['geraet_nr']:25s} | {m['meter_type']}")

    if dry_run:
        print("\n[DRY-RUN] Fertig.")
        return

    state = load_state(state_file)
    if unit_nr not in state:
        state[unit_nr] = {"unit_name": unit_info["name"], "meters": []}

    for meter in meters:
        meter_id = await create_meter(page, meter, dry_run)
        if meter_id:
            existing = next(
                (e for e in state[unit_nr]["meters"] if e["geraet_nr"] == meter["geraet_nr"]),
                None
            )
            entry = {
                "geraet_nr": meter["geraet_nr"],
                "typ":       meter["typ"],
                "name":      meter["name"],
                "meter_id":  meter_id,
            }
            if existing:
                existing.update(entry)
            else:
                state[unit_nr]["meters"].append(entry)
            save_state(state, state_file)

    print(f"\n✓ Zähler für Einheit {unit_nr} ({unit_info['name']}) angelegt.")


# ---------------------------------------------------------------------------
# Standalone-Hauptprogramm
# ---------------------------------------------------------------------------

async def main(unit_nr: str, csv_file: Path, state_file: Path, dry_run: bool) -> None:
    if unit_nr not in UNIT_MAP:
        print(f"Fehler: Nutzeinheit '{unit_nr}' unbekannt. Gültig: {list(UNIT_MAP.keys())}")
        sys.exit(1)

    if not csv_file.exists():
        print(f"Fehler: CSV-Datei nicht gefunden: {csv_file}")
        sys.exit(1)

    unit_info = UNIT_MAP[unit_nr]
    print("=== immocloud Zähler anlegen ===")
    print(f"Nutzeinheit: {unit_nr} → {unit_info['name']}")
    print(f"CSV:         {csv_file}")
    print(f"State:       {state_file}")
    if dry_run:
        print("*** DRY-RUN MODUS – keine Änderungen in immocloud ***\n")

    meters = load_meters_for_unit(unit_nr, csv_file)
    if not meters:
        print("Keine aktiven Zähler in der CSV gefunden.")
        return

    print(f"\nGefundene aktive Zähler ({len(meters)}):")
    for m in meters:
        print(f"  {m['name']:15s} | {m['geraet_nr']:25s} | {m['meter_type']}")

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
            await run(page, unit_nr, csv_file, state_file, dry_run)
            print(f"\n  Nächster Schritt: python immocloud_sync/immocloud_add_readings.py {unit_nr} 2024-12-31,2025-12-31 --csv {csv_file}")
        except Exception as e:
            screenshot = Path(__file__).parent.parent / "fehler_screenshot.png"
            await page.screenshot(path=str(screenshot))
            print(f"\n✗ Fehler: {e}")
            print(f"  Screenshot: {screenshot}")
            raise
        finally:
            input("\nEnter drücken zum Schließen des Browsers...")
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Zähler in immocloud anlegen."
    )
    parser.add_argument("unit", help="Nutzeinheit (1–8)")
    parser.add_argument("--csv", required=True, type=Path,
                        help="Pfad zur Ablesewerte-CSV")
    parser.add_argument("--state", default="meters_state.json", type=Path,
                        help="Pfad zur State-Datei (Standard: meters_state.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Keine Änderungen, nur Vorschau")
    args = parser.parse_args()

    asyncio.run(main(args.unit, args.csv, args.state, args.dry_run))
