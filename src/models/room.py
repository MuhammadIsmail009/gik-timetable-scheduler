"""
room.py
Represents a physical room/lab available for scheduling.

Room data is parsed from the institutional timetable Excel file.
The scheduler uses Room objects to enforce:
  - No double-booking (a room can host only one class per slot)
  - Capacity matching (room.capacity >= course.expected_students)
  - Type matching (lab courses go to lab rooms; lectures go to lecture halls)
"""

from dataclasses import dataclass, field
from enum import Enum, auto


class RoomType(Enum):
    """
    Broad classification of a room.

    LECTURE : Standard classroom or lecture hall (FEE, AcB, FSCE auditoriums, etc.)
    LAB     : Computer/engineering lab (needs consecutive slots for lab courses)
    SEMINAR : Small seminar/discussion room (low capacity)
    """
    LECTURE = auto()
    LAB     = auto()
    SEMINAR = auto()


# Map common GIK room-name prefixes → RoomType
_PREFIX_TYPE_MAP: dict[str, RoomType] = {
    "Lab":   RoomType.LAB,
    "lab":   RoomType.LAB,
    "LAB":   RoomType.LAB,
    "FEE":   RoomType.LECTURE,
    "AcB":   RoomType.LECTURE,
    "FSCE":  RoomType.LECTURE,
    "Aud":   RoomType.LECTURE,
    "CR":    RoomType.SEMINAR,
    "Sem":   RoomType.SEMINAR,
}


def _infer_room_type(name: str) -> RoomType:
    """Infer RoomType from the room name using known GIK prefix conventions."""
    for prefix, rtype in _PREFIX_TYPE_MAP.items():
        if name.startswith(prefix):
            return rtype
    # Fallback: names containing 'lab' (case-insensitive)
    if "lab" in name.lower():
        return RoomType.LAB
    return RoomType.LECTURE


@dataclass
class Room:
    """
    A physical room available for scheduling.

    Attributes
    ----------
    name : str
        Room identifier exactly as it appears in the institutional timetable,
        e.g. "FEE-1", "AcB-2", "Lab-CS1".
    capacity : int
        Maximum number of students the room can hold.
    room_type : RoomType
        Lecture hall, lab, or seminar room.
        Auto-inferred from name if not provided.
    building : str
        Building identifier extracted from the room name prefix.
        Informational only (not used in hard constraints).
    available_days : list[str]
        Days this room is available. Empty list = all weekdays.
    available_slots : list[str]
        Specific slot strings this room is available for.
        Empty list = all slots defined in config.
    """

    name:            str
    capacity:        int
    room_type:       RoomType  = field(default=RoomType.LECTURE)
    building:        str       = field(default="")
    available_days:  list[str] = field(default_factory=list)
    available_slots: list[str] = field(default_factory=list)

    def __post_init__(self):
        # Auto-infer room type from name if not explicitly set
        if self.room_type == RoomType.LECTURE:
            self.room_type = _infer_room_type(self.name)

        # Auto-extract building from name prefix before first "-" or digit
        if not self.building:
            self.building = self.name.split("-")[0].rstrip("0123456789").strip()

    # ── Convenience helpers ───────────────────────────────────────────────────

    @property
    def is_lab(self) -> bool:
        return self.room_type == RoomType.LAB

    @property
    def is_lecture_hall(self) -> bool:
        return self.room_type == RoomType.LECTURE

    def can_fit(self, num_students: int) -> bool:
        """Return True if this room can accommodate the given number of students."""
        return self.capacity >= num_students

    def is_available_on(self, day: str, slot: str) -> bool:
        """
        Return True if this room is available on the given day and slot.
        An empty available_days/slots list means 'any day/slot is fine'.
        """
        day_ok  = (not self.available_days)  or (day  in self.available_days)
        slot_ok = (not self.available_slots) or (slot in self.available_slots)
        return day_ok and slot_ok

    def suitable_for(self, course_is_lab: bool, num_students: int) -> bool:
        """
        Quick check: does this room match both the course type and capacity?

        Lab courses → must be a LAB room.
        Lecture courses → must NOT be a LAB room (labs have equipment setups).
        """
        type_ok = (course_is_lab == self.is_lab)
        size_ok = self.can_fit(num_students)
        return type_ok and size_ok

    def to_dict(self) -> dict:
        """Serialize to a flat dict (useful for debugging / export)."""
        return {
            "name":      self.name,
            "capacity":  self.capacity,
            "type":      self.room_type.name,
            "building":  self.building,
        }

    def __repr__(self) -> str:
        return (
            f"Room({self.name!r}, "
            f"cap={self.capacity}, "
            f"type={self.room_type.name})"
        )

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Room):
            return NotImplemented
        return self.name == other.name