"""Forecast Virginia notifiable-disease counts a fixed horizon ahead (US-050).

Structure mirrors the county/patient models: baselines first, then a model that
has to beat them, evaluated by rolling-origin backtest rather than a random
split. Point estimates ship with a quantile interval, and a series without
enough history returns INSUFFICIENT_HISTORY instead of a confident-looking guess.

Run:
    uv run python -m src.model.forecast --backtest
    uv run python -m src.model.forecast --train
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd

from src.catalog import REPO_ROOT
from src.model import forecast_config as FC
from src.model import forecast_dataset as fd

MODEL_DIR = REPO_ROOT / "models"
MODEL_PATH = MODEL_DIR / "forecast_nndss.joblib"
METRICS_PATH = MODEL_DIR / "forecast_metrics.json"

INSUFFICIENT_HISTORY = "insufficient_history"

# Quantiles for the prediction interval. 0.5 is the point estimate.
QUANTILES = (0.1, 0.5, 0.9)

# Backtest cuts: each trains on everything before the cut and scores the next
# HORIZON_WEEKS. Rolling-origin, so the model never sees its own future.
BACKTEST_FOLDS = 5
MIN_TRAIN_WEEKS = 60


def _sklearn():
    try:
        from sklearn.ensemble import GradientBoostingRegressor
    except ImportError as exc:
        raise ImportError(
            "scikit-learn is required. Install with `uv sync --extra model`."
        ) from exc
    return GradientBoostingRegressor


# --- baselines ---------------------------------------------------------------

def naive_forecast(series: pd.Series, horizon: int = FC.HORIZON_WEEKS) -> float:
    """Last observed value carried forward."""
    observed = series.dropna()
    return float(observed.iloc[-1]) if len(observed) else float("nan")


def seasonal_naive_forecast(
    series: pd.Series,
    horizon: int = FC.HORIZON_WEEKS,
    period: int = FC.SEASONAL_LAG_WEEKS,
) -> float:
    """Value from the same week last year; falls back to naive if unavailable."""
    if len(series) > period:
        candidate = series.iloc[-period + horizon - 1] if period >= horizon else np.nan
        if pd.notna(candidate):
            return float(candidate)
    return naive_forecast(series, horizon)


# --- metrics -----------------------------------------------------------------

def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean absolute percentage error, skipping zero actuals."""
    nonzero = actual != 0
    if not nonzero.any():
        return float("nan")
    return float(np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100)


# --- supervised framing ------------------------------------------------------

def supervised_frame(panel: pd.DataFrame, horizon: int = FC.HORIZON_WEEKS) -> pd.DataFrame:
    """Attach the horizon-ahead target to each condition's rows."""
    frames = []
    for condition, g in panel.groupby("condition", sort=False):
        g = g.sort_values("week_idx").copy()
        g["y"] = g[FC.TARGET_COLUMN].shift(-horizon)
        frames.append(g)
    out = pd.concat(frames, ignore_index=True) if frames else panel.copy()
    return out.dropna(subset=fd.feature_columns() + ["y"])


class QuantileForecaster:
    """Quantile GBMs plus a split-conformal widening term: raw quantile regression
    on this little data undercovers, so held-out residuals widen the band."""

    def __init__(self, models: dict[float, object], delta: float = 0.0) -> None:
        self.models = models
        self.delta = delta

    def predict(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        lo = self.models[min(QUANTILES)].predict(X) - self.delta
        mid = self.models[0.5].predict(X)
        hi = self.models[max(QUANTILES)].predict(X) + self.delta
        return lo, mid, hi


def _fit_quantiles(X: pd.DataFrame, y: pd.Series, calibrate: bool = True) -> QuantileForecaster:
    GradientBoostingRegressor = _sklearn()

    def fit(Xf, yf) -> dict[float, object]:
        out = {}
        for q in QUANTILES:
            # Shallow and leaf-constrained: few rows per condition, and an
            # overfit quantile learner produces intervals that are too narrow.
            m = GradientBoostingRegressor(
                loss="quantile", alpha=q, random_state=FC.RANDOM_STATE,
                n_estimators=150, max_depth=2, learning_rate=0.05,
                min_samples_leaf=5, subsample=0.9,
            )
            m.fit(Xf, yf)
            out[q] = m
        return out

    # Calibrate on the most recent slice, keeping the split chronological.
    split = int(len(X) * 0.75)
    if not calibrate or split < 20 or len(X) - split < 10:
        return QuantileForecaster(fit(X, y))

    models = fit(X.iloc[:split], y.iloc[:split])
    Xc, yc = X.iloc[split:], y.iloc[split:].to_numpy(dtype=float)
    lo = models[min(QUANTILES)].predict(Xc)
    hi = models[max(QUANTILES)].predict(Xc)

    # CQR conformity score: how far outside the band each calibration point fell.
    scores = np.maximum(lo - yc, yc - hi)
    nominal = max(QUANTILES) - min(QUANTILES)
    delta = float(max(0.0, np.quantile(scores, nominal)))
    return QuantileForecaster(fit(X, y), delta)


# --- backtest ----------------------------------------------------------------

def backtest(
    panel: pd.DataFrame | None = None,
    horizon: int = FC.HORIZON_WEEKS,
    folds: int = BACKTEST_FOLDS,
) -> dict:
    """Rolling-origin evaluation against both baselines."""
    panel = panel if panel is not None else fd.condition_panel()
    fd.assert_no_leakage(panel)

    frame = supervised_frame(panel, horizon)
    if frame.empty:
        return {"horizon_weeks": horizon, "n_conditions": 0,
                "folds": [], "per_condition": [], "summary": {}}

    features = fd.feature_columns()
    per_fold = []

    # One model per condition. Pooling series that differ by two orders of
    # magnitude (Chlamydia ~682/wk vs Giardiasis ~4/wk) wrecks both MAPE and
    # interval calibration.
    for condition, cframe in frame.groupby("condition", sort=False):
        weeks = np.sort(cframe["week_idx"].unique())
        n_folds = folds
        if len(weeks) < MIN_TRAIN_WEEKS + folds:
            n_folds = max(1, (len(weeks) - MIN_TRAIN_WEEKS) // max(1, horizon))
        if len(weeks) <= MIN_TRAIN_WEEKS or n_folds < 1:
            continue

        cuts = np.linspace(MIN_TRAIN_WEEKS, len(weeks) - 1, num=n_folds + 1, dtype=int)[:-1]
        for cut in cuts:
            cut_week = weeks[cut]
            train = cframe[cframe["week_idx"] <= cut_week]
            test = cframe[(cframe["week_idx"] > cut_week) & (cframe["week_idx"] <= cut_week + horizon)]
            if len(train) < 20 or test.empty:
                continue

            forecaster = _fit_quantiles(train[features], train["y"])
            actual = test["y"].to_numpy(dtype=float)
            lo, predicted, hi = forecaster.predict(test[features])

            per_fold.append({
                "condition": condition,
                "cut_week_idx": int(cut_week),
                "n_test": int(len(test)),
                "model_mae": mae(actual, predicted),
                "model_mape": mape(actual, predicted),
                "naive_mae": mae(actual, test["lag_1"].to_numpy(dtype=float)),
                "seasonal_naive_mae": mae(
                    actual, test[f"lag_{FC.SEASONAL_LAG_WEEKS}"].fillna(test["lag_1"]).to_numpy(dtype=float)
                ),
                "interval_coverage": float(np.mean((actual >= lo) & (actual <= hi))),
            })

    folds_df = pd.DataFrame(per_fold)
    if folds_df.empty:
        return {"horizon_weeks": horizon, "n_conditions": 0,
                "folds": [], "per_condition": [], "summary": {}}

    def agg(vals) -> dict:
        vals = np.asarray(vals, dtype=float)
        vals = vals[~np.isnan(vals)]
        return {"mean": float(vals.mean()), "sd": float(vals.std(ddof=0))} if len(vals) else {}

    # Skill = model error / baseline error. Scale-free, so conditions of very
    # different magnitude can be compared and averaged; < 1 means the model wins.
    per_condition = []
    for condition, g in folds_df.groupby("condition", sort=True):
        m, n, s = g.model_mae.mean(), g.naive_mae.mean(), g.seasonal_naive_mae.mean()
        per_condition.append({
            "condition": condition,
            "model_mae": float(m), "naive_mae": float(n), "seasonal_naive_mae": float(s),
            "model_mape": float(g.model_mape.mean()),
            "skill_vs_naive": float(m / n) if n else float("nan"),
            "skill_vs_seasonal": float(m / s) if s else float("nan"),
            "interval_coverage": float(g.interval_coverage.mean()),
            "folds": int(len(g)),
        })

    skill_naive = [c["skill_vs_naive"] for c in per_condition]
    skill_seasonal = [c["skill_vs_seasonal"] for c in per_condition]

    return {
        "horizon_weeks": horizon,
        "n_conditions": len(per_condition),
        "folds": per_fold,
        "per_condition": per_condition,
        "summary": {
            "mape": agg([c["model_mape"] for c in per_condition]),
            "interval_coverage": agg([c["interval_coverage"] for c in per_condition]),
            "skill_vs_naive": agg(skill_naive),
            "skill_vs_seasonal": agg(skill_seasonal),
            "conditions_beating_naive": int(sum(s < 1 for s in skill_naive)),
            "conditions_beating_seasonal": int(sum(s < 1 for s in skill_seasonal)),
        },
    }


def beats_baseline(results: dict) -> bool:
    """True when mean skill beats both baselines across conditions."""
    summary = results.get("summary", {})
    naive = summary.get("skill_vs_naive", {}).get("mean")
    seasonal = summary.get("skill_vs_seasonal", {}).get("mean")
    if naive is None or seasonal is None:
        return False
    return naive < 1.0 and seasonal < 1.0


# --- prediction --------------------------------------------------------------

def forecast_conditions(panel: pd.DataFrame | None = None, horizon: int = FC.HORIZON_WEEKS) -> list[dict]:
    """Latest-week forecast per condition, with interval and status."""
    panel = panel if panel is not None else fd.condition_panel()
    usable, thin = fd.usable_conditions(panel)

    out = [
        {"condition": c, "status": INSUFFICIENT_HISTORY, "point": None,
         "lower": None, "upper": None, "horizon_weeks": horizon}
        for c in thin
    ]
    if not usable:
        return out

    features = fd.feature_columns()
    # Series stop reporting at different weeks, so a forecast can be anchored to
    # an old week and still look current. weeks_stale makes that visible.
    panel_latest = int(panel["week_idx"].max())

    for condition in usable:
        cpanel = panel[panel.condition == condition]
        frame = supervised_frame(cpanel, horizon)
        latest = cpanel.dropna(subset=features).sort_values("week_idx").tail(1)
        if len(frame) < 20 or latest.empty:
            out.append({"condition": condition, "status": INSUFFICIENT_HISTORY, "point": None,
                        "lower": None, "upper": None, "horizon_weeks": horizon})
            continue

        forecaster = _fit_quantiles(frame[features], frame["y"])
        row = latest.iloc[0]
        X = row[features].to_frame().T.astype(float)
        lower, point, upper = (float(v[0]) for v in forecaster.predict(X))

        out.append({
            "condition": condition,
            "status": "ok",
            # Counts cannot be negative; the quantile learner does not know that.
            "point": max(0.0, round(point, 1)),
            "lower": max(0.0, round(lower, 1)),
            "upper": max(0.0, round(upper, 1)),
            "horizon_weeks": horizon,
            "as_of_year": int(row["mmwr_year"]),
            "as_of_week": int(row["mmwr_week"]),
            "weeks_stale": panel_latest - int(row["week_idx"]),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", action="store_true", help="rolling-origin evaluation")
    ap.add_argument("--train", action="store_true", help="fit and write the model artifact")
    args = ap.parse_args()

    panel = fd.condition_panel()
    fd.assert_no_leakage(panel)

    if args.backtest or not args.train:
        results = backtest(panel)
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        METRICS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

        s = results["summary"]
        n = results["n_conditions"]
        if not s:
            print("Backtest produced no folds (history too thin); "
                  f"metrics written to {METRICS_PATH}")
        else:
            print(f"Rolling-origin backtest, horizon {results['horizon_weeks']}w, "
                  f"{n} conditions, {len(results['folds'])} fold-fits")
            print(f"  skill vs naive       {s['skill_vs_naive']['mean']:.2f} "
                  f"(<1 wins; {s['conditions_beating_naive']}/{n} conditions)")
            print(f"  skill vs seasonal    {s['skill_vs_seasonal']['mean']:.2f} "
                  f"({s['conditions_beating_seasonal']}/{n} conditions)")
            print(f"  MAPE                 {s['mape']['mean']:.1f}% +/- {s['mape']['sd']:.1f}")
            print(f"  interval coverage    {s['interval_coverage']['mean']:.0%} "
                  f"(nominal {max(QUANTILES) - min(QUANTILES):.0%})")
            print(f"  beats both baselines {beats_baseline(results)}\n")
            for c in sorted(results["per_condition"], key=lambda r: r["skill_vs_naive"]):
                print(f"  {c['skill_vs_naive']:.2f}  {c['condition'][:52]:<52} "
                      f"MAE {c['model_mae']:7.2f} vs naive {c['naive_mae']:7.2f}")

    if args.train:
        import joblib

        artifacts = {}
        for condition, cpanel in panel.groupby("condition", sort=True):
            frame = supervised_frame(cpanel)
            if len(frame) < 20:
                continue
            artifacts[condition] = _fit_quantiles(frame[fd.feature_columns()], frame["y"])
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({"per_condition": artifacts, "features": fd.feature_columns(),
                     "horizon_weeks": FC.HORIZON_WEEKS, "quantiles": QUANTILES}, MODEL_PATH)
        print(f"Wrote {MODEL_PATH.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
