"""
test_parser.py
Unit tests for CourseParser and TimetableParser.
Run with: python -m pytest tests/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tempfile
import pytest
import pandas as pd

from src.parser.course_parser import CourseParser
from src.parser.timetable_parser import TimetableParser
from src.models.room import RoomType


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_courses_excel(rows: list[dict]) -> Path:
    """Write a minimal courses Excel file and return its path."""
    df = pd.DataFrame(rows)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False)
    return Path(tmp.name)


# ── CourseParser tests ────────────────────────────────────────────────────────

class TestCourseParser:

    def test_parses_basic_lecture(self):
        path = _make_courses_excel([{
            "Code": "CS478", "Sec": "A",
            "Course Title": "Design and Analysis of Algorithms",
            "Course Instructor": "Mr. Ahsan Shah",
            "CHs": 3, "For": "BAI", "Exp Nos": 45,
        }])
        courses = CourseParser(path).parse()
        assert len(courses) == 1
        c = courses[0]
        assert c.code == "CS478"
        assert c.section == "A"
        assert c.credit_hours == 3
        assert not c.is_lab
        assert c.department == "CS"
        assert c.sessions_per_week == 3
        assert c.expected_students == 45

    def test_detects_lab_by_code_suffix(self):
        path = _make_courses_excel([{
            "Code": "CS221L", "Sec": "A",
            "Course Title": "Data Structures Lab",
            "Course Instructor": "Mr. Naeem",
            "CHs": 1, "For": "BAI", "Exp Nos": 25,
        }])
        courses = CourseParser(path).parse()
        assert courses[0].is_lab

    def test_detects_lab_by_title(self):
        path = _make_courses_excel([{
            "Code": "CE324L", "Sec": "B1",
            "Course Title": "Microprocessor Interfacing Lab",
            "Course Instructor": "Engr. Abbas Khan",
            "CHs": 1, "For": "BCE", "Exp Nos": 40,
        }])
        courses = CourseParser(path).parse()
        assert courses[0].is_lab

    def test_skips_empty_rows(self):
        path = _make_courses_excel([
            {"Code": "CS478", "Sec": "A", "Course Title": "DAA",
             "Course Instructor": "Mr. Shah", "CHs": 3, "For": "BAI", "Exp Nos": 45},
            {"Code": None, "Sec": None, "Course Title": None,
             "Course Instructor": None, "CHs": None, "For": None, "Exp Nos": None},
        ])
        courses = CourseParser(path).parse()
        assert len(courses) == 1

    def test_deduplicates_same_unique_id(self):
        path = _make_courses_excel([
            {"Code": "CS478", "Sec": "A", "Course Title": "DAA",
             "Course Instructor": "Mr. Shah", "CHs": 3, "For": "BAI", "Exp Nos": 45},
            {"Code": "CS478", "Sec": "A", "Course Title": "DAA Updated",
             "Course Instructor": "Mr. Shah", "CHs": 3, "For": "BAI", "Exp Nos": 45},
        ])
        courses = CourseParser(path).parse()
        assert len(courses) == 1
        assert courses[0].title == "DAA Updated"    # last row wins

    def test_tba_instructor_normalised(self):
        path = _make_courses_excel([{
            "Code": "CS311", "Sec": "C",
            "Course Title": "Operating Systems",
            "Course Instructor": "TBD",
            "CHs": 3, "For": "BCS", "Exp Nos": 40,
        }])
        courses = CourseParser(path).parse()
        assert courses[0].instructor == "TBA"

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            CourseParser(Path("nonexistent.xlsx")).parse()

    def test_summary_counts(self):
        path = _make_courses_excel([
            {"Code": "CS478",  "Sec": "A", "Course Title": "DAA",
             "Course Instructor": "Mr. Shah", "CHs": 3, "For": "BAI", "Exp Nos": 45},
            {"Code": "CS221L", "Sec": "A", "Course Title": "DSA Lab",
             "Course Instructor": "Mr. Naeem", "CHs": 1, "For": "BAI", "Exp Nos": 25},
        ])
        parser = CourseParser(path)
        parser.parse()
        s = parser.summary()
        assert s["total"] == 2
        assert s["lectures"] == 1
        assert s["labs"] == 1


# ── TimetableParser tests ─────────────────────────────────────────────────────

class TestTimetableParser:

    def test_defaults_loaded_when_no_file(self):
        tt = TimetableParser(None)
        assert len(tt.rooms) > 0
        assert len(tt.slots) > 0

    def test_default_slot_count(self):
        tt = TimetableParser(None)
        # 5 days × 8 slots each
        assert len(tt.slots) == 40

    def test_default_room_types(self):
        tt = TimetableParser(None)
        labs     = tt.rooms_of_type(RoomType.LAB)
        lectures = tt.rooms_of_type(RoomType.LECTURE)
        assert len(labs) > 0
        assert len(lectures) > 0

    def test_slots_sorted_chronologically(self):
        tt = TimetableParser(None)
        for i in range(len(tt.slots) - 1):
            assert tt.slots[i] <= tt.slots[i + 1]

    def test_slot_indices_per_day(self):
        tt = TimetableParser(None)
        mon_slots = tt.slots_for_day("Monday")
        for i, s in enumerate(mon_slots):
            assert s.index == i

    def test_lab_blocks_are_adjacent(self):
        tt = TimetableParser(None)
        blocks = tt.lab_blocks(length=2)
        assert len(blocks) > 0
        for block in blocks:
            assert len(block.slots) == 2
            assert block.slots[0].is_adjacent_to(block.slots[1])
            assert block.slots[0].day == block.slots[1].day

    def test_lab_blocks_all_same_day(self):
        tt = TimetableParser(None)
        for block in tt.lab_blocks(length=2):
            days = {s.day for s in block.slots}
            assert len(days) == 1

    def test_summary_keys(self):
        tt = TimetableParser(None)
        s = tt.summary()
        assert "rooms" in s and "slots" in s and "days" in s