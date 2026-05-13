"""
FastAPI Server để expose data từ PostgreSQL
Chạy: uvicorn api_server:app --reload --port 5000
hoặc: python api_server.py
API sẽ chạy ở http://localhost:5000
API Docs: http://localhost:5000/docs
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import psycopg2
import psycopg2.pool
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

# Import configuration
from config import CACHE_TTL_SECONDS, TOP_N_TEAMS, BAR_CHART_LIMIT

load_dotenv()

# ===== Cache Configuration =====
_cache = {
    "data": {"value": None, "expires": None, "hash": None},
    "stats": {"value": None, "expires": None}
}

# ===== Pydantic Models =====
class HealthResponse(BaseModel):
    status: str
    message: str
    timestamp: str


class KeywordData(BaseModel):
    team_name: str
    player_name: str
    keyword: str
    keyword_count: int
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class DataResponse(BaseModel):
    status: str
    data: List[KeywordData]
    count: int
    timestamp: str


class Stats(BaseModel):
    total_teams: int
    total_players: int
    total_keywords: int
    total_records: int
    timestamp: str


class StatsResponse(BaseModel):
    status: str
    stats: Stats


class ErrorResponse(BaseModel):
    status: str
    message: str


class IndexResponse(BaseModel):
    message: str
    endpoints: Dict[str, str]
    docs: str


# ===== FastAPI App =====
app = FastAPI(
    title="Team Performance API",
    description="Real-time team performance data API với PostgreSQL",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production nên chỉ định cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable GZip compression để giảm data transfer
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ===== Database Config =====
PG_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "password"),
    "sslmode": os.getenv("PGSSLMODE", "require"),
    "connect_timeout": int(os.getenv("PGCONNECT_TIMEOUT", "5")),
}

# Connection pool for better performance
_connection_pool = None

def get_connection_pool():
    """
    Get or create connection pool
    
    Fixed maxconn to prevent pool exhaustion:
    - Increased from 10 to 30 to handle concurrent requests
    - Auto-refresh every 3-5s can cause bursts of requests
    """
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=2,    # Tăng từ 1 lên 2 cho stability
            maxconn=30,   # Tăng từ 10 lên 30 để tránh pool exhausted
            **PG_CONFIG
        )
    return _connection_pool

def get_pg_conn():
    """Get connection from pool"""
    pool = get_connection_pool()
    return pool.getconn()

def return_pg_conn(conn):
    """Return connection to pool"""
    pool = get_connection_pool()
    pool.putconn(conn)


# ===== API Endpoints =====
@app.get("/", response_model=IndexResponse)
async def root():
    """Root endpoint - API information"""
    return {
        "message": "Team Performance API Server (FastAPI)",
        "endpoints": {
            "/api/health": "Check database health",
            "/api/data": f"Get top {TOP_N_TEAMS} teams keyword data (for bar & bubble charts)",
            "/api/stats": "Get statistics",
            "/api/optimize": "Create database indexes (POST)"
        },
        "config": {
            "top_n_teams": TOP_N_TEAMS,
            "cache_ttl_seconds": CACHE_TTL_SECONDS
        },
        "docs": "http://localhost:5000/docs"
    }


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Kiểm tra kết nối database
    
    Returns:
        HealthResponse: Status và message của database connection
    
    Raises:
        HTTPException: Khi không thể kết nối database
    """
    conn = None
    try:
        conn = get_pg_conn()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.execute("SELECT to_regclass('public.player_stats')")
            exists = cursor.fetchone()[0] is not None
            if not exists:
                raise HTTPException(
                    status_code=500,
                    detail="Table player_stats not found"
                )
        
        return {
            "status": "healthy",
            "message": "Database connection OK",
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            return_pg_conn(conn)


@app.get("/api/data", response_model=DataResponse)
async def get_data():
    """
    Lấy keyword counts từ database (Optimized - Top N + Caching)
    
    Returns:
        DataResponse: List of top N teams data với metadata
    
    Raises:
        HTTPException: Khi có lỗi query database
    """
    try:
        # Check cache first
        now = datetime.now()
        cache_entry = _cache["data"]
        
        if cache_entry["value"] and cache_entry["expires"] and now < cache_entry["expires"]:
            # Return cached data
            return cache_entry["value"]
        
        # Optimized query with subquery:
        # 1. Get top N teams by DISTINCT keyword count (không đếm duplicate keywords)
        # 2. Get detailed data only for those teams
        # 3. Much faster than full scan
        query = f"""
            WITH top_teams AS (
                SELECT team_name, COUNT(DISTINCT keyword) as total_count
                FROM player_stats
                GROUP BY team_name
                ORDER BY total_count DESC
                LIMIT {BAR_CHART_LIMIT}
            )
            SELECT
                ps.team_name,
                ps.player_name,
                ps.keyword,
                COUNT(*) AS keyword_count,
                MIN(ps.created_at) AS first_seen,
                MAX(ps.created_at) AS last_seen
            FROM player_stats ps
            INNER JOIN top_teams tt ON ps.team_name = tt.team_name
            GROUP BY ps.team_name, ps.player_name, ps.keyword
            ORDER BY ps.team_name, ps.keyword
        """
        
        conn = get_pg_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                data = []
                for row in rows:
                    item = dict(zip(columns, row))
                    
                    # Convert datetime objects to ISO format strings
                    if 'first_seen' in item and item['first_seen']:
                        item['first_seen'] = item['first_seen'].isoformat()
                    if 'last_seen' in item and item['last_seen']:
                        item['last_seen'] = item['last_seen'].isoformat()
                    
                    data.append(item)
        finally:
            return_pg_conn(conn)
        
        # Create response
        result = {
            "status": "success",
            "data": data,
            "count": len(data),
            "timestamp": datetime.now().isoformat()
        }
        
        # Cache the result
        _cache["data"]["value"] = result
        _cache["data"]["expires"] = now + timedelta(seconds=CACHE_TTL_SECONDS)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """
    Lấy thống kê tổng quan (Optimized + Caching)
    
    Returns:
        StatsResponse: Statistics về teams, players, keywords
    
    Raises:
        HTTPException: Khi có lỗi query database
    """
    try:
        # Check cache first
        now = datetime.now()
        cache_entry = _cache["stats"]
        
        if cache_entry["value"] and cache_entry["expires"] and now < cache_entry["expires"]:
            return cache_entry["value"]
        
        # Optimized: Single pass với parallel aggregates
        query = """
            SELECT
                COUNT(DISTINCT team_name) as total_teams,
                COUNT(DISTINCT player_name) as total_players,
                COUNT(DISTINCT keyword) as total_keywords,
                COUNT(*) as total_records
            FROM player_stats
        """
        
        conn = get_pg_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()
                
                stats = {
                    "total_teams": row[0],
                    "total_players": row[1],
                    "total_keywords": row[2],
                    "total_records": row[3],
                    "timestamp": datetime.now().isoformat()
                }
        finally:
            return_pg_conn(conn)
        
        result = {
            "status": "success",
            "stats": stats
        }
        
        # Cache the result
        _cache["stats"]["value"] = result
        _cache["stats"]["expires"] = now + timedelta(seconds=CACHE_TTL_SECONDS)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/optimize")
async def optimize_database():
    """
    Tạo indexes để tối ưu performance (chỉ chạy 1 lần)
    
    Returns:
        Dict với status và list indexes đã tạo
    
    Note:
        Chạy endpoint này để tạo indexes cho bảng player_stats.
        Indexes sẽ tăng tốc độ GROUP BY và ORDER BY queries.
    """
    conn = None
    try:
        indexes = []
        
        conn = get_pg_conn()
        with conn.cursor() as cursor:
            # Index cho team_name (dùng trong GROUP BY và ORDER BY)
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_player_stats_team 
                    ON player_stats(team_name)
                """)
                indexes.append("idx_player_stats_team")
            except Exception as e:
                print(f"Index team exists or error: {e}")
            
            # Index cho keyword (dùng trong GROUP BY và ORDER BY)
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_player_stats_keyword 
                    ON player_stats(keyword)
                """)
                indexes.append("idx_player_stats_keyword")
            except Exception as e:
                print(f"Index keyword exists or error: {e}")
            
            # Composite index cho (team_name, keyword) - tối ưu nhất
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_player_stats_team_keyword 
                    ON player_stats(team_name, keyword)
                """)
                indexes.append("idx_player_stats_team_keyword")
            except Exception as e:
                print(f"Index composite exists or error: {e}")
            
            # Index cho created_at (dùng trong MIN/MAX)
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_player_stats_created 
                    ON player_stats(created_at)
                """)
                indexes.append("idx_player_stats_created")
            except Exception as e:
                print(f"Index created_at exists or error: {e}")
            
            conn.commit()
        
        return {
            "status": "success",
            "message": "Database optimization completed",
            "indexes_created": indexes,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            return_pg_conn(conn)


# ===== Startup Event =====
@app.on_event("startup")
async def startup_event():
    """Event chạy khi server start"""
    print("\n" + "="*60)
    print("🚀 FastAPI Server Started!")
    print("="*60)
    print("📍 API Endpoints:")
    print("   - http://localhost:5000/")
    print("   - http://localhost:5000/api/health")
    print("   - http://localhost:5000/api/data")
    print("   - http://localhost:5000/api/stats")
    print("   - http://localhost:5000/api/optimize (POST)")
    print("\n📚 API Documentation:")
    print("   - Swagger UI: http://localhost:5000/docs")
    print("   - ReDoc:      http://localhost:5000/redoc")
    print("\n⚡ Performance Tip:")
    print("   - Chạy POST /api/optimize để tạo database indexes")
    print("   - Hoặc: curl -X POST http://localhost:5000/api/optimize")
    print("\n🔄 Press Ctrl+C to stop")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Run server với uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=5000,
        reload=True,  # Auto-reload khi code thay đổi
        log_level="info"
    )
