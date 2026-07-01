# Betriebskostenabrechnung 2025 — Zaschendorfer Str. 20, Meißen

Werkzeuge und Daten für die jährliche Betriebs- und Heizkostenabrechnung des
Mehrfamilienhauses (8 Nutzeinheiten, Abrechnungsjahr 2025).

---

## Struktur

```
immocloud_sync/                   Skripte zum Übertragen der Zählerwerte in immocloud
  immocloud_create_meters.py      Zähler in immocloud anlegen (einmalig je NE/Gerät)
  immocloud_add_readings.py       Ablesewerte aus CSV in immocloud einspielen
  sync_jobs/                      Job-Definitionen je Zählertyp (HKVE, WWZ, KWZ)
  meters_state.json               Zustand letzter Sync (verhindert Doppeleinträge)

exports/                          Rohdaten vom Thermomess-Portal
  Ablesewerte_*_semikolon.csv     Original-CSV ohne Kd-Faktor
  Ablesewerte_2025_mit_Kd_Faktor.csv  Angereichert (Kd-Faktor-Spalte)

heizkosten_rechner/
  heizkosten_config_gen.py        Erzeugt heizkosten_config.yaml aus immocloud-Export
  heizkosten_calc.py              Berechnung nach HeizkostenV → heizkosten_ergebnis.yaml
  heizkosten_pdf.py               PDF-Abrechnung je Mieter aus heizkosten_ergebnis.yaml
  output/
    heizkosten_config.yaml        Eingabe: Mieter, Flächen, Kosten, CSV-Pfad
    heizkosten_ergebnis.yaml      Ausgabe: Kosten je Mieter/Periode inkl. HKVE-Gerätedetails
    Heizk_2025_*.pdf              Fertige Abrechnungs-PDFs je Mieter

specs/
  001-heizkostenabrechnung/       Fachliche Grundlagen, Berechnungsschritte, Datenstruktur
  002-faktorBerechnung/           Workflow Kd-Faktor ermitteln und CSV anreichern
```

---

## Workflow

```
1. heizkosten_config_gen.py  →  output/heizkosten_config.yaml
2. (Kd-Faktor manuell eintragen, siehe specs/002-faktorBerechnung/spec.md)
3. heizkosten_calc.py        →  output/heizkosten_ergebnis.yaml
4. heizkosten_pdf.py         →  output/Heizk_2025_*.pdf
```

### Ausführung

```bash
cd heizkosten_rechner

# Schritt 3 — Abrechnung berechnen
python3 heizkosten_calc.py \
    --config output/heizkosten_config.yaml \
    --csv    ../exports/Ablesewerte_2025_mit_Kd_Faktor.csv \
    --output output/heizkosten_ergebnis.yaml

# Schritt 4 — PDFs erzeugen
python3 heizkosten_pdf.py \
    --ergebnis   output/heizkosten_ergebnis.yaml \
    --csv        ../exports/Ablesewerte_2025_mit_Kd_Faktor.csv \
    --config     output/heizkosten_config.yaml \
    --output-dir output/
```

Python-Abhängigkeiten (im `.venv`): `reportlab`, `PyYAML`

---

## Wichtige Hinweise

- **Kd-Faktor:** Der CSV-Export aus dem Thermomess-Portal enthält keinen Kd-Faktor.
  Er muss manuell aus der Webansicht ermittelt und dem CSV hinzugefügt werden.
  Vollständiger Workflow → [specs/002-faktorBerechnung/spec.md](specs/002-faktorBerechnung/spec.md)

- **Leerstand:** Lücken zwischen Mieterperioden werden automatisch als Leerstand
  berechnet; Kosten gehen zu Lasten des Vermieters.

- **CO₂-Abgabe (CO₂KostAufG):** Wegen Denkmalschutz trägt der Mieter 90 % der
  CO₂-Kosten. Konfigurierbar in `heizkosten_config.yaml` → `co2_mieter_pct`.
