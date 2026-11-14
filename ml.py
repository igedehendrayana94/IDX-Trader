"""ML layer: predict P(trade plan ends in profit) with gradient boosting, validated walk-forward."""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

import idx

FEATURES = ["ret1", "ret5", "ret10", "ret20", "dist_ema20", "dist_ema50", "ema_spread", "rsi", "macd_n",
            "atr_n", "vol_ratio", "close_pos", "dist_high20", "log_value", "mkt_ret5", "mkt_ret20", "rel_ret20"]
IHSG = ["ihsg_ret5", "ihsg_ret20", "ihsg_dist_ema50", "ihsg_vol20", "rel_ihsg20"]
FOREIGN = ["fnet5", "fnet20"]


def cols(p):
    """Features present in this dataset (IHSG and foreign flow are optional inputs)."""
    return [c for c in FEATURES + IHSG + FOREIGN if c in p.columns]


def ihsg_features(ih):
    c = ih["Close"]
    r = c.pct_change()
    return pd.DataFrame({
        "ihsg_ret5": c.pct_change(5), "ihsg_ret20": c.pct_change(20),
        "ihsg_dist_ema50": c / c.ewm(span=50, adjust=False).mean() - 1, "ihsg_vol20": r.rolling(20).std(),
    }, index=ih.index)


def features(d):
    c = d["Close"]
    return pd.DataFrame({
        "ret1": c.pct_change(), "ret5": c.pct_change(5), "ret10": c.pct_change(10), "ret20": c.pct_change(20),
        "dist_ema20": c / d["ema20"] - 1, "dist_ema50": c / d["ema50"] - 1, "ema_spread": d["ema20"] / d["ema50"] - 1,
        "rsi": d["rsi"], "macd_n": d["macd_hist"] / c, "atr_n": d["atr"] / c, "vol_ratio": d["Volume"] / d["vol20"],
        "close_pos": d["close_pos"], "dist_high20": c / d["high20"] - 1, "log_value": np.log1p(d["value20"]),
    }, index=d.index)


def dataset(data, mode, ihsg=None, foreign=None):
    """Panel of (date, code, features, label, ret). Label = plan from that day's close ends with net profit.
    Last `hold` rows per stock have no complete outcome: label NaN, used only for prediction."""
    hold = idx.MODES[mode]["hold"]
    parts = []
    for code, df in data.items():
        d = idx.indicators(df)
        f = features(d)
        arr = idx.ohlca(d)
        n = len(d)
        ret = np.full(n, np.nan)
        for i in range(50, n - hold):  # need full horizon after entry day i+1
            ret[i] = idx.outcome(arr, i, mode)[0]
        if foreign is not None and len(foreign):
            # net foreign shares over 5/20 days, scaled by normal volume so stocks are comparable
            fn = foreign[foreign["code"] == code].groupby("date")["fnet"].sum().reindex(d.index)
            f["fnet5"] = fn.rolling(5, min_periods=3).sum() / (5 * d["vol20"])
            f["fnet20"] = fn.rolling(20, min_periods=10).sum() / (20 * d["vol20"])
        f["ret"], f["code"] = ret, code
        parts.append(f.iloc[50:])
    p = pd.concat(parts).rename_axis("date").reset_index()
    # market context: equal-weight universe average, shared by every stock on a date
    g = p.groupby("date")
    p["mkt_ret5"], p["mkt_ret20"] = g["ret5"].transform("mean"), g["ret20"].transform("mean")
    p["rel_ret20"] = p["ret20"] - p["mkt_ret20"]
    if ihsg is not None:
        p = p.merge(ihsg_features(ihsg), left_on="date", right_index=True, how="left")
        p["rel_ihsg20"] = p["ret20"] - p["ihsg_ret20"]
    p["y"] = (p["ret"] > 0).astype(float).where(p["ret"].notna())
    return p.replace([np.inf, -np.inf], np.nan)


def model():
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                          min_samples_leaf=200, l2_regularization=1.0, random_state=0)


def walk_forward(p, mode, folds=4, test_days=120):
    """Train only on dates before each test block, with a gap of `hold`+1 days so labels never overlap the test."""
    gap = idx.MODES[mode]["hold"] + 1
    lab, X = p[p["y"].notna()], cols(p)
    dates = np.sort(lab["date"].unique())
    rows = []
    for k in range(folds, 0, -1):
        start = len(dates) - k * test_days
        if start - gap < 250:  # need about a year of training data
            continue
        test_dates = dates[start:start + test_days]
        train = lab[lab["date"] < dates[start - gap]]
        test = lab[lab["date"].isin(test_dates)]
        prob = model().fit(train[X], train["y"]).predict_proba(test[X])[:, 1]
        top = test[prob >= np.quantile(prob, 0.9)]
        rows.append({
            "test_from": pd.Timestamp(test_dates[0]).date(), "test_to": pd.Timestamp(test_dates[-1]).date(),
            "auc": roc_auc_score(test["y"], prob), "base_win%": test["y"].mean() * 100,
            "top10_win%": top["y"].mean() * 100, "base_avg%": test["ret"].mean() * 100,
            "top10_avg%": top["ret"].mean() * 100, "n_test": len(test),
        })
    return pd.DataFrame(rows).round(2)


def predict_latest(p):
    """Fit on all labeled rows, return P(profit) for each stock's latest day."""
    lab, X = p[p["y"].notna()], cols(p)
    last = p.sort_values("date").groupby("code").tail(1)
    prob = model().fit(lab[X], lab["y"]).predict_proba(last[X])[:, 1]
    return pd.Series(prob, index=last["code"].to_numpy(), name="ml_prob")


if __name__ == "__main__":
    # leakage check: pure random walks must give AUC near 0.5; leaking future data would push it far above
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2020-01-01", periods=900)
    data = {}
    for s in range(20):
        c = 1000 * np.exp(np.cumsum(rng.normal(0, 0.02, len(dates))))
        o = c * np.exp(rng.normal(0, 0.005, len(dates)))
        data[f"S{s}"] = pd.DataFrame({"Open": o, "High": np.maximum(o, c) * 1.01, "Low": np.minimum(o, c) * 0.99,
                                      "Close": c, "Volume": rng.integers(1e6, 2e6, len(dates))}, index=dates)
    for mode in idx.MODES:
        wf = walk_forward(dataset(data, mode), mode)
        assert len(wf) and wf["auc"].between(0.44, 0.56).all(), wf
    print("ok")
