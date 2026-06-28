"""
Unit-Tests für heizkosten_calc.py

Getestete Bereiche:
  - Datumshilfsfunktionen (resolve_start_col, resolve_end_col, period_days, …)
  - CO₂-Stufenermittlung (co2_mieter_rate)
  - CSV-Hilfsdatenstruktur (CsvData) mit In-Memory-CSV
  - Verbrauchsberechnung (device_consumption, unit_hkve/wwz_consumption)
  - Periodenbildung (build_periods) inkl. Leerstand und Mieterwechsel
  - PDF-Dateiname (_pdf_filename)
  - Summenprüfung der Gesamtberechnung (run) mit Minimal-CSV + Config
"""

import io
import sys
import textwrap
from datetime import date
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ─── Pfad zum Modul einhängen ────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heizkosten_rechner"))

import heizkosten_calc as calc  # noqa: E402  (nach sys.path-Manipulation)


# ═══════════════════════════════════════════════════════════════════════════════
# Hilfsfunktionen für Tests
# ═══════════════════════════════════════════════════════════════════════════════

def make_csv_data(rows: list[dict]) -> calc.CsvData:
    """
    Erstellt ein CsvData-Objekt aus einer Liste von Row-Dicts ohne echte CSV-Datei.
    Umgeht __init__ und befüllt _values/_meta direkt.
    """
    obj = object.__new__(calc.CsvData)
    obj._values = {}
    obj._meta = {}

    for row in rows:
        unit_nr   = row["unit_nr"]
        geraet_nr = row["geraet_nr"]
        typ       = row.get("typ", "HKVE")
        einbau    = row.get("einbau", "")
        ausbau    = row.get("ausbau", "")
        raum      = row.get("raum", "")
        key = (unit_nr, geraet_nr)
        obj._values[key] = {
            col: row.get(col) for col in calc.DATE_COLUMNS
        }
        obj._meta[key] = {
            "typ":    typ,
            "einbau": einbau,
            "ausbau": ausbau,
            "raum":   raum,
        }

    return obj


# ═══════════════════════════════════════════════════════════════════════════════
# Datumshilfsfunktionen
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveCols:

    def test_start_jahresanfang(self):
        """Einzug am 01.01. → Startspalte ist der Vorjahresendstand."""
        assert calc.resolve_start_col(date(2025, 1, 1)) == "2024-12-31"

    def test_start_vor_abrechnungsjahr(self):
        """Einzug vor 2025 → ebenfalls Vorjahresendstand."""
        assert calc.resolve_start_col(date(2024, 6, 1)) == "2024-12-31"

    def test_start_monatsanfang_april(self):
        """Einzug am 01.04. → Startspalte ist Endstand März."""
        assert calc.resolve_start_col(date(2025, 4, 1)) == "2025-03-31"

    def test_start_mitten_im_monat(self):
        """Einzug am 15.07. → Startspalte ist Endstand Juni (Vormonat)."""
        assert calc.resolve_start_col(date(2025, 7, 15)) == "2025-06-30"

    def test_start_dezember(self):
        """Einzug am 01.12. → Startspalte ist Endstand November."""
        assert calc.resolve_start_col(date(2025, 12, 1)) == "2025-11-30"

    def test_end_jahresende(self):
        """Auszug/Periode am 31.12. → Endspalte ist letzter Jahresendstand."""
        assert calc.resolve_end_col(date(2025, 12, 31)) == "2025-12-31"

    def test_end_nach_jahresende(self):
        """Perioden-Ende nach Abrechnungsjahr → auf 31.12. geclippt."""
        assert calc.resolve_end_col(date(2026, 3, 31)) == "2025-12-31"

    def test_end_monatsende_april(self):
        """Auszug am 30.04. → Endspalte ist April-Endstand."""
        assert calc.resolve_end_col(date(2025, 4, 30)) == "2025-04-30"

    def test_end_mitten_im_monat(self):
        """Auszug am 14.07. → Endspalte ist Juli-Endstand."""
        assert calc.resolve_end_col(date(2025, 7, 14)) == "2025-07-31"


class TestPeriodDays:

    def test_ein_tag(self):
        assert calc.period_days(date(2025, 6, 1), date(2025, 6, 1)) == 1

    def test_ganzes_jahr(self):
        assert calc.period_days(date(2025, 1, 1), date(2025, 12, 31)) == 365

    def test_januar(self):
        assert calc.period_days(date(2025, 1, 1), date(2025, 1, 31)) == 31

    def test_februar(self):
        assert calc.period_days(date(2025, 2, 1), date(2025, 2, 28)) == 28


# ═══════════════════════════════════════════════════════════════════════════════
# CO₂-Stufenermittlung
# ═══════════════════════════════════════════════════════════════════════════════

class TestCo2MieterRate:

    @pytest.mark.parametrize("kg_m2, expected", [
        (53.0,  0.00),   # > 52 → 0 %
        (52.0,  0.00),   # Grenze oben Stufe 2 → gehört noch zu 0 %
        (47.0,  0.10),   # 42–52 → 10 %
        (42.0,  0.10),   # Grenze 42 → 10 % (42 <= x <= 52)
        (37.0,  0.20),   # 32–42 → 20 %
        (26.78, 0.35),   # Realer Wert aus Projekt → 35 %
        (22.0,  0.35),   # Grenze 22 → 35 %
        (17.0,  0.55),   # 12–22 → 55 %
        (6.0,   0.65),   # < 12 → 65 %
        (0.0,   0.65),   # 0 kg → niedrigste Stufe
    ])
    def test_stufen(self, kg_m2, expected):
        assert calc.co2_mieter_rate(kg_m2) == pytest.approx(expected)


# ═══════════════════════════════════════════════════════════════════════════════
# CsvData-Klasse
# ═══════════════════════════════════════════════════════════════════════════════

class TestCsvData:

    def _make(self):
        return make_csv_data([
            {
                "unit_nr": "1", "geraet_nr": "HKVE-A", "typ": "HKVE",
                "2024-12-31": 100.0, "2025-06-30": 250.0, "2025-12-31": 400.0,
            },
            {
                "unit_nr": "1", "geraet_nr": "WWZ-A", "typ": "WWZ",
                "2024-12-31": 5.0, "2025-12-31": 15.0,
            },
            {
                "unit_nr": "1", "geraet_nr": "KWZ-A", "typ": "KWZ",
                "2024-12-31": 8.0, "2025-12-31": 20.0,
            },
            {
                "unit_nr": "2", "geraet_nr": "HKVE-B", "typ": "HKVE",
                "2024-12-31": 200.0, "2025-12-31": 500.0,
                "ausbau": "2025-06-30",  # ausgebautes Gerät
            },
        ])

    def test_get_existing(self):
        csv = self._make()
        assert csv.get("1", "HKVE-A", "2025-12-31") == pytest.approx(400.0)

    def test_get_missing_col(self):
        csv = self._make()
        assert csv.get("1", "HKVE-A", "2025-02-28") is None

    def test_get_unknown_unit(self):
        csv = self._make()
        assert csv.get("9", "HKVE-A", "2025-12-31") is None

    def test_meters_for_unit_hkve(self):
        csv = self._make()
        meters = csv.meters_for_unit("1", {"HKVE"})
        assert "HKVE-A" in meters
        assert "WWZ-A" not in meters

    def test_meters_for_unit_wwz(self):
        csv = self._make()
        meters = csv.meters_for_unit("1", {"WWZ", "FAM (WWZ)"})
        assert "WWZ-A" in meters
        assert "KWZ-A" not in meters

    def test_meters_for_unit_excludes_ausgebaut(self):
        """Ausgebaute Geräte dürfen nicht zurückgegeben werden."""
        csv = self._make()
        meters = csv.meters_for_unit("2", {"HKVE"})
        assert "HKVE-B" not in meters

    def test_meters_for_unit_empty(self):
        csv = self._make()
        assert csv.meters_for_unit("99", {"HKVE"}) == []


# ═══════════════════════════════════════════════════════════════════════════════
# Verbrauchsberechnung
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeviceConsumption:

    def test_hkve_jahreswert(self):
        """HKVE Startcol = 2024-12-31 → Startwert wird als 0 behandelt (Reset)."""
        csv = make_csv_data([{
            "unit_nr": "1", "geraet_nr": "HKV", "typ": "HKVE",
            "2024-12-31": 999.0,  # Vorjahreswert, ignoriert
            "2025-12-31": 71.0,
        }])
        result = calc.device_consumption(csv, "1", "HKV", "2024-12-31", "2025-12-31", is_hkve=True)
        assert result == pytest.approx(71.0)

    def test_hkve_halbjahr(self):
        """HKVE-Verbrauch von Jahresbeginn bis Ende Juni."""
        csv = make_csv_data([{
            "unit_nr": "1", "geraet_nr": "HKV", "typ": "HKVE",
            "2024-12-31": 50.0,
            "2025-06-30": 180.0,
            "2025-12-31": 400.0,
        }])
        result = calc.device_consumption(csv, "1", "HKV", "2024-12-31", "2025-06-30", is_hkve=True)
        assert result == pytest.approx(180.0)  # ab Reset (Startwert = 0)

    def test_wwz_kumulativ(self):
        """WWZ-Verbrauch: Differenz zweier kumulativer Stände."""
        csv = make_csv_data([{
            "unit_nr": "1", "geraet_nr": "WWZ", "typ": "WWZ",
            "2024-12-31": 5.0, "2025-12-31": 15.7,
        }])
        result = calc.device_consumption(csv, "1", "WWZ", "2024-12-31", "2025-12-31", is_hkve=False)
        assert result == pytest.approx(10.7)

    def test_wwz_neues_geraet_ohne_startwert(self):
        """WWZ eingebaut 2025-01-01 — kein 2024-12-31-Wert → Startwert = 0."""
        csv = make_csv_data([{
            "unit_nr": "1", "geraet_nr": "WWZ-NEU", "typ": "WWZ",
            "2024-12-31": None,
            "2025-12-31": 10.79,
        }])
        result = calc.device_consumption(csv, "1", "WWZ-NEU", "2024-12-31", "2025-12-31", is_hkve=False)
        assert result == pytest.approx(10.79)

    def test_no_end_value(self):
        """Kein Endstand → 0 zurückgeben."""
        csv = make_csv_data([{
            "unit_nr": "1", "geraet_nr": "HKV", "typ": "HKVE",
            "2024-12-31": 100.0, "2025-12-31": None,
        }])
        result = calc.device_consumption(csv, "1", "HKV", "2024-12-31", "2025-12-31", is_hkve=True)
        assert result == pytest.approx(0.0)

    def test_no_end_col(self):
        """end_col=None → 0 zurückgeben."""
        csv = make_csv_data([{"unit_nr": "1", "geraet_nr": "HKV", "typ": "HKVE"}])
        result = calc.device_consumption(csv, "1", "HKV", "2024-12-31", None, is_hkve=True)
        assert result == pytest.approx(0.0)

    def test_wert_nicht_negativ(self):
        """Negativer Differenzwert (Datenfehler) → 0 zurückgeben."""
        csv = make_csv_data([{
            "unit_nr": "1", "geraet_nr": "WWZ", "typ": "WWZ",
            "2024-12-31": 20.0, "2025-06-30": 10.0,  # defekte Daten
        }])
        result = calc.device_consumption(csv, "1", "WWZ", "2024-12-31", "2025-06-30", is_hkve=False)
        assert result == pytest.approx(0.0)


class TestUnitConsumption:

    def _csv_ne1(self):
        """NE 1 mit zwei HKVE-Geräten und einem WWZ."""
        return make_csv_data([
            {
                "unit_nr": "1", "geraet_nr": "H1", "typ": "HKVE",
                "2024-12-31": 0.0, "2025-12-31": 100.0,
            },
            {
                "unit_nr": "1", "geraet_nr": "H2", "typ": "HKVE",
                "2024-12-31": 0.0, "2025-12-31": 50.0,
            },
            {
                "unit_nr": "1", "geraet_nr": "W1", "typ": "WWZ",
                "2024-12-31": 0.0, "2025-12-31": 8.5,
            },
        ])

    def test_hkve_summe_ganzes_jahr(self):
        csv = self._csv_ne1()
        result = calc.unit_hkve_consumption(csv, "1", date(2025, 1, 1), date(2025, 12, 31))
        assert result == pytest.approx(150.0)

    def test_wwz_ganzes_jahr(self):
        csv = self._csv_ne1()
        result = calc.unit_wwz_consumption(csv, "1", date(2025, 1, 1), date(2025, 12, 31))
        assert result == pytest.approx(8.5)

    def test_hkve_halbjahrperiode_einzug(self):
        """
        Einzug 01.07.2025: Startspalte = 2025-06-30.
        Nur der Verbrauch ab Juli wird berechnet.
        """
        csv = make_csv_data([{
            "unit_nr": "1", "geraet_nr": "H1", "typ": "HKVE",
            "2025-06-30": 40.0, "2025-12-31": 100.0,
        }])
        result = calc.unit_hkve_consumption(csv, "1", date(2025, 7, 1), date(2025, 12, 31))
        assert result == pytest.approx(60.0)

    def test_wwz_unterjährig_auszug(self):
        """
        Auszug 14.07.2025: Endspalte = 2025-07-31.
        """
        csv = make_csv_data([{
            "unit_nr": "1", "geraet_nr": "W1", "typ": "WWZ",
            "2024-12-31": 2.0, "2025-07-31": 7.5, "2025-12-31": 12.0,
        }])
        result = calc.unit_wwz_consumption(csv, "1", date(2025, 1, 1), date(2025, 7, 14))
        assert result == pytest.approx(5.5)

    def test_keine_geraete(self):
        """NE ohne Geräte → Verbrauch = 0."""
        csv = make_csv_data([])
        assert calc.unit_hkve_consumption(csv, "99", date(2025, 1, 1), date(2025, 12, 31)) == 0.0
        assert calc.unit_wwz_consumption(csv, "99", date(2025, 1, 1), date(2025, 12, 31)) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Periodenbildung
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildPeriods:

    def test_ein_mieter_ganzes_jahr(self):
        ne_cfg = {"mieter": [{"name": "Max M.", "einzug": "2025-01-01", "auszug": None}]}
        periods = calc.build_periods("1", ne_cfg)
        assert len(periods) == 1
        p = periods[0]
        assert p["name"] == "Max M."
        assert p["start"] == date(2025, 1, 1)
        assert p["end"]   == date(2025, 12, 31)
        assert p["is_leerstand"] is False

    def test_leerstand_ganzes_jahr(self):
        ne_cfg = {"mieter": []}
        periods = calc.build_periods("3", ne_cfg)
        assert len(periods) == 1
        assert periods[0]["is_leerstand"] is True
        assert periods[0]["start"] == date(2025, 1, 1)
        assert periods[0]["end"]   == date(2025, 12, 31)

    def test_mieterwechsel_nahtlos(self):
        ne_cfg = {"mieter": [
            {"name": "Alt", "einzug": "2025-01-01", "auszug": "2025-03-31"},
            {"name": "Neu", "einzug": "2025-04-01", "auszug": None},
        ]}
        periods = calc.build_periods("2", ne_cfg)
        assert len(periods) == 2
        names = [p["name"] for p in periods]
        assert "Alt" in names
        assert "Neu" in names
        leerstand_count = sum(1 for p in periods if p["is_leerstand"])
        assert leerstand_count == 0

    def test_leerstand_zwischen_mietern(self):
        ne_cfg = {"mieter": [
            {"name": "A", "einzug": "2025-01-01", "auszug": "2025-04-30"},
            {"name": "B", "einzug": "2025-07-15", "auszug": None},
        ]}
        periods = calc.build_periods("1", ne_cfg)
        leerstand = [p for p in periods if p["is_leerstand"]]
        assert len(leerstand) == 1
        ls = leerstand[0]
        assert ls["start"] == date(2025, 5, 1)
        assert ls["end"]   == date(2025, 7, 14)

    def test_leerstand_am_jahresende(self):
        ne_cfg = {"mieter": [
            {"name": "A", "einzug": "2025-01-01", "auszug": "2025-06-30"},
        ]}
        periods = calc.build_periods("1", ne_cfg)
        leerstand = [p for p in periods if p["is_leerstand"]]
        assert len(leerstand) == 1
        ls = leerstand[0]
        assert ls["start"] == date(2025, 7, 1)
        assert ls["end"]   == date(2025, 12, 31)

    def test_leerstand_am_jahresanfang(self):
        ne_cfg = {"mieter": [
            {"name": "A", "einzug": "2025-07-01", "auszug": None},
        ]}
        periods = calc.build_periods("1", ne_cfg)
        leerstand = [p for p in periods if p["is_leerstand"]]
        assert len(leerstand) == 1
        ls = leerstand[0]
        assert ls["start"] == date(2025, 1, 1)
        assert ls["end"]   == date(2025, 6, 30)

    def test_einzug_vor_abrechnungsjahr(self):
        """Mieter eingezogen 2022, kein Auszug → komplettes Jahr 2025."""
        ne_cfg = {"mieter": [{"name": "Alt", "einzug": "2022-05-01", "auszug": None}]}
        periods = calc.build_periods("5", ne_cfg)
        assert len(periods) == 1
        assert periods[0]["start"] == date(2025, 1, 1)
        assert periods[0]["end"]   == date(2025, 12, 31)

    def test_tage_summe_gleich_365(self):
        """Summe aller Periodentagezahlen = 365."""
        ne_cfg = {"mieter": [
            {"name": "A", "einzug": "2025-01-01", "auszug": "2025-04-30"},
            {"name": "B", "einzug": "2025-07-15", "auszug": None},
        ]}
        periods = calc.build_periods("1", ne_cfg)
        total = sum(calc.period_days(p["start"], p["end"]) for p in periods)
        assert total == 365

    def test_mehrere_mieterwechsel_ne5(self):
        """NE 5 mit 3 Mietern und Lücke — wie in echten Daten."""
        ne_cfg = {"mieter": [
            {"name": "Christian Fürschke", "einzug": "2025-01-01", "auszug": "2025-05-31"},
            {"name": "Robert Sukanik",     "einzug": "2025-08-15", "auszug": "2025-10-31"},
            {"name": "Marek Ziga",         "einzug": "2025-11-01", "auszug": None},
        ]}
        periods = calc.build_periods("5", ne_cfg)
        total = sum(calc.period_days(p["start"], p["end"]) for p in periods)
        assert total == 365
        leerstand = [p for p in periods if p["is_leerstand"]]
        assert len(leerstand) == 1
        ls = leerstand[0]
        assert ls["start"] == date(2025, 6, 1)
        assert ls["end"]   == date(2025, 8, 14)


# ═══════════════════════════════════════════════════════════════════════════════
# PDF-Dateiname
# ═══════════════════════════════════════════════════════════════════════════════

class TestPdfFilename:

    def test_einfacher_name(self):
        assert calc._pdf_filename("Max Müller") == "Heizk_2025_Max_Muller.pdf"

    def test_name_mit_akzent(self):
        fn = calc._pdf_filename("Jennifer Rose Gombár")
        assert fn == "Heizk_2025_Jennifer_Rose_Gombar.pdf"

    def test_name_mit_mehreren_spaces(self):
        fn = calc._pdf_filename("Anna  Maria  Muster")
        assert fn == "Heizk_2025_Anna_Maria_Muster.pdf"

    def test_name_mit_komma(self):
        fn = calc._pdf_filename("Sukanik, Robert")
        assert fn == "Heizk_2025_Sukanik_Robert.pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# Integrationstest: run() mit Minimal-Konfiguration
# ═══════════════════════════════════════════════════════════════════════════════

MINIMAL_CONFIG = """\
objekt:
  adresse: "Teststraße 1"
  plz: "01234"
  ort: "Teststadt"
  abrechnungsjahr: 2025
  csv_datei: "test.csv"
  gesamtflaeche_m2: 100.0

nutzeinheiten:
  "1":
    name: "EG links"
    flaeche_m2: 50.0
    mieter:
      - name: "Mieter A"
        einzug: "2025-01-01"
        auszug: null
  "2":
    name: "EG rechts"
    flaeche_m2: 50.0
    mieter:
      - name: "Mieter B"
        einzug: "2025-01-01"
        auszug: null

kosten:
  heizung_gesamt: 1000.00
  co2_abgabe: 100.00
  co2_spezifisch_kg_m2: 26.78

wmz_geraete:
  warmwasser: "WMZ-WW"
  heizung:    "WMZ-H"

aufteilung:
  heizung_grundkosten_pct: 30
  warmwasser_grundkosten_pct: 30
"""

# Minimale CSV-Inhalte für den Integrationstest
MINIMAL_CSV = (
    "Nutzeinheit;Stockwerk;Lage;Raum;Geräte-Nr;Typ;Einbau;Ausbau;"
    "2024-12-31;2025-01-31;2025-02-28;2025-03-31;2025-04-30;2025-05-31;"
    "2025-06-30;2025-07-31;2025-08-31;2025-09-30;2025-10-31;2025-11-30;2025-12-31;\n"
    # NE 1: HKVE + WWZ
    "1;EG;L;WZ;HKVE-1;HKVE;;;0.0;10.0;20.0;30.0;40.0;50.0;60.0;70.0;80.0;90.0;100.0;110.0;200.0;\n"
    "1;EG;L;BAD;WWZ-1;WWZ;2025-01-01;;;1.0;2.0;3.0;4.0;5.0;6.0;7.0;8.0;9.0;10.0;11.0;12.0;\n"
    # NE 2: HKVE + WWZ
    "2;EG;R;WZ;HKVE-2;HKVE;;;0.0;10.0;20.0;30.0;40.0;50.0;60.0;70.0;80.0;90.0;100.0;110.0;200.0;\n"
    "2;EG;R;BAD;WWZ-2;WWZ;2025-01-01;;;1.0;2.0;3.0;4.0;5.0;6.0;7.0;8.0;9.0;10.0;11.0;12.0;\n"
    # WMZ (NE 10 + 11 analog)
    "10;1.UG;;Heizr;WMZ-WW;WMZ;2025-01-01;;;2.0;4.0;6.0;8.0;10.0;12.0;14.0;16.0;18.0;20.0;22.0;25.0;\n"
    "11;1.UG;;Heizr;WMZ-H;WMZ;2025-01-01;;;3.0;6.0;9.0;12.0;15.0;18.0;21.0;24.0;27.0;30.0;33.0;37.5;\n"
)


class TestIntegrationRun:
    """Integrationstest: run() mit tmp-Dateien, prüft Summen und Struktur."""

    @pytest.fixture
    def tmp_files(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        csv_path = tmp_path / "test.csv"
        out_path = tmp_path / "ergebnis.yaml"

        cfg_path.write_text(MINIMAL_CONFIG, encoding="utf-8")
        csv_path.write_text(MINIMAL_CSV, encoding="utf-8")

        return cfg_path, csv_path, out_path

    def test_run_erstellt_ergebnis(self, tmp_files):
        cfg_path, csv_path, out_path = tmp_files
        calc.run(cfg_path, csv_path, out_path)
        assert out_path.exists()

    def test_summen_pruefen(self, tmp_files):
        import yaml as _yaml
        cfg_path, csv_path, out_path = tmp_files
        calc.run(cfg_path, csv_path, out_path)

        with open(out_path, encoding="utf-8") as f:
            result = _yaml.safe_load(f)

        meta = result["meta"]
        ne_units = result["nutzeinheiten"]

        # Σ aller Perioden-Summen sollte innerhalb der Rundungstoleranz liegen
        summe_alle = sum(
            p["summe_eur"]
            for ne in ne_units.values()
            for p in ne.get("mieter", []) + ne.get("leerstand", [])
        )
        erwartete_summe = (
            meta["h_netto_eur"] + meta["ww_waerme_eur"] + meta["co2_mieter_total_eur"]
        )
        assert summe_alle == pytest.approx(erwartete_summe, abs=0.10)

    def test_wmz_aufteilung(self, tmp_files):
        import yaml as _yaml
        cfg_path, csv_path, out_path = tmp_files
        calc.run(cfg_path, csv_path, out_path)

        with open(out_path, encoding="utf-8") as f:
            result = _yaml.safe_load(f)

        meta = result["meta"]
        # WMZ-WW = 25.0 (2025-12-31), WMZ-H = 37.5 → WW-Anteil = 25/62.5 = 40 %
        assert meta["wmz_ww_mwh"] == pytest.approx(25.0)
        assert meta["wmz_h_mwh"]  == pytest.approx(37.5)
        assert meta["ww_anteil_pct"] == pytest.approx(40.0)

    def test_zwei_ne_gleiche_aufteilung(self, tmp_files):
        """Bei gleicher Fläche und gleichem Verbrauch: beide NE bekommen gleiche Kosten."""
        import yaml as _yaml
        cfg_path, csv_path, out_path = tmp_files
        calc.run(cfg_path, csv_path, out_path)

        with open(out_path, encoding="utf-8") as f:
            result = _yaml.safe_load(f)

        ne1_summe = result["nutzeinheiten"]["1"]["mieter"][0]["summe_eur"]
        ne2_summe = result["nutzeinheiten"]["2"]["mieter"][0]["summe_eur"]
        assert ne1_summe == pytest.approx(ne2_summe, abs=0.02)

    def test_heizung_netto_gleich_gesamt_minus_ww(self, tmp_files):
        import yaml as _yaml
        cfg_path, csv_path, out_path = tmp_files
        calc.run(cfg_path, csv_path, out_path)

        with open(out_path, encoding="utf-8") as f:
            result = _yaml.safe_load(f)

        meta = result["meta"]
        assert meta["h_netto_eur"] + meta["ww_waerme_eur"] == pytest.approx(
            meta["heiz_gesamt_eur"], abs=0.01
        )

    def test_co2_mieter_pct_korrekt(self, tmp_files):
        """26.78 kg/m²/Jahr → 35 % Mieteranteil."""
        import yaml as _yaml
        cfg_path, csv_path, out_path = tmp_files
        calc.run(cfg_path, csv_path, out_path)

        with open(out_path, encoding="utf-8") as f:
            result = _yaml.safe_load(f)

        assert result["meta"]["co2_mieter_pct"] == 35
