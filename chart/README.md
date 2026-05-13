# Dynamic Team Performance Dashboard

## 📊 Tổng quan

Dashboard hiển thị hiệu suất đội theo thời gian thực với 2 loại biểu đồ:
- **Bar Chart**: Hiển thị top 30 đội có keyword count cao nhất
- **Bubble Chart**: Hiển thị top 7 đội với bubble size thể hiện keyword count

## 🏗️ Kiến trúc

```
chart/
├── api_server.py          # FastAPI backend server
├── config.py              # Backend configuration
├── config.js              # Frontend configuration
├── dynamic_chart.html     # Frontend dashboard
└── dynamic_chart.js       # Chart logic & API calls
```

## 📋 Yêu cầu

- Python 3.10+
- PostgreSQL database với bảng `player_stats`
- Các dependencies:
  - FastAPI
  - uvicorn
  - psycopg2
  - python-dotenv

## 🚀 Hướng dẫn chạy

### Bước 1: Cài đặt dependencies

```bash
pip install fastapi uvicorn psycopg2-binary python-dotenv
```

### Bước 2: Cấu hình database

Tạo file `.env` trong thư mục gốc của project với nội dung:

```env
PGHOST=<your_host>
PGPORT=<your_port>
PGDATABASE=<your_database>
PGUSER=<your_user>
PGPASSWORD=<your_password>
PGSSLMODE=require
PGCONNECT_TIMEOUT=5
```

### Bước 3: Chạy API Server

Có 3 cách để chạy server:

**Cách 1: Chạy trực tiếp với Python**
```bash
cd chart
python api_server.py
```

**Cách 2: Chạy với uvicorn**
```bash
cd chart
uvicorn api_server:app --reload --port 5000
```

**Cách 3: Chạy với host và port tùy chỉnh**
```bash
uvicorn api_server:app --host 0.0.0.0 --port 5000 --reload
```

Server sẽ chạy tại: `http://localhost:5000`

### Bước 4: Mở Dashboard

Mở file `dynamic_chart.html` trong trình duyệt:

**Windows:**
```bash
start dynamic_chart.html
```

**Linux:**
```bash
xdg-open dynamic_chart.html
```

Hoặc double-click vào file `dynamic_chart.html`.

## 🔧 Cấu hình

### Backend Configuration (`config.py`)

```python
TOP_N_TEAMS = 30              # Số đội hiển thị trong bar chart
CACHE_TTL_SECONDS = 3         # Cache TTL (seconds)
BAR_CHART_LIMIT = TOP_N_TEAMS # Limit cho bar chart
BUBBLE_CHART_LIMIT = None     # None = hiển thị tất cả
TEAM_COLORS_COUNT = 50        # Số lượng màu unique
```

### Frontend Configuration (`config.js`)

```javascript
API_BASE_URL: 'http://localhost:5000'  // API endpoint
TOP_N_TEAMS: 30                        // Bar chart limit
BUBBLE_CHART_MAX_TEAMS: 7              // Bubble chart limit
DEFAULT_REFRESH_INTERVAL: 5            // Auto-refresh (seconds)
BAR_CHART_ANIMATION_DURATION: 1000     // Animation duration (ms)
```


## 🔍 API Documentation

Sau khi start server, truy cập:
- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc

## 🎯 Features

### Performance Optimizations
- ✅ Connection pooling (2-30 connections)
- ✅ Response caching (3 seconds TTL)
- ✅ GZip compression (60-80% data reduction)
- ✅ Optimized SQL queries
- ✅ Duplicate update prevention

### Dashboard Features
- 📊 Real-time bar chart (top 30 teams)
- 🫧 Interactive bubble chart (top 7 teams)
- 🔄 Auto-refresh (configurable interval)
- ⏸️ Pause/Resume updates
- 📱 Responsive design
- 🎨 Color-coded teams

## ⚙️ Customization

### Thay đổi số đội hiển thị

**Bar Chart:**
```python
# config.py
TOP_N_TEAMS = 50  # Hiển thị top 50 đội
```

**Bubble Chart:**
```javascript
// config.js
BUBBLE_CHART_MAX_TEAMS: 10  // Hiển thị 10 đội
```

### Thay đổi refresh interval

```javascript
// config.js
DEFAULT_REFRESH_INTERVAL: 3  // Refresh mỗi 3 giây
```

### Thay đổi cache TTL

```python
# config.py
CACHE_TTL_SECONDS = 5  # Cache 5 giây
```

## 📝 Notes

- Dashboard sử dụng Chart.js cho visualization
- API response được cache 3 giây để giảm database load
- Connection pool tự động manage connections (2-30 connections)
- GZip compression tự động áp dụng cho responses > 1KB
