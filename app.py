import os
import time
from contextlib import contextmanager

import pandas as pd
from psycopg2 import pool as pg_pool
import streamlit as st
import streamlit_highcharts as st_hc

st.set_page_config(page_title="Team Dashboard", layout="wide")
st.title("📊 Real-time Team Performance Dashboard")

DEFAULT_REFRESH_SEC = 15
MAX_AUTO_CYCLES = 500

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


def check_db_health() -> tuple[bool, str]:
    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.execute("SELECT to_regclass('public.player_stats')")
                exists = cursor.fetchone()[0] is not None
                if not exists:
                    return False, "Table player_stats not found"
        return True, "DB healthy"
    except Exception as exc:
        return False, f"Health check error: {exc}"


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


def run_data_workflow() -> tuple[pd.DataFrame | None, dict]:
    healthy, health_msg = check_db_health()
    if not healthy:
        return None, {
            "healthy": False,
            "message": health_msg,
            "db": os.getenv("PGHOST", "db.prisma.io"),
            "timestamp": time.strftime("%H:%M:%S"),
        }

    df = fetch_keyword_counts()
    return df, {
        "healthy": True,
        "message": "DB healthy",
        "db": os.getenv("PGHOST", "db.prisma.io"),
        "timestamp": time.strftime("%H:%M:%S"),
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
        "title": {"text": f"Cập nhật dữ liệu lúc: {time.strftime('%H:%M:%S')}"},
        "xAxis": {
            "type": "category",
            "title": {"text": "Team"},
            "tickInterval": 1,
            "labels": {"step": 1},
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
    agg = df.groupby(["team_name", "keyword"])["keyword_count"].sum().reset_index()

    # Keep only the top N teams by total keyword count to avoid bubble clutter.
    TOP_N_TEAMS = 7
    if not agg.empty:
        team_totals = (
            agg.groupby("team_name")["keyword_count"].sum().reset_index().sort_values("keyword_count", ascending=False)
        )
        top_team_names = set(team_totals.head(TOP_N_TEAMS)["team_name"].tolist())
        agg = agg[agg["team_name"].isin(top_team_names)]

    if agg.empty:
        return {
            "chart": {"type": "packedbubble"},
            "title": {"text": "Keyword distribution across the top 7 teams"},
            "series": [],
        }

    max_value = int(agg["keyword_count"].max()) if not agg.empty else 1

    def _team_sort_key(name: str):
        try:
            # Sort numerically when team_name represents a number (e.g., "1", "02", "10").
            return (0, float(name))
        except (TypeError, ValueError):
            # Otherwise fall back to case-insensitive alphabetical sort.
            return (1, str(name).lower())

    series: list[dict] = []
    for team, group in agg.groupby("team_name"):
        data = [
            {"name": row["keyword"], "value": int(row["keyword_count"])}
            for _, row in group.iterrows()
        ]
        series.append({"name": team, "data": data})
    
    # Sort series by team name (numerically if possible, then alphabetically)
    series.sort(key=lambda s: _team_sort_key(s["name"]))

    return {
        "chart": {"type": "packedbubble"},
        "title": {"text": "Keyword distribution across the top 7 teams"},
        "tooltip": {"useHTML": True, "pointFormat": "<b>{point.name}</b>: {point.value}"},
        "plotOptions": {
            "packedbubble": {
                "minSize": "20%",
                "maxSize": "100%",
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
                    "filter": {"property": "y", "operator": ">", "value": 0},
                    "style": {"textOutline": "none", "fontWeight": "normal"},
                },
            }
        },
        "series": series,
    }


def run_ui() -> None:
    col1, col2 = st.columns([3, 1])
    with col1:
        refresh_seconds = st.slider(
            "Update Interval (seconds)", min_value=1, max_value=30, value=DEFAULT_REFRESH_SEC, step=1
        )
    with col2:
        auto_refresh = st.checkbox("Auto Update", value=True, key="auto_refresh_toggle")

    placeholder_chart = st.empty()
    placeholder_bubble = st.empty()

    def render(df: pd.DataFrame):
        refresh_idx = st.session_state.get("refresh_count", 0)
        options = build_chart_options(df)
        bubble_options = build_packedbubble_options(df)
        with placeholder_chart.container():
            st_hc.streamlit_highcharts(options, height=450, key=f"column_chart_{refresh_idx}")
        with placeholder_bubble.container():
            st_hc.streamlit_highcharts(bubble_options, height=500, key=f"bubble_chart_{refresh_idx}")

    df, meta = run_data_workflow()
    if not meta["healthy"] or df is None:
        st.error(meta["message"])
        st.stop()

    render(df)
    st.session_state["refresh_count"] += 1

    if auto_refresh:
        for _ in range(MAX_AUTO_CYCLES):
            time.sleep(refresh_seconds)
            df, meta = run_data_workflow()
            if not meta["healthy"] or df is None:
                st.error(meta["message"])
                st.stop()
            render(df)
            st.session_state["refresh_count"] += 1


if __name__ == "__main__":
    run_ui()
