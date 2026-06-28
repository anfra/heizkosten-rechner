# immocloud Playwright Automation – Erkenntnisse

## Login
- URL: https://app.immocloud.de/login
- E-Mail-Feld: `input[type='email']` (id=input-1)
- Passwort-Feld: `input[type='password']` (id=input-2)
- Login-Button: `button[name='Login']` (exakt: "Login")
- Nach Login: 2FA per E-Mail-Code → manuell eingeben, 180s Timeout

## Zähler anlegen
- URL: https://app.immocloud.de/meters/add
- "Neuen Zähler anlegen" Button → navigiert zu /meters/add
- Nach Anlegen: URL wird zu /meters/{meter-id}

### Formular-Felder
- **Objekt / Einheit**: PrimeVue AutoComplete → `.p-autocomplete input`
- **Zählernummer**: `get_by_label("Zählernummer")`
- **Zählertyp**: PrimeVue Select → label `for`-Attribut → trigger klicken → listbox wartet
- **Maßeinheit**: PrimeVue Select → zweites Dropdown
- **Zählername**: `get_by_label("Zählername")`
- **Lage**: `get_by_label("Lage des Zählers im Gebäude")`
- **Versorger**: `get_by_label("Versorger")`
- Speichern: `button name="Zähler anlegen"` (exact=True)

### Zählertyp-Optionen (bestätigt)
`['Strom', 'Kaltwasser', 'Warmwasser', 'Wasser (Gesamt)', 'Gas', 'Heizung', 'Fernwärme', 'Sonstiges']`

### CSV → immocloud Mapping
| CSV Typ  | immocloud Typ | Maßeinheit |
|----------|--------------|-----------|
| HKVE     | Heizung      | kWh       |
| WWZ      | Warmwasser   | m³        |
| KWZ      | Kaltwasser   | m³        |
| WMZ      | Fernwärme    | MWh (?)   |

### PrimeVue Dropdown-Klick (kritisch!)
- `aria-label="[object Object]"` → `get_by_role("option", name=...)` funktioniert NICHT
- Korrekt: Trigger klicken → `.p-select-overlay` warten → `.p-select-option` mit `has_text` klicken
- `page.locator(".p-select-option", has_text="Heizung").first.click()`

## Zählerstand eintragen
- URL: https://app.immocloud.de/meters/{meter-id}/readings/add
- Datum-Format: TT.MM.JJJJ
- Jahresgesamtwert: Startstand 01.01.2025 = 0, Endstand 31.12.2025 = Wert aus CSV

## Versorger
- "Meißner Stadtwerke Gmbh"
