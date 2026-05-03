"""
course_parser.py
Reads the offered-courses Excel file and returns a list of Course objects.

Expected Excel columns (order-independent, matched by header name):
    Code        → course code       e.g. "CS478"
    Sec         → section           e.g. "A", "B1"
    Course Title → full title       e.g. "Design and Analysis of Algorithms"
    CHs         → credit hours      e.g. 3
    Course Instructor → instructor  e.g. "Mr. Ahsan Shah"
    For         → target batch      e.g. "BAI"
    Exp Nos     → expected students e.g. 45

Lab detection:
    A row is treated as a lab if:
      - The course code ends with "L"  (e.g. CS221L, CE324L)
      - OR the title contains "Lab"    (case-insensitive)
      - OR CHs == 1 and title contains "Lab"

The parser is intentionally tolerant:
    - Missing optional columns are silently skipped
    - Rows with no Code or empty Code are skipped
    - Leading/trailing whitespace is stripped from all fields
    - Duplicate unique_ids (Code_Sec) are de-duplicated (last row wins)
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.models.course import Course


# ── Column name aliases ────────────────────────────────────────────────────────
# Maps canonical field name → list of possible header strings in the Excel file
_COL_ALIASES: dict[str, list[str]] = {
    "code":        ["Code", "code", "CODE", "Course Code"],
    "section":     ["Sec", "Section", "sec", "SECTION"],
    "title":       ["Course Title", "Title", "Course Name", "TITLE"],
    "instructor":  ["Course Instructor", "Instructor", "INSTRUCTOR", "Faculty"],
    "credit_hours":["CHs", "Credit Hours", "CH", "Credits", "CHS"],
    "for_batch":   ["For", "Batch", "FOR", "Programme", "Program"],
    "expected":    ["Exp Nos", "Expected", "Strength", "EXP NOS", "Enrollment"],
}


def _resolve_columns(df_columns: list[str]) -> dict[str, str | None]:
    """
    For each canonical field, find which actual column name is present in df.
    Returns a mapping: canonical_name → actual_column_name (or None if missing).
    """
    col_set = set(df_columns)
    resolved = {}
    for field, aliases in _COL_ALIASES.items():
        resolved[field] = next((a for a in aliases if a in col_set), None)
    return resolved


# Departments whose "L"-suffixed courses are actually lecture-hall classes,
# not equipment labs (HM = Humanities; courses like HM101L "Communication
# Skills Lab" meet in regular lecture halls alongside paired sections).
_NON_EQUIPMENT_LAB_DEPTS = {"HM"}


def _is_lab(code: str, title: str, credit_hours: int) -> bool:
    """Determine if a row represents an equipment lab session."""
    code_str = str(code).strip().upper()

    # Humanities-style "labs" are reclassified as lectures — they meet in
    # regular lecture halls, so routing them through lab logic forces them
    # to compete for nonexistent equipment rooms and they always fail.
    dept_prefix = "".join(ch for ch in code_str if ch.isalpha())[:2]
    if dept_prefix in _NON_EQUIPMENT_LAB_DEPTS:
        return False

    code_lab  = code_str.endswith("L")
    title_lab = "lab" in str(title).lower()
    ch_lab    = (credit_hours == 1 and title_lab)
    return code_lab or title_lab or ch_lab


def _clean_str(val) -> str:
    """Return a stripped string, or empty string for NaN/None."""
    if pd.isna(val) if not isinstance(val, str) else False:
        return ""
    return str(val).strip()


def _clean_int(val, default: int = 0) -> int:
    """Parse an integer safely, returning default for non-numeric values."""
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default


class CourseParser:
    """
    Parses an Excel file of offered courses into a list of Course objects.

    Parameters
    ----------
    path : str | Path
        Path to the courses Excel file.
    sheet_name : str | int
        Sheet to read. Defaults to the first sheet (0).
    header_row : int
        0-based row index of the header row. Defaults to 0.

    Example
    -------
        parser  = CourseParser("data/courses.xlsx")
        courses = parser.parse()
    """

    def __init__(
        self,
        path: str | Path,
        sheet_name: str | int = 0,
        header_row: int | None = None,
    ):
        self.path       = Path(path)
        self.sheet_name = sheet_name
        self.header_row = header_row

        self._errors:   list[str] = []    # non-fatal warnings collected during parse
        self._courses:  list[Course] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def parse(self) -> list[Course]:
        """
        Read the Excel file and return a list of Course objects.
        Raises FileNotFoundError if the path does not exist.
        Raises ValueError if no valid courses could be parsed.
        """
        if not self.path.exists():
            raise FileNotFoundError(f"Course file not found: {self.path}")

        # Auto-detect header row: scan first 5 rows for one containing 'Code'
        if self.header_row is None:
            raw = pd.read_excel(self.path, sheet_name=self.sheet_name,
                                header=None, dtype=str, nrows=5)
            detected = 0
            for i, row in raw.iterrows():
                if any(str(v).strip() in ("Code", "code", "CODE") for v in row if pd.notna(v)):
                    detected = i
                    break
            header_row = detected
        else:
            header_row = self.header_row

        df = pd.read_excel(
            self.path,
            sheet_name=self.sheet_name,
            header=header_row,
            dtype=str,
        )

        df.columns = [str(c).strip() for c in df.columns]
        col_map    = _resolve_columns(list(df.columns))

        self._errors  = []
        self._courses = []
        seen_ids: dict[str, Course] = {}   # unique_id → Course (de-dup)

        for row_idx, row in df.iterrows():
            course = self._parse_row(row, col_map, row_idx)
            if course is None:
                continue
            # De-duplicate: last row for a given unique_id wins
            seen_ids[course.unique_id] = course

        self._courses = list(seen_ids.values())

        if not self._courses:
            raise ValueError(
                f"No valid courses found in '{self.path}'. "
                f"Check column headers match expected names."
            )

        return self._courses

    @property
    def errors(self) -> list[str]:
        """Non-fatal warnings collected during the last parse() call."""
        return list(self._errors)

    @property
    def courses(self) -> list[Course]:
        """Courses from the last parse() call (empty before first call)."""
        return list(self._courses)

    def summary(self) -> dict:
        """Return a quick summary dict after parsing."""
        labs      = [c for c in self._courses if c.is_lab]
        lectures  = [c for c in self._courses if not c.is_lab]
        depts     = sorted({c.department for c in self._courses})
        return {
            "total":     len(self._courses),
            "lectures":  len(lectures),
            "labs":      len(labs),
            "departments": depts,
            "warnings":  len(self._errors),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _parse_row(
        self, row: pd.Series, col_map: dict[str, str | None], row_idx: int
    ) -> Course | None:
        """
        Convert a single DataFrame row into a Course.
        Returns None if the row should be skipped.
        """
        # ── Code ──────────────────────────────────────────────────────────────
        code_col = col_map.get("code")
        if code_col is None:
            return None
        code = _clean_str(row.get(code_col, ""))
        if not code or code.lower() == "code":
            return None   # empty row or repeated header row

        # Reject junk rows — valid codes are short (typically 5-12 chars),
        # have no newlines, and match the pattern of 2+ letters then digits.
        if len(code) > 15 or "\n" in code or "  " in code:
            return None
        import re
        # Valid: CS101, CS101L, EE201/EE213, CS4xx, MT202 etc.
        if not re.match(r"^[A-Za-z]{2,}[A-Za-z0-9/xX]*L?$", code):
            return None

        # ── Section ───────────────────────────────────────────────────────────
        sec_col = col_map.get("section")
        section = _clean_str(row.get(sec_col, "")) if sec_col else "A"
        if not section:
            section = "A"

        # ── Title ─────────────────────────────────────────────────────────────
        title_col = col_map.get("title")
        title     = _clean_str(row.get(title_col, "")) if title_col else code

        # ── Credit hours ──────────────────────────────────────────────────────
        ch_col       = col_map.get("credit_hours")
        credit_hours = _clean_int(row.get(ch_col, 3)) if ch_col else 3
        if credit_hours <= 0:
            self._errors.append(
                f"Row {row_idx}: {code}_{section} has CHs={credit_hours}, defaulting to 1."
            )
            credit_hours = 1

        # ── Instructor ────────────────────────────────────────────────────────
        ins_col    = col_map.get("instructor")
        instructor = _clean_str(row.get(ins_col, "")) if ins_col else "TBA"
        if not instructor or instructor.upper() in ("TBA", "TBD", "NAN", ""):
            instructor = "TBA"

        # ── For batch ─────────────────────────────────────────────────────────
        batch_col = col_map.get("for_batch")
        for_batch = _clean_str(row.get(batch_col, "")) if batch_col else ""

        # ── Expected students ─────────────────────────────────────────────────
        exp_col           = col_map.get("expected")
        expected_students = _clean_int(row.get(exp_col, 0)) if exp_col else 0

        # ── Lab detection ─────────────────────────────────────────────────────
        is_lab = _is_lab(code, title, credit_hours)

        return Course(
            code              = code,
            section           = section,
            title             = title,
            instructor        = instructor,
            credit_hours      = credit_hours,
            is_lab            = is_lab,
            for_batch         = for_batch,
            expected_students = expected_students,
        )