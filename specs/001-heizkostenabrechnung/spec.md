# Spec 001 — Heizkostenabrechnung nach HeizkostenV

**Status:** Draft  
**Erstellt:** 2026-06-28  
**Objekt:** Zaschendorfer Str. 20, Meißen  
**Abrechnungsjahr:** 2025  
**Anzahl Nutzeinheiten:** 8  

---

## 1. Fachlicher Hintergrund

### 1.1 Rechtsgrundlage

Die **Heizkostenverordnung (HeizkostenV)** verpflichtet Vermieter, die Kosten für Heizung und Warmwasser verbrauchsabhängig auf die Mieter umzulegen (§ 1 HeizkostenV). Die Verordnung gilt für Gebäude mit zentraler Wärme- und Warmwasserversorgung.

**Kernparagraphen:**

| § | Thema |
|---|-------|
| § 6 | Aufteilung Heizkosten: 30–50 % Grundkosten, 50–70 % Verbrauchskosten |
| § 7 | Verteilung der Heizkosten (Heizkostenverteiler / Wärmemengenzähler) |
| § 8 | Aufteilung Warmwasserkosten: 30–50 % Grundkosten, 50–70 % Verbrauchskosten |
| § 9 | Verteilung der Warmwasserkosten (WWZ) |
| § 9a | Berechnung Wärmeanteil Warmwasser aus Brennstoffverbrauch |
| § 12 | Kürzungsrecht des Mieters bei Verstoß (−15 %) |

### 1.2 Messsystem in diesem Objekt

| Gerät | Kürzel | Einheit | Funktion |
|-------|--------|---------|----------|
| Heizkostenverteiler elektronisch | HKVE | HKE (dimensionslos) | Raumheizung je Nutzeinheit |
| Warmwasserzähler | WWZ | m³ | Warmwasserverbrauch je Nutzeinheit |
| Kaltwasserzähler | KWZ | m³ | Kaltwasserverbrauch je Nutzeinheit |
| Wärmemengenzähler | WMZ | MWh | Gesamtwärmeverbrauch Heizkreis |
| FAM-Zähler (Funkablesung) | FAM (WWZ) | m³ | Warmwasser (funkbasiert) |

**HKVE-Besonderheit:** Der elektronische Heizkostenverteiler misst die Heizkörperoberflächen-temperatur relativ zur Raumtemperatur und gibt dimensionslose **Heizkosteneinheiten (HKE)** aus. Der Thermomess-**Kd-Faktor** (z.B. 1,582) ist bereits in den exportierten Ablesewerten enthalten — keine manuelle Umrechnung erforderlich. Das Gerät wird nach der Jahresablesung auf 0 zurückgesetzt.

---

## 2. Datenbasis

### 2.1 Eingabedaten

| Quelle | Inhalt | Format |
|--------|--------|--------|
| `Ablesewerte_*_semikolon.csv` | Monatliche Zählerstände je Gerät und Nutzeinheit | CSV, Semikolon-getrennt |
| Heizkostenrechnung Versorger | Gesamtkosten Heizung + Warmwasser | PDF / manuell |
| Wohnflächennachweis | m²-Fläche je Nutzeinheit | manuell |

### 2.2 CSV-Struktur

```
Nutzeinheit ; Stockwerk ; Lage ; Raum ; Geräte-Nr ; Typ ; Einbau ; Ausbau ;
2024-12-31 ; 2025-01-31 ; ... ; 2025-12-31
```

- Spalte `2024-12-31`: Anfangsstand (= Endstand Vorjahr)
- Spalten `2025-01-31` … `2025-12-31`: Monatliche Stände
- Leere Zelle oder `[FS*]`: kein Wert (Zähler defekt, Leerstand)

### 2.3 Nutzeinheiten

| NE | Bezeichnung       | Fläche (m²) |
|----|-------------------|-------------|
| 1  | 20 - EG links     | *zu erfassen* |
| 2  | 10 - EG rechts    | *zu erfassen* |
| 3  | 40 - 1.OG links   | *zu erfassen* |
| 4  | 30 - 1.OG rechts  | *zu erfassen* |
| 5  | 60 - 2.OG links   | *zu erfassen* |
| 6  | 50 - 2.OG rechts  | *zu erfassen* |
| 7  | 80 - DG links     | *zu erfassen* |
| 8  | 70 - DG rechts    | *zu erfassen* |

---

## 3. Berechnungsschritte

### 3.1 Schritt 1 — Gesamtkosten erfassen

Der Versorger stellt Gesamtkosten für:
- **Heizung** (Brennstoff, Wartung, ggf. CO₂-Abgabe)
- **Warmwasser** (Brennstoffanteil + Kaltwasserkosten für Erwärmung)

Diese werden manuell eingegeben oder aus einer Rechnung importiert.

### 3.2 Schritt 2 — Kostenaufteilung Heizung (§ 6, § 7 HeizkostenV)

```
Heizkosten_gesamt = H_grund + H_verbrauch
```

Aufteilungsschlüssel (konfigurierbar, Standard 30/70):

```
H_grund     = Heizkosten_gesamt × Grundkostenanteil  (z.B. 30 %)
H_verbrauch = Heizkosten_gesamt × Verbrauchsanteil   (z.B. 70 %)
```

**Grundkostenverteilung** nach Wohnfläche:

```
H_grund_NE_i = H_grund × (Fläche_i / Fläche_gesamt)
```

**Verbrauchskostenverteilung** nach HKVE-Einheiten:

```
HKVE_gesamt = Σ HKVE_Jahreswert_NE_i   (alle aktiven Zähler)

H_verbrauch_NE_i = H_verbrauch × (HKVE_NE_i / HKVE_gesamt)
```

**Heizkosten je Nutzeinheit:**

```
Heizkosten_NE_i = H_grund_NE_i + H_verbrauch_NE_i
```

### 3.3 Schritt 3 — Kostenaufteilung Warmwasser (§ 8, § 9 HeizkostenV)

Warmwasserkosten setzen sich zusammen aus:
- **Wärmekosten** (Energie zum Erhitzen): aus WMZ oder nach § 9a berechnet
- **Wasserkosten** (Kaltwasserpreis × Warmwasserverbrauch)

```
WW_kosten_gesamt = WW_wärme + WW_wasser
```

Aufteilungsschlüssel (Standard 30/70):

```
WW_grund     = WW_kosten_gesamt × Grundkostenanteil
WW_verbrauch = WW_kosten_gesamt × Verbrauchsanteil
```

**Grundkostenverteilung** nach Wohnfläche:

```
WW_grund_NE_i = WW_grund × (Fläche_i / Fläche_gesamt)
```

**Verbrauchskostenverteilung** nach WWZ-Verbrauch:

```
WWZ_verbrauch_NE_i = WWZ_Endstand_NE_i − WWZ_Anfangsstand_NE_i

WWZ_verbrauch_gesamt = Σ WWZ_verbrauch_NE_i

WW_verbrauch_NE_i = WW_verbrauch × (WWZ_verbrauch_NE_i / WWZ_verbrauch_gesamt)
```

**Warmwasserkosten je Nutzeinheit:**

```
WW_kosten_NE_i = WW_grund_NE_i + WW_verbrauch_NE_i
```

### 3.4 Schritt 4 — Gesamtabrechnung je Nutzeinheit

```
Gesamtkosten_NE_i = Heizkosten_NE_i + WW_kosten_NE_i
Vorauszahlungen_NE_i = (aus Mietvertrag, monatlich × Monate)
Nachzahlung_NE_i = Gesamtkosten_NE_i − Vorauszahlungen_NE_i
```

Negatives Ergebnis = Guthaben.

### 3.5 Sonderfall: Mieterwechsel unterjährig

Bei Mieterwechsel innerhalb des Abrechnungsjahres:

- **Verbrauchskosten**: auf Basis der Ablesungen zum Ein-/Auszugsdatum (Zwischenablesung)
- **Grundkosten**: zeitanteilig (Tage Mietdauer / 365)
- Beide Mieter erhalten separate Abrechnungen

```
H_grund_Mieter_A = H_grund_NE_i × (Tage_A / 365)
H_grund_Mieter_B = H_grund_NE_i × (Tage_B / 365)

H_verbrauch_Mieter_A = H_verbrauch × (HKVE_A / HKVE_gesamt)
H_verbrauch_Mieter_B = H_verbrauch × (HKVE_B / HKVE_gesamt)
```

---

## 4. Berechnung Wärmeanteil Warmwasser (§ 9a HeizkostenV)

Wenn kein separater WMZ für Warmwasser vorhanden:

```
Q_ww = 2,5 × kWh/m³ × WWZ_verbrauch_gesamt   (Richtwert § 9a)
```

Alternativ aus WMZ-Ablesung (bevorzugt, da genauer).

Anteil Wärmekosten für Warmwasser am Gesamtwärmeverbrauch:

```
WW_wärme = Heiz_Gesamtkosten × (Q_ww / Q_gesamt)
```

---

## 5. CO₂-Kostenaufteilung (CO₂KostAufG ab 2023)

Das CO₂KostAufG schreibt eine Aufteilung der CO₂-Abgabe zwischen Vermieter und Mieter vor, gestaffelt nach dem spezifischen CO₂-Ausstoß des Gebäudes (kg CO₂/m²/Jahr):

| CO₂-Ausstoß (kg/m²/Jahr) | Mieteranteil |
|---------------------------|--------------|
| > 52                      | 0 %          |
| 42–52                     | 10 %         |
| 32–42                     | 20 %         |
| 22–32                     | 35 %         |
| 12–22                     | 55 %         |
| < 12                      | 65 %         |

```
CO2_mieter_anteil  = CO2_Gesamtabgabe × Mieteranteil_Prozentsatz
CO2_vermieter_anteil = CO2_Gesamtabgabe − CO2_mieter_anteil

CO2_je_NE_i = CO2_mieter_anteil × (Fläche_i / Fläche_gesamt)
```

---

## 6. Anwendungsstruktur

Die Applikation besteht aus **drei unabhängigen Werkzeugen**, die sequenziell ausgeführt werden:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. heizkosten_config_gen.py                                 │
│    Input:  Immocloud_Objektexport.xlsx                      │
│    Output: heizkosten_config.yaml (mit Dummy-Energiekosten) │
│    → Manuell: Energiekosten aus Versorger-Rechnung eintragen│
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│ 2. heizkosten_calc.py                                       │
│    Input:  heizkosten_config.yaml                           │
│            Ablesewerte_*.csv                                │
│    Output: heizkosten_ergebnis.yaml / .csv (je NE + Mieter) │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│ 3. heizkosten_immocloud_export.py  (optional)               │
│    Input:  heizkosten_ergebnis.yaml                         │
│    Output: Werte als "extern berechnete Kosten" in Immocloud│
│            (via Playwright oder API, falls verfügbar)       │
└─────────────────────────────────────────────────────────────┘
```

### 6.1 Konfigurations-Generator (`heizkosten_config_gen.py`)

**Zweck:** Einmalig oder bei Mieterwechsel aus dem immocloud-Objektexport ausführen.

```
load_xlsx(path, abrechnungsjahr)
├── Einheit → NE-Nummer mappen (EINHEIT_TO_NR)
├── Wohnfläche je Einheit lesen
├── Mieter mit Einzug/Auszug lesen
├── Mieterwechsel innerhalb Abrechnungsjahr erkennen
└── → heizkosten_config.yaml schreiben (Energiekosten = 0,00 vorbelegt)
```

Zukünftige Inputs (erweiterbar): Excel-Export anderer Hausverwaltungssoftware, manuelle CSV.

### 6.2 Berechnungs-Modul (`heizkosten_calc.py`)

```
Calculator
├── calc_heating(costs, hkve, areas, split)    → Heizkosten je NE
├── calc_hotwater(costs, wwz, areas, split)    → WW-Kosten je NE
├── calc_co2(co2_total, co2_factor, areas)     → CO₂-Anteil je NE
├── calc_tenant_split(readings, tenants)       → Mieterwechsel-Aufteilung
└── calc_statement(ne)                         → Kostenbetrag je NE/Mieter
```

**Ausgabe je Nutzeinheit/Mieter:**
- Heizkosten (EUR): Grundanteil + Verbrauchsanteil
- Warmwasserkosten (EUR): Grundanteil + Verbrauchsanteil  
- CO₂-Mieteranteil (EUR)
- **Summe Heizkosten (EUR)** — für Übergabe an immocloud als "extern berechnete Kosten"

### 6.3 Ausgabe-Modul

```
OutputModule
├── render_console(statements)   → Kontrollausgabe Summenprüfung
├── render_csv(statements)       → Tabellarische Zusammenfassung (Excel-lesbar)
└── render_immocloud(statements) → Vorbereitung für immocloud-Übergabe
```

**Kein PDF-Abrechnungsdruck** — die Heizkostenabrechnung gegenüber dem Mieter erfolgt über immocloud (Nebenkostenabrechnung). Dieses Tool liefert nur die **berechneten EUR-Beträge** als Input.

---

## 7. Konfiguration

Die Applikation liest eine YAML-Konfigurationsdatei:

```yaml
# heizkosten_config.yaml
objekt:
  adresse: "Zaschendorfer Str. 20, 01662 Meißen"
  abrechnungsjahr: 2025
  csv_datei: "Ablesewerte_20260622-221802_semikolon.csv"

nutzeinheiten:
  "1": {name: "20 - EG links",    flaeche_m2: 62.5}
  "2": {name: "10 - EG rechts",   flaeche_m2: 58.0}
  "3": {name: "40 - 1.OG links",  flaeche_m2: 62.5}
  "4": {name: "30 - 1.OG rechts", flaeche_m2: 58.0}
  "5": {name: "60 - 2.OG links",  flaeche_m2: 62.5}
  "6": {name: "50 - 2.OG rechts", flaeche_m2: 58.0}
  "7": {name: "80 - DG links",    flaeche_m2: 55.0}
  "8": {name: "70 - DG rechts",   flaeche_m2: 55.0}

kosten:
  heizung_gesamt:       3850.00   # EUR inkl. CO₂-Abgabe
  co2_abgabe:            420.00   # EUR (Anteil an heizung_gesamt)
  warmwasser_waerme:    1250.00   # EUR
  warmwasser_wasser:     380.00   # EUR (Kaltwasserpreis × m³)

aufteilung:
  heizung_grundkosten_pct:    30   # § 6 HeizkostenV (30–50 %)
  warmwasser_grundkosten_pct: 30   # § 8 HeizkostenV (30–50 %)

co2:
  spezifischer_ausstoss_kg_m2: 38  # → Mieteranteil 20 % laut CO₂KostAufG

mieter:
  "1": [{name: "Mustermann, Max",  einzug: "2020-01-01", auszug: null}]
  "2": [{name: "Musterfrau, Anna", einzug: "2020-01-01", auszug: null}]
  # Mieterwechsel Beispiel NE 3:
  "3":
    - {name: "Alt, Mieter",  einzug: "2020-01-01",  auszug: "2025-03-31"}
    - {name: "Neu, Mieter",  einzug: "2025-04-01",  auszug: null}
```

---

## 8. Ziel-Output: Immocloud-Übergabe

Diese Applikation macht **keine** eigenständige Mieter-Abrechnung.
Sie berechnet den **Heizkosten-Betrag je Nutzeinheit (und Mietperiode)**, der dann als
"extern berechnete Kosten" in immocloud übernommen wird — dort erfolgt die eigentliche
Nebenkostenabrechnung gegenüber dem Mieter.

**Übergabe-Format (Ergebnis je NE/Mieter):**

```yaml
# heizkosten_ergebnis.yaml
ergebnis:
  "1":
    name: "20 - EG links"
    mieter:
      - name:   "Jennifer Rose Gombár"
        periode: "2025-01-01 bis 2025-04-30"
        heizkosten_eur:    142.30
        warmwasser_eur:     48.10
        co2_mieter_eur:      8.20
        summe_eur:         198.60
      - name:   "Dirk Hamm"
        periode: "2025-07-15 bis 2025-12-31"
        heizkosten_eur:    168.40
        warmwasser_eur:     57.90
        co2_mieter_eur:      9.80
        summe_eur:         236.10
```

Leerstandsperioden (hier: 01.05.–14.07.) werden separat ausgewiesen und dem Vermieter zugerechnet.

---

## 9. Validierungen & Plausibilitätsprüfungen

| Prüfung | Kriterium |
|---------|-----------|
| Vollständigkeit | Alle aktiven Zähler haben Jahresendwert |
| Plausibilität HKVE | Kein Wert > 200 % des Durchschnitts (Ausreißer) |
| Plausibilität WWZ | Jahresverbrauch > 0 wenn Wohnung bewohnt |
| KWZ ≥ WWZ | Kaltwasser ≥ Warmwasser je NE (physikalisch zwingend) |
| Summe Grundkostenanteile | Σ Grundkostenanteil_NE_i = 100 % (Floating-Point-tolerant) |
| Summe Verbrauchsanteile | Σ Verbrauchsanteil_NE_i = 100 % |
| CO₂-Aufteilung | Vermieter + Mieter = CO₂_gesamt |
| Mieterwechsel | Summe Tage_A + Tage_B = 365 (bzw. Perioden lückenlos) |

---

## 10. Pflichtangaben im Ergebnis (§ 6 Abs. 4 HeizkostenV)

Der berechnete Output muss folgende Werte enthalten, damit immocloud die
Abrechnung rechtskonform erstellen kann:

1. **Abrechnungszeitraum** je Mieter
2. **Verbrauchseinheiten** des Nutzers (HKVE, m³ WWZ)
3. **Gesamtverbrauch** des Gebäudes (HKVE-Summe, WWZ-Summe)
4. **Anteil** des Nutzers am Gesamtverbrauch (%)
5. **Kosten** aufgeteilt: Grundkostenanteil + Verbrauchskostenanteil
6. **CO₂-Mieteranteil** (EUR) gemäß CO₂KostAufG
7. **Summe Heizkosten (EUR)** — Übergabewert an immocloud

---

## 11. Implementierungs-Checkliste

### Phase 1 — Konfigurations-Generator ✅
- [x] `heizkosten_config_gen.py` implementiert
- [x] XLSX-Import aus immocloud-Objektexport
- [x] Wohnflächen automatisch extrahiert (402,18 m² gesamt)
- [x] Mieter mit Einzug/Auszug korrekt erkannt (inkl. Mieterwechsel)
- [ ] Lücken zwischen Mietern als "Leerstand"-Periode kennzeichnen
- [ ] Energiekosten aus der Versorger-Rechnung eintragen

### Phase 2 — Berechnung (`heizkosten_calc.py`)
- [ ] CSV-Ladelogik aus `immocloud_common.py` wiederverwenden
- [ ] `calc_heating()` — Heizkosten nach HKVE
- [ ] `calc_hotwater()` — WW-Kosten nach WWZ
- [ ] `calc_co2()` — CO₂-Mieteranteil nach CO₂KostAufG
- [ ] `calc_tenant_split()` — Mieterwechsel (zeitanteilig + verbrauchsbasiert)
- [ ] Leerstandsperioden dem Vermieter zurechnen
- [ ] Unit-Tests für alle Formeln

### Phase 3 — Validierung
- [ ] Plausibilitätsprüfungen aus Abschnitt 9
- [ ] Kontrollausgabe: Summen = Gesamtkosten

### Phase 4 — Übergabe an immocloud
- [ ] `heizkosten_ergebnis.yaml` + `.csv` schreiben
- [ ] Optional: Playwright-Upload als "extern berechnete Kosten"

---

## 12. Abhängigkeiten

```
openpyxl     – XLSX-Import (immocloud Objektexport)
pyyaml       – Konfigurationsdatei lesen/schreiben
pytest       – Unit-Tests Berechnungslogik
```

---

## 13. Offene Fragen

| # | Frage | Priorität | Status |
|---|-------|-----------|--------|
| 1 | Wohnflächen je NE (m²) | HOCH | ✅ aus XLSX: 402,18 m² gesamt |
| 2 | Mieterwechsel 2025 vollständig? | HOCH | ✅ NE 1 (Apr), NE 5 (3×) erkannt |
| 3 | Gesamtkosten Heizung 2025 (Versorger-Rechnung) | HOCH | ⏳ manuell eintragen |
| 4 | Gesamtkosten Warmwasser 2025 | HOCH | ⏳ manuell eintragen |
| 5 | CO₂-Abgabe-Anteil aus Rechnung | MITTEL | ⏳ manuell eintragen |
| 6 | Spezifischer CO₂-Ausstoß kg/m²/Jahr (Energieausweis) | MITTEL | ⏳ offen |
| 7 | WMZ-Daten für Warmwasser-Wärmeanteil (statt § 9a Schätzung) | NIEDRIG | ⏳ offen |
| 8 | Leerstandsperioden NE 1 (01.05.–14.07.2025) — Kosten Vermieter? | MITTEL | ⏳ offen |
