# 70 — Closing a trip (check the administration's settlement letter)

The final step. The user drops the Reisestelle's settlement letter (the
"Reisekostenabrechnung / Festsetzung", often a `Bitzek_DR####_…_CM.pdf`) into the
trip folder. The pilot compares what was **paid** against what the user
**claimed**, explains any differences, and — if it's right — closes the trip.

## Trigger

The user says the money arrived / drops the settlement letter / asks to "close"
the trip, or "check the Abrechnung".

## Behavior

1. **Sort the letter** into `6_Followup/` (it's the proof of payment).
2. **Read both documents:**
   - the user's submitted **Reiseabrechnung** (in `5_Expense_Report/`), and
   - the administration's **settlement letter** (in `6_Followup/`).

   Extract the amounts from each — total reimbursed vs. total claimed, and the
   line items where possible (per-diems/Tagegeld, hotel, travel, incidentals,
   any deductions for meals provided). This is an **LLM reading task**, portable
   across any tool-using model — there is no deterministic parser, because letter
   layouts vary.
3. **Compare and explain the differences in plain language.** For each
   discrepancy say what changed and the likely reason, e.g.:
   - "Tagegeld reduced by €14 — lunch on day 2 was provided by the host, so the
     meal deduction (40 %) was applied."
   - "Hotel paid in full." / "Taxi receipt of €23 not reimbursed — possibly
     missing original."
   If the settlement letter is a flat scan with no text layer, say so and ask the
   user to read out the totals rather than guessing.
4. **Never invent figures.** Only state amounts actually found in the documents.
   The check is assistive — the user makes the final call on whether to accept or
   query the Reisestelle.
5. **Decision:**
   - **Differences the user wants to query** → leave the trip open, note the open
     point in `## 6. Follow-up`, and (if helpful) draft a short email to
     `travel@mpi-susmat.de`.
   - **Everything fine / user accepts** → set `milestones: erstattet: true` and
     `status: closed`; record the settled total and any accepted differences in
     `## 6. Follow-up` (and the trip number if it wasn't set yet).
6. **Bonus points reminder:** if not already done, ask about BahnBonus / Miles &
   More for this trip and record them (see `00_pilot.md`).
7. **Regenerate the dashboard** so the trip moves to "closed".

## Notes

- "Closed" requires this settlement proof on file — that's exactly what the
  dashboard and the status model mean by `closed`.
- The dashboard only lists closed trips from the **current year**, so older
  closed trips drop off automatically (run `dashboard.py --all-closed` to see all).
