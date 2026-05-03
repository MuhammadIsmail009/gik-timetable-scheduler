"""
timetable_view.py
Semester timetable rendered as a recurring weekly room x slot grid grouped by
building, mirroring the exporter (which mirrors the GIK Spring 2026 PDF).
Friday uses a different morning slot grid (10:00 / 11:00 / 12:00) per the PDF.
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# Mon-Thu slot order
SLOTS_WEEKDAY = [
    "08:00–08:50", "09:00–09:50",
    "10:30–11:20", "11:30–12:20", "12:30–13:20",
    "14:30–15:20", "15:30–16:20", "16:30–17:20",
]

# Friday's morning is shifted earlier per the PDF (no breakfast break,
# Jumu'ah breaks the day later instead).
SLOTS_FRIDAY = [
    "08:00–08:50", "09:00–09:50",
    "10:00–10:50", "11:00–11:50", "12:00–12:50",
    "14:30–15:20", "15:30–16:20", "16:30–17:20",
]


def slots_for_day(day: str) -> list[str]:
    return SLOTS_FRIDAY if day == "Friday" else SLOTS_WEEKDAY


# Building -> static room list, verified against PDF and the exporter.
# The Labs sub-section is appended dynamically based on actual assignments.
BUILDING_ROOMS = [
    ("FCSE / FEE", [
        "CS LH1", "CS LH2", "CS LH3", "CS LH4", "FCSE - SE Lab",
        "EE LH1", "EE LH2", "EE LH3", "EE LH4", "EE LH5", "EE LH6",
        "EE Main", "FEE Quiz Hall",
    ]),
    ("FES", [
        "ES LH1", "ES LH2", "ES LH3", "ES LH4", "ES Main",
        "FES Quiz Hall", "FES - PH Lab", "PC Lab",
    ]),
    ("Acad. Block", [
        "AcB LH1", "AcB LH2", "AcB LH3", "AcB LH4", "AcB LH5", "AcB LH6",
        "AcB LH7", "AcB LH8", "AcB LH9", "AcB LH10", "AcB LH11", "AcB LH12",
        "AcB Main1", "AcB Main2", "AcB Main3",
    ]),
    ("BB", [
        "BB Main", "BB LH2", "BB EH1", "BB EH2", "BB EH3", "BB EH4",
        "Old PC Lab", "New PC Lab", "Sem. Hall", "WR 1", "WR 2",
    ]),
    ("FME", [
        "ME LH1", "ME LH2", "ME LH3", "ME Main", "FME Quiz Hall", "TBA",
    ]),
    ("FMCE", [
        "MCE LH1", "MCE LH2", "MCE LH3", "MCE LH4", "MCE Main",
        "FMCE Quiz Hall", "Mat. Lab",
    ]),
]

ALL_STATIC_ROOMS = {r for _, rs in BUILDING_ROOMS for r in rs}

# Department fill colours
DEPT_FILLS = {
    "CS": "#DBEAFE", "CE": "#D1FAE5", "EE": "#FEF9C3",
    "ME": "#EDE9FE", "CV": "#FFE4E6", "AI": "#CFFAFE",
    "DS": "#DCFCE7", "CH": "#FFEDD5", "HM": "#E0F2FE",
    "MS": "#F3E8FF", "MM": "#CCFBF1", "PH": "#FEF9C3",
    "MT": "#FCE7F3", "ES": "#EFF6FF", "SE": "#D1FAE5",
    "CY": "#D1FAE5", "IF": "#F1F5F9", "AF": "#F3E8FF",
    "SC": "#F3E8FF", "MG": "#F3E8FF", "EM": "#F3E8FF",
    "_":  "#F8FAFC",
}
DEPT_TEXT = {
    "CS": "#1E40AF", "CE": "#065F46", "EE": "#854D0E",
    "ME": "#4C1D95", "CV": "#9F1239", "AI": "#164E63",
    "DS": "#14532D", "CH": "#9A3412", "HM": "#075985",
    "MS": "#581C87", "MM": "#134E4A", "PH": "#713F12",
    "MT": "#831843", "ES": "#1E3A8A", "SE": "#065F46",
    "CY": "#065F46", "IF": "#374151", "AF": "#581C87",
    "SC": "#581C87", "MG": "#581C87", "EM": "#581C87",
    "_":  "#475569",
}


def _dept(code: str) -> tuple[str, str]:
    prefix = code[:2].upper()
    return DEPT_FILLS.get(prefix, DEPT_FILLS["_"]), DEPT_TEXT.get(prefix, DEPT_TEXT["_"])


class TimetableView(ctk.CTkFrame):

    def __init__(self, master, colors: dict, fonts: dict, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.C = colors
        self.F = fonts
        self._data: list[dict] = []
        self._filter_day  = tk.StringVar(value="All Days")
        self._filter_bldg = tk.StringVar(value="All Buildings")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._build_toolbar()
        self._build_empty()

    # ── Toolbar ──────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = ctk.CTkFrame(
            self,
            fg_color=self.C["bg_surface"],
            corner_radius=8,
            border_width=1,
            border_color=self.C["border"],
        )
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        bar.columnconfigure(3, weight=1)

        ctk.CTkLabel(
            bar, text="Filter by day",
            font=self.F["small"], text_color=self.C["text_muted"],
        ).grid(row=0, column=0, padx=(16, 6), pady=10)

        self._day_menu = ctk.CTkOptionMenu(
            bar,
            values=["All Days"] + DAYS,
            variable=self._filter_day,
            width=140, height=32,
            fg_color=self.C["bg_muted"],
            button_color=self.C["bg_muted"],
            button_hover_color=self.C["border_dark"],
            text_color=self.C["text_primary"],
            dropdown_fg_color=self.C["bg_surface"],
            dropdown_text_color=self.C["text_primary"],
            font=self.F["small"],
            command=lambda _: self._render(),
        )
        self._day_menu.grid(row=0, column=1, padx=(0, 16), pady=10)

        ctk.CTkLabel(
            bar, text="Building",
            font=self.F["small"], text_color=self.C["text_muted"],
        ).grid(row=0, column=2, padx=(0, 6), pady=10)

        bldg_names = ["All Buildings"] + [b for b, _ in BUILDING_ROOMS] + ["Labs"]
        self._bldg_menu = ctk.CTkOptionMenu(
            bar,
            values=bldg_names,
            variable=self._filter_bldg,
            width=160, height=32,
            fg_color=self.C["bg_muted"],
            button_color=self.C["bg_muted"],
            button_hover_color=self.C["border_dark"],
            text_color=self.C["text_primary"],
            dropdown_fg_color=self.C["bg_surface"],
            dropdown_text_color=self.C["text_primary"],
            font=self.F["small"],
            command=lambda _: self._render(),
        )
        self._bldg_menu.grid(row=0, column=3, padx=(0, 16), pady=10, sticky="w")

        self._stats = ctk.CTkLabel(
            bar, text="",
            font=self.F["small"], text_color=self.C["text_muted"],
        )
        self._stats.grid(row=0, column=4, padx=16, pady=10, sticky="e")

        ctk.CTkButton(
            bar,
            text="Export Excel",
            width=110, height=32,
            corner_radius=6,
            fg_color=self.C["accent"],
            hover_color=self.C["accent_hover"],
            text_color="#FFFFFF",
            font=self.F["small"],
            command=self._export,
        ).grid(row=0, column=5, padx=16, pady=10)

    def _build_empty(self):
        self._empty = ctk.CTkFrame(
            self,
            fg_color=self.C["bg_surface"],
            corner_radius=8,
            border_width=1,
            border_color=self.C["border"],
        )
        self._empty.grid(row=2, column=0, sticky="nsew")
        self._empty.rowconfigure(0, weight=1)
        self._empty.columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(self._empty, fg_color="transparent")
        inner.grid(row=0, column=0)

        ctk.CTkLabel(
            inner,
            text="No timetable generated yet",
            font=self.F["heading"],
            text_color=self.C["text_secondary"],
        ).pack()
        ctk.CTkLabel(
            inner,
            text="Go to Generate and upload the courses file",
            font=self.F["body"],
            text_color=self.C["text_muted"],
        ).pack(pady=(4, 0))

        self._scroll: ctk.CTkScrollableFrame | None = None

    # ── Data Loading ─────────────────────────────────────────────────────────

    def load_data(self, data: list[dict], report: dict = {}):
        self._data = data
        self._empty.grid_remove()

        if self._scroll:
            self._scroll.destroy()

        self._scroll = ctk.CTkScrollableFrame(
            self,
            corner_radius=8,
            fg_color=self.C["bg_surface"],
            border_width=1,
            border_color=self.C["border"],
            scrollbar_button_color=self.C["border_dark"],
            scrollbar_button_hover_color=self.C["accent"],
            orientation="vertical",
        )
        self._scroll.grid(row=2, column=0, sticky="nsew")
        self._render()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _virtual_lab_rooms_used(self) -> list[str]:
        """Lab rooms that show up in assignments but aren't in the static grid."""
        seen: set[str] = set()
        for item in self._data:
            if not item.get("is_lab"):
                continue
            room = item.get("room", "")
            if room and room not in ALL_STATIC_ROOMS and room != "TBA":
                seen.add(room)

        def sort_key(name: str) -> tuple:
            if " #" in name:
                base, num = name.rsplit(" #", 1)
                if num.isdigit():
                    return (base, int(num))
            parts = name.rsplit(" ", 1)
            if len(parts) == 2 and parts[1].isdigit():
                return (parts[0], int(parts[1]))
            return (name, 0)

        return sorted(seen, key=sort_key)

    # ── Grid Rendering ───────────────────────────────────────────────────────

    def _render(self):
        if not self._scroll:
            return

        for w in self._scroll.winfo_children():
            w.destroy()

        day_filter  = self._filter_day.get()
        bldg_filter = self._filter_bldg.get()

        days_to_show = [d for d in DAYS if day_filter == "All Days" or d == day_filter]

        # Build lookup: (day, slot, room) -> list[course text]
        lookup: dict[tuple, list[str]] = {}
        for item in self._data:
            key = (item["day"], item["slot"], item["room"])
            text = f"{item['course']} {item['section']}"
            lookup.setdefault(key, []).append(text)

        session_count = sum(len(v) for v in lookup.values())
        self._stats.configure(
            text=f"{session_count} sessions  •  {len(days_to_show)} day(s)"
        )

        # Build the union slot grid: any slot that appears for any visible day.
        # Fr days share most columns with Mon-Thu; Friday adds 10:00/11:00/12:00.
        slot_set: list[str] = []
        for d in days_to_show:
            for s in slots_for_day(d):
                if s not in slot_set:
                    slot_set.append(s)

        def _norm(t: str) -> int:
            hh, mm = t.split("–")[0].split(":")
            return int(hh) * 60 + int(mm)

        slot_set.sort(key=_norm)

        # Layout dimensions
        ROOM_W  = 110
        BLDG_W  = 88
        CELL_W  = 130
        CELL_H  = 36
        HDR_H   = 30

        col_offset = 2  # col 0 = building, col 1 = room

        # ── Header row (sticky-ish via being row 0) ──────────────────────────
        ctk.CTkLabel(
            self._scroll, text="Building",
            font=self.F["label"], text_color=self.C["text_muted"],
            fg_color=self.C["bg_muted"], corner_radius=4,
            width=BLDG_W, height=HDR_H,
        ).grid(row=0, column=0, padx=1, pady=1, sticky="w")

        ctk.CTkLabel(
            self._scroll, text="Room",
            font=self.F["label"], text_color=self.C["text_muted"],
            fg_color=self.C["bg_muted"], corner_radius=4,
            width=ROOM_W, height=HDR_H,
        ).grid(row=0, column=1, padx=1, pady=1, sticky="w")

        col = col_offset
        col_to_day_slot: dict[int, tuple[str, str]] = {}
        for day in days_to_show:
            for slot in slot_set:
                # Greyed out if slot doesn't apply to this day
                applies = slot in slots_for_day(day)
                if applies:
                    bg = self.C["bg_muted"]
                    fg = self.C["text_secondary"]
                else:
                    bg = "#EDEEF1"
                    fg = self.C["text_muted"]

                lbl = ctk.CTkLabel(
                    self._scroll,
                    text=f"{day[:3]}\n{slot[:5]}",
                    font=self.F["tiny"],
                    text_color=fg,
                    fg_color=bg,
                    corner_radius=4,
                    width=CELL_W, height=HDR_H,
                )
                lbl.grid(row=0, column=col, padx=1, pady=1, sticky="ew")
                col_to_day_slot[col] = (day, slot)
                col += 1

        # ── Compose room list with dynamic Labs section ──────────────────────
        groups = list(BUILDING_ROOMS)
        virtual_labs = self._virtual_lab_rooms_used()
        if virtual_labs:
            groups.append(("Labs", virtual_labs))

        # ── Room rows ────────────────────────────────────────────────────────
        grid_row = 1

        for bldg, rooms in groups:
            if bldg_filter != "All Buildings" and bldg != bldg_filter:
                continue

            for room_idx, room in enumerate(rooms):
                bldg_text = bldg if room_idx == 0 else ""
                ctk.CTkLabel(
                    self._scroll,
                    text=bldg_text,
                    font=self.F["tiny"],
                    text_color=self.C["text_muted"],
                    anchor="w",
                    width=BLDG_W,
                ).grid(row=grid_row, column=0, padx=(4, 0), pady=1, sticky="w")

                ctk.CTkLabel(
                    self._scroll,
                    text=room,
                    font=self.F["small"],
                    text_color=self.C["text_primary"],
                    fg_color=self.C["bg_muted"],
                    corner_radius=4,
                    anchor="w",
                    width=ROOM_W,
                ).grid(row=grid_row, column=1, padx=1, pady=1, sticky="ew")

                col = col_offset
                for day in days_to_show:
                    for slot in slot_set:
                        applies = slot in slots_for_day(day)
                        entries = lookup.get((day, slot, room), []) if applies else []

                        if entries:
                            text = " / ".join(entries)
                            bg, fg = _dept(entries[0].split()[0])
                            cell = ctk.CTkLabel(
                                self._scroll,
                                text=text,
                                font=self.F["tiny"],
                                text_color=fg,
                                fg_color=bg,
                                corner_radius=4,
                                width=CELL_W, height=CELL_H,
                                wraplength=CELL_W - 6,
                            )
                        else:
                            # Slot doesn't apply -> dim grey; otherwise empty white
                            cell_bg = "#F0F1F4" if not applies else self.C["bg_surface"]
                            cell = ctk.CTkLabel(
                                self._scroll,
                                text="",
                                fg_color=cell_bg,
                                corner_radius=0,
                                width=CELL_W, height=CELL_H,
                            )
                        cell.grid(row=grid_row, column=col, padx=1, pady=1, sticky="ew")
                        col += 1

                grid_row += 1

            # Separator between groups
            ctk.CTkFrame(
                self._scroll, height=2, fg_color=self.C["border"]
            ).grid(row=grid_row, column=0,
                   columnspan=col_offset + len(days_to_show) * len(slot_set),
                   sticky="ew", pady=2)
            grid_row += 1

    # ── Export ───────────────────────────────────────────────────────────────

    def _export(self):
        if not self._data:
            messagebox.showinfo("No Data", "Generate a timetable first.")
            return
        from src.exporter.excel_exporter import ExcelExporter
        out = ExcelExporter(self._data).save("output/timetable.xlsx")
        messagebox.showinfo("Saved", f"Timetable exported to:\n{out}")
