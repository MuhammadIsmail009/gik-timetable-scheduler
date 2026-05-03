"""
slot_manager.py
Manages all schedulable time slots for the week.

Responsibilities:
  - Load slots from TimetableParser
  - Mark break slots as blocked (breakfast + lunch)
  - Pre-compute all valid single lecture slots
  - Pre-compute all valid 3-slot consecutive lab blocks
    (blocks that don't cross any break)

Usage:
    from src.scheduler.slot_manager import SlotManager
    from src.parser.timetable_parser import TimetableParser

    tt  = TimetableParser("data/institutional_timetable.xlsx")
    sm  = SlotManager(tt.slots)

    lecture_slots = sm.lecture_slots          # list[TimeSlot]
    lab_blocks    = sm.lab_blocks             # list[list[TimeSlot]]
"""

from __future__ import annotations

from datetime import time

from config import BREAK_SLOTS, DAYS, LAB_BLOCK_LENGTH, MAX_ADJACENT_GAP_MINUTES
from src.models.slot import SlotBlock, TimeSlot

try:
    from config import BREAK_SLOTS_BY_DAY
except ImportError:
    BREAK_SLOTS_BY_DAY = {}


def _to_time(hhmm: str) -> time:
    """Parse 'HH:MM' string into datetime.time."""
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def _slot_overlaps_break(slot: TimeSlot) -> bool:
    """
    Return True if this slot overlaps with any defined break period
    for its day.

    Day-aware: Friday's grid has no breakfast break, so slots like
    10:00-10:50 must NOT be blocked there. Mon-Thu keep both breaks.
    """
    breaks = BREAK_SLOTS_BY_DAY.get(slot.day, BREAK_SLOTS)

    for break_start_str, break_end_str in breaks:
        break_start = _to_time(break_start_str)
        break_end   = _to_time(break_end_str)

        slot_start  = slot.start
        slot_end    = slot.end

        # Overlap condition: slot starts before break ends AND slot ends after break starts
        if slot_start < break_end and slot_end > break_start:
            return True

    return False


class SlotManager:
    """
    Manages valid time slots for lecture and lab scheduling.

    Parameters
    ----------
    all_slots : list[TimeSlot]
        All slots parsed from the institutional timetable (via TimetableParser).
    lab_block_length : int
        Number of consecutive slots required for a lab session. Default = 3.

    Attributes
    ----------
    lecture_slots : list[TimeSlot]
        All slots that are not blocked by a break — valid for lectures.
    lab_blocks : list[SlotBlock]
        All consecutive slot blocks of length `lab_block_length` that:
          - Are on the same day
          - Do not cross any break period
          - All individual slots are valid (not blocked)
    """

    def __init__(
        self,
        all_slots:        list[TimeSlot],
        lab_block_length: int = LAB_BLOCK_LENGTH,
    ):
        self._all_slots       = all_slots
        self._lab_block_length = lab_block_length

        self._blocked:       set[str]      = set()   # unique_ids of blocked slots
        self._lecture_slots: list[TimeSlot] = []
        self._lab_blocks:    list[SlotBlock] = []

        self._build()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def lecture_slots(self) -> list[TimeSlot]:
        """All non-blocked slots valid for lecture scheduling."""
        return list(self._lecture_slots)

    @property
    def lab_blocks(self) -> list[SlotBlock]:
        """
        All valid 3-slot consecutive blocks for lab scheduling.
        Guaranteed to not cross any break period.
        """
        return list(self._lab_blocks)

    def is_blocked(self, slot: TimeSlot) -> bool:
        """Return True if this slot falls inside a break period."""
        return slot.unique_id in self._blocked

    def slots_for_day(self, day: str) -> list[TimeSlot]:
        """Return all non-blocked lecture slots for a specific day."""
        return [s for s in self._lecture_slots if s.day == day]

    def lab_blocks_for_day(self, day: str) -> list[SlotBlock]:
        """Return all valid lab blocks for a specific day."""
        return [b for b in self._lab_blocks if b.day == day]

    def summary(self) -> dict:
        """Quick summary for debugging."""
        return {
            "total_slots":    len(self._all_slots),
            "blocked_slots":  len(self._blocked),
            "lecture_slots":  len(self._lecture_slots),
            "lab_blocks":     len(self._lab_blocks),
            "days_covered":   len({s.day for s in self._lecture_slots}),
        }

    # ── Internal build ────────────────────────────────────────────────────────

    def _build(self):
        """
        Step 1: Mark blocked slots.
        Step 2: Build lecture slot list.
        Step 3: Pre-compute valid lab blocks.
        """
        self._mark_breaks()
        self._build_lecture_slots()
        self._build_lab_blocks()

    def _mark_breaks(self):
        """
        Mark any slot that overlaps a break period as blocked.
        Stores their unique_ids in self._blocked.
        """
        for slot in self._all_slots:
            if _slot_overlaps_break(slot):
                self._blocked.add(slot.unique_id)

    def _build_lecture_slots(self):
        """
        Collect all slots that are NOT blocked.
        These are valid for lecture assignment.
        """
        self._lecture_slots = [
            s for s in self._all_slots
            if s.unique_id not in self._blocked
        ]

    def _build_lab_blocks(self):
        """
        Pre-compute all valid consecutive lab blocks.

        A block is valid if:
          1. All slots are on the same day
          2. All slots are non-blocked (don't fall in a break)
          3. Consecutive slots are adjacent (gap <= MAX_ADJACENT_GAP_MINUTES)
          4. The block has exactly lab_block_length slots

        Iterates day by day for clarity and correctness.
        """
        blocks: list[SlotBlock] = []

        for day in DAYS:
            # Get non-blocked slots for this day in chronological order
            day_slots = [
                s for s in self._all_slots
                if s.day == day and s.unique_id not in self._blocked
            ]

            # Slide a window of lab_block_length across the day's slots
            for i in range(len(day_slots) - self._lab_block_length + 1):
                window = day_slots[i : i + self._lab_block_length]

                # Check all pairs in window are adjacent
                all_adjacent = all(
                    window[j].is_adjacent_to(window[j + 1])
                    for j in range(len(window) - 1)
                )

                if all_adjacent:
                    blocks.append(SlotBlock(slots=window))

        self._lab_blocks = blocks