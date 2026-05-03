"""
csp_solver.py
Multi-session CSP solver for GIK timetable scheduling.

Key design decisions based on reference timetable analysis:
  - Each course needs sessions_per_week slots (3CH = 3 sessions)
  - All sessions of a course use the SAME room (room locking)
  - Each session must be on a DIFFERENT day
  - Sessions spread across Tue/Wed preferred (matching reference distribution)
  - Labs scheduled first (highest constraint), then lectures
  - Instructor-load ordering within labs

Algorithm:
  1. Build ordered list of (course, session_number) pairs — each pair is one CSP variable
  2. For each variable, build domain of (slot, room) respecting all constraints
  3. Backtrack: assign, recurse, unassign on failure
  4. Timeout = accept partial solution
"""

from __future__ import annotations

import time
from typing import Callable

from src.models.course import Course
from src.models.room import Room, RoomType
from src.models.slot import TimeSlot
from src.parser.timetable_parser import TimetableParser
from src.scheduler.constraint_checker import ConstraintChecker
from src.scheduler.room_allocator import RoomAllocator
from src.scheduler.slot_manager import SlotManager

DomainValue = tuple[TimeSlot, list[TimeSlot], Room]

_BUILDING_PREFIXES: dict[str, list[str]] = {
    "ACB":  ["AcB LH"],
    "FCSE": ["CS LH"],
    "FEE":  ["EE LH", "EE Main", "FEE Quiz"],
    "FES":  ["ES LH", "ES Main", "FES Quiz"],
    "FME":  ["ME LH", "ME Main", "FME Quiz"],
    "FMCE": ["MCE LH", "MCE Main", "FMCE Quiz"],
    "BB":   ["BB LH", "BB EH", "BB Main"],
}


def _room_in_building(room: Room, building_code: str) -> bool:
    prefixes = _BUILDING_PREFIXES.get(building_code, [])
    return any(room.name.startswith(p) for p in prefixes)


class CSPSolver:
    """
    Parameters
    ----------
    courses        : list[Course]
    tt_parser      : TimetableParser
    minimize_gaps  : bool
    continuous_labs: bool
    time_limit     : float
    on_progress    : callable | None  — callback(assigned_sessions, total_sessions)
    """

    def __init__(
        self,
        courses:         list[Course],
        tt_parser:       TimetableParser,
        minimize_gaps:   bool  = True,
        continuous_labs: bool  = True,
        time_limit:      float = 120.0,
        on_progress:     Callable[[int, int], None] | None = None,
    ):
        self._courses         = courses
        self._all_rooms       = tt_parser.rooms
        self._minimize_gaps   = minimize_gaps
        self._continuous_labs = continuous_labs
        self._time_limit      = time_limit
        self._on_progress     = on_progress

        self._slot_manager    = SlotManager(tt_parser.slots)
        self._allocator       = RoomAllocator()
        self._checker         = ConstraintChecker()
        self._virtual_rooms:  dict[str, Room] = {}
        self._room_instances: dict[str, int]  = self._compute_room_instances()

        self._start_time:      float = 0.0
        self._placed_sessions: int   = 0

        # Day load counter — tracks sessions placed per day for load balancing.
        # Pre-seeded with virtual load to match reference distribution:
        #   Mon/Tue/Wed/Thu = heavy (~22% each)
        #   Friday          = light (~12%, mostly morning + labs)
        # Higher initial load on Friday => load balancer picks it last.
        self._day_load:       dict[str, int] = {
            "Monday":    0,
            "Tuesday":   0,
            "Wednesday": 0,
            "Thursday":  0,
            "Friday":    80,   # virtual load — keeps Friday lighter
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def solve(self) -> list[dict]:
        self._start_time     = time.time()
        self._placed_sessions = 0

        for c in self._courses:
            c.reset_assignment()

        # Build the variable list: each "variable" = one session of one course
        variables = self._build_variables()
        total_sessions = len(variables)

        self._backtrack(variables, 0, total_sessions)

        # Collect results — one dict per session
        result: list[dict] = []
        for c in self._courses:
            result.extend(c.to_dict_list())

        # Filter out unscheduled (empty day/slot)
        return [r for r in result if r.get("day") and r.get("slot") and r.get("room")]

    def report(self) -> dict:
        assigned   = [c for c in self._courses if c.is_assigned]
        partial    = [c for c in self._courses if c.is_partially_assigned and not c.is_assigned]
        unassigned = [c for c in self._courses if not c.is_partially_assigned]
        return {
            "total":            len(self._courses),
            "assigned":         len(assigned) + len(partial),
            "fully_assigned":   len(assigned),
            "partial":          len(partial),
            "unassigned":       len(unassigned),
            "unassigned_ids":   [c.unique_id for c in unassigned],
            "elapsed_s":        round(time.time() - self._start_time, 2),
            "slot_summary":     self._slot_manager.summary(),
            "checker":          self._checker.stats(),
        }

    # ── Variable construction ─────────────────────────────────────────────────

    def _build_variables(self) -> list[Course]:
        """
        Return ordered list of courses where each course appears
        sessions_per_week times (one entry per session needed).

        Ordering:
          1. Labs first (highest constraint)
          2. Within labs: by instructor load descending
          3. Lectures: by credit hours descending (more sessions = harder)
          4. Within same CH: alphabetical by code for determinism
        """
        from collections import Counter

        labs     = [c for c in self._courses if c.is_lab]
        lectures = [c for c in self._courses if not c.is_lab]

        inst_load = Counter(c.instructor for c in labs)

        def lab_key(c: Course) -> tuple:
            if c.instructor == "TBA":
                return (1, 0, c.code)
            return (0, -inst_load[c.instructor], c.code)

        def lec_key(c: Course) -> tuple:
            return (-c.credit_hours, -c.expected_students, c.code)

        labs_sorted = sorted(labs, key=lab_key)
        lecs_sorted = sorted(lectures, key=lec_key)

        # Expand: course appears N times (one per session needed)
        variables: list[Course] = []
        for c in labs_sorted:
            for _ in range(c.sessions_per_week):
                variables.append(c)
        for c in lecs_sorted:
            for _ in range(c.sessions_per_week):
                variables.append(c)

        return variables

    # ── Backtracking ──────────────────────────────────────────────────────────

    def _backtrack(self, variables: list[Course], index: int, total: int) -> bool:
        """
        Iterative greedy placement — no recursion to avoid stack overflow
        with 1000+ session variables.

        For each variable in order, find the best valid (slot, room) and assign.
        If no valid option exists, skip (partial solution).
        This is greedy-with-soft-score, not full backtracking, but produces
        good results fast for large instances.
        """
        for i in range(index, len(variables)):
            if time.time() - self._start_time > self._time_limit:
                break

            course = variables[i]

            # Skip if all sessions for this course already placed
            if course.sessions_needed == 0:
                continue

            domain = self._build_domain(course)

            if not domain:
                continue  # skip — no valid slot

            # NOTE: don't resort by soft_score — domain is already ordered
            # by least-loaded day (from _lecture_domain / _lab_domain).
            # Sorting would break the load balance.
            # Instead, pick the FIRST entry whose soft_score is acceptable.
            if self._minimize_gaps:
                # Stable sort by soft_score (preserves load-balanced day order
                # within same-score groups)
                domain = sorted(
                    domain,
                    key=lambda d: -self._checker.soft_score(course, d[0]),
                )

            # Take the best option (greedy)
            slot, extra_slots, room = domain[0]
            self._checker.assign(course, slot, room, extra_slots)
            self._placed_sessions += 1
            self._day_load[slot.day] = self._day_load.get(slot.day, 0) + 1

            if self._on_progress:
                self._on_progress(self._placed_sessions, total)

        return True

    # ── Domain Generation ─────────────────────────────────────────────────────

    def _build_domain(self, course: Course) -> list[DomainValue]:
        if course.is_lab and self._continuous_labs:
            return self._lab_domain(course)
        return self._lecture_domain(course)

    def _lecture_domain(self, course: Course) -> list[DomainValue]:
        """
        Build (slot, [], room) domain for a lecture session.

        Day ordering = LEAST LOADED DAY FIRST.
        This is a load-balancing heuristic: we prefer days that currently
        have fewer sessions, which naturally spreads sessions across Mon-Fri.
        Days the course already used (same-day constraint) are excluded.
        """
        allowed_buildings = self._allocator.get_lecture_buildings(course)
        candidate_rooms   = [
            r for r in self._all_rooms
            if not r.is_lab
            and any(_room_in_building(r, b) for b in allowed_buildings)
        ]

        # Capacity-aware fallback: if no room in the preferred buildings can
        # actually fit this section's enrollment, widen the search to ANY
        # lecture room with sufficient capacity (e.g. Main halls, Quiz halls
        # in other faculties). Without this, a CS section of 100 students
        # silently fails because ACB/FCSE rooms cap out at 80.
        students = course.expected_students
        if students > 0 and not any(r.capacity >= students for r in candidate_rooms):
            overflow = [
                r for r in self._all_rooms
                if not r.is_lab and r.capacity >= students
            ]
            if overflow:
                candidate_rooms = overflow

        if not candidate_rooms:
            candidate_rooms = [r for r in self._all_rooms if not r.is_lab]

        from src.models.slot import TimeSlot

        # Group slots by day
        slots_by_day: dict[str, list[TimeSlot]] = {}
        for s in self._slot_manager.lecture_slots:
            slots_by_day.setdefault(s.day, []).append(s)

        # Order days by current load (ascending) — emptiest day first
        # Exclude days the course already uses
        days_used = set(course.assigned_days)
        available_days = [d for d in self._day_load.keys() if d not in days_used]
        preferred_order = sorted(available_days, key=lambda d: self._day_load[d])

        # Build slot order: all slots from least-loaded day first.
        # On Friday, prefer MORNING slots (before 14:30) — reference shows
        # Friday afternoons are mostly labs + light make-up classes.
        ordered_slots: list[TimeSlot] = []
        for day in preferred_order:
            day_slots = slots_by_day.get(day, [])
            if day == "Friday":
                # Morning first (start_time < 14:30), then afternoon as fallback
                morning = [s for s in day_slots if s.start_time < "14:30"]
                afternoon = [s for s in day_slots if s.start_time >= "14:30"]
                ordered_slots.extend(morning + afternoon)
            else:
                ordered_slots.extend(day_slots)

        domain: list[DomainValue] = []
        for slot in ordered_slots:
            for room in candidate_rooms:
                if self._checker.is_valid(course, slot, room):
                    domain.append((slot, [], room))

        return domain

    def _lab_domain(self, course: Course) -> list[DomainValue]:
        """
        Build (primary, extras, room) domain for a lab session.
        Lab blocks ordered by least-loaded day (same load-balancing approach).

        Last-resort fallback: if primary + backups are exhausted, widen the
        candidate pool to ANY lab room. This prevents the greedy solver from
        leaving labs unassigned when the dedicated lab is saturated but
        another lab room (e.g. FBS Lab, TBA) is still free.
        """
        lab_room_names  = self._allocator.get_lab_rooms(course)
        lab_blocks      = self._slot_manager.lab_blocks

        if not lab_blocks:
            return self._lecture_domain(course)

        candidate_rooms = self._expand_lab_rooms(lab_room_names)

        # Order blocks by day load (least-loaded day first)
        days_used = set(course.assigned_days)
        ordered_blocks = sorted(
            [b for b in lab_blocks if b.day not in days_used],
            key=lambda b: self._day_load.get(b.day, 0),
        )

        def _build(rooms: list[Room]) -> list[DomainValue]:
            out: list[DomainValue] = []
            for room in rooms:
                for block in ordered_blocks:
                    primary = block.slots[0]
                    extras  = block.slots[1:]
                    if self._checker.is_valid(course, primary, room, extras):
                        out.append((primary, extras, room))
            return out

        domain = _build(candidate_rooms)
        if domain:
            return domain

        # Fallback 1: any lab room from the timetable + virtual TBAs.
        all_lab_rooms = [r for r in self._all_rooms if r.is_lab]
        # Add virtual TBA copies so a saturated environment can still place labs.
        virtual_tba = [
            self._get_virtual_room(f"TBA {i}", RoomType.LAB)
            for i in range(1, 11)
        ]
        seen_names = {r.name for r in candidate_rooms}
        fallback_rooms = [r for r in all_lab_rooms + virtual_tba if r.name not in seen_names]

        return _build(fallback_rooms)

    # ── Room helpers ──────────────────────────────────────────────────────────

    def _compute_room_instances(self) -> dict[str, int]:
        """
        Estimate how many virtual copies of each lab room are needed.

        Two demand signals are combined:
          1. PRIMARY demand — courses whose first-choice room is X.
          2. BACKUP overflow — when room Y is full, any course primaried to
             Y but listed with X as a backup may spill onto X. We add a
             discounted share so popular backup targets get extra copies.

        Without (2) the FME Lab and Mat. Lab end up saturated by ME and MM
        courses respectively, forcing late ME labs into the unassigned bucket.
        """
        import math
        from collections import Counter
        from config import BACKUP_LAB_ROOMS

        blocks_available = max(len(self._slot_manager.lab_blocks), 1)
        primary_count: Counter = Counter()

        for c in self._courses:
            if c.is_lab:
                primary = self._allocator.get_primary_lab_room(c)
                primary_count[primary] += 1

        # Spread each primary's count over its first 2 backup rooms at 50%
        # weight — a rough estimate of how often the chain spills to backups.
        overflow: Counter = Counter()
        for primary, count in primary_count.items():
            backups = BACKUP_LAB_ROOMS.get(primary, [])[:2]
            for b in backups:
                overflow[b] += count * 0.5

        instances: dict[str, int] = {}
        room_names = set(primary_count) | set(overflow)
        for room_name in room_names:
            total_demand = primary_count.get(room_name, 0) + overflow.get(room_name, 0)
            raw = math.ceil(total_demand / blocks_available)
            # Cap at a reasonable max — ten copies of any one room would
            # already give 100 weekly blocks, far beyond realistic need.
            instances[room_name] = max(1, min(raw, 10))

        return instances

    def _expand_lab_rooms(self, room_names: list[str]) -> list[Room]:
        """
        Expand a list of lab-room names into actual Room objects.

        Two cases:
        1. The room exists in the timetable (real physical lab). Use exactly
           one instance — GIK has only one FCSE-SE Lab, one ACB-AI Lab, etc.,
           and the PDF runs labs sequentially through that single room. Extra
           demand must spill to the backup chain (CyS Lab, FES-SE Lab, etc.),
           NOT to fictional "SE Lab #2" copies.
        2. The room name is virtual (no timetable match — e.g. "CV Lab",
           "TBA"). Create N parallel virtual instances sized by demand, since
           these names represent logical pools rather than specific rooms.
        """
        expanded: list[Room] = []
        seen: set[str] = set()

        for room_name in room_names:
            timetable_match = next(
                (r for r in self._all_rooms if r.name == room_name), None
            )
            if timetable_match:
                if timetable_match.name not in seen:
                    seen.add(timetable_match.name)
                    expanded.append(timetable_match)
                # Do NOT create virtual copies of real rooms — the PDF
                # explicitly only has one of each. Overflow goes to backups.
                continue

            n = self._room_instances.get(room_name, 1)
            prefix = "TBA" if room_name == "TBA" else room_name
            for i in range(1, n + 1):
                key = f"{prefix} {i}" if n > 1 else prefix
                if key not in seen:
                    seen.add(key)
                    expanded.append(self._get_virtual_room(key, RoomType.LAB))

        return expanded

    def _get_virtual_room(self, name: str, room_type: RoomType, capacity: int = 500) -> Room:
        if name not in self._virtual_rooms:
            self._virtual_rooms[name] = Room(name=name, capacity=capacity, room_type=room_type)
        return self._virtual_rooms[name]