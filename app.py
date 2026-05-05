import os
import sqlite3
import time

import pandas as pd
import streamlit as st
import streamlit_highcharts as st_hc

# Cấu hình giao diện
st.set_page_config(page_title="Team Dashboard", layout="wide")
st.title("📊 Real-time Team Performance Dashboard")

DB_FILE = "your_database.db"
DEFAULT_REFRESH_SEC = 2
MAX_AUTO_CYCLES = 500

if "refresh_count" not in st.session_state:
    st.session_state["refresh_count"] = 0


def check_db_health(db_path: str = DB_FILE) -> tuple[bool, str]:
    """Kết nối và kiểm tra tình trạng DB.

    Trả về (is_healthy, message).
    """
    if not os.path.exists(db_path):
        return False, f"Không tìm thấy file DB tại {db_path}"

    try:
        conn = sqlite3.connect(db_path, timeout=2)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        is_ok = bool(result) and str(result[0]).lower() == "ok"
        return (True, "DB healthy") if is_ok else (False, f"Integrity check failed: {result}")
    except Exception as exc:  # pragma: no cover - logging/UI layer may handle details
        return False, f"Health check error: {exc}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def fetch_data(db_path: str = DB_FILE) -> pd.Series:
    """Lấy giá trị mới nhất từ từng bảng Team_1..Team_10."""
    conn = sqlite3.connect(db_path)
    team_data: dict[str, int] = {}
    for i in range(1, 11):
        table_name = f"Team_{i}"
        try:
            query = f"SELECT value FROM {table_name} ORDER BY rowid DESC LIMIT 1"
            df = pd.read_sql_query(query, conn)
            team_data[table_name] = int(df.iloc[0, 0]) if not df.empty else 0
        except Exception:
            team_data[table_name] = 0
    conn.close()
    return pd.Series(team_data)


def run_data_workflow(db_path: str = DB_FILE) -> tuple[pd.Series | None, dict]:
    """Tách luồng query DB ra khỏi UI.

    Returns: (data_series_or_none, meta)
    meta = {"healthy": bool, "message": str, "db_path": str, "timestamp": str}
    """
    healthy, health_msg = check_db_health(db_path)
    if not healthy:
        return None, {
            "healthy": False,
            "message": health_msg,
            "db_path": db_path,
            "timestamp": time.strftime("%H:%M:%S"),
        }

    data = fetch_data(db_path)
    return data, {
        "healthy": True,
        "message": "DB healthy",
        "db_path": db_path,
        "timestamp": time.strftime("%H:%M:%S"),
    }


def build_chart_options(data: pd.Series) -> dict:
    series_data = []
    drilldown_series = []
    for team, value in data.items():
        series_data.append({"name": team, "y": value, "drilldown": team})
        drilldown_series.append(
            {
                "id": team,
                "name": f"{team} chi tiết",
                "type": "column",
                "data": [["Giá trị", value]],
            }
        )

    return {
        "chart": {"type": "column", "animation": True},
        "title": {"text": f"Cập nhật dữ liệu lúc: {time.strftime('%H:%M:%S')}"},
        "xAxis": {"type": "category", "title": {"text": "Team"}},
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


def run_ui(db_path: str = DB_FILE) -> None:
    """Luồng UI tách khỏi luồng truy vấn dữ liệu."""
    col1, col2 = st.columns([3, 1])
    with col1:
        refresh_seconds = st.slider(
            "Chu kỳ cập nhật (giây)", min_value=1, max_value=10, value=DEFAULT_REFRESH_SEC, step=1
        )
    with col2:
        auto_refresh = st.checkbox("Tự động cập nhật", value=True, key="auto_refresh_toggle")

    placeholder_chart = st.empty()
    placeholder_meta = st.empty()

    data, meta = run_data_workflow(db_path)
    if not meta["healthy"] or data is None:
        st.error(meta["message"])
        st.stop()

    options = build_chart_options(data)
    with placeholder_chart.container():
        st_hc.streamlit_highcharts(options, height=450)

    st.session_state["refresh_count"] += 1

    if auto_refresh:
        for _ in range(MAX_AUTO_CYCLES):
            time.sleep(refresh_seconds)
            data, meta = run_data_workflow(db_path)
            if not meta["healthy"] or data is None:
                st.error(meta["message"])
                st.stop()

            options = build_chart_options(data)
            with placeholder_chart.container():
                st_hc.streamlit_highcharts(options, height=450)

            st.session_state["refresh_count"] += 1


if __name__ == "__main__":
    run_ui()
