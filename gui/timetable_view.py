"""
timetable_view.py
Semester timetable rendered as a recurring weekly room x slot grid grouped by
building and day, mirroring the Excel exporter (which mirrors the GIK Spring
2026 PDF). Friday uses a different morning slot grid (10:00 / 11:00 / 12:00)
per the PDF.

Rendering uses plain tkinter widgets (tk.Label / tk.Frame) instead of
CustomTkinter wrappers. With ~50 rooms x 5 days x 8 slots = ~2500 cells per
render, CTk widgets create a noticeable blank-screen delay; tk widgets are
single C-level widgets and complete the same render in a fraction of a second.
"""

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

SLOTS_WEEKDAY = [
    "08:00–08:50", "09:00–09:50",
    "10:30–11:20", "11:30–12:20", "12:30–13:20",
    "14:30–15:20", "15:30–16:20", "16:30–17:20",
]

SLOTS_FRIDAY = [
    "08:00–08:50", "09:00–09:50",
    "10:00–10:50", "11:00–11:50", "12:00–12:50",
    "14:30–15:20", "15:30–16:20", "16:30–17:20",
]


def slots_for_day(day: str) -> list[str]:
    return SLOTS_FRIDAY if day == "Friday" else SLOTS_WEEKDAY


# Building -> static room list, verified against PDF and the exporter.
# Labs sub-section appended dynamically based on actual virtual rooms used.
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


# Layout constants
BLDG_W   = 80
ROOM_W   = 110
CELL_W   = 130
CELL_H   = 30
HDR_H    = 28
DAY_H    = 32

FONT_SLOT = ("Segoe UI", 9)
FONT_ROOM = ("Segoe UI", 9)
FONT_BLDG = ("Segoe UI", 8)
FONT_CELL = ("Segoe UI", 8, "bold")
FONT_DAY  = ("Segoe UI", 11, "bold")


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
            command=lambda _: self._render_async(),
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
            command=lambda _: self._render_async(),
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

        # Loading overlay (used during render)
        self._loading: ctk.CTkFrame | None = None
        self._scroll_outer: ctk.CTkScrollableFrame | None = None
        self._scroll_canvas_host: tk.Frame | None = None

    # ── Data loading ─────────────────────────────────────────────────────────

    def load_data(self, data: list[dict], report: dict = {}):
        self._data = data
        self._empty.grid_remove()

        if self._scroll_outer:
            self._scroll_outer.destroy()

        # Outer CTk scrollable container
        self._scroll_outer = ctk.CTkScrollableFrame(
            self,
            corner_radius=8,
            fg_color=self.C["bg_surface"],
            border_width=1,
            border_color=self.C["border"],
            scrollbar_button_color=self.C["border_dark"],
            scrollbar_button_hover_color=self.C["accent"],
            orientation="vertical",
        )
        self._scroll_outer.grid(row=2, column=0, sticky="nsew")
        # Inner host frame uses plain tk for fast widget creation
        self._scroll_canvas_host = tk.Frame(
            self._scroll_outer, bg=self.C["bg_surface"]
        )
        self._scroll_canvas_host.pack(fill="both", expand=True, padx=8, pady=8)

        self._render_async()

    # ── Async render (so the UI shows a loading state instead of freezing) ──

    def _render_async(self):
        if not self._scroll_canvas_host:
            return
        # Show a quick "Rendering..." flash, then build on idle
        self._show_loading("Rendering timetable...")
        self.after(30, self._render)

    def _show_loading(self, text: str):
        if self._loading:
            try:
                self._loading.destroy()
            except Exception:
                pass
        self._loading = ctk.CTkFrame(
            self,
            fg_color=self.C["bg_surface"],
            corner_radius=8,
        )
        self._loading.place(in_=self._scroll_outer, relx=0.5, rely=0.05, anchor="n")
        ctk.CTkLabel(
            self._loading, text=text,
            font=self.F["small"], text_color=self.C["text_secondary"],
        ).pack(padx=18, pady=8)

    def _hide_loading(self):
        if self._loading:
            try:
                self._loading.destroy()
            except Exception:
                pass
            self._loading = None

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _virtual_lab_rooms_used(self) -> list[str]:
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

    # ── Grid render (per-day blocks, plain tk widgets) ───────────────────────

    def _render(self):
        host = self._scroll_canvas_host
        if not host:
            return

        # Clear previous content
        for w in host.winfo_children():
            w.destroy()

        day_filter  = self._filter_day.get()
        bldg_filter = self._filter_bldg.get()

        days_to_show = [d for d in DAYS if day_filter == "All Days" or d == day_filter]

        # Build lookup
        lookup: dict[tuple, list[str]] = {}
        for item in self._data:
            key = (item["day"], item["slot"], item["room"])
            text = f"{item['course']} {item['section']}"
            lookup.setdefault(key, []).append(text)

        session_count = sum(
            len(v) for k, v in lookup.items() if k[0] in days_to_show
        )
        self._stats.configure(
            text=f"{session_count} sessions  •  {len(days_to_show)} day(s)"
        )

        # Compose room list with dynamic Labs section
        groups = list(BUILDING_ROOMS)
        virtual_labs = self._virtual_lab_rooms_used()
        if virtual_labs:
            groups.append(("Labs", virtual_labs))

        # Filter groups
        if bldg_filter != "All Buildings":
            groups = [(b, rs) for b, rs in groups if b == bldg_filter]

        # Render one block per day
        for day in days_to_show:
            self._render_day_block(host, day, groups, lookup)
            # Spacer between day blocks
            tk.Frame(host, bg=self.C["bg_surface"], height=14).pack(fill="x")

        self._hide_loading()

    def _render_day_block(self, host: tk.Frame, day: str,
                          groups: list[tuple[str, list[str]]],
                          lookup: dict[tuple, list[str]]):
        slots = slots_for_day(day)
        n_cols = 2 + len(slots)  # building + room + slots

        block = tk.Frame(host, bg=self.C["bg_surface"])
        block.pack(fill="x", anchor="w")

        # Day header (full width, bold navy)
        day_header = tk.Label(
            block,
            text=day.upper(),
            bg=self.C["accent"],
            fg="#FFFFFF",
            font=FONT_DAY,
            anchor="w",
            padx=12,
        )
        day_header.grid(row=0, column=0, columnspan=n_cols, sticky="ew",
                        pady=(0, 1), ipady=4)

        # Slot header row
        tk.Label(block, text="Building", bg=self.C["bg_muted"],
                 fg=self.C["text_muted"], font=FONT_BLDG, width=10, height=2,
                 anchor="w", padx=4
        ).grid(row=1, column=0, sticky="nsew", padx=1, pady=1)
        tk.Label(block, text="Room", bg=self.C["bg_muted"],
                 fg=self.C["text_muted"], font=FONT_BLDG, width=14, height=2,
                 anchor="w", padx=4
        ).grid(row=1, column=1, sticky="nsew", padx=1, pady=1)

        for ci, slot in enumerate(slots, start=2):
            tk.Label(block, text=slot,
                     bg=self.C["bg_muted"], fg=self.C["text_secondary"],
                     font=FONT_SLOT, width=15, height=2,
                     ).grid(row=1, column=ci, sticky="nsew", padx=1, pady=1)

        # Room rows
        row_idx = 2
        for bldg, rooms in groups:
            for room_idx, room in enumerate(rooms):
                bldg_text = bldg if room_idx == 0 else ""

                tk.Label(block, text=bldg_text,
                         bg=self.C["bg_surface"], fg=self.C["text_muted"],
                         font=FONT_BLDG, anchor="w", padx=4, width=10,
                         ).grid(row=row_idx, column=0, sticky="nsew", padx=1, pady=1)

                tk.Label(block, text=room,
                         bg=self.C["bg_muted"], fg=self.C["text_primary"],
                         font=FONT_ROOM, anchor="w", padx=6, width=14,
                         ).grid(row=row_idx, column=1, sticky="nsew", padx=1, pady=1)

                for ci, slot in enumerate(slots, start=2):
                    entries = lookup.get((day, slot, room), [])
                    if entries:
                        text = " / ".join(entries)
                        bg, fg = _dept(entries[0].split()[0])
                        # Truncate long text to keep cell single-line
                        if len(text) > 22:
                            text = text[:20] + "…"
                        tk.Label(block, text=text,
                                 bg=bg, fg=fg, font=FONT_CELL,
                                 width=15,
                                 ).grid(row=row_idx, column=ci,
                                        sticky="nsew", padx=1, pady=1)
                    else:
                        tk.Label(block, text="",
                                 bg=self.C["bg_surface"], width=15,
                                 ).grid(row=row_idx, column=ci,
                                        sticky="nsew", padx=1, pady=1)

                row_idx += 1

            # Building separator row
            tk.Frame(block, bg=self.C["border"], height=2).grid(
                row=row_idx, column=0, columnspan=n_cols, sticky="ew", pady=(2, 2)
            )
            row_idx += 1

    # ── Export ───────────────────────────────────────────────────────────────

    def _export(self):
        if not self._data:
            messagebox.showinfo("No Data", "Generate a timetable first.")
            return
        from src.exporter.excel_exporter import ExcelExporter
        out = ExcelExporter(self._data).save("output/timetable.xlsx")
        messagebox.showinfo("Saved", f"Timetable exported to:\n{out}")
