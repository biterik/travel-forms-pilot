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

140 FORMTEXT fields, 24 checkboxes. **Mapping recovered 18 Aug 2026** by diffing a
filled report (`20260522_FAU-Erlangen`) against the blank template and confirming the
stride against the label context of all 140 fields.

### Header (indices 0–8)

| Idx | Field | Alias |
|---:|---|---|
| 0 | Name | `name` |
| 1 | Personal-Nr. | `personalnummer` |
| 2 | Reiseziel | `reiseziel` |
| 3 | Pauschalerstattung € | `pauschal_erstattung_eur` |
| 4 | Reisezweck | `reisezweck` |
| 5 | Kostenstelle | `kostenstelle` |
| 6 | Wohnort | `wohnort` |
| 7 | Reise genehmigt am | `reise_genehmigt_am` |
| 8 | … von | `reise_von` |

### Per-day block — SIX rows, stride 11, first row at index 9

Row *n* (0-based) starts at `9 + 11*n` → **9, 20, 31, 42, 53, 64**.

| Offset | Field | Alias (row 1) |
|---:|---|---|
| +0 | Datum | `tag1_datum` |
| +1 | Abfahrt | `tag1_abfahrt` |
| +2 | An-/Rückkunft | `tag1_rueckkunft` |
| +3 | Beginn Dienstgeschäft | `tag1_beginn_dienstgeschaeft` |
| +4 | Ende Dienstgeschäft | `tag1_ende_dienstgeschaeft` |
| +5 | Bemerkungen (upper line, by the M:/A: boxes) | `tag1_bemerkung` |
| +6 | Frühstück — Inland € | `tag1_fruehstueck_inland` |
| +7 | Frühstück — Ausland € | `tag1_fruehstueck_ausland` |
| +8 | Bemerkungen (lower line, by the F: box) | `tag1_bemerkung2` |
| +9 | Übernachtung — Inland € | `tag1_uebernachtung_inland` |
| +10 | Übernachtung — Ausland € | `tag1_uebernachtung_ausland` |

Aliases `tag1_…` … `tag6_…` are generated automatically; `day_field(row, key)` gives
the raw index.

### Summary block

| Idx | Field | Alias |
|---:|---|---|
| 75/76 | Summe 1 Frühstück Inland / Ausland | `summe1_fruehstueck_inland` / `…_ausland` |
| 77/78 | Summe 2 Übernachtung Inland / Ausland | `summe2_uebernachtung_inland` / `…_ausland` |
| 79/80/81 | Privat-KFZ: km / **Inland €** / **Ausland €** | `pkw_km` / `pkw_inland` / `pkw_ausland` |
| 83–100 | Fahrtkosten rows (4×), *only if the employee paid* | raw indices |
| 101/102 | Summe 3: Fahrtkosten — Inland / Ausland | `summe3_fahrtkosten` / `…_ausland` |
| 104–118 | Sonstige Ausgaben lt. Beleg (4 rows) | raw indices |
| 119 | Summe 4 | `summe4_sonstige` |
| 121 | Summe 5 | `summe5` |
| 123 | Erstattungsbetrag durch Dritte (Feld 6) | `erstattung_dritte_eur` |
| 125 | Auszahlungsbetrag (Summe 7) | `auszahlungsbetrag` |
| **126** | **"vom MPI bezahlt" free text (Feld 8)** | `vom_mpi_bezahlt_text` |
| **127** | **…€** | `vom_mpi_bezahlt_eur` |
| 131 | Vorschuss erhalten € | `vorschuss_eur` |
| 134 | Gesamtreisekosten | `gesamtreisekosten` |
| 135 | Datum (Unterschrift Reisender) | `datum_unterschrift` |
| 136 | Datum (Prüfung — leave blank) | `datum_pruefung` |

**The distinction that matters:** *Fahrtkosten* (Summe 3) and *Sonstige Ausgaben*
(Summe 4) are explicitly "sofern von Mitarbeitern bezahlt" — only out-of-pocket
spend. A ticket paid on the **central company credit card / AirPlus** does **not**
belong there; it goes into **Feld 8 (126/127), "vom MPI bezahlt"**, named
explicitly. Putting it in Summe 3 would claim a reimbursement Erik never paid for.

### Two kinds of `€` on this form — only one is off limits

Erik, 18.8.2026, confirmed the split:

- **`Betrag €` — `Inland` / `Ausland`, the boxes on the far right.** NEVER ours.
  The Reisekostenstelle computes and enters every figure there.
- **The `€` on the writing line to the LEFT**, on *vom MPI bezahlt (bitte
  benennen)*, *Vorschuss erhalten*, *Erstattungsbetrag durch Dritte*, the four
  *Fahrtkosten* rows and the four *Sonstige Ausgaben lt. Beleg* rows. **These are
  ours to fill.** For out-of-pocket spend the instruction is *"Description + €
  on the left line"* — name the expense and give the amount, so they can check it
  against the receipt.

### The `Betrag €` columns are OFF LIMITS

In every table on this form the **last two cells of a row are the Inland and
Ausland money columns**, and those are the Reisekostenstelle's to fill — never
ours. `fill_expense.py` enforces it with `RESERVED_BETRAG_FIELDS` (58 indices)
and exits with an error if a config targets one; `--allow-betrag` overrides only
on Erik's explicit instruction.

Left-side fields that ARE ours, and are easy to confuse with money columns:
`79` (Privat-KFZ **km**) and `126`/`127` (the "vom MPI bezahlt" description and
its € — these sit left of the money columns; Erik filled 127 himself on the
signed 20260522 report).

### Gotcha found on first real use (18 Aug 2026)

In the Privat-KFZ row the printed `€` glyph is **static text**, not a field. The
two FORMTEXT fields after `km:` are the **Inland** and **Ausland** money columns —
so `80` is Inland and `81` is Ausland, *not* "amount" and "Inland". Filling both
on a domestic trip puts a euro figure in the Ausland column. Same shape for
Summe 3 (101 = Inland, 102 = Ausland).

**Rendering the PDF once is justified the first time a newly recovered index is
used on a money field** — this is the exception to "don't re-inspect outputs",
which assumes an already-validated mapping.

### Checkbox map (24 literal ☐ glyphs, 0-based)

| Idx | Checkbox |
|---:|---|
| 0 | Verbindung der Reise mit Urlaub |
| 1–18 | per-day meals: day *n* (0-based) → M = 1+3n, A = 2+3n, F = 3+3n |
| 19 | bei Auslandsreisen: Mittagsverpflegung in einer Kantine |
| 20 | an Mitarbeiter gezahlter Zuschussbetrag |
| 21 | Erstattungsbetrag durch Dritte |
| 22 | Vorschuss erhalten |
| 23 | auf Dienstreise erkrankt |

Helper: `meal_checkbox(row, 'M'|'A'|'F')`.

To extend the mapping further:

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
