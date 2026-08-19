#!/usr/bin/env python3
"""Fill the MPIE Reiseabrechnung (travel expense report) in one shot.

Usage:
    python fill_expense.py --config expense_inputs.yaml [--output-dir 5_Expense_Report/]

The Reiseabrechnung template is large: **140 FORMTEXT fields** and **24
checkboxes**, mostly arranged as repeating per-day blocks. We deliberately
do NOT hardcode a "field name → index" mapping here: the mapping isn't fully
documented yet, and most fields stay empty for any given trip.

The config YAML uses raw 0-based indices, plus a few well-known aliases for
the header fields. Add more aliases to NAMED_FIELDS over time as the mapping
gets nailed down.

Config shape:

    # Optional override of the template path
    template: ../../templates/Reiseabrechnung_Vorlage.docx

    output_basename: 20260522_FAU_Reiseabrechnung

    # Header fields by alias (resolved against NAMED_FIELDS below).
    named:
      name: Bitzek
      personalnummer: "1234"
      reiseziel: "Erlangen, Deutschland"
      pauschal_erstattung_eur: ""
      reisezweck: "FAU Erlangen, AMMP-Vorlesung"
      kostenstelle: W0405001
      wohnort: Düsseldorf
      reise_genehmigt_am: ""

    # Free-form fields by raw 0-based index.
    fields:
      8: "22.05.2026"     # "von:"
      # ...

    # 0-based indices of checkboxes to mark ☒. Leave empty for none.
    checkboxes: []
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("Missing dependency: pip install pyyaml --break-system-packages\n")
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _docx_form import DocxForm  # noqa: E402

DEFAULT_TEMPLATE = (Path(__file__).resolve().parent.parent
                    / 'templates' / 'Reiseabrechnung_Vorlage.docx')

# Named aliases for header FORMTEXT fields. Indices come from inspecting the
# document.xml of the MPIE Reiseabrechnung template (May 2026). Extend as needed.
NAMED_FIELDS = {
    'name': 0,
    'personalnummer': 1,
    'reiseziel': 2,
    'pauschal_erstattung_eur': 3,
    'reisezweck': 4,
    'kostenstelle': 5,
    'wohnort': 6,
    'reise_genehmigt_am': 7,
    'reise_von': 8,
    # --- summary block ---
    'summe1_fruehstueck_inland': 75,
    'summe1_fruehstueck_ausland': 76,
    'summe2_uebernachtung_inland': 77,
    'summe2_uebernachtung_ausland': 78,
    'pkw_km': 79,
    'pkw_inland': 80,      # the '€' left of it is static text
    'pkw_ausland': 81,
    # --- Fahrtkosten rows ("sofern von Mitarbeitern bezahlt"), 4 rows ---
    # Each row: Bezeichnung + the € on the LEFT writing line. Both are ours.
    'fahrtkosten1_bezeichnung': 85,  'fahrtkosten1_eur': 86,
    'fahrtkosten2_bezeichnung': 89,  'fahrtkosten2_eur': 90,
    'fahrtkosten3_bezeichnung': 93,  'fahrtkosten3_eur': 94,
    'fahrtkosten4_bezeichnung': 97,  'fahrtkosten4_eur': 98,
    # --- Sonstige Ausgaben lt. Beleg, 4 rows ---
    'sonstige1_bezeichnung': 103, 'sonstige1_eur': 104,
    'sonstige2_bezeichnung': 107, 'sonstige2_eur': 108,
    'sonstige3_bezeichnung': 111, 'sonstige3_eur': 112,
    'sonstige4_bezeichnung': 115, 'sonstige4_eur': 116,
    'summe3_fahrtkosten': 101,        # Inland column
    'summe3_fahrtkosten_ausland': 102,
    'summe4_sonstige': 119,
    'summe5': 121,
    'erstattung_dritte_bezeichnung': 122,
    'erstattung_dritte_eur': 123,   # left-hand € line
    'auszahlungsbetrag': 125,
    'vom_mpi_bezahlt_text': 126,     # "Feld 8" — what the institute already paid
    'vom_mpi_bezahlt_eur': 127,
    'vorschuss_bezeichnung': 130,
    'vorschuss_eur': 131,           # left-hand € line
    'gesamtreisekosten': 134,
    'datum_unterschrift': 135,
    'datum_pruefung': 136,
}

# --- Per-day block ------------------------------------------------------
# The day table has SIX rows. Each row is a block of 11 consecutive FORMTEXT
# fields; the first row starts at index 9, so row n (0-based) starts at
# 9 + 11*n  ->  9, 20, 31, 42, 53, 64.
#
# Offsets within a row:
#   +0  Datum
#   +1  Abfahrt                       (departure from home/office)
#   +2  An-/Rückkunft                 (arrival back)
#   +3  Beginn Dienstgeschäft
#   +4  Ende Dienstgeschäft
#   +5  Bemerkungen (upper line, next to the M:/A: meal checkboxes)
#   +6  Betrag Frühstück   — Inland
#   +7  Betrag Frühstück   — Ausland
#   +8  Bemerkungen (lower line, next to the F: checkbox)
#   +9  Betrag Übernachtung — Inland
#   +10 Betrag Übernachtung — Ausland
#
# Recovered 18 Aug 2026 by diffing the filled 20260522_FAU-Erlangen report
# against the blank template, then confirming the stride against the label
# context of all 140 fields. Verified: 140 FORMTEXT fields, 24 checkboxes.
DAY_ROW_BASE = 9
DAY_ROW_STRIDE = 11
DAY_ROWS = 6
DAY_OFFSETS = {
    'datum': 0, 'abfahrt': 1, 'rueckkunft': 2,
    'beginn_dienstgeschaeft': 3, 'ende_dienstgeschaeft': 4,
    'bemerkung': 5,
    'fruehstueck_inland': 6, 'fruehstueck_ausland': 7,
    'bemerkung2': 8,
    'uebernachtung_inland': 9, 'uebernachtung_ausland': 10,
}


def day_field(row: int, key: str) -> int:
    """Index of `key` in day row `row` (0-based). See DAY_OFFSETS."""
    if not 0 <= row < DAY_ROWS:
        raise SystemExit(f"day row {row} out of range (0..{DAY_ROWS - 1})")
    if key not in DAY_OFFSETS:
        raise SystemExit(f"unknown day field {key!r}. Known: {sorted(DAY_OFFSETS)}")
    return DAY_ROW_BASE + DAY_ROW_STRIDE * row + DAY_OFFSETS[key]


for _r in range(DAY_ROWS):
    for _k in DAY_OFFSETS:
        NAMED_FIELDS[f'tag{_r + 1}_{_k}'] = day_field(_r, _k)

# --- Checkbox map (24 literal ☐ glyphs, 0-based, in document order) ----
# Recovered 18 Aug 2026 alongside the field map.
#   0        "Verbindung der Reise mit Urlaub"  (header, top right)
#   1..18    per-day meal boxes: day n (0-based) -> M = 1+3n, A = 2+3n, F = 3+3n
#   19       "bei Auslandsreisen: Mittagsverpflegung in einer Kantine"
#   20       "an Mitarbeiter gezahlter Zuschussbetrag"
#   21       "Erstattungsbetrag durch Dritte"
#   22       "Vorschuss erhalten"
#   23       "auf Dienstreise erkrankt"
CB_URLAUB = 0
CB_AUSLAND_KANTINE = 19
CB_ZUSCHUSS = 20
CB_DRITTE = 21
CB_VORSCHUSS = 22
CB_ERKRANKT = 23


# --- "Betrag €" columns — RESERVED FOR THE REISESTELLE -------------------
# HARD RULE (Erik, 18.8.2026): "never put yourself anything in the columns
# Betrag Euro, that is for the Dienstreisestelle to fill in. We just fill in
# the stuff on the left."
#
# We supply the FACTS on the left of the form — dates, times, km, Bemerkungen,
# what the institute already paid — and the Reisekostenstelle computes and
# enters every euro figure in the right-hand Inland/Ausland money columns.
# Writing our own numbers there pre-empts their calculation and, if we get a
# rate or a per-diem bracket wrong, turns an arithmetic slip into an incorrect
# claim over Erik's signature.
#
# In every table on this form the LAST TWO cells of a row are the Inland and
# Ausland money columns. Derived from the table structure, verified 18.8.2026.
RESERVED_BETRAG_FIELDS = frozenset({
    # per-day Frühstück (Inland, Ausland) and Übernachtung (Inland, Ausland)
    15, 16, 18, 19,   26, 27, 29, 30,   37, 38, 40, 41,
    48, 49, 51, 52,   59, 60, 62, 63,   70, 71, 73, 74,
    75, 76,           # Summe 1: Frühstück
    77, 78,           # Summe 2: Übernachtung
    80, 81,           # Privat-KFZ  (km in 79 is ours; the money is theirs)
    87, 88, 91, 92, 95, 96, 99, 100,    # Fahrtkosten rows
    101, 102,         # Summe 3: Fahrtkosten
    105, 106, 109, 110, 113, 114, 117, 118,   # Sonstige Ausgaben rows
    119, 120,         # Summe 4
    121,              # Summe 5
    124,              # Feld 6 — Erstattungsbetrag durch Dritte
    125,              # Auszahlungsbetrag (Summe 7)
    128, 129,         # Feld 8/9 money columns
    132, 133,         # Vorschuss money columns
    134,              # Gesamtreisekosten
})
# NOT reserved, deliberately: 79 (km), 126/127 ("vom MPI bezahlt" description
# and its € on the LEFT of the form — Erik fills that himself, cf. the signed
# 20260522 report), 122/123, 130/131.


def meal_checkbox(row: int, meal: str) -> int:
    """Checkbox index for a meal provided by a third party on day row `row`.

    meal: 'M' (Mittag), 'A' (Abendessen) or 'F' (Frühstück).
    """
    order = {'M': 1, 'A': 2, 'F': 3}
    if not 0 <= row < DAY_ROWS:
        raise SystemExit(f"day row {row} out of range (0..{DAY_ROWS - 1})")
    if meal not in order:
        raise SystemExit(f"meal must be one of M/A/F, got {meal!r}")
    return 3 * row + order[meal]



def merge_inputs(named: dict, fields: dict) -> dict:
    """Resolve `named:` aliases to indices and merge with `fields:`."""
    out = {}
    for k, v in (named or {}).items():
        if k not in NAMED_FIELDS:
            raise SystemExit(
                f"Unknown named field {k!r}. Known: {sorted(NAMED_FIELDS)}\n"
                "Add it to NAMED_FIELDS in fill_expense.py if the mapping is documented."
            )
        out[NAMED_FIELDS[k]] = v
    for k, v in (fields or {}).items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            raise SystemExit(f"fields key {k!r} is not an integer index")
        out[idx] = v
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True,
                    help='YAML file with named/fields/checkboxes/output_basename.')
    ap.add_argument('--output-dir', default='.',
                    help='Where the DOCX/PDF go. Default: cwd.')
    ap.add_argument('--no-pdf', action='store_true',
                    help='Skip the LibreOffice PDF conversion.')
    ap.add_argument('--allow-betrag', action='store_true',
                    help='Override the guard on the "Betrag €" columns. Those '
                         'belong to the Reisekostenstelle — only use this if '
                         'Erik has explicitly asked for a figure to be placed '
                         'there.')
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding='utf-8')) or {}
    template = Path(cfg.get('template') or DEFAULT_TEMPLATE)
    if not template.is_absolute():
        template = (Path(args.config).resolve().parent / template).resolve()

    if 'output_basename' not in cfg:
        sys.exit("Config must specify `output_basename`.")
    basename = cfg['output_basename']

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    docx_path = out_dir / f'{basename}.docx'
    pdf_path = out_dir / f'{basename}.pdf'

    with DocxForm(template) as form:
        n_fields = form.field_count()
        n_boxes = form.checkbox_count()
        print(f"Template: {template.name}  ({n_fields} FORMTEXT fields, "
              f"{n_boxes} checkboxes)")

        merged = merge_inputs(cfg.get('named'), cfg.get('fields'))
        bad = [i for i in merged if i < 0 or i >= n_fields]
        if bad:
            sys.exit(f"fields indices out of range (0..{n_fields - 1}): {bad}")
        offenders = sorted(i for i, v in merged.items()
                           if i in RESERVED_BETRAG_FIELDS
                           and v not in (None, ''))
        if offenders and not args.allow_betrag:
            names = {v: k for k, v in NAMED_FIELDS.items()}
            detail = ', '.join(f"{i} ({names.get(i, '?')}) = {merged[i]!r}"
                               for i in offenders)
            sys.exit(
                "Refusing to write to the 'Betrag \u20ac' columns: " + detail + "\n"
                "Those columns are filled in by the Reisekostenstelle, not by us.\n"
                "We supply the facts on the left (dates, times, km, Bemerkungen); "
                "they compute the money.\n"
                "If Erik has explicitly asked for a figure there, re-run with "
                "--allow-betrag."
            )
        form.fill_fields(merged)
        n_filled = len([v for v in merged.values() if v not in (None, '')])
        print(f"Filled {n_filled} FORMTEXT fields.")

        cbx = list(cfg.get('checkboxes') or [])
        bad = [i for i in cbx if i < 0 or i >= n_boxes]
        if bad:
            sys.exit(f"checkbox indices out of range (0..{n_boxes - 1}): {bad}")
        form.toggle_checkboxes(cbx)
        if cbx:
            print(f"Checked boxes: {sorted(cbx)}")

        # The Reiseabrechnung template has no superfluous pages to trim by
        # default — Erik submits the whole thing. If a future use needs trimming,
        # add a `trim:` knob here.

        form.save_docx(docx_path)
        print(f"DOCX written: {docx_path}")

        if args.no_pdf:
            return

        if form.to_pdf(docx_path, pdf_path):
            print(f"PDF written:  {pdf_path}")
        else:
            print("PDF conversion skipped — LibreOffice (soffice) not found.",
                  file=sys.stderr)


if __name__ == '__main__':
    main()
