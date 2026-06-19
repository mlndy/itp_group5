"""Build a clean source release ZIP for the timetable prototype."""

from __future__ import annotations

import fnmatch
import zipfile
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "dist" / "itp_group5_prototype.zip"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".pytest_cache",
    "__pycache__",
    "generated",
    "output_files",
    "dist",
    ".vscode",
}
EXCLUDED_FILE_PATTERNS = {
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "~$*.xlsx",
    "~$*.xlsm",
    "*.tmp",
}
REQUIRED_PATHS = {
    "README.md",
    "DEMO.md",
    "AI_USAGE_LOG.md",
    "DEMO_SCRIPT.md",
    "FINAL_RESULTS.md",
    "PRESENTATION_EVIDENCE.md",
    "RELEASE_CHECKLIST.md",
    "REPORT_EVIDENCE.md",
    "timetable_scheduler/AGENTS.md",
    "timetable_scheduler/main.py",
    "timetable_scheduler/run_ui.py",
    "timetable_scheduler/requirements.txt",
    "Data/Common Modules(Sheet1).csv",
    "Data/Requirements_ENG",
    "Data/Requirements Template.xlsx",
    "Data/TTConstraints_timetline(Constraints).xlsx",
    "Data/Uni-Wide Module.xlsx",
    "Data/Upload template_System (Template 2).xlsx",
    "Data/Venue Information(Campus Court).csv",
    "timetable_scheduler/tests",
}


@dataclass(frozen=True, slots=True)
class ReleaseBuildResult:
    """Summary of the created release ZIP."""

    output_path: Path
    file_count: int
    size_bytes: int


def is_excluded(relative_path: Path) -> bool:
    """Return True when a path should be excluded from the release ZIP."""
    if any(part in EXCLUDED_DIR_NAMES for part in relative_path.parts):
        return True
    return any(fnmatch.fnmatch(relative_path.name, pattern) for pattern in EXCLUDED_FILE_PATTERNS)


def ensure_required_files(source_root: Path) -> None:
    """Fail clearly if a required release path is missing."""
    missing = [path for path in sorted(REQUIRED_PATHS) if not (source_root / path).exists()]
    if missing:
        joined = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Required release files are missing:\n{joined}")


def iter_release_files(source_root: Path, output_path: Path) -> list[Path]:
    """Return sorted source files that should be written to the ZIP."""
    files: list[Path] = []
    resolved_output = output_path.resolve()
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root)
        if path.resolve() == resolved_output:
            continue
        if is_excluded(relative):
            continue
        files.append(relative)
    return sorted(files, key=lambda item: item.as_posix().casefold())


def build_release_zip(
    source_root: Path = PROJECT_ROOT,
    output_path: Path | None = None,
) -> ReleaseBuildResult:
    """Create the clean release ZIP and return its summary."""
    source_root = source_root.resolve()
    output_path = (output_path or source_root / "dist" / "itp_group5_prototype.zip").resolve()
    ensure_required_files(source_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    release_files = iter_release_files(source_root, output_path)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in release_files:
            archive.write(source_root / relative, relative.as_posix())

    return ReleaseBuildResult(output_path=output_path, file_count=len(release_files), size_bytes=output_path.stat().st_size)


def main() -> None:
    """Build the release ZIP from the repository root."""
    result = build_release_zip(PROJECT_ROOT, DEFAULT_OUTPUT_PATH)
    size_mb = result.size_bytes / (1024 * 1024)
    print(f"Created release ZIP: {result.output_path}")
    print(f"Files included: {result.file_count}")
    print(f"Final size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
