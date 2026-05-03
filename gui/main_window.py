"""
main_window.py
Root window and application shell for the GIK Timetable Scheduler.

Design: Clean institutional — light background, navy accent, Segoe UI typography.
No emojis, no heavy shadows, consistent 8px grid spacing.
"""

from pathlib import Path

import customtkinter as ctk

try:
    from PIL import Image
except ImportError:
    Image = None

LOGO_PATH = Path(__file__).resolve().parent.parent / "data" / "logo.jpg"

# ── Appearance ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ── Design Tokens ─────────────────────────────────────────────────────────────
COLORS = {
    # Backgrounds
    "bg_app":       "#FAFAFA",   # near-white canvas — warmer than pure grey
    "bg_surface":   "#FFFFFF",   # true white cards
    "bg_sidebar":   "#111418",   # near-black sidebar — more refined than navy
    "bg_hover":     "#F5F5F4",
    "bg_muted":     "#F3F4F6",

    # Accent — a confident slate/ink tone rather than generic blue
    "accent":       "#1E293B",   # ink / slate 800
    "accent_hover": "#0F172A",   # deeper on hover
    "accent_light": "#F1F5F9",
    "accent_text":  "#0F172A",

    # Sidebar
    "sidebar_text":      "#9CA3AF",
    "sidebar_active":    "#FFFFFF",
    "sidebar_hover":     "#1C1F25",
    "sidebar_active_bg": "#1C1F25",
    "sidebar_accent":    "#D4AF37",   # warm gold — single decorative highlight

    # Text
    "text_primary":   "#111418",
    "text_secondary": "#52525B",
    "text_muted":     "#9CA3AF",
    "text_inverse":   "#FAFAFA",

    # Semantic
    "success":  "#059669",
    "warning":  "#D97706",
    "error":    "#DC2626",
    "info":     "#0284C7",

    # Borders
    "border":      "#E5E7EB",
    "border_dark": "#D1D5DB",

    # Sidebar divider
    "divider":     "#1F2328",
}

def _build_fonts() -> dict:
    """Build font dict — must be called AFTER a Tk root window exists."""
    return {
        "display":  ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        "heading":  ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        "subhead":  ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        "body":     ctk.CTkFont(family="Segoe UI", size=13),
        "small":    ctk.CTkFont(family="Segoe UI", size=11),
        "tiny":     ctk.CTkFont(family="Segoe UI", size=10),
        "mono":     ctk.CTkFont(family="Consolas",  size=11),
        "label":    ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
    }

# FONTS is populated once the MainWindow is created
FONTS: dict = {}

# ── Navigation Items ──────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("upload",    "Generate",   "Generate timetable"),
    ("timetable", "Timetable",  "View semester schedule"),
    ("stats",     "Statistics", "Session analytics"),
]


class _NavButton(ctk.CTkFrame):
    """A single sidebar navigation button with active indicator."""

    def __init__(self, master, label: str, key: str, on_click, **kwargs):
        super().__init__(
            master,
            fg_color="transparent",
            corner_radius=6,
            cursor="hand2",
            **kwargs,
        )
        self._key      = key
        self._on_click = on_click
        self._active   = False

        self.columnconfigure(1, weight=1)

        # Active indicator bar
        self._indicator = ctk.CTkFrame(
            self, width=3, fg_color="transparent", corner_radius=2
        )
        self._indicator.grid(row=0, column=0, sticky="ns", padx=(4, 0), pady=4)

        self._label = ctk.CTkLabel(
            self,
            text=label,
            font=FONTS.get("body"),
            text_color=COLORS["sidebar_text"],
            anchor="w",
        )
        self._label.grid(row=0, column=1, sticky="ew", padx=(10, 12), pady=10)

        # Bind clicks
        for widget in (self, self._label, self._indicator):
            widget.bind("<Button-1>", lambda _: self._on_click(self._key))
            widget.bind("<Enter>",    self._on_enter)
            widget.bind("<Leave>",    self._on_leave)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self.configure(fg_color=COLORS["sidebar_active_bg"])
            self._label.configure(
                text_color=COLORS["sidebar_active"],
                font=FONTS.get("subhead"),
            )
            self._indicator.configure(fg_color=COLORS["sidebar_active"])
        else:
            self.configure(fg_color="transparent")
            self._label.configure(
                text_color=COLORS["sidebar_text"],
                font=FONTS.get("body"),
            )
            self._indicator.configure(fg_color="transparent")

    def _on_enter(self, _=None):
        if not self._active:
            self.configure(fg_color=COLORS["sidebar_hover"])

    def _on_leave(self, _=None):
        if not self._active:
            self.configure(fg_color="transparent")


class Sidebar(ctk.CTkFrame):
    """Left navigation panel — dark navy, no emojis."""

    def __init__(self, master, on_navigate, **kwargs):
        super().__init__(
            master,
            width=220,
            corner_radius=0,
            fg_color=COLORS["bg_sidebar"],
            **kwargs,
        )
        self.on_navigate = on_navigate
        self._buttons: dict[str, _NavButton] = {}
        self._active_key: str | None = None
        self._build()

    def _build(self):
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.grid_rowconfigure(10, weight=1)   # spacer

        # ── Brand ─────────────────────────────────────────────────────────────
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=24, pady=(28, 0))

        # GIK logo (if Pillow + image are available)
        if Image is not None and LOGO_PATH.exists():
            try:
                pil_img = Image.open(LOGO_PATH).convert("RGBA")
                self._logo_image = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(64, 64),
                )
                ctk.CTkLabel(
                    brand,
                    image=self._logo_image,
                    text="",
                ).pack(anchor="w", pady=(0, 8))
            except Exception:
                pass

        # Small gold accent mark
        accent_row = ctk.CTkFrame(brand, fg_color="transparent")
        accent_row.pack(anchor="w", pady=(0, 8))
        ctk.CTkFrame(
            accent_row,
            width=24, height=2,
            fg_color=COLORS["sidebar_accent"],
            corner_radius=1,
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand,
            text="Ghulam Ishaq Khan",
            font=ctk.CTkFont(family="Georgia", size=15, weight="normal"),
            text_color=COLORS["sidebar_active"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand,
            text="Scheduler",
            font=ctk.CTkFont(family="Georgia", size=15, slant="italic"),
            text_color=COLORS["sidebar_text"],
        ).pack(anchor="w", pady=(0, 2))

        # ── Divider ───────────────────────────────────────────────────────────
        ctk.CTkFrame(
            self, height=1, fg_color=COLORS["divider"]
        ).grid(row=1, column=0, sticky="ew", padx=0, pady=28)

        # ── Section label ─────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="MENU",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=2, column=0, sticky="w", padx=24, pady=(0, 10))

        # ── Nav buttons ───────────────────────────────────────────────────────
        for i, (key, label, _tooltip) in enumerate(NAV_ITEMS):
            btn = _NavButton(self, label=label, key=key, on_click=self._clicked)
            btn.grid(row=3 + i, column=0, sticky="ew", padx=12, pady=2)
            self._buttons[key] = btn

        # ── Divider ───────────────────────────────────────────────────────────
        ctk.CTkFrame(
            self, height=1, fg_color=COLORS["divider"]
        ).grid(row=10, column=0, sticky="ew", padx=0, pady=(0, 0))

        # ── Footer ────────────────────────────────────────────────────────────
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=11, column=0, sticky="ew", padx=24, pady=20)

        ctk.CTkLabel(
            footer,
            text="CS378 · Design & Analysis of Algorithms",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            footer,
            text="Fall 2025",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", pady=(2, 0))

    def _clicked(self, key: str):
        self.navigate(key)

    def navigate(self, key: str):
        if self._active_key and self._active_key in self._buttons:
            self._buttons[self._active_key].set_active(False)
        self._active_key = key
        if key in self._buttons:
            self._buttons[key].set_active(True)
        self.on_navigate(key)


class _TopBar(ctk.CTkFrame):
    """Slim top bar showing page title and breadcrumb."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            height=60,
            corner_radius=0,
            fg_color=COLORS["bg_surface"],
            **kwargs,
        )
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)

        ctk.CTkFrame(
            self, height=1, fg_color=COLORS["border"]
        ).grid(row=1, column=0, columnspan=3, sticky="ew")

        self._title = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self._title.grid(row=0, column=0, sticky="w", padx=32, pady=0)

        self._subtitle = ctk.CTkLabel(
            self,
            text="GIK Institute  ·  Engineering Sciences & Technology",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLORS["text_muted"],
            anchor="e",
        )
        self._subtitle.grid(row=0, column=1, sticky="e", padx=32, pady=0)

    def set_title(self, title: str):
        self._title.configure(text=title)


class MainWindow(ctk.CTk):
    """Root application window."""

    def __init__(self):
        super().__init__()
        # Build fonts now that the root window exists
        FONTS.update(_build_fonts())

        self.title("GIK Timetable Scheduler")
        self.geometry("1300x780")
        self.minsize(1000, 640)
        self.configure(fg_color=COLORS["bg_app"])

        # Window icon
        if Image is not None and LOGO_PATH.exists():
            try:
                from PIL import ImageTk
                self._icon_image = ImageTk.PhotoImage(Image.open(LOGO_PATH))
                self.iconphoto(True, self._icon_image)
            except Exception:
                pass

        self._views:       dict[str, ctk.CTkFrame] = {}
        self._view_titles: dict[str, str] = {
            "upload":    "Generate Timetable",
            "timetable": "Semester Timetable",
            "stats":     "Statistics",
        }

        self._build_layout()
        self._register_views()
        self.sidebar.navigate("upload")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Sidebar
        self.sidebar = Sidebar(self, on_navigate=self._switch_view)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")

        # Top bar
        self._topbar = _TopBar(self)
        self._topbar.grid(row=0, column=1, sticky="ew")

        # Content area
        self._content = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=COLORS["bg_app"],
        )
        self._content.grid(row=1, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

    # ── View Management ───────────────────────────────────────────────────────

    def _register_views(self):
        from gui.upload_panel import UploadPanel
        from gui.timetable_view import TimetableView
        from gui.stats_view import StatsView

        self._timetable_view = TimetableView(
            self._content, colors=COLORS, fonts=FONTS
        )
        self._upload_panel = UploadPanel(
            self._content,
            colors=COLORS,
            fonts=FONTS,
            on_generate=self._on_generate,
        )
        self._stats_view = StatsView(
            self._content, colors=COLORS, fonts=FONTS
        )

        self._views = {
            "upload":    self._upload_panel,
            "timetable": self._timetable_view,
            "stats":     self._stats_view,
        }

        for view in self._views.values():
            view.grid(row=0, column=0, sticky="nsew", padx=32, pady=24)

    def _switch_view(self, key: str):
        for view in self._views.values():
            view.grid_remove()
        self._views[key].grid()
        self._topbar.set_title(self._view_titles.get(key, ""))

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_generate(self, timetable_data: list[dict], report: dict = {}):
        self._timetable_view.load_data(timetable_data, report)
        self._stats_view.load_report(report, timetable_data)
        self.sidebar.navigate("timetable")


def run():
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    run()