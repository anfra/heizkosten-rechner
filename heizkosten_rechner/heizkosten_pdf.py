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


def _hr(width="100%", thickness: float = 0.5) -> HRFlowable:
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

        kd  = meta.get("kd_faktor", 1.0)
        raw = max(0.0, end_val - start_val)
        row = {
            "raum":        RAUM_LANG.get(meta["raum"], meta["raum"]),
            "geraet_nr":   g,
            "typ":         meta["typ"],
            "einbau":      _dt(meta["einbau"]) if meta["einbau"] else "—",
            "start_val":   start_val,
            "end_val":     end_val,
            "kd_faktor":   kd,
            "consumption": raw * kd if is_hkve else raw,
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
    von = _dt(period["periode_von"])
    bis = _dt(period["periode_bis"])
    heute = date.today().strftime("%d.%m.%Y")

    # ── Briefkopf: links Absender + Empfänger, rechts Datum + Eckdaten ───────
    left = (
        f"<b>{period['name']}</b><br/>"
        f"{strasse}<br/>"
        f"{plz_ort}"
    )
    right = (
        f"Erstellt am:<br/>"
        f"{heute}<br/>"
        f"<br/>"
        f"Abrechnungszeitraum:<br/>"
        f"<b>{von}</b> bis <b>{bis}</b> ({period['tage']} Tage)<br/>"
        f"<br/>"
        f"Wohnfläche:<br/>"
        f"{_de(ne_entry['flaeche_m2'])} m²"
    )
    addr_tbl = Table(
        [[Paragraph(left, st["addr"]), Paragraph(right, ParagraphStyle("addr_r", parent=st["addr"], alignment=2))]],  # 2=RIGHT
        colWidths=[PAGE_W * 0.48, PAGE_W * 0.52],
        hAlign="LEFT",
    )
    addr_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    els.append(addr_tbl)
    els.append(Spacer(1, 0.4 * cm))

    # ── Titel ─────────────────────────────────────────────────────────────────
    els.append(_hr())
    els.append(Paragraph(
        f"Heizkostenabrechnung {meta['abrechnungsjahr']}  —  "
        f"{ne_entry['name']} (NE {ne_nr})",
        st["title"],
    ))
    els.append(_hr())
    els.append(Spacer(1, 0.3 * cm))

    # ── HKVE-Tabelle ──────────────────────────────────────────────────────────
    els.append(Paragraph(
        "Ablesewerte Raumwärme (Heizkostenverteiler HKVE)", st["h2"]
    ))
    els.append(Spacer(1, 1 * mm))

    # 8 columns: Raum | Geräte-Nr. | Typ | Ablesung Anfang | Ablesung Ende | Kd-Faktor | Verbrauch (HKE) | Einheit
    col_w = [2.2 * cm, 3.8 * cm, 1.4 * cm, 2.0 * cm, 2.0 * cm, 1.7 * cm, 2.1 * cm, 1.4 * cm]
    hdr = [
        Paragraph("Raum",              st["tbl_hdr"]),
        Paragraph("Geräte-Nr.",        st["tbl_hdr"]),
        Paragraph("Typ",               st["tbl_hdr"]),
        Paragraph("Ablesung<br/>Anfang", st["tbl_hdr_r"]),
        Paragraph("Ablesung<br/>Ende",  st["tbl_hdr_r"]),
        Paragraph("Kd-<br/>Faktor",    st["tbl_hdr_r"]),
        Paragraph("Verbrauch<br/>(HKE)", st["tbl_hdr_r"]),
        Paragraph("Einheit",           st["tbl_hdr"]),
    ]
    rows = [hdr]
    for r in hkve_rows:
        rows.append([
            Paragraph(r["raum"],                         st["tbl"]),
            Paragraph(r["geraet_nr"],                    st["tbl"]),
            Paragraph(r["typ"],                          st["tbl"]),
            Paragraph(_de(r["start_val"], 2),            st["tbl_r"]),
            Paragraph(_de(r["end_val"], 2),              st["tbl_r"]),
            Paragraph(_de(r["kd_faktor"], 3),            st["tbl_r"]),
            Paragraph(_de(r["consumption"], 2),          st["tbl_br"]),
            Paragraph("HKE",                             st["tbl"]),
        ])
    total_hkve = sum(r["consumption"] for r in hkve_rows)
    rows.append([
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("Summe:", st["tbl_br"]),
        Paragraph("", st["tbl"]),
        Paragraph(_de(total_hkve, 2), st["tbl_br"]),
        Paragraph("HKE", st["tbl_b"]),
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

    col_w_w = [2.2 * cm, 3.8 * cm, 1.4 * cm, 2.3 * cm, 2.3 * cm, 2.2 * cm, 1.4 * cm]
    hdr_w = [
        Paragraph("Raum",           st["tbl_hdr"]),
        Paragraph("Geräte-Nr.",     st["tbl_hdr"]),
        Paragraph("Typ",            st["tbl_hdr"]),
        Paragraph("Stand Anfang",   st["tbl_hdr_r"]),
        Paragraph("Stand Ende",     st["tbl_hdr_r"]),
        Paragraph("Verbrauch",      st["tbl_hdr_r"]),
        Paragraph("Einheit",        st["tbl_hdr"]),
    ]
    rows_w = [hdr_w]
    for r in wwz_rows:
        rows_w.append([
            Paragraph(r["raum"],                st["tbl"]),
            Paragraph(r["geraet_nr"],           st["tbl"]),
            Paragraph(r["typ"],                 st["tbl"]),
            Paragraph(_de(r["start_val"], 3),   st["tbl_r"]),
            Paragraph(_de(r["end_val"], 3),     st["tbl_r"]),
            Paragraph(_de(r["consumption"], 3), st["tbl_br"]),
            Paragraph("m³",                     st["tbl"]),
        ])
    total_wwz = sum(r["consumption"] for r in wwz_rows)
    rows_w.append([
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("", st["tbl"]),
        Paragraph("Summe:", st["tbl_br"]),
        Paragraph(_de(total_wwz, 3), st["tbl_br"]),
        Paragraph("m³", st["tbl_b"]),
    ])

    wwz_tbl = _make_reading_table(rows_w, col_w_w)
    els.append(wwz_tbl)
    if not wwz_rows:
        els.append(Paragraph("Keine WWZ-Daten für diesen Zeitraum.", st["small"]))

    els.append(Spacer(1, 0.3 * cm))
    els.append(Paragraph(
        "* Verbrauch (HKE) = Ablesung Ende × Kd-Faktor (gerätespezifische Gerätekonstante).",
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

    # 3 columns: Bezeichnung | Zahlenwert (rechtsbündig) | Einheit
    col3 = [PAGE_W * 0.65, PAGE_W * 0.20, PAGE_W * 0.15]

    def row3(label: str, number: str, unit: str,
             bold: bool = False, indent: int = 0) -> list:
        l_st = ParagraphStyle(
            f"l3_{id(label)}", parent=st["label_b" if bold else "label"],
            leftIndent=indent,
        )
        r_st = st["r_b"] if bold else st["r"]
        u_st = st["label_b"] if bold else st["label"]
        return [Paragraph(label, l_st), Paragraph(number, r_st), Paragraph(unit, u_st)]

    def make_section_table(data: list, shade_last: bool = False) -> Table:
        t = Table(data, colWidths=col3, hAlign="LEFT")
        n = len(data)
        s = [
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (2, 0), (2, -1),  4),
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
        row3("Gas / Brennstoff (inkl. CO2-Abgabe)",
             _de(meta["heiz_gesamt_eur"]), "€"),
        row3("davon CO2-Abgabe (in Heizkosten enthalten)",
             _de(meta["co2_gesamt_eur"]), "€"),
        row3("Verteilungsmasse Raumwärme + Wassererwärmung",
             _de(meta["heiz_gesamt_eur"]), "€", bold=True),
    ], shade_last=True))
    els.append(Spacer(1, 0.3 * cm))

    # ── WMZ-basierte Trennung ─────────────────────────────────────────────────
    els.append(Paragraph("Trennung Raumwärme / Wassererwärmung (WMZ, § 9)", st["h2"]))
    wmz_ges = meta["wmz_ww_mwh"] + meta["wmz_h_mwh"]
    els.append(make_section_table([
        row3(
            f"WMZ-WW: {_mwh(meta['wmz_ww_mwh'])} von gesamt {_mwh(wmz_ges)}",
            _de(meta["ww_anteil_pct"]), "%", indent=8,
        ),
        row3(
            f"Kostenanteil Wassererwärmung: "
            f"{_de(meta['ww_anteil_pct'])} % × {_de(meta['heiz_gesamt_eur'])} €",
            _de(meta["ww_waerme_eur"]), "€", indent=8,
        ),
        row3(
            f"Kostenanteil Raumwärme: "
            f"{_de(meta['heiz_gesamt_eur'])} € − {_de(meta['ww_waerme_eur'])} €",
            _de(meta["h_netto_eur"]), "€", indent=8,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── CO2-Abgabe (informatorisch) ───────────────────────────────────────────
    els.append(Paragraph("CO2-Abgabe (enthaltene Kosten, CO2KostAufG)", st["h2"]))
    els.append(make_section_table([
        row3("CO2-Abgabe gesamt (in Heizkosten enthalten)",
             _de(meta["co2_gesamt_eur"]), "€"),
        row3(
            f"Spez. CO2-Ausstoß: {_de(meta['co2_spezifisch_kg_m2'])} kg / m² * Jahr"
            f" → Mieteranteil {meta['co2_mieter_pct']} %",
            _de(meta["co2_mieter_total_eur"]), "€", indent=8,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── Verteilung Raumwärme ──────────────────────────────────────────────────
    els.append(Paragraph("Verteilung Raumwärme", st["h2"]))
    h_gp = int(round(meta["h_grund_total_eur"] / meta["h_netto_eur"] * 100))
    h_vp = 100 - h_gp
    els.append(make_section_table([
        row3(
            f"{h_gp} % Grundanteil: {_eur(meta['h_grund_total_eur'])}"
            f" ÷ {_de(meta['gesamtflaeche_m2'])} m² ÷ 365 Tage",
            _de(meta["h_grund_rate_eur_m2_tag"], 6), "€ / m² / Tag", indent=8,
        ),
        row3(
            f"{h_vp} % Verbrauch: {_eur(meta['h_verbr_total_eur'])}"
            f" ÷ {_de(meta['hkve_gesamt'], 1)} HKE",
            _de(meta["h_verbr_rate_eur_hke"], 6), "€ / HKE", indent=8,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── Verteilung Wassererwärmung ─────────────────────────────────────────────
    els.append(Paragraph("Verteilung Wassererwärmung", st["h2"]))
    ww_gp = int(round(meta["ww_grund_total_eur"] / meta["ww_waerme_eur"] * 100))
    ww_vp = 100 - ww_gp
    els.append(make_section_table([
        row3(
            f"{ww_gp} % Grundanteil: {_eur(meta['ww_grund_total_eur'])}"
            f" ÷ {_de(meta['gesamtflaeche_m2'])} m² ÷ 365 Tage",
            _de(meta["ww_grund_rate_eur_m2_tag"], 6), "€ / m² / Tag", indent=8,
        ),
        row3(
            f"{ww_vp} % Verbrauch: {_eur(meta['ww_verbr_total_eur'])}"
            f" ÷ {_de(meta['wwz_gesamt_m3'], 3)} m³",
            _de(meta["ww_verbr_rate_eur_m3"], 6), "€ / m³", indent=8,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── Umlagepreise (Übersicht) ───────────────────────────────────────────────
    els.append(Paragraph("Umlagepreise", st["h2"]))
    rate_data = [
        row3("Raumwärme — Grundanteil",
             _de(meta["h_grund_rate_eur_m2_tag"], 6), "€ / m² / Tag"),
        row3("Raumwärme — Verbrauch",
             _de(meta["h_verbr_rate_eur_hke"], 6), "€ / HKE"),
        row3("Wassererwärmung — Grundanteil",
             _de(meta["ww_grund_rate_eur_m2_tag"], 6), "€ / m² / Tag"),
        row3("Wassererwärmung — Verbrauch",
             _de(meta["ww_verbr_rate_eur_m3"], 6), "€ / m³"),
    ]
    rate_tbl = Table(rate_data, colWidths=col3, hAlign="LEFT")
    rate_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
        ("LINEABOVE",    (0, 0), (-1, 0),  0.5, colors.black),
        ("LINEBELOW",    (0, -1), (-1, -1), 0.5, colors.black),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (0, -1),  4),
        ("LEFTPADDING",  (1, 0), (1, -1),  0),
        ("LEFTPADDING",  (2, 0), (2, -1),  4),
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

    # 3 columns: Bezeichnung+Formel | Zahlenwert | Einheit
    col3 = [PAGE_W * 0.68, PAGE_W * 0.19, PAGE_W * 0.13]

    fl   = ne_entry["flaeche_m2"]
    tage = period["tage"]
    hkve = period["hkve_einheiten"]
    wwz  = period["wwz_m3"]

    def cost_row(label: str, formula: str, amount: float,
                 bold: bool = False, unit: str = "€") -> list:
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
        u_st = st["label_b"] if bold else st["label"]
        return [
            Paragraph(combined, l_st),
            Paragraph(_de(amount, 2), r_st),
            Paragraph(unit, u_st),
        ]

    def section_table(data: list, bold_last: bool = True) -> Table:
        t = Table(data, colWidths=col3, hAlign="LEFT")
        n = len(data)
        s = [
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (2, 0), (2, -1),  4),
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
            f"{_de(m['h_grund_rate_eur_m2_tag'], 6)} € / m² / Tag"
            f" × {_de(fl)} m² × {tage} Tage",
            period["heizung_grundkosten_eur"],
        ),
        cost_row(
            "Verbrauchsanteil",
            f"{_de(m['h_verbr_rate_eur_hke'], 6)} € / HKE × {_de(hkve)} HKE",
            period["heizung_verbrauchskosten_eur"],
        ),
        cost_row(
            "Summe Raumwärme", "",
            period["heizung_gesamt_eur"],
            bold=True,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── Wassererwärmung ───────────────────────────────────────────────────────
    els.append(Paragraph("Wassererwärmung", st["h2"]))
    els.append(section_table([
        cost_row(
            "Grundanteil",
            f"{_de(m['ww_grund_rate_eur_m2_tag'], 6)} € / m² / Tag"
            f" × {_de(fl)} m² × {tage} Tage",
            period["warmwasser_grundkosten_eur"],
        ),
        cost_row(
            "Verbrauchsanteil",
            f"{_de(m['ww_verbr_rate_eur_m3'], 6)} € / m³ × {_de(wwz, 3)} m³",
            period["warmwasser_verbrauchskosten_eur"],
        ),
        cost_row(
            "Summe Wassererwärmung", "",
            period["warmwasser_gesamt_eur"],
            bold=True,
        ),
    ]))
    els.append(Spacer(1, 0.3 * cm))

    # ── CO2-Abgabe (informatorisch) ─────────────────────────────────────────────
    co2_enthalten = period.get("co2_enthaltene_eur", 0.0)
    co2_info = (
        f"In Ihren Heizkosten ist eine CO2-Abgabe von "
        f"{_de(co2_enthalten, 2)} € enthalten "
        f"({m['co2_mieter_pct']} % Mieteranteil bei "
        f"{_de(m['co2_spezifisch_kg_m2'])} kg / m² * Jahr, CO2KostAufG)."
    )
    els.append(Paragraph(co2_info, st["small"]))
    els.append(Spacer(1, 0.4 * cm))

    # ── Gesamtkosten ──────────────────────────────────────────────────────────
    total_tbl = Table(
        [[
            Paragraph("Ihre Gesamtkosten Heizung + Warmwasser (inkl. CO2)", st["total"]),
            Paragraph(_de(period["summe_eur"], 2), st["total_r"]),
            Paragraph("€", st["total"]),
        ]],
        colWidths=col3,
        hAlign="LEFT",
    )
    total_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (2, 0), (2, -1),  4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE",     (0, 0), (-1, -1), 1.0, colors.black),
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
