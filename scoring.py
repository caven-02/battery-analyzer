"""
scoring.py — Battery Thermal Analyzer v4
Piecewise linear scoring model with M_safety multiplier.
"""
import pandas as pd
import numpy as np

try:
    from scipy.optimize import curve_fit
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

# ── Column name constants ─────────────────────────────────────────────────────
COL_CELL_HIGH  = "Highest_Single_Cell_Temp"
COL_CELL_LOW   = "Lowest_Single_Cell_Temp"
COL_CELL_AVG   = "Average_Single_Cell_Temp"
COL_MOSFET_MAX = "MOSFET_Highest_Temp"
COL_MOSFET_AVG = "MOSFET_Average_Temp"
COL_AMBIENT    = "Ambient_Temp"
COL_BMS_AVG    = "BMS_Temp_Average"
COL_BMS_HIGH   = "BMS_Temp_Highest"
COL_BMS_LOW    = "BMS_Temp_Lowest"
COL_ALARM_CELL = "Alarm_Single_Core_High_Temp"
COL_ALARM_MOS  = "Alarm_MOSFET_Overtemp"

# ── Piecewise linear scorer ───────────────────────────────────────────────────
def _score(x, w_max, x_ideal, x_fail):
    """
    S_i(x) = W_max                                        for x <= x_ideal
    S_i(x) = W_max - W_max * (x-x_ideal)/(x_fail-x_ideal) for x_ideal < x < x_fail
    S_i(x) = 0                                            for x >= x_fail
    """
    return max(0.0, min(float(w_max),
        float(w_max) - float(w_max) * (float(x) - float(x_ideal))
        / (float(x_fail) - float(x_ideal))
    ))

# Weighted metric scorers (match images exactly)
score_ss   = lambda t_ss:      _score(t_ss,    20, 35.0, 55.0)   # steady-state cell temp
score_amb  = lambda dt_amb:    _score(dt_amb,  20, 10.0, 25.0)   # ambient-to-cell deltaT
score_uni  = lambda dt_cell:   _score(dt_cell, 40,  2.0,  5.0)   # cell uniformity
score_rise = lambda rise_cs:   _score(rise_cs, 10,  1.2,  3.0)   # rise rate °C/s
score_mos  = lambda dt_mos:    _score(dt_mos,  10, 10.0, 30.0)   # MOSFET deltaT

def _smooth(series, window=3):
    return series.rolling(window=window, center=True, min_periods=1).median()

def _parse_timestamps(ts_series):
    """Return elapsed seconds as float Series. Tries datetime, then numeric."""
    try:
        parsed = pd.to_datetime(ts_series, dayfirst=True)
        elapsed = (parsed - parsed.iloc[0]).dt.total_seconds()
        # If total duration < 1 s, pandas misread integers as epoch nanoseconds — fall through
        if elapsed.max() < 1.0:
            raise ValueError("duration too short")
        return elapsed
    except Exception:
        numeric = pd.to_numeric(ts_series, errors="coerce")
        t0 = numeric.iloc[0]
        t_max = numeric.max() - t0
        if t_max > 3600:
            return numeric - t0          # already seconds
        elif t_max > 60:
            return numeric - t0          # seconds
        else:
            return (numeric - t0) * 60   # minutes → seconds

def _steady_state(time_s, avg_cell, window_frac=0.10, slope_threshold=0.002):
    """
    Detect steady-state temperature.
    window_frac: fraction of run duration to use as trailing window.
    slope_threshold: °C/s — if slope in window is below this, it's steady.

    Returns (value, is_extrapolated, confidence_note)
    """
    n = len(avg_cell)
    window = max(5, int(n * window_frac))
    tail_temp = avg_cell.iloc[-window:]
    tail_time = time_s.iloc[-window:]

    # Fit line to tail to get slope
    if len(tail_time) >= 2:
        coeffs = np.polyfit(tail_time.values, tail_temp.values, 1)
        slope = abs(coeffs[0])  # °C/s
    else:
        slope = 0.0

    if slope <= slope_threshold:
        # Genuinely flat — use mean of tail
        return float(tail_temp.mean()), False, f"Measured (slope {slope*1000:.3f} m°C/s)"
    else:
        # Still rising — extrapolate asymptote
        if SCIPY_OK:
            try:
                t0  = float(time_s.iloc[0])
                t_s = time_s.values - t0
                T   = avg_cell.values

                def model(t, T_ss, tau):
                    return T_ss * (1 - np.exp(-t / tau)) + T[0] * np.exp(-t / tau)

                p0     = [T[-1] + 5.0, float(t_s[-1])]
                bounds = ([T[-1], 1.0], [T[-1] + 50.0, 1e6])
                popt, _ = curve_fit(model, t_s, T, p0=p0, bounds=bounds, maxfev=5000)
                T_ss = float(popt[0])
                return T_ss, True, f"Extrapolated (still rising at {slope*1000:.1f} m°C/s)"
            except Exception:
                pass
        # Fallback: linear extrapolation
        T_ss = float(tail_temp.iloc[-1]) + slope * float(time_s.iloc[-1]) * 0.5
        return T_ss, True, f"Extrapolated-linear (still rising at {slope*1000:.1f} m°C/s)"

def _fit_tau(time_s, cell_high, ambient):
    """Fit exponential cool-down to get thermal time constant τ (minutes)."""
    if not SCIPY_OK:
        return None
    peak_loc = cell_high.values.argmax()
    if peak_loc >= len(cell_high) * 0.80:
        return None
    cool_T   = cell_high.iloc[peak_loc:].values
    cool_t   = (time_s.iloc[peak_loc:] - time_s.iloc[peak_loc]).values
    cool_amb = ambient.iloc[peak_loc:].values if ambient is not None else np.full(len(cool_T), 22.0)
    if cool_T[-1] >= cool_T[0]:
        return None
    try:
        T_amb = float(np.mean(cool_amb))
        def model(t, tau):
            return T_amb + (cool_T[0] - T_amb) * np.exp(-t / tau)
        popt, _ = curve_fit(model, cool_t, cool_T, p0=[300.0], bounds=(1.0, 1e5), maxfev=3000)
        return round(float(popt[0]) / 60.0, 2)  # seconds → minutes
    except Exception:
        return None

def compute_metrics(df, time_col, thresholds):
    """Compute all metrics. Returns dict including internal series prefixed with _."""
    def col(name):
        return df[name].copy() if name in df.columns else None

    time_s    = _parse_timestamps(df[time_col])
    time_min  = time_s / 60.0
    dt_s      = time_s.diff().replace(0, np.nan)

    cell_high = col(COL_CELL_HIGH)
    cell_low  = col(COL_CELL_LOW)
    cell_avg  = col(COL_CELL_AVG)
    mosfet_mx = col(COL_MOSFET_MAX)
    mosfet_av = col(COL_MOSFET_AVG)
    ambient   = col(COL_AMBIENT)
    bms_avg   = col(COL_BMS_AVG)
    bms_high  = col(COL_BMS_HIGH)
    bms_low   = col(COL_BMS_LOW)

    # ── Alarms ───────────────────────────────────────────────────────────────
    def alarm_fired(c):
        s = col(c)
        return bool((pd.to_numeric(s, errors="coerce").fillna(0) > 0).any()) if s is not None else False

    alarm_cell  = alarm_fired(COL_ALARM_CELL)
    alarm_mosfet = alarm_fired(COL_ALARM_MOS)
    any_alarm   = alarm_cell or alarm_mosfet

    # ── Cell temps ────────────────────────────────────────────────────────────
    peak_cell = float(cell_high.max()) if cell_high is not None else None
    min_cell  = float(cell_low.min())  if cell_low  is not None else None

    # ── Steady-state ──────────────────────────────────────────────────────────
    ss_value, ss_extrapolated, ss_note = None, False, "No avg cell data"
    if cell_avg is not None:
        ss_value, ss_extrapolated, ss_note = _steady_state(time_s, cell_avg)

    # ── Cell ΔT ───────────────────────────────────────────────────────────────
    if cell_high is not None and cell_low is not None:
        delta_series = cell_high - cell_low
        max_delta    = float(delta_series.max())
        avg_delta    = float(delta_series.mean())
    else:
        delta_series = pd.Series(dtype=float)
        max_delta    = None
        avg_delta    = None

    # ── Rise rate in °C/s (smoothed) ─────────────────────────────────────────
    rise_series_cs = pd.Series(dtype=float)
    accel_series   = pd.Series(dtype=float)
    max_rise_cs    = None
    max_accel      = None

    if cell_high is not None:
        smoothed   = _smooth(cell_high)
        rise_cs    = smoothed.diff() / dt_s
        rise_cs    = rise_cs.replace([np.inf, -np.inf], np.nan)
        rise_series_cs = rise_cs
        max_rise_cs = float(rise_cs.max(skipna=True))
        if np.isnan(max_rise_cs): max_rise_cs = 0.0

        accel_cs   = rise_cs.diff() / dt_s
        accel_cs   = accel_cs.replace([np.inf, -np.inf], np.nan)
        accel_series = accel_cs
        max_accel  = float(accel_cs.max(skipna=True))
        if np.isnan(max_accel): max_accel = 0.0

    # ── MOSFET ΔT ─────────────────────────────────────────────────────────────
    mosfet_peak  = float(mosfet_mx.max()) if mosfet_mx is not None else None
    mosfet_avg_v = float(mosfet_av.mean()) if mosfet_av is not None else None

    if mosfet_mx is not None and mosfet_av is not None:
        mosfet_delta_series = mosfet_mx - mosfet_av
        max_mosfet_delta    = float(mosfet_delta_series.max())
    else:
        mosfet_delta_series = pd.Series(dtype=float)
        max_mosfet_delta    = None

    # ── Ambient → Cell ΔT ─────────────────────────────────────────────────────
    ambient_avg   = float(ambient.mean()) if ambient is not None else None
    if cell_avg is not None and ambient is not None:
        amb_delta_series = cell_avg - ambient
        max_amb_delta    = float(amb_delta_series.max())
    else:
        amb_delta_series = pd.Series(dtype=float)
        max_amb_delta    = None

    # ── Thermal dose ─────────────────────────────────────────────────────────
    dose_threshold = thresholds.get("dose_threshold", 40.0)
    if cell_high is not None:
        excess = (cell_high - dose_threshold).clip(lower=0)
        _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
        thermal_dose = float(_trapz(excess, x=time_min))
        if np.isnan(thermal_dose): thermal_dose = 0.0
    else:
        thermal_dose = None

    # ── BMS ───────────────────────────────────────────────────────────────────
    bms_peak_v = float(bms_high.max()) if bms_high is not None else None
    bms_avg_v  = float(bms_avg.mean()) if bms_avg  is not None else None
    bms_min_v  = float(bms_low.min())  if bms_low  is not None else None

    # ── Thermal time constant ─────────────────────────────────────────────────
    tau = None
    if cell_high is not None:
        tau = _fit_tau(time_s, cell_high, ambient)

    duration_min = float(time_min.max() - time_min.min())

    return {
        # Weighted metric inputs
        "ss_value":          ss_value,
        "ss_extrapolated":   ss_extrapolated,
        "ss_note":           ss_note,
        "max_amb_delta":     max_amb_delta,
        "max_delta":         max_delta,
        "avg_delta":         avg_delta,
        "max_rise_cs":       max_rise_cs,
        "max_mosfet_delta":  max_mosfet_delta,
        # Safety / display inputs
        "peak_cell":         peak_cell,
        "min_cell":          min_cell,
        "mosfet_peak":       mosfet_peak,
        "mosfet_avg":        mosfet_avg_v,
        "max_accel":         max_accel,
        "thermal_dose":      thermal_dose,
        "dose_threshold":    dose_threshold,
        "tau":               tau,
        # Alarms
        "alarm_cell":        alarm_cell,
        "alarm_mosfet":      alarm_mosfet,
        "any_alarm":         any_alarm,
        # BMS (display only)
        "bms_peak":          bms_peak_v,
        "bms_avg":           bms_avg_v,
        "bms_min":           bms_min_v,
        # Ambient
        "ambient_avg":       ambient_avg,
        # Meta
        "duration_min":      duration_min,
        "n_samples":         len(df),
        # Series for charts
        "_time_s":           time_s,
        "_time_min":         time_min,
        "_delta_series":     delta_series,
        "_rise_series_cs":   rise_series_cs,
        "_accel_series":     accel_series,
        "_mosfet_delta_s":   mosfet_delta_series,
        "_amb_delta_s":      amb_delta_series,
    }


def score_run(metrics, thresholds):
    """
    Score = M_safety * (S_ss + S_amb + S_uni + S_rise + S_mos)

    M_safety = 0 if:
      - Peak cell temp >= 60°C, OR
      - Peak MOSFET temp >= 85°C, OR
      - Any alarm fired
    M_safety = 1 otherwise

    Returns (total_score: int, breakdown: dict)
    """
    peak_cell_override  = thresholds.get("override_peak_cell",  60.0)
    peak_mosfet_override = thresholds.get("override_peak_mosfet", 85.0)

    # ── M_safety ──────────────────────────────────────────────────────────────
    safety_fail_reason = None
    if metrics.get("any_alarm"):
        safety_fail_reason = "Alarm_Single_Core_High_Temp triggered"
    elif (metrics.get("peak_cell") or 0) >= peak_cell_override:
        safety_fail_reason = f"Peak cell {metrics['peak_cell']:.1f}°C ≥ {peak_cell_override}°C override"
    elif (metrics.get("mosfet_peak") or 0) >= peak_mosfet_override:
        safety_fail_reason = f"Peak MOSFET {metrics['mosfet_peak']:.1f}°C ≥ {peak_mosfet_override}°C override"

    m_safety = 0.0 if safety_fail_reason else 1.0

    # ── Weighted scores ───────────────────────────────────────────────────────
    ss   = metrics.get("ss_value")
    amb  = metrics.get("max_amb_delta")
    uni  = metrics.get("max_delta")
    rise = metrics.get("max_rise_cs")
    mos  = metrics.get("max_mosfet_delta")

    s_ss   = score_ss(ss)     if ss   is not None else 20.0  # no data → assume ideal
    s_amb  = score_amb(amb)   if amb  is not None else 20.0
    s_uni  = score_uni(uni)   if uni  is not None else 40.0
    s_rise = score_rise(rise) if rise is not None else 10.0
    s_mos  = score_mos(mos)   if mos  is not None else 10.0

    raw_total  = s_ss + s_amb + s_uni + s_rise + s_mos
    final      = int(round(m_safety * raw_total))

    breakdown = {}

    if safety_fail_reason:
        breakdown["⚠️ SAFETY OVERRIDE"] = {
            "points": 0, "max": 100, "is_override": True,
            "detail": safety_fail_reason
        }
        return 0, breakdown

    # Weighted breakdown
    ss_label = " ⚠️ EXTRAPOLATED" if metrics.get("ss_extrapolated") else ""
    breakdown["Steady-state Cell Temp"] = {
        "points": round(s_ss, 1), "max": 20, "is_override": False,
        "detail": f"{ss:.1f}°C{ss_label}  |  ideal ≤35°C  |  fail ≥55°C"
        if ss is not None else "No data"
    }
    breakdown["Max Ambient → Cell ΔT"] = {
        "points": round(s_amb, 1), "max": 20, "is_override": False,
        "detail": f"{amb:.1f}°C  |  ideal ≤10°C  |  fail ≥25°C"
        if amb is not None else "No Ambient_Temp column"
    }
    breakdown["Max Cell ΔT (Uniformity)"] = {
        "points": round(s_uni, 1), "max": 40, "is_override": False,
        "detail": f"{uni:.2f}°C  |  ideal ≤2°C  |  fail ≥5°C"
        if uni is not None else "No data"
    }
    breakdown["Max Rise Rate"] = {
        "points": round(s_rise, 1), "max": 10, "is_override": False,
        "detail": f"{rise:.4f}°C/s  |  ideal ≤1.2°C/s  |  fail ≥3.0°C/s"
        if rise is not None else "No data"
    }
    breakdown["Max MOSFET ΔT"] = {
        "points": round(s_mos, 1), "max": 10, "is_override": False,
        "detail": f"{mos:.1f}°C  |  ideal ≤10°C  |  fail ≥30°C"
        if mos is not None else "No MOSFET data"
    }

    return final, breakdown
