# Spec 002 — Kd-Faktor-Berechnung für HKVE-Ablesewerte

**Status:** Implementiert (2026-07-01)  
**Objekt:** Zaschendorfer Str. 20, Meißen  
**Betrifft:** Alle Abrechnungsjahre ab 2025  

---

## 1. Problemstellung

Der CSV-Export aus dem **Thermomess-Portal** enthält nur die **Roh-Ablesewerte** der HKVE-Geräte (HKE dimensionslos), aber keinen gerätespezifischen **Kd-Faktor** (Gerätekonstante).

Der Kd-Faktor ist eine technische Kalibrierkonstante, die den Einfluss von Heizkörpertype, -größe und Wandmontagefaktor auf den Messwertverlauf normiert. Er ist pro Gerät fest und ändert sich nur bei Geräteaustausch.

**Ohne Kd-Korrektur sind die Ablesewerte nicht vergleichbar und die Heizkostenverteilung ist falsch.**

### Formel

```
HKE_korrigiert = Rohablesewert_Ende × Kd-Faktor
```

---

## 2. Warum der Faktor nicht im CSV steht

Das Thermomess-Portal exportiert im CSV-Format nur Messwerte, keine Gerätemetadaten wie Kd-Faktor oder Heizkörpergröße. Der Faktor ist ausschließlich in der **Webansicht** des Portals unter „Gerätedetails" oder in der kopierbaren Wertetabelle pro Gerät sichtbar.

**Konsequenz für den Jahresworkflow:** Der Faktor muss jedes Jahr manuell aus der Webansicht extrahiert und dem CSV hinzugefügt werden — oder automatisch über einen zweiten Exportschritt.

---

## 3. Workflow: Kd-Faktor ermitteln und CSV anreichern

### Schritt 1 — CSV ohne Faktor herunterladen

1. Im Thermomess-Portal einloggen (https://thermomess.de oder Kundenportal)
2. Objekt „Zaschendorfer Str. 20" auswählen
3. Abrechnungsjahr-Export aufrufen:  
   `Ablesen → Jahresauswertung → CSV-Export (Semikolon-getrennt)`
4. Datei speichern als:  
   `exports/Ablesewerte_YYYYMMDD-HHmmss_semikolon.csv`

**Hinweis:** Der Export enthält keine Spalte `Kd-Faktor` — das ist Schritt 2.

### Schritt 2 — Faktor-Tabelle aus Webansicht kopieren

1. Im Portal zur Geräteverwaltung navigieren:  
   `Geräte → Alle Geräte → Tabelle anzeigen`  
   oder alternativ: Einzelgerät anklicken → Gerätedetails → Kd-Faktor ablesen
2. Alle NEs (1–8) durchgehen, für jede NE die Gerätelist mit Kd-Faktor aufrufen
3. Tabelle aus der Webansicht **vollständig** kopieren (Strg+A → Strg+C in der Tabelle)
4. Den kopierten Text als Rohtext in folgende Eingabedatei einfügen:  
   `exports/kd_faktoren_rohtext_YYYY.txt`

**Erwartetes Format** des kopierten Texts (Beispiel NE 2, EG rechts):
```
BADHKVE0.674SON-29728206-082024-12-31...
KÜHKVE1.167SON-29728205-082024-12-31...
WZHKVE1.297SON-29728210-082024-12-31...
WZHKVE1.297SON-29728203-082024-12-31...
SZHKVE1.582SON-29728202-082024-12-31...
KIHKVE1.582SON-29728201-082024-12-31...
```

Alternativ tabellarisch (wenn die Webansicht eine HTML-Tabelle zeigt):
```
Raum    Typ    Kd-Faktor    Geräte-Nr
BAD     HKVE   0,674        SON-29728206-08
KÜ      HKVE   1,167        SON-29728205-08
...
```

### Schritt 3 — Faktoren aus Rohtext ableiten (manuell / KI-gestützt)

Es existiert **kein fertiges Skript** für diesen Schritt. Das Format des kopierten Texts
kann sich je nach Portal-Version oder Browser ändern und muss individuell geprüft werden.

**Vorgehen:**

1. Den kopierten Rohtext dem Copilot-Agenten vorlegen mit dem Hinweis:
   > „Leite daraus für jede Geräte-Nr (Format `SON-XXXXXXXX-08`) den Kd-Faktor ab
   > und gleiche das Ergebnis mit der CSV-Datei ab."
2. Der Agent parst das Muster `<RAUM>HKVE<FAKTOR>SON-<SERIENNUMMER>-08` (zusammenhängend,
   ohne Leerzeichen — so wie beim Kopieren aus der Webansicht) und liefert eine
   Verifizierungstabelle: NE | Raum | Geräte-Nr | Kd-Faktor.
3. **Ergebnis manuell prüfen:** Anzahl der Geräte mit der Referenztabelle (Abschnitt 4)
   abgleichen. Fehlende oder unplausible Faktoren (z. B. < 0,3 oder > 3,0) sofort klären.

> **Hinweis:** Ein Hilfsskript wäre denkbar, müsste aber das tatsächliche Kopierformat
> der jeweiligen Portal-Version kennen. Da sich dieses ändern kann, ist manuelle Prüfung
> in jedem Fall erforderlich.

### Schritt 4 — CSV mit Kd-Faktor anreichern (manuell / KI-gestützt)

Es existiert **kein fertiges Skript** für diesen Schritt. Die Anreicherung erfolgt
durch den Copilot-Agenten auf Basis der in Schritt 3 ermittelten Faktoren.

**Vorgehen:**

1. Die geprüfte Faktor-Tabelle (Geräte-Nr → Kd-Faktor) dem Agenten übergeben mit:
   > „Schreibe das CSV `exports/Ablesewerte_YYYYMMDD_semikolon.csv` um:
   > füge eine Spalte `Kd-Faktor` nach Spalte `Typ` ein, trage für jede HKVE-Geräte-Nr
   > den entsprechenden Faktor ein, und speichere als `exports/Ablesewerte_YYYY_mit_Kd_Faktor.csv`."
2. Der Agent ergänzt außerdem eine Kontrollspalte `{jahr}-12-31-Kd-korr`
   (Jahresendwert × Kd-Faktor, nur HKVE-Zeilen) zur schnellen Plausibilitätsprüfung.
3. **Ausgabe prüfen:** Stimmt die Anzahl der Zeilen mit Faktor mit der Geräteanzahl überein?
   Haben alle HKVE-Zeilen einen Faktor ≠ `?`?

**Benennung der Ausgabedatei:**  
`exports/Ablesewerte_YYYY_mit_Kd_Faktor.csv`

### Schritt 5 — heizkosten_config.yaml anpassen

In `heizkosten_rechner/output/heizkosten_config.yaml` den Pfad aktualisieren:

```yaml
objekt:
  csv_datei: "Ablesewerte_YYYY_mit_Kd_Faktor.csv"
```

Das Skript `heizkosten_calc.py` liest die `Kd-Faktor`-Spalte automatisch aus dem CSV
und multipliziert sie auf jeden HKVE-Rohwert an. Geräte ohne Faktor (Spalte fehlt oder `?`)
werden mit Faktor **1,0** behandelt (keine Korrektur, Warnung im Log).

---

## 4. Gerätestammdaten 2025 (Referenztabelle)

Diese Tabelle ist der Stand per 01.01.2025. Bei Gerätewechsel muss die Tabelle aktualisiert werden.

| NE | Lage        | Raum | Geräte-Nr          | Kd-Faktor 2025 | Kd-Faktor 2024¹ |
|----|-------------|------|--------------------|:--------------:|:---------------:|
| 1  | EG links    | KI   | SON-29728199-08    | 1,582          | 0,674           |
| 1  | EG links    | SZ   | SON-29728198-08    | 1,582          | 1,167           |
| 1  | EG links    | WZ   | SON-29728197-08    | 1,297          | 1,297           |
| 1  | EG links    | WZ   | SON-29728196-08    | 1,297          | 1,297           |
| 1  | EG links    | KÜ   | SON-29728195-08    | 1,167          | 1,582           |
| 1  | EG links    | BAD  | SON-29728204-08    | 0,820          | 1,582           |
| 2  | EG rechts   | BAD  | SON-29728206-08    | 0,674          | —               |
| 2  | EG rechts   | KÜ   | SON-29728205-08    | 1,167          | —               |
| 2  | EG rechts   | WZ   | SON-29728210-08    | 1,297          | —               |
| 2  | EG rechts   | WZ   | SON-29728203-08    | 1,297          | —               |
| 2  | EG rechts   | SZ   | SON-29728202-08    | 1,582          | —               |
| 2  | EG rechts   | KI   | SON-29728201-08    | 1,582          | —               |
| 3  | 1.OG links  | KI   | SON-29728200-08    | 1,297          | —               |
| 3  | 1.OG links  | SZ   | SON-29728207-08    | 1,297          | —               |
| 3  | 1.OG links  | WZ   | SON-29728211-08    | 1,582          | —               |
| 3  | 1.OG links  | WZ   | SON-29728208-08    | 1,582          | —               |
| 3  | 1.OG links  | KÜ   | SON-29728209-08    | 1,167          | —               |
| 3  | 1.OG links  | BAD  | SON-29728212-08    | 0,550          | —               |
| 4  | 1.OG rechts | BAD  | SON-29728214-08    | 0,537          | —               |
| 4  | 1.OG rechts | KÜ   | SON-29728213-08    | 1,167          | —               |
| 4  | 1.OG rechts | WZ   | SON-29728215-08    | 1,297          | —               |
| 4  | 1.OG rechts | WZ   | SON-29728216-08    | 1,297          | —               |
| 4  | 1.OG rechts | SZ   | SON-29728220-08    | 1,582          | —               |
| 4  | 1.OG rechts | KI   | SON-29728217-08    | 1,582          | —               |
| 5  | 2.OG links  | KI   | SON-29728218-08    | 1,582          | —               |
| 5  | 2.OG links  | SZ   | SON-29728219-08    | 1,582          | —               |
| 5  | 2.OG links  | WZ   | SON-29728222-08    | 1,297          | —               |
| 5  | 2.OG links  | WZ   | SON-29728221-08    | 1,297          | —               |
| 5  | 2.OG links  | KÜ   | SON-29728223-08    | 1,167          | —               |
| 5  | 2.OG links  | BAD  | SON-29728224-08    | 0,550          | —               |
| 6  | 2.OG rechts | BAD  | SON-29728230-08    | 0,550          | —               |
| 6  | 2.OG rechts | KÜ   | SON-29728231-08    | 1,167          | —               |
| 6  | 2.OG rechts | WZ   | SON-29728232-08    | 1,297          | —               |
| 6  | 2.OG rechts | WZ   | SON-29728233-08    | 1,582          | —               |
| 6  | 2.OG rechts | SZ   | SON-29728234-08    | 1,582          | —               |
| 6  | 2.OG rechts | KI   | SON-29728225-08    | 1,297          | —               |
| 7  | DG links    | WZ   | SON-33412366-08    | 2,237          | —               |
| 7  | DG links    | KÜ   | SON-33412367-08    | 1,582          | —               |
| 7  | DG links    | BAD  | SON-33412368-08    | 0,778          | —               |
| 8  | DG rechts   | BAD  | SON-29728235-08    | 0,778          | —               |
| 8  | DG rechts   | KÜ   | SON-29728236-08    | 1,582          | —               |
| 8  | DG rechts   | WZ   | SON-29728237-08    | 1,265          | —               |
| 8  | DG rechts   | WZ   | SON-29728238-08    | 1,265          | —               |
| 8  | DG rechts   | SZ   | SON-29728239-08    | 1,265          | —               |
| 8  | DG rechts   | KI   | SON-29728244-08    | 1,265          | —               |

¹ Kd 2024 nur für NE1 bekannt (restliche NEs nicht abgerufen). Für die Abrechnung 2024
  sind die fehlenden Faktoren aus dem Portal nachzutragen (analog Schritt 2).

**Besonderheit NE 7 (Alexander Otto):** Alte Geräte wurden am 04.11.2025 ausgebaut und durch
neue Geräte der Serie `SON-334xxxxx` ersetzt. Die alten Geräte hatten `[FS*]`-Fehlermarken
in 2024 → für die Abrechnung 2024 wurde eine Schätzung nach § 9a HeizkostenV verwendet.

---

## 5. Implementierung in heizkosten_calc.py

Der `CsvData`-Reader in `heizkosten_calc.py` liest die Spalte `Kd-Faktor` automatisch:

```python
# In CsvData._load():
kd_raw = row.get("Kd-Faktor", "").strip()
kd_faktor = float(kd_raw) if kd_raw and kd_raw != "?" else 1.0
self._meta[key]["kd_faktor"] = kd_faktor

# In device_consumption():
if is_hkve:
    kd = csv.get_kd_faktor(unit_nr, geraet_nr)
    return raw_consumption * kd
```

**Rückwärtskompatibilität:** CSV-Dateien ohne `Kd-Faktor`-Spalte werden mit Faktor 1,0
verarbeitet. Es erscheint keine Fehlermeldung; die Werte sind dann unkorriert (wie vor 2026).

---

## 6. Ausgabe in YAML und PDF

### 6.1 YAML-Ausgabe (heizkosten_ergebnis.yaml)

Pro Mieter/Periode werden die HKVE-Gerätedaten als Liste ausgegeben:

```yaml
hkve_geraete:
  - raum: Küche
    geraet_nr: SON-29728205-08
    ablese_start: 0.0
    ablese_ende: 215.0
    kd_faktor: 1.167
    verbrauch_hke: 250.91    # = 215.0 × 1.167
  - raum: Wohnzimmer
    ...
hkve_einheiten: 1988.70     # Summe aller verbrauch_hke
```

### 6.2 PDF-Ausgabe (Ablesewerte-Tabelle)

Die HKVE-Tabelle in Seite 1 der Abrechnung enthält folgende Spalten:

| Raum | Geräte-Nr. | Typ | Ablesung Anfang | Ablesung Ende | Kd-Faktor | Verbrauch (HKE) |
|------|-----------|-----|:--------------:|:-------------:|:---------:|:---------------:|
| Küche | SON-29728205-08 | HKVE | 0,00 | 215,00 | 1,167 | 250,91 |
| Wohnzimmer | … | … | … | … | … | … |
| **Summe** | | | | | | **1.988,70** |

Die Spalte `Verbrauch (HKE)` zeigt den **Kd-korrigierten** Wert (= Stand Ende × Kd-Faktor).
Der Rohwert (Stand Ende) ist weiterhin ablesbar.

---

## 7. Checkliste für die nächste Abrechnung (2026)

- [ ] CSV ohne Faktor aus Thermomess-Portal exportieren → `exports/Ablesewerte_*_semikolon.csv`
- [ ] Faktor-Rohtext aus Webansicht kopieren → `exports/kd_faktoren_rohtext_2026.txt`
- [ ] Rohtext dem Copilot-Agenten vorlegen → Faktor-Tabelle ableiten und gegen Abschnitt 4 prüfen
- [ ] Agenten das CSV anreichern lassen → `exports/Ablesewerte_2026_mit_Kd_Faktor.csv` manuell prüfen
- [ ] `heizkosten_config.yaml` → `csv_datei` aktualisieren
- [ ] `python3 heizkosten_calc.py` ausführen → `output/heizkosten_ergebnis.yaml` prüfen
- [ ] `python3 heizkosten_pdf.py` ausführen → PDFs in `output/` prüfen
- [ ] Bei Gerätewechsel: Tabelle in Abschnitt 4 dieser Spec aktualisieren
