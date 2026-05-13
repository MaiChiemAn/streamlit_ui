"""
Configuration file for API Server
Centralized settings for database queries and API behavior
"""

# ===== Chart Configuration =====
TOP_N_TEAMS = 30  # Number of top teams to show in bar chart

# ===== Cache Configuration =====
CACHE_TTL_SECONDS = 3  # Cache TTL in seconds

# ===== Database Query Limits =====
# Bar chart shows top N teams
BAR_CHART_LIMIT = TOP_N_TEAMS

# Bubble chart shows all teams (no limit)
BUBBLE_CHART_LIMIT = None  # None means no limit

# ===== Color Configuration =====
# Number of unique colors for teams (bubble chart)
TEAM_COLORS_COUNT = 50
