"""
room_allocator.py
Deterministic room assignment for lectures and labs.

For labs:
  1. Check course title against KEYWORD_LAB_MAP (keyword takes priority)
  2. Fall back to LAB_ROOM_MAP using course code prefix
  3. If primary lab room is occupied, try BACKUP_LAB_ROOMS in order

For lectures:
  1. Look up DEPT_BUILDINGS using course code prefix
  2. Return allowed building names in priority order
  3. Caller (CSPSolver) picks first conflict-free room from that building

No randomisation — always deterministic priority order.

Usage:
    from src.scheduler.room_allocator import RoomAllocator
    allocator = RoomAllocator()

    # For a lab:
    lab_rooms = allocator.get_lab_rooms(course)   # list[str], priority order

    # For a lecture:
    buildings = allocator.get_lecture_buildings(course)  # list[str]
"""

from __future__ import annotations

from config import (
    BACKUP_LAB_ROOMS,
    DEPT_BUILDINGS,
    KEYWORD_LAB_MAP,
    LAB_ROOM_MAP,
)
from src.models.course import Course


class RoomAllocator:
    """
    Determines valid rooms/buildings for a given course.

    All logic is driven by config.py mappings — no hardcoded
    if-else chains. Adding a new department or lab room only
    requires updating config.py.
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def get_lab_rooms(self, course: Course) -> list[str]:
        """
        Return an ordered list of lab room names to try for this course.

        Order:
          1. Primary room (from keyword match or prefix map)
          2. Backup rooms (from BACKUP_LAB_ROOMS)

        Parameters
        ----------
        course : Course
            Must have is_lab == True.

        Returns
        -------
        list[str]
            Lab room names in priority order. Never empty —
            falls back to "TBA" if nothing matches.
        """
        primary = self._resolve_lab_room(course)
        backups = BACKUP_LAB_ROOMS.get(primary, [])

        # Deduplicate while preserving order
        seen:   set[str]  = set()
        result: list[str] = []
        for room in [primary] + backups:
            if room not in seen:
                seen.add(room)
                result.append(room)

        return result

    def get_lecture_buildings(self, course: Course) -> list[str]:
        """
        Return an ordered list of building codes allowed for this lecture.

        Parameters
        ----------
        course : Course
            Must have is_lab == False.

        Returns
        -------
        list[str]
            Building codes in priority order (e.g. ["ACB", "FCSE"]).
            Falls back to ["ACB"] if department is unrecognised.
        """
        prefix = self._dept_prefix(course)
        return list(DEPT_BUILDINGS.get(prefix, DEPT_BUILDINGS["_"]))

    def get_primary_lab_room(self, course: Course) -> str:
        """Return only the primary lab room name (no backups)."""
        return self._resolve_lab_room(course)

    def get_primary_building(self, course: Course) -> str:
        """Return only the first/preferred building for a lecture."""
        buildings = self.get_lecture_buildings(course)
        return buildings[0] if buildings else "ACB"

    # ── Resolution logic ──────────────────────────────────────────────────────

    def _resolve_lab_room(self, course: Course) -> str:
        """
        Resolve the primary lab room for a course.

        Priority:
          1. Keyword match in course title (most specific)
          2. Course code prefix match
          3. "TBA" as last resort
        """
        title_lower = course.title.lower()

        # Step 1: keyword scan (longer keywords checked first to avoid
        # partial matches — e.g. "mass transfer" before "heat")
        for keyword in sorted(KEYWORD_LAB_MAP.keys(), key=len, reverse=True):
            if keyword in title_lower:
                return KEYWORD_LAB_MAP[keyword]

        # Step 2: prefix map
        prefix = self._dept_prefix(course)
        if prefix in LAB_ROOM_MAP:
            return LAB_ROOM_MAP[prefix]

        # Step 3: fallback
        return "TBA"

    @staticmethod
    def _dept_prefix(course: Course) -> str:
        """
        Extract the department prefix from a course code.

        Rules:
          - Strip trailing 'L' for lab courses first
            (CS221L → CS221 → CS)
          - Take leading alpha characters (up to 2)
            CS221  → CS
            EE311  → EE
            HM101  → HM
            AI321L → AI
        """
        code = course.code.upper()

        # Strip trailing L for labs
        if code.endswith("L"):
            code = code[:-1]

        # Extract leading letters (max 2)
        prefix = ""
        for ch in code:
            if ch.isalpha():
                prefix += ch
                if len(prefix) == 2:
                    break
            else:
                break

        return prefix if prefix else "_"

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def explain(self, course: Course) -> dict:
        """
        Return a human-readable explanation of the allocation decision.
        Useful for debugging and the project report.

        Example output:
        {
            "course":    "CS221L_A",
            "type":      "lab",
            "prefix":    "CS",
            "keyword":   None,
            "primary":   "FCSE - SE Lab",
            "backups":   ["FES - SE Lab", "ACB - CS Lab"],
            "buildings": None,
        }
        """
        prefix  = self._dept_prefix(course)
        keyword = None
        title_lower = course.title.lower()

        for kw in sorted(KEYWORD_LAB_MAP.keys(), key=len, reverse=True):
            if kw in title_lower:
                keyword = kw
                break

        if course.is_lab:
            primary   = self._resolve_lab_room(course)
            backups   = BACKUP_LAB_ROOMS.get(primary, [])
            buildings = None
        else:
            primary   = None
            backups   = []
            buildings = self.get_lecture_buildings(course)

        return {
            "course":    course.unique_id,
            "type":      "lab" if course.is_lab else "lecture",
            "prefix":    prefix,
            "keyword":   keyword,
            "primary":   primary,
            "backups":   backups,
            "buildings": buildings,
        }