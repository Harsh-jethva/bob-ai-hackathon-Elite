from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR  = PROJECT_ROOT / "data" / "raw"
MODEL_DIR = PROJECT_ROOT / "models"
DATA_DIR.mkdir(parents=True, exist_ok=True); MODEL_DIR.mkdir(exist_ok=True)

CRANE_RATE_TEU_PER_H = 30      # moves per crane-hour
HORIZON_HOURS  = 72
BUCKET_HOURS   = 6             # forecast granularity
MAX_WAIT_HOURS = 12
PRIORITY_WEIGHT = {1: 3, 2: 2, 3: 1}          # 1 = highest priority
CONGESTION_THRESHOLDS = (0.4, 0.9)            # queue/berths → MEDIUM, HIGH