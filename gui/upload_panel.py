"""
upload_panel.py
Single-action upload screen.

Design: Refined minimalism. One clear flow — select file, click generate.
No options, no info panels, no decorative elements.
"""

import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk


class UploadPanel(ctk.CTkFrame):

    def __init__(self, master, colors: dict, fonts: dict, on_generate, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.C = colors
        self.F = fonts
        self.on_generate = on_generate
        self._path: Path | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)   # vertical centering
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Centered container — gives the content breathing room
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=1, column=0, sticky="n", pady=(48, 0))
        center.columnconfigure(0, weight=1)

        # ── Overline label (small uppercase marker) ───────────────────────────
        ctk.CTkLabel(
            center,
            text="TIMETABLE GENERATOR",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self.C["accent"],
        ).grid(row=0, column=0, pady=(0, 14))

        # ── Display headline ──────────────────────────────────────────────────
        ctk.CTkLabel(
            center,
            text="Generate the semester schedule.",
            font=ctk.CTkFont(family="Georgia", size=34, weight="normal"),
            text_color=self.C["text_primary"],
        ).grid(row=1, column=0)

        # ── Subtitle ──────────────────────────────────────────────────────────
        ctk.CTkLabel(
            center,
            text="Upload your offered courses file. One click to produce a clash-free timetable.",
            font=self.F["body"],
            text_color=self.C["text_secondary"],
            wraplength=600,
        ).grid(row=2, column=0, pady=(12, 44))

        # ── File drop area (clickable, minimal) ───────────────────────────────
        self._drop = ctk.CTkFrame(
            center,
            fg_color=self.C["bg_surface"],
            corner_radius=12,
            border_width=1,
            border_color=self.C["border"],
            width=640, height=140,
        )
        self._drop.grid(row=3, column=0, sticky="ew", padx=40)
        self._drop.grid_propagate(False)
        self._drop.columnconfigure(0, weight=1)
        self._drop.rowconfigure(0, weight=1)

        drop_inner = ctk.CTkFrame(self._drop, fg_color="transparent")
        drop_inner.grid(row=0, column=0)

        self._drop_icon = ctk.CTkLabel(
            drop_inner,
            text="↑",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="normal"),
            text_color=self.C["text_muted"],
        )
        self._drop_icon.pack()

        self._drop_text = ctk.CTkLabel(
            drop_inner,
            text="Click to choose courses file",
            font=self.F["body"],
            text_color=self.C["text_secondary"],
        )
        self._drop_text.pack(pady=(6, 2))

        self._drop_hint = ctk.CTkLabel(
            drop_inner,
            text=".xlsx · Code · Section · Title · CHs · Instructor",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.C["text_muted"],
        )
        self._drop_hint.pack()

        # Make the whole drop area clickable
        for w in (self._drop, drop_inner, self._drop_icon, self._drop_text, self._drop_hint):
            w.bind("<Button-1>", lambda _: self._pick())
            w.bind("<Enter>",    lambda _: self._hover_in())
            w.bind("<Leave>",    lambda _: self._hover_out())
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

        # ── Progress (hidden initially) ───────────────────────────────────────
        self._progress_wrap = ctk.CTkFrame(center, fg_color="transparent", height=50)
        self._progress_wrap.grid(row=4, column=0, sticky="ew", padx=40, pady=(24, 0))
        self._progress_wrap.grid_propagate(False)
        self._progress_wrap.columnconfigure(0, weight=1)

        self._progress = ctk.CTkProgressBar(
            self._progress_wrap,
            mode="indeterminate",
            height=2,
            corner_radius=1,
            fg_color=self.C["border"],
            progress_color=self.C["accent"],
        )
        self._progress_label = ctk.CTkLabel(
            self._progress_wrap,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.C["text_muted"],
        )

        # ── Generate button ───────────────────────────────────────────────────
        self._btn = ctk.CTkButton(
            center,
            text="Generate Timetable",
            height=52,
            width=640,
            corner_radius=10,
            fg_color=self.C["accent"],
            hover_color=self.C["accent_hover"],
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#FFFFFF",
            command=self._start,
        )
        self._btn.grid(row=5, column=0, padx=40, pady=(32, 0))

        # ── Footer micro-text ─────────────────────────────────────────────────
        ctk.CTkLabel(
            center,
            text="Output saved to  output/timetable.xlsx",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.C["text_muted"],
        ).grid(row=6, column=0, pady=(20, 0))

    # ── Drop area interactions ────────────────────────────────────────────────

    def _hover_in(self):
        self._drop.configure(border_color=self.C["accent"], border_width=2)

    def _hover_out(self):
        self._drop.configure(border_color=self.C["border"], border_width=1)

    def _pick(self):
        path = filedialog.askopenfilename(
            title="Select Offered Courses File",
            filetypes=[("Excel files", "*.xlsx *.xls")],
        )
        if path:
            self._path = Path(path)
            # Show file selected state
            self._drop_icon.configure(
                text="✓",
                text_color=self.C["success"],
            )
            self._drop_text.configure(
                text=self._path.name,
                text_color=self.C["text_primary"],
            )
            self._drop_hint.configure(
                text="Click to change",
                text_color=self.C["text_muted"],
            )

    # ── Generation ────────────────────────────────────────────────────────────

    def _start(self):
        if not self._path:
            messagebox.showwarning("No File", "Please choose the courses file first.")
            return

        self._progress.grid(row=0, column=0, sticky="ew")
        self._progress_label.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._progress.start()
        self._progress_label.configure(text="Initialising scheduler...")

        self._btn.configure(state="disabled", text="Generating...", fg_color=self.C["text_muted"])

        threading.Thread(target=self._run, daemon=True).start()

    def _on_progress(self, assigned: int, total: int):
        pct = int((assigned / max(total, 1)) * 100)
        self.after(0, self._progress_label.configure,
                   {"text": f"Placing {assigned:,} of {total:,} sessions  ·  {pct}%"})

    def _run(self):
        try:
            from src.parser.course_parser import CourseParser
            from src.parser.timetable_parser import TimetableParser
            from src.scheduler.csp_solver import CSPSolver
            from src.exporter.excel_exporter import ExcelExporter

            courses = CourseParser(self._path).parse()
            tt      = TimetableParser(None)
            solver  = CSPSolver(
                courses, tt,
                minimize_gaps=True,
                continuous_labs=True,
                on_progress=self._on_progress,
            )
            result = solver.solve()
            report = solver.report()

            # Always auto-export
            ExcelExporter(result).save("output/timetable.xlsx")

            self.after(0, self._done, result, report)

        except Exception:
            self.after(0, self._error, traceback.format_exc())

    def _done(self, result, report):
        self._progress.stop()
        self._progress.grid_remove()
        self._progress_label.grid_remove()
        self._btn.configure(state="normal", text="Generate Timetable", fg_color=self.C["accent"])
        self.on_generate(result, report)

    def _error(self, trace: str):
        self._progress.stop()
        self._progress.grid_remove()
        self._progress_label.grid_remove()
        self._btn.configure(state="normal", text="Generate Timetable", fg_color=self.C["accent"])
        messagebox.showerror("Error", f"Scheduling failed:\n\n{trace[-800:]}")