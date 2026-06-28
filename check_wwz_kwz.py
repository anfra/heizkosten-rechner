import csv

CSV = "Ablesewerte_20260622-221802_semikolon.csv"
TYPES = ("WWZ", "KWZ", "FAM (WWZ)")
DATE = "2025-12-31"

totals = {t: 0.0 for t in TYPES}
rows_by_unit = {}

with open(CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        if row is None or row.get("Nutzeinheit") is None:
            continue
        typ     = (row.get("Typ") or "").strip()
        unit    = (row.get("Nutzeinheit") or "").strip()
        ausbau  = (row.get("Ausbau") or "").strip()
        geraet  = (row.get("Geräte-Nr") or "").strip()
        raum    = (row.get("Raum") or "").strip()
        val_raw = (row.get(DATE) or "").strip()

        if typ not in TYPES:
            continue
        if ausbau:
            continue
        if not val_raw or val_raw in ("[FS*]",):
            print(f"  !! NE {unit:2s}  {typ:9s}  {geraet:25s}  -> KEIN WERT")
            continue

        val = float(val_raw)
        totals[typ] += val
        rows_by_unit.setdefault(unit, []).append((typ, raum, geraet, val))

print(f"\nWerte {DATE} nach Einheit (WWZ + KWZ):")
print(f"{'NE':>4}  {'Typ':9}  {'Raum':6}  {'Geraete-Nr':25}  {'Wert':>10}")
print("-" * 65)
grand = 0.0
for unit in sorted(rows_by_unit, key=lambda x: int(x)):
    unit_sum = 0.0
    for typ, raum, geraet, val in sorted(rows_by_unit[unit]):
        print(f"  {unit:2s}   {typ:9s}  {raum:6s}  {geraet:25s}  {val:10.3f}")
        unit_sum += val
        grand += val
    print(f"       Summe NE {unit:2s}:                                   {unit_sum:10.3f}")
    print()

print("=" * 65)
print(f"  Gesamtsumme WWZ+KWZ:   {grand:10.3f} m3")
print(f"  davon WWZ:             {totals['WWZ']:10.3f} m3")
print(f"  davon FAM (WWZ):       {totals['FAM (WWZ)']:10.3f} m3")
print(f"  davon KWZ:             {totals['KWZ']:10.3f} m3")
print(f"  WWZ gesamt (incl.FAM): {totals['WWZ']+totals['FAM (WWZ)']:10.3f} m3")
