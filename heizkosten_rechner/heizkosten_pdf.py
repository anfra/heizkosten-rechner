#!/usr/bin/env python3
"""
heizkosten_pdf.py — Heizkostenabrechnung als PDF je Mieter generieren.

Liest heizkosten_ergebnis.yaml + CSV-Ablesewerte und erstellt je Mieter ein
versandfertiges 3-seitiges PDF nach HeizkostenV § 6 Abs. 4.

Verwendung:
    python heizkosten_pdf.py [--ergebnis output/heizkosten_ergebnis.yaml] [--csv exports/Ablesewerte.csv] [--config output/heizkosten_config.yaml] [--output-dir output/]

Abhängigkeiten:
    pip install reportlab pyyaml
"""

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Importiere gemeinsame Logik aus heizkosten_calc
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from heizkosten_calc import (  # noqa: E402
    HKVE_TYPEN,
    WWZ_TYPEN,
    CsvData,
    load_config,
    resolve_end_col,
    resolve_start_col,
)

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

ABSENDER = {
    "name":    "Anton Frank",
    "strasse": "Loschwitzer Str. 17",
    "plz_ort": "01309 Dresden",
}

RAUM_LANG = {
    "BAD":  "Bad",
    "KÜ":   "Küche",
    "KI":   "Kinderzimmer",
    "WZ":   "Wohnzimmer",
    "SZ":   "Schlafzimmer",
    "DZ":   "Zimmer",
    "HZ":   "Heizraum",
    "FL":   "Flur",
    "WASC": "Waschküche",
    "HB":   "Hobbyraum",
    "EZ":   "Esszimmer",
    "AZ":   "Arbeitszimmer",
    "BÜ":   "Büro",
}

# A4 content width in points: 210mm − 25mm left − 20mm right
PAGE_W = A4[0] - 2.5 * cm - 2.0 * cm


# ---------------------------------------------------------------------------
# Zahlenformatierung (deutsches Format: Punkt = Tausender, Komma = Dezimal)
# ---------------------------------------------------------------------------

def _de(v: float, dec: int = 2) -> str:
    """1234.56 → '1.234,56'"""
    s = f"{abs(v):,.{dec}f}"
    int_part, dec_part = s.split(".")
    int_part = int_part.replace(",", ".")
    result = f"{int_part},{dec_part}"
    return f"-{result}" if v < -0.001 else result


def _eur(v: float) -> str:
    return _de(v, 2) + "\u00a0€"


def _mwh(v: float) -> str:
    return _de(v, 2) + "\u00a0MWh"


def _m3(v: float) -> str:
    return _de(v, 3) + "\u00a0m³"


def _pct(v: float) -> str:
    return _de(v, 2) + "\u00a0%"


def _dt(iso: str) -> str:
    """'2025-04-30' → '30.04.2025'"""
    if not iso:
        return "—"
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except ValueError:
        return iso


# ---------------------------------------------------------------------------
# Paragraph-Stile
# ---------------------------------------------------------------------------

def _styles() -> dict:
    def ps(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    grey_dark = colors.HexColor("#444444")
    grey_med  = colors.HexColor("#666666")

    return {
        "title":    ps("title",    fontName="Helvetica-Bold", fontSize=11, leading=14,
                        spaceBefore=4, spaceAfter=4),
        "h2":       ps("h2",       fontName="Helvetica-Bold", fontSize=9.5, leading=12,
                        spaceBefore=6, spaceAfter=2),
        "body":     ps("body",     fontName="Helvetica",      fontSize=9,   leading=12),
        "small":    ps("small",    fontName="Helvetica",      fontSize=8,   leading=10,
                        textColor=grey_dark),
        "sep":      ps("sep",      fontName="Helvetica",      fontSize=7,   leading=9,
                        textColor=colors.HexColor("#999999")),
        "addr":     ps("addr",     fontName="Helvetica",      fontSize=9,   leading=12),
        "label":    ps("label",    fontName="Helvetica",      fontSize=9,   leading=11),
        "label_b":  ps("label_b",  fontName="Helvetica-Bold", fontSize=9,   leading=11),
        "total":    ps("total",    fontName="Helvetica-Bold", fontSize=10,  leading=13),
        "r":        ps("r",        fontName="Helvetica",      fontSize=9,   leading=11,
                        alignment=TA_RIGHT),
        "r_b":      ps("r_b",      fontName="Helvetica-Bold", fontSize=9,   leading=11,
                        alignment=TA_RIGHT),
        "total_r":  ps("total_r",  fontName="Helvetica-Bold", fontSize=10,  leading=13,
                        alignment=TA_RIGHT),
        "tbl_hdr":  ps("tbl_hdr",  fontName="Helvetica-Bold", fontSize=8,   leading=10,
                        alignment=TA_CENTER),
        "tbl_hdr_r":ps("tbl_hdr_r",fontName="Helvetica-Bold", fontSize=8,   leading=10,
                        alignment=TA_RIGHT),
        "tbl":      ps("tbl",      fontName="Helvetica",      fontSize=8,   leading=10),
        "tbl_r":    ps("tbl_r",    fontName="Helvetica",      fontSize=8,   leading=10,
                        alignment=TA_RIGHT),
        "tbl_b":    ps("tbl_b",    fontName="Helvetica-Bold", fontSize=8,   leading=10),
        "tbl_br":   ps("tbl_br",   fontName="Helvetica-Bold", fontSize=8,   leading=10,
                        alignment=TA_RIGHT),
        "formula":  ps("formula",  fontName="Helvetica",      fontSize=7.5, leading=9,
                        textColor=grey_med),
    }


def _hr(width: float = PAGE_W, thickness: float = 0.5) -> HRFlowable:
    return HRFlowable(width=width, thickness=thickness, color=colors.black,
                      spaceAfter=3, spaceBefore=3)


# ---------------------------------------------------------------------------
# Ablesewerte je Gerät für eine Periode aus CSV extrahieren
# ---------------------------------------------------------------------------

def _device_rows(
    csv: CsvData,
    ne_nr: str,
    period_start: date,
    period_end: date,
) -> tuple[list, list]:
    """
    Gibt (hkve_rows, wwz_rows) zurück.
    Jede Row: dict mit raum, geraet_nr, typ, einbau, start_val, end_val, consumption
    """
    start_col = resolve_start_col(period_start)
    end_col   = resolve_end_col(period_end)

    hkve_rows: list = []
    wwz_rows:  list = []
    seen: set = set()

    for (u, g), meta in csv._meta.items():
        if u != ne_nr:
            continue
        if meta["ausbau"]:
            continue
        key = (u, g, meta["typ"])
        if key in seen:
            continue
        seen.add(key)

        if meta["typ"] not in (HKVE_TYPEN | WWZ_TYPEN):
            continue

        is_hkve = meta["typ"] in HKVE_TYPEN

        if is_hkve and start_col == "2024-12-31":
            start_val = 0.0
        else:
            start_val = csv.get(ne_nr, g, start_col) or 0.0

        end_val = (csv.get(ne_nr, g, end_col) or 0.0) if end_col else 0.0

        row = {
            "raum":        RAUM_LANG.get(meta["raum"], meta["raum"]),
            "geraet_nr":   g,
            "typ":         meta["typ"],
            "einbau":      _dt(meta["einbau"]) if meta["einbau"] else "—",
            "start_val":   start_val,
            "end_val":     end_val,
            "consumption": max(0.0, end_val - start_val),
        }
        if is_hkve:
            hkve_rows.append(row)
        else:
            wwz_rows.append(row)

    hkve_rows.sort(key=lambda r: r["raum"])
    wwz_rows.sort(key=lambda r: r["raum"])
    return hkve_rows, wwz_rows


# ---------------------------------------------------------------------------
# Seite 1 — Briefkopf + Ablesewerte
# ---------------------------------------------------------------------------

def _page1(
    st: dict,
    ne_nr: str,
    ne_entry: dict,
    period: dict,
    meta: dict,
    objekt_cfg: dict,
    hkve_rows: list,
    wwz_rows: list,
) -> list:
    els = []

    plz_ort = f"{objekt_cfg.get('plz', '')} {objekt_cfg.get('ort', '')}".strip()
    strasse = meta["adresse"]

    # ── Adressblock (links: Absender, rechts: Empfänger) ──────────────────────
    addr_data = [
        [
            Paragraph(f"<b>{ABSENDER['name']}</b>", st["addr"]),
            Paragraph(f"<b>{period['name']}</b>", st["addr"]),
        ],
        [
            Paragraph(ABSENDER["strasse"], st["addr"]),
            Paragraph(strasse, st["addr"]),
        ],
        [
            Paragraph(ABSENDER["plz_ort"], st["addr"]),
            Paragraph(plz_ort, st["addr"]),
        ],
    ]
    addr_tbl = Table(
        addr_data,
        colWidths=[PAGE_W * 0.48, PAGE_W * 0.52],
        hAlign="LEFT",
    )
    addr_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    els.append(addr_tbl)
    els.append(Spacer(1, 0.4 * cm))

    # ── Titel + Periode ────────────────────────────────────────────────────────
    els.append(_hr())
    els.append(Paragraph(
        f"Heizkostenabrechnung {meta['abrechnungsjahr']}  —  "
        f"{ne_entry['name']} (NE {ne_nr})",
        st["title"],
    ))
    von = _dt(period["periode_von"])
    bis = _dt(period["periode_bis"])
    els.append(Paragraph(
        f"Abrechnungszeitraum: <b>{von}</b> bis <b>{bis}</b>"
        f"  ({period['tage']} Tage)  |  Wohnfläche: {_de(ne_entry['flaeche_m2'])} m²",
        st["body"],
    ))
    els.append(_hr())
    els.append(Spacer(1, 0.3 * cm))

    # ── HKVE-Tabelle ──────────────────────────────────────────────────────────
    els.append(Paragraph(
        "Ablesewerte Raumwärme (Heizkostenverteiler HKVE)", st["h2"]
    ))
    els.append(Spacer(1, 1 * mm))

    col_w = [2.4 * cm, 4.2 * cm, 1.8 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 2.1 * cm]
    hdr = [
        Paragraph("Raum",           st["tbl_hdr"]),
        Paragraph("Geräte-Nr.",     st["tbl_hdr"]),
        Paragraph("Typ",            st["tbl_hdr"]),
        Paragraph("Einbau",         st["tbl_hdr"]),
        Paragraph("Stand Anfang",   st["tbl_hdr_r"]),
        Paragraph("Stand Ende",     st["tbl_hdr_r"]),
        Paragraph("Einheiten",      st["tbl_hdr_r"]),
    ]
    rows = [hdr]
    for r in hkve_rows:
        rows.append([
            Paragraph(r["raum"],                     st["tbl"]),
            Paragraph(r["geraet_nr"],                st["tbl"]),
            Paragraph(r["typ"],                      st["tbl"]),
            Paragraph(r["einbau"],                   st["tbl"]),
            Paragraph(_de(r["start_val"], 2),        st["tbl_r"]),
            Paragraph(_de(r["end_val"], 2),          st["tbl_r"]),
            Paragraph(_de(r["consumption"], 2),      st["tbl_br"]),
        ])
    total_hkve = sum(r["consumption"] for r in hkve_rows)
    rows.append([
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("Summe HKVE:", st["tbl_br"]),
        Paragraph(_de(total_hkve, 2), st["tbl_br"]),
    ])

    hkve_tbl = _make_reading_table(rows, col_w)
    els.append(hkve_tbl)
    if not hkve_rows:
        els.append(Paragraph("Keine HKVE-Daten für diesen Zeitraum.", st["small"]))
    els.append(Spacer(1, 0.4 * cm))

    # ── WWZ-Tabelle ───────────────────────────────────────────────────────────
    els.append(Paragraph(
        "Ablesewerte Warmwasser (Warmwasserzähler WWZ)", st["h2"]
    ))
    els.append(Spacer(1, 1 * mm))

    hdr_w = [
        Paragraph("Raum",               st["tbl_hdr"]),
        Paragraph("Geräte-Nr.",         st["tbl_hdr"]),
        Paragraph("Typ",                st["tbl_hdr"]),
        Paragraph("Einbau",             st["tbl_hdr"]),
        Paragraph("Stand Anfang (m³)",  st["tbl_hdr_r"]),
        Paragraph("Stand Ende (m³)",    st["tbl_hdr_r"]),
        Paragraph("Verbrauch (m³)",     st["tbl_hdr_r"]),
    ]
    rows_w = [hdr_w]
    for r in wwz_rows:
        rows_w.append([
            Paragraph(r["raum"],                     st["tbl"]),
            Paragraph(r["geraet_nr"],                st["tbl"]),
            Paragraph(r["typ"],                      st["tbl"]),
            Paragraph(r["einbau"],                   st["tbl"]),
            Paragraph(_de(r["start_val"], 3),        st["tbl_r"]),
            Paragraph(_de(r["end_val"], 3),          st["tbl_r"]),
            Paragraph(_de(r["consumption"], 3),      st["tbl_br"]),
        ])
    total_wwz = sum(r["consumption"] for r in wwz_rows)
    rows_w.append([
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("Summe WWZ:", st["tbl_br"]),
        Paragraph(_de(total_wwz, 3), st["tbl_br"]),
    ])

    wwz_tbl = _make_reading_table(rows_w, col_w)
    els.append(wwz_tbl)
    if not wwz_rows:
        els.append(Paragraph("Keine WWZ-Daten für diesen Zeitraum.", st["small"]))

    els.append(Spacer(1, 0.3 * cm))
    els.append(Paragraph(
        "* HKVE-Werte enthalten den gerätespezifischen Kd-Faktor (von Thermomess vorverarbeitet).",
        st["sep"],
    ))

    return els


def _make_reading_table(rows: list, col_w: list) -> Table:
    """Erstellt eine Ablesewerte-Tabelle mit einheitlichem Styling."""
    tbl = Table(rows, colWidths=col_w, hAlign="LEFT")
    n = len(rows)
    style = [
        ("BACKGROUND",   (0, 0), (-1, 0),    colors.HexColor("#e8e8e8")),
        ("LINEBELOW",    (0, 0), (-1, 0),    0.5, colors.black),
        ("LINEABOVE",    (0, n - 1), (-1, n - 1), 0.5, colors.black),
        ("LINEBELOW",    (0, n - 1), (-1, n - 1), 0.5, colors.black),
        ("VALIGN",       (0, 0), (-1, -1),   "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1),   3),
        ("RIGHTPADDING", (0, 0), (-1, -1),   3),
        ("TOPPADDING",   (0, 0), (-1, -1),   2),
        ("BOTTOMPADDING",(0, 0), (-1, -1),   2),
    ]
    for i in range(1, n - 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f6f6f6")))
    tbl.setStyle(TableStyle(style))
    return tbl


# ---------------------------------------------------------------------------
# Seite 2 — Gesamtkosten der Liegenschaft
# ---------------------------------------------------------------------------

def _page2(st: dict, meta: dict) -> list:
    els = []

    els.append(_hr())
    els.append(Paragraph(
        "Gesamtkosten der Liegenschaft im Abrechnungszeitraum", st["title"]
    ))
    els.append(Spacer(1, 0.2 * cm))

    col2 = [PAGE_W * 0.73, PAGE_W * 0.27]

    def row2(label: str, value: str, bold: bool = False, indent: int = 0) -> list:
        l_st = ParagraphStyle(
            f"l2_{id(label)}", parent=st["label_b" if bold else "label"],
            leftIndent=indent,
        )
        r_st = st["r_b"] if bold else st["r"]
        return [Paragraph(label, l_st), Paragraph(value, r_st)]

    def make_section_table(data: list, shade_last: bool = False) -> Table:
        t = Table(data, colWidths=col2, hAlign="LEFT")
        n = len(data)
        s = [
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        if shade_last:
            s += [
                ("BACKGROUND",  (0, n - 1), (-1, n - 1), colors.HexColor("#f0f0f0")),
                ("LINEABOVE",   (0, n - 1), (-1, n - 1), 0.5, colors.black),
                ("LINEBELOW",   (0, n - 1), (-1, n - 1), 0.5, colors.black),
            ]
        t.setStyle(TableStyle(s))
        return t

    # ── Energieträgerkosten ───────────────────────────────────────────────────
    els.append(Paragraph("Energieträgerkosten", st["h2"]))
    els.append(make_section_table([
        row2("Gas / Brennstoff (inkl. CO₂-Abgabe)", _eur(meta["heiz_gesamt_eur"])),
        row2("Summe Heizungskosten", _eur(meta["heiz_gesamt_eur"]), bold=True),
    ], shade_last=True))
    els.append(Spacer(1, 0.3 * cm))

    # ── WMZ-basierte Trennung ─────────────────────────────────────────────────
    els.append(Paragraph("Trennung Raumwärme / Wassererwärmung (WMZ, § 9)", st["h2"]))
    wmz_ges = meta["wmz_ww_mwh"] + meta["wmz_h_mwh"]
    els.append(make_section_table([
        row2(
            f"WMZ-WW: {_mwh(meta['wmz_ww_mwh'])} von gesamt {_mwh(wmz_ges)}",
            _pct(meta["ww_anteil_pct"]),
            indent=8,
        ),
        row2(
            f"Kostenanteil Wassererwärmung: "
            f"{_pct(meta['ww_anteil_pct'])} × {_eur(meta['heiz_gesamt_eur'])}",
            _eur(meta["ww_waerme_eur"]),
            indent=8,
        ),
        row2(
            f"Kostenanteil Raumwärme: "
            f"{_eur(meta['heiz_gesamt_eur'])} − {_eur(meta['ww_waerme_eur'])}",
            _eur(meta["h_netto_eur"]),
            bold=True,
            indent=8,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── CO₂-Abgabe ───────────────────────────────────────────────────────────
    els.append(Paragraph("CO₂-Kostenaufteilung (CO₂KostAufG)", st["h2"]))
    els.append(make_section_table([
        row2("CO₂-Abgabe gesamt", _eur(meta["co2_gesamt_eur"])),
        row2(
            f"Spez. CO₂-Ausstoß: {_de(meta['co2_spezifisch_kg_m2'])} kg/m²/Jahr"
            f" → Mieteranteil {meta['co2_mieter_pct']} %",
            _eur(meta["co2_mieter_total_eur"]),
            bold=True,
            indent=8,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── Verteilung Raumwärme ──────────────────────────────────────────────────
    els.append(Paragraph("Verteilung Raumwärme", st["h2"]))
    h_gp = int(round(meta["h_grund_total_eur"] / meta["h_netto_eur"] * 100))
    h_vp = 100 - h_gp
    els.append(make_section_table([
        row2(
            f"{h_gp} % Grundanteil: {_eur(meta['h_grund_total_eur'])}"
            f" ÷ {_de(meta['gesamtflaeche_m2'])} m² ÷ 365 Tage",
            f"{_de(meta['h_grund_rate_eur_m2_tag'], 6)} €/m²/Tag",
            indent=8,
        ),
        row2(
            f"{h_vp} % Verbrauch: {_eur(meta['h_verbr_total_eur'])}"
            f" ÷ {_de(meta['hkve_gesamt'], 1)} HKE",
            f"{_de(meta['h_verbr_rate_eur_hke'], 6)} €/HKE",
            indent=8,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── Verteilung Wassererwärmung ─────────────────────────────────────────────
    els.append(Paragraph("Verteilung Wassererwärmung", st["h2"]))
    ww_gp = int(round(meta["ww_grund_total_eur"] / meta["ww_waerme_eur"] * 100))
    ww_vp = 100 - ww_gp
    els.append(make_section_table([
        row2(
            f"{ww_gp} % Grundanteil: {_eur(meta['ww_grund_total_eur'])}"
            f" ÷ {_de(meta['gesamtflaeche_m2'])} m² ÷ 365 Tage",
            f"{_de(meta['ww_grund_rate_eur_m2_tag'], 6)} €/m²/Tag",
            indent=8,
        ),
        row2(
            f"{ww_vp} % Verbrauch: {_eur(meta['ww_verbr_total_eur'])}"
            f" ÷ {_de(meta['wwz_gesamt_m3'], 3)} m³",
            f"{_de(meta['ww_verbr_rate_eur_m3'], 6)} €/m³",
            indent=8,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── Umlagepreise (Übersicht) ───────────────────────────────────────────────
    els.append(Paragraph("Umlagepreise", st["h2"]))
    rate_data = [
        row2("Raumwärme — Grundanteil",
             f"{_de(meta['h_grund_rate_eur_m2_tag'], 6)} €/m²/Tag"),
        row2("Raumwärme — Verbrauch",
             f"{_de(meta['h_verbr_rate_eur_hke'], 6)} €/HKE"),
        row2("Wassererwärmung — Grundanteil",
             f"{_de(meta['ww_grund_rate_eur_m2_tag'], 6)} €/m²/Tag"),
        row2("Wassererwärmung — Verbrauch",
             f"{_de(meta['ww_verbr_rate_eur_m3'], 6)} €/m³"),
        row2("CO₂-Abgabe (Mieteranteil)",
             f"{_de(meta['co2_rate_eur_m2_tag'], 6)} €/m²/Tag"),
    ]
    rate_tbl = Table(rate_data, colWidths=col2, hAlign="LEFT")
    rate_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
        ("LINEABOVE",    (0, 0), (-1, 0),  0.5, colors.black),
        ("LINEBELOW",    (0, -1), (-1, -1), 0.5, colors.black),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
    ]))
    els.append(rate_tbl)

    return els


# ---------------------------------------------------------------------------
# Seite 3 — Mieteranteil (Kostenzuordnung)
# ---------------------------------------------------------------------------

def _page3(st: dict, ne_entry: dict, period: dict, meta: dict) -> list:
    els = []

    von = _dt(period["periode_von"])
    bis = _dt(period["periode_bis"])

    els.append(_hr())
    els.append(Paragraph(
        f"Ihre Kosten — Abrechnungszeitraum {von} bis {bis}",
        st["title"],
    ))
    els.append(Spacer(1, 0.2 * cm))

    col2 = [PAGE_W * 0.73, PAGE_W * 0.27]

    fl   = ne_entry["flaeche_m2"]
    tage = period["tage"]
    hkve = period["hkve_einheiten"]
    wwz  = period["wwz_m3"]

    def cost_row(label: str, formula: str, amount: str, bold: bool = False) -> list:
        l_st = ParagraphStyle(
            f"cr_{id(label)}", parent=st["label_b" if bold else "label"],
            leftIndent=0 if bold else 12,
        )
        combined = label
        if formula:
            combined = (
                f"{label}<br/>"
                f"<font size='7.5' color='#666666'>{formula}</font>"
            )
        r_st = st["r_b"] if bold else st["r"]
        return [Paragraph(combined, l_st), Paragraph(amount, r_st)]

    def section_table(data: list, bold_last: bool = True) -> Table:
        t = Table(data, colWidths=col2, hAlign="LEFT")
        n = len(data)
        s = [
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if bold_last:
            s += [
                ("LINEABOVE",  (0, n - 1), (-1, n - 1), 0.5, colors.black),
                ("LINEBELOW",  (0, n - 1), (-1, n - 1), 0.5, colors.black),
                ("BACKGROUND", (0, n - 1), (-1, n - 1), colors.HexColor("#f0f0f0")),
            ]
        t.setStyle(TableStyle(s))
        return t

    m = meta

    # ── Raumwärme ─────────────────────────────────────────────────────────────
    els.append(Paragraph("Raumwärme", st["h2"]))
    els.append(section_table([
        cost_row(
            "Grundanteil",
            f"{_de(m['h_grund_rate_eur_m2_tag'], 6)} €/m²/Tag"
            f" × {_de(fl)} m² × {tage} Tage",
            _eur(period["heizung_grundkosten_eur"]),
        ),
        cost_row(
            "Verbrauchsanteil",
            f"{_de(m['h_verbr_rate_eur_hke'], 6)} €/HKE × {_de(hkve)} HKE",
            _eur(period["heizung_verbrauchskosten_eur"]),
        ),
        cost_row(
            "Summe Raumwärme", "",
            _eur(period["heizung_gesamt_eur"]),
            bold=True,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── Wassererwärmung ───────────────────────────────────────────────────────
    els.append(Paragraph("Wassererwärmung", st["h2"]))
    els.append(section_table([
        cost_row(
            "Grundanteil",
            f"{_de(m['ww_grund_rate_eur_m2_tag'], 6)} €/m²/Tag"
            f" × {_de(fl)} m² × {tage} Tage",
            _eur(period["warmwasser_grundkosten_eur"]),
        ),
        cost_row(
            "Verbrauchsanteil",
            f"{_de(m['ww_verbr_rate_eur_m3'], 6)} €/m³ × {_de(wwz, 3)} m³",
            _eur(period["warmwasser_verbrauchskosten_eur"]),
        ),
        cost_row(
            "Summe Wassererwärmung", "",
            _eur(period["warmwasser_gesamt_eur"]),
            bold=True,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── CO₂-Abgabe ───────────────────────────────────────────────────────────
    els.append(Paragraph("CO₂-Abgabe (Mieteranteil)", st["h2"]))
    els.append(section_table([
        cost_row(
            "CO₂-Abgabe",
            f"{_de(m['co2_rate_eur_m2_tag'], 6)} €/m²/Tag"
            f" × {_de(fl)} m² × {tage} Tage"
            f"  ({m['co2_mieter_pct']} % Mieteranteil)",
            _eur(period["co2_mieter_eur"]),
        ),
    ], bold_last=False))
    els.append(Spacer(1, 0.4 * cm))

    # ── Gesamtkosten ──────────────────────────────────────────────────────────
    HRFlowable(width=PAGE_W, thickness=1.5, color=colors.black,
               spaceAfter=0, spaceBefore=0)
    els.append(_hr(thickness=1.0))

    total_tbl = Table(
        [[
            Paragraph("Ihre Gesamtkosten Heizung + Warmwasser + CO₂", st["total"]),
            Paragraph(_eur(period["summe_eur"]), st["total_r"]),
        ]],
        colWidths=col2,
        hAlign="LEFT",
    )
    total_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW",     (0, 0), (-1, -1), 1.0, colors.black),
    ]))
    els.append(total_tbl)
    els.append(Spacer(1, 0.5 * cm))

    # ── Hinweis ───────────────────────────────────────────────────────────────
    els.append(Paragraph(
        "Diese Abrechnung enthält ausschließlich die Kosten für Raumwärme und "
        "Warmwassererwärmung nach HeizkostenV §§ 6–9. Alle übrigen Betriebskosten "
        "(Kaltwasser, Gebäudeversicherung, Hausmeister, Müllentsorgung etc.) "
        "erhalten Sie gesondert über Ihre Nebenkostenabrechnung.",
        st["small"],
    ))

    return els


# ---------------------------------------------------------------------------
# PDF zusammenbauen
# ---------------------------------------------------------------------------

def build_pdf(
    output_path: Path,
    ne_nr: str,
    ne_entry: dict,
    period: dict,
    meta: dict,
    objekt_cfg: dict,
    hkve_rows: list,
    wwz_rows: list,
) -> None:
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.0 * cm,
    )
    st = _styles()

    story = []
    story += _page1(st, ne_nr, ne_entry, period, meta, objekt_cfg, hkve_rows, wwz_rows)
    story.append(PageBreak())
    story += _page2(st, meta)
    story.append(PageBreak())
    story += _page3(st, ne_entry, period, meta)

    doc.build(story)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    base = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Heizkostenabrechnung PDF je Mieter generieren.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiel:
  python heizkosten_pdf.py
  python heizkosten_pdf.py --ergebnis output/heizkosten_ergebnis.yaml --output-dir output/
""",
    )
    parser.add_argument(
        "--ergebnis", "-e",
        type=Path,
        default=None,
        help="Ergebnis-YAML (default: output/heizkosten_ergebnis.yaml neben diesem Skript)",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        help="Konfigurationsdatei (default: output/heizkosten_config.yaml neben diesem Skript)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Ablesewerte-CSV (überschreibt csv_datei aus config)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=None,
        help="Ausgabeverzeichnis für PDFs (default: output/ neben diesem Skript)",
    )
    args = parser.parse_args()

    ergebnis_path = args.ergebnis or (base / "output" / "heizkosten_ergebnis.yaml")
    config_path   = args.config   or (base / "output" / "heizkosten_config.yaml")
    output_dir    = args.output_dir or (base / "output")

    if not ergebnis_path.exists():
        parser.error(f"Ergebnis-YAML nicht gefunden: {ergebnis_path}")
    if not config_path.exists():
        parser.error(f"Konfigurationsdatei nicht gefunden: {config_path}")

    with open(ergebnis_path, encoding="utf-8") as f:
        ergebnis = yaml.safe_load(f)

    cfg        = load_config(config_path)
    objekt_cfg = cfg["objekt"]
    meta       = ergebnis["meta"]

    # CSV laden (für per-Gerät Ablesewerte auf Seite 1)
    if args.csv:
        csv_path = args.csv.resolve()
    else:
        csv_name = objekt_cfg.get("csv_datei")
        if not csv_name:
            parser.error(
                "--csv ist erforderlich, wenn kein csv_datei in der config gesetzt ist."
            )
        ergebnis_dir = ergebnis_path.resolve().parent
        candidates = [
            ergebnis_dir / "exports" / csv_name,
            ergebnis_dir.parent / "exports" / csv_name,
            ergebnis_dir.parent.parent / "exports" / csv_name,
            base.parent / "exports" / csv_name,
            base.parent / csv_name,
        ]
        csv_path = next((p for p in candidates if p.exists()), None)
        if csv_path is None:
            parser.error(
                f"CSV nicht gefunden (gesucht in: {candidates[0].parent}, "
                f"{candidates[1].parent})"
            )

    csv = CsvData(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for ne_nr, ne_entry in ergebnis["nutzeinheiten"].items():
        for period in ne_entry.get("mieter", []):
            start = date.fromisoformat(period["periode_von"])
            end   = date.fromisoformat(period["periode_bis"])

            hkve_rows, wwz_rows = _device_rows(csv, ne_nr, start, end)
            out_file = output_dir / period["pdf_datei"]

            build_pdf(
                out_file, ne_nr, ne_entry, period,
                meta, objekt_cfg, hkve_rows, wwz_rows,
            )
            print(f"  ✓  {out_file.name}")
            count += 1

    print(f"\n{count} PDF(s) erstellt in {output_dir}")


if __name__ == "__main__":
    main()
