import os
import time
import sqlite3
import pandas as pd
import streamlit as st
import streamlit_highcharts as st_hc

# --- CONFIGURATION ---
st.set_page_config(page_title="Team Dashboard", layout="wide")
st.title("📊 Real-time Team Performance Dashboard")

DB_FILE = os.getenv("SQLITE_DB_FILE", "your_database.db")
DEFAULT_REFRESH_SEC = 5 

def get_db_conn():
    return sqlite3.connect(DB_FILE)

# --- DATA FETCHING ---
def fetch_keyword_counts() -> pd.DataFrame:
    query = """
        WITH dedup AS (
            SELECT 
                team_name, 
                keyword, 
                MIN(created_at) AS first_seen, 
                MAX(created_at) AS last_seen
            FROM player_stats
            GROUP BY team_name, keyword
        )
        SELECT team_name, keyword, 1 AS keyword_count, first_seen, last_seen
        FROM dedup
        ORDER BY team_name, keyword
    """
    try:
        with get_db_conn() as conn:
            df = pd.read_sql_query(query, conn)
            # FIX: Ensure keyword_count is a standard integer early on
            if not df.empty:
                df['keyword_count'] = df['keyword_count'].astype(int)
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

# --- CHART BUILDERS ---
def build_column_chart(df: pd.DataFrame) -> dict:
    team_counts = df.groupby("team_name")["keyword_count"].sum().reset_index()
    
    # Sort teams numerically if possible
    team_counts['sort_val'] = pd.to_numeric(team_counts['team_name'], errors='coerce')
    team_counts = team_counts.sort_values(by=['sort_val', 'team_name']).drop(columns=['sort_val'])

    # FIX: Use int() and str() to ensure JSON serializable types
    series_data = [
        {
            "name": str(r["team_name"]), 
            "y": int(r["keyword_count"])
        } for _, r in team_counts.iterrows()
    ]

    return {
        "chart": {"type": "column"},
        "title": {"text": f"Latest Stats (Updated: {time.strftime('%H:%M:%S')})"},
        "xAxis": {"type": "category", "title": {"text": "Teams"}},
        "yAxis": {"title": {"text": "Keywords Count"}},
        "series": [{"name": "Keywords", "colorByPoint": True, "data": series_data}]
    }

def build_bubble_chart(df: pd.DataFrame) -> dict:
    series = []
    for team, group in df.groupby("team_name"):
        # FIX: Ensure all values in the bubble list are native types
        data = [
            {
                "name": str(row["keyword"]), 
                "value": int(row["keyword_count"])
            } for _, row in group.iterrows()
        ]
        series.append({"name": str(team), "data": data})

    return {
        "chart": {"type": "packedbubble", "height": "500px"},
        "title": {"text": "Keyword Distribution"},
        "plotOptions": {
            "packedbubble": {
                "minSize": "30%", "maxSize": "100%",
                "layoutAlgorithm": {"splitSeries": True, "gravitationalConstant": 0.02},
                "dataLabels": {"enabled": True, "format": "{point.name}"}
            }
        },
        "series": series
    }

# --- LIVE UI LOGIC ---
def run_ui():
    col1, col2 = st.columns([2, 1])
    with col1:
        refresh_rate = st.slider("Refresh Interval (seconds)", 1, 60, DEFAULT_REFRESH_SEC)
    with col2:
        auto_refresh = st.toggle("Enable Auto-Refresh", value=True)

    @st.fragment(run_every=refresh_rate if auto_refresh else None)
    def chart_fragment():
        df = fetch_keyword_counts()
        
        if df.empty:
            st.warning("No data found in player_stats table.")
            return

        c1, c2 = st.columns(2)
        
        # Use unique keys with floor division to prevent unnecessary re-renders 
        # within the same second if the fragment triggers fast.
        ts = int(time.time())
        
        with c1:
            opts_col = build_column_chart(df)
            st_hc.streamlit_highcharts(opts_col, key=f"col_{ts}")
            
        with c2:
            opts_bub = build_bubble_chart(df)
            st_hc.streamlit_highcharts(opts_bub, key=f"bub_{ts}")
            
        st.caption(f"Last successful update: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    chart_fragment()

if __name__ == "__main__":
    run_ui()