#!/usr/bin/env python3
"""Back-fill an OLD trip folder into the Travel Forms Pilot convention.

Unlike `bootstrap_trip.py` (which prepares a *fresh* folder), this script is the
lenient "backlog" importer for trips that already happened. Given a single-trip
folder that already contains the signed application, the Reisestelle settlement
PDF, an expense report, etc., it:

  1. Scaffolds the canonical subfolders and a `trip.md` (like bootstrap).
  2. Recovers what it can WITHOUT asking:
       - trip number (DR....) from the settlement-PDF filename,
       - destination, purpose and travel dates from the signed application's
         front page (via `pdftotext -layout`),
       - dates / location / event from the folder name as a fallback.
  3. Infers a status from which artifacts are present:
       settlement PDF -> reimbursed
       expense report -> filed
       signed application + past end date -> completed
       signed application (future) / trip number -> approved
       otherwise -> planned
  4. Fills the `trip.md` YAML header with all of the above and marks it
     `backlog_imported: true`.
  5. Moves confidently-classified loose files into the right subfolder
     (application/A1 -> 2_Application, settlement -> 6_Followup, expense report
     -> 5_Expense_Report, invitations -> 1_Invitation, bookings/tickets ->
     3_Booking, invoices/receipts/photos -> receipts). Anything ambiguous is
     LEFT at the top level and reported, for a human (or the agent) to place.

Nothing is overwritten: a file is only moved if no same-named file already
sits in the target subfolder, and an existing `trip.md` is never clobbered
(use --force-trip-md to refill its header).

Safety: PREVIEW is the default — the script prints the gleaned facts (with where
each came from) and an explicit "missing / needs checking" list, and the exact
changes it would make, WITHOUT touching anything. Pass --confirm to actually
write trip.md and move files. Designed for single-trip folders; year-aggregator
folders (e.g. 2025_FAU holding many trips) are out of scope for this version.

Usage:
    python backlog_trip.py <trip-folder>             # preview facts + gaps only
    python backlog_trip.py <trip-folder> --confirm   # apply (write + sort files)
    python backlog_trip.py <trip-folder> --confirm --force-trip-md
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Reuse the folder-name parser + subfolder list + template path from bootstrap.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap_trip import parse_folder_name, SUBFOLDERS, DEFAULT_TEMPLATE  # noqa: E402


# ----------------------------------------------------------------------------- filename classification

def classify(name: str):
    """Return the target subfolder for a loose file, or None if ambiguous."""
    low = name.lower()
    if low in ("trip.md", ".ds_store"):
        return None
    # Expense report (check before generic "antrag"/invoice keywords).
    if "reiseabrechnung" in low or "abrechnung" in low:
        return "5_Expense_Report"
    # Reisestelle settlement confirmation (filename carries a DR number + name).
    # Note: DR is often preceded by "_" so a \b boundary fails — use a letter lookbehind.
    if re.search(r"(?<![a-z])dr\d{3,}", low) and "bitzek" in low:
        return "6_Followup"
    # Application + A1 certificate (application-specific tokens only — the bare
    # "signedEB" catch comes last so signed *non*-application forms don't land here).
    if ("dienstreiseantrag" in low or "antrag" in low
            or "a1-bescheinigung" in low or low.startswith("a1")
            or "_a1" in low or "-a1" in low):
        return "2_Application"
    # Invitations / programmes.
    if any(k in low for k in ("invitation", "einladung", "programme", "program", "invite")):
        return "1_Invitation"
    # Invoices / payment confirmations / claim forms / fee receipts.
    if any(k in low for k in ("invoice", "payment", "zahlung", "rechnung", "claim",
                              "receipt", "quittung", "beleg")):
        return "receipts"
    # Bookings / tickets.
    if any(k in low for k in ("flight", "ticket", "booking", "buchung", "bahn",
                              "db_", "train", "boarding", "hotel", "ride", "bolt")):
        return "3_Booking"
    # Receipt photos / scans.
    if low.endswith((".jpg", ".jpeg", ".png", ".heic", ".heif")):
        return "receipts"
    # Any other signed PDF — most likely an application variant. Catch last.
    if "signedeb" in low or "signdeb" in low:
        return "2_Application"
    return None


# ----------------------------------------------------------------------------- extraction

def norm_stem(name: str) -> str:
    """Filename stem, lowercased, with signed/version suffixes stripped.

    Lets us recognize that '<trip>.pdf' and '<trip>_signedEB.pdf' are the same
    application document, so the unsigned copy follows the signed one into
    2_Application instead of being left as 'ambiguous'.
    """
    s = Path(name).stem.lower()
    for suf in ("_signedeb", "-signedeb", "_signdeb", "-signdeb",
                "_signed", "-signed"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s.strip(" _-")


def parse_german_date(s: str):
    """Parse a German d.m.y(y) date into an ISO string, or None."""
    s = s.strip().rstrip(".")
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", s)
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    if y < 100:
        y += 2000
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def extract_app_fields(pdf: Path) -> dict:
    """Pull destination / purpose / dates / cost center from an application front page."""
    out = {}
    try:
        text = subprocess.run(
            ["pdftotext", "-layout", "-f", "1", "-l", "1", str(pdf), "-"],
            capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return out

    m = re.search(r"Reisezweck:\s*(.+)", text)
    if m:
        out["reisezweck"] = m.group(1).strip()
    m = re.search(r"Reiseland/Ort:\s*(.+)", text)
    if m:
        out["ziel"] = m.group(1).strip()
    m = re.search(r"Von:\s*([\d.]+)\s*bis einschl\.?:\s*([\d.]+)", text)
    if m:
        out["datum_start"] = parse_german_date(m.group(1))
        out["datum_ende"] = parse_german_date(m.group(2))
    m = re.search(r"Kostenstelle\s+([A-Za-z0-9]+)", text)
    if m:
        out["kostenstelle"] = m.group(1).strip()
    return out


def pick_app_fields(files) -> dict:
    """Extract from the first PDF that yields usable application text.

    Tries signed application first, then anything named like an application,
    then other PDFs — skipping the obvious non-applications to the end. This
    survives signed copies that are flattened scans with no text layer.
    """
    def rank(p: Path) -> int:
        low = p.name.lower()
        if "signedeb" in low or "signdeb" in low:
            return 0
        if "dienstreiseantrag" in low or "antrag" in low:
            return 1
        if ("a1" in low or "invoice" in low or "abrechnung" in low
                or re.search(r"(?<![a-z])dr\d{3,}", low)):
            return 3   # unlikely to be the application — try last
        return 2

    pdfs = sorted((p for p in files if p.suffix.lower() == ".pdf"),
                  key=lambda p: (rank(p), p.name))
    for p in pdfs:
        f = extract_app_fields(p)
        if f.get("ziel") or f.get("datum_start") or f.get("reisezweck"):
            return f
    return {}


def find_trip_number(names) -> str | None:
    for n in names:
        m = re.search(r"(?<![A-Za-z])(DR\d{3,})", n, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None


# ----------------------------------------------------------------------------- trip.md header writing

def set_field(content: str, key: str, value, quote: bool = False) -> str:
    """Replace `key: <value>` in the YAML header, preserving indentation + comment.

    Works for both top-level keys and indented (nested) keys like milestones.
    """
    if value in (None, ""):
        return content
    val = '"' + str(value).replace('"', '\\"') + '"' if quote else str(value)
    pattern = rf"^(\s*)({re.escape(key)}:)[^\n#]*(\s+#.*)?$"
    new, n = re.subn(
        pattern,
        lambda mt: f"{mt.group(1)}{mt.group(2)} {val}{mt.group(3) or ''}",
        content, count=1, flags=re.MULTILINE)
    return new if n else content


def insert_after_key(content: str, key: str, lines) -> str:
    pattern = rf"^({re.escape(key)}:[^\n]*\n)"
    add = "".join(l + "\n" for l in lines)
    new, n = re.subn(pattern, lambda mt: mt.group(1) + add, content,
                     count=1, flags=re.MULTILINE)
    return new if n else content


def plus_three_months(end_iso) -> str | None:
    """Return end date + 3 months (the Abrechnungsfrist), clamped to month length."""
    try:
        d = dt.date.fromisoformat(str(end_iso))
    except (ValueError, TypeError):
        return None
    mo = d.month + 3
    yr = d.year + (mo - 1) // 12
    mo = (mo - 1) % 12 + 1
    last = [31, 29 if yr % 4 == 0 and (yr % 100 or yr % 400 == 0) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
    return dt.date(yr, mo, min(d.day, last)).isoformat()


def resolve_values(folder_name: str, fields: dict) -> dict:
    """Merge application-extracted fields with folder-name fallbacks.

    Also records, per field, WHERE each value came from ('application',
    'folder name', '= start date', 'default', or None) so the caller can show
    the user what was gleaned vs. guessed vs. missing.
    """
    iso_date, location, event = parse_folder_name(folder_name)
    ziel = fields.get("ziel") or location
    start = fields.get("datum_start") or iso_date
    end = fields.get("datum_ende") or start
    src = {
        "ziel": "application" if fields.get("ziel") else ("folder name" if location else None),
        "event": "folder name" if event else None,
        "datum_start": "application" if fields.get("datum_start")
        else ("folder name" if iso_date else None),
        "datum_ende": "application" if fields.get("datum_ende")
        else ("= start date" if start else None),
        "kostenstelle": "application" if fields.get("kostenstelle") else "default",
        "reisezweck": "application" if fields.get("reisezweck") else None,
    }
    return {
        "ziel": ziel, "event": event,
        "datum_start": start, "datum_ende": end,
        "abrechnungsfrist": plus_three_months(end),
        "kostenstelle": fields.get("kostenstelle"),
        "reisezweck": fields.get("reisezweck"),
        "sources": src,
    }


def build_trip_md(template: str, *, folder_name: str, resolved: dict, status: str,
                  reisenummer, milestones: dict, today: dt.date) -> str:
    c = template
    c = set_field(c, "status", status)
    for k, v in milestones.items():
        if v is not None:
            c = set_field(c, k, "true" if v else "false")
    c = set_field(c, "ziel", resolved["ziel"], quote=True)
    c = set_field(c, "event", resolved["event"], quote=True)
    c = set_field(c, "datum_start", resolved["datum_start"])
    c = set_field(c, "datum_ende", resolved["datum_ende"])
    c = set_field(c, "abrechnungsfrist", resolved["abrechnungsfrist"])
    c = set_field(c, "reisenummer", reisenummer, quote=True)
    if resolved.get("kostenstelle"):
        c = set_field(c, "kostenstelle", resolved["kostenstelle"])
    c = set_field(c, "reisezweck_kurz", resolved.get("reisezweck"), quote=True)
    # Mark provenance right after the reisenummer line.
    c = insert_after_key(c, "reisenummer",
                         [f"backlog_imported: true   # imported from existing files on {today.isoformat()}"])
    # Replace the title placeholder.
    title = resolved["event"] or resolved["ziel"] or folder_name
    c = c.replace("# {Trip title}", f"# {title}", 1)
    return c


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trip_folder", help="Path to a single-trip folder.")
    ap.add_argument("--confirm", action="store_true",
                    help="Actually write trip.md and move files. Without it, the "
                         "script only PREVIEWS the gleaned facts and planned changes.")
    ap.add_argument("--force-trip-md", action="store_true",
                    help="Re-fill the YAML header even if trip.md already exists.")
    ap.add_argument("--status", default=None,
                    help="Override the inferred status (e.g. completed) after reviewing the preview.")
    ap.add_argument("--event", default=None,
                    help="Override / set the event name (useful when the folder name can't be parsed).")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE),
                    help="Path to trip.md.tmpl (default: bundled template).")
    args = ap.parse_args()

    trip = Path(args.trip_folder).resolve()
    if not trip.is_dir():
        sys.exit(f"Not a directory: {trip}")
    write = args.confirm
    today = dt.date.today()

    # Loose files (top level only) are what we MOVE.
    loose = sorted(p for p in trip.iterdir()
                   if p.is_file() and p.name not in ("trip.md", ".DS_Store"))
    # Detection scans the WHOLE folder (incl. already-sorted subfolders), so a
    # --force-trip-md re-run after files were moved still infers the right status.
    all_files = [p for p in trip.rglob("*")
                 if p.is_file() and p.name not in ("trip.md", ".DS_Store")]
    all_names = [p.name for p in all_files]

    # ---- detect artifacts / status
    has_settlement = any(classify(n) == "6_Followup" for n in all_names)
    has_expense = any(classify(n) == "5_Expense_Report" for n in all_names)
    has_signed_app = any(("signedeb" in n.lower() or "signdeb" in n.lower()
                          or "dienstreiseantrag" in n.lower()) for n in all_names)
    reisenummer = find_trip_number(all_names)

    # ---- pull data from the best readable application PDF, merge with folder name
    fields = pick_app_fields(all_files)
    rv = resolve_values(trip.name, fields)
    src = rv["sources"]
    end_for_status = rv["datum_ende"] or rv["datum_start"]

    # ---- milestones inferred from the files (conservative: only mark True on
    #      positive evidence, leave unknown ones blank/None)
    booking_present = any(classify(n) == "3_Booking" for n in all_names)
    hotel_present = any("hotel" in n.lower() for n in all_names)
    expense_real = any(classify(n) == "5_Expense_Report"
                       and "vorlage" not in n.lower() and "template" not in n.lower()
                       for n in all_names)
    event_past = bool(end_for_status) and end_for_status < today.isoformat()

    milestones = {
        "antrag_gestellt": True if has_signed_app else None,
        "antrag_genehmigt": True if reisenummer else None,
        "reise_gebucht": True if booking_present else None,
        "hotel_gebucht": True if hotel_present else None,
        "vorschuss": None,
        "event_stattgefunden": True if event_past else None,
        "abrechnung_eingereicht": True if (has_settlement or expense_real) else None,
        "erstattet": True if has_settlement else None,
    }

    # ---- headline status. Backlog = an old ingest, so be honest: only "closed"
    #      when there is settlement proof; otherwise "open-unsure".
    if has_settlement:
        status, status_why = "closed", "settlement (DR-Abrechnung) proof on file"
    else:
        status, status_why = "open-unsure", "old import; milestones not verified"

    # ---- manual overrides (after the user has reviewed the preview)
    if args.status:
        status, status_why = args.status, "manual override"
    if args.event:
        rv["event"] = args.event
        src["event"] = "manual"

    # Stems of known application files — used to rescue unsigned copies
    # (e.g. "<trip>.pdf" alongside "<trip>_signedEB.pdf") into 2_Application.
    app_stems = {norm_stem(n) for n in all_names if classify(n) == "2_Application"}

    # ---- classify the loose files (no moving yet)
    to_move, skipped, ambiguous = [], [], []
    for p in loose:
        target = classify(p.name)
        if target is None and norm_stem(p.name) in app_stems:
            target = "2_Application"
        if target is None:
            ambiguous.append(p.name)
        elif (trip / target / p.name).exists():
            skipped.append((p.name, target))
        else:
            to_move.append((p.name, target))

    trip_md = trip / "trip.md"
    md_exists = trip_md.exists()
    will_write_md = (not md_exists) or args.force_trip_md

    # ===================================================================== REPORT
    mode = "CONFIRM (writing)" if write else "PREVIEW (no changes)"
    print("=" * 70)
    print(f"{trip.name}   [{mode}]")
    print("=" * 70)

    # ---- 1. gleaned facts
    print("Gleaned facts:")
    print(f"  status        : {status}   ({status_why})")
    print(f"  trip number   : {reisenummer or '—'}")
    print(f"  event         : {rv['event'] or '—'}"
          + (f"   [{src['event']}]" if src['event'] else ""))
    print(f"  destination   : {rv['ziel'] or '—'}"
          + (f"   [{src['ziel']}]" if src['ziel'] else ""))
    print(f"  dates         : {rv['datum_start'] or '—'} -> {rv['datum_ende'] or '—'}"
          f"   [{src['datum_start'] or '—'}]")
    print(f"  Abrechnungsfr.: {rv['abrechnungsfrist'] or '—'}")
    print(f"  cost center   : {rv['kostenstelle'] or '(template default W0405001)'}"
          f"   [{src['kostenstelle']}]")
    print(f"  purpose       : {rv['reisezweck'] or '—'}")
    print("  milestones    :")
    for k, v in milestones.items():
        mark = "yes" if v is True else ("no" if v is False else " ? ")
        print(f"      [{mark:^3}] {k}")

    # ---- 2. what's missing / needs checking
    missing = []
    if not rv["ziel"]:
        missing.append("destination: could not determine (not in app PDF or folder name)")
    elif src["ziel"] == "folder name":
        missing.append("destination: only guessed from the folder name — verify the city/country")
    if not rv["event"]:
        missing.append("event name: not determined (folder name not parseable / no event "
                       "field on the form) — fill in by hand")
    elif src["event"] == "folder name":
        missing.append("event name: taken from the folder name — old folders are sometimes "
                       "EVENT_LOCATION, so check event vs. destination aren't swapped")
    if src["datum_start"] != "application":
        missing.append("dates: no dates read from an application PDF — using the folder-name "
                       "date; end date assumed = start (verify multi-day trips)")
    elif src["datum_ende"] == "= start date":
        missing.append("end date: not found, assumed same day as start")
    if not rv["reisezweck"]:
        missing.append("purpose (reisezweck_kurz): not found — left blank, fill in by hand")
    if not reisenummer:
        missing.append("trip number: none found (no Reisestelle settlement PDF in the folder)")
    if src["kostenstelle"] == "default":
        missing.append("cost center: not read from the application — defaulting to W0405001")
    if ambiguous:
        missing.append(f"{len(ambiguous)} file(s) couldn't be auto-sorted (listed below)")

    print("\nMissing / needs checking:")
    if missing:
        for m in missing:
            print(f"  ⚠ {m}")
    else:
        print("  ✓ nothing flagged — all key fields recovered")

    # ---- 3. planned (or performed) changes
    verb = "Changes made" if write else "Changes that WILL be made on --confirm"
    print(f"\n{verb}:")
    new_subfolders = [sf for sf in SUBFOLDERS if not (trip / sf).exists()]
    if new_subfolders:
        print(f"  • create subfolders: {', '.join(new_subfolders)}")
    if will_write_md:
        print(f"  • {'overwrite' if md_exists else 'write'} trip.md")
    else:
        print("  • trip.md already exists — leave it (use --force-trip-md to refill)")
    if to_move:
        print(f"  • move {len(to_move)} file(s):")
        for n, t in to_move:
            print(f"        {n}  ->  {t}/")
    if skipped:
        print(f"  • already in place ({len(skipped)}): {', '.join(n for n, _ in skipped)}")
    if ambiguous:
        print(f"  • LEAVE at top level for you to place ({len(ambiguous)}):")
        for n in ambiguous:
            print(f"        {n}")

    # ===================================================================== APPLY
    if not write:
        print("\nPREVIEW only — nothing changed. Re-run with --confirm to apply.")
        return

    for sf in new_subfolders:
        (trip / sf).mkdir(parents=True, exist_ok=True)
    if will_write_md:
        template = Path(args.template).read_text(encoding="utf-8")
        content = build_trip_md(template, folder_name=trip.name, resolved=rv,
                                status=status, reisenummer=reisenummer,
                                milestones=milestones, today=today)
        trip_md.write_text(content, encoding="utf-8")
    for n, t in to_move:
        (trip / t).mkdir(parents=True, exist_ok=True)
        shutil.move(str(trip / n), str(trip / t / n))
    print("\nDone.")


if __name__ == "__main__":
    main()
