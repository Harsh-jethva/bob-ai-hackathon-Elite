import joblib, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from src.config.settings import MODEL_DIR, CONGESTION_THRESHOLDS
from src.data.features import FEATURES

class CongestionModel:
    def __init__(self):
        self.model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.06)

    def fit(self, df):
        self.model.fit(df[FEATURES], df.label_queue_next6h)

    def predict(self, feats: pd.DataFrame) -> np.ndarray:
        return np.clip(self.model.predict(feats[FEATURES]), 0, None)

    @staticmethod
    def level(queue: float, n_berths: int) -> str:
        r = queue / max(n_berths, 1)
        if r >= CONGESTION_THRESHOLDS[1]: return "HIGH"
        if r >= CONGESTION_THRESHOLDS[0]: return "MEDIUM"
        return "LOW"

    def save(self, path=MODEL_DIR / "congestion.joblib"):
        joblib.dump(self.model, path)
    @classmethod
    def load(cls, path=MODEL_DIR / "congestion.joblib"):
        m = cls(); m.model = joblib.load(path); return m