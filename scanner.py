import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import yfinance as yf
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# ============================================================
# STOCKAI SCANNER V5.6
# Beginner-friendly technical scanner
# - 5 nearest supports + 5 nearest resistances
# - historical breakout / breakdown logic
# - entry zone, breakout entry, stop loss, targets
# - risk/reward and explanation
# ============================================================

STOCKS = [
    # "WIPRO.NS",
    # "INFY.NS",
    # "TCS.NS",
    # "HDFCBANK.NS",
    # "RELIANCE.NS",
    # "HFCL.NS",
    # "TMCV.NS",
    # "ADANIPORTS.NS",
    # "QPOWER.NS",
    "Marine.NS"
]

DATA_PERIOD = "2y"
RSI_PERIOD = 14
ATR_PERIOD = 14
ADX_PERIOD = 14
EMA_FAST, EMA_MID, EMA_SLOW = 20, 50, 200
VOLUME_PERIOD = 20
VOLUME_THRESHOLD = 1.5
VOLUME_GOOD = 1.5
VOLUME_NEUTRAL = 0.8
VOLUME_WEAK = 0.5
BB_PERIOD, BB_STD = 20, 2.0
SR_WINDOWS = [20, 60, 120]
SR_MERGE_PCT = 0.01
BREAKOUT_LOOKBACK = 20
BREAKOUT_ATR_MULT = 0.10
ADX_STRONG = 20
REPORT_LIMIT = 10


def clean_yfinance(data):
    if data is None or data.empty:
        return None
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in data.columns and isinstance(data[col], pd.DataFrame):
            data[col] = data[col].iloc[:, 0]
    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in data.columns for c in needed):
        return None
    data = data[needed].copy()
    for c in needed:
        data[c] = pd.to_numeric(data[c], errors="coerce")
    return data.dropna(subset=["High", "Low", "Close"])


def rsi_wilder(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss > 0)), 0)
    return rsi


def atr_wilder(df, period=14):
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx_wilder(df, period=14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return adx, plus_di, minus_di


def supertrend(df, period=10, multiplier=3.0):
    """SuperTrend with a valid warm-up period (avoids N/A propagation)."""
    atr = atr_wilder(df, period)
    hl2 = (df["High"] + df["Low"]) / 2
    upper_basic = hl2 + multiplier * atr
    lower_basic = hl2 - multiplier * atr

    upper = pd.Series(np.nan, index=df.index, dtype=float)
    lower = pd.Series(np.nan, index=df.index, dtype=float)
    direction = pd.Series(np.nan, index=df.index, dtype=float)
    st = pd.Series(np.nan, index=df.index, dtype=float)

    valid = np.where(atr.notna().values)[0]
    if len(valid) == 0:
        return st, direction

    first = int(valid[0])
    upper.iloc[first] = upper_basic.iloc[first]
    lower.iloc[first] = lower_basic.iloc[first]
    direction.iloc[first] = 1
    st.iloc[first] = lower.iloc[first]

    for i in range(first + 1, len(df)):
        if pd.isna(upper_basic.iloc[i]) or pd.isna(lower_basic.iloc[i]):
            continue

        prev_upper = upper.iloc[i - 1]
        prev_lower = lower.iloc[i - 1]
        prev_direction = direction.iloc[i - 1]

        if pd.isna(prev_upper):
            prev_upper = upper_basic.iloc[i]
        if pd.isna(prev_lower):
            prev_lower = lower_basic.iloc[i]
        if pd.isna(prev_direction):
            prev_direction = 1

        prev_close = df["Close"].iloc[i - 1]
        upper.iloc[i] = (upper_basic.iloc[i]
                         if upper_basic.iloc[i] < prev_upper or prev_close > prev_upper
                         else prev_upper)
        lower.iloc[i] = (lower_basic.iloc[i]
                         if lower_basic.iloc[i] > prev_lower or prev_close < prev_lower
                         else prev_lower)

        if prev_direction == -1 and df["Close"].iloc[i] > upper.iloc[i]:
            direction.iloc[i] = 1
        elif prev_direction == 1 and df["Close"].iloc[i] < lower.iloc[i]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = prev_direction

        st.iloc[i] = lower.iloc[i] if direction.iloc[i] == 1 else upper.iloc[i]

    return st, direction


def add_indicators(df):
    df = df.copy()
    df["RSI"] = rsi_wilder(df["Close"], RSI_PERIOD)
    df["EMA20"] = df["Close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=EMA_MID, adjust=False).mean()
    df["EMA200"] = df["Close"].ewm(span=EMA_SLOW, adjust=False).mean()
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]
    df["ATR"] = atr_wilder(df, ATR_PERIOD)
    df["ADX"], df["PLUS_DI"], df["MINUS_DI"] = adx_wilder(df, ADX_PERIOD)
    df["SUPERTREND"], df["ST_DIRECTION"] = supertrend(df, 10, 3.0)
    df["VOL_AVG"] = df["Volume"].rolling(VOLUME_PERIOD).mean()
    df["VOL_RATIO"] = df["Volume"] / df["VOL_AVG"].replace(0, np.nan)
    df["BB_MID"] = df["Close"].rolling(BB_PERIOD).mean()
    bb_std = df["Close"].rolling(BB_PERIOD).std()
    df["BB_UPPER"] = df["BB_MID"] + BB_STD * bb_std
    df["BB_LOWER"] = df["BB_MID"] - BB_STD * bb_std
    df["52W_HIGH"] = df["High"].rolling(252, min_periods=20).max()
    df["52W_LOW"] = df["Low"].rolling(252, min_periods=20).min()
    rng = df["52W_HIGH"] - df["52W_LOW"]
    df["52W_POSITION"] = 100 * (df["Close"] - df["52W_LOW"]) / rng.replace(0, np.nan)
    return df


def local_levels(df):
    """Collect swing highs/lows and rolling levels from several windows."""
    supports = []
    resistances = []

    for w in SR_WINDOWS:
        roll_low = df["Low"].rolling(w, min_periods=max(5, w // 3)).min()
        roll_high = df["High"].rolling(w, min_periods=max(5, w // 3)).max()
        supports.extend(roll_low.dropna().tolist())
        resistances.extend(roll_high.dropna().tolist())

    # Pivot-like swing points. Shifted windows avoid treating the current
    # candle as the historical breakout level.
    h = df["High"]
    l = df["Low"]
    for span in [2, 3, 5]:
        swing_high = h[(h == h.rolling(2 * span + 1, center=True).max())]
        swing_low = l[(l == l.rolling(2 * span + 1, center=True).min())]
        resistances.extend(swing_high.dropna().tolist())
        supports.extend(swing_low.dropna().tolist())

    return supports, resistances


def cluster_levels(levels, current_price, side):
    if side == "support":
        candidates = [float(x) for x in levels if np.isfinite(x) and x < current_price * 0.9995]
        candidates.sort(reverse=True)
    else:
        candidates = [float(x) for x in levels if np.isfinite(x) and x > current_price * 1.0005]
        candidates.sort()

    clusters = []
    for level in candidates:
        if not clusters:
            clusters.append([level])
            continue
        ref = np.mean(clusters[-1])
        if abs(level - ref) / ref <= SR_MERGE_PCT:
            clusters[-1].append(level)
        else:
            clusters.append([level])
        if len(clusters) >= 12:
            break

    result = []
    for cluster in clusters:
        level = float(np.mean(cluster))
        result.append({"level": level, "touches": len(cluster), "projected": False})
    return result[:5]


def level_strength(touches):
    if touches >= 6:
        return "VERY STRONG"
    if touches >= 4:
        return "STRONG"
    if touches >= 2:
        return "MEDIUM"
    return "WEAK"


def assess_sr_structure(price, supports, resistances, atr):
    """Add beginner-friendly context around existing V3.2.5 S/R levels."""
    support = supports[0] if supports else None
    resistance = resistances[0] if resistances else None
    support_dist = ((price-support["level"])/price*100) if support else np.nan
    resistance_dist = ((resistance["level"]-price)/price*100) if resistance else np.nan
    support_strength = level_strength(support["touches"]) if support and not support.get("projected") else "PROJECTED"
    resistance_strength = level_strength(resistance["touches"]) if resistance and not resistance.get("projected") else "PROJECTED"
    room_atr = ((resistance["level"]-price)/atr) if resistance and atr > 0 else np.nan
    if pd.isna(resistance_dist): resistance_status = "NO RESISTANCE FOUND"
    elif resistance_dist <= 1.0: resistance_status = "VERY CLOSE"
    elif resistance_dist <= 2.5: resistance_status = "CLOSE"
    elif resistance_dist <= 5.0: resistance_status = "MODERATE ROOM"
    else: resistance_status = "GOOD ROOM"
    if pd.isna(support_dist): support_status = "NO SUPPORT FOUND"
    elif support_dist <= 1.0: support_status = "VERY CLOSE"
    elif support_dist <= 3.0: support_status = "CLOSE"
    elif support_dist <= 6.0: support_status = "MODERATE CUSHION"
    else: support_status = "LARGE CUSHION"
    if resistance and resistance_dist <= 2.0: sr_bias = "RESISTANCE PRESSURE"
    elif support and support_dist <= 2.0: sr_bias = "SUPPORT ZONE"
    elif resistance and support: sr_bias = "BALANCED RANGE"
    elif resistance: sr_bias = "UPSIDE CEILING"
    elif support: sr_bias = "DOWNSIDE FLOOR"
    else: sr_bias = "NO CLEAR STRUCTURE"
    return {"SupportDistancePct": support_dist, "ResistanceDistancePct": resistance_dist,
            "SupportStrength": support_strength, "ResistanceStrength": resistance_strength,
            "ResistanceRoomATR": room_atr, "SupportStatus": support_status,
            "ResistanceStatus": resistance_status, "SRBias": sr_bias}


def historical_break_levels(df):
    """Historical structure levels excluding the current candle."""
    prior_high = df["High"].rolling(BREAKOUT_LOOKBACK).max().shift(1)
    prior_low = df["Low"].rolling(BREAKOUT_LOOKBACK).min().shift(1)
    return prior_high, prior_low


def build_trade_setup(action, price, atr, nearest_support, nearest_resistance,
                      prior_resistance, prior_support, breakout_entry, stop_loss,
                      target1, target2, target3, trade_risk_pct, breakout,
                      breakdown, breakout_watch, breakdown_watch, retest,
                      trend, macd_bull, st_bull, adx, plus_di, minus_di,
                      vol_ratio, rsi, technical_risk, sr_bias):
    """V4.3 trade-setup interpretation layered on top of V3.2.5 levels.

    This does not replace the scanner's indicators or mechanical levels. It
    translates them into a beginner-friendly setup state and checklist.
    """
    def pct_distance(a, b):
        return ((a - b) / b * 100) if pd.notna(a) and pd.notna(b) and b else np.nan

    breakout_distance_pct = pct_distance(breakout_entry, price)
    resistance_distance_pct = pct_distance(nearest_resistance, price)
    support_distance_pct = pct_distance(price, nearest_support)
    stop_distance_pct = pct_distance(price, stop_loss)
    t1_distance_pct = pct_distance(target1, price)
    t2_distance_pct = pct_distance(target2, price)
    t3_distance_pct = pct_distance(target3, price)

    # Determine the setup state from the already-established V3.2.5 action.
    if breakdown or action == "AVOID — BREAKDOWN":
        setup_state = "NO NEW ENTRY — BREAKDOWN"
        entry_plan = "NO NEW ENTRY"
        trigger_type = "BREAKDOWN INVALIDATION"
        trigger_price = prior_support * 0.995 if pd.notna(prior_support) else np.nan
    elif breakout or action == "CONFIRMED BREAKOUT":
        setup_state = "BREAKOUT CONFIRMED"
        entry_plan = "BREAKOUT CONFIRMATION"
        trigger_type = "BREAKOUT CONFIRMATION"
        trigger_price = breakout_entry
    elif retest or action == "BREAKOUT RETEST":
        setup_state = "BREAKOUT RETEST"
        entry_plan = "RETEST / HOLD"
        trigger_type = "RETEST HOLD"
        trigger_price = prior_resistance if pd.notna(prior_resistance) else nearest_support
    elif action == "WAIT — RESISTANCE":
        setup_state = "WAIT — RESISTANCE"
        entry_plan = "WAIT FOR CLEARANCE"
        trigger_type = "CLEAR NEAREST RESISTANCE"
        trigger_price = nearest_resistance
    elif action == "WAIT — BREAKOUT":
        setup_state = "WAIT — BREAKOUT"
        entry_plan = "BREAKOUT CONFIRMATION"
        trigger_type = "BREAKOUT CONFIRMATION"
        trigger_price = breakout_entry
    elif action == "WAIT — CONFIRMATION":
        setup_state = "WAIT — CONFIRMATION"
        entry_plan = "WAIT FOR CONFIRMATION"
        trigger_type = "MOMENTUM / VOLUME CONFIRMATION"
        trigger_price = breakout_entry
    elif action == "WATCH — SUPPORT":
        setup_state = "WATCH — SUPPORT"
        entry_plan = "SUPPORT HOLD / RECOVERY"
        trigger_type = "SUPPORT HOLD"
        trigger_price = nearest_support
    elif action == "WATCH — RECOVERY":
        setup_state = "WATCH — RECOVERY"
        entry_plan = "RECOVERY CONFIRMATION"
        trigger_type = "BREAKOUT / TREND CONFIRMATION"
        trigger_price = breakout_entry
    elif action == "AVOID — BEARISH":
        setup_state = "NO NEW ENTRY — BEARISH"
        entry_plan = "NO NEW ENTRY"
        trigger_type = "TREND RECOVERY"
        trigger_price = breakout_entry
    else:
        setup_state = "WATCH — MIXED"
        entry_plan = "REFERENCE ONLY"
        trigger_type = "SETUP IMPROVEMENT"
        trigger_price = breakout_entry

    confirmation = []
    confirmation.append("Historical breakout confirmed" if breakout else "Historical breakout NOT confirmed")
    confirmation.append("Volume >= 1.5x average" if vol_ratio >= VOLUME_THRESHOLD else "Volume confirmation missing")
    confirmation.append("MACD bullish" if macd_bull else "MACD bearish")
    confirmation.append("SuperTrend bullish" if st_bull else "SuperTrend bearish")
    confirmation.append("ADX/+DI trend confirmation" if adx >= ADX_STRONG and plus_di > minus_di else "ADX/+DI confirmation missing")

    if nearest_resistance is not None and pd.notna(nearest_resistance):
        if resistance_distance_pct <= 1:
            resistance_comment = "Resistance is very close"
        elif resistance_distance_pct <= 2.5:
            resistance_comment = "Resistance is close"
        else:
            resistance_comment = "Adequate resistance room"
    else:
        resistance_comment = "No clear resistance found"
    confirmation.append(resistance_comment)

    # V4.3.1: keep two concepts separate.
    # Trade stop = mechanical 1.5 ATR risk level.
    # Setup invalidation = level below current price where a bullish/recovery
    # thesis would fail. For bearish setups, do NOT use prior support if it is
    # already above the current price; that would create a nonsensical
    # "invalidation" above market price.
    trade_stop_price = stop_loss
    if action in ["AVOID — BREAKDOWN", "AVOID — BEARISH"]:
        setup_invalidation_price = stop_loss
    elif pd.notna(nearest_support) and nearest_support < price:
        setup_invalidation_price = nearest_support * 0.995
    else:
        setup_invalidation_price = stop_loss

    # Two-stage trigger: first clear the nearby resistance, then confirm the
    # larger historical breakout level. This is descriptive, not predictive.
    immediate_trigger_price = nearest_resistance if pd.notna(nearest_resistance) else breakout_entry
    breakout_confirmation_price = breakout_entry

    if setup_state == "WAIT — RESISTANCE":
        trigger_type = "CLEAR R1 → CONFIRM BREAKOUT"
        trigger_price = immediate_trigger_price
    elif setup_state in ["WATCH — MIXED", "WATCH — SUPPORT", "WATCH — RECOVERY"]:
        trigger_type = "CLEAR R1 → CONFIRM BREAKOUT"
        trigger_price = immediate_trigger_price


    # Mechanical target room. These are descriptive distances, not forecasts.
    target_room = {
        "T1": t1_distance_pct,
        "T2": t2_distance_pct,
        "T3": t3_distance_pct,
    }

    if trade_risk_pct <= 3:
        setup_risk = "LOW"
    elif trade_risk_pct <= 6:
        setup_risk = "MODERATE"
    elif trade_risk_pct <= 10:
        setup_risk = "HIGH"
    else:
        setup_risk = "VERY HIGH"

    return {
        "SetupState": setup_state,
        "EntryPlan": entry_plan,
        "TriggerType": trigger_type,
        "TriggerPrice": trigger_price,
        "ImmediateTriggerPrice": immediate_trigger_price,
        "BreakoutConfirmationPrice": breakout_confirmation_price,
        "BreakoutDistancePct": breakout_distance_pct,
        "ResistanceDistancePctV43": resistance_distance_pct,
        "SupportDistancePctV43": support_distance_pct,
        "StopDistancePct": stop_distance_pct,
        "Target1DistancePct": t1_distance_pct,
        "Target2DistancePct": t2_distance_pct,
        "Target3DistancePct": t3_distance_pct,
        "TradeStopPrice": trade_stop_price,
        "SetupInvalidationPrice": setup_invalidation_price,
        "InvalidationPrice": setup_invalidation_price,
        "ConfirmationChecklist": confirmation,
        "SetupRiskLevel": setup_risk,
        "SRBiasAtSetup": sr_bias,
        "SetupReady": bool(breakout or retest),
        "TradePlanNote": (
            "First clear the nearby R1, then confirm the historical breakout level; "
            "mechanical stop remains separate from setup invalidation."
        ),
    }


def analyse_stock(symbol):
    print(f"\nDownloading {symbol}...")
    raw = yf.download(symbol, period=DATA_PERIOD, interval="1d", auto_adjust=False, progress=False)
    df = clean_yfinance(raw)
    if df is None or len(df) < 220:
        return None
    df = add_indicators(df)
    row = df.iloc[-1]
    price = float(row["Close"])

    supports_raw, resistances_raw = local_levels(df.iloc[:-1])
    supports = cluster_levels(supports_raw, price, "support")
    resistances = cluster_levels(resistances_raw, price, "resistance")

    # Guarantee five levels when enough history exists by using additional
    # historical rolling levels as a fallback.
    if len(supports) < 5:
        extra = df["Low"].rolling(10).min().dropna().tolist()
        supports = cluster_levels(supports_raw + extra, price, "support")
    if len(resistances) < 5:
        extra = df["High"].rolling(10).max().dropna().tolist()
        resistances = cluster_levels(resistances_raw + extra, price, "resistance")

    nearest_support = supports[0]["level"] if supports else np.nan
    nearest_resistance = resistances[0]["level"] if resistances else np.nan

    prior_high, prior_low = historical_break_levels(df)
    prior_resistance = float(prior_high.iloc[-1]) if pd.notna(prior_high.iloc[-1]) else nearest_resistance
    prior_support = float(prior_low.iloc[-1]) if pd.notna(prior_low.iloc[-1]) else nearest_support

    atr = float(row["ATR"]) if pd.notna(row["ATR"]) else max(price * 0.02, 1)

    # If there are fewer than five genuine historical levels, fill the display
    # with ATR-based PROJECTED levels, clearly marked as projections.
    if len(resistances) < 5:
        existing = [x["level"] for x in resistances]
        base = max(existing) if existing else price
        for mult in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
            candidate = base + mult * atr
            if all(abs(candidate - x["level"]) / candidate > 0.01 for x in resistances):
                resistances.append({"level": candidate, "touches": 0, "projected": True})
            if len(resistances) >= 5:
                break

    if len(supports) < 5:
        existing = [x["level"] for x in supports]
        base = min(existing) if existing else price
        for mult in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
            candidate = base - mult * atr
            if candidate > 0 and all(abs(candidate - x["level"]) / candidate > 0.01 for x in supports):
                supports.append({"level": candidate, "touches": 0, "projected": True})
            if len(supports) >= 5:
                break

    sr_context = assess_sr_structure(price, supports, resistances, atr)

    vol_ratio = float(row["VOL_RATIO"]) if pd.notna(row["VOL_RATIO"]) else 0
    adx = float(row["ADX"]) if pd.notna(row["ADX"]) else 0
    plus_di = float(row["PLUS_DI"]) if pd.notna(row["PLUS_DI"]) else 0
    minus_di = float(row["MINUS_DI"]) if pd.notna(row["MINUS_DI"]) else 0
    rsi = float(row["RSI"]) if pd.notna(row["RSI"]) else 50
    macd_bull = row["MACD"] > row["MACD_SIGNAL"]
    st_bull = row["ST_DIRECTION"] == 1

    if price > row["EMA20"] > row["EMA50"] > row["EMA200"]:
        trend = "STRONG UPTREND"
    elif price > row["EMA20"] and price > row["EMA50"]:
        trend = "UPTREND"
    elif price < row["EMA20"] < row["EMA50"] < row["EMA200"]:
        trend = "STRONG DOWNTREND"
    elif price < row["EMA20"] and price < row["EMA50"]:
        trend = "DOWNTREND"
    else:
        trend = "SIDEWAYS"

    strong_volume = vol_ratio >= VOLUME_THRESHOLD
    breakout_margin = max(atr * BREAKOUT_ATR_MULT, price * 0.001)
    breakout = (
        price > prior_resistance + breakout_margin
        and strong_volume
        and (st_bull or macd_bull or trend in ["UPTREND", "STRONG UPTREND"])
    )
    breakdown = (
        price < prior_support - breakout_margin
        and strong_volume
        and ((not st_bull) or (not macd_bull) or trend in ["DOWNTREND", "STRONG DOWNTREND"])
    )

    breakout_watch = bool(not breakout and pd.notna(prior_resistance) and price >= prior_resistance * 0.98)
    breakdown_watch = bool(not breakdown and pd.notna(prior_support) and price <= prior_support * 1.02)

    # A retest must refer to a real historical breakout event:
    # 1) an earlier candle closed above its own prior resistance,
    # 2) the breakout had meaningful volume, and
    # 3) price subsequently returned close to that SAME broken level.
    # This avoids calling the current nearest resistance a "retest".
    retest = False
    retest_level = np.nan
    retest_date = None
    search_start = max(21, len(df) - 16)
    search_end = len(df) - 3
    for i in range(search_start, search_end):
        level = prior_high.iloc[i]
        if pd.isna(level):
            continue
        breakout_margin_i = max(float(df["ATR"].iloc[i]) * BREAKOUT_ATR_MULT, float(df["Close"].iloc[i]) * 0.001)
        breakout_event = (
            float(df["Close"].iloc[i]) > float(level) + breakout_margin_i
            and float(df["VOL_RATIO"].iloc[i]) >= VOLUME_THRESHOLD
            and (int(df["ST_DIRECTION"].iloc[i]) == 1 or float(df["MACD"].iloc[i]) > float(df["MACD_SIGNAL"].iloc[i]))
        )
        if not breakout_event:
            continue
        broken_level = float(level)
        future = df.iloc[i + 1:]
        if future.empty:
            continue
        # Require a later touch of the broken level, while the latest close
        # remains within a reasonable band above/around it.
        touched = ((future["Low"] <= broken_level * 1.015) &
                   (future["High"] >= broken_level * 0.985)).any()
        latest_holds = price >= broken_level * 0.985
        if touched and latest_holds:
            retest = True
            retest_level = broken_level
            retest_date = df.index[i]
            break

    opp = 0
    technical_risk = 0
    reasons = []

    volume_status = (
        "STRONG" if vol_ratio >= VOLUME_GOOD else
        "NORMAL" if vol_ratio >= VOLUME_NEUTRAL else
        "WEAK" if vol_ratio >= VOLUME_WEAK else
        "VERY WEAK"
    )

    if 40 <= rsi <= 60:
        opp += 5
        reasons.append("RSI is in a neutral-to-healthy zone")
    elif rsi < 35 and macd_bull:
        opp += 10
        reasons.append("RSI is low while MACD is bullish, suggesting recovery potential")
    elif 60 < rsi <= 70:
        opp += 5
        reasons.append("RSI shows positive momentum without being above 70")
    if price > row["EMA20"]:
        opp += 10
        reasons.append("Price is above EMA20")
    if price > row["EMA50"]:
        opp += 10
        reasons.append("Price is above EMA50")
    if price > row["EMA200"]:
        opp += 10
        reasons.append("Price is above EMA200")
    if macd_bull:
        opp += 10
        reasons.append("MACD is bullish")
    if vol_ratio >= VOLUME_GOOD:
        opp += 10
        reasons.append(f"Volume confirmation is strong at {vol_ratio:.2f}x the 20-day average")
    elif vol_ratio < VOLUME_WEAK:
        opp -= 10
        reasons.append(f"Volume is very weak at only {vol_ratio:.2f}x the 20-day average")
    elif vol_ratio < VOLUME_NEUTRAL:
        opp -= 5
        reasons.append(f"Volume is below normal at {vol_ratio:.2f}x the 20-day average")
    else:
        reasons.append(f"Volume is moderate at {vol_ratio:.2f}x the 20-day average")
    if breakout:
        opp += 20
        reasons.append("Historical resistance breakout is confirmed with volume")
    elif breakout_watch:
        opp += 5
        reasons.append("Price is close to a historical breakout level")
    if st_bull:
        opp += 5
        reasons.append("SuperTrend is bullish")
    if adx >= ADX_STRONG and plus_di > minus_di:
        opp += 5
        reasons.append(f"ADX {adx:.1f} shows a meaningful trend with bullish DI")
    if retest:
        opp += 10
        reasons.append(f"A real prior breakout level is being retested near {money(retest_level)}")
    if pd.notna(nearest_resistance) and (nearest_resistance - price) / price < 0.02:
        opp -= 5
        reasons.append("Price is close to resistance, so immediate upside may be constrained")

    if rsi < 30:
        technical_risk += 20
        reasons.append("RSI is below 30")
    elif rsi < 35:
        technical_risk += 10
    if price < row["EMA20"]:
        technical_risk += 10
    if price < row["EMA50"]:
        technical_risk += 10
    if price < row["EMA200"]:
        technical_risk += 15
    if not macd_bull:
        technical_risk += 10
    if pd.notna(row["52W_POSITION"]) and row["52W_POSITION"] <= 5:
        technical_risk += 15
    if breakdown:
        technical_risk += 20
    elif breakdown_watch:
        technical_risk += 10
    if adx >= ADX_STRONG and (not st_bull) and minus_di > plus_di:
        technical_risk += 10
    if vol_ratio < VOLUME_WEAK:
        technical_risk += 5
    technical_risk = min(100, int(technical_risk))
    opp = max(0, min(100, int(opp)))

    near_resistance = bool(pd.notna(nearest_resistance) and (nearest_resistance - price) / price <= 0.01)
    weak_volume = vol_ratio < VOLUME_WEAK
    incomplete_confirmation = weak_volume or (not macd_bull)

    # Classification intentionally requires agreement across different signal
    # families rather than allowing a single green indicator to create a
    # confirmed breakout. These labels are scanner classifications, not
    # personalized investment instructions.
    if breakdown:
        action = "AVOID — BREAKDOWN"
    elif breakout:
        action = "CONFIRMED BREAKOUT"
    elif retest and technical_risk < 50 and not (near_resistance and weak_volume):
        action = "BREAKOUT RETEST"
    # Constructive/mixed setups are evaluated before the generic bearish
    # technical-risk fallback. This prevents a single trend score from
    # overriding useful confirmation such as bullish MACD + SuperTrend.
    elif (trend in ["UPTREND", "STRONG UPTREND"] and st_bull
          and technical_risk < 50 and near_resistance):
        action = "WAIT — RESISTANCE"
    elif (trend in ["UPTREND", "STRONG UPTREND"] and st_bull
          and technical_risk < 50 and (weak_volume or not macd_bull)):
        action = "WAIT — CONFIRMATION"
    elif (trend in ["UPTREND", "STRONG UPTREND"] and st_bull and macd_bull
          and adx >= ADX_STRONG and plus_di > minus_di and 45 <= rsi <= 70
          and technical_risk < 40 and opp >= 35 and not weak_volume and not near_resistance):
        action = "WATCH — BULLISH"
    elif (pd.notna(nearest_support) and (price - nearest_support) / price < 0.02
          and trend not in ["DOWNTREND", "STRONG DOWNTREND"]
          and (macd_bull or st_bull)):
        action = "WATCH — SUPPORT"
    elif breakdown_watch and technical_risk >= 60:
        action = "AVOID — BEARISH"
    elif breakdown_watch:
        action = "WATCH — SUPPORT RISK"
    elif breakout_watch:
        action = "WAIT — BREAKOUT"
    # Recovery state: the broader EMA trend can still be bearish while
    # short-term momentum is improving. Do not label such a setup as
    # outright bearish/avoid when MACD + SuperTrend are bullish, RSI is
    # constructive, risk is controlled, and no breakdown is active.
    elif (trend in ["DOWNTREND", "STRONG DOWNTREND"]
          and not breakdown
          and not breakdown_watch
          and macd_bull
          and st_bull
          and rsi >= 45
          and technical_risk < 50):
        action = "WATCH — RECOVERY"
    elif technical_risk >= 60 or trend == "STRONG DOWNTREND":
        action = "AVOID — BEARISH"
    else:
        action = "WATCH — MIXED"

    bull_votes = sum([
        price > row["EMA20"], price > row["EMA50"], price > row["EMA200"],
        rsi >= 50, macd_bull, st_bull, adx >= ADX_STRONG and plus_di > minus_di
    ])
    bear_votes = 7 - bull_votes
    recovery_setup = (
        trend in ["DOWNTREND", "STRONG DOWNTREND"]
        and not breakdown
        and not breakdown_watch
        and macd_bull
        and st_bull
        and rsi >= 45
        and technical_risk < 50
    )

    if recovery_setup:
        signal_view = "RECOVERY / MIXED"
    elif bull_votes >= 6:
        signal_view = "STRONG BULLISH"
    elif bull_votes >= 4:
        signal_view = "BULLISH"
    elif bear_votes >= 6:
        signal_view = "STRONG BEARISH"
    elif bear_votes >= 4:
        signal_view = "BEARISH"
    else:
        signal_view = "MIXED"

    # --------------------------------------------------------
    # V3.2 trade levels: preserve the V3 baseline used in the recent
    # scanner output. Current price is a REFERENCE PRICE, not a command
    # to buy. Risk levels are calculated from the current reference price.
    # Stop = 1.5 ATR; targets = 1.5R / 2.5R / 3.5R.
    # Breakout confirmation = previous 20D high + 0.5%.
    # --------------------------------------------------------
    reference_price = price
    support_ref = nearest_support if pd.notna(nearest_support) else price - atr
    resistance_ref = nearest_resistance if pd.notna(nearest_resistance) else price + atr

    pullback_entry_low = max(support_ref, price - 0.50 * atr)
    pullback_entry_high = max(pullback_entry_low, min(price + 0.10 * atr, resistance_ref - 0.10 * atr))

    if pd.notna(prior_resistance):
        breakout_entry = prior_resistance * 1.005
    else:
        breakout_entry = resistance_ref + max(0.10 * atr, price * 0.002)

    primary_entry = reference_price
    entry_type = "REFERENCE PRICE"

    stop_loss = max(0.01, primary_entry - 1.5 * atr)
    risk_per_share = max(0.01, primary_entry - stop_loss)
    trade_risk_pct = (risk_per_share / primary_entry) * 100 if primary_entry > 0 else np.nan
    if trade_risk_pct <= 3:
        trade_risk_level = "LOW"
    elif trade_risk_pct <= 6:
        trade_risk_level = "MODERATE"
    elif trade_risk_pct <= 10:
        trade_risk_level = "HIGH"
    else:
        trade_risk_level = "VERY HIGH"

    target1 = primary_entry + 1.5 * risk_per_share
    target2 = primary_entry + 2.5 * risk_per_share
    target3 = primary_entry + 3.5 * risk_per_share
    rr2 = 2.5

    # Identify structural resistance that sits before each target. This is
    # displayed as an intermediate hurdle rather than replacing the target.
    def resistance_before(target):
        vals = [x["level"] for x in resistances if pd.notna(x.get("level")) and x["level"] > primary_entry and x["level"] <= target]
        return min(vals) if vals else np.nan

    target1_resistance = resistance_before(target1)
    target2_resistance = resistance_before(target2)
    target3_resistance = resistance_before(target3)

    exit_trigger = stop_loss
    # Keep profit-booking areas aligned with the mechanical targets.
    # Intermediate resistance is shown separately below so it does not
    # overwrite or duplicate the target levels.
    profit_exit1 = target1
    profit_exit2 = target2

    trade_setup = build_trade_setup(
        action, price, atr, nearest_support, nearest_resistance,
        prior_resistance, prior_support, breakout_entry, stop_loss,
        target1, target2, target3, trade_risk_pct, breakout, breakdown,
        breakout_watch, breakdown_watch, retest, trend, macd_bull, st_bull,
        adx, plus_di, minus_di, vol_ratio, rsi, technical_risk, sr_context["SRBias"]
    )

    return {
        "Stock": symbol.replace(".NS", ""),
        "Price": price,
        "ReferencePrice": reference_price,
        "Action": action,
        "BreakoutStatus": ("🔴 BREAKDOWN" if breakdown else "🟢 CONFIRMED BREAKOUT" if breakout else "🟢 BREAKOUT RETEST" if retest else "🟡 NEAR BREAKOUT" if breakout_watch else "⚪ NO BREAKOUT"),
        "Trend": trend,
        "Signal": signal_view,
        "Opportunity": opp,
        "TechnicalRisk": technical_risk,
        "TradeRiskPct": trade_risk_pct,
        "TradeRiskLevel": trade_risk_level,
        "RSI": rsi,
        "MACD": float(row["MACD"]),
        "MACD_Signal": float(row["MACD_SIGNAL"]),
        "ADX": adx,
        "+DI": plus_di,
        "-DI": minus_di,
        "SuperTrend": float(row["SUPERTREND"]) if pd.notna(row["SUPERTREND"]) else np.nan,
        "ST_Direction": "BULLISH" if st_bull else "BEARISH",
        "EMA20": float(row["EMA20"]),
        "EMA50": float(row["EMA50"]),
        "EMA200": float(row["EMA200"]),
        "VolumeRatio": vol_ratio,
        "ATR": atr,
        "BB_Upper": float(row["BB_UPPER"]) if pd.notna(row["BB_UPPER"]) else np.nan,
        "BB_Lower": float(row["BB_LOWER"]) if pd.notna(row["BB_LOWER"]) else np.nan,
        "52W_Position": float(row["52W_POSITION"]) if pd.notna(row["52W_POSITION"]) else np.nan,
        "PriorResistance": prior_resistance,
        "PriorSupport": prior_support,
        "BreakdownTrigger": prior_support * 0.995 if pd.notna(prior_support) else np.nan,
        "Breakout": breakout,
        "Breakdown": breakdown,
        "BreakoutWatch": breakout_watch,
        "BreakdownWatch": breakdown_watch,
        "Retest": retest,
        "RetestLevel": retest_level,
        "RetestDate": retest_date,
        "VolumeStatus": volume_status,
        "NearResistance": near_resistance,
        "Supports": supports,
        "Resistances": resistances,
        "NearestSupport": nearest_support,
        "NearestResistance": nearest_resistance,
        "SupportDistancePct": sr_context["SupportDistancePct"],
        "ResistanceDistancePct": sr_context["ResistanceDistancePct"],
        "SupportStrength": sr_context["SupportStrength"],
        "ResistanceStrength": sr_context["ResistanceStrength"],
        "ResistanceRoomATR": sr_context["ResistanceRoomATR"],
        "SupportStatus": sr_context["SupportStatus"],
        "ResistanceStatus": sr_context["ResistanceStatus"],
        "SRBias": sr_context["SRBias"],
        "EntryType": entry_type,
        "Entry": primary_entry,
        "EntryLow": pullback_entry_low,
        "EntryHigh": pullback_entry_high,
        "BreakoutEntry": breakout_entry,
        "StopLoss": stop_loss,
        "Target1": target1,
        "Target2": target2,
        "Target3": target3,
        "RR": rr2,
        "ExitTrigger": exit_trigger,
        "ProfitExit1": profit_exit1,
        "ProfitExit2": profit_exit2,
        "Target1Resistance": target1_resistance,
        "Target2Resistance": target2_resistance,
        "Target3Resistance": target3_resistance,
        "SetupState": trade_setup["SetupState"],
        "EntryPlan": trade_setup["EntryPlan"],
        "TriggerType": trade_setup["TriggerType"],
        "TriggerPrice": trade_setup["TriggerPrice"],
        "ImmediateTriggerPrice": trade_setup["ImmediateTriggerPrice"],
        "BreakoutConfirmationPrice": trade_setup["BreakoutConfirmationPrice"],
        "BreakoutDistancePct": trade_setup["BreakoutDistancePct"],
        "ResistanceDistancePctV43": trade_setup["ResistanceDistancePctV43"],
        "SupportDistancePctV43": trade_setup["SupportDistancePctV43"],
        "StopDistancePct": trade_setup["StopDistancePct"],
        "Target1DistancePct": trade_setup["Target1DistancePct"],
        "Target2DistancePct": trade_setup["Target2DistancePct"],
        "Target3DistancePct": trade_setup["Target3DistancePct"],
        "TradeStopPrice": trade_setup["TradeStopPrice"],
        "SetupInvalidationPrice": trade_setup["SetupInvalidationPrice"],
        "InvalidationPrice": trade_setup["SetupInvalidationPrice"],
        "ConfirmationChecklist": trade_setup["ConfirmationChecklist"],
        "SetupRiskLevel": trade_setup["SetupRiskLevel"],
        "SRBiasAtSetup": trade_setup["SRBiasAtSetup"],
        "SetupReady": trade_setup["SetupReady"],
        "TradePlanNote": trade_setup["TradePlanNote"],
        "Reasons": reasons[:8],
        "RSI_Bull": 45 <= rsi <= 65,
        "MACD_Bull": bool(macd_bull),
        "ST_Bull": bool(st_bull),
        "ADX_Bull": bool(adx >= ADX_STRONG and plus_di > minus_di),
        "Volume_Bull": bool(vol_ratio >= VOLUME_GOOD),
        "Structure_Bull": bool(breakout or retest or (not breakdown and "UPTREND" in trend)),

    }



def status_circle(action, risk, opportunity):
    if action.startswith("CONFIRMED BREAKOUT") or action == "BREAKOUT RETEST":
        return "🟢"
    if action.startswith("WATCH") or action.startswith("WAIT"):
        return "🟡"
    if action.startswith("AVOID"):
        return "🔴"
    return "🟠"


def indicator_circle(kind, value, **kwargs):
    """Simple beginner-friendly indicator status markers."""
    if kind == "rsi":
        if 45 <= value <= 65:
            return "🟢"
        if 35 <= value < 45 or 65 < value <= 70:
            return "🟡"
        if value < 30 or value > 75:
            return "🔴"
        return "🟠"
    if kind == "macd":
        return "🟢" if kwargs.get("bullish", False) else "🔴"
    if kind == "trend":
        return "🟢" if "UPTREND" in value else ("🔴" if "DOWNTREND" in value else "🟡")
    if kind == "st":
        return "🟢" if value == "BULLISH" else "🔴"
    if kind == "adx":
        adx = value
        plus = kwargs.get("plus", 0)
        minus = kwargs.get("minus", 0)
        if adx >= ADX_STRONG and plus > minus:
            return "🟢"
        if adx >= ADX_STRONG and minus > plus:
            return "🔴"
        return "🟡"
    if kind == "adx_strength":
        adx = value
        if adx >= 25:
            return "🟢"
        if adx >= 20:
            return "🟡"
        return "⚪"
    if kind == "volume":
        if value >= VOLUME_GOOD:
            return "🟢"
        if value >= VOLUME_NEUTRAL:
            return "🟡"
        if value >= VOLUME_WEAK:
            return "🟠"
        return "🔴"
    return "🟡"


def level_circle(level, current_price, side):
    distance = abs(level - current_price) / current_price * 100
    if side == "support":
        return "🟢" if distance <= 2 else ("🟡" if distance <= 5 else "🟠")
    return "🟠" if distance <= 2 else ("🟡" if distance <= 5 else "🟢")

def money(x):
    return f"₹{x:,.2f}" if pd.notna(x) else "N/A"


def pct(x):
    return f"{x:.2f}%" if pd.notna(x) else "N/A"


def print_levels(title, levels, current_price, side):
    print(f"\n{title}")
    if not levels:
        print("  No reliable levels found")
        return
    for i, item in enumerate(levels, 1):
        circle = level_circle(item["level"], current_price, side)
        if item.get("projected", False):
            label = "PROJECTED"
            touches = "n/a"
        else:
            label = level_strength(item["touches"])
            touches = str(item["touches"])
        print(f"  {circle} {i}. ₹{item['level']:,.2f} | {label} | touches: {touches}")


def indicator_status(r):
    """Return beginner-friendly visual states for the V4.7 dashboard."""
    price = r["Price"]
    rsi = r["RSI"]
    macd_bull = r["MACD"] > r["MACD_Signal"]
    ema_bull = price > r["EMA20"] > r["EMA50"] > r["EMA200"]
    ema_bear = price < r["EMA20"] < r["EMA50"] < r["EMA200"]
    di_bull = r["+DI"] > r["-DI"]
    adx = r["ADX"]
    vol = r["VolumeRatio"]
    st_bull = r["ST_Direction"] == "BULLISH"

    if rsi >= 50 and rsi < 70: rsi_s = "🟢"
    elif rsi >= 35 and rsi < 50: rsi_s = "🟡"
    elif rsi < 35: rsi_s = "🟠"
    else: rsi_s = "🔴"

    macd_s = "🟢" if macd_bull else "🔴"
    ema_s = "🟢" if ema_bull else ("🔴" if ema_bear else "🟡")
    st_s = "🟢" if st_bull else "🔴"
    di_s = "🟢" if di_bull else "🔴"
    # ADX measures trend strength; DI determines trend direction.
    if adx >= 25: adx_s = "🟢"
    elif adx >= 20: adx_s = "🟡"
    else: adx_s = "⚪"
    if vol >= 1.5: vol_s = "🟢"
    elif vol >= 0.8: vol_s = "🟡"
    elif vol >= 0.5: vol_s = "🟠"
    else: vol_s = "🔴"

    # 52-week position is descriptive: high position is not automatically bullish.
    pos = r["52W_Position"]
    if pd.isna(pos): pos_s = "⚪"
    elif pos >= 80: pos_s = "🟢"
    elif pos >= 50: pos_s = "🟡"
    elif pos >= 20: pos_s = "🟠"
    else: pos_s = "🔴"

    return {
        "RSIIcon": rsi_s, "EMAIcon": ema_s, "MACDIcon": macd_s,
        "STIcon": st_s, "ADXIcon": adx_s, "DIIcon": di_s,
        "VOLIcon": vol_s, "52WIcon": pos_s,
        "EMAStructure": "BULLISH ALIGNMENT" if ema_bull else ("BEARISH ALIGNMENT" if ema_bear else "MIXED ALIGNMENT"),
        "MACDState": "BULLISH" if macd_bull else "BEARISH",
        "DIState": "+DI > -DI" if di_bull else "+DI < -DI",
        "ADXState": "STRONG" if adx >= 25 else ("MEANINGFUL" if adx >= 20 else "WEAK / EARLY"),
        "VolumeState": "STRONG" if vol >= 1.5 else ("NORMAL" if vol >= 0.8 else ("WEAK" if vol >= 0.5 else "VERY WEAK")),
    }


def print_indicator_dashboard(r):
    """V4.7 detailed indicator dashboard using already-calculated values."""
    st = indicator_status(r)
    print("\nINDICATOR DASHBOARD — V4.7")
    print("  Visual summary of the scanner's existing technical indicators")
    print("  " + "-" * 72)
    print(f"  RSI             {st['RSIIcon']} {r['RSI']:6.2f}   | {'Bullish momentum' if 50 <= r['RSI'] < 70 else 'Neutral / recovery' if 35 <= r['RSI'] < 50 else 'Weak / oversold area' if r['RSI'] < 35 else 'Overbought area'}")
    print(f"  EMA structure    {st['EMAIcon']} {st['EMAStructure']:<19} | Price {money(r['Price'])}")
    print(f"  EMA20            {money(r['EMA20']):>12}   | {'Price above EMA20' if r['Price'] > r['EMA20'] else 'Price below EMA20'}")
    print(f"  EMA50            {money(r['EMA50']):>12}   | {'Price above EMA50' if r['Price'] > r['EMA50'] else 'Price below EMA50'}")
    print(f"  EMA200           {money(r['EMA200']):>12}   | {'Price above EMA200' if r['Price'] > r['EMA200'] else 'Price below EMA200'}")
    print(f"  MACD             {st['MACDIcon']} {r['MACD']:8.2f}   | Signal {r['MACD_Signal']:8.2f} | {st['MACDState']}")
    print(f"  SuperTrend       {st['STIcon']} {money(r['SuperTrend']):>12}   | {r['ST_Direction']}")
    print(f"  ADX              {st['ADXIcon']} {r['ADX']:6.2f}   | {st['ADXState']:<13} | +DI {r['+DI']:.2f} / -DI {r['-DI']:.2f}")
    print(f"  DI direction     {st['DIIcon']} {st['DIState']:<12} | trend context")
    print(f"  Volume           {st['VOLIcon']} {r['VolumeRatio']:6.2f}x   | {st['VolumeState']:<8} vs 20D average")
    print(f"  ATR              ⚪ {money(r['ATR']):>12}   | approx. daily volatility measure")
    print(f"  52W position     {st['52WIcon']} {r['52W_Position']:6.1f}%   | position between 52W low and high")
    if pd.notna(r['BB_Upper']) and pd.notna(r['BB_Lower']):
        print(f"  Bollinger band   ⚪ {money(r['BB_Lower']):>12} - {money(r['BB_Upper']):<12} | current {money(r['Price'])}")
    print(f"  Breakout         {'🟢' if r['Breakout'] else '⚪'} {'CONFIRMED' if r['Breakout'] else 'NOT CONFIRMED'} | volume threshold {VOLUME_THRESHOLD:.2f}x")
    print(f"  Breakdown        {'🔴' if r['Breakdown'] else '⚪'} {'CONFIRMED' if r['Breakdown'] else 'NOT CONFIRMED'}")
    print(f"  S/R bias         {'🔴' if 'RESISTANCE' in r['SRBias'] else '🟢' if 'SUPPORT' in r['SRBias'] else '🟡'} {r['SRBias']}")


def final_indicator_dashboard(results):
    """Compact all-stock V4.4 indicator matrix for quick scanning."""
    if not results:
        return
    df = pd.DataFrame(results)
    print("\n" + "#" * 118)
    print("STOCKAI V4.7 — INDICATOR DASHBOARD")
    print("RSI + EMA + MACD + SuperTrend + ADX/DI + Volume + 52W + S/R")
    print("#" * 118)
    print(f"{'Stock':<12}{'Price':>11}  {'RSI':>5} {'EMA':>4} {'MACD':>5} {'ST':>4} {'ADX':>5} {'DI':>4} {'VOL':>5} {'52W':>5} {'S/R':>4}  {'Trend':<20}")
    print("-" * 118)
    for _, x in df.iterrows():
        st = indicator_status(x)
        sr = '🔴' if x['ResistanceDistancePct'] <= 1 else ('🟡' if x['ResistanceDistancePct'] <= 2.5 else ('🟢' if x['SupportDistancePct'] <= 2 else '🟡'))
        print(f"{x['Stock']:<12}{money(x['Price']):>11}  {st['RSIIcon']:>5} {st['EMAIcon']:>4} {st['MACDIcon']:>5} {st['STIcon']:>4} {st['ADXIcon']:>5} {st['DIIcon']:>4} {st['VOLIcon']:>5} {st['52WIcon']:>5} {sr:>4}  {x['Trend']:<20}")

    print("\nV4.7 INDICATOR LEGEND")
    print("  RSI: 🟢 constructive  🟡 neutral/recovery  🟠 weak/oversold  🔴 overbought/extreme")
    print("  EMA: 🟢 bullish alignment  🟡 mixed alignment  🔴 bearish alignment")
    print("  MACD/ST/DI: 🟢 bullish  🔴 bearish")
    print("  ADX: 🟢 strong trend (>=25)  🟡 meaningful/early (20-24.99)  ⚪ weak (<20)")
    print("  VOL: 🟢 >=1.5x  🟡 0.8-1.49x  🟠 0.5-0.79x  🔴 <0.5x")
    print("  52W: 🟢 upper zone  🟡 middle zone  🟠 lower-middle  🔴 lower zone")
    print("  S/R: 🔴 resistance very close  🟡 neutral/structural caution  🟢 support nearby")
    print("  Icons summarize indicator state; they are not independent buy/sell signals.")


def print_stock_report(r):
    print("\n" + "=" * 78)
    overall = status_circle(r["Action"], r["TechnicalRisk"], r["Opportunity"])
    print(f"{overall} {r['Stock']}  |  {money(r['Price'])}  |  {r['Action']}")
    print("=" * 78)
    print(f"Overall: {overall} | Trend: {indicator_circle('trend', r['Trend'])} {r['Trend']} | Signal View: {r['Signal']} | Opportunity: {r['Opportunity']} | Technical Risk Score: {r['TechnicalRisk']}/100")

    print("\nTECHNICAL SNAPSHOT")
    print(f"  {indicator_circle('rsi', r['RSI'])} RSI: {r['RSI']:.2f} | {indicator_circle('macd', r['MACD'], bullish=r['MACD'] > r['MACD_Signal'])} MACD: {r['MACD']:.2f} vs Signal {r['MACD_Signal']:.2f}")
    print(f"  {indicator_circle('adx_strength', r['ADX'])} ADX: {r['ADX']:.2f} | DI direction: {indicator_circle('adx', r['ADX'], plus=r['+DI'], minus=r['-DI'])} +DI {r['+DI']:.2f} / -DI {r['-DI']:.2f}")
    print(f"  {indicator_circle('st', r['ST_Direction'])} SuperTrend: {r['ST_Direction']} at {money(r['SuperTrend'])}")
    print(f"  EMA20/50/200: {money(r['EMA20'])} / {money(r['EMA50'])} / {money(r['EMA200'])}")
    print(f"  {indicator_circle('volume', r['VolumeRatio'])} Volume: {r['VolumeRatio']:.2f}x average | Volume status: {r['VolumeStatus']} | ATR: {money(r['ATR'])} | 52W Position: {pct(r['52W_Position'])}")

    print_levels("SUPPORT — 5 NEAREST LEVELS", r["Supports"], r["Price"], "support")
    print_levels("RESISTANCE — 5 NEAREST LEVELS", r["Resistances"], r["Price"], "resistance")

    print("\nS/R INTERPRETATION — V4.2")
    print(f"  S/R bias:              {r['SRBias']}")
    print(f"  Nearest support:       {money(r['NearestSupport'])} | {r['SupportStrength']} | {r['SupportDistancePct']:.2f}% below price" if pd.notna(r['SupportDistancePct']) else "  Nearest support:       N/A")
    print(f"  Nearest resistance:    {money(r['NearestResistance'])} | {r['ResistanceStrength']} | {r['ResistanceDistancePct']:.2f}% above price" if pd.notna(r['ResistanceDistancePct']) else "  Nearest resistance:    N/A")
    print(f"  Support condition:     {r['SupportStatus']}")
    print(f"  Resistance condition:  {r['ResistanceStatus']}")
    print(f"  Resistance room:       {r['ResistanceRoomATR']:.2f} ATR" if pd.notna(r['ResistanceRoomATR']) else "  Resistance room:       N/A")

    print("\nBREAKOUT / STRUCTURE")
    print(f"  Status:               {r['BreakoutStatus']}")
    print(f"  Nearest resistance:    {money(r['NearestResistance'])}")
    print(f"  Nearest support:       {money(r['NearestSupport'])}")
    print(f"  Historical resistance: {money(r['PriorResistance'])}")
    print(f"  Historical support:    {money(r['PriorSupport'])}")
    print(f"  Breakout: {r['Breakout']} | Breakdown: {r['Breakdown']} | Breakout watch: {r['BreakoutWatch']} | Breakdown watch: {r['BreakdownWatch']}")
    if r["Retest"]:
        date_txt = str(r['RetestDate'].date()) if r.get('RetestDate') is not None else "recent"
        print(f"  Retest: YES at actual broken level {money(r['RetestLevel'])} | breakout date: {date_txt}")
    else:
        print("  Retest: NO")

    print("\nENTRY / EXIT PLAN")
    print(f"  Entry type:       {r['EntryType']}")
    print(f"  Reference price:  {money(r['ReferencePrice'])}")
    print(f"  Pullback zone:    {money(r['EntryLow'])} - {money(r['EntryHigh'])}")
    if r["Breakdown"]:
        print("  Breakout trigger: N/A while breakdown is active")
    else:
        print(f"  Breakout confirmation: {money(r['BreakoutEntry'])}")
    print(f"  Stop loss:        {money(r['StopLoss'])}")
    print(f"  Target 1:         {money(r['Target1'])}")
    print(f"  Target 2:         {money(r['Target2'])}")
    print(f"  Target 3:         {money(r['Target3'])}")
    print(f"  Risk / Reward:    1 : {r['RR']:.2f}")
    print(f"  Technical Risk Score:   {r['TechnicalRisk']}/100")
    print(f"  Mechanical Stop Risk:       {r['TradeRiskPct']:.2f}% | {r['TradeRiskLevel']} (entry to stop)")
    print(f"  Existing-position exit trigger: {money(r['ExitTrigger'])}")
    print(f"  Profit-booking area 1:          {money(r['ProfitExit1'])}")
    print(f"  Profit-booking area 2:          {money(r['ProfitExit2'])}")
    print(f"  Resistance before T1:           {money(r['Target1Resistance'])}")
    print(f"  Resistance before T2:           {money(r['Target2Resistance'])}")
    print(f"  Resistance before T3:           {money(r['Target3Resistance'])}")

    print("\nTRADE SETUP ENGINE — V4.7")
    print(f"  Setup state:          {r['SetupState']}")
    print(f"  Entry plan:           {r['EntryPlan']}")
    print(f"  Trigger type:         {r['TriggerType']}")
    print(f"  Immediate trigger R1: {money(r['ImmediateTriggerPrice'])}" if pd.notna(r['ImmediateTriggerPrice']) else "  Immediate trigger R1: N/A")
    print(f"  Breakout confirm:     {money(r['BreakoutConfirmationPrice'])}" if pd.notna(r['BreakoutConfirmationPrice']) else "  Breakout confirm:     N/A")
    print(f"  Reference entry:      {money(r['ReferencePrice'])}")
    print(f"  Pullback zone:        {money(r['EntryLow'])} - {money(r['EntryHigh'])}")
    print(f"  Trade stop:           {money(r['TradeStopPrice'])}")
    print(f"  Setup invalidation:   {money(r['SetupInvalidationPrice'])}")
    print(f"  Mechanical Stop Risk:           {r['TradeRiskPct']:.2f}% | {r['SetupRiskLevel']}")
    print(f"  Breakout distance:    {r['BreakoutDistancePct']:.2f}%" if pd.notna(r['BreakoutDistancePct']) else "  Breakout distance:    N/A")
    print(f"  T1 room:              {r['Target1DistancePct']:.2f}%")
    print(f"  T2 room:              {r['Target2DistancePct']:.2f}%")
    print(f"  T3 room:              {r['Target3DistancePct']:.2f}%")
    print("  Confirmation checklist:")
    for item in r["ConfirmationChecklist"]:
        print(f"    • {item}")
    print(f"  Setup ready:          {'YES' if r['SetupReady'] else 'NO'}")
    print(f"  Note:                 {r['TradePlanNote']}")

    print_indicator_dashboard(r)

    print("\nWHY")
    if r["Reasons"]:
        for reason in r["Reasons"]:
            print(f"  • {reason}")
    else:
        print("  • No strong confirming factor detected")



def _card_icon(state):
    """Map a simple card state to the scanner's visual language."""
    if state == "bullish":
        return "🟢"
    if state == "bearish":
        return "🔴"
    if state == "caution":
        return "🟠"
    return "🟡"


def setup_completeness(r):
    """Descriptive count of currently confirmed setup components.
    This is not a probability, forecast, or performance score.
    """
    checks = [
        r.get("Breakout", False),
        r.get("VolumeRatio", 0) >= VOLUME_THRESHOLD,
        r.get("MACD", np.nan) > r.get("MACD_Signal", np.nan),
        r.get("ST_Direction", "") == "BULLISH",
        r.get("+DI", np.nan) > r.get("-DI", np.nan),
        r.get("ADX", 0) >= 20,
    ]
    count = sum(bool(x) for x in checks)
    if count >= 5:
        return count, "HIGH"
    if count >= 3:
        return count, "MEDIUM"
    return count, "LOW"


def stock_card(r):
    """V4.7 beginner-friendly one-screen stock card.

    Uses only values already calculated by the deterministic scanner.
    It does not create a new scoring model or price forecast.
    """
    price = r["Price"]
    rsi = r["RSI"]
    macd_bull = r["MACD"] > r["MACD_Signal"]
    ema_bull = price > r["EMA20"] > r["EMA50"] > r["EMA200"]
    ema_bear = price < r["EMA20"] < r["EMA50"] < r["EMA200"]
    st_bull = r["ST_Direction"] == "BULLISH"
    di_bull = r["+DI"] > r["-DI"]
    vol = r["VolumeRatio"]

    if 50 <= rsi < 70:
        rsi_state = "bullish"
    elif rsi < 35:
        rsi_state = "caution"
    elif rsi >= 70:
        rsi_state = "caution"
    else:
        rsi_state = "neutral"

    if r["SetupState"].startswith("NO NEW ENTRY"):
        headline_icon = "🔴"
    elif r["SetupState"] in ["BREAKOUT CONFIRMED", "BREAKOUT RETEST"]:
        headline_icon = "🟢"
    else:
        headline_icon = "🟡"

    # Beginner-friendly confirmation summary.
    confirmations = []
    missing = []
    checks = [
        ("MACD", macd_bull),
        ("SuperTrend", st_bull),
        ("+DI", di_bull),
        ("Volume", vol >= VOLUME_THRESHOLD),
    ]
    for name, ok in checks:
        (confirmations if ok else missing).append(name)

    if ema_bull:
        confirmations.append("EMA alignment")
    elif ema_bear:
        missing.append("EMA alignment")

    if r["Breakout"]:
        confirmation_text = "BREAKOUT CONFIRMED"
    elif r["Retest"]:
        confirmation_text = "BREAKOUT RETEST"
    elif r["SetupState"] == "WAIT — RESISTANCE":
        confirmation_text = "CLEAR R1 → CONFIRM BREAKOUT"
    elif r["SetupState"] == "WATCH — RECOVERY":
        confirmation_text = "RECOVERY → CONFIRM TREND"
    elif r["SetupState"] == "WATCH — SUPPORT":
        confirmation_text = "WATCH SUPPORT HOLD"
    elif r["SetupState"].startswith("NO NEW ENTRY"):
        confirmation_text = "BEARISH / NO NEW ENTRY"
    else:
        confirmation_text = "WAIT FOR CONFIRMATION"

    if confirmations:
        why_positive = ", ".join(confirmations[:4])
    else:
        why_positive = "No major bullish confirmation"
    if missing:
        why_missing = ", ".join(missing[:4])
    else:
        why_missing = "No major missing confirmation"

    completeness_count, completeness_label = setup_completeness(r)

    return {
        "headline_icon": headline_icon,
        "rsi_icon": _card_icon(rsi_state),
        "ema_icon": "🟢" if ema_bull else ("🔴" if ema_bear else "🟡"),
        "ema_structure": "BULLISH ALIGNMENT" if ema_bull else ("BEARISH ALIGNMENT" if ema_bear else "MIXED ALIGNMENT"),
        "macd_icon": "🟢" if macd_bull else "🔴",
        "st_icon": "🟢" if st_bull else "🔴",
        "adx_icon": indicator_circle("adx_strength", r["ADX"]),
        "di_icon": "🟢" if di_bull else "🔴",
        "vol_icon": "🟢" if vol >= 1.5 else ("🟡" if vol >= 0.8 else ("🟠" if vol >= 0.5 else "🔴")),
        "confirmation_text": confirmation_text,
        "completeness_count": completeness_count,
        "completeness_label": completeness_label,
        "why_positive": why_positive,
        "why_missing": why_missing,
    }


def print_stock_card(r):
    """Print a compact V4.7 stock card."""
    c = stock_card(r)
    print("\n" + "╔" + "═" * 76 + "╗")
    print(f"║ {c['headline_icon']} {r['Stock']:<12} {money(r['Price']):>14}  | {r['Action']:<30} ║")
    print("╠" + "═" * 76 + "╣")
    print(f"║ Trend        {indicator_circle('trend', r['Trend'])} {r['Trend']:<22} | Setup: {r['SetupState']:<25} ║")
    print(f"║ RSI          {c['rsi_icon']} {r['RSI']:>6.2f}              | EMA: {c['ema_icon']} {c['ema_structure']:<24} ║")
    print(f"║ MACD         {c['macd_icon']} {'BULLISH' if r['MACD'] > r['MACD_Signal'] else 'BEARISH':<8}          | SuperTrend: {c['st_icon']} {r['ST_Direction']:<15} ║")
    print(f"║ ADX / DI     {c['adx_icon']} {r['ADX']:>5.2f}  | DI: {c['di_icon']} +DI {r['+DI']:>5.2f} -DI {r['-DI']:>5.2f} | Volume: {c['vol_icon']} {r['VolumeRatio']:.2f}x ║")
    print(f"║ Context      {r.get('MarketStockContext', 'MIXED MARKET / STOCK CONTEXT'):<68} ║")
    print(f"║ Completeness {c['completeness_label']:<7} ({c['completeness_count']}/6 confirmations currently present)             ║")
    print("╠" + "═" * 76 + "╣")
    print(f"║ R1 trigger   {money(r['ImmediateTriggerPrice']):>12}  | Breakout confirmation {money(r['BreakoutConfirmationPrice']):>12} ║")
    print(f"║ Trade stop   {money(r['TradeStopPrice']):>12}  | Invalidation           {money(r['SetupInvalidationPrice']):>12} ║")
    print(f"║ Target 1     {money(r['Target1']):>12}  | Target 2               {money(r['Target2']):>12} ║")
    print(f"║ Target 3     {money(r['Target3']):>12}  | Mechanical stop risk    {r['TradeRiskPct']:>8.2f}% ║")
    print("╠" + "═" * 76 + "╣")
    print(f"║ STATUS       {c['confirmation_text']:<61} ║")
    print(f"║ WHY          + {c['why_positive']:<61} ║")
    print(f"║              - {c['why_missing']:<61} ║")
    print("╚" + "═" * 76 + "╝")


def print_stock_cards(results):
    """Print all V4.7 stock cards."""
    if not results:
        return
    print("\n" + "#" * 118)
    print("STOCKAI V4.7 — STOCK CARDS")
    print("One-screen summary: trend + indicators + setup + levels + confirmation")
    print("#" * 118)
    for r in results:
        print_stock_card(r)



# ============================================================
# STOCKAI V4.7 — MARKET DASHBOARD
# Market context layer only. It does NOT change individual-stock logic.
# Primary market: NIFTY 50 (^NSEI)
# Optional volatility context: India VIX (^INDIAVIX)
# ============================================================

def market_regime_label(price, ema20, ema50, ema200, macd_bull, st_bull, adx, plus_di, minus_di):
    """Descriptive market regime from independent trend/momentum signals."""
    bull_votes = sum([
        price > ema20,
        price > ema50,
        price > ema200,
        macd_bull,
        st_bull,
        plus_di > minus_di,
    ])
    bear_votes = 6 - bull_votes

    if bull_votes >= 5 and adx >= 25:
        return "STRONG BULLISH TREND"
    if bear_votes >= 5 and adx >= 25:
        return "STRONG BEARISH TREND"
    if bull_votes >= 4:
        return "BULLISH / CONSTRUCTIVE"
    if bear_votes >= 4:
        return "BEARISH / CAUTIOUS"
    return "MIXED / RANGE"


def fetch_market_data(symbol="^NSEI"):
    """Fetch and calculate market indicators using the same technical engine."""
    try:
        raw = yf.download(symbol, period=DATA_PERIOD, interval="1d", auto_adjust=False, progress=False)
        df = clean_yfinance(raw)
        if df is None or len(df) < 220:
            return None
        df = add_indicators(df)
        row = df.iloc[-1]

        price = float(row["Close"])
        ema20 = float(row["EMA20"])
        ema50 = float(row["EMA50"])
        ema200 = float(row["EMA200"])
        rsi = float(row["RSI"])
        macd = float(row["MACD"])
        macd_signal = float(row["MACD_SIGNAL"])
        adx = float(row["ADX"])
        plus_di = float(row["PLUS_DI"])
        minus_di = float(row["MINUS_DI"])
        st = float(row["SUPERTREND"]) if pd.notna(row["SUPERTREND"]) else np.nan
        st_direction = "BULLISH" if float(row["ST_DIRECTION"]) == 1 else "BEARISH"
        vol_ratio = float(row["VOL_RATIO"]) if pd.notna(row["VOL_RATIO"]) else np.nan

        # Previous close and short-term change are descriptive market context.
        prev_close = float(df["Close"].iloc[-2])
        day_change_pct = ((price - prev_close) / prev_close * 100) if prev_close else np.nan
        close_5d = float(df["Close"].iloc[-6]) if len(df) >= 6 else np.nan
        change_5d_pct = ((price - close_5d) / close_5d * 100) if pd.notna(close_5d) and close_5d else np.nan
        close_20d = float(df["Close"].iloc[-21]) if len(df) >= 21 else np.nan
        change_20d_pct = ((price - close_20d) / close_20d * 100) if pd.notna(close_20d) and close_20d else np.nan

        return {
            "Symbol": symbol,
            "Name": "NIFTY 50",
            "Price": price,
            "RSI": rsi,
            "EMA20": ema20,
            "EMA50": ema50,
            "EMA200": ema200,
            "MACD": macd,
            "MACDSignal": macd_signal,
            "ADX": adx,
            "+DI": plus_di,
            "-DI": minus_di,
            "SuperTrend": st,
            "STDirection": st_direction,
            "VolumeRatio": vol_ratio,
            "DayChangePct": day_change_pct,
            "Change5DPct": change_5d_pct,
            "Change20DPct": change_20d_pct,
        }
    except Exception as exc:
        print(f"  Market data error ({symbol}): {exc}")
        return None


def market_indicator_icon(kind, value, **kwargs):
    if kind == "rsi":
        if 50 <= value < 70:
            return "🟢"
        if 35 <= value < 50:
            return "🟡"
        if value < 35:
            return "🟠"
        return "🔴"
    if kind == "macd":
        return "🟢" if kwargs.get("bullish", False) else "🔴"
    if kind == "ema":
        return "🟢" if kwargs.get("bullish", False) else ("🔴" if kwargs.get("bearish", False) else "🟡")
    if kind == "st":
        return "🟢" if value == "BULLISH" else "🔴"
    if kind == "adx":
        if value >= 25:
            return "🟢"
        if value >= 20:
            return "🟡"
        return "⚪"
    if kind == "di":
        return "🟢" if kwargs.get("bullish", False) else "🔴"
    if kind == "volume":
        return indicator_circle("volume", value)
    return "⚪"


def market_stock_context(market_regime, stock_signal, stock_trend):
    """Descriptive market-vs-stock context; not a forecast or recommendation."""
    market_bear = "BEARISH" in market_regime
    market_bull = "BULLISH" in market_regime or "CONSTRUCTIVE" in market_regime
    stock_bull = stock_signal in ["STRONG BULLISH", "BULLISH", "RECOVERY / MIXED"] or "UPTREND" in stock_trend
    stock_bear = stock_signal in ["STRONG BEARISH", "BEARISH"] or "DOWNTREND" in stock_trend
    if market_bear and stock_bull:
        return "MARKET WEAK / STOCK STRONGER"
    if market_bull and stock_bear:
        return "MARKET STRONGER / STOCK WEAKER"
    if market_bear and stock_bear:
        return "MARKET + STOCK BOTH WEAK"
    if market_bull and stock_bull:
        return "MARKET + STOCK BOTH CONSTRUCTIVE"
    return "MIXED MARKET / STOCK CONTEXT"


def print_market_dashboard(results):
    """Print V4.7 market context and breadth without altering stock signals."""
    print("\n" + "#" * 118)
    print("STOCKAI V4.7 — MARKET DASHBOARD")
    print("Market context first → then individual-stock technical setups")
    print("#" * 118)

    market = fetch_market_data("^NSEI")
    vix = fetch_market_data("^INDIAVIX")

    if market is None:
        print("  ⚪ NIFTY 50 market data unavailable — stock analysis continues unchanged.")
        return

    p = market["Price"]
    ema_bull = p > market["EMA20"] > market["EMA50"] > market["EMA200"]
    ema_bear = p < market["EMA20"] < market["EMA50"] < market["EMA200"]
    macd_bull = market["MACD"] > market["MACDSignal"]
    st_bull = market["STDirection"] == "BULLISH"
    di_bull = market["+DI"] > market["-DI"]
    regime = market_regime_label(p, market["EMA20"], market["EMA50"], market["EMA200"], macd_bull, st_bull, market["ADX"], market["+DI"], market["-DI"])

    regime_icon = "🟢" if regime.startswith("STRONG BULLISH") or regime.startswith("BULLISH") else ("🔴" if regime.startswith("STRONG BEARISH") or regime.startswith("BEARISH") else "🟡")

    print(f"  MARKET REGIME       {regime_icon} {regime}")
    print(f"  NIFTY 50            {money(p):>12} | Day {market['DayChangePct']:+.2f}% | 5D {market['Change5DPct']:+.2f}% | 20D {market['Change20DPct']:+.2f}%")
    print("  " + "-" * 90)
    print(f"  RSI                 {market_indicator_icon('rsi', market['RSI'])} {market['RSI']:>6.2f}")
    print(f"  EMA structure       {market_indicator_icon('ema', p, bullish=ema_bull, bearish=ema_bear)} {'BULLISH ALIGNMENT' if ema_bull else 'BEARISH ALIGNMENT' if ema_bear else 'MIXED ALIGNMENT':<20} | 20 {money(market['EMA20'])} | 50 {money(market['EMA50'])} | 200 {money(market['EMA200'])}")
    print(f"  MACD                {market_indicator_icon('macd', market['MACD'], bullish=macd_bull)} {'BULLISH' if macd_bull else 'BEARISH':<8} | MACD {market['MACD']:>8.2f} | Signal {market['MACDSignal']:>8.2f}")
    print(f"  SuperTrend          {market_indicator_icon('st', market['STDirection'])} {market['STDirection']:<8} | Level {money(market['SuperTrend'])}")
    print(f"  ADX / DI            {market_indicator_icon('adx', market['ADX'])} {market['ADX']:>6.2f} | DI {market_indicator_icon('di', market['+DI'], bullish=di_bull)} +DI {market['+DI']:>6.2f} / -DI {market['-DI']:>6.2f}")
    print(f"  Volume              {market_indicator_icon('volume', market['VolumeRatio'])} {market['VolumeRatio']:>6.2f}x average")

    if vix is not None:
        print(f"  India VIX           ⚪ {vix['Price']:>6.2f} | Day {vix['DayChangePct']:+.2f}%")
    else:
        print("  India VIX           ⚪ unavailable")

    # Breadth across the stocks already scanned.
    total = len(results)
    bullish = sum(1 for r in results if r["Signal"] in ["STRONG BULLISH", "BULLISH"] or r["Action"] in ["CONFIRMED BREAKOUT", "BREAKOUT RETEST", "WATCH — BULLISH"])
    bearish = sum(1 for r in results if r["Signal"] in ["STRONG BEARISH", "BEARISH"] or r["Action"].startswith("AVOID"))
    mixed = max(0, total - bullish - bearish)
    breakouts = sum(1 for r in results if r["Breakout"])
    breakdowns = sum(1 for r in results if r["Breakdown"])
    near_resistance = sum(1 for r in results if r.get("NearResistance", False))
    avg_risk = float(np.mean([r["TechnicalRisk"] for r in results])) if results else np.nan

    print("\n  STOCK BREADTH — CURRENT SCANNED UNIVERSE")
    print("  " + "-" * 90)
    print(f"  Stocks scanned       {total:>3} | 🟢 Bullish/constructive {bullish:>2} | 🟡 Mixed {mixed:>2} | 🔴 Bearish/avoid {bearish:>2}")
    print(f"  Breakouts            {breakouts:>3} | Breakdowns {breakdowns:>2} | Near resistance {near_resistance:>2} | Avg technical risk score {avg_risk:>5.1f}/100")

    if total:
        breadth_pct = bullish / total * 100
        if breadth_pct >= 60:
            breadth_label = "BULLISH BREADTH"
            breadth_icon = "🟢"
        elif breadth_pct <= 40:
            breadth_label = "BEARISH BREADTH"
            breadth_icon = "🔴"
        else:
            breadth_label = "MIXED BREADTH"
            breadth_icon = "🟡"
        print(f"  Breadth view          {breadth_icon} {breadth_label} | {breadth_pct:.0f}% bullish/constructive")

    print("\n  HOW TO READ V4.7")
    print("  • Market regime describes NIFTY 50 conditions; it is not a forecast.")
    print("  • Breadth describes only the stocks in this scanner's current universe.")
    print("  • Market context does NOT override an individual stock's setup, stop, or breakout logic.")
    print("  • India VIX is volatility context, not a buy/sell signal.")



# ============================================================
# STOCKAI V5 — FUNDAMENTALS ENGINE
# Deterministic fundamental data layer using yfinance.
# This module adds context; it does NOT alter V4.7 technical signals.
# ============================================================

FUNDAMENTAL_SCORE_MAX = 100
FUNDAMENTAL_HISTORY_YEARS = 4

# ============================================================
# V5.5 SECTOR-AWARE FUNDAMENTALS
# ------------------------------------------------------------
# The generic V5 score is retained as the common language, but
# the score is now built from metrics that matter more for the
# company's business model. Missing sector metrics are NOT treated
# as zero; the score is normalized over available components.
# ============================================================

SECTOR_PROFILES = {
    "BANKS": {
        "keywords": ["bank"],
        "metrics": [
            ("ROE", "ROE", 20, "higher", 15, 10),
            ("ROA", "ROA", 15, "higher", 1.5, 1.0),
            ("NIM", "NIM", 20, "higher", 4.0, 3.0),
            ("GNPA", "GNPA", 15, "lower", 2.0, 4.0),
            ("NNPA", "NNPA", 10, "lower", 1.0, 2.0),
            ("Capital Adequacy", "CapitalAdequacy", 10, "higher", 15, 12),
            ("Profit Growth", "ProfitGrowthPct", 5, "higher", 10, 0),
            ("Credit/Loan Growth", "LoanGrowthPct", 5, "higher", 10, 0),
        ],
    },
    "IT": {
        "keywords": ["software", "information technology", "it services", "information services"],
        "metrics": [
            ("ROE", "ROE", 20, "higher", 20, 12),
            ("Operating Margin", "OperatingMargin", 20, "higher", 20, 15),
            ("Revenue Growth", "RevenueGrowthPct", 15, "higher", 10, 0),
            ("Profit Growth", "ProfitGrowthPct", 10, "higher", 10, 0),
            ("FCF", "FCFPositive", 15, "binary", 1, 0),
            ("Debt/Equity", "DebtToEquity", 10, "lower", 50, 100),
            ("ROCE", "ROCE", 10, "higher", 20, 12),
        ],
    },
    "INDUSTRIALS": {
        "keywords": ["industrial", "electrical equipment", "engineering", "machinery", "specialty industrial"],
        "metrics": [
            ("ROCE", "ROCE", 20, "higher", 15, 10),
            ("ROE", "ROE", 15, "higher", 15, 10),
            ("Revenue Growth", "RevenueGrowthPct", 15, "higher", 10, 0),
            ("Profit Growth", "ProfitGrowthPct", 10, "higher", 10, 0),
            ("FCF", "FCFPositive", 15, "binary", 1, 0),
            ("Debt/Equity", "DebtToEquity", 15, "lower", 50, 100),
            ("Operating Margin", "OperatingMargin", 10, "higher", 15, 8),
        ],
    },
    "AUTO": {
        "keywords": ["auto", "automobile", "motor", "vehicle", "truck", "parts"],
        "metrics": [
            ("Revenue Growth", "RevenueGrowthPct", 20, "higher", 10, 0),
            ("Profit Growth", "ProfitGrowthPct", 15, "higher", 10, 0),
            ("Operating Margin", "OperatingMargin", 15, "higher", 15, 8),
            ("ROCE", "ROCE", 15, "higher", 15, 10),
            ("ROE", "ROE", 10, "higher", 15, 10),
            ("Debt/Equity", "DebtToEquity", 15, "lower", 50, 100),
            ("FCF", "FCFPositive", 10, "binary", 1, 0),
        ],
    },
    "ENERGY": {
        "keywords": ["oil", "gas", "energy", "integrated oil", "refining", "power", "utilities"],
        "metrics": [
            ("ROCE", "ROCE", 20, "higher", 15, 10),
            ("ROE", "ROE", 15, "higher", 15, 10),
            ("Revenue Growth", "RevenueGrowthPct", 10, "higher", 10, 0),
            ("Profit Growth", "ProfitGrowthPct", 15, "higher", 10, 0),
            ("FCF", "FCFPositive", 15, "binary", 1, 0),
            ("Debt/Equity", "DebtToEquity", 15, "lower", 60, 120),
            ("Operating Margin", "OperatingMargin", 10, "higher", 15, 8),
        ],
    },
    "PORTS_LOGISTICS": {
        "keywords": ["port", "marine transportation", "transportation", "logistics", "shipping"],
        "metrics": [
            ("ROCE", "ROCE", 20, "higher", 15, 10),
            ("ROE", "ROE", 15, "higher", 15, 10),
            ("Revenue Growth", "RevenueGrowthPct", 15, "higher", 10, 0),
            ("Profit Growth", "ProfitGrowthPct", 15, "higher", 10, 0),
            ("FCF", "FCFPositive", 15, "binary", 1, 0),
            ("Debt/Equity", "DebtToEquity", 10, "lower", 75, 125),
            ("Operating Margin", "OperatingMargin", 10, "higher", 20, 10),
        ],
    },
    "COMMUNICATION_EQUIPMENT": {
        "keywords": ["communication equipment", "networking", "optical fiber", "telecom equipment"],
        "metrics": [
            ("Revenue Growth", "RevenueGrowthPct", 20, "higher", 10, 0),
            ("Profit Growth", "ProfitGrowthPct", 15, "higher", 10, 0),
            ("Operating Margin", "OperatingMargin", 15, "higher", 15, 8),
            ("ROCE", "ROCE", 15, "higher", 15, 10),
            ("Debt/Equity", "DebtToEquity", 15, "lower", 50, 100),
            ("FCF", "FCFPositive", 10, "binary", 1, 0),
            ("ROE", "ROE", 10, "higher", 15, 10),
        ],
    },
    "DEFAULT": {
        "keywords": [],
        "metrics": [
            ("Revenue Growth", "RevenueGrowthPct", 15, "higher", 10, 0),
            ("Profit Growth", "ProfitGrowthPct", 15, "higher", 10, 0),
            ("ROE", "ROE", 15, "higher", 15, 10),
            ("ROCE", "ROCE", 15, "higher", 15, 10),
            ("Debt/Equity", "DebtToEquity", 15, "lower", 50, 100),
            ("FCF", "FCFPositive", 15, "binary", 1, 0),
            ("Operating Margin", "OperatingMargin", 10, "higher", 15, 8),
        ],
    },
}


def _safe_float(value):
    try:
        if value is None or pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def _first_info_value(info, keys):
    for key in keys:
        value = _safe_float(info.get(key))
        if pd.notna(value):
            return value
    return np.nan


def _latest_statement_value(statement, candidates):
    if statement is None or statement.empty:
        return np.nan
    for name in candidates:
        if name in statement.index:
            row = statement.loc[name]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            for value in row.tolist():
                value = _safe_float(value)
                if pd.notna(value):
                    return value
    return np.nan


def _prior_statement_value(statement, candidates):
    if statement is None or statement.empty:
        return np.nan
    for name in candidates:
        if name in statement.index:
            row = statement.loc[name]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            values = [_safe_float(v) for v in row.tolist()]
            values = [v for v in values if pd.notna(v)]
            if len(values) >= 2:
                return values[1]
    return np.nan


def _growth_pct(current, previous):
    if pd.isna(current) or pd.isna(previous) or previous == 0:
        return np.nan
    return (current / previous - 1.0) * 100.0


def _format_fund_value(value, suffix=""):
    if pd.isna(value):
        return "N/A"
    if abs(value) >= 1e7:
        return f"₹{value/1e7:,.2f} Cr{suffix}"
    return f"₹{value:,.0f}{suffix}"


def _sector_bucket(sector, industry, symbol=""):
    text = f"{sector} {industry}".lower()
    ticker = str(symbol).replace(".NS", "").upper()

    # Explicit ticker overrides prevent broad keyword collisions.
    # QPOWER is an electrical-equipment/industrial business; HFCL is
    # communication equipment.
    if ticker == "QPOWER":
        return "INDUSTRIALS"
    if ticker == "HFCL":
        return "COMMUNICATION_EQUIPMENT"

    # Industry-specific mapping before broad sector mapping.
    if "bank" in text:
        return "BANKS"
    if any(k in text for k in ["communication equipment", "telecom equipment", "optical fiber", "networking"]):
        return "COMMUNICATION_EQUIPMENT"
    if any(k in text for k in ["software", "information technology", "information services"]):
        return "IT"
    if any(k in text for k in ["electrical equipment", "industrial", "engineering", "machinery", "specialty industrial"]):
        return "INDUSTRIALS"
    if any(k in text for k in ["port", "marine transportation", "transportation", "logistics", "shipping"]):
        return "PORTS_LOGISTICS"
    if any(k in text for k in ["auto", "automobile", "motor", "vehicle", "truck"]):
        return "AUTO"
    if any(k in text for k in ["oil", "gas", "energy", "power", "utility", "utilities"]):
        return "ENERGY"
    return "DEFAULT"


def _metric_score(value, direction, strong, acceptable):
    if pd.isna(value):
        return np.nan
    if direction == "binary":
        return 100.0 if value > 0 else 0.0
    if direction == "higher":
        if value >= strong:
            return 100.0
        if value >= acceptable:
            if strong == acceptable:
                return 50.0
            return 50.0 + 50.0 * (value - acceptable) / (strong - acceptable)
        # Keep a declining score below the acceptable threshold without
        # turning a modest miss into an automatic zero.
        if acceptable == 0:
            return max(0.0, 50.0 * (value / strong))
        return max(0.0, 50.0 * (value / acceptable))
    if direction == "lower":
        if value <= strong:
            return 100.0
        if value <= acceptable:
            return 50.0 + 50.0 * (acceptable - value) / (acceptable - strong)
        return max(0.0, 50.0 * (acceptable / value)) if value > 0 else 100.0
    return np.nan


def _sector_metric_label(key):
    return {
        "ROE": "ROE",
        "ROA": "ROA",
        "NIM": "NIM",
        "GNPA": "GNPA",
        "NNPA": "NNPA",
        "CapitalAdequacy": "Capital adequacy",
        "LoanGrowthPct": "Loan/credit growth",
        "OperatingMargin": "Operating margin",
        "RevenueGrowthPct": "Revenue growth",
        "ProfitGrowthPct": "Profit growth",
        "ROCE": "ROCE",
        "DebtToEquity": "Debt/equity",
        "FCFPositive": "Free cash flow",
    }.get(key, key)


def fetch_fundamentals(symbol):
    """Fetch common + sector-specific fundamentals with defensive fallbacks."""
    try:
        ticker = yf.Ticker(symbol)
        info = {}
        try:
            info = ticker.get_info()
        except Exception:
            try:
                info = ticker.info
            except Exception:
                info = {}

        income = pd.DataFrame()
        balance = pd.DataFrame()
        cashflow = pd.DataFrame()
        try: income = ticker.income_stmt
        except Exception: pass
        try: balance = ticker.balance_sheet
        except Exception: pass
        try: cashflow = ticker.cashflow
        except Exception: pass

        revenue = _latest_statement_value(income, ["Total Revenue", "Operating Revenue"])
        prev_revenue = _prior_statement_value(income, ["Total Revenue", "Operating Revenue"])
        net_income = _latest_statement_value(income, ["Net Income", "Net Income Common Stockholders"])
        prev_net_income = _prior_statement_value(income, ["Net Income", "Net Income Common Stockholders"])
        ebit = _latest_statement_value(income, ["EBIT", "Operating Income"])

        eps = _safe_float(info.get("trailingEps"))
        roe_raw = _first_info_value(info, ["returnOnEquity"])
        roa_raw = _first_info_value(info, ["returnOnAssets"])
        roe = roe_raw * 100 if pd.notna(roe_raw) and abs(roe_raw) <= 2 else roe_raw
        roa = roa_raw * 100 if pd.notna(roa_raw) and abs(roa_raw) <= 2 else roa_raw
        debt_to_equity = _safe_float(info.get("debtToEquity"))
        profit_margin_raw = _safe_float(info.get("profitMargins"))
        operating_margin_raw = _safe_float(info.get("operatingMargins"))
        profit_margin = profit_margin_raw * 100 if pd.notna(profit_margin_raw) and abs(profit_margin_raw) <= 2 else profit_margin_raw
        operating_margin = operating_margin_raw * 100 if pd.notna(operating_margin_raw) and abs(operating_margin_raw) <= 2 else operating_margin_raw
        pe = _safe_float(info.get("trailingPE"))
        pb = _safe_float(info.get("priceToBook"))

        total_assets = _latest_statement_value(balance, ["Total Assets"])
        current_liabilities = _latest_statement_value(balance, ["Current Liabilities", "Total Current Liabilities"])
        invested_base = total_assets - current_liabilities if pd.notna(total_assets) and pd.notna(current_liabilities) else np.nan
        roce = (ebit / invested_base) * 100 if pd.notna(ebit) and pd.notna(invested_base) and invested_base > 0 else np.nan

        cfo = _latest_statement_value(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
        capex = _latest_statement_value(cashflow, ["Capital Expenditure", "Capital Expenditures"])
        fcf = cfo - abs(capex) if pd.notna(cfo) and pd.notna(capex) else (cfo if pd.notna(cfo) else np.nan)

        current_ratio = _safe_float(info.get("currentRatio"))
        revenue_growth = _growth_pct(revenue, prev_revenue)
        profit_growth = _growth_pct(net_income, prev_net_income)
        market_cap = _safe_float(info.get("marketCap"))
        insider_pct = _safe_float(info.get("heldPercentInsiders"))
        if pd.notna(insider_pct): insider_pct *= 100

        sector = str(info.get("sector") or "N/A")
        industry = str(info.get("industry") or "N/A")
        sector_bucket = _sector_bucket(sector, industry, symbol)

        # Sector-specific data. Yahoo/yfinance coverage varies by company,
        # so every metric is optional and explicitly reported as N/A if absent.
        nim_raw = _first_info_value(info, ["netInterestMargin", "netInterestMarginTTM", "netInterestMarginAnnual"])
        nim = nim_raw * 100 if pd.notna(nim_raw) and abs(nim_raw) <= 2 else nim_raw
        gnpa = _first_info_value(info, ["grossNpa", "grossNonPerformingAssets", "grossNonPerformingAssetRatio", "grossNonPerformingAssetsRatio"])
        nnpa = _first_info_value(info, ["netNpa", "netNonPerformingAssets", "netNonPerformingAssetRatio", "netNonPerformingAssetsRatio"])
        capital_adequacy = _first_info_value(info, ["capitalAdequacyRatio", "capitalAdequacy", "tier1CapitalRatio"])
        loan_growth = _first_info_value(info, ["loanGrowth", "totalLoanGrowth", "totalLoansGrowth", "creditGrowth"])
        if pd.notna(loan_growth) and abs(loan_growth) <= 2: loan_growth *= 100

        valuation_notes = []
        if pd.notna(pe):
            if pe >= 50: valuation_notes.append("P/E is high")
            elif pe >= 25: valuation_notes.append("P/E is elevated")
        if pd.notna(pb):
            if pb >= 10: valuation_notes.append("P/B is very high")
            elif pb >= 5: valuation_notes.append("P/B is elevated")
        if pd.notna(fcf) and fcf < 0: valuation_notes.append("FCF is negative")

        metric_values = {
            "ROE": roe, "ROA": roa, "NIM": nim, "GNPA": gnpa,
            "NNPA": nnpa, "CapitalAdequacy": capital_adequacy,
            "LoanGrowthPct": loan_growth, "OperatingMargin": operating_margin,
            "RevenueGrowthPct": revenue_growth, "ProfitGrowthPct": profit_growth,
            "ROCE": roce, "DebtToEquity": debt_to_equity,
            "FCFPositive": 1.0 if pd.notna(fcf) and fcf > 0 else (-1.0 if pd.notna(fcf) else np.nan),
        }

        profile = SECTOR_PROFILES.get(sector_bucket, SECTOR_PROFILES["DEFAULT"])
        weighted = 0.0
        weight_available = 0.0
        sector_components = []
        for label, key, weight, direction, strong, acceptable in profile["metrics"]:
            value = metric_values.get(key, np.nan)
            ms = _metric_score(value, direction, strong, acceptable)
            if pd.notna(ms):
                weighted += ms * weight
                weight_available += weight
                sector_components.append({
                    "Label": label, "Key": key, "Value": value,
                    "Weight": weight, "MetricScore": ms,
                    "Direction": direction, "Strong": strong, "Acceptable": acceptable,
                })

        raw_score = (weighted / weight_available) if weight_available else np.nan
        total_profile_weight = sum(m[2] for m in profile["metrics"])
        coverage_pct = (weight_available / total_profile_weight * 100.0) if total_profile_weight else 0.0
        available = len(sector_components)

        if coverage_pct >= 80:
            data_confidence = "HIGH"
        elif coverage_pct >= 60:
            data_confidence = "MEDIUM"
        elif coverage_pct > 0:
            data_confidence = "LOW"
        else:
            data_confidence = "NONE"

        # The normalized score is already 0-100. Only incomplete data gets a
        # transparent confidence ceiling; high-confidence scores remain purely
        # metric-driven.
        if pd.notna(raw_score):
            if data_confidence == "LOW":
                score = min(round(raw_score), 70)
            elif data_confidence == "MEDIUM":
                score = min(round(raw_score), 85)
            else:
                score = round(raw_score)
        else:
            score = np.nan

        if pd.isna(score) or available < 2:
            health = "INSUFFICIENT FUNDAMENTAL DATA"
        elif data_confidence == "HIGH" and score >= 75:
            health = "STRONG FUNDAMENTAL PROFILE"
        elif score >= 55:
            health = "CONSTRUCTIVE FUNDAMENTAL PROFILE"
        elif score >= 35:
            health = "MIXED FUNDAMENTAL PROFILE"
        else:
            health = "WEAK FUNDAMENTAL PROFILE"

        sector_notes = []
        sector_risks = []
        for c in sector_components:
            v = c["Value"]
            key = c["Key"]
            if key == "FCFPositive":
                if v > 0: sector_notes.append("Positive free cash flow")
                else: sector_risks.append("Negative free cash flow")
            elif c["Direction"] == "higher":
                if v >= c["Strong"]: sector_notes.append(f"{c['Label']} is strong")
                elif v < c["Acceptable"]: sector_risks.append(f"{c['Label']} is below the sector threshold")
            elif c["Direction"] == "lower":
                if v <= c["Strong"]: sector_notes.append(f"{c['Label']} is controlled")
                elif v > c["Acceptable"]: sector_risks.append(f"{c['Label']} is elevated")

        return {
            "FundamentalScore": score,
            "RawFundamentalScore": round(raw_score) if pd.notna(raw_score) else np.nan,
            "FundamentalHealth": health,
            "FundamentalDataPoints": available,
            "FundamentalCoveragePct": coverage_pct,
            "FundamentalDataConfidence": data_confidence,
            "Sector": sector, "Industry": industry, "SectorBucket": sector_bucket,
            "Revenue": revenue, "RevenueGrowthPct": revenue_growth,
            "NetIncome": net_income, "ProfitGrowthPct": profit_growth,
            "EPS": eps, "ROE": roe, "ROA": roa, "ROCE": roce,
            "NIM": nim, "GNPA": gnpa, "NNPA": nnpa,
            "CapitalAdequacy": capital_adequacy, "LoanGrowthPct": loan_growth,
            "DebtToEquity": debt_to_equity, "ProfitMargin": profit_margin,
            "OperatingMargin": operating_margin, "CurrentRatio": current_ratio,
            "CFO": cfo, "Capex": capex, "FCF": fcf,
            "PE": pe, "PB": pb, "MarketCap": market_cap,
            "InsiderHoldingPct": insider_pct, "ValuationNotes": valuation_notes,
            "SectorComponents": sector_components,
            "SectorNotes": sector_notes[:5], "SectorRisks": sector_risks[:5],
        }
    except Exception as exc:
        return {
            "FundamentalScore": np.nan,
            "FundamentalHealth": "FUNDAMENTAL DATA ERROR",
            "FundamentalDataPoints": 0,
            "FundamentalCoveragePct": 0.0,
            "FundamentalDataConfidence": "NONE",
            "SectorBucket": "DEFAULT",
            "FundamentalError": str(exc)[:120],
        }


def fundamental_icon(score, health):
    if "ERROR" in health or "INSUFFICIENT" in health or pd.isna(score): return "⚪"
    if score >= 75: return "🟢"
    if score >= 55: return "🟡"
    if score >= 35: return "🟠"
    return "🔴"


def _fmt_pct(v):
    return "N/A" if pd.isna(v) else f"{v:+.1f}%"


def _fmt_num(v):
    return "N/A" if pd.isna(v) else f"{v:.1f}"


def _fundamental_quality_flags(f):
    flags = list(f.get("ValuationNotes", []))
    bucket = f.get("SectorBucket", "DEFAULT")
    roce = f.get("ROCE", np.nan)

    # Use the sector profile's own ROCE threshold instead of a generic 10%
    # rule, and keep this as a quality flag separate from health scoring.
    if pd.notna(roce):
        for label, key, weight, direction, strong, acceptable in SECTOR_PROFILES.get(bucket, SECTOR_PROFILES["DEFAULT"])["metrics"]:
            if key == "ROCE" and direction == "higher" and roce < acceptable:
                flags.append(f"ROCE below sector threshold ({acceptable:.0f}%)")
                break

    if bucket == "BANKS":
        for key, label in [("NIM", "NIM"), ("GNPA", "GNPA"), ("NNPA", "NNPA"), ("CapitalAdequacy", "Capital adequacy")]:
            if pd.isna(f.get(key, np.nan)):
                flags.append(f"{label} unavailable")
    return list(dict.fromkeys(flags))[:5]

def _sector_dashboard_detail(f):
    bucket = f.get("SectorBucket", "DEFAULT")
    if bucket == "BANKS":
        return f"ROE {_fmt_pct(f.get('ROE',np.nan))} | ROA {_fmt_pct(f.get('ROA',np.nan))} | NIM {_fmt_pct(f.get('NIM',np.nan))} | GNPA {_fmt_pct(f.get('GNPA',np.nan))} | NNPA {_fmt_pct(f.get('NNPA',np.nan))}"
    return f"ROCE {_fmt_pct(f.get('ROCE',np.nan))} | OpMargin {_fmt_pct(f.get('OperatingMargin',np.nan))} | D/E {_fmt_num(f.get('DebtToEquity',np.nan))} | FCF {_format_fund_value(f.get('FCF',np.nan))}"


def print_fundamental_dashboard(results):
    print("\n" + "#" * 132)
    print("STOCKAI V5.5.3 — SECTOR-AWARE FUNDAMENTAL DASHBOARD")
    print("Business-model-specific financial health | sector metrics | growth | profitability | leverage | cash flow")
    print("#" * 132)
    print(f"{'Stock':<12}{'Score':>8}  {'Sector Profile':<18} {'Health':<31} {'RevGrowth':>10} {'ProfitGrowth':>13} {'ROE':>8} {'ROCE':>8}")
    print("-" * 132)
    for r in results:
        f = r.get("Fundamentals", {})
        score = f.get("FundamentalScore", np.nan)
        score_text = "N/A" if pd.isna(score) else f"{score:.0f}/100"
        conf = f.get("FundamentalDataConfidence", "NONE")
        coverage = f.get("FundamentalCoveragePct", np.nan)
        print(f"{r['Stock']:<12}{fundamental_icon(score, f.get('FundamentalHealth','')):>2} {score_text:>6}  {f.get('SectorBucket','DEFAULT'):<24} {f.get('FundamentalHealth','N/A'):<31} {_fmt_pct(f.get('RevenueGrowthPct',np.nan)):>10} {_fmt_pct(f.get('ProfitGrowthPct',np.nan)):>13} {_fmt_pct(f.get('ROE',np.nan)):>8} {_fmt_pct(f.get('ROCE',np.nan)):>8}")
        cov_txt = "N/A" if pd.isna(coverage) else f"{coverage:.0f}%"
        print(f"  Data confidence: {conf:<6} | sector metric coverage: {cov_txt:<4} | {_sector_dashboard_detail(f)}")

    print("\nHOW TO READ V5.5.3")
    print("  • Fundamental Score is a sector-aware health summary, NOT a price target, return probability or recommendation.")
    print("  • Banks emphasize ROE, ROA, NIM, asset quality and capital adequacy when those data are available.")
    print("  • IT emphasizes margins, ROE, growth, cash generation and leverage.")
    print("  • Industrials/Auto/Energy/Ports emphasize ROCE, growth, margins, leverage and free cash flow.")
    print("  • Missing sector metrics are N/A; the score is confidence-adjusted so incomplete sector data cannot look fully supported.")
    print("  • P/E and P/B remain valuation context and are NOT judged in isolation.")
    print("  • Data confidence is based on the weight of available sector metrics; it is not a forecast or probability.")
    print("  • Valuation/quality flags are shown separately from fundamental health.")


def attach_fundamentals(results):
    for r in results:
        r["Fundamentals"] = fetch_fundamentals(r["Stock"] + ".NS")
    return results


# ============================================================
# V5.1 NEWS & EVENTS ENGINE
# Descriptive recent-news context. It does NOT modify technical
# or fundamental scores.
# ============================================================

NEWS_COUNT = 8
NEWS_MAX_AGE_DAYS = 14

# V5.2 news relevance aliases. High relevance requires company-specific
# wording; sector/macro headlines remain context only.
NEWS_COMPANY_ALIASES = {
    "WIPRO": ["wipro"],
    "INFY": ["infosys", "infosys limited", "infy"],
    "TCS": ["tcs", "tata consultancy services"],
    "HDFCBANK": ["hdfc bank", "hdfcbank"],
    "RELIANCE": ["reliance industries", "reliance", "jio"],
    "HFCL": ["hfcl", "hfcl limited"],
    "TMCV": ["tmcv", "tata motors", "tata motors commercial vehicles"],
    "ADANIPORTS": ["adani ports", "adaniports"],
    "QPOWER": ["quality power", "quality power electrical", "qpower"],
}

NEWS_GENERIC_NOISE = [
    "stocks trade", "shares trade", "stocks rise", "stocks fall",
    "shares rise", "shares fall", "adr", "market trading guide",
    "stocks to watch", "stocks in focus", "sensex", "nifty",
    "what investors should know", "why did", "stock price target",
    "may outperform", "recommendation", "buy call", "sell call",
    "top 5", "top 10", "top companies", "stocks:", "shares:",
    "dividend jackpot", "best stocks", "stocks with the most",
    "companies with the most", "stocks to buy", "stocks to sell",
]

def _news_timestamp(item):
    for key in ("providerPublishTime", "pubTime", "publishedTime", "timestamp"):
        val = item.get(key)
        if val is None:
            continue
        try:
            ts = pd.to_datetime(val, unit="s", errors="coerce")
            if pd.notna(ts):
                return ts
        except Exception:
            pass
        try:
            ts = pd.to_datetime(val, errors="coerce")
            if pd.notna(ts):
                return ts
        except Exception:
            pass
    return pd.NaT

def _news_text(item, *keys):
    for key in keys:
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""

def _classify_news(title):
    t = title.lower()
    rules = [
        ("EARNINGS", ["earnings", "profit", "revenue", "results", "eps", "quarter"]),
        ("ORDER / BUSINESS", ["order", "contract", "deal", "project", "wins", "award"]),
        ("CORPORATE ACTION", ["dividend", "bonus", "split", "buyback", "acquisition", "acquire", "acquires", "merger", "stake"]),
        ("MANAGEMENT", ["ceo", "cfo", "director", "resign", "appoint", "management"]),
        ("REGULATION / LEGAL", ["sebi", "regulator", "regulatory", "court", "lawsuit", "penalty", "notice"]),
        ("CAPEX / EXPANSION", ["capex", "expansion", "plant", "facility", "capacity"]),
        ("MACRO / SECTOR", ["sector", "industry", "tariff", "export", "import", "policy", "rate"]),
    ]
    for label, words in rules:
        if any(w in t for w in words):
            return label
    return "GENERAL"

def _classify_sentiment(title):
    t = title.lower()
    positive = ["growth", "profit rises", "profit up", "revenue rises", "revenue up",
                "order win", "new order", "contract win", "expansion", "record",
                "upgrade", "dividend", "buyback", "approval", "launch"]
    negative = ["profit falls", "profit down", "revenue falls", "revenue down",
                "loss", "decline", "downgrade", "penalty", "fraud", "lawsuit",
                "resign", "cut", "warning", "delay", "weak"]
    p = sum(w in t for w in positive)
    n = sum(w in t for w in negative)
    if p and n:
        return "MIXED"
    if p:
        return "POSITIVE"
    if n:
        return "NEGATIVE"
    return "NEUTRAL"

def _news_relevance(stock, title):
    """Classify headline relevance conservatively.

    HIGH is reserved for a genuinely company-specific event. Headlines that
    list several stocks/companies, recommendation lists, market commentary,
    or price-action articles are context and cannot drive the main News View.
    """
    stock = stock.replace(".NS", "").upper()
    t = title.lower()
    aliases = NEWS_COMPANY_ALIASES.get(stock, [stock.lower()])
    company_hits = sum(1 for a in aliases if a in t)
    noise = any(x in t for x in NEWS_GENERIC_NOISE)

    # Detect list-style headlines even when the other company names are not
    # in our tracked universe (e.g. "BEML, IRCTC, HFCL, KPI Green Energy").
    list_markers = [
        "stocks:", "shares:", "stocks to watch", "stocks in focus",
        "stock split", "dividend today", "dividends today",
        "top 5", "top 10", "stocks to buy", "stocks to sell",
    ]
    comma_count = t.count(",")
    multi_company_list = comma_count >= 2 and any(m in t for m in list_markers)

    # Count other tracked companies as an additional multi-company signal.
    other_hits = 0
    for other_stock, other_aliases in NEWS_COMPANY_ALIASES.items():
        if other_stock == stock:
            continue
        if any(a in t for a in other_aliases):
            other_hits += 1

    event_type = _classify_news(title)
    company_event_types = {
        "EARNINGS", "ORDER / BUSINESS", "CORPORATE ACTION",
        "MANAGEMENT", "REGULATION / LEGAL", "CAPEX / EXPANSION"
    }

    # Explicit list/multi-company context is never HIGH.
    if company_hits >= 1 and (other_hits > 0 or multi_company_list or noise):
        return "MEDIUM", 2

    if company_hits >= 1:
        # Company-specific operational/corporate events are HIGH.
        # Pure price-action/general headlines remain MEDIUM.
        if event_type in company_event_types:
            return "HIGH", 3
        return "MEDIUM", 2

    sector_terms = {
        "WIPRO": ["it services", "information technology", "software services", "indian it"],
        "INFY": ["it services", "information technology", "software services", "indian it"],
        "TCS": ["it services", "information technology", "software services", "indian it"],
        "HDFCBANK": ["private banks", "banking", "banks", "financial services"],
        "RELIANCE": ["oil and gas", "telecom", "retail", "energy", "jio"],
        "HFCL": ["telecom", "optical fiber", "fiber optic", "defence", "networking"],
        "TMCV": ["commercial vehicles", "auto", "automobile", "trucks"],
        "ADANIPORTS": ["ports", "logistics", "infrastructure", "shipping"],
        "QPOWER": ["power equipment", "transformer", "grid", "electrical equipment"],
    }.get(stock, [])
    if any(x in t for x in sector_terms):
        return "MEDIUM", 2
    return "LOW", 1


def _news_view_from_items(items):
    """Build a conservative descriptive news view.

    Only HIGH-relevance company-specific headlines can drive the main view.
    MEDIUM/LOW relevance headlines remain context and cannot by themselves
    create a positive/negative company-news label.
    """
    if not items:
        return "NO RECENT NEWS"

    high = [x for x in items if x.get("Relevance") == "HIGH"]
    medium = [x for x in items if x.get("Relevance") == "MEDIUM"]

    # Company-specific headlines have the strongest evidentiary value.
    source_items = high if high else medium
    if not source_items:
        return "LIMITED / LOW RELEVANCE"

    pos = sum(1 for x in source_items if x.get("Sentiment") == "POSITIVE")
    neg = sum(1 for x in source_items if x.get("Sentiment") == "NEGATIVE")
    mix = sum(1 for x in source_items if x.get("Sentiment") == "MIXED")

    # Require a clear balance before calling news positive/negative.
    if pos > 0 and neg > 0:
        return "MIXED"
    if mix > 0 and (pos or neg):
        return "MIXED"
    if pos >= 2 and neg == 0:
        return "POSITIVE"
    if neg >= 2 and pos == 0:
        return "NEGATIVE"
    if pos == 1 and neg == 0 and len(source_items) == 1:
        return "POSITIVE"
    if neg == 1 and pos == 0 and len(source_items) == 1:
        return "NEGATIVE"
    if mix:
        return "MIXED"
    return "NEUTRAL"


def _parse_news_items(raw_items, stock, cutoff):
    """Normalize yfinance/Yahoo-style news dictionaries."""
    items = []
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else item
        title = _news_text(content, "title", "headline") or _news_text(item, "title", "headline")
        if not title:
            continue
        ts = _news_timestamp(content)
        if pd.isna(ts):
            ts = _news_timestamp(item)
        if pd.notna(ts):
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            if ts < cutoff:
                continue
        provider = _news_text(content, "providerDisplayName", "publisher", "provider") or _news_text(item, "publisher", "provider")
        url = ""
        click = content.get("clickThroughUrl") if isinstance(content, dict) else None
        if isinstance(click, dict):
            url = click.get("url") or ""
        if not url:
            url = _news_text(content, "link", "url") or _news_text(item, "link", "url")
        relevance, relevance_score = _news_relevance(stock, title)
        items.append({
            "Title": title,
            "Date": ts,
            "Source": provider or "Yahoo Finance",
            "Type": _classify_news(title),
            "Sentiment": _classify_sentiment(title),
            "Relevance": relevance,
            "RelevanceScore": relevance_score,
            "URL": url,
        })
    return items


def _fetch_google_news_rss(stock):
    """Fallback source using Google News RSS. Returns normalized dictionaries."""
    aliases = NEWS_COMPANY_ALIASES.get(stock, [stock.lower()])
    query = aliases[0]
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": f"{query} India stock",
        "hl": "en-IN", "gl": "IN", "ceid": "IN:en"
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 StockAI/5.2"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    raw = []
    for item in root.findall("./channel/item")[:NEWS_COUNT * 2]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        source = item.findtext("source") or "Google News"
        ts = pd.to_datetime(pub, utc=True, errors="coerce")
        raw.append({"title": title, "link": link, "pubTime": ts, "publisher": source})
    return raw


def _dedupe_news(items):
    seen = set()
    out = []
    for x in sorted(items, key=lambda z: (z["RelevanceScore"], z["Date"] if pd.notna(z["Date"]) else pd.Timestamp.min.tz_localize("UTC")), reverse=True):
        key = " ".join(x.get("Title", "").lower().split())
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def fetch_news(symbol):
    result = {
        "NewsItems": [], "NewsView": "NO RECENT NEWS", "NewsCount": 0,
        "NewsCoverage": "NONE", "NewsRelevance": "NONE", "NewsError": "",
        "NewsSourceMode": "NONE",
    }
    stock = symbol.replace(".NS", "").upper()
    now = pd.Timestamp.now(tz="UTC")
    cutoff = now - pd.Timedelta(days=NEWS_MAX_AGE_DAYS)
    all_items = []
    source_modes = []

    # 1) yfinance first. Different yfinance versions/provider responses can
    # expose either get_news() or ticker.news, so try both independently.
    try:
        ticker = yf.Ticker(symbol)
        raw = []
        try:
            raw = ticker.get_news(count=NEWS_COUNT, tab="news") or []
        except Exception:
            pass
        if raw:
            all_items.extend(_parse_news_items(raw, stock, cutoff))
            source_modes.append("yfinance")
        if len(all_items) < 3:
            try:
                raw2 = ticker.news or []
                if raw2:
                    all_items.extend(_parse_news_items(raw2, stock, cutoff))
                    source_modes.append("yfinance.news")
            except Exception:
                pass
    except Exception as exc:
        result["NewsError"] = f"yfinance: {str(exc)[:100]}"

    # 2) Google News RSS fallback when yfinance gives no/too little data.
    if len(all_items) < 3:
        try:
            rss_raw = _fetch_google_news_rss(stock)
            rss_items = _parse_news_items(rss_raw, stock, cutoff)
            if rss_items:
                all_items.extend(rss_items)
                source_modes.append("Google RSS")
        except Exception as exc:
            if not all_items:
                result["NewsError"] = (result["NewsError"] + "; " if result["NewsError"] else "") + f"RSS: {str(exc)[:100]}"

    items = _dedupe_news(all_items)[:NEWS_COUNT]
    if not items:
        result["NewsSourceMode"] = "FAILED" if result["NewsError"] else "NO DATA"
        return result

    high = sum(x["Relevance"] == "HIGH" for x in items)
    medium = sum(x["Relevance"] == "MEDIUM" for x in items)
    relevance_view = "HIGH" if high >= 2 else "MEDIUM" if (high + medium) >= 2 else "LOW"
    result.update({
        "NewsItems": items,
        "NewsView": _news_view_from_items(items),
        "NewsCount": len(items),
        "NewsCoverage": "GOOD" if len(items) >= 5 else "LIMITED",
        "NewsRelevance": relevance_view,
        "NewsSourceMode": " + ".join(dict.fromkeys(source_modes)),
    })
    return result

def news_icon(view):
    return {
        "POSITIVE": "🟢",
        "MIXED": "🟡",
        "NEUTRAL": "⚪",
        "NEGATIVE": "🔴",
        "NO RECENT NEWS": "⚪",
        "NEWS DATA ERROR": "⚪",
        "LIMITED / LOW RELEVANCE": "⚪",
    }.get(view, "⚪")

def attach_news(results):
    for r in results:
        r["News"] = fetch_news(r["Stock"] + ".NS")
    return results

def print_news_dashboard(results):
    print("\n" + "#" * 118)
    print("STOCKAI V5.5.3 — NEWS & EVENTS DASHBOARD")
    print("Recent company news | event classification | descriptive headline sentiment")
    print("#" * 118)
    print("News sentiment is headline-based context only; it does NOT change technical or fundamental scores.")
    print("-" * 118)

    for r in results:
        n = r.get("News", {})
        view = n.get("NewsView", "NO RECENT NEWS")
        count = n.get("NewsCount", 0)
        coverage = n.get("NewsCoverage", "NONE")
        print(f"\n{r['Stock']:<12}{news_icon(view)} {view:<18} | Items: {count:<2} | Coverage: {coverage:<7} | Relevance: {n.get('NewsRelevance','NONE')}")
        if n.get("NewsError"):
            print(f"  Error: {n['NewsError']}")
            continue
        for item in n.get("NewsItems", [])[:5]:
            dt = item.get("Date")
            date_text = dt.strftime("%Y-%m-%d") if pd.notna(dt) else "N/A"
            print(f"  {date_text} | {item.get('Relevance','N/A'):<6} | {item['Sentiment']:<8} | {item['Type']:<20} | {item['Title'][:100]}")
        if not n.get("NewsItems"):
            print("  No recent news returned by the data source.")

    print("\nHOW TO READ V5.5.3")
    print("  • NewsView is descriptive headline context, not a trading signal.")
    print("  • Event type is keyword-based and may be imperfect.")
    print("  • Sentiment is a simple headline classifier, not analyst research.")
    print("  • Recent-news coverage can be incomplete; absence of news is not evidence of no event.")
    print("  • News does not modify Technical Risk, Fundamental Score, Entry, Stop or Targets.")
    print("  • yfinance exposes recent ticker news through get_news()/news; returned fields can vary by provider/version.")
    print("  • Positive/negative News View requires clear company-specific headlines; multi-company/sector headlines are context only.")
    print("  • LIMITED / LOW RELEVANCE means headlines exist but are not strong enough to characterize company-specific news.")

def attach_fundamentals(results):
    for r in results:
        r["Fundamentals"] = fetch_fundamentals(r["Stock"] + ".NS")
    return results


# ============================================================
# V5.2 CONSOLIDATED ANALYSIS LAYER
# Combines existing technical + fundamental + news + market context.
# It intentionally does NOT create an overall score, ranking, probability,
# or price forecast.
# ============================================================

def _safe_text(v, default="N/A"):
    if v is None:
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    return str(v)


def _fund_note_lines(f):
    notes = []
    rg = f.get("RevenueGrowthPct", np.nan)
    pg = f.get("ProfitGrowthPct", np.nan)
    roe = f.get("ROE", np.nan)
    roce = f.get("ROCE", np.nan)
    de = f.get("DebtToEquity", np.nan)
    fcf = f.get("FCF", np.nan)
    pe = f.get("PE", np.nan)
    pb = f.get("PB", np.nan)
    bucket = f.get("SectorBucket", "DEFAULT")

    for x in f.get("SectorNotes", []): notes.append(x)
    # Keep valuation/data-quality context separate from operating health.
    for x in _fundamental_quality_flags(f): notes.append(f"Fundamental flag: {x}")
    for x in f.get("SectorRisks", []):
        # FCF negativity is already represented by the explicit valuation/quality
        # flag. Do not print the same issue again with different wording.
        if x == "Negative free cash flow" and any("FCF is negative" in n for n in notes):
            continue
        notes.append(x)
    if pd.notna(rg) and rg > 10: notes.append("Revenue growth is strong")
    elif pd.notna(rg) and rg < 0: notes.append("Revenue growth is negative")
    if pd.notna(pg) and pg > 10: notes.append("Profit growth is strong")
    elif pd.notna(pg) and pg < 0: notes.append("Profit growth is negative")
    if pd.notna(roe) and roe >= 15: notes.append("ROE is healthy")
    if pd.notna(roce) and roce >= 15: notes.append("ROCE is healthy")
    if pd.notna(de) and de > 100: notes.append("Leverage is elevated")

    # Add banking metrics explicitly when present.
    if bucket == "BANKS":
        nim, gnpa, nnpa, car, roa = [f.get(k, np.nan) for k in ["NIM","GNPA","NNPA","CapitalAdequacy","ROA"]]
        if pd.notna(nim): notes.append(f"NIM is {nim:.1f}%")
        if pd.notna(gnpa): notes.append(f"GNPA is {gnpa:.1f}%")
        if pd.notna(nnpa): notes.append(f"NNPA is {nnpa:.1f}%")
        if pd.notna(car): notes.append(f"Capital adequacy is {car:.1f}%")
        if pd.notna(roa): notes.append(f"ROA is {roa:.1f}%")
    return list(dict.fromkeys(notes))[:8]


def _technical_state(r):
    action = r.get("Action", "")
    trend = r.get("Trend", "")
    if action.startswith("CONFIRMED BREAKOUT"):
        return "CONFIRMED BREAKOUT"
    if action == "BREAKOUT RETEST":
        return "BREAKOUT RETEST"
    if "WAIT — RESISTANCE" in action:
        return "BULLISH STRUCTURE / RESISTANCE NEAR"
    if "WATCH — RECOVERY" in action:
        return "RECOVERY / MIXED"
    if "AVOID — BREAKDOWN" in action:
        return "BREAKDOWN / BEARISH"
    if "AVOID — BEARISH" in action:
        return "BEARISH STRUCTURE"
    return action.replace("WATCH — ", "WATCH — ").replace("WAIT — ", "WAIT — ") or trend


def build_v52_analysis(r, market_regime="MARKET CONTEXT UNAVAILABLE"):
    f = r.get("Fundamentals", {})
    n = r.get("News", {})
    tech = _technical_state(r)
    positives, risks, watch = [], [], []

    # Technical facts
    if r.get("Breakout") or r.get("Retest"):
        positives.append("Historical breakout structure is confirmed/retesting")
    elif "UPTREND" in r.get("Trend", "") and r.get("ST_Direction") == "BULLISH":
        positives.append("Trend and SuperTrend are bullish")
    if r.get("VolumeRatio", 0) >= VOLUME_THRESHOLD:
        positives.append(f"Volume is strong at {r['VolumeRatio']:.2f}x average")
    if r.get("MACD_Bull"):
        positives.append("MACD is bullish")
    if r.get("TechnicalRisk", 0) >= 60:
        risks.append(f"Technical risk score is elevated ({r['TechnicalRisk']}/100)")
    if "DOWNTREND" in r.get("Trend", ""):
        risks.append("Price remains in a broader downtrend")
    if not r.get("MACD_Bull"):
        risks.append("MACD is bearish")
    if r.get("VolumeRatio", 0) < VOLUME_NEUTRAL:
        risks.append("Volume is below normal")
    if pd.notna(r.get("NearestResistance")) and r.get("ResistanceDistancePct", 99) <= 2.5:
        watch.append(f"Nearest resistance {money(r['NearestResistance'])} is close")
    if pd.notna(r.get("NearestSupport")) and r.get("SupportDistancePct", 99) <= 3:
        watch.append(f"Support {money(r['NearestSupport'])} is close")
    watch.append(f"Setup trigger: {money(r.get('TriggerPrice'))}")

    # Fundamentals: sector-aware descriptive facts.
    for line in _fund_note_lines(f):
        low = line.lower()
        if any(k in low for k in ["negative", "below", "elevated"]):
            risks.append(line)
        elif any(k in low for k in ["strong", "healthy", "controlled", "positive"]):
            positives.append(line)
        else:
            watch.append(line)

    # News is contextual and independent of technical/fundamental scores.
    nv = n.get("NewsView", "NO RECENT NEWS")
    nr = n.get("NewsRelevance", "NONE")
    if nv == "POSITIVE": positives.append(f"Recent company-specific news view is positive ({nr.lower()} relevance)")
    elif nv == "NEGATIVE": risks.append(f"Recent company-specific news view is negative ({nr.lower()} relevance)")
    elif nv == "MIXED":
        watch.append(f"Recent company-specific news is mixed ({nr.lower()} relevance)")
    elif nv == "LIMITED / LOW RELEVANCE":
        watch.append("Recent headlines are low-relevance market/commentary context")
    if nv == "NO RECENT NEWS": watch.append("No recent news was returned; absence of news is not evidence of no event")

    # Market context and contradictions.
    if "BEARISH" in market_regime and ("UPTREND" in r.get("Trend", "") or r.get("ST_Direction") == "BULLISH"):
        risks.append("Bullish stock structure is occurring inside a bearish market regime")
    if "BULLISH" in market_regime and "DOWNTREND" in r.get("Trend", ""):
        risks.append("Stock trend is weaker than the broader market regime")

    # Deduplicate while preserving order, including known semantic duplicates.
    def _dedupe_semantic(lines):
        out = []
        seen = set()
        for line in lines:
            normalized = line.lower().strip()
            if "negative free cash flow" in normalized:
                key = "fcf_negative"
            elif "fcf is negative" in normalized:
                key = "fcf_negative"
            elif "roce below sector threshold" in normalized:
                key = "roce_below_sector"
            elif "roce is below the sector threshold" in normalized:
                key = "roce_below_sector"
            else:
                key = normalized
            if key in seen:
                continue
            seen.add(key)
            out.append(line)
        return out

    positives = _dedupe_semantic(positives)[:4]
    risks = _dedupe_semantic(risks)[:5]
    watch = _dedupe_semantic(watch)[:4]

    if not positives: positives = ["No major positive confirmation identified by the current rules"]
    if not risks: risks = ["No major rule-based contradiction identified"]

    return {
        "TechnicalState": tech,
        "FundamentalHealth": f.get("FundamentalHealth", "N/A"),
        "FundamentalScore": f.get("FundamentalScore", np.nan),
        "NewsView": nv,
        "NewsRelevance": nr,
        "MarketRegime": market_regime,
        "Positives": positives,
        "Risks": risks,
        "Watch": watch,
    }


def print_v52_quick_map(results):
    print("\n" + "#" * 150)
    print("STOCKAI V5.5.3 — QUICK ANALYSIS MAP")
    print("What is happening now?  Market + Technical + Fundamental + News context")
    print("No overall score, ranking, return probability, or price forecast is created.")
    print("#" * 150)
    print(f"{'Stock':<12}{'Price':>12}  {'Market':<22} {'Technical':<30} {'Fundamental':<27} {'News':<18} {'Setup':<28}")
    print("-" * 150)
    for r in results:
        a = r.get("V52", {})
        score = a.get("FundamentalScore", np.nan)
        fs = "N/A" if pd.isna(score) else f"{score:.0f}/100"
        fund = f"{fundamental_icon(score, a.get('FundamentalHealth',''))} {fs}"
        news = f"{news_icon(a.get('NewsView','NO RECENT NEWS'))} {a.get('NewsView','N/A')}"
        print(f"{r['Stock']:<12}{money(r['Price']):>12}  {a.get('MarketRegime','N/A')[:22]:<22} {a.get('TechnicalState','N/A')[:30]:<30} {fund:<27} {news:<18} {r.get('SetupState','N/A')[:28]:<28}")


def print_v52_cards(results):
    print("\n" + "#" * 150)
    print("STOCKAI V5.5.3 — CONSOLIDATED STOCK CARDS")
    print("#" * 150)
    for r in results:
        a = r.get("V52", {})
        f = r.get("Fundamentals", {})
        n = r.get("News", {})
        print(f"\n{r['Stock']} — {money(r['Price'])}")
        print(f"  Market Context : {a.get('MarketRegime','N/A')}")
        print(f"  Technical State: {a.get('TechnicalState','N/A')} | Action: {r.get('Action','N/A')} | Technical Risk Flags: {r.get('TechnicalRisk','N/A')}/100")
        fs = a.get('FundamentalScore', np.nan)
        fs_text = "N/A" if pd.isna(fs) else f"{fs:.0f}/100"
        print(f"  Fundamental    : {fundamental_icon(fs, a.get('FundamentalHealth',''))} {fs_text} | {a.get('FundamentalHealth','N/A')} | data points: {f.get('FundamentalDataPoints','N/A')}")
        print(f"  News View      : {news_icon(a.get('NewsView','NO RECENT NEWS'))} {a.get('NewsView','N/A')} | relevance: {a.get('NewsRelevance','N/A')} | items: {n.get('NewsCount',0)}")
        print(f"  Setup          : {r.get('SetupState','N/A')} | Trigger {money(r.get('TriggerPrice'))} | Stop {money(r.get('TradeStopPrice'))} | T1 mechanical {money(r.get('Target1'))} | T2 mechanical {money(r.get('Target2'))}")
        print("  Key Positives:")
        for x in a.get("Positives", []): print(f"    + {x}")
        print("  Key Risks:")
        for x in a.get("Risks", []): print(f"    ! {x}")
        print("  What To Watch:")
        for x in a.get("Watch", []): print(f"    > {x}")
        relevant_news = sorted(n.get("NewsItems", []), key=lambda x: x.get("RelevanceScore", 0), reverse=True)[:2]
        if relevant_news:
            print("  Relevant headlines:")
            for item in relevant_news:
                dt = item.get("Date")
                d = dt.strftime("%Y-%m-%d") if pd.notna(dt) else "N/A"
                print(f"    {d} | {item.get('Relevance','N/A'):<6} | {item.get('Type','GENERAL'):<20} | {item.get('Title','')[:100]}")



def _v56_label_icon(label):
    icons = {
        "STRONG": "🟢", "CONSTRUCTIVE": "🟢", "CONSTRUCTIVE — CONFIRMATION PENDING": "🟢",
        "EARLY RECOVERY INSIDE DOWNTREND": "🟡", "MIXED / RECOVERY": "🟡",
        "MIXED / BEARISH": "🟠", "BEARISH": "🔴", "STRONG BEARISH": "🔴",
        "REASONABLE": "🟢", "ELEVATED": "🟡", "WATCH": "🟡",
        "EXPENSIVE": "🟠", "VERY EXPENSIVE": "🔴",
        "SUPPORT": "🟢", "RESISTANCE": "🔴", "NEUTRAL": "⚪",
        "COMPANY POSITIVE": "🟢", "COMPANY NEGATIVE": "🔴", "MIXED": "🟡",
        "CONTEXT ONLY": "⚪", "NO RECENT NEWS": "⚪", "UNAVAILABLE": "⚪",
        "LIMITED": "⚪", "WEAK": "🔴",
    }
    return icons.get(label, "🟡")


def _v56_valuation_view(f):
    notes = [str(x) for x in f.get("ValuationNotes", [])]
    text = " | ".join(notes).lower()

    very_high_pb = "p/b is very high" in text
    high_pe = "p/e is high" in text
    elevated_pe = "p/e is elevated" in text
    elevated_pb = "p/b is elevated" in text
    negative_fcf = "fcf is negative" in text

    if very_high_pb and high_pe:
        return "VERY EXPENSIVE"
    if high_pe or very_high_pb:
        return "EXPENSIVE"
    if elevated_pe or elevated_pb:
        return "ELEVATED"
    if negative_fcf or notes:
        return "WATCH"
    return "REASONABLE"


def _v56_technical_view(r):
    signal = str(r.get("Signal", ""))
    trend = str(r.get("Trend", ""))
    risk = r.get("TechnicalRisk", 50)
    adx = r.get("ADX", np.nan)
    macd_bull = bool(r.get("MACDBullish", False))
    st_bull = bool(r.get("SuperTrendBullish", False))
    plus_di = r.get("PlusDI", np.nan)
    minus_di = r.get("MinusDI", np.nan)

    # Important UX rule: do not call a stock "STRONG" merely because the
    # signal says STRONG BULLISH when trend-strength confirmation is still low.
    if "STRONG BULLISH" in signal and risk <= 35:
        if pd.notna(adx) and adx < 25:
            return "CONSTRUCTIVE — CONFIRMATION PENDING"
        return "STRONG"

    if signal == "RECOVERY / MIXED":
        if "DOWNTREND" in trend:
            return "EARLY RECOVERY INSIDE DOWNTREND"
        return "MIXED / RECOVERY"

    # Mixed evidence should remain visibly mixed rather than being collapsed
    # into a simple bearish label.
    if "DOWNTREND" in trend and (macd_bull or st_bull):
        return "MIXED / BEARISH"

    if signal in ["BULLISH", "RECOVERY / MIXED"] and risk <= 45:
        return "CONSTRUCTIVE"

    if "STRONG BEARISH" in signal or "STRONG DOWNTREND" in trend:
        return "STRONG BEARISH"
    if "BEARISH" in signal or "DOWNTREND" in trend:
        return "BEARISH"
    return "WATCH"


def _v56_fundamental_view(f):
    score = f.get("FundamentalScore", np.nan)
    health = str(f.get("FundamentalHealth", ""))
    if pd.isna(score):
        return "UNAVAILABLE"
    if "INSUFFICIENT" in health or f.get("FundamentalDataConfidence") == "LOW":
        return "WATCH" if score >= 55 else "LIMITED"
    if score >= 75:
        return "STRONG"
    if score >= 55:
        return "CONSTRUCTIVE"
    return "WEAK"


def _v56_news_view(n):
    """Convert the V5.5.3 news layer into beginner-friendly decision labels.

    Recommendation lists, multi-company lists, market commentary and pure
    price-action headlines are context only. They should never appear as
    COMPANY POSITIVE/NEGATIVE in Decision Intelligence.
    """
    raw = str(n.get("NewsView", "NO RECENT NEWS"))
    items = n.get("NewsItems", []) or []
    high_items = [x for x in items if x.get("Relevance") == "HIGH"]

    if raw == "NO RECENT NEWS" or not items:
        return "NO RECENT NEWS"

    if high_items:
        if raw == "POSITIVE":
            return "COMPANY POSITIVE"
        if raw == "NEGATIVE":
            return "COMPANY NEGATIVE"
        if raw == "MIXED":
            return "MIXED"

    # If there are no high-relevance company-specific events, the headline
    # set is useful only as background context.
    return "CONTEXT ONLY"


def _v56_sr_view(r):
    resistance = r.get("ResistanceDistancePct", np.nan)
    support = r.get("SupportDistancePct", np.nan)
    if pd.notna(resistance) and resistance <= 2.5:
        return "RESISTANCE"
    if pd.notna(support) and support <= 3.0:
        return "SUPPORT"
    return "NEUTRAL"


def _v56_final_view(r, market_context, technical, fundamental, valuation, news, sr):
    setup = str(r.get("SetupState", ""))
    action = str(r.get("Action", ""))

    if "NO NEW ENTRY — BEARISH" in setup or "AVOID — BEARISH" in action or "AVOID — BREAKDOWN" in action:
        return "AVOID — BEARISH"
    if "WAIT — RESISTANCE" in setup:
        return "WAIT — DO NOT CHASE"
    if "WATCH — RECOVERY" in setup:
        return "WATCH — CONFIRM RECOVERY"
    if "SUPPORT RISK" in setup:
        return "WATCH — SUPPORT RISK"
    if "WATCH — MIXED" in setup:
        return "WATCH — CONFIRMATION"
    if "BREAKOUT RETEST" in setup:
        return "WATCH — BREAKOUT RETEST"
    if "BREAKOUT CONFIRMED" in setup:
        return "BULLISH — MANAGE RISK"
    if "WAIT — BREAKOUT" in setup:
        return "WAIT — BREAKOUT CONFIRMATION"
    return "WATCH — CONFIRMATION"


def _v56_plan(r, final_view):
    r1 = money(r.get("NearestResistance"))
    breakout = money(r.get("BreakoutConfirmationPrice"))
    support = money(r.get("NearestSupport"))
    stop = money(r.get("TradeStopPrice"))
    if final_view == "AVOID — BEARISH":
        return [f"Wait for trend improvement; monitor R1 {r1}", f"Reconsider only after stronger confirmation above {breakout}"]
    if final_view == "WAIT — DO NOT CHASE":
        return [f"Clear nearest resistance {r1}", f"Then watch historical breakout confirmation {breakout}", f"Mechanical stop reference {stop} — scanner level, NOT a forecast"]
    if final_view == "WATCH — CONFIRM RECOVERY":
        return [f"Hold off on confirmation; watch R1 {r1}", f"Look for sustained strength above {breakout}"]
    if final_view == "WATCH — SUPPORT RISK":
        return [f"Monitor support {support} closely", f"Avoid assuming support will hold without confirmation"]
    if final_view == "WATCH — CONFIRMATION":
        return [f"Watch R1 {r1}", f"Require confirmation above {breakout}"]
    if final_view == "WATCH — BREAKOUT RETEST":
        return [f"Monitor retest of the broken level {r1}", f"Protect downside using the mechanical stop reference {stop}"]
    if final_view == "BULLISH — MANAGE RISK":
        return [f"Manage the position around the mechanical stop reference {stop}", "Mechanical T1/T2/T3 are scanner levels, not price forecasts"]
    return [f"Watch resistance {r1} and breakout confirmation {breakout}"]


def _v56_reasons(r, technical, fundamental, valuation, news, market_context, sr):
    positives, risks = [], []
    f = r.get("Fundamentals", {})
    if technical in ["STRONG", "CONSTRUCTIVE", "CONSTRUCTIVE — CONFIRMATION PENDING"]:
        positives.append("Technical structure is constructive")
    elif technical == "EARLY RECOVERY INSIDE DOWNTREND":
        positives.append("Early recovery signals are visible, but the broader trend is still down")
    elif technical == "MIXED / RECOVERY":
        positives.append("Recovery signals are emerging but not fully confirmed")
    elif technical == "MIXED / BEARISH":
        risks.append("Technical evidence is mixed with the broader structure still bearish")
    elif technical in ["BEARISH", "STRONG BEARISH"]:
        risks.append("Technical trend is bearish")
    if fundamental == "STRONG":
        positives.append(f"Fundamental health is strong ({f.get('FundamentalScore', 0):.0f}/100)")
    elif fundamental == "CONSTRUCTIVE":
        positives.append(f"Fundamental health is constructive ({f.get('FundamentalScore', 0):.0f}/100)")
    elif fundamental in ["WEAK", "LIMITED"]:
        risks.append("Fundamental support is weak or data-limited")
    if valuation == "VERY EXPENSIVE":
        risks.append("Valuation/quality flags indicate very expensive pricing")
    elif valuation == "EXPENSIVE":
        risks.append("Valuation/quality flags indicate expensive pricing")
    elif valuation in ["ELEVATED", "WATCH"]:
        risks.append("Valuation/quality flags need attention")
    if news == "COMPANY POSITIVE":
        positives.append("Recent high-relevance company-specific news is positive")
    elif news == "COMPANY NEGATIVE":
        risks.append("Recent high-relevance company-specific news is negative")
    elif news == "MIXED":
        risks.append("Recent high-relevance company-specific news is mixed")
    if "MARKET WEAK" in market_context:
        risks.append("Broader market is weak")
    elif "MARKET + STOCK BOTH CONSTRUCTIVE" in market_context:
        positives.append("Broader market is also constructive")
    if sr == "RESISTANCE":
        risks.append(f"Resistance is close at {money(r.get('NearestResistance'))}")
    elif sr == "SUPPORT":
        positives.append(f"Price is near support at {money(r.get('NearestSupport'))}")
    return positives[:3], risks[:4]


def build_v56_decision(r):
    a = r.get("V52", {})
    f = r.get("Fundamentals", {})
    n = r.get("News", {})
    market_context = r.get("MarketStockContext", "MIXED MARKET / STOCK CONTEXT")
    technical = _v56_technical_view(r)
    fundamental = _v56_fundamental_view(f)
    valuation = _v56_valuation_view(f)
    news = _v56_news_view(n)
    sr = _v56_sr_view(r)
    final_view = _v56_final_view(r, market_context, technical, fundamental, valuation, news, sr)
    positives, risks = _v56_reasons(r, technical, fundamental, valuation, news, market_context, sr)
    return {
        "Technical": technical,
        "Fundamental": fundamental,
        "Valuation": valuation,
        "News": news,
        "Market": market_context,
        "SR": sr,
        "Setup": r.get("SetupState", "N/A"),
        "FinalView": final_view,
        "Positives": positives,
        "Risks": risks,
        "Plan": _v56_plan(r, final_view),
    }


def print_v56_decision_intelligence(results):
    print("\n" + "#" * 118)
    print("STOCKAI V5.6.2 — DECISION INTELLIGENCE")
    print("Beginner-friendly synthesis of Market + Technical + Fundamental + Valuation + News + S/R + Setup")
    print("No hidden overall score, ranking, return probability, or price forecast is created.")
    print("#" * 118)
    for r in results:
        d = build_v56_decision(r)
        r["V56"] = d
        print("\n" + "═" * 72)
        print(f"{r['Stock']} — {money(r['Price'])}")
        print("═" * 72)
        print(f"  Technical       {_v56_label_icon(d['Technical'])} {d['Technical']}")
        print(f"  Fundamental     {_v56_label_icon(d['Fundamental'])} {d['Fundamental']}" + (f" {r.get('Fundamentals', {}).get('FundamentalScore'):.0f}/100" if pd.notna(r.get('Fundamentals', {}).get('FundamentalScore', np.nan)) else ""))
        print(f"  Valuation       {_v56_label_icon(d['Valuation'])} {d['Valuation']}")
        print(f"  News            {_v56_label_icon(d['News'])} {d['News']}")
        print(f"  Market          {_v56_label_icon('BEARISH' if 'WEAK' in d['Market'] else 'CONSTRUCTIVE')} {d['Market']}")
        print(f"  S/R             {_v56_label_icon(d['SR'])} {d['SR']}")
        print(f"  Setup           🟡 {d['Setup']}")
        print("\n  FINAL VIEW")
        print(f"  {_v56_label_icon('BEARISH' if 'AVOID' in d['FinalView'] else 'WATCH')} {d['FinalView']}")
        print("\n  WHY?")
        for x in d["Positives"]: print(f"  ✓ {x}")
        for x in d["Risks"]: print(f"  ✗ {x}")
        print("\n  PLAN")
        for i, x in enumerate(d["Plan"], 1): print(f"  {i}. {x}")

    print("\nV5.6.2 LABEL GUIDE")
    print("  🟢 STRONG / CONSTRUCTIVE = bullish structure; confirmation strength still matters")
    print("  🟡 EARLY RECOVERY INSIDE DOWNTREND = recovery signals inside a larger bearish trend")
    print("  🟠 MIXED / BEARISH = conflicting signals with bearish structure still dominant")
    print("  🟢 COMPANY POSITIVE / 🔴 COMPANY NEGATIVE = high-relevance company-specific news only")
    print("  ⚪ CONTEXT ONLY = recommendation/list/sector/price-action headlines; not company sentiment")
    print("  Mechanical T1/T2/T3 = scanner calculations, NOT price targets or forecasts")

    print("\nV5.6.2 RULES")
    print("  • Final View is a rule-based synthesis, not a prediction or guaranteed recommendation.")
    print("  • Technical, Fundamental, Valuation, News, Market and S/R remain separate signals; contradictions are preserved.")
    print("  • WAIT — DO NOT CHASE means the setup may be constructive but nearby resistance has not been cleared.")
    print("  • Valuation labels are separate from fundamental health: ELEVATED/EXPENSIVE/VERY EXPENSIVE describe pricing flags, not business quality.")
    print("  • AVOID — BEARISH means the current technical setup is bearish; it does not mean the company is fundamentally bad.")
    print("  • Mechanical Stop/T1/T2/T3 remain scanner levels, not price forecasts.")


# ============================================================
# STOCKAI V6 — ACTION ENGINE + OPTIONAL PORTFOLIO INTELLIGENCE
# V4.7/V5.6.2 calculations are intentionally NOT changed.
# V6 adds a transparent rule-based action layer only.
# ============================================================
PORTFOLIO_FILE = "portfolio.csv"  # Optional. Leave absent to skip portfolio analysis.


def _v6_action_icon(action):
    a = str(action).upper()
    if "BUY" in a:
        return "🟢"
    if "WATCH" in a or "WAIT" in a:
        return "🟡"
    if "REDUCE" in a or "EXIT" in a:
        return "🔴"
    if "AVOID" in a:
        return "🔴"
    return "⚪"


def _v6_action_reason(r, action):
    d = r.get("V56", {})
    reasons = []
    technical = d.get("Technical", "")
    fundamental = d.get("Fundamental", "")
    valuation = d.get("Valuation", "")
    news = d.get("News", "")
    sr = d.get("SR", "")
    setup = str(r.get("SetupState", ""))

    if "BUY ON BREAKOUT" in action:
        reasons.append("Technical and fundamental structure support the setup, but nearby resistance must be cleared first")
    elif action == "BUY":
        reasons.append("Technical structure and fundamental health are aligned without an immediate resistance barrier")
    elif "WATCH / RECOVERY" in action:
        reasons.append("Recovery signals are visible, but the broader trend is not fully confirmed")
    elif "WAIT — DO NOT CHASE" in action:
        reasons.append("The structure is constructive, but entry is too close to resistance for a fresh chase")
    elif "WATCH — CONFIRMATION" in action:
        reasons.append("Some positives exist, but trend/confirmation is not strong enough for a fresh entry")
    elif "AVOID" in action:
        reasons.append("Current technical structure is bearish; a better setup should be allowed to develop")

    if fundamental in ["STRONG", "CONSTRUCTIVE"]:
        reasons.append(f"Fundamentals are {fundamental.lower()}")
    if valuation in ["EXPENSIVE", "VERY EXPENSIVE"]:
        reasons.append(f"Valuation is {valuation.lower()}, so price discipline is important")
    if news == "COMPANY NEGATIVE":
        reasons.append("High-relevance company-specific news is negative")
    if sr == "RESISTANCE" and "resistance" not in " ".join(reasons).lower():
        reasons.append(f"Nearest resistance is {money(r.get('NearestResistance'))}")
    if "BEARISH" in technical and action != "AVOID — BEARISH":
        reasons.append("Broader technical trend remains bearish")
    return reasons[:3]


def _v61_risk_level(r):
    risk = r.get("TradeRiskPct", np.nan)
    flags = r.get("TechnicalRisk", np.nan)
    if pd.isna(risk): return "N/A"
    if risk <= 3 and (pd.isna(flags) or flags < 35): return "LOW"
    if risk <= 5 and (pd.isna(flags) or flags < 60): return "MODERATE"
    if risk <= 8 and (pd.isna(flags) or flags < 80): return "HIGH"
    return "VERY HIGH"

def _v61_entry_status(r, action):
    trigger = r.get("BreakoutConfirmationPrice", r.get("BreakoutEntry", np.nan))
    if "BUY ON BREAKOUT" in action: return f"WAIT BELOW RESISTANCE — breakout entry {money(trigger)}"
    if action == "BUY": return "ENTRY CONDITIONS ACCEPTABLE"
    if "RECOVERY" in action: return "WAIT FOR TREND CONFIRMATION"
    if "AVOID" in action: return "NO NEW ENTRY"
    if "DO NOT CHASE" in action: return "WAIT — ENTRY TOO CLOSE TO RESISTANCE"
    return "WAIT FOR CONFIRMATION"

def _v61_why_not_now(r, action):
    d = r.get("V56", {})
    valuation = d.get("Valuation", "")
    if "BUY ON BREAKOUT" in action: return "Price is near resistance; wait for the stated breakout confirmation before entering."
    if action == "BUY": return "No immediate structural blocker is identified by the current rule set."
    if "RECOVERY" in action: return "Broader trend is not fully confirmed yet."
    if "AVOID" in action: return "Current technical structure is bearish; fundamentals alone do not override it."
    if "DO NOT CHASE" in action and valuation in ["EXPENSIVE", "VERY EXPENSIVE"]: return "Entry is close to resistance and/or valuation is demanding."
    if "DO NOT CHASE" in action: return "Entry is too close to resistance for a fresh chase."
    return "Mixed evidence requires stronger confirmation."

def _v61_beginner_decision(action):
    if action == "BUY": return "BUY — FOLLOW THE PLAN"
    if "BUY ON BREAKOUT" in action: return "BUY ONLY AFTER BREAKOUT"
    if "RECOVERY" in action: return "WAIT — CONFIRM RECOVERY"
    if "AVOID" in action: return "AVOID FOR NOW"
    if "DO NOT CHASE" in action: return "WAIT — DO NOT CHASE"
    return "WAIT FOR CONFIRMATION"


def build_v6_action(r):
    """Transparent action engine. No aggregate score and no price prediction."""
    d = r.get("V56") or build_v56_decision(r)
    technical = d.get("Technical", "")
    fundamental = d.get("Fundamental", "")
    valuation = d.get("Valuation", "")
    news = d.get("News", "")
    sr = d.get("SR", "")
    setup = str(d.get("Setup", r.get("SetupState", "")))
    resistance_dist = r.get("ResistanceDistancePct", np.nan)
    risk_flags = r.get("TechnicalRisk", np.nan)
    market = d.get("Market", "")

    strong_tech = technical in ["STRONG", "CONSTRUCTIVE", "CONSTRUCTIVE — CONFIRMATION PENDING"]
    recovery_tech = technical in ["EARLY RECOVERY INSIDE DOWNTREND", "MIXED / RECOVERY"]
    weak_tech = technical in ["BEARISH", "STRONG BEARISH", "MIXED / BEARISH"]
    good_fund = fundamental in ["STRONG", "CONSTRUCTIVE"]
    valuation_ok = valuation in ["REASONABLE", "WATCH"]
    expensive = valuation in ["EXPENSIVE", "VERY EXPENSIVE"]
    negative_news = news == "COMPANY NEGATIVE"
    market_weak = "BOTH WEAK" in market
    resistance_close = pd.notna(resistance_dist) and resistance_dist <= 2.5
    breakout_confirmed = bool(r.get("Breakout", False)) and not bool(r.get("Breakdown", False))

    # Priority order deliberately avoids turning strong fundamentals into an automatic BUY.
    if negative_news or weak_tech:
        action = "AVOID — BEARISH"
    elif strong_tech and good_fund and breakout_confirmed and not negative_news and valuation_ok:
        action = "BUY"
    elif strong_tech and good_fund and (resistance_close or sr == "RESISTANCE") and not negative_news:
        action = "BUY ON BREAKOUT"
    elif strong_tech and good_fund and expensive and (resistance_close or sr == "RESISTANCE"):
        action = "WAIT — DO NOT CHASE"
    elif recovery_tech or "RECOVERY" in setup:
        action = "WATCH / RECOVERY"
    elif good_fund and strong_tech and not market_weak and not resistance_close and valuation_ok:
        action = "BUY"
    elif "SUPPORT" in setup and not weak_tech:
        action = "WATCH — CONFIRMATION"
    else:
        action = "WATCH — CONFIRMATION"

    if pd.notna(risk_flags) and risk_flags >= 70 and action in ["BUY", "BUY ON BREAKOUT"]:
        action = "WATCH — CONFIRMATION"

    plan = {
        "CurrentPrice": r.get("Price"),
        "EntryZone": r.get("Entry"),
        "BreakoutTrigger": r.get("BreakoutConfirmationPrice", r.get("BreakoutEntry")),
        "Stop": r.get("TradeStopPrice", r.get("StopLoss")),
        "T1": r.get("Target1"),
        "T2": r.get("Target2"),
        "RiskPct": r.get("TradeRiskPct", np.nan),
        "Invalidation": r.get("SetupInvalidationPrice"),
        "NearestResistance": r.get("NearestResistance", np.nan),
    }
    return {
        "Action": action,
        "Technical": technical or "N/A",
        "Fundamental": fundamental or "N/A",
        "Valuation": valuation or "N/A",
        "News": news or "N/A",
        "Market": market or "N/A",
        "SR": sr or "N/A",
        "Setup": setup or "N/A",
        "Reasons": _v6_action_reason(r, action),
        "Plan": plan,
        "DoNotChase": action in ["WAIT — DO NOT CHASE", "BUY ON BREAKOUT"],
        "RiskLevel": _v61_risk_level(r),
        "EntryStatus": _v61_entry_status(r, action),
        "WhyNotNow": _v61_why_not_now(r, action),
        "BeginnerDecision": _v61_beginner_decision(action),
    }


def _v6_plan_text(v6):
    p = v6.get("Plan", {})
    def val(x): return money(x) if pd.notna(x) else "N/A"
    risk = p.get("RiskPct", np.nan)
    risk_text = f"{risk:.2f}%" if pd.notna(risk) else "N/A"
    action = v6.get("Action", "")
    if "BUY ON BREAKOUT" in action:
        lines = [f"Current price {val(p.get('CurrentPrice'))} | Status WAIT BELOW RESISTANCE",
                 f"Nearest resistance {val(p.get('NearestResistance'))} | Breakout entry {val(p.get('BreakoutTrigger'))}"]
    else:
        lines = [f"Current price {val(p.get('CurrentPrice'))} | Entry reference {val(p.get('EntryZone'))}"]
    lines += [f"Mechanical stop {val(p.get('Stop'))} | Mechanical T1 {val(p.get('T1'))} | Mechanical T2 {val(p.get('T2'))}",
              f"Mechanical stop risk {risk_text} | Risk level {v6.get('RiskLevel','N/A')}",
              f"Setup invalidation {val(p.get('Invalidation'))}"]
    return lines


def print_v6_action_engine(results):
    print("\n" + "#" * 124)
    print("STOCKAI V6.1 — ACTION ENGINE")
    print("BUY + BUY ON BREAKOUT + WATCH/RECOVERY + WAIT + AVOID")
    print("Transparent rules only — no hidden score, ranking, probability or price forecast.")
    print("#" * 124)

    headers = f"{'Stock':<13}{'Price':>12}  {'Action':<24} {'Tech':<31} {'Fund':<14} {'Valuation':<16} {'Setup':<27} {'Risk':<10}"
    print(headers)
    print("-" * len(headers))
    for r in results:
        d = build_v6_action(r)
        r["V6"] = d
        f = r.get("Fundamentals", {})
        fund = d.get("Fundamental", "N/A")
        if pd.notna(f.get("FundamentalScore", np.nan)):
            fund = f"{fund} {f['FundamentalScore']:.0f}"
        print(f"{r['Stock']:<13}{money(r['Price']):>12}  {_v6_action_icon(d['Action'])} {d['Action']:<21} {d.get('Technical','N/A'):<31} {fund:<14} {d.get('Valuation','N/A'):<16} {d.get('Setup','N/A'):<27} {d.get('RiskLevel','N/A'):<10}")

    print("\nV6 BUY / ACTION PLANS")
    for r in results:
        d = r["V6"]
        print("\n" + "─" * 92)
        print(f"{r['Stock']} — {money(r['Price'])} — {_v6_action_icon(d['Action'])} {d['Action']}")
        print("─" * 92)
        print("  WHY?")
        for reason in d["Reasons"]:
            print(f"  • {reason}")
        print("  PLAN")
        for line in _v6_plan_text(d):
            print(f"  • {line}")
        print("  ENTRY STATUS")
        print(f"  • {d.get('EntryStatus','N/A')}")
        print("  WHY NOT BUY NOW?")
        print(f"  • {d.get('WhyNotNow','N/A')}")
        print("  BEGINNER DECISION")
        print(f"  • {d.get('BeginnerDecision','N/A')}")
        if "BUY" in d["Action"]:
            print("  • BUY is conditional decision support — wait for the stated confirmation/trigger and respect the stop.")
        if d["Action"] == "AVOID — BEARISH":
            print("  • Reconsider only after the technical structure improves; strong fundamentals alone do not override a bearish setup.")

    print("\nV6 ACTION RULES")
    print("  🟢 BUY               = technical + fundamental alignment with acceptable entry conditions")
    print("  🟢 BUY ON BREAKOUT   = strong/constructive technical + fundamental setup; enter only after the stated breakout confirmation")
    print("  🟡 WATCH / RECOVERY  = recovery signs exist, but the larger trend needs confirmation")
    print("  🟡 WAIT — DO NOT CHASE = constructive setup but entry is too close to resistance/valuation risk")
    print("  🟡 WATCH — CONFIRMATION = mixed evidence; wait for stronger confirmation")
    print("  🔴 AVOID — BEARISH   = current technical structure is bearish")
    print("  RISK LEVEL = transparent band using existing mechanical stop risk + Technical Risk Flags; NOT probability of loss.")
    print("  For BUY ON BREAKOUT, current price is NOT the entry; breakout entry is the stated confirmation trigger.")
    print("  IMPORTANT: BUY does not mean guaranteed profit. Mechanical levels are risk-management references, not price forecasts.")


def _v6_load_portfolio():
    """Load optional portfolio.csv. Columns: Symbol, Qty, AvgPrice. Other columns are ignored."""
    path = PORTFOLIO_FILE
    try:
        if not path or not pd.io.common.file_exists(path):
            return None
        df = pd.read_csv(path)
        cols = {str(c).strip().lower(): c for c in df.columns}
        symbol_col = cols.get("symbol") or cols.get("ticker")
        qty_col = cols.get("qty") or cols.get("quantity") or cols.get("shares")
        avg_col = cols.get("avgprice") or cols.get("averageprice") or cols.get("avg_price")
        if not symbol_col or not qty_col or not avg_col:
            print(f"\nV6 PORTFOLIO: {path} found, but required columns are Symbol, Qty, AvgPrice. Skipping.")
            return None
        out = pd.DataFrame({
            "Symbol": df[symbol_col].astype(str).str.strip().str.upper(),
            "Qty": pd.to_numeric(df[qty_col], errors="coerce"),
            "AvgPrice": pd.to_numeric(df[avg_col], errors="coerce"),
        }).dropna(subset=["Symbol", "Qty", "AvgPrice"])
        return out[out["Qty"] > 0].copy()
    except Exception as exc:
        print(f"\nV6 PORTFOLIO: unable to read {path}: {exc}")
        return None


def print_v6_portfolio_intelligence(results):
    portfolio = _v6_load_portfolio()
    if portfolio is None or portfolio.empty:
        print("\nV6 PORTFOLIO INTELLIGENCE: skipped — optional portfolio.csv not found.")
        print("  Create portfolio.csv with columns: Symbol, Qty, AvgPrice")
        return

    by_symbol = {str(r.get("Stock", "")).upper(): r for r in results}
    print("\n" + "#" * 124)
    print("STOCKAI V6 — PORTFOLIO INTELLIGENCE")
    print("Existing holdings are evaluated separately from fresh scanner BUY decisions.")
    print("#" * 124)
    hdr = f"{'Stock':<13}{'Qty':>8}{'Avg':>12}{'Price':>12}{'P/L %':>10}  {'Action':<24} {'Trend':<22}"
    print(hdr)
    print("-" * len(hdr))
    for _, row in portfolio.iterrows():
        symbol = row["Symbol"]
        symbol_yf = symbol if symbol.endswith(".NS") else symbol + ".NS"
        r = by_symbol.get(symbol_yf.upper()) or by_symbol.get(symbol.upper())
        if r is None:
            print(f"{symbol:<13}{row['Qty']:>8.0f}{money(row['AvgPrice']):>12}{'N/A':>12}{'N/A':>10}  ⚪ NOT SCANNED")
            continue
        price = r.get("Price", np.nan)
        pnl_pct = ((price / row["AvgPrice"]) - 1.0) * 100 if pd.notna(price) and row["AvgPrice"] else np.nan
        d = r.get("V6") or build_v6_action(r)
        technical = d.get("Technical", "")
        if technical in ["BEARISH", "STRONG BEARISH", "MIXED / BEARISH"]:
            hold_action = "REDUCE / EXIT REVIEW" if pnl_pct < -10 else "HOLD — REVIEW"
        elif technical in ["STRONG", "CONSTRUCTIVE"] and d.get("Fundamental") in ["STRONG", "CONSTRUCTIVE"]:
            hold_action = "HOLD / MANAGE RISK"
        else:
            hold_action = "HOLD — WATCH"
        print(f"{symbol:<13}{row['Qty']:>8.0f}{money(row['AvgPrice']):>12}{money(price):>12}{pnl_pct:>9.2f}%  {_v6_action_icon(hold_action)} {hold_action:<21} {technical:<22}")

    print("\nPORTFOLIO RULES")
    print("  • A holding is NOT automatically sold because its scanner action is AVOID.")
    print("  • REDUCE / EXIT REVIEW means review the thesis, position size, trend and risk — it is not a forced sell signal.")
    print("  • Existing holdings and new BUY candidates are intentionally separated.")
    print("  • For a personalized portfolio decision, also consider taxes, capital needs, position concentration and MTF/loan costs outside this technical engine.")

def final_report(results):
    if not results:
        print("\nNo usable stock results.")
        return

    # V5 fundamentals are attached after the V4.7 technical scan; technical calculations remain unchanged.
    attach_fundamentals(results)
    print_fundamental_dashboard(results)

    # V5.1 news is independent context; it does not alter V4.7/V5 calculations.
    attach_news(results)
    print_news_dashboard(results)

    df = pd.DataFrame(results)

    # V4.7 context is descriptive only. It does not modify stock calculations.
    market = fetch_market_data("^NSEI")
    if market is not None:
        market_regime = market_regime_label(
            market["Price"], market["EMA20"], market["EMA50"], market["EMA200"],
            market["MACD"] > market["MACDSignal"],
            market["STDirection"] == "BULLISH",
            market["ADX"], market["+DI"], market["-DI"],
        )
        for r in results:
            r["MarketStockContext"] = market_stock_context(market_regime, r["Signal"], r["Trend"])
    else:
        for r in results:
            r["MarketStockContext"] = "MARKET CONTEXT UNAVAILABLE"

    print_market_dashboard(results)

    # V5.4 consolidated analysis: descriptive synthesis only.
    for r in results:
        r["V52"] = build_v52_analysis(r, r.get("MarketStockContext", "MARKET CONTEXT UNAVAILABLE"))
    print_v52_quick_map(results)
    print_v52_cards(results)
    print_v56_decision_intelligence(results)
    print_v6_action_engine(results)
    print_v6_portfolio_intelligence(results)

    print("\n" + "#" * 118)
    print("STOCKAI V4.7 — QUICK DECISION MAP")
    print("Action + Technical Indicators + Trade Setup + Entry + Breakout + Breakdown + Stop Loss + Targets")
    print("#" * 190)
    print(f"{'Stock':<12}{'Price':>12}  {'Setup':<20}  {'RSI':>4} {'MACD':>5} {'ST':>4} {'ADX':>5} {'VOL':>5} {'STR':>5} {'S/R':>6}  {'Action':<24} {'Entry':>12} {'Breakout':>12} {'Breakdown':>12} {'Stop':>12} {'T1':>12} {'T2':>12} {'RiskFlags':>9}")
    print("-" * 190)
    for _, x in df.sort_values("TechnicalRisk").iterrows():
        setup = x["Signal"][:20]
        action = x["Action"][:23]
        rsi_icon = indicator_circle("rsi", x["RSI"])
        macd_icon = indicator_circle("macd", x["MACD"], bullish=x["MACD_Bull"])
        st_icon = indicator_circle("st", x["ST_Direction"])
        adx_icon = indicator_circle("adx_strength", x["ADX"])
        vol_icon = indicator_circle("volume", x["VolumeRatio"])
        if x["Breakdown"] or "DOWNTREND" in x["Trend"]:
            str_icon = "🔴"
        elif x["Breakout"] or x["Retest"]:
            str_icon = "🟢"
        elif "UPTREND" in x["Trend"]:
            str_icon = "🟡"
        else:
            str_icon = "🟡"
        sr_icon = '🔴' if x['ResistanceDistancePct'] <= 1.0 else ('🟡' if x['ResistanceDistancePct'] <= 2.5 else ('🟢' if x['SupportDistancePct'] <= 2.0 else '🟡'))
        print(f"{x['Stock']:<12}{money(x['Price']):>12}  {setup:<20}  {rsi_icon:>4} {macd_icon:>5} {st_icon:>4} {adx_icon:>5} {vol_icon:>5} {str_icon:>5} {sr_icon:>6}  {action:<24} {money(x['Entry']):>12} {money(x['BreakoutEntry']):>12} {money(x['BreakdownTrigger']):>12} {money(x['StopLoss']):>12} {money(x['Target1']):>12} {money(x['Target2']):>12} {x['TechnicalRisk']:>9.0f}")

    print("\nTECHNICAL INDICATOR LEGEND")
    print("  RSI  = 🟢 healthy/constructive   🟡 neutral/caution   🔴 weak/extreme")
    print("  MACD = 🟢 bullish                🔴 bearish")
    print("  ST   = 🟢 bullish                🔴 bearish")
    print("  ADX  = 🟢 strong trend (>=25)   🟡 meaningful/early (20-24.99)   ⚪ weak (<20)")
    print("  DI   = 🟢 bullish direction (+DI > -DI)   🔴 bearish direction (+DI < -DI)")
    print("  VOL  = 🟢 >=1.5x average         🟡 0.8–1.49x         🟠 0.5–0.79x         🔴 <0.5x")
    print("  STR  = 🟢 confirmed bullish structure   🟡 bullish/constructive but breakout not confirmed   🔴 bearish/breakdown structure")
    print("  S/R  = 🔴 resistance very close   🟡 structural caution/neutral   🟢 price near support")

    print("\nBREAKOUT / BREAKDOWN STATUS")
    for _, x in df.iterrows():
        print(f"  {x['Stock']:<12} {x['BreakoutStatus']:<24} | nearest resistance {money(x['NearestResistance'])} | confirmation {money(x['BreakoutEntry']) if not x['Breakdown'] else 'N/A'}")

    print("\nS/R DECISION MAP")
    for _, x in df.iterrows():
        print(f"  {x['Stock']:<12} Support {money(x['NearestSupport']):>12} ({x['SupportStrength']:<10}) | Resistance {money(x['NearestResistance']):>12} ({x['ResistanceStrength']:<10}) | {x['SRBias']}")

    final_indicator_dashboard(results)
    print("\nV4.7 TRADE SETUP MAP")
    for _, x in df.iterrows():
        r1 = money(x['ImmediateTriggerPrice']) if pd.notna(x['ImmediateTriggerPrice']) else 'N/A'
        breakout = money(x['BreakoutConfirmationPrice']) if pd.notna(x['BreakoutConfirmationPrice']) else 'N/A'
        invalid = money(x['SetupInvalidationPrice']) if pd.notna(x['SetupInvalidationPrice']) else 'N/A'
        stop = money(x['TradeStopPrice']) if pd.notna(x['TradeStopPrice']) else 'N/A'
        print(f"  {x['Stock']:<12} {x['SetupState']:<28} | R1 {r1:>12} | breakout {breakout:>12} | stop {stop:>12} | invalidation {invalid:>12}")

    print("\nV5.5.3 FUNDAMENTAL SNAPSHOT")
    for _, x in df.iterrows():
        f = x.get("Fundamentals", {})
        score = f.get("FundamentalScore", np.nan)
        score_text = "N/A" if pd.isna(score) else f"{score:.0f}/100"
        print(f"  {x['Stock']:<12} {fundamental_icon(score, f.get('FundamentalHealth',''))} {score_text:>6} | {f.get('FundamentalHealth','N/A')}")
        rg = f.get("RevenueGrowthPct", np.nan); pg = f.get("ProfitGrowthPct", np.nan); roe = f.get("ROE", np.nan); roce = f.get("ROCE", np.nan); de = f.get("DebtToEquity", np.nan)
        print(f"    Revenue growth {_safe_text(f"{rg:+.1f}%" if pd.notna(rg) else None)} | Profit growth {_safe_text(f"{pg:+.1f}%" if pd.notna(pg) else None)} | ROE {_safe_text(f"{roe:.1f}%" if pd.notna(roe) else None)} | ROCE {_safe_text(f"{roce:.1f}%" if pd.notna(roce) else None)} | D/E {_safe_text(f"{de:.1f}" if pd.notna(de) else None)}")
        pe_text = "N/A" if pd.isna(f.get("PE", np.nan)) else f"{f.get('PE'):.1f}"
        pb_text = "N/A" if pd.isna(f.get("PB", np.nan)) else f"{f.get('PB'):.1f}"
        print(f"    P/E {pe_text} | P/B {pb_text} | FCF {_format_fund_value(f.get('FCF',np.nan))}")
        print(f"    Sector {f.get('Sector','N/A')} | Industry {f.get('Industry','N/A')}")
        notes = _fundamental_quality_flags(f)
        if notes:
            print("    Valuation/Quality flags: " + " | ".join(notes[:4]))

    print_stock_cards(results)

    print("\nHOW TO READ THE ACTION LABELS")
    print("  🟢 CONFIRMED BREAKOUT  = price cleared the historical breakout level with the scanner's volume/trend confirmation")
    print("  🟢 BREAKOUT RETEST      = a previously broken level is being retested and still holding")
    print("  🟡 WAIT — BREAKOUT      = constructive setup, but historical breakout confirmation is still missing")
    print("  🟡 WAIT — RESISTANCE    = setup is constructive, but nearby resistance is very close")
    print("  🟡 WATCH — BULLISH      = bullish structure without complete breakout confirmation")
    print("  🟡 WATCH / SUPPORT      = price is near a support area that matters to the setup")
    print("  S/R strength            = based on clustered historical level touches; PROJECTED means there was not enough historical evidence for a real level")
    print("  Technical Risk Flags    = structural/bearish risk flags (0–100); NOT a probability of loss; 0 does NOT mean risk-free")
    print("  Mechanical stop risk    = percentage distance from reference entry to mechanical stop; separate from Technical Risk Flags")
    print("  Completeness            = number of currently confirmed technical components; descriptive, not a success probability")
    print("  🔴 AVOID — BEARISH      = bearish structure / elevated technical risk score")
    print("  🔴 AVOID — BREAKDOWN    = historical support breakdown is confirmed")

    print("\nV5.5.3 INTERPRETATION RULES")
    print("  • The consolidated card explains what the existing technical, fundamental, news and market layers are saying together.")
    print("  • News relevance is ranked company-specific > sector/context; only HIGH-relevance, genuinely company-specific event headlines drive the main positive/negative News View; list-style and price-action headlines are context only.")
    print("  • Contradictions are displayed explicitly instead of being collapsed into one score.")
    print("  • Fundamental Score remains a rule-based health summary, not a return probability or price target.")
    print("  • News never changes Technical Risk Flags, Fundamental Score, Entry, Stop or mechanical levels.")

    print("\nIMPORTANT")
    print("  Reference price is the current market price used for calculation; it is NOT a buy instruction.")
    print("  Breakout confirmation is separate from the nearest resistance. First clear R1, then confirm the historical breakout level.")
    print("  Trade stop and setup invalidation are separate concepts. For bearish setups, invalidation is kept below current price to avoid misleading levels.")
    print("  Mechanical Stop and Mechanical T1/T2/T3 are scanner levels: Stop = 1.5 ATR; T1/T2/T3 = 1.5R / 2.5R / 3.5R. They are not price forecasts.")
    print("  V4.3 Trade Setup Engine interprets the existing levels; it does not predict future prices or guarantee execution.")
    print("  This remains technical decision-support, not a guarantee of future returns.")


def main():
    print("=" * 78)
    print("STOCKAI SCANNER V6.0")
    print("Market Dashboard + Advanced S/R + Trade Setup + Indicator Dashboard + Fundamentals + News + Decision Intelligence")
    print("V3.2.5 core logic preserved | V4.2 S/R | V4.3 Trade Setup | V4.4 Dashboard | V4.5 Stock Cards | V4.5.1 cleanup | V4.6 Market Dashboard | V4.7 consistency + context cleanup | V5 Fundamentals | V5.1 News & Events | V5.2 Consolidated Analysis | V5.4 News quality + terminology cleanup | V5.5.3 fundamental scoring + sector mapping + strict news relevance + duplicate flag cleanup | V5.6 Decision Intelligence polish")
    print("Core breakout volume threshold: 1.50x")
    print("=" * 78)
    print(f"Universe: {len(STOCKS)} stocks | Data: {DATA_PERIOD} | Timeframe: Daily")
    print("VISUAL LEGEND:")
    print("  🟢 Confirmed / constructive   🟡 Wait / watch   🟠 Caution   🔴 Bearish / breakdown   ⚪ Not confirmed")

    results = []
    for symbol in STOCKS:
        try:
            result = analyse_stock(symbol)
            if result is None:
                print(f"Skipping {symbol}: insufficient/invalid data")
                continue
            results.append(result)
            print_stock_report(result)
        except Exception as exc:
            print(f"ERROR {symbol}: {exc}")

    final_report(results)


if __name__ == "__main__":
    main()

