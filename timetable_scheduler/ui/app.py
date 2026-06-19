"""Tkinter desktop interface for the Engineering timetable scheduler."""

from __future__ import annotations

import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from pipeline import PipelineResult
from ui.controller import (
    ControllerRunResult,
    TimetableUIController,
    build_default_ui_options,
)
from ui.styles import COLORS, configure_styles

GENERATION_PROGRESS_RE = re.compile(r"Generating timetable:\s*(\d+)\s*/\s*(\d+)")

STAGE_PROGRESS: dict[str, tuple[str, int]] = {
    "checking": ("Checking schedule", 5),
    "loading": ("Loading requirements", 10),
    "preflight": ("Preflight validation", 15),
    "generating": ("Creating timetable", 15),
    "optimising": ("Improving timetable quality", 80),
    "preparing": ("Preparing Excel files", 90),
    "validating": ("Validating results", 97),
    "complete": ("Complete", 100),
}


def generation_progress_percent(position: int, total: int) -> int:
    """Map generator course progress into the 15 to 75 percent range."""
    if total <= 0:
        return 15
    bounded = min(max(position / total, 0), 1)
    return int(round(15 + (bounded * 60)))


def progress_for_message(message: str) -> tuple[str, int]:
    """Return a user-facing stage label and approximate progress value."""
    match = GENERATION_PROGRESS_RE.search(message)
    if match:
        return STAGE_PROGRESS["generating"][0], generation_progress_percent(int(match.group(1)), int(match.group(2)))

    lower = message.lower()
    if "loading input" in lower:
        return STAGE_PROGRESS["loading"]
    if "preflight" in lower:
        return STAGE_PROGRESS["preflight"]
    if "generating timetable" in lower:
        return STAGE_PROGRESS["generating"]
    if "optimiser" in lower:
        return STAGE_PROGRESS["optimising"]
    if "stakeholder reports" in lower or "exporting proposed timetable" in lower:
        return STAGE_PROGRESS["preparing"]
    if "validating outputs" in lower:
        return STAGE_PROGRESS["validating"]
    if "completed" in lower:
        return STAGE_PROGRESS["complete"]
    return STAGE_PROGRESS["checking"]


class TimetableSchedulerApp:
    """Single-window desktop UI for the tested timetable pipeline."""

    def __init__(self, root: tk.Tk, controller: TimetableUIController | None = None) -> None:
        self.root = root
        self.controller = controller or TimetableUIController()
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.latest_result: PipelineResult | None = None
        self.screens: dict[str, ttk.Frame] = {}

        self.consolidated_schedule_path: Path | None = None
        self.selected_file_var = tk.StringVar(value="No workbook selected")
        self.validation_var = tk.StringVar(value="Select a valid Excel workbook")
        self.stage_var = tk.StringVar(value=STAGE_PROGRESS["checking"][0])
        self.percent_var = tk.StringVar(value="0%")
        self.details_visible = tk.BooleanVar(value=False)
        self.result_vars: dict[str, tk.StringVar] = {}
        self.output_buttons: dict[str, ttk.Button] = {}

        self._build_window()
        self._show_screen("input")
        self._poll_queue()

    def _build_window(self) -> None:
        """Create the root window and all screens."""
        self.root.title("Engineering Timetable Scheduler")
        self.root.geometry("760x520")
        self.root.minsize(720, 500)
        configure_styles(self.root)
        self.root.configure(bg=COLORS["window"])

        container = ttk.Frame(self.root, style="App.TFrame", padding=24)
        container.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.screens["input"] = self._build_input_screen(container)
        self.screens["loading"] = self._build_loading_screen(container)
        self.screens["complete"] = self._build_complete_screen(container)
        for screen in self.screens.values():
            screen.grid(row=0, column=0, sticky="nsew")

    def _build_input_screen(self, parent: ttk.Frame) -> ttk.Frame:
        """Build the single-workbook selection screen."""
        frame = ttk.Frame(parent, style="App.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="Engineering Timetable Scheduler", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Generate a proposed timetable from the consolidated schedule.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 28))

        card = ttk.Frame(frame, style="Card.TFrame", padding=24)
        card.grid(row=2, column=0, sticky="new")
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text="Consolidated Schedule", style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text="Select the consolidated scheduling requirements workbook.", style="Message.TLabel").grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(6, 10),
        )
        ttk.Label(card, textvariable=self.selected_file_var, style="Filename.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 14))
        ttk.Button(card, text="Browse", command=self._browse_input).grid(row=2, column=1, sticky="e", padx=(16, 0))
        ttk.Label(card, textvariable=self.validation_var, style="Message.TLabel").grid(row=3, column=0, columnspan=2, sticky="w")
        self.generate_button = ttk.Button(
            card,
            text="Generate Timetable",
            style="Primary.TButton",
            command=self._generate,
            state="disabled",
        )
        self.generate_button.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(26, 0))
        return frame

    def _build_loading_screen(self, parent: ttk.Frame) -> ttk.Frame:
        """Build the dedicated progress screen."""
        frame = ttk.Frame(parent, style="App.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)

        ttk.Label(frame, text="Creating your timetable", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Progress through processing stages", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 28))
        ttk.Label(frame, textvariable=self.stage_var, style="Stage.TLabel").grid(row=2, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(frame, mode="determinate", maximum=100, value=0, style="Dark.Horizontal.TProgressbar")
        self.progress_bar.grid(row=3, column=0, sticky="ew", pady=(12, 8))
        ttk.Label(frame, textvariable=self.percent_var, style="Message.TLabel").grid(row=4, column=0, sticky="w")

        details_frame = ttk.Frame(frame, style="App.TFrame")
        details_frame.grid(row=5, column=0, sticky="nsew", pady=(20, 0))
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(1, weight=1)
        self.details_button = ttk.Button(details_frame, text="Show details", command=self._toggle_details)
        self.details_button.grid(row=0, column=0, sticky="w")
        self.log = scrolledtext.ScrolledText(
            details_frame,
            height=8,
            wrap=tk.WORD,
            state="disabled",
            bg=COLORS["card"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
        )
        self.log.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.log.grid_remove()

        ttk.Button(frame, text="Cancel", command=self._cancel).grid(row=6, column=0, sticky="w", pady=(20, 0))
        return frame

    def _build_complete_screen(self, parent: ttk.Frame) -> ttk.Frame:
        """Build the completion screen and output actions."""
        frame = ttk.Frame(parent, style="App.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        ttk.Label(frame, text="Timetable ready", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Ready to review and export.", style="Success.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 20))

        metrics = ttk.Frame(frame, style="App.TFrame")
        metrics.grid(row=2, column=0, sticky="ew")
        for col in range(4):
            metrics.columnconfigure(col, weight=1)
        for col, label in enumerate(["Coverage", "Scheduled classes", "Classes needing review", "Hard conflicts"]):
            self.result_vars[label] = tk.StringVar(value="-")
            card = ttk.Frame(metrics, style="Card.TFrame", padding=14)
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
            ttk.Label(card, text=label, style="MetricLabel.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(card, textvariable=self.result_vars[label], style="MetricValue.TLabel", wraplength=130).grid(
                row=1,
                column=0,
                sticky="w",
                pady=(8, 0),
            )

        actions = ttk.Frame(frame, style="App.TFrame")
        actions.grid(row=3, column=0, sticky="nsew", pady=(22, 0))
        actions.columnconfigure(0, weight=1)
        for row, (key, action) in enumerate(self.controller.output_actions().items()):
            action_frame = ttk.Frame(actions, style="Surface.TFrame", padding=12)
            action_frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
            action_frame.columnconfigure(0, weight=1)
            ttk.Label(action_frame, text=action.label, style="OutputLabel.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(action_frame, text=action.description, style="Message.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
            button = ttk.Button(action_frame, text=action.label, command=lambda output_key=key: self._open_output(output_key))
            button.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))
            self.output_buttons[key] = button

        ttk.Button(frame, text="Generate Another Timetable", command=self._reset).grid(row=4, column=0, sticky="ew", pady=(10, 0))
        return frame

    def _show_screen(self, name: str) -> None:
        """Show one screen and hide the others."""
        for screen_name, screen in self.screens.items():
            if screen_name == name:
                screen.tkraise()
            else:
                screen.lower()

    def _browse_input(self) -> None:
        """Select one consolidated schedule workbook."""
        path = filedialog.askopenfilename(
            title="Select Consolidated Schedule",
            filetypes=[("Excel workbooks", "*.xlsx *.xlsm")],
        )
        if path:
            self.consolidated_schedule_path = Path(path)
            self.selected_file_var.set(self.consolidated_schedule_path.name)
            self._validate_input()

    def _validate_input(self) -> bool:
        """Validate the selected workbook and update the action state."""
        result = self.controller.validate_consolidated_schedule(self.consolidated_schedule_path)
        self.validation_var.set(result.message)
        self.generate_button.configure(state="normal" if result.valid else "disabled")
        return result.valid

    def _generate(self) -> None:
        """Start the scheduling pipeline in a worker thread."""
        if not self._validate_input() or self.consolidated_schedule_path is None:
            return
        self.cancel_event.clear()
        self.latest_result = None
        self._clear_log()
        self._set_progress(*STAGE_PROGRESS["checking"])
        self._show_screen("loading")
        options = build_default_ui_options(self.consolidated_schedule_path)

        def worker() -> None:
            run_result = self.controller.run_pipeline(options, self._worker_progress, self.cancel_event)
            self.queue.put(("done", run_result))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _worker_progress(self, message: str) -> None:
        """Receive worker progress without touching widgets."""
        self.queue.put(("progress", message))

    def _cancel(self) -> None:
        """Request cancellation between pipeline stages."""
        self.cancel_event.set()
        self._append_log("Cancellation requested. The generator may finish its current critical section first.")

    def _poll_queue(self) -> None:
        """Process worker messages on the Tkinter thread."""
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                message = str(payload)
                self._set_progress(*progress_for_message(message))
                self._append_log(message)
            elif kind == "done":
                self._handle_done(payload)
        self.root.after(150, self._poll_queue)

    def _handle_done(self, run_result: ControllerRunResult) -> None:
        """Apply completed run results to the UI."""
        if not run_result.success or run_result.result is None:
            self._show_screen("input")
            self.validation_var.set(run_result.message)
            messagebox.showerror("Engineering Timetable Scheduler", run_result.message)
            return
        self.latest_result = run_result.result
        self._set_progress(*STAGE_PROGRESS["complete"])
        for label, value in self.controller.display_values(run_result.result).items():
            self.result_vars[label].set(value)
        self._show_screen("complete")

    def _set_progress(self, stage: str, percent: int) -> None:
        """Update progress widgets from the Tkinter thread."""
        bounded = min(max(percent, 0), 100)
        self.stage_var.set(stage)
        self.percent_var.set(f"{bounded}%")
        self.progress_bar.configure(value=bounded)

    def _toggle_details(self) -> None:
        """Show or hide the technical details panel."""
        visible = not self.details_visible.get()
        self.details_visible.set(visible)
        self.details_button.configure(text="Hide details" if visible else "Show details")
        if visible:
            self.log.grid()
        else:
            self.log.grid_remove()

    def _append_log(self, message: str) -> None:
        """Append one line to the hidden progress details."""
        self.log.configure(state="normal")
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        """Clear previous technical details."""
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")

    def _open_output(self, key: str) -> None:
        """Open one generated workbook or folder."""
        result = self.controller.open_output(self.latest_result, key)
        if not result.valid:
            messagebox.showwarning("Engineering Timetable Scheduler", result.message)
        elif key == "unscheduled_review":
            messagebox.showinfo("Engineering Timetable Scheduler", result.message)

    def _reset(self) -> None:
        """Return to the file-selection screen for a new run."""
        self.consolidated_schedule_path = None
        self.latest_result = None
        self.selected_file_var.set("No workbook selected")
        self.validation_var.set("Select a valid Excel workbook")
        self.generate_button.configure(state="disabled")
        for value in self.result_vars.values():
            value.set("-")
        self._show_screen("input")


def run_app() -> None:
    """Open the desktop UI."""
    root = tk.Tk()
    TimetableSchedulerApp(root)
    root.mainloop()
