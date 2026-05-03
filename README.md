# GIK Timetable Scheduler

Automated weekly timetable generator for GIK Institute, built for the
Spring 2026 catalogue. Greedy CSP solver with PDF-aware room/slot rules,
a CustomTkinter GUI, and an Excel exporter that mirrors the official
timetable layout.

## Quick start

```bash
pip install -r requirements.txt

# GUI
python main.py

# CLI
python main.py --cli --courses data/courses.xlsx --output output/timetable.xlsx
```

## Inputs / Outputs

- **Input**: `data/courses.xlsx` — Code, Sec, Course Title, CHs, Course Instructor, For, Exp Nos.
- **Output**: `output/timetable.xlsx` — room x slot grid grouped by building,
  Friday rendered with its shifted morning grid (10:00 / 11:00 / 12:00),
  cells colour-coded by department.

## Project layout

```
config.py                     # building / room / lab / break configuration
main.py                       # entry point (GUI default, --cli for headless)
src/
  parser/                     # courses.xlsx + institutional timetable readers
  scheduler/                  # CSP solver, constraint checker, room allocator
  exporter/                   # Excel writer (PDF-style grid)
  models/                     # Course / Room / TimeSlot dataclasses
gui/
  main_window.py              # root shell, sidebar, top bar
  upload_panel.py             # one-click generate flow
  timetable_view.py           # weekly grid render
  stats_view.py               # per-day / per-building statistics
data/                         # input course list + GIK reference PDF
report/                       # IEEE project report (.docx)
```

## Constraints

Hard rules are enforced via O(1) hash-map lookups in
`src/scheduler/constraint_checker.py`:

- No teacher double-booked.
- No room double-booked.
- No section taught twice on the same day.
- All sessions of a course share one locked room.

Soft objectives in `csp_solver.py` and `constraint_checker.py`:

- Day-load balancing (least-loaded day first; Friday seeded heavier so it
  stays light, matching the PDF).
- Penalty for stacking 3 consecutive slots on one instructor in one day.
- Capacity-aware room allocation with a wider-room fallback.
- Last-resort lab fallback to virtual TBA copies.

## Group

- Ismail Waqar — 2023453
- Abubakar — 2023352
- Usman — 2023581
- Ali Muntazir — 2023098

CS378 - Design and Analysis of Algorithms - Spring 2026
