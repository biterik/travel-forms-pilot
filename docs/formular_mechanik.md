# Form mechanics — Dienstreiseantrag & Reiseabrechnung

How the MPIE Word forms get filled programmatically. The canonical path is the **single-shot Python scripts**; XML editing by hand is only the fallback for cases the scripts don't yet cover.

---

## Recommended workflow

```bash
python travel-forms-pilot/scripts/fill_application.py \
    --config <trip-folder>/2_Application/inputs.yaml \
    --output-dir <trip-folder>/2_Application/
```

The config YAML has this shape (full example with explanations is at the top of `scripts/fill_application.py`):

```yaml
output_basename: 20260906_Cargese_Dienstreiseantrag
trim: a1            # a1 | inland | none
fields:
  0: Bitzek
  1: Erik
  # ... see "Antrag field index table" below
checkboxes: [0, 1, 6, 11, 19]
```

For the expense report, `scripts/fill_expense.py` takes the same shape (plus a `named:` block for the few aliased header fields).

Both scripts:
1. unpack the DOCX template,
2. fill FORMTEXT fields by 0-based index,
3. toggle ☐ → ☒ checkboxes by 0-based index,
4. trim pages (Antrag only),
5. repack the DOCX,
6. convert to PDF via LibreOffice (`soffice`).

If LibreOffice isn't installed, only the DOCX is produced and the script tells you to convert manually.

---

## Antrag — field index table (42 FORMTEXT fields)

Indices in the order they appear in `word/document.xml` as `<w:fldChar w:fldCharType="begin">`:

| Idx | Field |
|---:|---|
| 0  | Name |
| 1  | First name |
| 2  | Department |
| 3  | Cost center (trip financing) |
| 4  | Personnel number |
| 5  | Project number |
| 6  | Trip purpose |
| 7  | Country / city |
| 8  | Trip from |
| 9  | Trip until (incl.) |
| 10 | Co-travellers (always empty for Erik) |
| 11 | "… externally borne by:" — free text |
| 12 | Private trip from |
| 13 | Private trip until |
| 14 | Seminar fees (free text right of checkbox) |
| 15 | Hotel cost (free text right of checkbox) |
| 16 | Official vehicle — free text |
| 17 | Train — free text |
| 18 | Airplane — free text *(Erik: leave empty, only check the box)* |
| 19 | Rental car — free text |
| 20 | Justification for means of transport with \* |
| 21 | Bonus programme — which |
| 22 | "Düsseldorf, on …" |
| 23–25 | Processing notes (filled by Reisestelle, always blank from us) |
| 26 | **A1 page:** Name |
| 27 | A1: First name |
| 28 | A1: Personnel number |
| 29 | A1: from |
| 30 | A1: until (incl.) |
| 31 | A1: Name of host institution |
| 32 | A1: Address of host institution |
| 33 | A1: Country |
| 34–41 | A1: second destination section within the EU (always empty for Erik so far) |

## Antrag — checkbox index table (21 checkboxes)

`☐` is unchecked, `☒` is checked. Indices in order of appearance:

| Idx | Checkbox | Cargèse value |
|---:|---|---|
| 0  | "Costs are … externally borne" (outer) | ☒ |
| 1  | "… (partly) …" (inner) | ☒ |
| 2  | "No costs will be charged to the institute" | empty |
| 3  | "… combined with a private trip" | empty |
| 4  | Seminar fees | empty (invited → no fee) |
| 5  | Hotel cost | empty (host pays) |
| 6  | Per diem | ☒ |
| 7  | Official vehicle | empty |
| 8  | Train | empty |
| 9  | Higher transport class \* | empty |
| 10 | Sleeper car \* | empty |
| 11 | Airplane | ☒ |
| 12 | Rental car \* | empty |
| 13 | Private motor vehicle \* | empty |
| 14 | Car: official interest "generally recognized" | empty |
| 15 | Car: "to be recognized for this trip" | empty |
| 16 | Car: "without substantial official interest" | empty |
| 17 | Car: "to/from train station / airport" | empty |
| 18 | Car: "entire route" | empty |
| 19 | Bonus programme — yes | ☒ |
| 20 | Bonus programme — no | empty |

## Antrag — trim modes

The MPIE template is 8 pages; only the application (page 2) and A1 (page 3) get submitted.

- `trim: a1` — outputs application + A1 page (~2 PDF pages). Used for EU trips.
- `trim: inland` — outputs application only (~1 PDF page). Used for domestic German trips.
- `trim: none` — leaves all 8 pages intact (for debugging).

Internal recipe (implemented in `DocxForm.trim_application_with_a1` / `trim_inland_single_page`):

1. **Drop the index page.** Delete everything from `<w:body>` start through the first `<w:br w:type="page"/>` paragraph (inclusive).
2. **Replace the cost-trigger disclaimer paragraph** (the one starting with "Kostenauslösung …") with a minimal paragraph that only carries the page break to the A1 page. Otherwise the red disclaimer slides onto an empty half-page.
3. **Drop EU country list & helpers.** For `a1`, delete from the "Liste der EU-Länder …" paragraph through the body-level `<w:sectPr>`. For `inland`, delete from the disclaimer paragraph itself.
4. **Trim trailing empty paragraphs** before `<w:sectPr>` (otherwise they push an empty trailing page).
5. **Keep `<w:sectPr>`** — defines page size, margins, header, footer.

---

## Reiseabrechnung — field overview

140 FORMTEXT fields, 24 checkboxes. The structure is a small header followed by a long repeating per-day block (date, departure/arrival times, "Abwesenheit" hours, meal-received checkboxes, hotel/per-diem amounts) plus summary fields at the end.

Only a few header fields are aliased in `fill_expense.py` so far. The full mapping isn't documented yet — most fields stay empty for any given trip. To extend:

1. Unpack the template and inspect:
   ```bash
   unzip Reiseabrechnung_Vorlage.docx -d /tmp/expense_template
   python3 - <<'PY'
   import re
   xml = open('/tmp/expense_template/word/document.xml', encoding='utf-8').read()
   for i, m in enumerate(re.finditer(r'<w:fldChar w:fldCharType="begin"', xml)):
       texts = re.findall(r'<w:t[^>]*>([^<]+)</w:t>', xml[max(0, m.start()-1500):m.start()])
       print(f"{i:3d}: {' | '.join(texts[-5:])[-120:]!r}")
   PY
   ```
2. Add discovered names to `NAMED_FIELDS` in `scripts/fill_expense.py`.
3. Commit.

---

## Manual XML editing (fallback)

Use the scripts above first. If the script doesn't yet support what you need, the manual recipe is:

1. Copy a fresh template into the working directory.
2. Unzip it (`unzip template.docx -d unpacked/`).
3. Edit `unpacked/word/document.xml`: set FORMTEXT values, toggle checkboxes, trim pages.
4. **Fix the broken Windows template reference** before repacking — otherwise some validators choke. Two changes:
   - Remove the line `<w:attachedTemplate r:id="rId1"/>` from `unpacked/word/settings.xml`.
   - Replace `unpacked/word/_rels/settings.xml.rels` with an empty `<Relationships .../>` element.
5. Repack as a ZIP with the standard DOCX file order, save as `.docx`.
6. Convert to PDF: `soffice --headless --convert-to pdf --outdir <dir> <docx>`.

Both `DocxForm.save_docx` and `DocxForm.to_pdf` in `scripts/_docx_form.py` handle 4, 5, 6 internally.
