import os
import time
from contextlib import contextmanager

import pandas as pd
from psycopg2 import pool as pg_pool
import streamlit as st
import streamlit_highcharts as st_hc
from datetime import datetime
import pytz

st.set_page_config(page_title="Team Dashboard", layout="wide")
st.markdown("<h1 style='text-align: center;'>📊 AI Game Board</h1>", unsafe_allow_html=True)

DEFAULT_REFRESH_SEC = 15

TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
PGTABLE_OFFICIAL_ROUND = os.getenv("PGTABLE_OFFICIAL_ROUND", "player_stats")
PGTABLE_DRAFT_ROUND = os.getenv("PGTABLE_DRAFT_ROUND", "player_stats_draft")
PGTABLE_FLASH_ROUND = os.getenv("PGTABLE_FLASH_ROUND", "extra_round")

@st.cache_resource
def get_connection_pool():
    return pg_pool.SimpleConnectionPool(
        1,
        10,
        host=os.getenv("PGHOST", "db.prisma.io"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv(
            "PGUSER",
            "e8faac1743f27125661a54b1c36785ffedb635ee82b76fe9c4741ea560c1fd05",
        ),
        password=os.getenv("PGPASSWORD", "sk_e8y0fMTmSZ8bqMI066wJt"),
        sslmode=os.getenv("PGSSLMODE", "require"),
    )

@contextmanager
def get_pg_conn():
    pool = get_connection_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)

if "refresh_count" not in st.session_state:
    st.session_state["refresh_count"] = 0


def check_db_health(table_name: str) -> tuple[bool, str]:
    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.execute(f"SELECT to_regclass('public.{table_name}')")
                exists = cursor.fetchone()[0] is not None
                if not exists:
                    return False, f"Table {table_name} not found"
        return True, "DB healthy"
    except Exception as exc:
        return False, f"Health check error: {exc}"


def fetch_keyword_counts(table_name: str) -> pd.DataFrame:
    query = f"""
        WITH dedup AS (
            SELECT
                team_name,
                keyword,
                MIN(created_at) AS first_seen,
                MAX(created_at) AS last_seen
            FROM {table_name}
            GROUP BY team_name, keyword
        )
        SELECT
            team_name,
            keyword,
            1 AS keyword_count,
            first_seen,
            last_seen
        FROM dedup
        ORDER BY team_name, keyword
    """
    with get_pg_conn() as conn:
        df = pd.read_sql_query(query, conn)
    return df


def run_data_workflow(table_name: str) -> tuple[pd.DataFrame | None, dict]:
    healthy, health_msg = check_db_health(table_name)
    if not healthy:
        return None, {
            "healthy": False,
            "message": health_msg,
            "db": os.getenv("PGHOST", "db.prisma.io"),
            "timestamp": datetime.now(TIMEZONE).strftime('%H:%M:%S'),
        }

    df = fetch_keyword_counts(table_name)
    return df, {
        "healthy": True,
        "message": "DB healthy",
        "db": os.getenv("PGHOST", "db.prisma.io"),
        "timestamp": datetime.now(TIMEZONE).strftime('%H:%M:%S'),
    }


def build_chart_options(df: pd.DataFrame) -> dict:
    team_counts = df.groupby("team_name")["keyword_count"].sum().reset_index()

    def _team_sort_key(name: str):
        try:
            # Sort numerically when team_name represents a number (e.g., "1", "02", "10").
            return (0, float(name))
        except (TypeError, ValueError):
            # Otherwise fall back to case-insensitive alphabetical sort.
            return (1, str(name).lower())

    sorted_team_rows = sorted(
        team_counts.to_dict("records"), key=lambda row: _team_sort_key(row["team_name"])
    )

    series_data = []
    drilldown_series = []

    for row in sorted_team_rows:
        team = row["team_name"]
        total = int(row["keyword_count"])
        series_data.append({"name": team, "y": total, "drilldown": team})

        detail = df[df["team_name"] == team][["keyword", "keyword_count"]]
        drilldown_series.append(
            {
                "id": team,
                "name": f"{team} keywords",
                "type": "column",
                "data": detail.values.tolist(),
            }
        )

    return {
        "chart": {"type": "column", "animation": True},
        "title": {"text": f"Team Ranking"},
        "xAxis": {
            "type": "category",
            "title": {"text": "Team"},
            "tickInterval": 1,
            "labels": {
                "step": 1,
                "rotation": -30,
                "align": "right",
                "style": {
                    "fontSize": "10px",
                    "textDecoration": "none",
                }
            },
        },
        "yAxis": {"title": {"text": "Number of pass keywords"}},
        "legend": False,
        "plotOptions": {
            "series": {
                "borderWidth": 0,
                "dataLabels": {"enabled": True, "format": "{point.y:.0f}"},
            }
        },
        "tooltip": {
            "headerFormat": "<span style='font-size:11px'>{series.name}</span><br>",
            "pointFormat": "<span style='color:{point.color}'>{point.name}</span>: <b>{point.y:.0f}</b><br/>",
        },
        "series": [
            {
                "name": "Teams",
                "colorByPoint": True,
                "data": series_data,
                "type": "column",
            }
        ],
        "drilldown": {"series": drilldown_series},
    }


def build_packedbubble_options(df: pd.DataFrame) -> dict:
    agg_teams = df.groupby("team_name").agg({
        "keyword_count": "sum",
        "last_seen": "max"
    }).reset_index()

    TOP_N_TEAMS = 7
    if not agg_teams.empty:
        top_teams_df = agg_teams.sort_values(
            by=["keyword_count", "last_seen"], 
            ascending=[False, True]
        ).head(TOP_N_TEAMS)
        
        top_team_names = set(top_teams_df["team_name"].tolist())
        
        agg = df[df["team_name"].isin(top_team_names)]
        agg = agg.groupby(["team_name", "keyword"])["keyword_count"].sum().reset_index()
    else:
        agg = pd.DataFrame()

    if agg.empty:
        return {
            "chart": {"type": "packedbubble"},
            "title": {"text": "Keyword distribution across the top 7 teams (Time-weighted)"},
            "series": [],
        }

    max_value = int(agg["keyword_count"].max())

    def _team_sort_key(name: str):
        try:
            return (0, float(name))
        except (TypeError, ValueError):
            return (1, str(name).lower())

    series: list[dict] = []
    for team, group in agg.groupby("team_name"):
        distinct_keywords_count = group["keyword"].nunique()
        data = [
            {"name": row["keyword"], "value": int(row["keyword_count"])}
            for _, row in group.iterrows()
        ]
        series.append({"name": f"{team} ({distinct_keywords_count} keywords)", "data": data})
    
    series.sort(key=lambda s: _team_sort_key(s["name"].split(" ")[0]))

    return {
        "chart": {"type": "packedbubble"},
        "title": {"text": "Keyword distribution across the top 7 teams"},
        "tooltip": {"useHTML": True, "pointFormat": "<b>{point.name}</b>: {point.value}"},
        "plotOptions": {
            "packedbubble": {
                "minSize": "20%",
                "maxSize": "70%",
                "zMin": 0,
                "zMax": max_value,
                "layoutAlgorithm": {
                    "gravitationalConstant": 0.05,
                    "splitSeries": True,
                    "seriesInteraction": False,
                    "dragBetweenSeries": True,
                    "parentNodeLimit": True,
                },
                "dataLabels": {
                    "enabled": True,
                    "format": "{point.name}",
                    "style": {"textOutline": "none", "fontWeight": "normal"},
                },
            }
        },
        "series": series,
    }


def run_ui():
    # Session State Initialization
    if "refresh_count" not in st.session_state:
        st.session_state["refresh_count"] = 0
    if "countdown_start" not in st.session_state:
        st.session_state["countdown_start"] = None
    if "countdown_duration" not in st.session_state:
        st.session_state["countdown_duration"] = 600
    if "timer_minutes" not in st.session_state:
        st.session_state["timer_minutes"] = 10
    if "timer_seconds" not in st.session_state:
        st.session_state["timer_seconds"] = 0
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()
    if "latest_data" not in st.session_state:
        st.session_state["latest_data"] = None
    if "latest_meta" not in st.session_state:
        st.session_state["latest_meta"] = None
    if "final_query_done" not in st.session_state:
        st.session_state["final_query_done"] = False

    # Dashboard Controls
    with st.expander("⚙️ Dashboard Controls", expanded=True):
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1.5])
        with col1:
            refresh_seconds = st.slider("Update Interval (sec)", 1, 60, DEFAULT_REFRESH_SEC)
        with col2:
            auto_refresh = st.checkbox("Auto Update", value=False)
        with col3:
            manual_update = st.button("🔄 Update Now", use_container_width=True)
        with col4:
            selected_table_name = st.radio(
                "**Round**",
                options=["Draft", "Official", "Flash"],
                index=0,
                key="table_selector"
            )
        
        # Timer Setup in col5
        with col5:
            st.markdown("**⏱️ Timer Setup**")
            timer_col1, timer_col2 = st.columns([1, 1])
            with timer_col1:
                timer_minutes = st.number_input(
                    "Min",
                    min_value=0,
                    max_value=60,
                    value=st.session_state["timer_minutes"],
                    step=1,
                    key="timer_min_input",
                    label_visibility="visible"
                )
            with timer_col2:
                timer_seconds = st.number_input(
                    "Sec",
                    min_value=0,
                    max_value=59,
                    value=st.session_state["timer_seconds"],
                    step=1,
                    key="timer_sec_input",
                    label_visibility="visible"
                )

    # Timer Controls and Display (outside expander) - compact version
    timer_row1, timer_row2, timer_row3 = st.columns([1, 1, 1])
    with timer_row2:
        # Timer display
        timer_display = st.empty()
        
        # Control buttons in a single row
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
        with btn_col1:
            if st.button("▶️ Start", use_container_width=True, type="primary"):
                st.session_state["timer_minutes"] = timer_minutes
                st.session_state["timer_seconds"] = timer_seconds
                st.session_state["countdown_start"] = time.time()
                st.session_state["countdown_duration"] = timer_minutes * 60 + timer_seconds
                st.session_state["final_query_done"] = False  # Reset final query flag
                st.rerun()
        with btn_col2:
            if st.button("⏸️ Stop", use_container_width=True):
                if st.session_state["countdown_start"] is not None:
                    # Freeze current time
                    elapsed = time.time() - st.session_state["countdown_start"]
                    remaining = max(0, st.session_state["countdown_duration"] - elapsed)
                    st.session_state["countdown_duration"] = remaining
                    st.session_state["countdown_start"] = None
                st.rerun()
        with btn_col3:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state["countdown_start"] = None
                st.session_state["countdown_duration"] = st.session_state["timer_minutes"] * 60 + st.session_state["timer_seconds"]
                st.session_state["final_query_done"] = False  # Reset final query flag
                st.rerun()

    # Update countdown display
    def update_countdown_display():
        if st.session_state["countdown_start"] is not None:
            elapsed = time.time() - st.session_state["countdown_start"]
            remaining = max(0, st.session_state["countdown_duration"] - elapsed)
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            
            if remaining > 0:
                timer_display.markdown(
                    f"<div style='text-align: center;'><h1 style='color: #FF4B4B; margin: 5px 0; font-size: 2.5rem;'>⏱️ {minutes:02d}:{seconds:02d}</h1></div>",
                    unsafe_allow_html=True
                )
                return True
            else:
                timer_display.markdown(
                    "<div style='text-align: center;'><h1 style='color: #666666; margin: 5px 0; font-size: 2rem;'>⏰ Time's Up!</h1></div>",
                    unsafe_allow_html=True
                )
                return False
        elif st.session_state["countdown_duration"] > 0:
            # Timer is paused
            minutes = int(st.session_state["countdown_duration"] // 60)
            seconds = int(st.session_state["countdown_duration"] % 60)
            timer_display.markdown(
                f"<div style='text-align: center;'><h1 style='color: #FFA500; margin: 5px 0; font-size: 2.5rem;'>⏸️ {minutes:02d}:{seconds:02d}</h1></div>",
                unsafe_allow_html=True
            )
            return True
        else:
            timer_display.markdown(
                "<div style='text-align: center;'><h2 style='color: #888888; margin: 5px 0; font-size: 1.5rem;'>⏱️ Timer Ready</h2></div>",
                unsafe_allow_html=True
            )
            return True
    
    # Map selected name to actual table name
    table_mapping = {
        "Draft": PGTABLE_DRAFT_ROUND,
        "Official": PGTABLE_OFFICIAL_ROUND,
        "Flash": PGTABLE_FLASH_ROUND
    }
    selected_table = table_mapping[selected_table_name]
    
    # Check timer status
    timer_active = update_countdown_display()
    
    # Determine if we should fetch new data
    should_fetch_data = False
    time_since_refresh = time.time() - st.session_state["last_refresh"]
    
    # Fetch data if:
    # 1. Manual update button clicked
    # 2. Auto refresh is on AND enough time passed AND timer is still active
    # 3. First time loading (no data yet)
    # 4. Timer just finished AND haven't done final query yet (to get latest data before freeze)
    if manual_update:
        should_fetch_data = True
        st.session_state["final_query_done"] = False  # Reset if manual update
    elif not timer_active and not st.session_state["final_query_done"]:
        # Timer just finished - do final query to get latest data
        should_fetch_data = True
        st.session_state["final_query_done"] = True
    elif auto_refresh and timer_active and time_since_refresh >= refresh_seconds:
        should_fetch_data = True
    elif st.session_state["latest_data"] is None:
        should_fetch_data = True
    
    # Fetch and update data (Thread 2: DB updates)
    data_just_fetched = False
    if should_fetch_data:
        df, meta = run_data_workflow(selected_table)
        
        if meta["healthy"] and df is not None:
            st.session_state["latest_data"] = df
            st.session_state["latest_meta"] = meta
            st.session_state["last_refresh"] = time.time()
            if auto_refresh or manual_update:
                st.session_state["refresh_count"] += 1
            data_just_fetched = True
        elif st.session_state["latest_data"] is None:
            # No previous data and current fetch failed
            st.error(f"❌ {meta['message']}")
            st.stop()
    
    # Display status and render charts
    if st.session_state["latest_data"] is not None:
        if not timer_active and st.session_state["final_query_done"]:
            # st.success("⏰ Time's up! Showing final results with latest data.")
            pass
        elif not timer_active:
            st.info("⏱️ Fetching final data...")
        
        # Render charts (key only changes when refresh_count changes, preventing unnecessary re-animation)
        curr_idx = st.session_state["refresh_count"]
        st_hc.streamlit_highcharts(
            build_chart_options(st.session_state["latest_data"]), 
            height=450, 
            key=f"col_{curr_idx}"
        )
        st_hc.streamlit_highcharts(
            build_packedbubble_options(st.session_state["latest_data"]), 
            height=500, 
            key=f"bub_{curr_idx}"
        )
    else:
        st.error("❌ No data available")
        st.stop()
    
    # Thread 1: Real-time countdown updates
    # Rerun immediately after fetching data to keep timer smooth
    # Otherwise sleep for shorter intervals for more responsive countdown
    # Stop rerunning when timer is finished and final query is done
    if not timer_active and st.session_state["final_query_done"]:
        # Timer finished and final query completed - freeze dashboard
        pass
    elif not timer_active and not st.session_state["final_query_done"]:
        # Timer just finished but haven't done final query yet - rerun immediately
        st.rerun()
    elif st.session_state["countdown_start"] is not None or auto_refresh:
        if data_just_fetched:
            # Rerun immediately after data fetch to compensate for query time
            st.rerun()
        else:
            # Sleep shorter time (0.5s instead of 1s) for smoother countdown
            time.sleep(0.5)
            st.rerun()

if __name__ == "__main__":
    run_ui()
