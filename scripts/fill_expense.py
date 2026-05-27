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
      personalnummer: "6568"
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
    # Indices 10+ are per-day blocks — add as the mapping gets validated.
}


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
