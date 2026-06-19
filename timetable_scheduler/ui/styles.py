"""Dark ttk styling helpers for the desktop UI."""

from __future__ import annotations

from tkinter import ttk

COLORS = {
    "window": "#111318",
    "card": "#1A1E24",
    "surface": "#222730",
    "border": "#303742",
    "text": "#F4F6F8",
    "muted": "#9CA6B4",
    "accent": "#5B8CFF",
    "success": "#39C77A",
    "warning": "#F2B84B",
    "error": "#FF6470",
    "disabled": "#6F7A88",
}


def configure_styles(root) -> None:
    """Apply a dark clam ttk style suitable for the desktop UI."""
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure(".", font=("Segoe UI", 10), background=COLORS["window"], foreground=COLORS["text"])
    style.configure("App.TFrame", background=COLORS["window"])
    style.configure("Card.TFrame", background=COLORS["card"], relief="flat")
    style.configure("Surface.TFrame", background=COLORS["surface"], relief="flat")

    style.configure("Title.TLabel", background=COLORS["window"], foreground=COLORS["text"], font=("Segoe UI", 20, "bold"))
    style.configure("Subtitle.TLabel", background=COLORS["window"], foreground=COLORS["muted"], font=("Segoe UI", 10))
    style.configure("FieldLabel.TLabel", background=COLORS["card"], foreground=COLORS["text"], font=("Segoe UI", 11, "bold"))
    style.configure("Filename.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=("Segoe UI", 10))
    style.configure("Message.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=("Segoe UI", 9))
    style.configure("Stage.TLabel", background=COLORS["window"], foreground=COLORS["text"], font=("Segoe UI", 12, "bold"))
    style.configure("Success.TLabel", background=COLORS["window"], foreground=COLORS["success"], font=("Segoe UI", 11, "bold"))
    style.configure("MetricLabel.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=("Segoe UI", 9))
    style.configure("MetricValue.TLabel", background=COLORS["card"], foreground=COLORS["text"], font=("Segoe UI", 11, "bold"))
    style.configure("OutputLabel.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Segoe UI", 10, "bold"))

    style.configure(
        "TButton",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        focusthickness=0,
        padding=(14, 8),
    )
    style.map(
        "TButton",
        background=[("disabled", COLORS["card"]), ("active", COLORS["border"])],
        foreground=[("disabled", COLORS["disabled"]), ("active", COLORS["text"])],
    )
    style.configure(
        "Primary.TButton",
        background=COLORS["accent"],
        foreground=COLORS["text"],
        bordercolor=COLORS["accent"],
        font=("Segoe UI", 10, "bold"),
        padding=(16, 10),
    )
    style.map(
        "Primary.TButton",
        background=[("disabled", COLORS["surface"]), ("active", "#729DFF")],
        foreground=[("disabled", COLORS["disabled"]), ("active", COLORS["text"])],
    )
    style.configure(
        "Dark.Horizontal.TProgressbar",
        troughcolor=COLORS["surface"],
        background=COLORS["accent"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
    )
