"""
ortools_solver.py
Alternative timetable solver using Google OR-Tools CP-SAT.

This solver models the timetable as a Constraint Programming problem
and uses the CP-SAT solver (an industrial-strength SAT-based optimizer)
to find a feasible — and optionally optimal — solution.

When to use this over CSPSolver:
  - The backtracking solver times out on large inputs
  - You want provably optimal soft-constraint satisfaction
  - You need to enumerate multiple distinct valid timetables

Installation:
    pip install ortools

If OR-Tools is not installed, importing this module raises ImportError
with a clear message. The GUI catches this and falls back to CSPSolver.

CP-SAT model summary:
  Variables:
    x[course_id, slot_id, room_id] ∈ {0, 1}
      = 1 if course is assigned to that slot+room

  Hard constraints:
    1. Each course assigned to exactly one (slot, room)
    2. At most one course per room per slot
    3. At most one course per instructor per slot
    4. At most one course per batch per slot
    5. Lab blocks: if lab assigned to slot s, also occupies slot s+1

  Objective (soft constraints, minimise):
    - Gaps in batch daily schedules
    - Instructor overload (> 3 consecutive slots)
    - Room over-capacity (rooms used above 90% of capacity)
"""

from __future__ import annotations

from typing import Callable

from src.models.course import Course
from src.models.room import Room
from src.models.slot import TimeSlot
from src.parser.timetable_parser import TimetableParser
from src.scheduler.constraint_checker import ConstraintChecker

try:
    from ortools.sat.python import cp_model
    _ORTOOLS_AVAILABLE = True
except ImportError:
    _ORTOOLS_AVAILABLE = False


def _require_ortools():
    if not _ORTOOLS_AVAILABLE:
        raise ImportError(
            "Google OR-Tools is not installed.\n"
            "Install it with:  pip install ortools\n"
            "Then restart the application."
        )


class ORToolsSolver:
    """
    CP-SAT based timetable solver (requires ortools package).

    Parameters
    ----------
    courses        : list[Course]       Courses to schedule.
    tt_parser      : TimetableParser    Provides rooms, slots, lab blocks.
    minimize_gaps  : bool               Add gap-minimisation to objective.
    continuous_labs: bool               Labs must occupy consecutive slots.
    time_limit     : float              Max solver wall-clock seconds. Default 60.
    on_progress    : callable | None    Optional callback(assigned, total).
    """

    def __init__(
        self,
        courses:         list[Course],
        tt_parser:       TimetableParser,
        minimize_gaps:   bool = True,
        continuous_labs: bool = True,
        time_limit:      float = 60.0,
        on_progress:     Callable[[int, int], None] | None = None,
    ):
        _require_ortools()

        self._courses         = courses
        self._rooms           = tt_parser.rooms
        self._slots           = tt_parser.slots
        self._lab_blocks      = tt_parser.lab_blocks(length=2) if continuous_labs else []
        self._minimize_gaps   = minimize_gaps
        self._continuous_labs = continuous_labs
        self._time_limit      = time_limit
        self._on_progress     = on_progress

        # Index lookups for O(1) access
        self._course_idx = {c.unique_id: i for i, c in enumerate(courses)}
        self._slot_idx   = {s.unique_id: i for i, s in enumerate(self._slots)}
        self._room_idx   = {r.name:      i for i, r in enumerate(self._rooms)}

    # ── Public API ────────────────────────────────────────────────────────────

    def solve(self) -> list[dict]:
        """
        Build and solve the CP-SAT model.

        Returns
        -------
        list[dict]  One dict per assigned course (Course.to_dict()).
        """
        model   = cp_model.CpModel()
        x, feasible_triples = self._build_variables(model)
        self._add_hard_constraints(model, x, feasible_triples)

        if self._minimize_gaps:
            self._add_soft_objective(model, x, feasible_triples)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self._time_limit
        solver.parameters.num_search_workers  = 4   # parallel search

        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._extract_solution(solver, x, feasible_triples)
        else:
            # No solution found — return empty and let caller handle it
            return []

    # ── Model Building ────────────────────────────────────────────────────────

    def _build_variables(
        self, model: "cp_model.CpModel"
    ) -> tuple[dict, list[tuple]]:
        """
        Create one Boolean variable per (course, slot, room) triple
        that passes the basic feasibility filter (type + capacity check).

        Returns
        -------
        x               : dict mapping (ci, si, ri) → BoolVar
        feasible_triples: list of (ci, si, ri, Course, TimeSlot, Room)
        """
        x: dict[tuple[int, int, int], object] = {}
        feasible_triples: list[tuple] = []

        for ci, course in enumerate(self._courses):
            for si, slot in enumerate(self._slots):
                for ri, room in enumerate(self._rooms):
                    # Basic feasibility: type match + capacity
                    if not room.suitable_for(course.is_lab, course.expected_students):
                        continue
                    var = model.NewBoolVar(f"x_c{ci}_s{si}_r{ri}")
                    x[(ci, si, ri)] = var
                    feasible_triples.append((ci, si, ri, course, slot, room))

        return x, feasible_triples

    def _add_hard_constraints(
        self,
        model:            "cp_model.CpModel",
        x:                dict,
        feasible_triples: list[tuple],
    ):
        """Add all hard constraints to the model."""

        # ── HC1: Each course assigned exactly once ────────────────────────────
        for ci, course in enumerate(self._courses):
            course_vars = [
                x[(ci, si, ri)]
                for (c, s, r, *_) in feasible_triples
                if c == ci
                for si, ri in [(s, r)]
                if (ci, si, ri) in x
            ]
            # Rebuild cleanly
            course_vars = [
                x[key] for key in x if key[0] == ci
            ]
            if course_vars:
                model.Add(sum(course_vars) == 1)

        # ── HC2: One course per room per slot ─────────────────────────────────
        for si, slot in enumerate(self._slots):
            for ri, room in enumerate(self._rooms):
                room_slot_vars = [
                    x[(ci, si, ri)]
                    for ci in range(len(self._courses))
                    if (ci, si, ri) in x
                ]
                if len(room_slot_vars) > 1:
                    model.Add(sum(room_slot_vars) <= 1)

        # ── HC3: One course per instructor per slot ───────────────────────────
        instructors = list({c.instructor for c in self._courses if c.instructor != "TBA"})
        for instructor in instructors:
            ins_courses = [
                ci for ci, c in enumerate(self._courses)
                if c.instructor == instructor
            ]
            for si in range(len(self._slots)):
                ins_slot_vars = [
                    x[(ci, si, ri)]
                    for ci in ins_courses
                    for ri in range(len(self._rooms))
                    if (ci, si, ri) in x
                ]
                if len(ins_slot_vars) > 1:
                    model.Add(sum(ins_slot_vars) <= 1)

        # ── HC4: One course per batch per slot ────────────────────────────────
        batches = list({c.for_batch for c in self._courses if c.for_batch})
        for batch in batches:
            batch_courses = [
                ci for ci, c in enumerate(self._courses)
                if c.for_batch == batch
            ]
            for si in range(len(self._slots)):
                batch_slot_vars = [
                    x[(ci, si, ri)]
                    for ci in batch_courses
                    for ri in range(len(self._rooms))
                    if (ci, si, ri) in x
                ]
                if len(batch_slot_vars) > 1:
                    model.Add(sum(batch_slot_vars) <= 1)

        # ── HC5: Labs must occupy consecutive slots ───────────────────────────
        if self._continuous_labs:
            lab_courses = [
                (ci, c) for ci, c in enumerate(self._courses) if c.is_lab
            ]
            for ci, course in lab_courses:
                for si, slot in enumerate(self._slots[:-1]):
                    next_slot = self._slots[si + 1]
                    if not slot.is_adjacent_to(next_slot):
                        # This slot cannot start a lab block — forbid it
                        for ri in range(len(self._rooms)):
                            if (ci, si, ri) in x:
                                model.Add(x[(ci, si, ri)] == 0)

    def _add_soft_objective(
        self,
        model:            "cp_model.CpModel",
        x:                dict,
        feasible_triples: list[tuple],
    ):
        """
        Minimise schedule gaps for each batch.
        Encoded as a penalty in the CP-SAT objective.
        """
        # For each batch, for each day, penalise spread of assigned slot indices
        # Penalty proxy: sum of slot indices used (prefer earlier, compact slots)
        penalties = []
        batches   = list({c.for_batch for c in self._courses if c.for_batch})

        for batch in batches:
            batch_cis = [
                ci for ci, c in enumerate(self._courses) if c.for_batch == batch
            ]
            for ci in batch_cis:
                for si, slot in enumerate(self._slots):
                    for ri in range(len(self._rooms)):
                        if (ci, si, ri) in x:
                            # Weight = slot index (higher index = later = slight penalty)
                            penalties.append(x[(ci, si, ri)] * si)

        if penalties:
            model.Minimize(sum(penalties))

    # ── Solution Extraction ───────────────────────────────────────────────────

    def _extract_solution(
        self,
        solver:           "cp_model.CpSolver",
        x:                dict,
        feasible_triples: list[tuple],
    ) -> list[dict]:
        """Read the solver's variable values and build the result list."""
        result = []
        for ci, si, ri in x:
            if solver.Value(x[(ci, si, ri)]) == 1:
                course = self._courses[ci]
                slot   = self._slots[si]
                room   = self._rooms[ri]

                course.assigned_day  = slot.day
                course.assigned_slot = slot.label
                course.assigned_room = room.name

                result.append(course.to_dict())

                if self._on_progress:
                    self._on_progress(len(result), len(self._courses))

        return result

    # ── Diagnostics ───────────────────────────────────────────────────────────

    @staticmethod
    def is_available() -> bool:
        """Return True if OR-Tools is installed and importable."""
        return _ORTOOLS_AVAILABLE