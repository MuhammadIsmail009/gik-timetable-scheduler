"""
course.py
Represents a single schedulable course/lab section.

Each row from the Excel course list becomes one Course object.
The scheduler treats every Course as an independent unit to be
assigned to exactly one (TimeSlot, Room) pair — except labs,
which need a block of consecutive slots.
"""

from dataclasses import dataclass, field


@dataclass
class Course:
    """
    A single course section as read from the Excel input.

    Attributes
    ----------
    code : str
        Course code, e.g. "CS478".
    section : str
        Section identifier, e.g. "A", "B1", "A2".
    title : str
        Full course title, e.g. "Design and Analysis of Algorithms".
    instructor : str
        Full name of the assigned instructor.
    credit_hours : int
        Number of credit hours (CHs). Determines how many 50-min
        lecture slots are needed per week (1 CH ≈ 1 slot/week).
    is_lab : bool
        True if this is a lab section (course code ends with "L"
        or CHs == 1 and title contains "Lab").
    department : str
        Two-letter prefix derived from course code, e.g. "CS", "EE".
    for_batch : str
        Target student batch/programme, e.g. "BAI", "BCE".
    expected_students : int
        Expected enrollment. Used to match room capacity.
    sessions_per_week : int
        How many scheduling slots this course needs per week.
        Derived automatically:
          - Lectures: typically credit_hours slots of 50 min each.
          - Labs    : 1 block (1–2 consecutive slots, set by LAB_SLOT_LENGTH).
    preferred_days : list[str]
        Optional soft constraint. Empty means any day is fine.
    assigned_day : str | None
        Filled in by the scheduler once a day is assigned.
    assigned_slot : str | None
        Filled in by the scheduler once a time slot is assigned.
    assigned_room : str | None
        Filled in by the scheduler once a room is assigned.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    code:              str
    section:           str
    title:             str
    instructor:        str

    # ── Scheduling parameters ─────────────────────────────────────────────────
    credit_hours:      int
    is_lab:            bool = False

    # ── Student / room info ───────────────────────────────────────────────────
    for_batch:         str  = ""
    expected_students: int  = 0

    # ── Soft constraints (optional) ───────────────────────────────────────────
    preferred_days:    list[str] = field(default_factory=list)

    # ── Assigned by scheduler ─────────────────────────────────────────────────
    # Multi-session: each lecture has sessions_per_week entries
    # Each session = (day, slot_label)
    # All sessions share the same room (locked after first session)
    assigned_sessions: list[tuple[str, str]] = field(default_factory=list, init=False)
    assigned_room:     str | None = field(default=None, init=False)

    # Legacy single-session aliases (still used by exporter/GUI)
    assigned_day:      str | None = field(default=None, init=False)
    assigned_slot:     str | None = field(default=None, init=False)

    # ── Derived fields (set in __post_init__) ─────────────────────────────────
    department:        str = field(init=False)
    sessions_per_week: int = field(init=False)

    # Number of consecutive 50-min slots a lab needs in one block
    LAB_SLOT_LENGTH: int = field(default=2, init=False, repr=False)

    def __post_init__(self):
        # Department = first 2 uppercase chars of code
        self.department = self.code[:2].upper()

        # Labs are 1 block per week; lectures = 1 slot per credit hour
        if self.is_lab:
            self.sessions_per_week = 1          # 1 block (LAB_SLOT_LENGTH slots)
        else:
            self.sessions_per_week = self.credit_hours

    # ── Convenience ───────────────────────────────────────────────────────────

    @property
    def unique_id(self) -> str:
        """Unique string key used in conflict-detection hash maps."""
        return f"{self.code}_{self.section}"

    @property
    def is_assigned(self) -> bool:
        """True once all required sessions have been placed."""
        return (
            len(self.assigned_sessions) >= self.sessions_per_week
            and self.assigned_room is not None
        )

    @property
    def is_partially_assigned(self) -> bool:
        """True if at least one session has been placed."""
        return len(self.assigned_sessions) > 0

    @property
    def sessions_needed(self) -> int:
        """How many more sessions still need to be placed."""
        return max(0, self.sessions_per_week - len(self.assigned_sessions))

    @property
    def assigned_days(self) -> list[str]:
        """Days that already have a session for this course."""
        return [day for day, _ in self.assigned_sessions]

    def add_session(self, day: str, slot: str, room: str) -> None:
        """Record one session assignment."""
        self.assigned_sessions.append((day, slot))
        self.assigned_room = room
        # Update legacy fields with latest session
        self.assigned_day  = day
        self.assigned_slot = slot

    def remove_last_session(self) -> tuple[str, str] | None:
        """Remove the most recently added session (backtracking)."""
        if not self.assigned_sessions:
            return None
        day, slot = self.assigned_sessions.pop()
        if self.assigned_sessions:
            self.assigned_day  = self.assigned_sessions[-1][0]
            self.assigned_slot = self.assigned_sessions[-1][1]
        else:
            self.assigned_day  = None
            self.assigned_slot = None
            self.assigned_room = None
        return day, slot

    def reset_assignment(self) -> None:
        """Clear all sessions — used during backtracking."""
        self.assigned_sessions = []
        self.assigned_day      = None
        self.assigned_slot     = None
        self.assigned_room     = None

    def to_dict_list(self) -> list[dict]:
        """
        Return one dict per session (for exporter).
        A 3CH course returns 3 dicts, one per day.
        """
        if not self.assigned_sessions:
            return [{
                "course": self.code, "section": self.section,
                "title": self.title, "instructor": self.instructor,
                "is_lab": self.is_lab, "day": "", "slot": "",
                "room": "", "for_batch": self.for_batch,
                "students": self.expected_students,
            }]
        return [
            {
                "course":     self.code,
                "section":    self.section,
                "title":      self.title,
                "instructor": self.instructor,
                "is_lab":     self.is_lab,
                "day":        day,
                "slot":       slot,
                "room":       self.assigned_room or "",
                "for_batch":  self.for_batch,
                "students":   self.expected_students,
            }
            for day, slot in self.assigned_sessions
        ]

    def to_dict(self) -> dict:
        """Legacy single-dict (uses first session). Use to_dict_list() for full output."""
        base = self.to_dict_list()
        return base[0] if base else {}

    def __repr__(self) -> str:
        status = (
            f"{self.assigned_day} | {self.assigned_slot} | {self.assigned_room}"
            if self.is_assigned else "unassigned"
        )
        return (
            f"Course({self.unique_id!r}, "
            f"{'LAB' if self.is_lab else 'LEC'}, "
            f"{self.credit_hours}CH, "
            f"instructor={self.instructor!r}, "
            f"status={status!r})"
        )

    def __hash__(self) -> int:
        return hash(self.unique_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Course):
            return NotImplemented
        return self.unique_id == other.unique_id