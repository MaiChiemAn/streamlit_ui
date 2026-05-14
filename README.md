# Real-time Team Performance Dashboard

This guide explains how to set up the environment, generate the sample SQLite database, run the real-time updater, and launch the Streamlit dashboard.

## Running with Docker Compose (Recommended)

### Prerequisites
- Docker and Docker Compose installed

### Quick Start

1. **Set up environment variables** (optional)

   The docker-compose configuration uses PostgreSQL. You can customize the database connection by creating a `.env` file:

   ```env
   PGHOST=your_postgres_host
   PGPORT=5432
   PGDATABASE=your_database
   PGUSER=your_username
   PGPASSWORD=your_password
   PGSSLMODE=require
   ```

2. **Start the dashboard**

   ```cmd
   docker-compose up
   ```

   Or run in detached mode:

   ```cmd
   docker-compose up -d
   ```

3. **Access the dashboard**

   Open your browser and navigate to `http://localhost:8502`

4. **Change the exposed port** (optional)

   If you want to use a different port (e.g., `9000` instead of `8502`), edit the `docker-compose.yml` file:

   ```yaml
   ports:
     - "9000:9001"  # Change 8502 to your desired port
   ```

   Then restart the container:

   ```cmd
   docker-compose down
   docker-compose up -d
   ```

   Access the dashboard at `http://localhost:9000`

5. **Stop the dashboard**

   If running in detached mode:

   ```cmd
   docker-compose down
   ```

   If running in foreground, press **Ctrl+C**

## Running Locally (Without Docker)

### 1) Prerequisites

- Python 3.10+ available on PATH
- (Recommended) A virtual environment

### 2) Install dependencies

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3) Initialize the database (one-time or when you want fresh data)

```cmd
python create_db.py
```

This creates `your_database.db` with 10 tables (`Team_1`..`Team_10`) and a single seeded row per table. See [create_db.py](create_db.py) for details.

### 4) Run the real-time data updater (background process)

```cmd
python update_realtime.py
```

- Writes a new random value to each `Team_1`..`Team_10` every few seconds.
- Keep this terminal running; stop with **Ctrl+C** when done.
- Implementation: [update_realtime.py](update_realtime.py).

### 5) Launch the Streamlit dashboard

Open a new terminal (leave the updater running) and ensure your virtual environment is active, then run:

```cmd
streamlit run app.py
```

- The app defaults to `http://localhost:8501`.
- It auto-refreshes to read the latest values written by the updater.
- Implementation: [app.py](app.py).

### 6) Typical workflow (Local setup)

1. Activate venv and install deps (step 2).
2. (Optional) Recreate seed data with `python create_db.py` (step 3).
3. Start the updater: `python update_realtime.py` (step 4).
4. Start the dashboard: `streamlit run app.py` (step 5).

### 7) Troubleshooting

- **Database not found**: Ensure `your_database.db` exists in the project root; rerun `python create_db.py`.
- **Port in use**: If `8501` is busy, run `streamlit run app.py --server.port 8502`.
- **Missing packages**: Re-run `pip install -r requirements.txt` inside the venv.
