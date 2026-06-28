# Spec 001 — Heizkostenabrechnung nach HeizkostenV

**Status:** In Progress — Phase 2 + Tests + Phase 4 (PDF) abgeschlossen  
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
| Kaltwasserzähler | KWZ | m³ | Kaltwasserverbrauch je Nutzeinheit (nur Plausibilitätsprüfung) |
| Wärmemengenzähler Heizung | WMZ-H | MWh | Gesamtwärmeverbrauch Heizkreis (Gerät `EFE-44556666H-04`, NE 11) |
| Wärmemengenzähler Warmwasser | WMZ-WW | MWh | Wärmeenergie für Warmwassererwärmung (Gerät `EFE-44556665H-04`, NE 10) |

**Abgrenzung:** Kaltwasser wird bereits separat über immocloud abgerechnet. Dieses Tool berechnet **nur Heizung und Warmwasser** nach HeizkostenV. KWZ-Werte werden ausschließlich für die Plausibilitätsprüfung (KWZ ≥ WWZ) verwendet.

**WMZ-Besonderheit:** Beide WMZ sind als "Nutzeinheit" 10 und 11 im Heizraum (1.UG) in der CSV enthalten. Sie wurden am 01.01.2025 eingebaut (kein 2024-12-31-Startwert). Die monatlichen Werte sind kumulative MWh ab Einbau:

| NE | Geräte-Nr | Funktion | Jahreswert 2025-12-31 |
|----|-----------|----------|-----------------------|
| 10 | `EFE-44556665H-04` | WMZ Warmwasser | 16,77 MWh |
| 11 | `EFE-44556666H-04` | WMZ Heizung | 26,33 MWh |

Da beide WMZ verfügbar sind, entfällt die Schätzung nach § 9a HeizkostenV.

**HKVE-Besonderheit:** Der elektronische Heizkostenverteiler misst die Heizkörperoberflächen-temperatur relativ zur Raumtemperatur und gibt dimensionslose **Heizkosteneinheiten (HKE)** aus. Der Thermomess-**Kd-Faktor** (z.B. 1,582) ist bereits in den exportierten Ablesewerten enthalten — keine manuelle Umrechnung erforderlich. Das Gerät wird nach der Jahresablesung auf 0 zurückgesetzt.

---

## 2. Datenbasis

### 2.1 Eingabedaten

| Quelle | Inhalt | Format |
|--------|--------|--------|
| `Ablesewerte_*_semikolon.csv` | Monatliche Zählerwerte je Gerät und Nutzeinheit (HKVE, WWZ, KWZ, **WMZ**) | CSV, Semikolon-getrennt |
| Heizkostenrechnung Versorger | Gesamtkosten Heizung + Warmwasser (Brennstoff, Wartung, CO₂-Abgabe) | PDF / manuell |
| Wohnflächennachweis | m²-Fläche je Nutzeinheit | aus XLSX |

> **Hinweis:** WMZ-Werte (NE 10 und 11) stehen in derselben CSV wie HKVE/WWZ. Sie haben keinen `2024-12-31`-Anfangswert (Einbau 01.01.2025) — der Startwert ist implizit 0.

### 2.2 CSV-Struktur

```
Nutzeinheit ; Stockwerk ; Lage ; Raum ; Geräte-Nr ; Typ ; Einbau ; Ausbau ;
2024-12-31 ; 2025-01-31 ; ... ; 2025-12-31
```

- Spalte `2024-12-31`: Anfangsstand (= Endstand Vorjahr)
- Spalten `2025-01-31` … `2025-12-31`: Monatliche Stände
- Leere Zelle oder `[FS*]`: kein Wert (Zähler defekt, Leerstand)

### 2.3 Nutzeinheiten

| NE | Bezeichnung       | Fläche (m²) | Aktueller Mieter (2025) |
|----|-------------------|-------------|-------------------------|
| 1  | 20 - EG links     | 50,40       | Jennifer Rose Gombár (bis 30.04.) / Dirk Hamm (ab 15.07.) |
| 2  | 10 - EG rechts    | 50,72       | Ilona Thiele |
| 3  | 40 - 1.OG links   | 50,40       | Leonie-Luna Fischer |
| 4  | 30 - 1.OG rechts  | 50,72       | Lena-Marie Mank |
| 5  | 60 - 2.OG links   | 50,40       | Christian Fürschke (bis 31.05.) / Leerstand / Robert Sukanik (ab 15.08.) / Marek Ziga (ab 01.11.) |
| 6  | 50 - 2.OG rechts  | 50,72       | Sandra Haschke |
| 7  | 80 - DG links     | 41,13       | Alexander Otto |
| 8  | 70 - DG rechts    | 57,69       | Uwe Schlegel |

**Gesamt:** 402,18 m²

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
- **Wasserkosten** (Kaltwasserpreis × Warmwasserverbrauch) — der Kaltwasserpreis für die Warmwassererwärmung ist Bestandteil der Versorgerrechnung

> **Hinweis:** Der allgemeine Kaltwasserverbrauch (Trinkwasser/Abwasser) wird separat über immocloud abgerechnet und ist nicht Teil dieser Berechnung.

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

- **Verbrauchskosten**: auf Basis der Zählerstände zum Ein-/Auszugsdatum
- **Grundkosten**: zeitanteilig (Tage Mietdauer / 365)
- Beide Mieter erhalten separate Abrechnungen

```
H_grund_Mieter_A = H_grund_NE_i × (Tage_A / 365)
H_grund_Mieter_B = H_grund_NE_i × (Tage_B / 365)

H_verbrauch_Mieter_A = H_verbrauch × (HKVE_A / HKVE_gesamt)
H_verbrauch_Mieter_B = H_verbrauch × (HKVE_B / HKVE_gesamt)
```

### 3.6 Startwert bei untermonatlichem Einzug

Wenn der Einzug nicht zum Monatsersten erfolgt (z.B. 15.07.), gibt es keinen
Zählerstand genau zum Einzugsdatum in der CSV (Stände sind immer Monatsendwerte).

**Regel:** Der Endwert des **Vormonats** gilt als Startwert für den einziehenden Mieter.

```
Beispiel: Einzug 15.07.2025
  → Startwert HKVE = CSV-Wert 2025-06-30
  → Startwert WWZ  = CSV-Wert 2025-06-30

Verbrauch Mieter_B = Endstand 2025-12-31 − Vormonatsendstand 2025-06-30
```

Für den ausziehenden Mieter (Auszug z.B. 14.07.) gilt spiegelbildlich:

```
  → Endwert Mieter_A = CSV-Wert 2025-07-31  (Endstand des aktuellen Monats)
  → Leerstandsperiode ab 15.07.: kein Verbrauch, kein eigener Zählerstand
    (Grundkosten der Leerstandstage gehen an den Vermieter)
```

**Implementierungshinweis:** Die Funktion `resolve_meter_value(geraet_nr, date, csv)`
sucht zunächst den exakten Monatsspalten-Wert. Liegt das Datum innerhalb eines Monats
(nicht Monatsletzter), gilt:
- **Einzug untermonatlich** → Startwert = Endstand des **Vormonats**
- **Auszug untermonatlich** → Endwert = Endstand des **aktuellen Monats**

---

## 4. Berechnung Wärmeanteil Warmwasser (§ 9a HeizkostenV)

Da **beide WMZ vorhanden** sind (WMZ-H und WMZ-WW), wird der Wärmeanteil für Warmwasser direkt aus den Messwerten berechnet — keine Schätzung nach § 9a erforderlich.

```
Q_ww      = WMZ-WW Jahreswert (MWh)   → z.B. 16,77 MWh
Q_heizung = WMZ-H  Jahreswert (MWh)   → z.B. 26,33 MWh
Q_gesamt  = Q_ww + Q_heizung          → z.B. 43,10 MWh

WW_wärme_anteil = Q_ww / Q_gesamt     → z.B. 38,9 %
WW_wärme        = Heiz_Gesamtkosten × WW_wärme_anteil
H_kosten_netto  = Heiz_Gesamtkosten × (1 − WW_wärme_anteil)
```

Fallback (§ 9a, nur wenn ein WMZ defekt/fehlt):

```
Q_ww = 2,5 × kWh/m³ × WWZ_verbrauch_gesamt
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

Die Applikation besteht aus **vier unabhängigen Werkzeugen**, die sequenziell ausgeführt werden:

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
         ┌──────────┴──────────┐
         │                     │
┌────────▼────────────┐  ┌─────▼───────────────────────────────┐
│ 3. heizkosten_      │  │ 4. heizkosten_pdf.py                │
│    immocloud_       │  │    Input:  heizkosten_ergebnis.yaml  │
│    export.py        │  │    Output: Heizk_<Mieter>.pdf je Mieter│
│    Input: Ergebnis  │  │    → Versand-fertige Abrechnung      │
│    Output: EUR-     │  │      (eigenständiges PDF, kein       │
│    Betrag in        │  │      (nur Heizung + Warmwasser)      │
│    immocloud als    │  └─────────────────────────────────────┘
│    "extern ber.     │
│    Kosten"          │
└─────────────────────┘
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

### 6.3 Ausgabe-Modul (`heizkosten_immocloud_export.py`)

```
OutputModule
├── render_console(statements)   → Kontrollausgabe Summenprüfung
├── render_csv(statements)       → Tabellarische Zusammenfassung (Excel-lesbar)
└── render_immocloud(statements) → Vorbereitung für immocloud-Übergabe
```

Liefert die **berechneten EUR-Beträge** (Heizung + Warmwasser je NE/Mieter) für den Upload in immocloud als "extern berechnete Kosten".

### 6.4 PDF-Generator (`heizkosten_pdf.py`)

Erzeugt je Mieter eine **Heizkostenabrechnung als PDF**, die direkt an den Mieter verschickt werden kann. Das PDF wird neu erstellt — das Referenzformat der bisherigen Heizkostenabrechnungen stammt von **Thermomess** (Abrechnungsdienstleister für Heizkosten/WMZ), nicht von immocloud.

Das PDF orientiert sich am **Thermomess-Format** (mehrseitig). Aufbau:

**Seite 1 — Kopf + Ablesewerte (je Nutzeinheit)**

```
Einzelabrechnung <ObjektNr> / <NE> — Abrechnungszeitraum 01.01.25 bis 31.12.25
──────────────────────────────────────────────────────────────────────────────
Absender:     Anton Frank, Loschwitzer Str. 17, 01309 Dresden
Empfänger:    <Mietername>, Zaschendorfer Str. 20, 01662 Meißen
Lage:         <Stockwerk, Seite>

Ihre Ablesewerte — Raumwärme (HKVE)
Raum   Seriennr.   Geräteart   Einbau      Anfang   Ablesung   Verbrauch   Kd-Fakt.   Einheiten
BAD    29728206    SONTEX868   01.01.2025     0,00     71,00      71,00      1,582       112,32
KÜ     29728205    …           …              …        …          …          …           …
…
                                                              Ihre Einheiten: xxx,xx VE

Ihre Ablesewerte — Warmwasser (WWZ)
Raum   Seriennr.   Geräteart   Einbau      Anfang   Ablesung   Verbrauch (m³)
BAD    28818103    WWZ         01.01.2025    0,000    10,790      10,790
                                                              Ihre Einheiten: x,xxx m³
```

**Seite 2 — Gesamtkosten der Liegenschaft + Verteilungsberechnung**

```
Gesamtkosten der Liegenschaft im Abrechnungszeitraum
──────────────────────────────────────────────────────────────────────────────
Energieträgerkosten
  Gas / Brennstoff          8.186,58 €
  Summe Heizungskosten      8.186,58 €

Warmwasserzusatzkosten        0,00 €
  (Gerätemieten und Abrechnungsdienst sind separat in der Nebenkostenabrechnung)

Gesamtkosten zur Verteilung   8.186,58 €

──────────────────────────────────────────────────────────────────────────────
Trennung Raumwärme / Wassererwärmung (aus WMZ):
  WMZ-WW: 16,77 MWh von gesamt 43,10 MWh = 38,91 %
  Kostenanteil Wassererwärmung  = 38,91 % × x.xxx,xx € = x.xxx,xx €
  Kostenanteil Raumwärme        = x.xxx,xx € − x.xxx,xx € = x.xxx,xx €

CO₂-Abgabe (CO₂KostAufG):
  Gesamt 704,98 € × 35 % Mieteranteil = 246,74 €  (Stufe 26,78 kg CO₂/m²/Jahr)

Verteilung Raumwärme:
  30 % Grundanteil  x.xxx,xx € ÷ 402,18 m²   = x,xxxxxx €/m²
  70 % Verbrauch    x.xxx,xx € ÷ xxxxx,xx VE  = x,xxxxxx €/VE

Verteilung Wassererwärmung:
  30 % Grundanteil  xxx,xx € ÷ 402,18 m²     = x,xxxxxx €/m²
  70 % Verbrauch    xxx,xx € ÷ xxx,xx m³     = xx,xxxxxx €/m³
```

**Seite 3 — Ihre Kosten (Mieteranteil)**

```
Ihre Kosten — Abrechnungszeitraum <von> bis <bis>
──────────────────────────────────────────────────────────────────────────────
Raumwärme
  Grundanteil:    x,xxxxxx €/m² × xx,xx m² × (Tage/365)  =  xx,xx €
  Verbrauchsant.: x,xxxxxx €/VE × xxx,xx VE               = xxx,xx €
  Summe Raumwärme                                          = xxx,xx €

Wassererwärmung
  Grundanteil:    x,xxxxxx €/m² × xx,xx m² × (Tage/365)  =  xx,xx €
  Verbrauchsant.: xx,xxxxxx €/m³ × x,xxx m³              =  xx,xx €
  Summe Wassererwärmung                                    =  xx,xx €

CO₂-Abgabe (Mieteranteil)                                 =  xx,xx €

Ihre Gesamtkosten Heizung + Warmwasser                    = xxx,xx €
──────────────────────────────────────────────────────────────────────────────
```

**Hinweis:** Das PDF enthält ausschließlich Heizung und Warmwasser. Alle anderen Betriebskosten (Kaltwasser, Gebäudeversicherung, Müll etc.) werden separat über immocloud abgerechnet und erscheinen dort in der vollständigen Nebenkostenabrechnung.

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
  heizung_gesamt:       3850.00   # EUR inkl. CO₂-Abgabe (Versorger-Gesamtrechnung)
  co2_abgabe:            420.00   # EUR (Anteil an heizung_gesamt)
  # WMZ-basierte Aufteilung Heizung vs. Warmwasser (aus CSV automatisch berechnet):
  wmz_heizung_mwh:        26.33   # WMZ-H (NE 11, EFE-44556666H-04)
  wmz_warmwasser_mwh:     16.77   # WMZ-WW (NE 10, EFE-44556665H-04)
  # wmz_waerme_anteil_ww: 0.389   # automatisch: wmz_warmwasser / (wmz_heizung + wmz_warmwasser)
  warmwasser_wasser:     380.00   # EUR (Kaltwasserpreis × m³ für Warmwassererwärmung, aus Versorger-Rechnung)

wmz_geraete:
  heizung:     "EFE-44556666H-04"   # NE 11 in CSV
  warmwasser:  "EFE-44556665H-04"   # NE 10 in CSV

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

## 8. Ziel-Outputs

Die Applikation produziert **zwei Outputs**:

### 8.1 Immocloud-Übergabe (EUR-Betrag)

Der berechnete **Heizkosten-Betrag je Nutzeinheit (und Mietperiode)** wird als
"extern berechnete Kosten" in immocloud eingetragen — dort erfolgt die vollständige
Nebenkostenabrechnung gegenüber dem Mieter (inkl. Kaltwasser, Versicherung, etc.).

### 8.2 Heizkostenabrechnung PDF (Mieterversand)

Zusätzlich wird je Mieter ein PDF erzeugt (`Heizk_<Jahr>_<Vorname>_<Nachname>.pdf`),
das die **detaillierte Aufschlüsselung der Heizkosten und Warmwasserkosten** enthält
nach den Anforderungen des § 6 Abs. 4 HeizkostenV. Dieses PDF wird direkt an den
Mieter verschickt.

**Übergabe-Format (Ergebnis je NE/Mieter):**

```yaml
# heizkosten_ergebnis.yaml
ergebnis:
  "1":
    name: "20 - EG links"
    flaeche_m2: 50.40
    mieter:
      - name:         "Jennifer Rose Gombár"
        periode_von:  "2025-01-01"
        periode_bis:  "2025-04-30"
        tage:         120
        hkve_einheiten: 312.5
        wwz_m3:         2.840
        heizung_grundkosten_eur:      28.10
        heizung_verbrauchskosten_eur: 114.20
        heizung_gesamt_eur:           142.30
        warmwasser_grundkosten_eur:    14.50
        warmwasser_verbrauchskosten_eur: 33.60
        warmwasser_gesamt_eur:          48.10
        co2_mieter_eur:                  8.20
        summe_eur:                     198.60
        pdf_datei: "Heizk_2025_Jennifer_Rose_Gombar.pdf"
      - name:         "Dirk Hamm"
        periode_von:  "2025-07-15"
        periode_bis:  "2025-12-31"
        tage:         170
        hkve_einheiten: 445.0
        wwz_m3:         4.120
        heizung_grundkosten_eur:      39.80
        heizung_verbrauchskosten_eur: 128.60
        heizung_gesamt_eur:           168.40
        warmwasser_grundkosten_eur:    20.60
        warmwasser_verbrauchskosten_eur: 37.30
        warmwasser_gesamt_eur:          57.90
        co2_mieter_eur:                  9.80
        summe_eur:                     236.10
        pdf_datei: "Heizk_2025_Dirk_Hamm.pdf"
    leerstand:
      - periode_von: "2025-05-01"
        periode_bis:  "2025-07-14"
        tage: 75
        kosten_vermieter_eur: 89.40   # Grundkostenanteil anteilig
```

Leerstandsperioden (hier: 01.05.–14.07.) werden separat ausgewiesen und dem Vermieter zugerechnet.

---

## 9. Validierungen & Plausibilitätsprüfungen

| Prüfung | Kriterium |
|---------|-----------|
| Vollständigkeit | Alle aktiven Zähler haben Jahresendwert |
| Plausibilität HKVE | Kein Wert > 200 % des Durchschnitts (Ausreißer) |
| Plausibilität WWZ | Jahresverbrauch > 0 wenn Wohnung bewohnt |
| KWZ ≥ WWZ | Kaltwasser ≥ Warmwasser je NE (physikalisch zwingend; KWZ nur für diese Prüfung) |
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
- [x] Lücken zwischen Mietern als "Leerstand"-Periode kennzeichnen (implementiert in `heizkosten_calc.py` → `build_periods()`)
- [x] Energiekosten aus der Versorger-Rechnung eintragen

### Phase 2 — Berechnung (`heizkosten_calc.py`)
- [x] CSV-Ladelogik aus `immocloud_common.py` wiederverwenden
- [x] `calc_heating()` — Heizkosten nach HKVE
- [x] `calc_hotwater()` — WW-Kosten nach WWZ
- [x] `calc_co2()` — CO₂-Mieteranteil nach CO₂KostAufG
- [x] `calc_tenant_split()` — Mieterwechsel (zeitanteilig + verbrauchsbasiert)
- [x] Leerstandsperioden dem Vermieter zurechnen
- [x] Unit-Tests für alle Formeln

### Phase 3 — Validierung
- [x] Plausibilitätsprüfungen aus Abschnitt 9 (Summenprüfung)
- [x] Kontrollausgabe: Summen = Gesamtkosten

### Phase 4 — PDF-Generator (`heizkosten_pdf.py`) ✅
- [x] PDF-Bibliothek auswählen: `reportlab` 5.0
- [x] Seite 1: Briefkopf Absender/Empfänger + HKVE-Gerätetabelle + WWZ-Gerätetabelle
- [x] Seite 2: Gesamtkosten Liegenschaft, WMZ-Trennung, CO₂-Stufe, Umlagepreise
- [x] Seite 3: Mieteranteil — Raumwärme + Wassererwärmung + CO₂ mit Rechenschritten
- [x] Summenzeile Heizung + Warmwasser + CO₂ gesamt
- [x] Ausgabe: `Heizk_<Jahr>_<Name>.pdf` je Mieter (11 PDFs für 2025 generiert)

### Phase 5 — Übergabe an immocloud
- [x] `heizkosten_ergebnis.yaml` schreiben (von `heizkosten_calc.py` erzeugt)
- [ ] `heizkosten_ergebnis.csv` schreiben (tabellarische Zusammenfassung, Excel-lesbar)
- [ ] Optional: Playwright-Upload als "extern berechnete Kosten"

---

## 12. Abhängigkeiten

```
openpyxl     – XLSX-Import (immocloud Objektexport)
pyyaml       – Konfigurationsdatei lesen/schreiben
pytest       – Unit-Tests Berechnungslogik
reportlab    – PDF-Erzeugung (Heizkostenabrechnung je Mieter) — verwendet
```

---

## 13. Offene Fragen

| # | Frage | Priorität | Status |
|---|-------|-----------|--------|
| 1 | Wohnflächen je NE (m²) | HOCH | ✅ aus XLSX: 402,18 m² gesamt (je NE in §2.3 eingetragen) |
| 2 | Mieterwechsel 2025 vollständig? | HOCH | ✅ NE 1 (Apr/Jul), NE 5 (3× Wechsel + Leerstand) erkannt |
| 3 | Gesamtkosten Heizung 2025 (Versorger-Rechnung) | HOCH | ✅ 8.186,58 € Brennstoff inkl. CO₂-Abgabe (in `heizkosten_config.yaml`) |
| 4 | Gesamtkosten Warmwasser 2025 | HOCH | ✅ WMZ-basiert berechnet: 38,91 % × 8.186,58 € = 3.185,36 € Wärmeanteil |
| 5 | CO₂-Abgabe-Anteil aus Rechnung | MITTEL | ✅ 704,98 € (in `heizkosten_config.yaml`; Mieteranteil 35 % = 246,74 €) |
| 6 | Spezifischer CO₂-Ausstoß kg/m²/Jahr | MITTEL | ✅ 26,78 kg/m²/Jahr aus Versorger-Rechnung (10.771,211 kg / 402,18 m²) → Stufe 22–32 → 35 % Mieteranteil |
| 7 | WMZ-Daten für Warmwasser-Wärmeanteil | NIEDRIG | ✅ WMZ-WW (16,77 MWh) und WMZ-H (26,33 MWh) aus CSV; § 9a nicht benötigt |
| 8 | Leerstandsperioden NE 1 (01.05.–14.07.2025) — Kosten Vermieter? | MITTEL | ✅ Ja — Grundkostenanteil anteilig dem Vermieter zugerechnet (81,97 €); implementiert in `build_periods()` |
