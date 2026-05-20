import os
import time
from contextlib import contextmanager

import pandas as pd
from psycopg2 import pool as pg_pool
import streamlit as st
import streamlit_highcharts as st_hc
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="AI Game Dashboard", layout="wide")
# st.markdown("<h1 style='text-align: center;'>📊 AI Game Board</h1>", unsafe_allow_html=True)

DEFAULT_REFRESH_SEC = 15
SESSION_DURATION_SEC = 10 * 60  # 10 minutes

TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')


def get_session_duration_sec() -> int:
    return int(st.session_state.get("session_duration_sec", SESSION_DURATION_SEC))


def inject_custom_css():
    st.markdown(
        """
        <style>
            /* Page background */
            .stApp {
                background: linear-gradient(180deg, #F8FBFF 0%, #FFFFFF 40%, #F7FAFC 100%);
            }

            /* Reduce default top spacing */
            
            .block-container {
                padding-top: 0.5rem;
                padding-bottom: 0.5rem;
                max-width: 100%;
            }

            /* Remove space between blocks */
            div[data-testid="stVerticalBlock"] {
                gap: 0.4rem;
            }

            /* Reduce all margins */
            .chart-card {
                padding: 10px 12px 12px 12px;
                margin-bottom: 8px;
                border-radius: 18px;
            }

            /* Smaller metric cards */
            .metric-card {
                padding: 10px 12px;
                min-height: 80px;
            }

            /* Smaller font inside metrics */
            .metric-value {
                font-size: 24px;
            }

            /* Timer more compact */
            .timer-card {
                padding: 12px 14px;
                margin-bottom: 8px;
            }

            .timer-value {
                font-size: 28px;
            }

            /* Hero smaller */
            .hero-card {
                padding: 14px 20px;
                margin-bottom: 10px;
            }

            .hero-title {
                font-size: 28px;
            }

            /* Expander remove space */
            .streamlit-expanderContent {
                padding-top: 0 !important;
            }


            /* Hide Streamlit default menu/footer/header if desired */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}

            /* Hero section */
            .hero-card {
                background: linear-gradient(135deg, #2563EB 0%, #7C3AED 55%, #EC4899 100%);
                border-radius: 28px;
                padding: 28px 34px;
                color: white;
                box-shadow: 0 18px 45px rgba(37, 99, 235, 0.22);
                margin-bottom: 18px;
                position: relative;
                overflow: hidden;
            }

            .hero-card:before {
                content: "";
                position: absolute;
                width: 240px;
                height: 240px;
                border-radius: 999px;
                background: rgba(255,255,255,0.16);
                right: -80px;
                top: -100px;
            }

            .hero-card:after {
                content: "";
                position: absolute;
                width: 160px;
                height: 160px;
                border-radius: 999px;
                background: rgba(255,255,255,0.10);
                left: 35%;
                bottom: -100px;
            }

            .hero-title {
                font-size: 42px;
                line-height: 1.1;
                font-weight: 850;
                margin-bottom: 8px;
                letter-spacing: -0.03em;
                position: relative;
                z-index: 1;
            }

            .hero-subtitle {
                font-size: 16px;
                opacity: 0.92;
                position: relative;
                z-index: 1;
            }

            /* Cards */
            .glass-card {
                background: rgba(255,255,255,0.92);
                border: 1px solid rgba(226,232,240,0.95);
                border-radius: 24px;
                padding: 20px;
                box-shadow: 0 12px 30px rgba(15, 23, 42, 0.07);
                margin-bottom: 16px;
            }
            
            div.stButton > button[kind="secondary"] {
                background: linear-gradient(135deg, #F97316 0%, #EF4444 100%);
            }


            .metric-card {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 22px;
                padding: 18px 20px;
                box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
                min-height: 118px;
            }

            .metric-label {
                color: #64748B;
                font-size: 13px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                margin-bottom: 6px;
            }

            .metric-value {
                color: #0F172A;
                font-size: 32px;
                font-weight: 850;
                line-height: 1.1;
            }

            .metric-help {
                color: #64748B;
                font-size: 13px;
                margin-top: 7px;
            }

            /* Timer */
            .timer-card {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 26px;
                padding: 22px 24px;
                box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
                margin-bottom: 18px;
            }

            .timer-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                margin-bottom: 12px;
            }

            .timer-label {
                color: #475569;
                font-size: 15px;
                font-weight: 800;
            }

            .timer-value {
                font-size: 38px;
                font-weight: 900;
                letter-spacing: -0.03em;
                color: #EF4444;
            }

            .progress-wrap {
                height: 14px;
                background: #F1F5F9;
                border-radius: 999px;
                overflow: hidden;
                border: 1px solid #E2E8F0;
            }

            .progress-fill {
                height: 100%;
                border-radius: 999px;
                background: linear-gradient(90deg, #22C55E 0%, #F59E0B 55%, #EF4444 100%);
                transition: width 0.35s ease;
            }

            .status-pill {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                border-radius: 999px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 800;
                background: #ECFDF5;
                color: #047857;
                border: 1px solid #A7F3D0;
            }

            .status-pill.warning {
                background: #FFF7ED;
                color: #C2410C;
                border-color: #FED7AA;
            }

            .status-pill.ended {
                background: #FEF2F2;
                color: #B91C1C;
                border-color: #FECACA;
            }

            .chart-card {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 26px;
                padding: 16px 18px 22px 18px;
                box-shadow: 0 14px 34px rgba(15, 23, 42, 0.07);
                margin-bottom: 20px;
            }

            .section-title {
                font-size: 22px;
                font-weight: 850;
                color: #0F172A;
                margin-bottom: 4px;
            }

            .section-subtitle {
                font-size: 13px;
                color: #64748B;
                margin-bottom: 14px;
            }

            .start-panel {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 30px;
                padding: 34px;
                text-align: center;
                box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
                margin-top: 18px;
            }

            .start-title {
                font-size: 34px;
                font-weight: 900;
                color: #0F172A;
                margin-bottom: 8px;
            }

            .start-subtitle {
                color: #64748B;
                font-size: 16px;
                margin-bottom: 18px;
            }

            /* Buttons */
            div.stButton > button {
                border-radius: 16px;
                border: 0;
                font-weight: 800;
                padding: 0.65rem 1rem;
                background: linear-gradient(135deg, #2563EB 0%, #7C3AED 100%);
                color: white;
                box-shadow: 0 10px 22px rgba(37, 99, 235, 0.24);
                transition: all 0.2s ease;
            }

            div.stButton > button:hover {
                transform: translateY(-1px);
                box-shadow: 0 14px 28px rgba(37, 99, 235, 0.30);
                color: white;
            }

            /* Expander */
            .streamlit-expanderHeader {
                font-weight: 800;
                color: #0F172A;
            }

            /* Inputs */
            .stSlider, .stCheckbox {
                color: #0F172A;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero():
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">📊 AI Game Dashboard</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_timer_card(remaining_sec: int, session_duration_sec: int):
    minutes = remaining_sec // 60
    seconds = remaining_sec % 60

    progress_pct = int((remaining_sec / session_duration_sec) * 100)

    if remaining_sec <= 60:
        status_class = "warning"
        status_text = "Final minute"
    else:
        status_class = ""
        status_text = "Game running"

    st.markdown(
        f"""
        <div class="timer-card">
            <div class="timer-row">
                <div>
                    <div class="timer-label">⏳ Remaining Time</div>
                    <div class="timer-value">{minutes:02d}:{seconds:02d}</div>
                </div>
                <div>
                    <span class="status-pill {status_class}">● {status_text}</span>
                </div>
            </div>
            <div class="progress-wrap">
                <div class="progress-fill" style="width:{progress_pct}%;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_dashboard_stats(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "total_teams": 0,
            "total_keywords": 0,
            "leader": "-",
            "leader_score": 0,
        }

    team_scores = (
        df.groupby("team_name")["keyword_count"]
        .sum()
        .sort_values(ascending=False)
    )

    leader = str(team_scores.index[0]) if not team_scores.empty else "-"
    leader_score = int(team_scores.iloc[0]) if not team_scores.empty else 0

    return {
        "total_teams": int(df["team_name"].nunique()),
        "total_keywords": int(df["keyword"].nunique()),
        "leader": leader,
        "leader_score": leader_score,
    }


def render_metric_cards(df: pd.DataFrame, cached_meta: dict | None):
    stats = get_dashboard_stats(df)

    last_update = "-"
    db_status = "Waiting"

    if cached_meta:
        last_update = cached_meta.get("timestamp", "-")
        db_status = cached_meta.get("message", "Unknown")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Teams</div>
                <div class="metric-value">{stats["total_teams"]}</div>
                <div class="metric-help">Active teams on board</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Keywords Found</div>
                <div class="metric-value">{stats["total_keywords"]}</div>
                <div class="metric-help">Unique discovered keywords</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Current Leader</div>
                <div class="metric-value">🏆 {stats["leader"]}</div>
                <div class="metric-help">{stats["leader_score"]} passed keywords</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Last Sync</div>
                <div class="metric-value">{last_update}</div>
                <div class="metric-help">{db_status}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_start_screen():
    duration_minutes = st.session_state["session_duration_sec"] // 60
    duration_minutes = st.slider(
        "Set session duration (minutes)",
        1,
        30,
        duration_minutes,
        help="Drag the slider to change how long the game session runs.",
        key="session_duration_minutes",
    )
    st.session_state["session_duration_sec"] = duration_minutes * 60

    st.markdown(
        f"""
        <div class="start-panel">
            <div class="start-title">🚀 Ready to start?</div>
            <div class="start-subtitle">
                Press the button below to begin.
            </div>
            <span class="status-pill">⏳ Timer Ready: {duration_minutes:02d}:00</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    col1, col2, col3 = st.columns([1.2, 1, 1.2])
    with col2:
        if st.button("▶️ Start Game", use_container_width=True):
            start_timer()
            st.rerun()
            
def close_db_pool():
    """
    Close all DB connections and clear the cached pool.
    """
    try:
        pool = get_connection_pool()
        pool.closeall()
    except Exception:
        pass

    try:
        get_connection_pool.clear()
    except Exception:
        pass


def init_timer_state():
    if "timer_started" not in st.session_state:
        st.session_state["timer_started"] = False

    if "session_started_at" not in st.session_state:
        st.session_state["session_started_at"] = None

    if "timer_expired" not in st.session_state:
        st.session_state["timer_expired"] = False

    if "db_disconnected" not in st.session_state:
        st.session_state["db_disconnected"] = False

    if "last_data_refresh_at" not in st.session_state:
        st.session_state["last_data_refresh_at"] = 0

    if "session_duration_sec" not in st.session_state:
        st.session_state["session_duration_sec"] = SESSION_DURATION_SEC

    if "cached_df" not in st.session_state:
        st.session_state["cached_df"] = None

    if "cached_meta" not in st.session_state:
        st.session_state["cached_meta"] = None


def get_remaining_seconds() -> int:
    session_duration_sec = get_session_duration_sec()

    if not st.session_state.get("timer_started", False):
        return session_duration_sec

    if st.session_state.get("session_started_at") is None:
        return session_duration_sec

    elapsed = time.time() - st.session_state["session_started_at"]
    remaining = session_duration_sec - elapsed
    return max(0, int(remaining))

def reset_timer():
    """
    Reset the 10-minute timer while keeping the game running.
    This starts a fresh 10-minute round immediately.
    """
    st.session_state["timer_started"] = True
    st.session_state["session_started_at"] = time.time()
    st.session_state["timer_expired"] = False
    st.session_state["db_disconnected"] = False

    # Reset data refresh state
    st.session_state["last_data_refresh_at"] = 0
    st.session_state["cached_df"] = None
    st.session_state["cached_meta"] = None
    st.session_state["refresh_count"] = 0
    
def start_timer():
    st.session_state["timer_started"] = True
    st.session_state["session_started_at"] = time.time()
    st.session_state["timer_expired"] = False
    st.session_state["db_disconnected"] = False
    st.session_state["last_data_refresh_at"] = 0
    st.session_state["cached_df"] = None
    st.session_state["cached_meta"] = None

def expire_session():
    st.session_state["timer_expired"] = True
    st.session_state["timer_started"] = False

    if not st.session_state.get("db_disconnected", False):
        close_db_pool()
        st.session_state["db_disconnected"] = True
        
        
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
    if st.session_state.get("timer_expired", False):
        return None, {
            "healthy": False,
            "message": "Timer expired. Database disconnected.",
            "db": os.getenv("PGHOST", "db.prisma.io"),
            "timestamp": datetime.now(TIMEZONE).strftime("%H:%M:%S"),
        }

    healthy, health_msg = check_db_health()
    if not healthy:
        return None, {
            "healthy": False,
            "message": health_msg,
            "db": os.getenv("PGHOST", "db.prisma.io"),
            "timestamp": datetime.now(TIMEZONE).strftime("%H:%M:%S"),
        }

    df = fetch_keyword_counts()
    return df, {
        "healthy": True,
        "message": "DB healthy",
        "db": os.getenv("PGHOST", "db.prisma.io"),
        "timestamp": datetime.now(TIMEZONE).strftime("%H:%M:%S"),
    }

def build_chart_options(df: pd.DataFrame) -> dict:
    team_counts = df.groupby("team_name")["keyword_count"].sum().reset_index()

    def _team_sort_key(name: str):
        try:
            return (0, float(name))
        except (TypeError, ValueError):
            return (1, str(name).lower())

    sorted_team_rows = sorted(
        team_counts.to_dict("records"), key=lambda row: _team_sort_key(row["team_name"])
    )

    series_data = []
    drilldown_series = []

    palette = [
        "#2563EB", "#7C3AED", "#EC4899", "#F97316", "#22C55E",
        "#06B6D4", "#EAB308", "#EF4444", "#14B8A6", "#6366F1"
    ]

    for idx, row in enumerate(sorted_team_rows):
        team = row["team_name"]
        total = int(row["keyword_count"])
        series_data.append(
            {
                "name": team,
                "y": total,
                "drilldown": team,
                "color": palette[idx % len(palette)],
            }
        )

        detail = df[df["team_name"] == team][["keyword", "keyword_count"]]
        drilldown_series.append(
            {
                "id": team,
                "name": f"{team} keywords",
                "type": "column",
                "data": detail.values.tolist(),
                "colorByPoint": True,
            }
        )

    return {
        "chart": {
            "type": "column",
            "animation": True,
            "backgroundColor": "transparent",
            "style": {"fontFamily": "Inter, system-ui, sans-serif"},
        },
        "colors": palette,
        "title": {
            "text": "",
        },
        "xAxis": {
            "type": "category",
            "title": {"text": None},
            "lineColor": "#E5E7EB",
            "tickColor": "#E5E7EB",
            "labels": {
                "rotation": -25,
                "align": "right",
                "style": {
                    "fontSize": "12px",
                    "color": "#475569",
                    "textDecoration": "none",
                },
            },
        },
        "yAxis": {
            "title": {
                "text": "Passed keywords",
                "style": {"color": "#64748B", "fontWeight": "700"},
            },
            "gridLineColor": "#EEF2F7",
            "labels": {"style": {"color": "#64748B"}},
        },
        "legend": {"enabled": False},
        "credits": {"enabled": False},
        "plotOptions": {
            "series": {
                "borderWidth": 0,
                "borderRadius": 8,
                "pointPadding": 0.12,
                "groupPadding": 0.08,
                "dataLabels": {
                    "enabled": True,
                    "format": "{point.y:.0f}",
                    "style": {
                        "fontWeight": "800",
                        "color": "#0F172A",
                        "textOutline": "none",
                    },
                },
            }
        },
        "tooltip": {
            "useHTML": True,
            "backgroundColor": "rgba(255,255,255,0.96)",
            "borderColor": "#E5E7EB",
            "borderRadius": 12,
            "shadow": True,
            "pointFormat": """
                <div style="padding:6px 4px;">
                    <div style="font-size:13px;color:#64748B;">Team / Keyword</div>
                    <div style="font-size:16px;font-weight:800;color:#0F172A;">{point.name}</div>
                    <div style="font-size:13px;color:#475569;margin-top:4px;">
                        Score: <b>{point.y:.0f}</b>
                    </div>
                </div>
            """,
        },
        "series": [
            {
                "name": "Teams",
                "data": series_data,
                "type": "column",
            }
        ],
        "drilldown": {
            "activeAxisLabelStyle": {
                "color": "#2563EB",
                "textDecoration": "none",
                "fontWeight": "800",
            },
            "activeDataLabelStyle": {
                "color": "#2563EB",
                "textDecoration": "none",
            },
            "series": drilldown_series,
        },
    }


def build_packedbubble_options(df: pd.DataFrame) -> dict:
    palette = [
        "#2563EB", "#7C3AED", "#EC4899", "#F97316", "#22C55E",
        "#06B6D4", "#EAB308", "#EF4444", "#14B8A6", "#6366F1"
    ]

    base_options = {
        "chart": {
            "type": "packedbubble",
            "backgroundColor": "transparent",
            "style": {"fontFamily": "Inter, system-ui, sans-serif"},
        },
        "colors": palette,
        "title": {"text": ""},
        "credits": {"enabled": False},
        "legend": {
            "enabled": True,
            "itemStyle": {
                "color": "#334155",
                "fontWeight": "700",
            },
        },
        "tooltip": {
            "useHTML": True,
            "backgroundColor": "rgba(255,255,255,0.96)",
            "borderColor": "#E5E7EB",
            "borderRadius": 12,
            "shadow": True,
            "pointFormat": """
                <div style="padding:6px 4px;">
                    <div style="font-size:13px;color:#64748B;">Keyword</div>
                    <div style="font-size:16px;font-weight:800;color:#0F172A;">{point.name}</div>
                    <div style="font-size:13px;color:#475569;margin-top:4px;">
                        Count: <b>{point.value}</b>
                    </div>
                </div>
            """,
        },
    }

    if df is None or df.empty:
        base_options["plotOptions"] = {
            "packedbubble": {
                "minSize": "18%",
                "maxSize": "72%",
                "zMin": 0,
                "zMax": 1,
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
                    "style": {
                        "textOutline": "none",
                        "fontWeight": "700",
                        "color": "#0F172A",
                        "fontSize": "11px",
                    },
                },
            }
        }
        base_options["series"] = []
        return base_options

    agg_teams = (
        df.groupby("team_name")
        .agg({
            "keyword_count": "sum",
            "last_seen": "max",
        })
        .reset_index()
    )

    TOP_N_TEAMS = 5

    if agg_teams.empty:
        base_options["plotOptions"] = {
            "packedbubble": {
                "minSize": "18%",
                "maxSize": "72%",
                "zMin": 0,
                "zMax": 1,
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
                    "style": {
                        "textOutline": "none",
                        "fontWeight": "700",
                        "color": "#0F172A",
                        "fontSize": "11px",
                    },
                },
            }
        }
        base_options["series"] = []
        return base_options

    top_teams_df = (
        agg_teams.sort_values(
            by=["keyword_count", "last_seen"],
            ascending=[False, True],
        )
        .head(TOP_N_TEAMS)
    )

    top_team_names = set(top_teams_df["team_name"].tolist())

    agg = df[df["team_name"].isin(top_team_names)]

    if agg.empty:
        base_options["plotOptions"] = {
            "packedbubble": {
                "minSize": "18%",
                "maxSize": "72%",
                "zMin": 0,
                "zMax": 1,
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
                    "style": {
                        "textOutline": "none",
                        "fontWeight": "700",
                        "color": "#0F172A",
                        "fontSize": "11px",
                    },
                },
            }
        }
        base_options["series"] = []
        return base_options

    agg = (
        agg.groupby(["team_name", "keyword"])["keyword_count"]
        .sum()
        .reset_index()
    )

    if agg.empty:
        base_options["plotOptions"] = {
            "packedbubble": {
                "minSize": "18%",
                "maxSize": "72%",
                "zMin": 0,
                "zMax": 1,
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
                    "style": {
                        "textOutline": "none",
                        "fontWeight": "700",
                        "color": "#0F172A",
                        "fontSize": "11px",
                    },
                },
            }
        }
        base_options["series"] = []
        return base_options

    max_value = max(1, int(agg["keyword_count"].max()))

    def _team_sort_key(name: str):
        try:
            return (0, float(name))
        except (TypeError, ValueError):
            return (1, str(name).lower())

    series: list[dict] = []

    for team, group in agg.groupby("team_name"):
        distinct_keywords_count = group["keyword"].nunique()

        data = [
            {
                "name": str(row["keyword"]),
                "value": int(row["keyword_count"]),
            }
            for _, row in group.iterrows()
        ]

        series.append(
            {
                "name": f"{team} ({distinct_keywords_count} keywords)",
                "data": data,
            }
        )

    series.sort(key=lambda s: _team_sort_key(s["name"].split(" ")[0]))

    base_options["plotOptions"] = {
        "packedbubble": {
            "minSize": "18%",
            "maxSize": "72%",
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
                "style": {
                    "textOutline": "none",
                    "fontWeight": "700",
                    "color": "#0F172A",
                    "fontSize": "11px",
                },
            },
        }
    }

    base_options["series"] = series

    return base_options


def run_ui():
    inject_custom_css()
    init_timer_state()

    if "refresh_count" not in st.session_state:
        st.session_state["refresh_count"] = 0

    # Real-time UI refresh for timer only.
    st_autorefresh(interval=2000, key="real_time_timer_refresh")

    render_hero()

    # =========================
    # BEFORE TIMER STARTS
    # =========================
    if (
        not st.session_state.get("timer_started", False)
        and not st.session_state.get("timer_expired", False)
    ):
        render_start_screen()
        st.stop()

    # =========================
    # TIMER RUNNING / EXPIRED
    # =========================
    remaining_sec = get_remaining_seconds()
    session_duration_sec = get_session_duration_sec()

    if remaining_sec <= 0:
        expire_session()

        st.markdown(
            """
            <div class="timer-card">
                <div class="timer-row">
                    <div>
                        <div class="timer-label">Game Status</div>
                        <div class="timer-value">00:00</div>
                    </div>
                    <div>
                        <span class="status-pill ended">● Time is up</span>
                    </div>
                </div>
                <div class="progress-wrap">
                    <div class="progress-fill" style="width:0%;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.error("⏰ Time is up!!!")

        cached_df = st.session_state.get("cached_df")
        cached_meta = st.session_state.get("cached_meta")

        if cached_df is not None:
            render_metric_cards(cached_df, cached_meta)

            st.markdown(
                """
                <div class="chart-card">
                    <div class="section-title">🏁 Final Team Ranking</div>
                    <div class="section-subtitle">Last cached result before the game ended.</div>
                """,
                unsafe_allow_html=True,
            )
            st_hc.streamlit_highcharts(
                build_chart_options(cached_df),
                height=450,
                key="final_col_chart",
            )
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown(
                """
                <div class="chart-card">
                    <div class="section-title">🫧 Final Keyword Distribution</div>
                    <div class="section-subtitle">Keyword spread among the top teams.</div>
                """,
                unsafe_allow_html=True,
            )
            st_hc.streamlit_highcharts(
                build_packedbubble_options(cached_df),
                height=500,
                key="final_bubble_chart",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1.2, 1, 1.2])
        with col2:
            if st.button("🔁 Reset Game", use_container_width=True):
                st.session_state.clear()
                st.rerun()

        st.stop()

    render_timer_card(remaining_sec, session_duration_sec)

    # =========================
    # CONTROLS
    # =========================
    with st.expander("⚙️ Dashboard Controls", expanded=True):
        duration_minutes = st.session_state.get("session_duration_sec", SESSION_DURATION_SEC) // 60
        st.session_state["session_duration_sec"] = st.slider(
            "Session Duration (minutes)",
            1,
            30,
            duration_minutes,
            help="Use the slider to adjust the game session length.",
            key="dashboard_session_duration_minutes",
        ) * 60

        col1, col2, col3 = st.columns([1.5, 1, 1])

        with col1:
            auto_refresh = st.checkbox(
                "Auto Update",
                value=False,
                help="Automatically fetch new data from database based on the selected interval.",
            )

        with col2:
            manual_update = st.button("🔄 Update Now", use_container_width=True)

        with col3:
            reset_timer_clicked = st.button("⏱️ Reset Timer", use_container_width=True)

    if reset_timer_clicked:
        reset_timer()
        st.rerun()

    now = time.time()
    should_fetch_data = False

    # First DB load after pressing Start Game
    if st.session_state["cached_df"] is None:
        should_fetch_data = True

    # Manual update
    if manual_update:
        should_fetch_data = True

    # Auto update based on fixed refresh interval
    if auto_refresh:
        seconds_since_last_refresh = now - st.session_state["last_data_refresh_at"]

        if seconds_since_last_refresh >= DEFAULT_REFRESH_SEC:
            should_fetch_data = True

    # =========================
    # DB FETCH
    # =========================
    if should_fetch_data and not st.session_state.get("timer_expired", False):
        with st.spinner("Syncing latest game data..."):
            df, meta = run_data_workflow()

        if not meta["healthy"] or df is None:
            st.error(f"❌ {meta['message']}")
            st.stop()

        st.session_state["cached_df"] = df
        st.session_state["cached_meta"] = meta
        st.session_state["last_data_refresh_at"] = now
        st.session_state["refresh_count"] += 1

    cached_df = st.session_state.get("cached_df")
    cached_meta = st.session_state.get("cached_meta")

    if cached_df is None:
        st.warning("No data loaded yet.")
        st.stop()

    # =========================
    # DASHBOARD BODY
    # =========================
    render_metric_cards(cached_df, cached_meta)

    if cached_meta:
        st.markdown(
            f"""
            <div style="margin: 8px 0 18px 0;">
                <span class="status-pill">● {cached_meta["message"]}</span>
                <span style="color:#64748B;font-size:13px;margin-left:10px;">
                    Last database sync: <b>{cached_meta["timestamp"]}</b>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    curr_idx = st.session_state["refresh_count"]

    st.markdown(
        """
        <div class="chart-card">
            <div class="section-title">🏆 Team Ranking</div>
            <div class="section-subtitle">
                Click a team bar to drill down into its passed keywords.
            </div>
        """,
        unsafe_allow_html=True,
    )

    st_hc.streamlit_highcharts(
        build_chart_options(cached_df),
        height=450,
        key=f"col_chart",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="chart-card">
            <div class="section-title">🫧 Keyword Distribution</div>
            <div class="section-subtitle">
                Bubble size represents keyword count across the top teams.
            </div>
        """,
        unsafe_allow_html=True,
    )

    st_hc.streamlit_highcharts(
        build_packedbubble_options(cached_df),
        height=500,
        key=f"bub_chart",
    )

    st.markdown("</div>", unsafe_allow_html=True)
    
if __name__ == "__main__":
    run_ui()
