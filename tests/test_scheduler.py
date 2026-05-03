"""
test_scheduler.py
Integration tests for the full scheduling pipeline:
    CourseParser → TimetableParser → CSPSolver → ExcelExporter

Run with: python -m pytest tests/
"""

import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd

from src.models.course import Course
from src.parser.course_parser import CourseParser
from src.parser.timetable_parser import TimetableParser
from src.scheduler.csp_solver import CSPSolver
from src.exporter.excel_exporter import ExcelExporter


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_courses_excel(rows: list[dict]) -> Path:
    df  = pd.DataFrame(rows)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False)
    return Path(tmp.name)

SAMPLE_ROWS = [
    {"Code": "CS478",  "Sec": "A",  "Course Title": "DAA",
     "Course Instructor": "Mr. Ahsan", "CHs": 3, "For": "BAI", "Exp Nos": 30},
    {"Code": "CS221",  "Sec": "B",  "Course Title": "DSA",
     "Course Instructor": "Mr. Qasim", "CHs": 3, "For": "BCE", "Exp Nos": 30},
    {"Code": "CS311",  "Sec": "A",  "Course Title": "OS",
     "Course Instructor": "Dr. Sarah", "CHs": 3, "For": "BAI", "Exp Nos": 40},
    {"Code": "CS351",  "Sec": "D",  "Course Title": "AI",
     "Course Instructor": "Dr. Ayaz",  "CHs": 3, "For": "BDS", "Exp Nos": 30},
    {"Code": "CS221L", "Sec": "A",  "Course Title": "DSA Lab",
     "Course Instructor": "Mr. Naeem", "CHs": 1, "For": "BAI", "Exp Nos": 25},
    {"Code": "CS311L", "Sec": "B",  "Course Title": "OS Lab",
     "Course Instructor": "Engr. Ali", "CHs": 1, "For": "BCE", "Exp Nos": 30},
]


# ── Parser → Solver integration ───────────────────────────────────────────────

class TestFullPipeline:

    def test_solver_places_all_small_set(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        solver  = CSPSolver(courses, tt, time_limit=30)
        result  = solver.solve()
        assert len(result) == len(SAMPLE_ROWS)

    def test_result_has_required_keys(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        result  = CSPSolver(courses, tt, time_limit=30).solve()
        required = {"course", "section", "instructor", "day", "slot", "room"}
        for item in result:
            assert required.issubset(item.keys()), f"Missing keys in {item}"

    def test_no_room_clashes(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        result  = CSPSolver(courses, tt, time_limit=30).solve()
        seen = set()
        for item in result:
            key = (item["day"], item["slot"], item["room"])
            assert key not in seen, f"Room clash detected: {key}"
            seen.add(key)

    def test_no_instructor_clashes(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        result  = CSPSolver(courses, tt, time_limit=30).solve()
        seen = set()
        for item in result:
            if item["instructor"] == "TBA":
                continue
            key = (item["day"], item["slot"], item["instructor"])
            assert key not in seen, f"Instructor clash: {key}"
            seen.add(key)

    def test_no_batch_clashes(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        result  = CSPSolver(courses, tt, time_limit=30).solve()
        seen = set()
        for item in result:
            if not item.get("for_batch"):
                continue
            key = (item["day"], item["slot"], item["for_batch"])
            assert key not in seen, f"Batch clash: {key}"
            seen.add(key)

    def test_labs_assigned_to_lab_rooms(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        result  = CSPSolver(courses, tt, time_limit=30).solve()
        lab_rooms = {r.name for r in tt.rooms if r.is_lab}
        for item in result:
            if item.get("is_lab"):
                assert item["room"] in lab_rooms, (
                    f"Lab {item['course']} assigned to non-lab room {item['room']}"
                )

    def test_lectures_not_assigned_to_lab_rooms(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        result  = CSPSolver(courses, tt, time_limit=30).solve()
        lab_rooms = {r.name for r in tt.rooms if r.is_lab}
        for item in result:
            if not item.get("is_lab"):
                assert item["room"] not in lab_rooms, (
                    f"Lecture {item['course']} assigned to lab room {item['room']}"
                )


# ── Solver report ─────────────────────────────────────────────────────────────

class TestSolverReport:

    def test_report_keys_present(self):
        courses = [Course(code="CS478", section="A", title="DAA",
                          instructor="Mr. Shah", credit_hours=3,
                          for_batch="BAI", expected_students=30)]
        tt     = TimetableParser(None)
        solver = CSPSolver(courses, tt, time_limit=10)
        solver.solve()
        report = solver.report()
        for key in ("total", "assigned", "unassigned", "elapsed_s", "checker"):
            assert key in report

    def test_report_counts_match(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        solver  = CSPSolver(courses, tt, time_limit=30)
        result  = solver.solve()
        report  = solver.report()
        assert report["assigned"] + report["unassigned"] == report["total"]
        assert report["assigned"] == len(result)


# ── Excel Exporter ────────────────────────────────────────────────────────────

class TestExcelExporter:

    def _get_result(self):
        path    = _make_courses_excel(SAMPLE_ROWS)
        courses = CourseParser(path).parse()
        tt      = TimetableParser(None)
        return CSPSolver(courses, tt, time_limit=30).solve()

    def test_exports_valid_xlsx(self):
        result  = self._get_result()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp = Path(f.name)
        ExcelExporter(result).save(tmp)
        assert tmp.exists()
        assert tmp.stat().st_size > 0
        tmp.unlink()

    def test_exported_file_has_two_sheets(self):
        result  = self._get_result()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp = Path(f.name)
        ExcelExporter(result).save(tmp)
        xl = pd.ExcelFile(tmp)
        assert "Timetable" in xl.sheet_names
        assert "Raw Data"  in xl.sheet_names
        tmp.unlink()

    def test_raw_data_sheet_row_count(self):
        result  = self._get_result()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp = Path(f.name)
        ExcelExporter(result).save(tmp)
        df = pd.read_excel(tmp, sheet_name="Raw Data")
        # Keep only actual course rows — summary rows have labels like "Total Sessions"
        # which don't match the pattern of a real course code (e.g. "CS478")
        df = df[df["Course Code"].str.match(r"^[A-Z]{2}\d+", na=False)]
        assert len(df) == len(result)
        tmp.unlink()


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_course_list_returns_empty(self):
        tt     = TimetableParser(None)
        result = CSPSolver([], tt, time_limit=5).solve()
        assert result == []

    def test_single_course_scheduled(self):
        courses = [Course(code="CS478", section="A", title="DAA",
                          instructor="Mr. Shah", credit_hours=3,
                          for_batch="BAI", expected_students=30)]
        tt     = TimetableParser(None)
        result = CSPSolver(courses, tt, time_limit=10).solve()
        assert len(result) == 1

    def test_impossible_course_skipped(self):
        # A course requiring 9999 students — no room will fit it
        courses = [
            Course(code="CS478", section="A", title="DAA",
                   instructor="Mr. Shah", credit_hours=3,
                   for_batch="BAI", expected_students=9999),
            Course(code="CS221", section="B", title="DSA",
                   instructor="Mr. Qasim", credit_hours=3,
                   for_batch="BCE", expected_students=30),
        ]
        tt     = TimetableParser(None)
        result = CSPSolver(courses, tt, time_limit=10).solve()
        # The impossible course should be skipped; the other should be placed
        codes  = [r["course"] for r in result]
        assert "CS221" in codes
        assert "CS478" not in codes