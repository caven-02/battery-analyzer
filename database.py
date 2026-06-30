"""
database.py — Battery Thermal Analyzer v4
"""
import sqlite3, json
import pandas as pd
from datetime import datetime

def init_db(db_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            pack_id             TEXT NOT NULL,
            timestamp           TEXT NOT NULL,
            score               REAL NOT NULL,
            verdict             TEXT NOT NULL,
            ss_value            REAL,
            ss_extrapolated     INTEGER DEFAULT 0,
            max_amb_delta       REAL,
            max_delta           REAL,
            max_rise_cs         REAL,
            max_mosfet_delta    REAL,
            peak_cell           REAL,
            mosfet_peak         REAL,
            max_accel           REAL,
            thermal_dose        REAL,
            tau                 REAL,
            alarm_cell          INTEGER DEFAULT 0,
            alarm_mosfet        INTEGER DEFAULT 0,
            duration_min        REAL,
            note                TEXT,
            raw_data_json       TEXT
        )
    """)
    # Upgrade path for old DBs
    existing = {r[1] for r in cur.execute("PRAGMA table_info(runs)")}
    upgrades = {
        "ss_value":"REAL","ss_extrapolated":"INTEGER DEFAULT 0",
        "max_amb_delta":"REAL","max_delta":"REAL","max_rise_cs":"REAL",
        "max_mosfet_delta":"REAL","peak_cell":"REAL","mosfet_peak":"REAL",
        "max_accel":"REAL","thermal_dose":"REAL","tau":"REAL",
        "alarm_cell":"INTEGER DEFAULT 0","alarm_mosfet":"INTEGER DEFAULT 0",
        "duration_min":"REAL",
    }
    for col, typ in upgrades.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE runs ADD COLUMN {col} {typ}")
    con.commit(); con.close()


def save_run(db_path, pack_id, metrics, score, verdict, df, time_col, note=""):
    con = sqlite3.connect(db_path)
    raw = df.to_dict(orient="list")
    raw["__time_col__"] = time_col
    cur = con.cursor()
    cur.execute("""
        INSERT INTO runs (
            pack_id, timestamp, score, verdict,
            ss_value, ss_extrapolated, max_amb_delta, max_delta,
            max_rise_cs, max_mosfet_delta, peak_cell, mosfet_peak,
            max_accel, thermal_dose, tau,
            alarm_cell, alarm_mosfet, duration_min, note, raw_data_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        pack_id,
        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        score, verdict,
        metrics.get("ss_value"), int(metrics.get("ss_extrapolated", False)),
        metrics.get("max_amb_delta"), metrics.get("max_delta"),
        metrics.get("max_rise_cs"), metrics.get("max_mosfet_delta"),
        metrics.get("peak_cell"), metrics.get("mosfet_peak"),
        metrics.get("max_accel"), metrics.get("thermal_dose"),
        metrics.get("tau"),
        int(metrics.get("alarm_cell", False)), int(metrics.get("alarm_mosfet", False)),
        metrics.get("duration_min"), note or "",
        json.dumps(raw),
    ))
    con.commit(); con.close()


def get_all_runs(db_path, pack_id=None):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    if pack_id:
        cur.execute("SELECT * FROM runs WHERE pack_id=? ORDER BY timestamp DESC", (pack_id,))
    else:
        cur.execute("SELECT * FROM runs ORDER BY timestamp DESC")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


def get_run_by_id(db_path, run_id):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT raw_data_json FROM runs WHERE id=?", (run_id,))
    row = cur.fetchone()
    con.close()
    if not row: return None, ""
    raw = json.loads(row[0])
    time_col = raw.pop("__time_col__")
    return pd.DataFrame(raw), time_col


def get_pack_ids(db_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT DISTINCT pack_id FROM runs ORDER BY pack_id")
    ids = [r[0] for r in cur.fetchall()]
    con.close()
    return ids
