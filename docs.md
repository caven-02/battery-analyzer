# Battery Thermal Analyzer — Scoring & Reference Guide

## What this app is for

This tool processes temperature telemetry exported from battery pack test equipment and produces:

- **Visual charts** of all temperature channels grouped on a single overview graph
- **A 0–100 thermal performance score** with a PASS / CAUTION / FAIL verdict
- **11 metric cards** split into weighted (scored) and safety/display-only categories
- **A run history database** for tracking the same pack across multiple test cycles
- **A Compare tab** for side-by-side analysis of multiple runs

**Primary users:** battery hardware engineers validating pack thermal design, running characterisation cycles, or performing incoming quality checks on prototype or production packs.

---

## Expected CSV format

The app auto-detects which format is in use based on the presence of `max_temp`, `min_temp`, and `temp_1` columns.

### New datalogger format (auto-detected)

Timestamp format: ISO 8601 with timezone offset — `2026-06-10T03:45:10.849+00:00`

| Column | Description | Mapped to |
|---|---|---|
| `timestamp` | ISO 8601 timestamp with UTC offset | Time axis |
| `step_name` | Charge/discharge step label | Display only |
| `soc` | State of charge (%) | Display only |
| `max_temp` | Peak cell temperature across all modules | Highest cell temp |
| `min_temp` | Lowest cell temperature across all modules | Lowest cell temp |
| `temp_1` … `temp_N` | Individual cell temperature sensors | Averaged → mean cell temp |
| `max_temp_position` | Position index of hottest cell | Display only |
| `min_temp_position` | Position index of coldest cell | Display only |
| `temp_diff` | max_temp − min_temp (raw) | Display only |
| `max_cell_voltage` | Peak cell voltage | Display only |
| `min_cell_voltage` | Minimum cell voltage | Display only |
| `max_cell_position` | Position index of highest-voltage cell | Display only |
| `min_cell_position` | Position index of lowest-voltage cell | Display only |
| `cell_voltage_diff` | Voltage spread across cells | Display only |
| `cell_01_voltage` … `cell_N_voltage` | Individual cell voltages | Display only |
| `inverter_temperature_1` | Inverter 1 temperature | MOSFET highest temp |
| `inverter_2_temperature_1` | Inverter 2 temperature | Averaged with inverter 1 → MOSFET mean temp |
| `inverter_vin/vout/iout` | Inverter 1 electrical readings | Display only |
| `inverter_2_vin/vout/iout` | Inverter 2 electrical readings | Display only |
| `inverter_fan_speed_1/2` | Inverter 1 fan speeds | Display only |
| `inverter_2_fan_speed_1/2` | Inverter 2 fan speeds | Display only |
| `inverter_fault_status` | Inverter 1 state register (64 = charging) | Not mapped — not a battery alarm |
| `inverter_2_fault_status` | Inverter 2 state register | Not mapped — not a battery alarm |
| *(last column, optional)* | Ambient temperature from onboard sensor | Ambient temp (when present) |

Alarm columns are not present in this format and do not affect scoring.

BMS temperature columns are not present in this format.

---

### Legacy format

Timestamp format: `dd/mm/yyyy HH:MM:SS`

| Column | Description |
|---|---|
| `Timestamp` | `dd/mm/yyyy HH:MM:SS` |
| `Highest_Single_Cell_Temp` | Peak cell temperature across all modules |
| `Lowest_Single_Cell_Temp` | Lowest cell temperature across all modules |
| `Average_Single_Cell_Temp` | Mean cell temperature |
| `MOSFET_Highest_Temp` | Peak MOSFET/FET temperature |
| `MOSFET_Average_Temp` | Mean MOSFET temperature |
| `Ambient_Temp` | Ambient air temperature at the pack |
| `BMS_Temp_Average` | BMS PCB average temperature |
| `BMS_Temp_Highest` | BMS PCB peak temperature |
| `BMS_Temp_Lowest` | BMS PCB minimum temperature |
| `Alarm_Single_Core_High_Temp` | Binary: 1 = over-temperature alarm |
| `Alarm_MOSFET_Overtemp` | Binary: 1 = MOSFET over-temperature alarm |

---

## Metric structure

Metrics are divided into two categories:

**Weighted metrics** contribute to the 0–100 score through a piecewise linear formula. They measure gradient thermal performance — how well the system is managing heat under load.

**Safety and display metrics** are shown on the dashboard for diagnostic context but do not contribute to the score. They either act as binary safety overrides (instant FAIL) or provide supplementary information.

---

## Scoring model

### General formula

For each weighted metric, a score component S_i is computed given a measured value x, maximum weight W_max, ideal threshold x_ideal, and failure threshold x_fail:

```
S_i(x) = W_max                                             for x <= x_ideal
S_i(x) = W_max - W_max * (x - x_ideal)/(x_fail - x_ideal) for x_ideal < x < x_fail
S_i(x) = 0                                                 for x >= x_fail
```

This means: full points when within the ideal window, linear decay toward zero as the value approaches the failure threshold, and zero once the threshold is reached or exceeded.

### Safety multiplier

```
Score = M_safety * (S_ss + S_amb + S_uni + S_rise + S_mos)
```

M_safety = 0 (instant FAIL) if any of:
- Peak cell temperature >= 60°C
- Peak MOSFET temperature >= 85°C
- Alarm_Single_Core_High_Temp = 1

M_safety = 1 otherwise.

---

## Weighted metrics (sum to 100 pts)

### Steady-state Cell Temperature — 20 pts

**Formula:** Mean of Average_Single_Cell_Temp during the final 10% of the run, if the slope is flat (< 0.002°C/s). If the pack is still rising at end of test, an asymptotic curve is fitted to extrapolate the equilibrium value. An EXTRAPOLATED badge is shown on the metric card when this occurs.

**Ideal:** <= 35°C (full 20 pts)
**Fail:** >= 55°C (0 pts)

**Why 20 pts:** Reflects the equilibrium operating point of the pack. The ideal operating window for Li-ion is under 35°C. Degradation becomes a serious concern above 55°C as SEI breakdown accelerates. Note: the weights for steady-state and ambient-to-cell delta together equal the uniformity weight (20 + 20 = 40), reflecting that both thermal environment and cooling quality jointly determine pack longevity.

### Max Ambient-to-Cell deltaT — 20 pts

**Formula:** max(Average_Single_Cell_Temp - Ambient_Temp) over the run.

**Ideal:** <= 10°C (full 20 pts)
**Fail:** >= 25°C (0 pts)

**Why 20 pts:** A delta of 10°C or less above ambient indicates excellent thermal shedding — the pack is efficiently rejecting heat to the environment. If the pack is running 25°C hotter than the ambient room, the cooling system is highly constrained and the pack will struggle under sustained load. Isolates system-generated heat from environmental variation.

### Max Cell deltaT (Uniformity) — 40 pts

**Formula:** max(Highest_Single_Cell_Temp - Lowest_Single_Cell_Temp) over the run.

**Ideal:** <= 2°C (full 40 pts)
**Fail:** >= 5°C (0 pts)

**Why 40 pts (highest weight):** This is the dominant longevity driver. A 2°C variance is exceptionally balanced design. Anything >= 5°C is considered a failure in modern BTMS design. Cells at different temperatures age at different rates — a hotter cell has lower internal resistance, draws more current proportionally, gets hotter still, and degrades faster, eventually bottlenecking the entire pack capacity. Keeping uniformity tight is the most impactful single design target.

### Max Rise Rate (cells) — 10 pts

**Formula:** max(d(Highest_Single_Cell_Temp) / dt) in °C/s, calculated on a 3-point median-smoothed signal to remove ADC jitter.

**Ideal:** <= 0.2°C/s (full 10 pts)
**Fail:** >= 1.0°C/s (0 pts)

**Why 10 pts (low weight):** A rise of 0.2°C/s is standard under heavy continuous load. Hitting 1.0°C/s means the cooling system has entirely lost control of I^2R ohmic heating. The weight is kept low because this metric is heavily affected by C-rate — it will naturally score worse at 1C than 0.5C. It should be used to compare runs at the same C-rate, not across different test profiles.

### Max MOSFET deltaT — 10 pts

**Formula:** max(MOSFET_Highest_Temp - MOSFET_Average_Temp) over the run.

**Ideal:** <= 10°C (full 10 pts)
**Fail:** >= 30°C (0 pts)

**Why 10 pts:** A delta of 10°C between the hottest and average FET is normal. A delta of 30°C indicates a massive localised hotspot — a failing component, a missing thermal pad, or a design flaw in the switching layout. Having this as a weighted metric rather than a display-only metric allows comparison of BMS thermal quality across different pack designs.

---

## Safety and display metrics (not scored)

### Thermal Time Constant (Cooling Rate) — display only

**Formula:** Fit T(t) = T_ambient + (T_peak - T_ambient) * exp(-t/tau) to the cool-down phase. Reports tau in minutes. Only available when a cool-down phase is detected (temperature falling after peak). Shows "No cool-down detected" if the run ends at peak temperature.

**Why display only:** Only measurable when the test protocol includes a deliberate rest phase after load removal. Cannot be fairly scored on runs that end at peak load. Future option: add to score weighting for validation workflows that include a cool-down protocol.

### Peak Cell Temp — display only, safety override

55°C: amber warning (from battery datasheet upper operating limit).
60°C: safety override — M_safety = 0, score forced to 0.

60°C is the universally recognised absolute upper safety limit for discharge. Above this, breakdown of the Solid Electrolyte Interphase (SEI) layer accelerates exponentially.

### Peak MOSFET Temp — display only, safety override

85°C: safety override — M_safety = 0, score forced to 0.

BMS will derate or trigger a cutoff warning between 70–75°C, with a hard shutdown at 80–85°C (check specific datasheet). Silicon MOSFETs have maximum junction temperatures of 150–175°C, but standard FR4 PCBs can delaminate above 130°C. 85°C provides a practical operating limit with thermal buffer.

### Max Rise Acceleration — display only

**Formula:** d^2(Highest_Single_Cell_Temp) / dt^2 in °C/s^2.

Warning threshold: >= 1.0°C/s^2.

Normal ohmic heating creates a relatively steady, linear rise. If the rate of rise begins to accelerate rapidly (crossing 1.0°C/s^2), the system is no longer heating from electrical resistance only — this may indicate the onset of internal exothermic chemical reactions.

### Thermal Dose — display only

**Formula:** integral of max(0, T_highest_cell - 40°C) dt over the run, in °C·min.

Battery degradation is cumulative. A pack that briefly spikes to 55°C is generally healthier than one that sits at 48°C for hours. Thermal dose captures time-integrated exposure and correlates with long-term State of Health degradation.

### Any Alarm Triggered — safety override

`Alarm_Single_Core_High_Temp = 1` → M_safety = 0, score = 0, FAIL.
`Alarm_MOSFET_Overtemp = 1` → displayed as amber warning, does not affect score.

---

## Threshold rationale

| Metric | Threshold | Basis |
|---|---|---|
| Peak Cell Temp warning | 55°C | Upper operating limit from battery datasheet |
| Peak Cell Temp override | 60°C | Universally recognised absolute discharge safety limit; SEI breakdown accelerates above this |
| Max Cell deltaT ideal | 2°C | Exceptional pack balance; minimises differential aging |
| Max Cell deltaT fail | 5°C | Upper limit in modern BTMS design; anything above indicates cooling imbalance |
| Peak MOSFET override | 85°C | BMS hard shutdown range; FR4 PCB thermal buffer limit |
| Max Rise ideal | 0.2°C/s | Standard under heavy continuous load |
| Max Rise fail | 1.0°C/s | Cooling has lost control of I^2R ohmic heating |
| Max Rise Accel warning | 1.0°C/s^2 | Rate of rise is itself accelerating — possible onset of exothermic reaction |

---

## Score verdict thresholds

| Score | Verdict |
|---|---|
| 75–100 | PASS — thermal system performing within design intent |
| 50–74 | CAUTION — marginal, investigate specific failing categories |
| 0–49 | FAIL — thermal system not meeting design requirements |
| 0 (override) | FAIL — safety override triggered, automatic disqualification |

---

## Phase roadmap

**Phase 1 (current):** Piecewise linear scoring, 5 weighted metrics, safety overrides, steady-state detection with extrapolation, combined temperature chart, Compare tab, thermal time constant diagnostic

**Phase 2:** Module-level hotspot tracking, run-to-run trend detection, charge vs discharge asymmetry, thermal time constant added to score for cool-down validation workflows, PDF report export

**Phase 3:** State of Health correlation tracking, Google Drive automatic CSV ingestion
