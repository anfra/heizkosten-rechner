"""
immocloud_session.py – Mehrere Aktionen in EINEM Browser-Fenster ausführen.

Verwendung:
    python immocloud_sync/immocloud_session.py <job-datei.yaml> --csv <pfad/zur/csv>

Job-Datei (YAML):
    - action: create_meters
      unit: "1"

    - action: add_readings
      unit: "1"
      dates: "2024-12-31,2025-12-31"

Aktionen:
    create_meters  – Zähler anlegen (wie immocloud_create_meters.py)
    add_readings   – Ablesewerte eintragen (wie immocloud_add_readings.py)

Optionen:
    --csv      Pfad zur Ablesewerte-CSV (Pflicht)
    --state    Pfad zur State-Datei (Standard: meters_state.json)
    --dry-run  Keine Klicks, nur Vorschau

Tipps:
    python immocloud_sync/immocloud_session.py sync_jobs/full_import.yaml --csv export/Ablesewerte.csv
"""

import argparse
import asyncio
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Fehler: PyYAML nicht installiert. Bitte ausführen:")
    print("  pip install pyyaml")
    sys.exit(1)

from playwright.async_api import async_playwright

from immocloud_common import (
    UNIT_MAP, DATE_COLUMNS, login, get_login_credentials,
)
import immocloud_create_meters as create_mod
import immocloud_add_readings as readings_mod


# ---------------------------------------------------------------------------
# Job-Validierung
# ---------------------------------------------------------------------------

def validate_jobs(jobs: list) -> list:
    """Validiert die Job-Liste und gibt sie bereinigt zurück."""
    valid   = []
    errors  = []

    for i, job in enumerate(jobs):
        action = job.get("action", "").strip()
        unit   = str(job.get("unit", "")).strip()

        if action not in ("create_meters", "add_readings"):
            errors.append(f"  Job {i+1}: Unbekannte Aktion '{action}'. Gültig: create_meters, add_readings")
            continue

        if unit not in UNIT_MAP:
            errors.append(f"  Job {i+1}: Nutzeinheit '{unit}' unbekannt. Gültig: {list(UNIT_MAP.keys())}")
            continue

        if action == "add_readings":
            dates_raw = str(job.get("dates", "")).strip()
            if not dates_raw:
                errors.append(f"  Job {i+1}: 'dates' fehlt für add_readings Einheit {unit}")
                continue
            date_columns = [d.strip() for d in dates_raw.split(",") if d.strip()]
            invalid = [d for d in date_columns if d not in DATE_COLUMNS]
            if invalid:
                errors.append(
                    f"  Job {i+1}: Unbekannte Datumsspalten: {invalid}\n"
                    f"    Gültige Spalten: {DATE_COLUMNS}"
                )
                continue
            valid.append({"action": action, "unit": unit, "dates": date_columns})
        else:
            valid.append({"action": action, "unit": unit})

    if errors:
        print("Fehler in der Job-Datei:")
        for e in errors:
            print(e)
        sys.exit(1)

    return valid


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

async def main(job_file: Path, csv_file: Path, state_file: Path, dry_run: bool) -> None:
    if not job_file.exists():
        print(f"Fehler: Job-Datei nicht gefunden: {job_file}")
        sys.exit(1)

    if not csv_file.exists():
        print(f"Fehler: CSV-Datei nicht gefunden: {csv_file}")
        sys.exit(1)

    with open(job_file, encoding="utf-8") as f:
        raw_jobs = yaml.safe_load(f)

    if not isinstance(raw_jobs, list) or not raw_jobs:
        print("Fehler: Job-Datei muss eine nicht-leere YAML-Liste sein.")
        sys.exit(1)

    jobs = validate_jobs(raw_jobs)

    print("=== immocloud Session ===")
    print(f"Job-Datei: {job_file}")    print(f"CSV:       {csv_file}")
    print(f"State:     {state_file}")    print(f"Jobs ({len(jobs)}):")
    for j in jobs:
        if j["action"] == "add_readings":
            print(f"  {j['action']:15s}  Einheit {j['unit']}  Spalten: {','.join(j['dates'])}")
        else:
            print(f"  {j['action']:15s}  Einheit {j['unit']}")

    if dry_run:
        print("\n*** DRY-RUN – keine Änderungen ***\n")

    email, password = get_login_credentials()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context()
        page    = await context.new_page()

        try:
            await login(page, email, password)

            for i, job in enumerate(jobs):
                print(f"\n{'─'*50}")
                print(f"Job {i+1}/{len(jobs)}: {job['action']} Einheit {job['unit']}")
                print(f"{'─'*50}")

                if job["action"] == "create_meters":
                    await create_mod.run(page, job["unit"], csv_file, state_file, dry_run)

                elif job["action"] == "add_readings":
                    await readings_mod.run(page, job["unit"], job["dates"], csv_file, state_file, dry_run)

            print(f"\n{'='*50}")
            print(f"✓ Session abgeschlossen. {len(jobs)} Jobs ausgeführt.")

        except Exception as e:
            screenshot = Path(__file__).parent.parent / "fehler_screenshot.png"
            await page.screenshot(path=str(screenshot))
            print(f"\n✗ Fehler bei Job: {e}")
            print(f"  Screenshot: {screenshot}")
            raise
        finally:
            input("\nEnter drücken zum Schließen des Browsers...")
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mehrere immocloud-Aktionen in einem Browser-Fenster ausführen."
    )
    parser.add_argument("jobs",    type=Path, help="YAML Job-Datei")
    parser.add_argument("--csv",   required=True, type=Path,
                        help="Pfad zur Ablesewerte-CSV")
    parser.add_argument("--state", default="meters_state.json", type=Path,
                        help="Pfad zur State-Datei (Standard: meters_state.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Keine Änderungen, nur Vorschau")
    args = parser.parse_args()

    asyncio.run(main(args.jobs, args.csv, args.state, args.dry_run))
