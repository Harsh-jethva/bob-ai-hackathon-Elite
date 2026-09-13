"""Run:  python check_structure.py  - verifies the project layout."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EXPECTED = [
    "src/config/__init__.py", "src/config/settings.py", "src/config/ports.py",
    "src/data/__init__.py", "src/data/generator.py", "src/data/features.py",
    "src/simulation/__init__.py", "src/simulation/port_sim.py",
    "src/models/__init__.py", "src/models/congestion_model.py", "src/models/train.py",
    "src/optimization/__init__.py", "src/optimization/router.py",
    "src/optimization/berth_allocator.py", "src/optimization/planner.py",
    "src/scenarios/__init__.py", "src/scenarios/demo.py",
    "src/app/__init__.py", "src/app/dashboard.py",
    "src/main.py", "requirements.txt",
]

problems = 0
for p in EXPECTED:
    f = ROOT / p
    if not f.exists():
        print(f"[MISSING] {p}"); problems += 1
    elif f.name == "__init__.py":
        print(f"[OK]      {p}")
    elif f.stat().st_size == 0:
        print(f"[EMPTY!]  {p}  <- paste the code into this file"); problems += 1
    else:
        print(f"[OK]      {p}")

if (ROOT / "src/config/generator.py").exists():
    print("[WRONG!]  src/config/generator.py  <- must be src/data/generator.py"); problems += 1
if (ROOT / "src/requirements.txt").exists():
    print("[WRONG!]  src/requirements.txt  <- must be at project root"); problems += 1

print("\nALL GOOD - next: pip install -r requirements.txt" if problems == 0
      else f"\n{problems} problem(s) - fix them, then re-run this script.")