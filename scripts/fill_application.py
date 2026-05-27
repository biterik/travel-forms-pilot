#!/usr/bin/env python3
"""Fill the MPIE Dienstreiseantrag (with optional A1) in one shot.

Usage:
    python fill_application.py --config trip_inputs.yaml [--output-dir 2_Application/]

The config YAML has this shape:

    # Optional — defaults to travel-forms-pilot/templates/Dienstreiseantrag_Mitarbeitende_mit_A1.docx
    template: ../../templates/Dienstreiseantrag_Mitarbeitende_mit_A1.docx

    output_basename: 20260906_Cargese_Dienstreiseantrag

    # How to trim the 7-page template:
    #   a1     — application + A1 page (EU trips)
    #   inland — single-page application only (domestic German trips)
    #   none   — keep all 7 pages
    trim: a1

    # FORMTEXT field values, keyed by 0-based index. See docs/formular_mechanik.md
    # for the index → meaning table. Missing entries / null = leave the field blank.
    fields:
      0: Bitzek
      1: Erik
      2: CM
      3: W0405001
      4: "6568"
      6: "MecaNano Summer School, COST CA21121"
      7: "Cargèse, Frankreich"
      8: "01.09.2026"
      9: "06.09.2026"
      11: "MecaNano (COST CA21121) — Unterkunft & Verpflegung"
      21: "Miles & More"
      22: "Düsseldorf, 26.05.2026"
      26: Bitzek
      27: Erik
      28: "6568"
      29: "01.09.2026"
      30: "06.09.2026"
      31: "Institut d'Études Scientifiques de Cargèse"
      32: "Menasina, 20130 Cargèse"
      33: Frankreich

    # 0-based indices of checkboxes to mark with ☒. Cargèse profile = {0,1,6,11,19}.
    checkboxes: [0, 1, 6, 11, 19]

Two outputs land in --output-dir:
    <output_basename>.docx
    <output_basename>.pdf   (only if LibreOffice is installed)
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

# Allow `python fill_application.py` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _docx_form import DocxForm  # noqa: E402

DEFAULT_TEMPLATE = (Path(__file__).resolve().parent.parent
                    / 'templates' / 'Dienstreiseantrag_Mitarbeitende_mit_A1.docx')


def normalize_field_keys(d):
    """YAML keys may parse as strings (e.g. '0'); coerce to int."""
    out = {}
    for k, v in (d or {}).items():
        try:
            out[int(k)] = v
        except (TypeError, ValueError):
            raise SystemExit(f"fields key {k!r} is not an integer index")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True,
                    help='YAML file with fields/checkboxes/output_basename/trim.')
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

        fields = normalize_field_keys(cfg.get('fields'))
        # Sanity-check indices
        bad = [i for i in fields if i < 0 or i >= n_fields]
        if bad:
            sys.exit(f"fields indices out of range (0..{n_fields - 1}): {bad}")
        form.fill_fields(fields)
        print(f"Filled {len([v for v in fields.values() if v not in (None, '')])} "
              f"FORMTEXT fields.")

        cbx = list(cfg.get('checkboxes') or [])
        bad = [i for i in cbx if i < 0 or i >= n_boxes]
        if bad:
            sys.exit(f"checkbox indices out of range (0..{n_boxes - 1}): {bad}")
        form.toggle_checkboxes(cbx)
        if cbx:
            print(f"Checked boxes: {sorted(cbx)}")

        trim = cfg.get('trim', 'a1')
        if trim == 'a1':
            form.trim_application_with_a1()
            print("Trimmed to application + A1.")
        elif trim == 'inland':
            form.trim_inland_single_page()
            print("Trimmed to inland single page.")
        elif trim == 'none':
            print("No trim applied.")
        else:
            sys.exit(f"Unknown trim mode: {trim!r}. Use a1 | inland | none.")

        form.save_docx(docx_path)
        print(f"DOCX written: {docx_path}")

        if args.no_pdf:
            return

        if form.to_pdf(docx_path, pdf_path):
            print(f"PDF written:  {pdf_path}")
        else:
            print("PDF conversion skipped — LibreOffice (soffice) not found.",
                  file=sys.stderr)
            print("Install LibreOffice or convert the DOCX manually.",
                  file=sys.stderr)


if __name__ == '__main__':
    main()
