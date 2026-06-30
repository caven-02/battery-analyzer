# 🔋 Battery Thermal Analyzer — Setup Guide
### For complete beginners. No experience needed.

---

## What you'll end up with

A browser-based app (runs on your own computer) where you:
- Drag and drop a CSV → see interactive temperature charts instantly
- Get a 0–100 score with PASS / CAUTION / FAIL
- Compare against previous runs of the same pack
- All data stored locally in a single file (no internet required)

---

## Step 1 — Install Python

Python is the programming language this app runs on. You only do this once.

1. Go to **https://www.python.org/downloads/**
2. Click the big yellow **"Download Python 3.x.x"** button
3. Run the installer
4. ⚠️ **IMPORTANT**: On the first screen of the installer, check the box that says **"Add Python to PATH"** before clicking Install

To verify it worked: open **Command Prompt** (Windows: press `Win+R`, type `cmd`, press Enter) and type:
```
python --version
```
You should see something like `Python 3.12.4`. If so, you're good.

---

## Step 2 — Download the app files

You should have received (or can download) a folder called `battery_analyzer` containing:
```
battery_analyzer/
├── app.py            ← the main app
├── scoring.py        ← scoring logic
├── database.py       ← data storage
├── sample_data.csv   ← test file to try first
└── SETUP_GUIDE.md    ← this file
```

Put this folder somewhere easy to find, like your **Desktop** or **Documents**.

---

## Step 3 — Install the required libraries

Open **Command Prompt** and type these commands one at a time, pressing Enter after each:

```
pip install streamlit
pip install pandas
pip install plotly
pip install numpy
```

Each one will show some download progress. Wait for it to finish before typing the next.

This also only needs to be done once.

---

## Step 4 — Run the app

In **Command Prompt**, navigate to your folder. For example if it's on your Desktop:
```
cd Desktop\battery_analyzer
```

Then start the app:
```
streamlit run app.py
```

Your browser will automatically open to `http://localhost:8501` and you'll see the app.

**To stop the app:** go back to Command Prompt and press `Ctrl + C`

**To run it again later:** just repeat Step 4 (Steps 1–3 only need to be done once).

---

## Step 5 — Try it with sample data

1. In the left sidebar, type a Pack ID like `PACK-001`
2. Click **"Browse files"** and select `sample_data.csv` from the folder
3. You'll see:
   - Charts for all 5 temperature channels
   - A score (should be around 85–90, PASS)
   - Metrics: peak temp, ΔT, rise rate, etc.
4. Click **"Save this run to database"**
5. Upload the same file again — you'll now see the previous run overlaid as dotted lines

---

## Using your own data

Your CSV just needs:
- **One time column** — named anything with "time", "sec", "min", or "elapsed" in it
- **One or more temperature columns** — named anything with "temp", "tc", "cell", "case", or "temperature" in it

Example:
```
Time_s, Cell_Temp_1, Cell_Temp_2, Case_Temp, Ambient_Temp
0, 22.1, 22.0, 21.8, 21.5
10, 22.3, 22.2, 21.9, 21.5
...
```

If your columns aren't auto-detected correctly, expand the **"Column mapping"** section in the app and pick them manually.

---

## Adjusting thresholds (go/no-go limits)

In the left sidebar you can set:
- **Max cell temp** — absolute maximum allowable temperature
- **Max ΔT** — maximum allowed cell-to-cell spread
- **Max rise rate** — maximum allowable rate of temperature increase

These are the limits the score is calculated against. Change them to match your spec sheet.

---

## Scoring explained

| Category | Points | What it checks |
|---|---|---|
| Peak Temperature | /30 | How close to (or over) your max temp limit |
| Thermal Uniformity (ΔT) | /25 | Cell-to-cell temperature spread |
| Rise Rate | /25 | How fast temperature is climbing |
| Time Over Limit | /20 | Minutes spent above the threshold |

| Score | Verdict |
|---|---|
| 75–100 | ✅ PASS |
| 50–74  | ⚠️ CAUTION |
| 0–49   | ❌ FAIL |

---

## Using Google Drive for shared data

The app saves a file called `battery_runs.db` in the same folder as `app.py`.

**Option A — Simple (recommended to start):**
Put the entire `battery_analyzer` folder in a shared Google Drive folder.
Anyone on your team can run the app from there — the `.db` file is shared automatically.

**Option B — More advanced:**
Point the `DB_PATH` variable in `app.py` to a Google Drive path on your computer.
On Windows with Drive for Desktop installed, this looks like:
```python
DB_PATH = r"G:\Shared drives\BatteryTests\battery_runs.db"
```

---

## Frequently asked questions

**Q: Do I need internet to run this?**
A: Only for the first install (Steps 1–3). After that it runs completely offline.

**Q: Where is my data stored?**
A: In `battery_runs.db` in the same folder as the app. It's a single file you can back up or share.

**Q: What if my CSV has extra header rows or metadata at the top?**
A: Open the CSV in Excel first, delete the extra rows, and save it. Or ask for help — this is easy to add.

**Q: Can I change the scoring weights?**
A: Yes — open `scoring.py` in Notepad and adjust the point values. Comments explain each section.

**Q: Something looks wrong / the app crashed**
A: Copy the red error text and share it — almost all errors are easy one-line fixes.

---

## Files explained (for when you're curious)

| File | What it does |
|---|---|
| `app.py` | The main app — layout, charts, UI |
| `scoring.py` | All the math: metrics and scoring logic |
| `database.py` | Saves and loads runs from the database |
| `battery_runs.db` | Created automatically — stores all your run history |
| `sample_data.csv` | Fake but realistic test data to try the app |
