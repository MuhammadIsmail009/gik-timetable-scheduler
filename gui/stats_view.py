"""
stats_view.py
Statistics and summary panel shown after timetable generation.
"""

import tkinter as tk
import customtkinter as ctk
from collections import Counter

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


class StatsView(ctk.CTkFrame):

    def __init__(self, master, colors: dict, fonts: dict, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.C = colors
        self.F = fonts
        self._report: dict = {}
        self._data:   list[dict] = []

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self._build_empty()

    def _build_empty(self):
        self._empty = ctk.CTkFrame(
            self,
            fg_color=self.C["bg_surface"],
            corner_radius=8,
            border_width=1,
            border_color=self.C["border"],
        )
        self._empty.grid(row=0, column=0, sticky="nsew")
        self._empty.rowconfigure(0, weight=1)
        self._empty.columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(self._empty, fg_color="transparent")
        inner.grid(row=0, column=0)
        ctk.CTkLabel(
            inner,
            text="No data yet",
            font=self.F["heading"],
            text_color=self.C["text_secondary"],
        ).pack()
        ctk.CTkLabel(
            inner,
            text="Generate a timetable to see statistics",
            font=self.F["body"],
            text_color=self.C["text_muted"],
        ).pack(pady=(4, 0))

        self._container: ctk.CTkScrollableFrame | None = None

    def load_report(self, report: dict, data: list[dict]):
        self._report = report
        self._data   = data
        self._empty.grid_remove()

        if self._container:
            self._container.destroy()

        self._container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=self.C["border_dark"],
        )
        self._container.grid(row=0, column=0, sticky="nsew")
        self._container.columnconfigure(0, weight=1)
        self._render()

    def _render(self):
        c = self._container

        # ── Page title ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            c,
            text="Statistics",
            font=self.F["display"],
            text_color=self.C["text_primary"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        ctk.CTkLabel(
            c,
            text="Summary of the generated timetable.",
            font=self.F["body"],
            text_color=self.C["text_secondary"],
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(0, 24))

        # ── KPI cards ─────────────────────────────────────────────────────────
        r = self._report
        total          = r.get("total", 0)
        fully_assigned = r.get("fully_assigned", 0)
        partial        = r.get("partial", 0)
        unassigned     = r.get("unassigned", 0)
        elapsed        = r.get("elapsed_s", 0)
        total_sessions = len(self._data)

        kpis = ctk.CTkFrame(c, fg_color="transparent")
        kpis.grid(row=2, column=0, sticky="ew", pady=(0, 24))
        kpis.columnconfigure((0, 1, 2, 3), weight=1)

        kpi_data = [
            ("Total Courses",    str(total),          self.C["text_primary"]),
            ("Fully Scheduled",  str(fully_assigned), self.C["success"]),
            ("Partial / Missed", f"{partial} / {unassigned}", self.C["warning"]),
            ("Total Sessions",   str(total_sessions), self.C["accent"]),
        ]

        for col, (label, value, color) in enumerate(kpi_data):
            card = ctk.CTkFrame(
                kpis,
                fg_color=self.C["bg_surface"],
                corner_radius=8,
                border_width=1,
                border_color=self.C["border"],
            )
            card.grid(row=0, column=col, sticky="ew", padx=(0, 12) if col < 3 else 0)

            ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
                text_color=color,
            ).pack(padx=20, pady=(16, 2))

            ctk.CTkLabel(
                card,
                text=label,
                font=self.F["small"],
                text_color=self.C["text_muted"],
            ).pack(padx=20, pady=(0, 16))

        # ── Day distribution ──────────────────────────────────────────────────
        ctk.CTkLabel(
            c,
            text="SESSION DISTRIBUTION BY DAY",
            font=self.F["label"],
            text_color=self.C["text_muted"],
            anchor="w",
        ).grid(row=3, column=0, sticky="w", pady=(0, 10))

        dist_card = ctk.CTkFrame(
            c,
            fg_color=self.C["bg_surface"],
            corner_radius=8,
            border_width=1,
            border_color=self.C["border"],
        )
        dist_card.grid(row=4, column=0, sticky="ew", pady=(0, 24))
        dist_card.columnconfigure(0, weight=1)

        day_ctr  = Counter(item["day"] for item in self._data)
        max_val  = max(day_ctr.values(), default=1)
        ref_pct  = {"Monday": 22, "Tuesday": 26, "Wednesday": 25, "Thursday": 12, "Friday": 4}

        for i, day in enumerate(DAYS):
            row_f = ctk.CTkFrame(dist_card, fg_color="transparent")
            row_f.grid(row=i, column=0, sticky="ew", padx=20, pady=6)
            row_f.columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_f, text=day[:3],
                font=self.F["small"], text_color=self.C["text_secondary"],
                width=36, anchor="w",
            ).grid(row=0, column=0, sticky="w")

            # Actual bar
            bar_w = int((day_ctr.get(day, 0) / max_val) * 400) if max_val > 0 else 0
            bar_frame = ctk.CTkFrame(row_f, fg_color=self.C["bg_muted"], height=20, corner_radius=4)
            bar_frame.grid(row=0, column=1, sticky="ew", padx=(8, 0))
            bar_frame.columnconfigure(0, weight=1)

            if bar_w > 0:
                actual_bar = ctk.CTkFrame(
                    bar_frame,
                    fg_color=self.C["accent"],
                    height=20, corner_radius=4,
                    width=bar_w,
                )
                actual_bar.grid(row=0, column=0, sticky="w")

            count = day_ctr.get(day, 0)
            pct   = (count / max(total_sessions, 1)) * 100
            ref   = ref_pct.get(day, 0)

            ctk.CTkLabel(
                row_f,
                text=f"{count}  ({pct:.0f}%)  ref {ref}%",
                font=self.F["tiny"],
                text_color=self.C["text_muted"],
                width=120, anchor="e",
            ).grid(row=0, column=2, sticky="e", padx=(8, 0))

        # ── Unscheduled list ──────────────────────────────────────────────────
        unassigned_ids = r.get("unassigned_ids", [])
        if unassigned_ids:
            ctk.CTkLabel(
                c,
                text="UNSCHEDULED COURSES",
                font=self.F["label"],
                text_color=self.C["error"],
                anchor="w",
            ).grid(row=5, column=0, sticky="w", pady=(0, 10))

            unsched_card = ctk.CTkFrame(
                c,
                fg_color=self.C["bg_surface"],
                corner_radius=8,
                border_width=1,
                border_color="#FECACA",
            )
            unsched_card.grid(row=6, column=0, sticky="ew", pady=(0, 24))

            for i, uid in enumerate(unassigned_ids[:20]):
                ctk.CTkLabel(
                    unsched_card,
                    text=uid,
                    font=self.F["mono"],
                    text_color=self.C["error"],
                    anchor="w",
                ).grid(row=i, column=0, sticky="w", padx=20, pady=3)

            if len(unassigned_ids) > 20:
                ctk.CTkLabel(
                    unsched_card,
                    text=f"... and {len(unassigned_ids) - 20} more",
                    font=self.F["small"],
                    text_color=self.C["text_muted"],
                    anchor="w",
                ).grid(row=20, column=0, sticky="w", padx=20, pady=(0, 10))

        # ── Solver info ───────────────────────────────────────────────────────
        ctk.CTkLabel(
            c,
            text="SOLVER DETAILS",
            font=self.F["label"],
            text_color=self.C["text_muted"],
            anchor="w",
        ).grid(row=7, column=0, sticky="w", pady=(0, 10))

        solver_card = ctk.CTkFrame(
            c,
            fg_color=self.C["bg_surface"],
            corner_radius=8,
            border_width=1,
            border_color=self.C["border"],
        )
        solver_card.grid(row=8, column=0, sticky="ew", pady=(0, 24))

        details = [
            ("Algorithm",        "CSP — Iterative Greedy with Day Rotation"),
            ("Constraints",      "Room conflict · Instructor conflict · Room locking · No same-day repeat"),
            ("Solver time",      f"{elapsed}s"),
            ("Sessions placed",  str(total_sessions)),
            ("Success rate",     f"{fully_assigned / max(total, 1) * 100:.1f}%"),
        ]

        for i, (key, val) in enumerate(details):
            row_f = ctk.CTkFrame(solver_card, fg_color="transparent")
            row_f.grid(row=i, column=0, sticky="ew", padx=20, pady=5)
            row_f.columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_f, text=key,
                font=self.F["small"], text_color=self.C["text_muted"],
                width=150, anchor="w",
            ).grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(
                row_f, text=val,
                font=self.F["small"], text_color=self.C["text_primary"],
                anchor="w",
            ).grid(row=0, column=1, sticky="w", padx=(16, 0))

        # Bottom padding
        ctk.CTkLabel(solver_card, text="").grid(row=len(details), column=0, pady=4)