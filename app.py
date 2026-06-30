"""
app.py — Battery Thermal Analyzer v4
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

from scoring import (
    compute_metrics, score_run,
    COL_CELL_HIGH, COL_CELL_LOW, COL_CELL_AVG,
    COL_MOSFET_MAX, COL_MOSFET_AVG, COL_AMBIENT,
    COL_BMS_AVG, COL_BMS_HIGH, COL_BMS_LOW,
    COL_ALARM_CELL, COL_ALARM_MOS,
    _parse_timestamps,
)
from database import init_db, save_run, get_all_runs, get_run_by_id, get_pack_ids

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Battery Thermal Analyzer",
                   page_icon="🔋", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
h1,h2,h3,h4{font-family:'Space Mono',monospace;}

.mc{background:#0f1117;border:1px solid #2a2d3a;border-radius:8px;padding:13px 15px;margin:4px 0;min-height:80px;}
.mc.warn{border-color:#ef4444;background:#1a0f0f;}
.mc.amber{border-color:#f59e0b;background:#1a1500;}
.mc.ok{border-color:#22c55e33;}
.mc.display{border-color:#374151;background:#111827;}
.mc-label{color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px;}
.mc-value{color:#f9fafb;font-size:21px;font-weight:600;font-family:'Space Mono',monospace;line-height:1.2;}
.mc-value.warn{color:#ef4444;} .mc-value.amber{color:#f59e0b;}
.mc-unit{color:#9ca3af;font-size:11px;margin-left:2px;}
.mc-sub{color:#6b7280;font-size:10px;margin-top:3px;}
.mc-badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:9px;
          font-weight:700;letter-spacing:1px;margin-left:4px;vertical-align:middle;}
.badge-extrap{background:#78350f;color:#fde68a;}
.badge-display{background:#1f2937;color:#6b7280;}
.badge-alarm{background:#450a0a;color:#fca5a5;}

.score-wrap{text-align:center;}
.score-circle{display:inline-flex;flex-direction:column;align-items:center;
  justify-content:center;width:155px;height:155px;border-radius:50%;
  font-family:'Space Mono',monospace;}
.sc-pass{background:radial-gradient(circle,#052e16,#14532d);border:3px solid #22c55e;}
.sc-warn{background:radial-gradient(circle,#1c1917,#431407);border:3px solid #f97316;}
.sc-fail{background:radial-gradient(circle,#1c0a0a,#450a0a);border:3px solid #ef4444;}
.sc-num{font-size:42px;font-weight:700;color:#f9fafb;line-height:1;}
.sc-lbl{font-size:10px;color:#9ca3af;margin-top:2px;}
.verdict{font-size:15px;font-weight:700;margin-top:8px;letter-spacing:2px;
         font-family:'Space Mono',monospace;}
.vpass{color:#22c55e;} .vwarn{color:#f97316;} .vfail{color:#ef4444;}

.bd-row{display:flex;justify-content:space-between;align-items:flex-start;
        padding:6px 0;border-bottom:1px solid #1f2130;}
.bd-name{color:#9ca3af;font-size:12px;}
.bd-detail{color:#6b7280;font-size:10px;margin-top:1px;}
.bd-pts{font-family:'Space Mono',monospace;font-weight:700;font-size:12px;
        white-space:nowrap;margin-left:10px;}

.alarm-banner{background:#450a0a;border:2px solid #ef4444;border-radius:8px;
  padding:12px 18px;margin:10px 0;font-family:'Space Mono',monospace;
  color:#ef4444;font-size:13px;letter-spacing:1px;}
.mosfet-banner{background:#1c1107;border:1px solid #f97316;border-radius:6px;
  padding:9px 15px;margin:5px 0;color:#f97316;font-size:12px;}

.sec-hdr{font-family:'Space Mono',monospace;font-size:10px;color:#6b7280;
  text-transform:uppercase;letter-spacing:2px;
  padding:6px 0 4px;border-bottom:1px solid #2a2d3a;margin-bottom:10px;}

.stButton>button{background:#2563eb;color:white;border:none;border-radius:6px;
  font-weight:600;padding:10px 22px;font-family:'DM Sans',sans-serif;}
.stButton>button:hover{background:#1d4ed8;}

.section-label{font-size:10px;color:#4b5563;text-transform:uppercase;
  letter-spacing:2px;margin:10px 0 4px;font-family:'Space Mono',monospace;}
</style>
""", unsafe_allow_html=True)

DB_PATH = os.path.join(os.path.dirname(__file__), "battery_runs.db")
init_db(DB_PATH)

# ── Colour palette ────────────────────────────────────────────────────────────
C_CELL_HIGH = "#3b82f6"
C_CELL_LOW  = "#93c5fd"
C_CELL_AVG  = "#1d4ed8"
C_MOS_HIGH  = "#f97316"
C_MOS_AVG   = "#fdba74"
C_BMS_HIGH  = "#10b981"
C_BMS_AVG   = "#34d399"
C_BMS_LOW   = "#6ee7b7"
C_AMBIENT   = "#9ca3af"
C_DELTA     = "#a78bfa"

def fmt(v, d=1, fallback="—"):
    if v is None or (isinstance(v, float) and np.isnan(v)): return fallback
    return f"{v:.{d}f}"

def base_layout(height=320, xtitle="Time", ytitle="Temperature (°C)"):
    return dict(
        template="plotly_dark", paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
        height=height, xaxis_title=xtitle, yaxis_title=ytitle,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified", font=dict(family="DM Sans"),
        margin=dict(l=55, r=55, t=35, b=50),
    )

# ── New-format pre-processor ──────────────────────────────────────────────────
def preprocess_new_format(df):
    """
    Detect and transform the new datalogger CSV into the app's canonical schema.

    New format is identified by the presence of max_temp, min_temp, temp_1.
    Computed columns:
      - Average_Single_Cell_Temp  = mean(temp_1 … temp_N)
      - MOSFET_Average_Temp       = mean(inverter_temperature_1, inverter_2_temperature_1)
    Direct renames:
      max_temp               → Highest_Single_Cell_Temp
      min_temp               → Lowest_Single_Cell_Temp
      inverter_temperature_1 → MOSFET_Highest_Temp
      inverter_fault_status  → Alarm_Single_Core_High_Temp
      inverter_2_fault_status→ Alarm_MOSFET_Overtemp

    Returns (processed_df, was_new_format: bool).
    """
    df = df.dropna(how='all').reset_index(drop=True)

    if not {'max_temp', 'min_temp', 'temp_1'}.issubset(df.columns):
        return df, False

    # Compute average cell temp from individual sensor columns (temp_1, temp_2, …)
    temp_sensor_cols = sorted(
        [c for c in df.columns if c.startswith('temp_') and c[5:].isdigit()],
        key=lambda x: int(x[5:])
    )
    if temp_sensor_cols:
        df[COL_CELL_AVG] = (
            df[temp_sensor_cols].apply(pd.to_numeric, errors='coerce').mean(axis=1)
        )

    # Compute average MOSFET-proxy temp from both inverters
    inv_cols = [c for c in ['inverter_temperature_1', 'inverter_2_temperature_1']
                if c in df.columns]
    if inv_cols:
        df[COL_MOSFET_AVG] = (
            df[inv_cols].apply(pd.to_numeric, errors='coerce').mean(axis=1)
        )

    # Direct column renames
    # Note: inverter_fault_status / inverter_2_fault_status are charger status codes,
    # not battery thermal alarms — do NOT map them to COL_ALARM_*.
    rename = {
        'max_temp':               COL_CELL_HIGH,
        'min_temp':               COL_CELL_LOW,
        'inverter_temperature_1': COL_MOSFET_MAX,
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    # Detect ambient temp: any column not accounted for by the standard new-format set
    # maps to COL_AMBIENT. Convention: the onboard ambient sensor will be appended as
    # the last column once available; until then this block is a no-op.
    _known = {
        'timestamp', 'soc', 'max_cell_voltage', 'max_cell_position',
        'min_cell_voltage', 'min_cell_position', 'cell_voltage_diff',
        'max_temp_position', 'min_temp_position', 'temp_diff',
        'inverter_fault_status', 'inverter_2_fault_status',
        'inverter_2_temperature_1',
        'inverter_vin', 'inverter_vout', 'inverter_iout',
        'inverter_fan_speed_1', 'inverter_fan_speed_2',
        'inverter_2_vin', 'inverter_2_vout', 'inverter_2_iout',
        'inverter_2_fan_speed_1', 'inverter_2_fan_speed_2',
        COL_CELL_HIGH, COL_CELL_LOW, COL_CELL_AVG,
        COL_MOSFET_MAX, COL_MOSFET_AVG,
    }
    for _c in list(df.columns):
        if (_c.startswith('temp_') and _c[5:].isdigit()) or \
           (_c.startswith('cell_') and _c[5:].isdigit()):
            _known.add(_c)
    _extra = [c for c in df.columns if c not in _known]
    if len(_extra) == 1 and COL_AMBIENT not in df.columns:
        df = df.rename(columns={_extra[0]: COL_AMBIENT})

    return df, True

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔋 Battery Thermal\nAnalyzer")
    st.markdown("---")

    st.markdown('<div class="sec-hdr">Safety Overrides</div>', unsafe_allow_html=True)
    override_cell   = st.number_input("Peak cell override (°C)",   value=60.0, step=1.0,
        help="Score → 0 if peak cell reaches this. 60°C = SEI breakdown limit.")
    override_mosfet = st.number_input("Peak MOSFET override (°C)", value=85.0, step=1.0,
        help="Score → 0 if peak MOSFET reaches this.")
    warn_cell       = st.number_input("Cell temp warning (°C)",    value=55.0, step=1.0,
        help="Amber warning on metric card. From battery datasheet.")

    st.markdown('<div class="sec-hdr">Ambient ΔT Limit</div>', unsafe_allow_html=True)
    max_amb_delta   = st.number_input("Max cell−ambient ΔT (°C)",  value=25.0, step=1.0,
        help="Used for reference line on chart only.")

    st.markdown('<div class="sec-hdr">Pack Info</div>', unsafe_allow_html=True)
    pack_id   = st.text_input("Pack / Unit ID",       placeholder="e.g. PACK-001")
    test_note = st.text_input("Test note / tags (optional)", placeholder="e.g. fan_v2 1C cooling_mod baseline")

    st.markdown("---")
    compare_enabled = st.checkbox("Overlay previous run on chart", value=True)

thresholds = {
    "override_peak_cell":   override_cell,
    "override_peak_mosfet": override_mosfet,
    "warn_cell":            warn_cell,
    "max_ambient_delta":    max_amb_delta,
    "dose_threshold":       40.0,
}

# ── Column mapper helper ──────────────────────────────────────────────────────
def build_df(df_raw):
    """Remap columns based on stored session state selectboxes."""
    df = df_raw.copy()
    mapping = {
        "map_time":    (None, None),
        "map_ch":      (COL_CELL_HIGH,  None),
        "map_cl":      (COL_CELL_LOW,   None),
        "map_ca":      (COL_CELL_AVG,   None),
        "map_mh":      (COL_MOSFET_MAX, None),
        "map_ma":      (COL_MOSFET_AVG, None),
        "map_amb":     (COL_AMBIENT,    None),
        "map_bh":      (COL_BMS_HIGH,   None),
        "map_ba":      (COL_BMS_AVG,    None),
        "map_bl":      (COL_BMS_LOW,    None),
        "map_almc":    (COL_ALARM_CELL, None),
        "map_almm":    (COL_ALARM_MOS,  None),
    }
    for key, (target, _) in mapping.items():
        src = st.session_state.get(key)
        if src and src != "— none —" and target and src in df.columns and src != target:
            df = df.rename(columns={src: target})
    return df

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_main, tab_compare, tab_docs = st.tabs(["📊  Analyzer", "🔍  Compare Runs", "📖  Scoring Guide"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — DOCS  (rendered first: st.stop() in other tabs would blank this)
# ════════════════════════════════════════════════════════════════════════════
with tab_docs:
    _docs_path = os.path.join(os.path.dirname(__file__), "docs.md")
    if os.path.exists(_docs_path):
        st.markdown(open(_docs_path, encoding="utf-8").read())
    else:
        st.warning("docs.md not found — expected alongside app.py.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — COMPARE RUNS  (rendered before tab_main: st.stop() in tab_main would blank this)
# ════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.title("Compare Runs")
    st.markdown("Filter saved runs from the database and compare them side-by-side.")

    all_ids = get_pack_ids(DB_PATH)
    if not all_ids:
        st.info("No saved runs yet. Upload a CSV in the Analyzer tab and click Save.")
    else:
        # ── Filter panel ─────────────────────────────────────────────────────
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            sel_packs = st.multiselect("Pack ID(s)", all_ids, default=all_ids)
        with fc2:
            verdict_opts = ["PASS","CAUTION","FAIL"]
            sel_verdicts = st.multiselect("Verdict", verdict_opts, default=verdict_opts)
        with fc3:
            score_min, score_max = st.slider("Score range", 0, 100, (0, 100))
        with fc4:
            max_runs = st.number_input("Max runs to show", value=20, min_value=1, max_value=100)

        fk1, fk2 = st.columns([3, 1])
        with fk1:
            note_kw = st.text_input(
                "Search notes / tags",
                placeholder="e.g. fan_v2   or   cooling_mod   or   baseline  (space = AND, comma = OR)",
            )
        with fk2:
            kw_mode = st.radio("Match mode", ["AND", "OR"], horizontal=True)

        # Fetch and filter
        all_runs = []
        for pid in (sel_packs if sel_packs else all_ids):
            all_runs.extend(get_all_runs(DB_PATH, pid))

        df_runs = pd.DataFrame(all_runs) if all_runs else pd.DataFrame()

        if df_runs.empty:
            st.info("No runs match the current filters.")
        else:
            if "verdict" in df_runs.columns:
                df_runs = df_runs[df_runs["verdict"].isin(sel_verdicts)]
            if "score" in df_runs.columns:
                df_runs = df_runs[(df_runs["score"] >= score_min) & (df_runs["score"] <= score_max)]

            if note_kw.strip() and "note" in df_runs.columns:
                if "," in note_kw:
                    terms = [t.strip() for t in note_kw.split(",") if t.strip()]
                    mask = df_runs["note"].fillna("").str.contains("|".join(terms), case=False, regex=True)
                else:
                    terms = note_kw.split()
                    if kw_mode == "AND":
                        mask = pd.Series([True] * len(df_runs), index=df_runs.index)
                        for t in terms:
                            mask &= df_runs["note"].fillna("").str.contains(t, case=False, regex=False)
                    else:
                        mask = df_runs["note"].fillna("").str.contains("|".join(terms), case=False, regex=True)
                df_runs = df_runs[mask]

            df_runs = df_runs.head(max_runs).reset_index(drop=True)

            if df_runs.empty:
                st.info("No runs match the current filters.")
            else:
                st.markdown(f"**{len(df_runs)} run(s) matched**")

                # ── Selection table ───────────────────────────────────────────
                disp_cols = [c for c in ["pack_id","timestamp","score","verdict","ss_value",
                    "max_delta","max_rise_cs","max_mosfet_delta","peak_cell","mosfet_peak",
                    "alarm_cell","note"] if c in df_runs.columns]
                col_rename = {
                    "pack_id":"Pack","timestamp":"Timestamp","score":"Score","verdict":"Verdict",
                    "ss_value":"SS Temp","max_delta":"Max ΔT","max_rise_cs":"Rise (°C/s)",
                    "max_mosfet_delta":"MOSFET ΔT","peak_cell":"Peak Cell",
                    "mosfet_peak":"Peak MOSFET","alarm_cell":"Alarm","note":"Note"
                }

                df_display = df_runs[disp_cols].rename(columns=col_rename).copy()
                df_display.insert(0, "Select", False)

                edited = st.data_editor(df_display, use_container_width=True, hide_index=True,
                                        column_config={"Select": st.column_config.CheckboxColumn("Select")},
                                        disabled=[c for c in df_display.columns if c != "Select"])

                selected_idx = edited[edited["Select"]].index.tolist()

                if not selected_idx:
                    st.caption("☝️  Check rows above to compare up to 5 runs.")
                else:
                    if len(selected_idx) > 5:
                        st.warning("Select up to 5 runs for comparison.")
                        selected_idx = selected_idx[:5]

                    selected_runs = df_runs.iloc[selected_idx].reset_index(drop=True)

                    # ── Overlay chart ─────────────────────────────────────────
                    st.markdown("---")
                    st.markdown("### Temperature Overlay — Highest Cell Temp")
                    COMPARE_COLORS = ["#3b82f6","#f97316","#10b981","#8b5cf6","#ef4444"]

                    fig_cmp = go.Figure()
                    for i, (_, row) in enumerate(selected_runs.iterrows()):
                        run_df, run_tc = get_run_by_id(DB_PATH, row["id"])
                        if run_df is None or COL_CELL_HIGH not in run_df.columns:
                            continue
                        try:
                            rx = pd.to_datetime(run_df[run_tc], dayfirst=True)
                            run_df["_elapsed_min"] = (rx - rx.iloc[0]).dt.total_seconds() / 60.0
                        except Exception:
                            run_df["_elapsed_min"] = _parse_timestamps(run_df[run_tc]) / 60.0

                        lbl = f"{row.get('pack_id','?')} · {str(row.get('timestamp',''))[:16]} · {row.get('verdict','?')} · {int(row.get('score',0))}"
                        fig_cmp.add_trace(go.Scatter(
                            x=run_df["_elapsed_min"], y=run_df[COL_CELL_HIGH],
                            name=lbl, line=dict(color=COMPARE_COLORS[i % 5], width=2),
                            hovertemplate=f"<b>{lbl}</b><br>Elapsed: %{{x:.1f}} min<br>T: %{{y:.2f}}°C<extra></extra>"
                        ))
                        if COL_CELL_LOW in run_df.columns:
                            fig_cmp.add_trace(go.Scatter(
                                x=run_df["_elapsed_min"], y=run_df[COL_CELL_LOW],
                                name=f"Low ({row.get('pack_id','?')})",
                                line=dict(color=COMPARE_COLORS[i % 5], width=1, dash="dot"),
                                opacity=0.4, showlegend=False,
                                hovertemplate=f"Cell Low<br>T: %{{y:.2f}}°C<extra></extra>"
                            ))

                    fig_cmp.add_hline(y=warn_cell, line_dash="dash", line_color="#f59e0b",
                                      annotation_text=f"Warn {warn_cell}°C")
                    fig_cmp.add_hline(y=override_cell, line_dash="dash", line_color="#ef4444",
                                      annotation_text=f"Override {override_cell}°C")
                    fig_cmp.update_layout(**base_layout(height=420, xtitle="Elapsed time (min)", ytitle="Temperature (°C)"))
                    st.plotly_chart(fig_cmp, use_container_width=True)

                    # ── Side-by-side metrics table ────────────────────────────
                    st.markdown("### Metrics Comparison")

                    metric_rows = {
                        "Score":              "score",
                        "Verdict":            "verdict",
                        "SS Cell Temp (°C)":  "ss_value",
                        "Amb → Cell ΔT (°C)": "max_amb_delta",
                        "Max Cell ΔT (°C)":   "max_delta",
                        "Max Rise (°C/s)":    "max_rise_cs",
                        "Max MOSFET ΔT (°C)": "max_mosfet_delta",
                        "Peak Cell (°C)":     "peak_cell",
                        "Peak MOSFET (°C)":   "mosfet_peak",
                        "Thermal Dose":       "thermal_dose",
                        "Alarm":              "alarm_cell",
                        "Note":               "note",
                    }

                    compare_table = {"Metric": list(metric_rows.keys())}
                    best_score = selected_runs["score"].max() if "score" in selected_runs.columns else None

                    for _, row in selected_runs.iterrows():
                        col_hdr = f"{row.get('pack_id','?')} · {str(row.get('timestamp',''))[:16]}"
                        vals = []
                        for label, db_col in metric_rows.items():
                            v = row.get(db_col, "—")
                            if v is None or (isinstance(v, float) and np.isnan(v)):
                                vals.append("—")
                            elif isinstance(v, float):
                                vals.append(f"{v:.2f}")
                            else:
                                vals.append(str(v))
                        compare_table[col_hdr] = vals

                    st.dataframe(pd.DataFrame(compare_table).set_index("Metric"),
                                 use_container_width=True)

                    if best_score and len(selected_runs) > 1:
                        st.markdown("**Score delta vs best run in selection:**")
                        delta_data = {"Pack · Timestamp": [], "Score": [], "Delta vs Best": []}
                        for _, row in selected_runs.iterrows():
                            s = row.get("score", 0)
                            delta_data["Pack · Timestamp"].append(
                                f"{row.get('pack_id','?')} · {str(row.get('timestamp',''))[:16]}")
                            delta_data["Score"].append(int(s))
                            delta_data["Delta vs Best"].append(f"{int(s - best_score):+d}")
                        st.dataframe(pd.DataFrame(delta_data), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — ANALYZER
# ════════════════════════════════════════════════════════════════════════════
with tab_main:
    st.title("Battery Thermal Analyzer")
    st.markdown("Upload a CSV export from your battery datalogger.")

    uploaded = st.file_uploader("Drop your CSV here", type=["csv"], key="main_upload")

    if not uploaded:
        st.markdown("""
        <div style="text-align:center;padding:50px 0;color:#6b7280">
            <div style="font-size:56px">🔋</div>
            <div style="font-size:18px;font-family:'Space Mono',monospace;
                        margin-top:14px;color:#9ca3af">Upload a CSV to begin</div>
            <div style="margin-top:8px;font-size:12px;color:#4b5563">
                New format: timestamp · max_temp · min_temp · temp_1…temp_6 · inverter_temperature_1/2
                <br>Old format: Timestamp · Highest/Lowest/Average_Single_Cell_Temp ·
                MOSFET_Highest/Average_Temp · Ambient_Temp · BMS_Temp_* · Alarm columns
            </div>
        </div>""", unsafe_allow_html=True)
        if pack_id:
            prev = get_all_runs(DB_PATH, pack_id)
            if prev: st.dataframe(pd.DataFrame(prev), use_container_width=True, hide_index=True)
        st.stop()

    try:
        df_raw = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}"); st.stop()

    df_raw, is_new_format = preprocess_new_format(df_raw)
    if is_new_format:
        _amb_note = (
            "Ambient temperature column auto-detected and mapped."
            if COL_AMBIENT in df_raw.columns
            else "No ambient sensor column found — Ambient ΔT metric will be skipped."
        )
        st.info(
            "**New datalogger format detected** — columns auto-mapped. "
            "Inverter temperatures used as MOSFET-proxy readings. "
            f"{_amb_note} "
            "Alarm columns are not mapped for this format (no battery thermal alarm signals present)."
        )

    # Auto-detect time column
    time_col = df_raw.columns[0]
    for c in df_raw.columns:
        if any(k in c.lower() for k in ["time","timestamp","date","elapsed"]):
            time_col = c; break

    # Column mapper
    with st.expander("⚙️  Column mapping (auto-detected — adjust if needed)"):
        all_c    = list(df_raw.columns)
        none_opt = ["— none —"]
        def pick(label, target_col, key, required=False):
            opts = all_c if required else (none_opt + all_c)
            default = target_col if target_col in all_c else (all_c[0] if required else "— none —")
            idx = opts.index(default) if default in opts else 0
            return st.selectbox(label, opts, index=idx, key=key)

        c1, c2 = st.columns(2)
        with c1:
            time_col    = pick("Timestamp column *",           time_col,      "map_time", True)
            col_ch      = pick("Highest Single Cell Temp *",   COL_CELL_HIGH, "map_ch",   True)
            col_cl      = pick("Lowest Single Cell Temp",      COL_CELL_LOW,  "map_cl")
            col_ca      = pick("Average Single Cell Temp",     COL_CELL_AVG,  "map_ca")
            col_mh      = pick("MOSFET Highest Temp",          COL_MOSFET_MAX,"map_mh")
            col_ma      = pick("MOSFET Average Temp",          COL_MOSFET_AVG,"map_ma")
        with c2:
            col_amb     = pick("Ambient Temp",                 COL_AMBIENT,   "map_amb")
            col_bh      = pick("BMS Temp Highest",             COL_BMS_HIGH,  "map_bh")
            col_ba      = pick("BMS Temp Average",             COL_BMS_AVG,   "map_ba")
            col_bl      = pick("BMS Temp Lowest",              COL_BMS_LOW,   "map_bl")
            col_almc    = pick("Alarm: Single Core High Temp", COL_ALARM_CELL,"map_almc")
            col_almm    = pick("Alarm: MOSFET Overtemp",       COL_ALARM_MOS, "map_almm")

    # Apply remapping
    df = df_raw.copy()
    for src, tgt in [(col_ch, COL_CELL_HIGH),(col_cl, COL_CELL_LOW),(col_ca, COL_CELL_AVG),
                     (col_mh, COL_MOSFET_MAX),(col_ma, COL_MOSFET_AVG),(col_amb, COL_AMBIENT),
                     (col_bh, COL_BMS_HIGH),(col_ba, COL_BMS_AVG),(col_bl, COL_BMS_LOW),
                     (col_almc, COL_ALARM_CELL),(col_almm, COL_ALARM_MOS)]:
        if src and src != "— none —" and src in df.columns and src != tgt:
            df = df.rename(columns={src: tgt})
        elif (not src or src == "— none —") and tgt in df.columns:
            # User explicitly cleared this channel — drop the canonical column so the
            # scorer treats it as absent rather than reading stale pre-renamed data.
            df = df.drop(columns=[tgt])

    for c in [COL_CELL_HIGH,COL_CELL_LOW,COL_CELL_AVG,
              COL_MOSFET_MAX,COL_MOSFET_AVG,COL_AMBIENT,
              COL_BMS_HIGH,COL_BMS_AVG,COL_BMS_LOW]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if COL_CELL_HIGH in df.columns:
        df = df.dropna(subset=[COL_CELL_HIGH])

    present = [c for c in [COL_CELL_HIGH,COL_CELL_LOW,COL_CELL_AVG,
               COL_MOSFET_MAX,COL_MOSFET_AVG,COL_AMBIENT,
               COL_BMS_HIGH,COL_BMS_AVG,COL_BMS_LOW,
               COL_ALARM_CELL,COL_ALARM_MOS] if c in df.columns]
    st.success(f"✓ {len(df):,} rows  |  detected: {', '.join(present)}")

    # ── Compute ───────────────────────────────────────────────────────────────
    metrics  = compute_metrics(df, time_col, thresholds)
    score, breakdown = score_run(metrics, thresholds)

    alarm_cell   = metrics["alarm_cell"]
    alarm_mosfet = metrics["alarm_mosfet"]
    any_alarm    = metrics["any_alarm"]

    verdict     = "FAIL" if score < 50 else ("PASS" if score >= 75 else "CAUTION")
    if any_alarm or score == 0: verdict = "FAIL"
    sc_cls      = "sc-fail" if verdict == "FAIL" else ("sc-pass" if verdict == "PASS" else "sc-warn")
    v_cls       = "vfail"   if verdict == "FAIL" else ("vpass"   if verdict == "PASS" else "vwarn")

    # Build x-axis from timestamps
    try:
        x_axis  = pd.to_datetime(df[time_col], dayfirst=True)
        x_label = "Time"
    except Exception:
        x_axis  = metrics["_time_min"]
        x_label = "Elapsed (min)"

    # ── Alarm banners ─────────────────────────────────────────────────────────
    if alarm_cell:
        st.markdown('<div class="alarm-banner">⚠️ CELL OVER-TEMPERATURE ALARM TRIGGERED'
                    '<br><span style="font-size:11px;color:#fca5a5">'
                    'Alarm_Single_Core_High_Temp = 1 → Score = 0 → FAIL</span></div>',
                    unsafe_allow_html=True)
    if alarm_mosfet:
        st.markdown('<div class="mosfet-banner">⚡ MOSFET Overtemperature alarm triggered '
                    '— diagnostic display only, does not affect score</div>',
                    unsafe_allow_html=True)

    # ── Score + Breakdown + Radar ─────────────────────────────────────────────
    st.markdown("---")
    col_sc, col_bd, col_radar = st.columns([1, 1.5, 1.5])

    with col_sc:
        st.markdown("### Score")
        st.markdown(f"""
        <div class="score-wrap">
          <div class="score-circle {sc_cls}">
            <div class="sc-num">{score}</div>
            <div class="sc-lbl">/ 100</div>
          </div>
          <div class="verdict {v_cls}">{verdict}</div>
        </div>""", unsafe_allow_html=True)
        st.caption("≥75 PASS · ≥50 CAUTION · <50 FAIL\nOverride or alarm → instant FAIL")

    with col_bd:
        st.markdown("### Breakdown")
        for name, val in breakdown.items():
            pts, mx = val["points"], val["max"]
            is_ov   = val.get("is_override", False)
            pct     = pts/mx if mx > 0 else 0
            clr     = "#ef4444" if is_ov else ("#22c55e" if pct>=0.8 else ("#f97316" if pct>=0.4 else "#ef4444"))
            st.markdown(
                f'<div class="bd-row"><div>'
                f'<div class="bd-name">{name}</div>'
                f'<div class="bd-detail">{val["detail"]}</div>'
                f'</div><div class="bd-pts" style="color:{clr}">{pts}/{mx}</div></div>',
                unsafe_allow_html=True)

    with col_radar:
        st.markdown("### Performance Radar")
        # 5 weighted metrics as % of their max weight
        bd_items = {k: v for k, v in breakdown.items() if not v.get("is_override")}
        if len(bd_items) == 5 and score > 0:
            labels = list(bd_items.keys())
            short  = ["SS Temp","Amb ΔT","Cell ΔT","Rise","MOSFET ΔT"]
            values = [v["points"]/v["max"]*100 for v in bd_items.values()]
            values_closed = values + [values[0]]
            angles = [i * 360/5 for i in range(5)] + [0]

            fig_r = go.Figure(go.Scatterpolar(
                r=values_closed, theta=short+[short[0]],
                fill="toself", fillcolor="rgba(59,130,246,0.18)",
                line=dict(color="#3b82f6", width=2),
                hovertemplate="%{theta}: %{r:.1f}%<extra></extra>"
            ))
            fig_r.update_layout(
                polar=dict(
                    bgcolor="#0f1117",
                    radialaxis=dict(visible=True, range=[0,100],
                                   tickfont=dict(size=9,color="#6b7280"),
                                   gridcolor="#2a2d3a",linecolor="#2a2d3a"),
                    angularaxis=dict(tickfont=dict(size=10,color="#9ca3af"),
                                     gridcolor="#2a2d3a",linecolor="#2a2d3a"),
                ),
                paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                height=280, margin=dict(l=40,r=40,t=30,b=30),
                font=dict(family="DM Sans"),
                showlegend=False,
            )
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.caption("Radar available after scoring.")

    # ── Metric cards ──────────────────────────────────────────────────────────
    st.markdown("---")

    def mc(col, label, value, unit, state="normal", sub=None, badge=None):
        badge_html = ""
        if badge == "extrap":
            badge_html = '<span class="mc-badge badge-extrap">EXTRAPOLATED</span>'
        elif badge == "display":
            badge_html = '<span class="mc-badge badge-display">DISPLAY</span>'
        elif badge == "alarm":
            badge_html = '<span class="mc-badge badge-alarm">ALARM</span>'
        val_cls  = "warn" if state=="warn" else ("amber" if state=="amber" else "")
        card_cls = state if state in ("warn","amber","ok","display") else "normal"
        sub_html = f'<div class="mc-sub">{sub}</div>' if sub else ""
        col.markdown(
            f'<div class="mc {card_cls}"><div class="mc-label">{label}{badge_html}</div>'
            f'<div class="mc-value {val_cls}">{value}<span class="mc-unit">{unit}</span></div>'
            f'{sub_html}</div>', unsafe_allow_html=True)

    # Weighted metric cards
    st.markdown('<div class="section-label">Weighted Metrics (contribute to score)</div>',
                unsafe_allow_html=True)
    r1 = st.columns(5)
    ss_val   = metrics.get("ss_value")
    ss_extrap = metrics.get("ss_extrapolated", False)
    mc(r1[0], "Steady-state Cell Temp",
       fmt(ss_val), "°C",
       state="warn" if (ss_val or 0) >= 55 else ("amber" if (ss_val or 0) >= 45 else "ok"),
       sub=metrics.get("ss_note",""),
       badge="extrap" if ss_extrap else None)

    amb_d = metrics.get("max_amb_delta")
    mc(r1[1], "Max Ambient → Cell ΔT",
       fmt(amb_d), "°C",
       state="warn" if (amb_d or 0) >= 25 else ("amber" if (amb_d or 0) >= 15 else "ok"),
       sub=f"ambient avg {fmt(metrics.get('ambient_avg'))}°C")

    max_d = metrics.get("max_delta")
    mc(r1[2], "Max Cell ΔT (Uniformity)",
       fmt(max_d, 2), "°C",
       state="warn" if (max_d or 0) >= 5 else ("amber" if (max_d or 0) >= 3 else "ok"),
       sub=f"avg {fmt(metrics.get('avg_delta'),2)}°C")

    rise = metrics.get("max_rise_cs")
    mc(r1[3], "Max Rise Rate (cells)",
       fmt(rise, 4), "°C/s",
       state="warn" if (rise or 0) >= 3.0 else ("amber" if (rise or 0) >= 2.0 else "ok"),
       sub="ideal ≤1.2°C/s · fail ≥3.0°C/s")

    mos_d = metrics.get("max_mosfet_delta")
    mc(r1[4], "Max MOSFET ΔT",
       fmt(mos_d), "°C",
       state="warn" if (mos_d or 0) >= 30 else ("amber" if (mos_d or 0) >= 20 else "ok"),
       sub=f"peak {fmt(metrics.get('mosfet_peak'))}°C · avg {fmt(metrics.get('mosfet_avg'))}°C"
       if metrics.get("mosfet_peak") else "no MOSFET data")

    # Display-only metric cards
    st.markdown('<div class="section-label">Safety &amp; Display Metrics (not scored)</div>',
                unsafe_allow_html=True)
    r2 = st.columns(6)

    tau_val = metrics.get("tau")
    mc(r2[0], "Thermal Time Constant",
       f"{tau_val} min" if tau_val else "—", "",
       state="display",
       sub="Cooling rate τ" if tau_val else "No cool-down detected",
       badge="display")

    peak_c = metrics.get("peak_cell")
    peak_state = "warn" if (peak_c or 0) >= override_cell else ("amber" if (peak_c or 0) >= warn_cell else "display")
    mc(r2[1], "Peak Cell Temp",
       fmt(peak_c), "°C",
       state=peak_state,
       sub=f"override ≥{override_cell}°C · warn ≥{warn_cell}°C",
       badge="display")

    peak_m = metrics.get("mosfet_peak")
    mc(r2[2], "Peak MOSFET Temp",
       fmt(peak_m) if peak_m else "—", "°C",
       state="warn" if (peak_m or 0) >= override_mosfet else ("amber" if (peak_m or 0) >= 70 else "display"),
       sub=f"override ≥{override_mosfet}°C",
       badge="display")

    accel = metrics.get("max_accel")
    mc(r2[3], "Max Rise Acceleration",
       fmt(accel, 4) if accel else "—", "°C/s²",
       state="warn" if (accel or 0) >= 5.0 else "display",
       sub="runaway signal ≥5.0°C/s²",
       badge="display")

    dose = metrics.get("thermal_dose")
    mc(r2[4], "Thermal Dose",
       fmt(dose), "°C·min",
       state="amber" if (dose or 0) > 20 else "display",
       sub=f"above {thresholds['dose_threshold']}°C",
       badge="display")

    alarm_txt   = "TRIGGERED" if any_alarm else "None"
    alarm_state = "warn" if any_alarm else "display"
    alarm_badge = "alarm" if any_alarm else "display"
    mc(r2[5], "Any Alarm Triggered",
       alarm_txt, "",
       state=alarm_state,
       sub="Cell alarm → score=0" if alarm_cell else
           ("MOSFET alarm → display only" if alarm_mosfet else "All clear"),
       badge=alarm_badge)

    # ══════════════════════════════════════════════════════════════════════════
    # COMBINED TEMPERATURE CHART
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### Temperature Overview")

    prev_df, prev_tc = None, None
    prev_label       = None
    if compare_enabled and pack_id:
        prev_runs = get_all_runs(DB_PATH, pack_id)
        if prev_runs:
            prev_df, prev_tc = get_run_by_id(DB_PATH, prev_runs[0]["id"])
            prev_label = f"Prev {prev_runs[0]['timestamp'][:10]}"
            try:
                prev_x = pd.to_datetime(prev_df[prev_tc], dayfirst=True)
            except Exception:
                prev_x = _parse_timestamps(prev_df[prev_tc]) / 60.0

    # Dual-axis: left = °C temps, right = Cell ΔT
    fig_main = make_subplots(specs=[[{"secondary_y": True}]])

    def add(col_name, label, color, width=2, dash="solid", opacity=1.0, secondary=False):
        if col_name in df.columns:
            fig_main.add_trace(go.Scatter(
                x=x_axis, y=df[col_name], name=label,
                line=dict(color=color, width=width, dash=dash),
                opacity=opacity,
                hovertemplate=f"<b>{label}</b><br>%{{y:.2f}}°C<extra></extra>"
            ), secondary_y=secondary)

    # Cell spread fill
    if COL_CELL_HIGH in df.columns and COL_CELL_LOW in df.columns:
        fig_main.add_trace(go.Scatter(
            x=pd.concat([x_axis, x_axis[::-1]]),
            y=pd.concat([df[COL_CELL_HIGH], df[COL_CELL_LOW][::-1]]),
            fill="toself", fillcolor="rgba(59,130,246,0.07)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Cell Spread", hoverinfo="skip", showlegend=True
        ), secondary_y=False)

    add(COL_CELL_HIGH, "Cell Highest",  C_CELL_HIGH, 2.5)
    add(COL_CELL_LOW,  "Cell Lowest",   C_CELL_LOW,  1.5)
    add(COL_CELL_AVG,  "Cell Average",  C_CELL_AVG,  1.5, "dash")
    add(COL_MOSFET_MAX,"MOSFET Highest",C_MOS_HIGH,  2.0)
    add(COL_MOSFET_AVG,"MOSFET Average",C_MOS_AVG,   1.5, "dash")
    add(COL_BMS_HIGH,  "BMS Highest",   C_BMS_HIGH,  1.5)
    add(COL_BMS_AVG,   "BMS Average",   C_BMS_AVG,   1.2, "dash")
    add(COL_BMS_LOW,   "BMS Lowest",    C_BMS_LOW,   1.0, "dot")
    add(COL_AMBIENT,   "Ambient",       C_AMBIENT,   1.5, "longdash")

    # Cell ΔT on secondary axis
    delta_s = metrics["_delta_series"]
    if delta_s is not None and len(delta_s) > 0:
        fig_main.add_trace(go.Scatter(
            x=x_axis, y=delta_s, name="Cell ΔT (right axis)",
            line=dict(color=C_DELTA, width=1.5, dash="dot"),
            hovertemplate="Cell ΔT: %{y:.2f}°C<extra></extra>",
            visible="legendonly",
        ), secondary_y=True)

    # Previous run overlay — highest cell only
    if prev_df is not None and COL_CELL_HIGH in prev_df.columns:
        try:
            prev_x = pd.to_datetime(prev_df[prev_tc], dayfirst=True)
        except Exception:
            prev_x = _parse_timestamps(prev_df[prev_tc]) / 60.0
        fig_main.add_trace(go.Scatter(
            x=prev_x, y=prev_df[COL_CELL_HIGH],
            name=f"Cell High ({prev_label})",
            line=dict(color=C_CELL_HIGH, width=1.5, dash="dot"),
            opacity=0.35,
        ), secondary_y=False)

    # Reference lines
    fig_main.add_hline(y=warn_cell, line_dash="dash", line_color="#f59e0b",
                       annotation_text=f"Cell warn {warn_cell}°C",
                       annotation_position="top left")
    fig_main.add_hline(y=override_cell, line_dash="dash", line_color="#ef4444",
                       annotation_text=f"Cell override {override_cell}°C",
                       annotation_position="top right")
    fig_main.add_hline(y=override_mosfet, line_dash="dot", line_color=C_MOS_HIGH,
                       annotation_text=f"MOSFET override {override_mosfet}°C",
                       annotation_position="bottom right")

    layout = base_layout(height=800, xtitle=x_label)
    layout.update({
        "yaxis":  dict(title="Temperature (°C)", gridcolor="#1f2130"),
        "yaxis2": dict(title="Cell ΔT (°C)", gridcolor="#1f2130",
                       overlaying="y", side="right",
                       tickfont=dict(color=C_DELTA),
                       title_font=dict(color=C_DELTA)),
        "legend": dict(orientation="h", yanchor="bottom", y=1.01,
                       xanchor="right", x=1, font=dict(size=11)),
    })
    fig_main.update_layout(**layout)
    st.plotly_chart(fig_main, use_container_width=True)

    # ── Historical score trend ────────────────────────────────────────────────
    if pack_id:
        all_prev = get_all_runs(DB_PATH, pack_id)
        if all_prev:
            st.markdown("---")
            st.markdown(f"### Run History — {pack_id}")
            hdf = pd.DataFrame(all_prev)

            fig_h = go.Figure()
            alarm_m = hdf.get("alarm_cell", pd.Series([0]*len(hdf))).astype(bool)
            fig_h.add_trace(go.Scatter(
                x=hdf["timestamp"], y=hdf["score"],
                mode="lines+markers",
                line=dict(color="#3b82f6", width=2),
                marker=dict(size=9, color=hdf["score"],
                            colorscale=[[0,"#ef4444"],[0.5,"#f97316"],[1,"#22c55e"]],
                            cmin=0, cmax=100,
                            symbol=["x" if a else "circle" for a in alarm_m]),
                hovertemplate="<b>%{x}</b><br>Score: %{y}<extra></extra>"
            ))
            fig_h.add_hrect(y0=75,y1=100,fillcolor="rgba(34,197,94,0.05)",line_width=0)
            fig_h.add_hrect(y0=50,y1=75, fillcolor="rgba(249,115,22,0.05)",line_width=0)
            fig_h.add_hrect(y0=0, y1=50, fillcolor="rgba(239,68,68,0.05)", line_width=0)
            fig_h.update_layout(**base_layout(height=220, xtitle="", ytitle="Score"))
            fig_h.update_layout(yaxis=dict(range=[0,100]))
            st.plotly_chart(fig_h, use_container_width=True)

            cols_show = [c for c in ["timestamp","score","verdict","ss_value","max_delta",
                "max_rise_cs","max_mosfet_delta","peak_cell","mosfet_peak",
                "alarm_cell","alarm_mosfet","note"] if c in hdf.columns]
            rename = {"timestamp":"Timestamp","score":"Score","verdict":"Verdict",
                "ss_value":"SS Temp","max_delta":"Max ΔT","max_rise_cs":"Rise (°C/s)",
                "max_mosfet_delta":"MOSFET ΔT","peak_cell":"Peak Cell",
                "mosfet_peak":"Peak MOSFET","alarm_cell":"Cell Alarm",
                "alarm_mosfet":"MOS Alarm","note":"Note"}
            st.dataframe(hdf[cols_show].rename(columns=rename),
                         use_container_width=True, hide_index=True)

    # ── Save ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("💾  Save this run to database"):
        if not pack_id:
            st.warning("Enter a Pack / Unit ID in the sidebar first.")
        else:
            save_run(DB_PATH, pack_id, metrics, score, verdict, df, time_col, test_note)
            st.success(f"✓ Saved — {pack_id}  |  Score: {score}  |  {verdict}")


# ════════════════════════════════════════════════════════════════════════════
