# 60 — Calendar entries (via the `calmcp` calendar MCP server)

A trip produces **two different kinds of calendar entry**, on two different
calendars, at two different moments. Keeping them apart is the whole point:

| | Absence | Itinerary |
|---|---|---|
| **Calendar** | `cm_absence` (Kerio, shared, owned by `cm-office`) | `ic_travel` (iCloud, "travel", owned by you) |
| **Who reads it** | the department — it says "Erik is away" | you, on your phone, in transit |
| **What goes on it** | one all-day block over the travel period, nothing more | one event per travel leg + one per hotel stay |
| **When** | right after the Dienstreiseantrag is generated | when booking confirmations arrive (workflow B) |
| **Source** | `trip.md` YAML header | the booking confirmations in `3_Booking/` |

**Never put booking details on `cm_absence`.** It is a shared departmental
calendar; flight numbers, hotel addresses and booking references do not belong
there. Conversely, don't clutter `ic_travel` with the absence block — the
itinerary events already cover the same days.

---

## The tool: `calmcp` MCP server

Calendar work goes through the **calendar MCP server**
(<https://github.com/biterik/calendar-mcp-server>), exposed as `calmcp` tools:

| Tool | Used for |
|---|---|
| `list_calendars` | check `cm_absence` / `ic_travel` are configured and reachable |
| `find_events` | look for an existing entry for this trip before creating one |
| `create_event` | create the absence block or an itinerary event |
| `update_event` / `move_event` | fix a date or time after a rebooking |
| `delete_event` | remove an entry (cancelled trip, test cleanup) |
| `get_free_busy` | sanity-check a proposed trip against what's already booked |

Credentials live in the user's OS keyring, never in the pilot, never in the
conversation. There is **no password prompt, no `push_calendar.command` file,
and nothing for the user to double-click** — that whole flow is retired. If the
MCP server is not available in the session, fall back to
`scripts/add_to_calendar.py` (see "Fallback" at the end).

### The two confirmation gates

`create_event` and friends are **dry-run by default**. They return a
`before`/`after` write contract and change nothing until confirmed:

- `confirm=true` — required for every real write.
- `confirm_foreign=true` — required **in addition** when the calendar's role is
  not `owner`. **`cm_absence` has role `writable`, so absence blocks always need
  both flags.** `ic_travel` is `owner`, so it needs only `confirm`.

**Always run the dry-run first, show the user what it returned, and only pass
the confirm flags after an explicit yes.** Never set `confirm_foreign` without
having shown the user that the write targets someone else's calendar.

---

## A — The absence block (`cm_absence`)

### Trigger — mandatory, never skip

After delivering a completed Dienstreiseantrag, **the very next action** is one
`AskUserQuestion`: "Add this trip to your calendar? Yes / No." Ask even if the
user never mentioned the calendar, and ask again after a correction or
regeneration — but only once per final PDF. Do not move on to "next steps"
prose before this question has been asked.

The user may also ask at any other point ("trag das in den Kalender ein") —
same flow.

### Flow

1. **Read the trip's `trip.md`** YAML header: `event`, `ziel`, `datum_start`,
   `datum_ende`, `reisenummer`, `reisezweck_kurz`, `event_url`, `status`.
2. **Check for an existing entry** with `find_events` (`q` = the event name,
   range = the trip dates ±7 days). If one exists, this is an *update*, not a
   create — say so.
3. **Dry-run `create_event`** (no confirm flags):

   ```
   calendar: cm_absence
   summary:  Dienstreise: <event> (<ziel>)
   start:    <datum_start>          # YYYY-MM-DD
   end:      <datum_ende>           # YYYY-MM-DD
   all_day:  true
   location: <ziel>
   uid:      travel-forms-pilot-<trip-folder-name>@mpie.de
   reminder: <alarm_days_before from identity.yaml; currently 0 = none>
   ```

   Keep the description empty or a single short line (`reisezweck_kurz`). No
   booking data, no trip number needed by anyone but you.

4. **Show the user the returned write contract** and ask one short confirmation:
   "I'll add *Dienstreise: MecaNano Summer School (Cargèse, France)*,
   Tu 1.9.2026 → Su 6.9.2026, all day, to **CM_Absence** — that's the shared
   departmental calendar. OK to push?" Always name the weekday with the dates
   (see the date sanity-checking rules in `00_pilot.md`).
5. **Only after an explicit yes**, re-run `create_event` with
   `confirm=true` **and** `confirm_foreign=true`.
6. **Report** in one line, and set `kalender: absenz_eingetragen: true` in
   `trip.md`.

### The UID matters

`uid: travel-forms-pilot-<trip-folder-name>@mpie.de` is the same scheme
`add_to_calendar.py` used, so re-running **updates** the existing event rather
than creating a duplicate — including events created before the move to the MCP
server. Never invent a different UID for a trip that already has one.

### All-day end date

Pass `end` as the **last day of the trip** (`datum_ende`) — `calmcp` does the
`DTEND`-is-exclusive conversion for you. Verified July 2026: input
`start 2026-09-06 / end 2026-09-12` returns `end: 2026-09-13` in the write
contract, i.e. a block covering 6–12 September inclusive, which is what you want.
Do **not** pre-add a day. The returned `end` in the contract will always look one
day later than the trip — that's correct, not an off-by-one.

---

## B — The itinerary (`ic_travel`)

### Trigger

When booking confirmations land in the trip folder — a train ticket, a flight
confirmation, a hotel reservation — as part of the normal update flow
(`00_pilot.md`, "Updating an existing trip"). After sorting the new file into
`3_Booking/` and updating the `trip.md` milestones, offer the itinerary entries:
"I can put the outbound ICE, the return, and the hotel into your iCloud
**travel** calendar. Want that?"

Booking happens only after the application is approved, so in practice this
always comes after the absence block already exists.

### One event per item

Read the actual times, numbers and addresses **out of the booking confirmation**
— never from memory, never invented. If a confirmation is a scan with no text
layer, say so and ask rather than guessing.

**Travel legs** — timed events, Europe/Berlin unless the booking says otherwise:

```
calendar: ic_travel
summary:  Train ICE 529  Düsseldorf Hbf → Erlangen
          Flight LH 1054  DUS → AJA
start:    2026-09-01 07:34
end:      2026-09-01 11:52
location: Düsseldorf Hbf            # the departure point
description: |
  Coach 8, seat 61. Booking 122278491956.
  3_Booking/db_ticket_122278491956.pdf
uid:      tfp-<trip-folder-name>-out@travel      # -ret for the return
                                                # -leg3, -leg4 … for further legs
```

**Hotel stays** — all-day, check-in day to check-out day:

```
calendar: ic_travel
summary:  Hotel: Ibis Erlangen
start:    2026-09-01
end:      2026-09-03
all_day:  true
location: <street, postcode, city — as printed on the confirmation>
description: |
  Booking reference ABC123. Breakfast included.
  3_Booking/hotel_confirmation.pdf
uid:      tfp-<trip-folder-name>-hotel@travel   # -hotel2 … if more than one
```

Put the source filename in the description. When the user is standing in a
station wondering which coach, that line is what makes the entry useful.

### Flow

1. Dry-run **all** the events first, then show them as one short table
   (summary / start / end / location) — not one confirmation per event.
2. On a single yes, create them all with `confirm=true` (no
   `confirm_foreign` — `ic_travel` is owned).
3. Report one line, and set `kalender: reise_eingetragen: true` in `trip.md`.

### Rebookings

If a leg changes, don't create a second event: `move_event` (new times) or
`update_event` (everything else) on the same UID. The UID scheme is stable per
trip folder precisely so a rebooking is an edit.

---

## Recording it in `trip.md`

The `kalender:` block in the YAML header tracks what has been pushed:

```yaml
kalender:
  absenz_eingetragen:        # all-day block on cm_absence? true / false / blank
  reise_eingetragen:         # itinerary events on ic_travel? true / false / blank
  notiz: ""                  # e.g. "return leg rebooked 3.9. — event moved"
```

Set these after a successful write, so a later session knows not to ask again.

---

## Meals, per diems and the expense report

The itinerary events are also the cleanest record of **when you actually left
and returned**, which is exactly what the Reiseabrechnung needs. When building
the expense report, `find_events` on `ic_travel` for the trip range gives the
departure and arrival times without the user having to dig out the tickets
again. Use it as a proposal to confirm, never as fact — the receipt still wins
if the two disagree (`00_pilot.md`, "On uncertainty").

---

## Fallback: no MCP server in the session

`scripts/add_to_calendar.py` still works and stays supported for anyone running
the pilot without the calendar MCP server — GWDG Chat AI, a bare chat, another
vendor's agent. It handles the **absence block only** (CalDAV, Kerio, all-day or
timed, confirm-first, same UID scheme):

```bash
python scripts/add_to_calendar.py <trip-folder>             # preview, no password
python scripts/add_to_calendar.py <trip-folder> --confirm   # push
```

In that mode the password is collected by a native OS dialog on the user's own
machine — write a `push_calendar.command` into the trip folder and have the user
double-click it (format in `SKILL.md`). **Only do this when the `calmcp` tools
are genuinely unavailable.** With the MCP server present, that flow is strictly
worse: an extra file, an extra manual step, and no itinerary support.

See the README for how to install and configure the calendar MCP server.
