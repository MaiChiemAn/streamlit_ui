# Real-time Team Performance Dashboard

This guide explains how to set up the environment, generate the sample SQLite database, run the real-time updater, and launch the Streamlit dashboard.

## 1) Prerequisites

- Python 3.10+ available on PATH
- (Recommended) A virtual environment

## 2) Install dependencies

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 3) Initialize the database (one-time or when you want fresh data)

```cmd
python create_db.py
```

This creates `your_database.db` with 10 tables (`Team_1`..`Team_10`) and a single seeded row per table. See [create_db.py](create_db.py) for details.

## 4) Run the real-time data updater (background process)

```cmd
python update_realtime.py
```

- Writes a new random value to each `Team_1`..`Team_10` every few seconds.
- Keep this terminal running; stop with **Ctrl+C** when done.
- Implementation: [update_realtime.py](update_realtime.py).

## 5) Launch the Streamlit dashboard

Open a new terminal (leave the updater running) and ensure your virtual environment is active, then run:

```cmd
streamlit run app.py
```

- The app defaults to `http://localhost:8501`.
- It auto-refreshes to read the latest values written by the updater.
- Implementation: [app.py](app.py).

## 6) Typical workflow

1. Activate venv and install deps (step 2).
2. (Optional) Recreate seed data with `python create_db.py` (step 3).
3. Start the updater: `python update_realtime.py` (step 4).
4. Start the dashboard: `streamlit run app.py` (step 5).

## 7) Troubleshooting

- **Database not found**: Ensure `your_database.db` exists in the project root; rerun `python create_db.py`.
- **Port in use**: If `8501` is busy, run `streamlit run app.py --server.port 8502`.
- **Missing packages**: Re-run `pip install -r requirements.txt` inside the venv.
