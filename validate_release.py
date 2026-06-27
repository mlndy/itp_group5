"""Repository-root entrypoint for v1.1 release validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCHEDULER_DIR = Path(__file__).resolve().parent / "timetable_scheduler"
VALIDATOR_PATH = SCHEDULER_DIR / "validate_release.py"

if str(SCHEDULER_DIR) not in sys.path:
    sys.path.insert(0, str(SCHEDULER_DIR))

spec = importlib.util.spec_from_file_location("_timetable_scheduler_validate_release", VALIDATOR_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - importlib defensive branch
    raise ImportError(f"Could not load release validator from {VALIDATOR_PATH}")

module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

ReleaseValidationResult = module.ReleaseValidationResult
validate_release = module.validate_release
parse_args = module.parse_args
main = module.main

if __name__ == "__main__":
    sys.exit(main())
