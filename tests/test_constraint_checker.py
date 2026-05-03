"""
test_constraint_checker.py
Unit tests for ConstraintChecker — the heart of conflict detection.
Run with: python -m pytest tests/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.models.course import Course
from src.models.room import Room, RoomType
from src.models.slot import TimeSlot
from src.scheduler.constraint_checker import ConstraintChecker


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_course(code="CS478", section="A", instructor="Mr. Shah",
                batch="BAI", students=30, is_lab=False):
    return Course(
        code=code, section=section,
        title="Test Course", instructor=instructor,
        credit_hours=1 if is_lab else 3,
        is_lab=is_lab, for_batch=batch, expected_students=students,
    )

def make_slot(day="Monday", start="08:00", end="08:50"):
    return TimeSlot(day=day, start_time=start, end_time=end)

def make_room(name="FEE-1", capacity=100, is_lab=False):
    rtype = RoomType.LAB if is_lab else RoomType.LECTURE
    return Room(name=name, capacity=capacity, room_type=rtype)


# ── Basic validity ────────────────────────────────────────────────────────────

class TestBasicValidity:

    def test_fresh_checker_accepts_any_valid_assignment(self):
        checker = ConstraintChecker()
        c = make_course()
        s = make_slot()
        r = make_room()
        assert checker.is_valid(c, s, r)

    def test_room_type_mismatch_rejected(self):
        checker = ConstraintChecker()
        lab_course = make_course(is_lab=True)
        lecture_room = make_room(is_lab=False)
        s = make_slot()
        assert not checker.is_valid(lab_course, s, lecture_room)

    def test_capacity_too_small_rejected(self):
        checker = ConstraintChecker()
        c = make_course(students=100)
        r = make_room(capacity=30)
        s = make_slot()
        assert not checker.is_valid(c, s, r)

    def test_capacity_exact_accepted(self):
        checker = ConstraintChecker()
        c = make_course(students=30)
        r = make_room(capacity=30)
        s = make_slot()
        assert checker.is_valid(c, s, r)


# ── Room conflict ─────────────────────────────────────────────────────────────

class TestRoomConflict:

    def test_room_double_booking_rejected(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI")
        c2 = make_course(code="CS221", section="B", batch="BCE",
                         instructor="Mr. Qasim")
        s = make_slot()
        r = make_room()
        checker.assign(c1, s, r)
        assert not checker.is_valid(c2, s, r)

    def test_same_room_different_slot_ok(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI")
        c2 = make_course(code="CS221", section="B", batch="BCE",
                         instructor="Mr. Qasim")
        s1 = make_slot(start="08:00", end="08:50")
        s2 = make_slot(start="09:00", end="09:50")
        r  = make_room()
        checker.assign(c1, s1, r)
        assert checker.is_valid(c2, s2, r)

    def test_different_rooms_same_slot_ok(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI")
        c2 = make_course(code="CS221", section="B", batch="BCE",
                         instructor="Mr. Qasim")
        s  = make_slot()
        r1 = make_room(name="FEE-1")
        r2 = make_room(name="FEE-2")
        checker.assign(c1, s, r1)
        assert checker.is_valid(c2, s, r2)


# ── Instructor conflict ───────────────────────────────────────────────────────

class TestInstructorConflict:

    def test_same_instructor_same_slot_rejected(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI",
                         instructor="Mr. Shah")
        c2 = make_course(code="CS221", section="B", batch="BCE",
                         instructor="Mr. Shah")
        s  = make_slot()
        r1 = make_room(name="FEE-1")
        r2 = make_room(name="FEE-2")
        checker.assign(c1, s, r1)
        assert not checker.is_valid(c2, s, r2)

    def test_tba_instructor_no_conflict(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI",
                         instructor="TBA")
        c2 = make_course(code="CS221", section="B", batch="BCE",
                         instructor="TBA")
        s  = make_slot()
        r1 = make_room(name="FEE-1")
        r2 = make_room(name="FEE-2")
        checker.assign(c1, s, r1)
        assert checker.is_valid(c2, s, r2)


# ── Batch conflict ────────────────────────────────────────────────────────────

class TestBatchConflict:

    def test_same_batch_same_slot_rejected(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI",
                         instructor="Mr. Shah")
        c2 = make_course(code="CS221", section="A", batch="BAI",
                         instructor="Mr. Qasim")
        s  = make_slot()
        r1 = make_room(name="FEE-1")
        r2 = make_room(name="FEE-2")
        checker.assign(c1, s, r1)
        assert not checker.is_valid(c2, s, r2)

    def test_different_batches_same_slot_ok(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI",
                         instructor="Mr. Shah")
        c2 = make_course(code="CS478", section="B", batch="BCE",
                         instructor="Mr. Qasim")
        s  = make_slot()
        r1 = make_room(name="FEE-1")
        r2 = make_room(name="FEE-2")
        checker.assign(c1, s, r1)
        assert checker.is_valid(c2, s, r2)


# ── Backtracking (assign/unassign) ────────────────────────────────────────────

class TestBacktracking:

    def test_unassign_frees_room(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI")
        c2 = make_course(code="CS221", section="B", batch="BCE",
                         instructor="Mr. Qasim")
        s = make_slot()
        r = make_room()
        checker.assign(c1, s, r)
        assert not checker.is_valid(c2, s, r)
        checker.unassign(c1, s, r)
        assert checker.is_valid(c2, s, r)

    def test_unassign_resets_course_fields(self):
        checker = ConstraintChecker()
        c = make_course()
        s = make_slot()
        r = make_room()
        checker.assign(c, s, r)
        assert c.is_assigned
        checker.unassign(c, s, r)
        assert not c.is_assigned
        assert c.assigned_day is None
        assert c.assigned_slot is None
        assert c.assigned_room is None

    def test_assign_sets_course_fields(self):
        checker = ConstraintChecker()
        c = make_course()
        s = make_slot(day="Tuesday", start="10:00", end="10:50")
        r = make_room(name="AcB-1")
        checker.assign(c, s, r)
        assert c.assigned_day  == "Tuesday"
        assert c.assigned_slot == "10:00–10:50"
        assert c.assigned_room == "AcB-1"


# ── Lab block constraints ─────────────────────────────────────────────────────

class TestLabBlocks:

    def test_lab_valid_with_consecutive_slots(self):
        checker = ConstraintChecker()
        lab = make_course(code="CS221L", section="A", is_lab=True,
                          batch="BAI", students=25)
        s1  = make_slot(start="08:00", end="08:50")
        s2  = make_slot(start="09:00", end="09:50")
        r   = make_room(name="Lab-CS1", is_lab=True, capacity=30)
        assert checker.is_valid(lab, s1, r, extra_slots=[s2])

    def test_lab_rejected_if_second_slot_occupied(self):
        checker = ConstraintChecker()
        # Occupy the second slot with another course
        occupier = make_course(code="CS478", section="A", batch="BCE",
                               instructor="Mr. Other")
        s2 = make_slot(start="09:00", end="09:50")
        r2 = make_room(name="FEE-1")
        checker.assign(occupier, s2, r2)

        lab = make_course(code="CS221L", section="A", is_lab=True,
                          batch="BAI", students=25, instructor="Mr. Naeem")
        s1  = make_slot(start="08:00", end="08:50")
        r_lab = make_room(name="Lab-CS1", is_lab=True, capacity=30)

        # Lab needs s1 AND s2 — but s2 instructor slot is free (different room),
        # so the only real conflict here would be if batch/instructor clashes.
        # This test confirms extra_slots are checked for the lab room
        checker2 = ConstraintChecker()
        occupier2 = make_course(code="CE221", section="A",
                                batch="BAI", instructor="Mr. Naeem")
        checker2.assign(occupier2, s2, r2)
        # Now lab's instructor is busy at s2 — should be rejected
        assert not checker2.is_valid(lab, s1, r_lab, extra_slots=[s2])


# ── Diagnostics ───────────────────────────────────────────────────────────────

class TestDiagnostics:

    def test_conflicts_for_returns_messages(self):
        checker = ConstraintChecker()
        c1 = make_course(code="CS478", section="A", batch="BAI")
        c2 = make_course(code="CS221", section="B", batch="BCE",
                         instructor="Mr. Shah")
        s  = make_slot()
        r  = make_room()
        checker.assign(c1, s, r)
        c1_again = make_course(code="CS999", section="X", batch="BDS",
                               instructor="Mr. Other")
        conflicts = checker.conflicts_for(c1_again, s, r)
        assert len(conflicts) > 0
        assert any("Room" in msg for msg in conflicts)

    def test_stats_tracks_usage(self):
        checker = ConstraintChecker()
        c = make_course()
        s = make_slot()
        r = make_room()
        checker.assign(c, s, r)
        stats = checker.stats()
        assert stats["room_slots_used"] >= 1
        assert stats["instructor_slots_used"] >= 1