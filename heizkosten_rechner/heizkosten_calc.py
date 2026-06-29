#!/usr/bin/env python3
"""
heizkosten_calc.py — Heizkostenberechnung nach HeizkostenV §§ 6–9a

Liest heizkosten_config.yaml + CSV-Ablesewerte und berechnet:
  - Heizkosten (HKVE-basiert) je NE/Mieter und Leerstandsperiode
  - Warmwasserkosten (WWZ-basiert) je NE/Mieter und Leerstandsperiode
  - CO₂-Mieteranteil (CO₂KostAufG) je NE/Mieter und Leerstandsperiode

Ausgabe: output/heizkosten_ergebnis.yaml

Verwendung:
    python heizkosten_calc.py [--config output/heizkosten_config.yaml] [--csv exports/Ablesewerte.csv] [--output output/heizkosten_ergebnis.yaml]
"""

import argparse
import calendar
import csv as csv_mod
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

ABRECHNUNGSJAHR = 2025
PERIODE_START   = date(ABRECHNUNGSJAHR, 1, 1)
PERIODE_END     = date(ABRECHNUNGSJAHR, 12, 31)
TAGE_GESAMT     = (PERIODE_END - PERIODE_START).days + 1  # 365

# CSV-Datumsspalten in Reihenfolge (prior-year stand + alle Monatsendstände 2025)
DATE_COLUMNS = [
    "2024-12-31",
    "2025-01-31", "2025-02-28", "2025-03-31",
    "2025-04-30", "2025-05-31", "2025-06-30", "2025-07-31",
    "2025-08-31", "2025-09-30", "2025-10-31", "2025-11-30", "2025-12-31",
]

# Typen der Messgeräte die wir je Nutzeinheit auslesen
HKVE_TYPEN = {"HKVE"}
WWZ_TYPEN  = {"WWZ", "FAM (WWZ)"}

# CO₂KostAufG Anlage: (obere_grenze, untere_grenze, mieteranteil)
CO2_STUFEN = [
    (float("inf"), 52.0, 0.00),
    (52.0,         42.0, 0.10),
    (42.0,         32.0, 0.20),
    (32.0,         22.0, 0.35),
    (22.0,         12.0, 0.55),
    (12.0,          0.0, 0.65),
]


# ---------------------------------------------------------------------------
# Hilfsfunktionen Datum
# ---------------------------------------------------------------------------

def col_to_date(col: str) -> date:
    return date.fromisoformat(col)


def prev_month_end_col(d: date) -> Optional[str]:
    """Gibt den CSV-Spaltennamen für den letzten Tag des Vormonats zurück."""
    first_of_month = d.replace(day=1)
    prev_end = first_of_month - timedelta(days=1)
    col = prev_end.isoformat()
    return col if col in DATE_COLUMNS else None


def month_end_col(d: date) -> Optional[str]:
    """Gibt den CSV-Spaltennamen für den letzten Tag des aktuellen Monats zurück."""
    last_day = calendar.monthrange(d.year, d.month)[1]
    col = date(d.year, d.month, last_day).isoformat()
    return col if col in DATE_COLUMNS else None


def resolve_start_col(d: date) -> str:
    """
    Bestimmt die CSV-Spalte für den Startwert einer Mieterperiode.

    - Einzug am 01.01. (Jahresanfang) → "2024-12-31" (für HKVE: implizit 0)
    - Einzug unterjährig (auch Monatserster) → Endstand des Vormonats
    """
    if d <= PERIODE_START:
        return "2024-12-31"
    col = prev_month_end_col(d)
    return col if col else "2024-12-31"


def resolve_end_col(d: date) -> Optional[str]:
    """
    Bestimmt die CSV-Spalte für den Endwert einer Mieterperiode.

    - Auszug am 31.12. (Jahresende) → "2025-12-31"
    - Auszug unterjährig (auch Monatsletzter) → Endstand des aktuellen Monats
    """
    if d >= PERIODE_END:
        return "2025-12-31"
    return month_end_col(d)


def period_days(start: date, end: date) -> int:
    """Inklusive Tagezahl."""
    return (end - start).days + 1


# ---------------------------------------------------------------------------
# CO₂-Mieteranteil
# ---------------------------------------------------------------------------

def co2_mieter_rate(spezifisch_kg_m2: float) -> float:
    """Gibt den Mieteranteil-Faktor für den spezifischen CO₂-Ausstoß zurück."""
    for upper, lower, rate in CO2_STUFEN:
        if lower <= spezifisch_kg_m2 <= upper:
            return rate
    return 0.65  # unterhalb der niedrigsten Stufe


# ---------------------------------------------------------------------------
# CSV-Datenhaltung
# ---------------------------------------------------------------------------

class CsvData:
    """
    Hält alle CSV-Rohdaten als Dictionary.
    Schlüssel: (unit_nr, geraet_nr) → { col → float | None }
    """

    def __init__(self, csv_file: Path):
        # (unit_nr, geraet_nr) → { col → float|None }
        self._values: dict[tuple, dict[str, Optional[float]]] = {}
        # (unit_nr, geraet_nr) → { typ, einbau, ausbau, raum }
        self._meta: dict[tuple, dict] = {}
        self._load(csv_file)

    def _load(self, csv_file: Path) -> None:
        with open(csv_file, encoding="utf-8") as f:
            reader = csv_mod.DictReader(f, delimiter=";")
            for row in reader:
                unit_nr   = (row.get("Nutzeinheit")   or "").strip()
                geraet_nr = (row.get("Geräte-Nr")    or "").strip()
                typ       = (row.get("Typ")           or "").strip()
                ausbau    = (row.get("Ausbau")        or "").strip()
                einbau    = (row.get("Einbau")        or "").strip()
                raum      = (row.get("Raum")          or "").strip()

                # Nicht-Datensatz-Zeilen überspringen (z.B. "* Funktstörung"-Anmerkungen)
                if not unit_nr.isdigit():
                    continue
                if not geraet_nr:
                    continue

                key = (unit_nr, geraet_nr)
                values: dict[str, Optional[float]] = {}
                for col in DATE_COLUMNS:
                    raw = row.get(col, "").strip()
                    if raw and raw not in ("[FS*]", ""):
                        try:
                            values[col] = float(raw)
                        except ValueError:
                            values[col] = None
                    else:
                        values[col] = None

                self._values[key] = values
                self._meta[key] = {
                    "typ":    typ,
                    "einbau": einbau,
                    "ausbau": ausbau,
                    "raum":   raum,
                }

    def get(self, unit_nr: str, geraet_nr: str, col: str) -> Optional[float]:
        return self._values.get((unit_nr, geraet_nr), {}).get(col)

    def meters_for_unit(self, unit_nr: str, typen: set) -> list[str]:
        """Gibt Geräte-Nummern für unit_nr und einen Satz von Typen zurück.
        Ausgebaute Geräte (Ausbau-Datum gesetzt) werden übersprungen."""
        result = []
        for (u, g), meta in self._meta.items():
            if u == unit_nr and meta["typ"] in typen and not meta["ausbau"]:
                result.append(g)
        return result


# ---------------------------------------------------------------------------
# Verbrauchsberechnung je Gerät und Periode
# ---------------------------------------------------------------------------

def device_consumption(
    csv: CsvData,
    unit_nr: str,
    geraet_nr: str,
    start_col: str,
    end_col: Optional[str],
    is_hkve: bool,
) -> float:
    """
    Berechnet den Verbrauch eines Zählers zwischen zwei CSV-Spalten.

    HKVE-Besonderheit:
      Das Gerät wird nach der Jahresablesung auf 0 zurückgesetzt.
      → Der 2024-12-31-Wert ist der Vorjahresstand VOR Reset; Startwert 2025 = 0.
      → Wenn start_col == "2024-12-31", wird der Startwert als 0 behandelt.

    WWZ/WMZ:
      Kumulativer Zähler. Neu eingebaute Geräte (2025-01-01) haben keinen
      2024-12-31-Wert → None → wird als 0 behandelt.
    """
    if end_col is None:
        return 0.0

    end_val = csv.get(unit_nr, geraet_nr, end_col)
    if end_val is None:
        return 0.0

    if is_hkve and start_col == "2024-12-31":
        # HKVE-Reset: Startwert 2025 = 0 (prior-year value is irrelevant)
        start_val = 0.0
    else:
        start_val = csv.get(unit_nr, geraet_nr, start_col) or 0.0

    return max(0.0, end_val - start_val)


def unit_hkve_consumption(csv: CsvData, unit_nr: str, start: date, end: date) -> float:
    """Summe HKVE-Verbrauch aller HKVE-Geräte einer NE für die gegebene Periode."""
    start_col = resolve_start_col(start)
    end_col   = resolve_end_col(end)
    total = 0.0
    for g in csv.meters_for_unit(unit_nr, HKVE_TYPEN):
        total += device_consumption(csv, unit_nr, g, start_col, end_col, is_hkve=True)
    return round(total, 2)


def unit_wwz_consumption(csv: CsvData, unit_nr: str, start: date, end: date) -> float:
    """Summe WWZ-Verbrauch aller WWZ-Geräte einer NE für die gegebene Periode."""
    start_col = resolve_start_col(start)
    end_col   = resolve_end_col(end)
    total = 0.0
    for g in csv.meters_for_unit(unit_nr, WWZ_TYPEN):
        total += device_consumption(csv, unit_nr, g, start_col, end_col, is_hkve=False)
    return round(total, 3)


def wmz_jahreswert(csv: CsvData, ne_nr: str, geraet_nr: str) -> float:
    """
    Jahreswert des WMZ (eingebaut 2025-01-01, kein 2024-12-31-Wert).
    → Einfacher Endstand 2025-12-31.
    """
    return csv.get(ne_nr, geraet_nr, "2025-12-31") or 0.0


# ---------------------------------------------------------------------------
# Periodenbildung (Mieter + Leerstand)
# ---------------------------------------------------------------------------

def build_periods(ne_nr: str, ne_cfg: dict) -> list[dict]:
    """
    Baut die Zeitperioden für eine Nutzeinheit auf:
      1. Mieterperioden aus der Konfiguration
      2. Leerstandsperioden (Lücken zwischen Mietern oder am Jahresanfang/-ende)

    Jede Periode ist ein dict mit:
      name (str), start (date), end (date), is_leerstand (bool)
    """
    parsed = []
    for m in ne_cfg.get("mieter", []):
        e = date.fromisoformat(m["einzug"])
        a = date.fromisoformat(m["auszug"]) if m.get("auszug") else PERIODE_END
        # Auf Abrechnungsjahr zuschneiden
        e = max(e, PERIODE_START)
        a = min(a, PERIODE_END)
        if e <= a:
            parsed.append({
                "name":         m["name"],
                "start":        e,
                "end":          a,
                "is_leerstand": False,
            })

    parsed.sort(key=lambda p: p["start"])

    periods: list[dict] = []
    cursor = PERIODE_START

    for p in parsed:
        if p["start"] > cursor:
            # Lücke → Leerstandsperiode
            periods.append({
                "name":         f"Leerstand NE {ne_nr}",
                "start":        cursor,
                "end":          p["start"] - timedelta(days=1),
                "is_leerstand": True,
            })
        periods.append(p)
        cursor = p["end"] + timedelta(days=1)

    # Leerstand am Jahresende
    if cursor <= PERIODE_END:
        periods.append({
            "name":         f"Leerstand NE {ne_nr}",
            "start":        cursor,
            "end":          PERIODE_END,
            "is_leerstand": True,
        })

    return periods


# ---------------------------------------------------------------------------
# Konfiguration laden
# ---------------------------------------------------------------------------

def load_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Hauptberechnung
# ---------------------------------------------------------------------------

def run(config_path: Path, csv_path: Path, output_path: Path) -> None:
    cfg = load_config(config_path)
    csv = CsvData(csv_path)

    objekt_cfg    = cfg["objekt"]
    kosten_cfg    = cfg["kosten"]
    aufteilung    = cfg["aufteilung"]
    wmz_cfg       = cfg["wmz_geraete"]
    gesamtflaeche = objekt_cfg["gesamtflaeche_m2"]

    # ── WMZ-basierte Aufteilung Heizung vs. Warmwasser ───────────────────────
    wmz_ww = wmz_jahreswert(csv, "10", wmz_cfg["warmwasser"])
    wmz_h  = wmz_jahreswert(csv, "11", wmz_cfg["heizung"])
    wmz_ges = wmz_ww + wmz_h

    if wmz_ges <= 0.0:
        print("FEHLER: WMZ-Jahreswerte sind 0 — keine WMZ-Daten verfügbar.", file=sys.stderr)
        sys.exit(1)

    ww_anteil = wmz_ww / wmz_ges

    # Gesamtkosten aus Config
    heiz_gesamt  = kosten_cfg["heizung_gesamt"]   # Brennstoff inkl. CO₂-Abgabe
    co2_gesamt   = kosten_cfg["co2_abgabe"]
    co2_spez     = kosten_cfg["co2_spezifisch_kg_m2"]

    # CO₂-Abgabe ist in heiz_gesamt enthalten und wird über den
    # WMZ-/HKVE-Schlüssel verteilt. Sie wird zusätzlich informatorisch
    # als "enthaltene Kosten" ausgewiesen (nicht separat aufgeschlagen).
    ww_waerme_eur = round(heiz_gesamt * ww_anteil, 2)
    h_netto_eur   = round(heiz_gesamt - ww_waerme_eur, 2)

    # Aufteilungsschlüssel (§ 6 / § 8)
    h_grund_pct  = aufteilung["heizung_grundkosten_pct"]    / 100.0
    ww_grund_pct = aufteilung["warmwasser_grundkosten_pct"] / 100.0
    h_verbr_pct  = 1.0 - h_grund_pct
    ww_verbr_pct = 1.0 - ww_grund_pct

    h_grund_total  = round(h_netto_eur   * h_grund_pct,  2)
    h_verbr_total  = round(h_netto_eur   * h_verbr_pct,  2)
    ww_grund_total = round(ww_waerme_eur * ww_grund_pct, 2)
    ww_verbr_total = round(ww_waerme_eur * ww_verbr_pct, 2)

    # CO₂-Mieteranteil (informatorisch) — aus Config-Override oder Stufentabelle
    if "co2_mieter_pct" in kosten_cfg:
        co2_rate_val = kosten_cfg["co2_mieter_pct"] / 100.0
    else:
        co2_rate_val = co2_mieter_rate(co2_spez)
    co2_mieter_total = round(co2_gesamt * co2_rate_val, 2)

    # ── Perioden aufbauen und Verbrauchswerte je Periode lesen ───────────────
    ne_perioden: dict[str, list[dict]] = {}
    for ne_nr, ne_cfg in cfg["nutzeinheiten"].items():
        periods = build_periods(ne_nr, ne_cfg)
        for p in periods:
            p["hkve"] = unit_hkve_consumption(csv, ne_nr, p["start"], p["end"])
            p["wwz"]  = unit_wwz_consumption(csv, ne_nr, p["start"], p["end"])
            p["tage"] = period_days(p["start"], p["end"])
        ne_perioden[ne_nr] = periods

    # ── Globale Verbrauchssummen (Nenner für Verbrauchskostensätze) ──────────
    hkve_gesamt = sum(
        p["hkve"] for periods in ne_perioden.values() for p in periods
    )
    wwz_gesamt = sum(
        p["wwz"]  for periods in ne_perioden.values() for p in periods
    )

    # ── Kostensätze ──────────────────────────────────────────────────────────
    # Grundkosten: pro m² und Tag  (= Grundkosten_total / (gesamtflaeche × 365))
    h_grund_rate  = h_grund_total  / (gesamtflaeche * TAGE_GESAMT)
    ww_grund_rate = ww_grund_total / (gesamtflaeche * TAGE_GESAMT)
    co2_rate      = co2_mieter_total / (gesamtflaeche * TAGE_GESAMT)

    # Verbrauchskosten: pro Einheit
    h_verbr_rate  = (h_verbr_total  / hkve_gesamt) if hkve_gesamt  > 0 else 0.0
    ww_verbr_rate = (ww_verbr_total / wwz_gesamt)  if wwz_gesamt   > 0 else 0.0

    # ── Kosten je Periode berechnen ──────────────────────────────────────────
    ergebnis: dict = {
        "meta": {
            "abrechnungsjahr":          objekt_cfg["abrechnungsjahr"],
            "adresse":                  objekt_cfg["adresse"],
            "gesamtflaeche_m2":         gesamtflaeche,
            "wmz_ww_mwh":               wmz_ww,
            "wmz_h_mwh":                wmz_h,
            "ww_anteil_pct":            round(ww_anteil * 100, 2),
            "heiz_gesamt_eur":          heiz_gesamt,
            "ww_waerme_eur":            ww_waerme_eur,
            "h_netto_eur":              h_netto_eur,
            "co2_gesamt_eur":           co2_gesamt,
            "co2_spezifisch_kg_m2":     co2_spez,
            "co2_mieter_pct":           int(round(co2_rate_val * 100)),
            "co2_mieter_total_eur":     co2_mieter_total,
            "h_grund_total_eur":        h_grund_total,
            "h_verbr_total_eur":        h_verbr_total,
            "ww_grund_total_eur":       ww_grund_total,
            "ww_verbr_total_eur":       ww_verbr_total,
            "hkve_gesamt":              round(hkve_gesamt, 2),
            "wwz_gesamt_m3":            round(wwz_gesamt, 3),
            "h_grund_rate_eur_m2_tag":  round(h_grund_rate,  8),
            "ww_grund_rate_eur_m2_tag": round(ww_grund_rate, 8),
            "co2_rate_eur_m2_tag":      round(co2_rate,      8),
            "h_verbr_rate_eur_hke":     round(h_verbr_rate,  6),
            "ww_verbr_rate_eur_m3":     round(ww_verbr_rate, 6),
        },
        "nutzeinheiten": {},
    }

    for ne_nr, ne_cfg in cfg["nutzeinheiten"].items():
        flaeche    = ne_cfg["flaeche_m2"]
        mieter_out: list[dict] = []
        leerstand_out: list[dict] = []

        for p in ne_perioden[ne_nr]:
            tage = p["tage"]
            hkve = p["hkve"]
            wwz  = p["wwz"]

            h_grund  = round(h_grund_rate  * flaeche * tage, 2)
            ww_grund = round(ww_grund_rate * flaeche * tage, 2)
            co2_ne   = round(co2_rate      * flaeche * tage, 2)

            h_verbr  = round(h_verbr_rate  * hkve, 2)
            ww_verbr = round(ww_verbr_rate * wwz,  2)

            h_gesamt  = round(h_grund  + h_verbr,  2)
            ww_gesamt = round(ww_grund + ww_verbr, 2)
            summe     = round(h_gesamt + ww_gesamt, 2)  # CO₂ enthalten in heiz_gesamt

            entry: dict = {
                "name":                           p["name"],
                "periode_von":                    p["start"].isoformat(),
                "periode_bis":                    p["end"].isoformat(),
                "tage":                           tage,
                "hkve_einheiten":                 hkve,
                "wwz_m3":                         wwz,
                "heizung_grundkosten_eur":        h_grund,
                "heizung_verbrauchskosten_eur":   h_verbr,
                "heizung_gesamt_eur":             h_gesamt,
                "warmwasser_grundkosten_eur":     ww_grund,
                "warmwasser_verbrauchskosten_eur": ww_verbr,
                "warmwasser_gesamt_eur":          ww_gesamt,
                "co2_enthaltene_eur":             co2_ne,   # informatorisch
                "summe_eur":                      summe,
                "anteil_gesamt_pct":              round(summe / heiz_gesamt * 100, 2),
            }

            if p["is_leerstand"]:
                entry["kosten_vermieter_eur"] = summe
                leerstand_out.append(entry)
            else:
                entry["pdf_datei"] = _pdf_filename(p["name"])
                mieter_out.append(entry)

        ne_entry: dict = {
            "name":       ne_cfg["name"],
            "flaeche_m2": flaeche,
        }
        if mieter_out:
            ne_entry["mieter"] = mieter_out
        if leerstand_out:
            ne_entry["leerstand"] = leerstand_out

        ergebnis["nutzeinheiten"][ne_nr] = ne_entry

    # ── Summenprüfung ────────────────────────────────────────────────────────
    _check_sums(ergebnis, h_grund_total, h_verbr_total,
                ww_grund_total, ww_verbr_total, co2_mieter_total)

    # ── Ergebnis schreiben ───────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(ergebnis, f, allow_unicode=True,
                  default_flow_style=False, sort_keys=False)
    print(f"\nErgebnis geschrieben: {output_path}")
    _print_summary(ergebnis)


# ---------------------------------------------------------------------------
# Hilfsfunktionen Ausgabe
# ---------------------------------------------------------------------------

def _pdf_filename(mieter_name: str) -> str:
    """Erstellt einen sicheren Dateinamen für die PDF-Abrechnung."""
    # Umlaute/Akzente normalisieren (NFD → ASCII)
    normalized = unicodedata.normalize("NFD", mieter_name)
    ascii_name = normalized.encode("ascii", "ignore").decode()
    # Nur alphanumerische Zeichen, Bindestriche und Leerzeichen behalten
    clean = re.sub(r"[^A-Za-z0-9\- ]", " ", ascii_name)
    # Mehrfache Leerzeichen bereinigen, Leerzeichen → Unterstrich
    clean = re.sub(r"\s+", "_", clean.strip())
    return f"Heizk_{ABRECHNUNGSJAHR}_{clean}.pdf"


def _check_sums(ergebnis: dict, h_grund_total: float, h_verbr_total: float,
                ww_grund_total: float, ww_verbr_total: float,
                co2_mieter_total: float) -> None:
    """Summenprüfung: Σ aller Perioden muss den Gesamtkosten entsprechen."""
    sums = {
        "h_grund":   0.0,
        "h_verbr":   0.0,
        "ww_grund":  0.0,
        "ww_verbr":  0.0,
    }
    for ne_entry in ergebnis["nutzeinheiten"].values():
        for p in ne_entry.get("mieter", []) + ne_entry.get("leerstand", []):
            sums["h_grund"]  += p["heizung_grundkosten_eur"]
            sums["h_verbr"]  += p["heizung_verbrauchskosten_eur"]
            sums["ww_grund"] += p["warmwasser_grundkosten_eur"]
            sums["ww_verbr"] += p["warmwasser_verbrauchskosten_eur"]

    tol = 0.10  # 10-Cent-Toleranz für Rundungsdifferenzen
    checks = [
        ("H-Grundkosten",   h_grund_total,  sums["h_grund"]),
        ("H-Verbrauch",     h_verbr_total,  sums["h_verbr"]),
        ("WW-Grundkosten",  ww_grund_total, sums["ww_grund"]),
        ("WW-Verbrauch",    ww_verbr_total, sums["ww_verbr"]),
    ]

    problems = []
    for label, soll, ist in checks:
        if abs(soll - ist) > tol:
            problems.append(f"  {label}: soll={soll:.2f} €, ist={ist:.2f} €, Δ={soll-ist:+.2f} €")

    if problems:
        print("\n⚠️  Summenprüfung FEHLGESCHLAGEN:")
        for line in problems:
            print(line)
    else:
        print("✓  Summenprüfung OK")


def _print_summary(ergebnis: dict) -> None:
    meta = ergebnis["meta"]
    sep = "─" * 72

    print(f"\n{sep}")
    print(f"Heizkostenabrechnung {meta['abrechnungsjahr']}  —  {meta['adresse']}")
    print(sep)
    print(f"  WMZ-WW : {meta['wmz_ww_mwh']:.2f} MWh")
    print(f"  WMZ-H  : {meta['wmz_h_mwh']:.2f} MWh")
    print(f"  WW-Anteil: {meta['ww_anteil_pct']:.2f} %")
    print(f"  Heizung netto      : {meta['h_netto_eur']:.2f} €"
          f"  (Grund {meta['h_grund_total_eur']:.2f} € + "
          f"Verbr {meta['h_verbr_total_eur']:.2f} €)")
    print(f"  Warmwasser Wärme   : {meta['ww_waerme_eur']:.2f} €"
          f"  (Grund {meta['ww_grund_total_eur']:.2f} € + "
          f"Verbr {meta['ww_verbr_total_eur']:.2f} €)")
    print(f"  CO₂ Mieteranteil   : {meta['co2_mieter_total_eur']:.2f} €"
          f"  ({meta['co2_mieter_pct']} %  bei {meta['co2_spezifisch_kg_m2']:.2f} kg/m²/Jahr)")
    print(f"  HKVE gesamt: {meta['hkve_gesamt']:.2f} HKE"
          f"  |  WWZ gesamt: {meta['wwz_gesamt_m3']:.3f} m³")
    print(f"  H-Verbrauchssatz : {meta['h_verbr_rate_eur_hke']:.4f} €/HKE"
          f"  |  WW-Verbrauchssatz : {meta['ww_verbr_rate_eur_m3']:.4f} €/m³")
    print(sep)
    print(f"  {'NE':<4} {'Lage':<24} {'Mieter / Leerstand':<36} {'Summe':>8}")
    print(sep)

    for ne_nr, ne_entry in ergebnis["nutzeinheiten"].items():
        lage = ne_entry["name"]
        all_periods = ne_entry.get("mieter", []) + ne_entry.get("leerstand", [])
        all_periods.sort(key=lambda p: p["periode_von"])
        for p in all_periods:
            tag = " [L]" if "kosten_vermieter_eur" in p else ""
            name_short = p["name"][:36]
            print(f"  {ne_nr:<4} {lage:<24} {name_short:<36} {p['summe_eur']:>8.2f} €{tag}")

    print(sep)

    # Gesamtsumme Mieter (exkl. Leerstand)
    summe_mieter = sum(
        p["summe_eur"]
        for ne in ergebnis["nutzeinheiten"].values()
        for p in ne.get("mieter", [])
    )
    summe_leerstand = sum(
        p["summe_eur"]
        for ne in ergebnis["nutzeinheiten"].values()
        for p in ne.get("leerstand", [])
    )
    summe_gesamt = round(summe_mieter + summe_leerstand, 2)
    print(f"  {'Summe Mieter':<64} {summe_mieter:>8.2f} €")
    print(f"  {'Leerstand (Vermieter)':<64} {summe_leerstand:>8.2f} €")
    print(f"  {'Gesamt (= Heizkosten + WW, CO₂ enthalten)':<64} {summe_gesamt:>8.2f} €")
    print(sep)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    base = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Heizkostenberechnung nach HeizkostenV §§ 6–9a",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiel:
  python heizkosten_calc.py
  python heizkosten_calc.py --csv ../exports/Ablesewerte_*.csv
  python heizkosten_calc.py --config output/heizkosten_config.yaml --output output/heizkosten_ergebnis.yaml
""",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=base / "output" / "heizkosten_config.yaml",
        help="Konfigurationsdatei (default: output/heizkosten_config.yaml neben diesem Skript)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Ablesewerte-CSV (überschreibt csv_datei aus config)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Ausgabedatei (default: heizkosten_ergebnis.yaml im selben Verzeichnis wie --config)",
    )
    args = parser.parse_args()

    if not args.config.exists():
        parser.error(f"Konfigurationsdatei nicht gefunden: {args.config}")

    # Output-Pfad: neben der Config-Datei, wenn nicht explizit angegeben
    config_dir = args.config.resolve().parent
    output_path = args.output if args.output else config_dir / "heizkosten_ergebnis.yaml"

    # Config laden um ggf. csv_datei zu lesen
    cfg_raw = load_config(args.config)

    if args.csv:
        csv_path = args.csv.resolve()
    else:
        csv_name = cfg_raw["objekt"].get("csv_datei")
        if not csv_name:
            parser.error("--csv ist erforderlich, wenn kein csv_datei in der config gesetzt ist.")
        # CSV suchen: exports/ relativ zum Config-Verzeichnis (1 oder 2 Ebenen hoch)
        # sowie relativ zum Skript-Verzeichnis als Fallback
        candidates = [
            config_dir / "exports" / csv_name,
            config_dir.parent / "exports" / csv_name,
            config_dir.parent.parent / "exports" / csv_name,
            base.parent / "exports" / csv_name,
            base.parent / csv_name,
        ]
        csv_path = next((p for p in candidates if p.exists()), None)
        if csv_path is None:
            parser.error(f"CSV-Datei nicht gefunden (gesucht in: {candidates[0].parent}, {candidates[1].parent})")

    run(args.config, csv_path, output_path)


if __name__ == "__main__":
    main()
