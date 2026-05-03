"""
constraint_checker.py
Constraint validation for multi-session timetable scheduling.

Hard constraints:
  1. No room double-booked (day, slot, room)
  2. No instructor double-booked (day, slot, instructor)
  3. Once a course is given a room, all its sessions must use that room
  4. No course can have two sessions on the same day

Soft score:
  - Penalise Monday overload (prefer Tue/Wed)
  - Penalise instructor > 3 consecutive slots in a day
"""

from __future__ import annotations
from collections import defaultdict
from src.models.course import Course
from src.models.room import Room
from src.models.slot import TimeSlot

# Day preferences are now handled by the load-balancer in csp_solver.py.
# Soft score only penalises instructor overload within a day.


class ConstraintChecker:

    def __init__(self):
        # (day, slot_label, room_name) → set of course unique_ids
        self._room_map:       dict[tuple, set[str]] = defaultdict(set)
        # (day, slot_label, instructor) → set of course unique_ids
        self._instructor_map: dict[tuple, set[str]] = defaultdict(set)
        # instructor → list of (day, slot_index)
        self._instructor_schedule: dict[str, list[tuple[str, int]]] = defaultdict(list)

    # ── Hard constraint check ─────────────────────────────────────────────────

    def is_valid(
        self,
        course:      Course,
        slot:        TimeSlot,
        room:        Room,
        extra_slots: list[TimeSlot] | None = None,
    ) -> bool:
        # Room type + capacity (once, not per slot)
        if not room.suitable_for(course.is_lab, course.expected_students):
            return False

        # Room locking: if course already has sessions, must use same room
        if course.assigned_room and course.assigned_room != room.name:
            return False

        # No two sessions on the same day
        if slot.day in course.assigned_days:
            return False

        slots_to_check = [slot] + (extra_slots or [])
        for s in slots_to_check:
            day, label = s.day, s.label

            # Room conflict
            if self._room_map[(day, label, room.name)]:
                return False

            # Instructor conflict
            if course.instructor != "TBA":
                if self._instructor_map[(day, label, course.instructor)]:
                    return False

        return True

    def check_room(self, day: str, slot_label: str, room_name: str) -> bool:
        return not bool(self._room_map[(day, slot_label, room_name)])

    def check_instructor(self, day: str, slot_label: str, instructor: str) -> bool:
        if instructor == "TBA":
            return True
        return not bool(self._instructor_map[(day, slot_label, instructor)])

    # ── Assignment / Unassignment ─────────────────────────────────────────────

    def assign(
        self,
        course:      Course,
        slot:        TimeSlot,
        room:        Room,
        extra_slots: list[TimeSlot] | None = None,
    ) -> None:
        slots_to_mark = [slot] + (extra_slots or [])
        uid = course.unique_id

        for s in slots_to_mark:
            day, label = s.day, s.label
            self._room_map[(day, label, room.name)].add(uid)
            if course.instructor != "TBA":
                self._instructor_map[(day, label, course.instructor)].add(uid)

        self._instructor_schedule[course.instructor].append((slot.day, slot.index))

        # Record EVERY slot (primary + extras) in the course's session list
        # so lab blocks appear as 3 rows in the exporter output.
        for s in slots_to_mark:
            course.add_session(s.day, s.label, room.name)

    def unassign(
        self,
        course:      Course,
        slot:        TimeSlot,
        room:        Room,
        extra_slots: list[TimeSlot] | None = None,
    ) -> None:
        slots_to_clear = [slot] + (extra_slots or [])
        uid = course.unique_id

        for s in slots_to_clear:
            day, label = s.day, s.label
            self._room_map[(day, label, room.name)].discard(uid)
            if course.instructor != "TBA":
                self._instructor_map[(day, label, course.instructor)].discard(uid)

        key = (slot.day, slot.index)
        ins_list = self._instructor_schedule[course.instructor]
        if key in ins_list:
            ins_list.remove(key)

        course.remove_last_session()

    # ── Soft score ────────────────────────────────────────────────────────────

    def soft_score(self, course: Course, slot: TimeSlot) -> float:
        """
        Return a soft-score for this (course, slot). Higher = better.
        Currently only penalises instructor overload — day preferences
        are handled by the load-balancer in CSPSolver._lecture_domain.
        """
        score = 1.0

        if course.instructor != "TBA":
            existing = [
                idx for day, idx in self._instructor_schedule[course.instructor]
                if day == slot.day
            ]
            if existing:
                consecutive = sum(1 for idx in existing if abs(idx - slot.index) <= 1)
                if consecutive >= 3:
                    score -= 0.3

        return max(0.0, score)

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def conflicts_for(self, course: Course, slot: TimeSlot, room: Room) -> list[str]:
        conflicts: list[str] = []
        day, label = slot.day, slot.label

        if course.assigned_room and course.assigned_room != room.name:
            conflicts.append(f"Room locked to '{course.assigned_room}', tried '{room.name}'")

        if slot.day in course.assigned_days:
            conflicts.append(f"Course already has a session on {slot.day}")

        if self._room_map[(day, label, room.name)]:
            conflicts.append(f"Room '{room.name}' already used by: {self._room_map[(day, label, room.name)]}")

        if course.instructor != "TBA":
            if self._instructor_map[(day, label, course.instructor)]:
                conflicts.append(f"Instructor '{course.instructor}' busy: {self._instructor_map[(day, label, course.instructor)]}")

        if not room.suitable_for(course.is_lab, course.expected_students):
            conflicts.append(f"Room capacity/type mismatch")

        return conflicts

    def stats(self) -> dict:
        return {
            "room_slots_used":       sum(len(v) for v in self._room_map.values()),
            "instructor_slots_used": sum(len(v) for v in self._instructor_map.values()),
        }