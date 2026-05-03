"""
config.py
Global configuration for the GIK Timetable Scheduler.

All constants that might need tuning are defined here in one place.
Import this module anywhere with:
    from config import DAYS, SLOT_TIMES, BUILDINGS, LAB_ROOM_MAP, BREAK_SLOTS
"""

from pathlib import Path

# ── Project paths ─────────────────────────────────────────────────────────────
ROOT_DIR   = Path(__file__).parent
DATA_DIR   = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"

OUTPUT_DIR.mkdir(exist_ok=True)

# ── Days ──────────────────────────────────────────────────────────────────────
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# ── Time slots (from institutional timetable) ─────────────────────────────────
# Format: (start, end) in HH:MM
SLOT_TIMES = [
    ("08:00", "08:50"),
    ("09:00", "09:50"),
    # --- Breakfast break: 09:50 - 10:30 (blocked) ---
    ("10:30", "11:20"),
    ("11:30", "12:20"),
    ("12:30", "13:20"),
    # --- Lunch break: 13:20 - 14:30 (blocked) ---
    ("14:30", "15:20"),
    ("15:30", "16:20"),
    ("16:30", "17:20"),
]

# ── Break slots (blocked - no classes allowed) ────────────────────────────────
# Day-aware: Friday's morning grid has no breakfast break (slots run
# 09:00-09:50 → 10:00-10:50 back-to-back per the PDF). Mon-Thu keep both.
# Format: day → list of (start, end) tuples in HH:MM.
BREAK_SLOTS_BY_DAY: dict[str, list[tuple[str, str]]] = {
    "Monday":    [("09:50", "10:30"), ("13:20", "14:30")],
    "Tuesday":   [("09:50", "10:30"), ("13:20", "14:30")],
    "Wednesday": [("09:50", "10:30"), ("13:20", "14:30")],
    "Thursday":  [("09:50", "10:30"), ("13:20", "14:30")],
    "Friday":    [("12:50", "14:30")],
}

# Backwards-compat: union of all breaks (used as fallback if a day not listed)
BREAK_SLOTS = [
    ("09:50", "10:30"),
    ("13:20", "14:30"),
]

# ── Lab scheduling ────────────────────────────────────────────────────────────
LAB_BLOCK_LENGTH        = 3    # 3 consecutive 50-min slots = ~3 hours
MAX_ADJACENT_GAP_MINUTES = 15  # max gap between slots to be considered adjacent

# ── Solver settings ───────────────────────────────────────────────────────────
CSP_TIME_LIMIT      = 120.0
ORTOOLS_TIME_LIMIT  = 60.0
ORTOOLS_NUM_WORKERS = 4

# ── Building system ───────────────────────────────────────────────────────────
BUILDINGS: dict = {
    "ACB": {
        "name":        "Academic Block",
        "departments": ["CS", "CE", "DS", "AI", "CY", "SE", "EE", "MT", "ES"],
        "capacity":    80,
    },
    "FCSE": {
        "name":        "Faculty of Computer Science & Engineering",
        "departments": ["CS", "CE", "DS", "AI", "CY", "SE"],
        "capacity":    60,
    },
    "FEE": {
        "name":        "Faculty of Electrical Engineering",
        "departments": ["EE"],
        "capacity":    80,
    },
    "FES": {
        "name":        "Faculty of Engineering Sciences",
        "departments": ["MT", "ES", "PH"],
        "capacity":    60,
    },
    "FME": {
        "name":        "Faculty of Mechanical Engineering",
        "departments": ["ME"],
        "capacity":    60,
    },
    "FMCE": {
        "name":        "Faculty of Materials & Chemical Engineering",
        "departments": ["MM", "CH", "CM"],
        "capacity":    60,
    },
    "BB": {
        "name":        "Business Block",
        "departments": ["HM", "MS", "SC", "AF", "MG"],
        "capacity":    60,
    },
}

# ── Department -> allowed buildings (lecture rooms, priority order) ────────────
# Verified against PDF "TimeTable Spring 2026" (data/) on 2026-05-03:
#   CH lectures live in AcB LH10/11/12 + AcB Main3 (ACB), NOT FMCE.
#   FMCE rooms (MCE LH1-4, MCE Main, Mat. Lab) are dedicated to MM (Materials).
#   Management subjects (HM/MS/SC/AF/MG/EM) all live in BB area.
DEPT_BUILDINGS: dict = {
    "CS":  ["FCSE", "ACB"],
    "CE":  ["FCSE", "ACB"],
    "DS":  ["ACB", "FCSE"],
    "AI":  ["ACB", "FCSE"],
    "CY":  ["ACB", "FCSE"],
    "SE":  ["ACB", "FCSE"],
    "EE":  ["FEE", "ACB"],
    "MT":  ["ACB", "FES"],
    "ES":  ["FES", "ACB"],
    "PH":  ["FES", "ACB"],
    "ME":  ["FME"],
    "MM":  ["FMCE"],
    "CH":  ["ACB", "FMCE"],
    "CM":  ["ACB", "FMCE"],
    "HM":  ["BB"],
    "MS":  ["BB"],
    "SC":  ["BB"],
    "AF":  ["BB"],
    "MG":  ["BB"],
    "EM":  ["BB"],
    "CV":  ["ACB"],
    "IF":  ["ACB", "FCSE"],
    "_":   ["ACB"],
}

# ── Lab room mappings (course code prefix -> lab room) ────────────────────────
# All lab rooms here MUST exist in data/gikirooms.xlsx. Verified 2026-05-03.
# Departments without a true equipment lab (e.g. HM = Humanities) are NOT mapped
# here — their "L" courses are reclassified as lectures by CourseParser._is_lab.
LAB_ROOM_MAP: dict = {
    # Building locations (verified against PDF + GIK student knowledge):
    #   FCSE building     → SE Lab (only software lab in FCSE)
    #   Academic Block    → AI Lab, CyS Lab, DA Lab
    # SE Lab is shared across CS/CE/SE because those programmes commonly
    # use the FCSE software lab. CY labs primarily live in ACB-CYS, DS in
    # ACB-DA, AI in ACB-AI.
    "SE":  "FCSE - SE Lab",
    "CE":  "FCSE - SE Lab",
    "CS":  "FCSE - SE Lab",
    "AI":  "ACB - AI Lab",
    "CY":  "ACB - CYS Lab",
    "DS":  "ACB - DA Lab",
    # FES labs
    "PH":  "FES - PH Lab",
    "ES":  "FBS Lab",
    "MT":  "FBS Lab",
    # FEE — no dedicated EE Lab in gikirooms; route to FBS lab as nearest fit
    "EE":  "FBS Lab",
    # FME
    "ME":  "FME Lab",
    # FMCE
    "MM":  "Mat. Lab",
    "CH":  "FMCE - CH Lab",
    "CM":  "FMCE - CH Lab",
    # Civil — uses dedicated CV labs (CV202L/CV231L/CV305L/CV314L/CV361L pairs).
    # Routed to a virtual "CV Lab" pool that the room expander fans out
    # into multiple instances based on demand.
    "CV":  "CV Lab",
    # Computing fundamentals (cross-faculty IF / freshman) — routed to
    # the FCSE software lab pool which has the broadest backup chain.
    "IF":  "FCSE - SE Lab",
    # Business / Management labs
    "MS":  "Old PC Lab",
    "AF":  "Old PC Lab",
    "SC":  "WR 1",
    "EM":  "WR 2",
    "MG":  "Sem. Hall",
}

# ── Keyword -> lab room override (checked before prefix map) ──────────────────
KEYWORD_LAB_MAP: dict = {
    "fluid":              "FME Lab",
    "heat":               "FME Lab",
    "vibration":          "FME Lab",
    "workshop":           "FME Lab",
    "mos":                "FME Lab",
    "mechanics of solid": "FME Lab",
    "vehicle":            "FME Lab",
    "thermo":             "FME Lab",
    "particle":           "FMCE - CH Lab",
    "chemical":           "FMCE - CH Lab",
    "mass transfer":      "FMCE - CH Lab",
}

# ── Backup lab rooms (if primary is full) ─────────────────────────────────────
# All entries MUST reference rooms that exist in data/gikirooms.xlsx.
BACKUP_LAB_ROOMS: dict = {
    # SE Lab (FCSE) — primary software lab. Backups prefer ACB siblings
    # (AI/CYS/DA all in Acad. Block) before crossing to FES.
    "FCSE - SE Lab":  ["ACB - CYS Lab", "ACB - AI Lab", "ACB - DA Lab", "FES - SE Lab", "FBS Lab", "PC Lab", "Old PC Lab", "New PC Lab"],
    "FES - SE Lab":   ["FCSE - SE Lab", "ACB - CYS Lab", "ACB - AI Lab", "ACB - DA Lab", "PC Lab"],
    # ACB labs — clustered together; spill into FCSE-SE Lab last.
    "ACB - CYS Lab":  ["ACB - AI Lab", "ACB - DA Lab", "FCSE - SE Lab", "FES - SE Lab"],
    "ACB - AI Lab":   ["ACB - DA Lab", "ACB - CYS Lab", "FCSE - SE Lab", "FES - SE Lab"],
    "ACB - DA Lab":   ["ACB - AI Lab", "ACB - CYS Lab", "FCSE - SE Lab", "FES - SE Lab"],
    # FCSE - CyS Lab kept as legacy backup (some old configs route here)
    "FCSE - CyS Lab": ["ACB - CYS Lab", "FCSE - SE Lab", "ACB - AI Lab", "ACB - DA Lab"],
    "FME Lab":        ["Mat. Lab", "FBS Lab"],
    "Mat. Lab":       ["FMCE - MM Lab", "FMCE - CH Lab", "FME Lab", "FBS Lab"],
    "FMCE - MM Lab":  ["Mat. Lab", "FMCE - CH Lab", "FBS Lab"],
    "FMCE - CH Lab":  ["FMCE - MM Lab", "Mat. Lab", "FBS Lab"],
    "FBS Lab":        ["FES - SE Lab", "FCSE - SE Lab", "PC Lab"],
    "FES - PH Lab":   ["FES - PH Lab 2", "FBS Lab"],
    "PC Lab":         ["FBS Lab", "FES - SE Lab", "Old PC Lab", "New PC Lab"],
    # Civil labs — no equipment lab in gikirooms; pool spreads load across
    # virtual instances and falls back to whichever AcB lecture rooms are
    # designated for civil labs in the PDF.
    "CV Lab":         ["FBS Lab", "PC Lab", "Sim. Lab"],
    # Business / Management labs
    "Old PC Lab":     ["New PC Lab", "Sem. Hall", "WR 1", "WR 2"],
    "New PC Lab":     ["Old PC Lab", "Sem. Hall", "WR 1", "WR 2"],
    "Sem. Hall":      ["Old PC Lab", "New PC Lab", "WR 1", "WR 2"],
    "WR 1":           ["WR 2", "Sem. Hall", "Old PC Lab", "New PC Lab"],
    "WR 2":           ["WR 1", "Sem. Hall", "Old PC Lab", "New PC Lab"],
    "Sim. Lab":       ["FBS Lab", "PC Lab", "Old PC Lab"],
}

# ── Output settings ───────────────────────────────────────────────────────────
OUTPUT_FILENAME   = "timetable.xlsx"
OUTPUT_EXCEL_PATH = OUTPUT_DIR / OUTPUT_FILENAME

# ── GUI settings ──────────────────────────────────────────────────────────────
WINDOW_TITLE  = "GIK Timetable Scheduler"
WINDOW_WIDTH  = 1280
WINDOW_HEIGHT = 760
WINDOW_MIN_W  = 960
WINDOW_MIN_H  = 620