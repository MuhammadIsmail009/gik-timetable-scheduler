"""
main.py
Entry point for the GIK Timetable Scheduler.

Run with:
    python main.py              → launches the GUI
    python main.py --cli        → runs the scheduler from the command line
                                  (useful for testing without a display)
    python main.py --help       → shows usage
"""

import argparse
import sys
from pathlib import Path


def run_gui():
    """Launch the CustomTkinter GUI application."""
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print(
            "[ERROR] customtkinter is not installed.\n"
            "Install dependencies with:\n"
            "    pip install -r requirements.txt\n"
        )
        sys.exit(1)

    from gui.main_window import run
    run()


def run_cli(courses_path: Path, timetable_path: Path | None, output_path: Path):
    """
    Run the scheduler from the command line without a GUI.
    Useful for automated testing and CI pipelines.
    """
    from src.parser.course_parser import CourseParser
    from src.parser.timetable_parser import TimetableParser
    from src.scheduler.csp_solver import CSPSolver
    from src.exporter.excel_exporter import ExcelExporter

    print(f"[1/4] Parsing courses from: {courses_path}")
    courses = CourseParser(courses_path).parse()
    print(f"      → {len(courses)} courses loaded")

    print(f"[2/4] Parsing timetable from: {timetable_path or 'default GIK config'}")
    tt_parser = TimetableParser(timetable_path)
    summary = tt_parser.summary()
    print(f"      → {summary['rooms']} rooms, {summary['slots']} slots")

    def progress(assigned, total):
        bar_len = 30
        filled  = int(bar_len * assigned / max(total, 1))
        bar     = "█" * filled + "░" * (bar_len - filled)
        print(f"\r[3/4] Scheduling [{bar}] {assigned}/{total}", end="", flush=True)

    print("[3/4] Running CSP solver…")
    solver = CSPSolver(
        courses,
        tt_parser,
        minimize_gaps=True,
        continuous_labs=True,
        on_progress=progress,
    )
    result = solver.solve()
    report = solver.report()
    print()  # newline after progress bar
    print(
        f"      → {report['assigned']}/{report['total']} courses placed "
        f"in {report['elapsed_s']}s"
    )

    if report["unassigned"]:
        print(f"      ⚠  Unscheduled: {', '.join(report['unassigned_ids'])}")

    print(f"[4/4] Exporting to: {output_path}")
    saved = ExcelExporter(result).save(output_path)
    print(f"      → Saved: {saved}")
    print("\nDone ✓")


def main():
    parser = argparse.ArgumentParser(
        prog="gik-scheduler",
        description="GIK Institute Automated Timetable Scheduler",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in command-line mode (no GUI)",
    )
    parser.add_argument(
        "--courses",
        type=Path,
        default=None,
        help="Path to courses Excel file (required for --cli)",
    )
    parser.add_argument(
        "--timetable",
        type=Path,
        default=None,
        help="Path to institutional timetable Excel file (optional, uses defaults if omitted)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/timetable.xlsx"),
        help="Output Excel file path (default: output/timetable.xlsx)",
    )

    args = parser.parse_args()

    if args.cli:
        if not args.courses:
            parser.error("--courses is required when using --cli")
        if not args.courses.exists():
            parser.error(f"Courses file not found: {args.courses}")
        run_cli(args.courses, args.timetable, args.output)
    else:
        run_gui()


if __name__ == "__main__":
    main()