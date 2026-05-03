"""
slot.py
Represents a single schedulable time slot on a given weekday.

TimeSlot objects are the "when" dimension of the timetable.
The scheduler assigns each Course to exactly one TimeSlot (for lectures)
or a consecutive block of TimeSlots (for labs).

Slot ordering and adjacency are critical for:
  - Enforcing no-overlap between courses in the same room / same instructor
  - Finding consecutive slots for lab courses
  - Soft constraint: minimizing gaps in student schedules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time


def _parse_time(t_str: str) -> time:
    """
    Parse a time string into a datetime.time object.

    Accepts formats:
        "08:00"   → time(8, 0)
        "8:00"    → time(8, 0)
        "14:30"   → time(14, 30)
        "08:00 AM"→ time(8, 0)
    """
    t_str = t_str.strip().upper().replace(" AM", "").replace(" PM", "")
    parts = t_str.split(":")
    return time(int(parts[0]), int(parts[1]))


@dataclass(order=True)
class TimeSlot:
    """
    A time slot on a specific weekday.

    Attributes
    ----------
    day : str
        Day of the week: "Monday" | "Tuesday" | ... | "Friday".
    start_time : str
        Slot start in "HH:MM" format, e.g. "08:00".
    end_time : str
        Slot end in "HH:MM" format, e.g. "08:50".
    index : int
        Zero-based position of this slot within the day's ordered slot list.
        Set by TimetableParser after all slots for a day are collected.
        Used for O(1) adjacency checks.

    Sort order
    ----------
    Slots are ordered by (day_index, start_time) so that sorting a list of
    TimeSlots gives a chronological order across the week.
    """

    # Sort key is computed in __post_init__ and stored in _sort_key
    _sort_key: tuple = field(init=False, repr=False, compare=True)

    day:        str
    start_time: str
    end_time:   str
    index:      int = field(default=0, compare=False)

    # Weekday ordering for sort key
    _DAY_ORDER: dict[str, int] = field(
        default_factory=lambda: {
            "Monday": 0, "Tuesday": 1, "Wednesday": 2,
            "Thursday": 3, "Friday": 4,
        },
        init=False, repr=False, compare=False,
    )

    def __post_init__(self):
        self._start = _parse_time(self.start_time)
        self._end   = _parse_time(self.end_time)
        day_idx     = self._DAY_ORDER.get(self.day, 99)
        self._sort_key = (day_idx, self._start.hour, self._start.minute)

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def start(self) -> time:
        """Parsed start time as datetime.time."""
        return self._start

    @property
    def end(self) -> time:
        """Parsed end time as datetime.time."""
        return self._end

    @property
    def duration_minutes(self) -> int:
        """Duration of this slot in minutes."""
        return (self._end.hour * 60 + self._end.minute) - \
               (self._start.hour * 60 + self._start.minute)

    @property
    def label(self) -> str:
        """Human-readable label, e.g. '08:00–08:50'."""
        return f"{self.start_time}–{self.end_time}"

    @property
    def unique_id(self) -> str:
        """Unique string key for use in hash maps: 'Monday_08:00'."""
        return f"{self.day}_{self.start_time}"

    # ── Adjacency ─────────────────────────────────────────────────────────────

    def is_adjacent_to(self, other: TimeSlot) -> bool:
        """
        Return True if 'other' starts immediately after this slot ends
        on the same day (with a tolerance of ±5 minutes for break gaps).

        Used by the scheduler to find consecutive lab blocks.
        """
        if self.day != other.day:
            return False
        self_end_min  = self._end.hour   * 60 + self._end.minute
        other_start_m = other._start.hour * 60 + other._start.minute
        gap = other_start_m - self_end_min
        return 0 <= gap <= 10      # allow up to 10-minute break between slots

    def overlaps_with(self, other: TimeSlot) -> bool:
        """
        Return True if this slot and 'other' overlap in time on the same day.
        Used in constraint checking.
        """
        if self.day != other.day:
            return False
        return self._start < other._end and other._start < self._end

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "day":        self.day,
            "start_time": self.start_time,
            "end_time":   self.end_time,
            "label":      self.label,
            "index":      self.index,
        }

    def __repr__(self) -> str:
        return f"TimeSlot({self.day!r}, {self.label!r}, idx={self.index})"

    def __hash__(self) -> int:
        return hash(self.unique_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimeSlot):
            return NotImplemented
        return self.unique_id == other.unique_id


@dataclass
class SlotBlock:
    """
    An ordered sequence of consecutive TimeSlots used for lab scheduling.

    Attributes
    ----------
    slots : list[TimeSlot]
        Ordered list of adjacent TimeSlots that form this block.
        Must all be on the same day.
    """
    slots: list[TimeSlot]

    def __post_init__(self):
        if not self.slots:
            raise ValueError("SlotBlock must contain at least one TimeSlot.")
        days = {s.day for s in self.slots}
        if len(days) > 1:
            raise ValueError(f"SlotBlock slots span multiple days: {days}")

    @property
    def day(self) -> str:
        return self.slots[0].day

    @property
    def start_time(self) -> str:
        return self.slots[0].start_time

    @property
    def end_time(self) -> str:
        return self.slots[-1].end_time

    @property
    def label(self) -> str:
        return f"{self.start_time}–{self.end_time}"

    @property
    def duration_minutes(self) -> int:
        return sum(s.duration_minutes for s in self.slots)

    def __len__(self) -> int:
        return len(self.slots)

    def __repr__(self) -> str:
        return f"SlotBlock({self.day!r}, {self.label!r}, {len(self)} slots)"

    def __iter__(self):
        return iter(self.slots)