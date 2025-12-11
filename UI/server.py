"""
NUAH Trading Dashboard - FastAPI Backend

Serves the UI and provides API endpoints to query trade data from SQLite.
Includes LLM usage cost tracking endpoints.
"""

import os
import sys
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Configuration
UI_DIR = Path(__file__).parent
SQLITE_PATH = os.environ.get(
    "SQLITE_PATH",
    str(UI_DIR.parent / "fetch-data-agent" / "data" / "user_data.db")
)
LLM_USAGE_DB_PATH = os.environ.get(
    "LLM_USAGE_DB_PATH",
    str(UI_DIR.parent / "data" / "llm_usage.db")
)

# Add shared module to path for LLM logger
sys.path.insert(0, str(UI_DIR.parent))

app = FastAPI(
    title="NUAH Trading Dashboard",
    description="Real-time P&L tracking for NUAH multi-agent trading system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = UI_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@contextmanager
def get_db():
    """Context manager for SQLite database connection."""
    conn = None
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            conn.close()


def parse_pnl(pnl_value: Any) -> float:
    """Safely parse P&L value to float."""
    if pnl_value is None:
        return 0.0
    try:
        return float(pnl_value)
    except (ValueError, TypeError):
        return 0.0


def get_today_start() -> str:
    """Get today's date at midnight in ISO format."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today.isoformat()


def get_today_end() -> str:
    """Get today's date at 23:59:59 in ISO format."""
    today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    return today.isoformat()


# ============================================================================
# HTML Page Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main dashboard page."""
    index_path = UI_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")


@app.get("/graph", response_class=HTMLResponse)
@app.get("/graph.html", response_class=HTMLResponse)
async def serve_graph():
    """Serve the graph visualization page."""
    graph_path = UI_DIR / "graph.html"
    if graph_path.exists():
        return FileResponse(graph_path)
    raise HTTPException(status_code=404, detail="graph.html not found")


@app.get("/chart", response_class=HTMLResponse)
@app.get("/chart.html", response_class=HTMLResponse)
async def serve_chart():
    """Serve the chart visualization page."""
    chart_path = UI_DIR / "chart.html"
    if chart_path.exists():
        return FileResponse(chart_path)
    raise HTTPException(status_code=404, detail="chart.html not found")


@app.get("/llm-costs", response_class=HTMLResponse)
@app.get("/llm-costs.html", response_class=HTMLResponse)
async def serve_llm_costs():
    """Serve the LLM costs tracking page."""
    llm_costs_path = UI_DIR / "llm-costs.html"
    if llm_costs_path.exists():
        return FileResponse(llm_costs_path)
    raise HTTPException(status_code=404, detail="llm-costs.html not found")


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    db_exists = Path(SQLITE_PATH).exists()
    return {
        "status": "healthy",
        "database_connected": db_exists,
        "database_path": SQLITE_PATH,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/daily-summary")
async def get_daily_summary():
    """
    Get today's trading summary including total P&L, trade counts, etc.
    """
    if not Path(SQLITE_PATH).exists():
        return {
            "total_pnl": 0.0,
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "skipped_trades": 0,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
            "best_trade": None,
            "worst_trade": None,
            "success_rate": 0.0,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "message": "No database found"
        }
    
    today_start = get_today_start()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trade_executions'
        """)
        if not cursor.fetchone():
            return {
                "total_pnl": 0.0,
                "total_trades": 0,
                "successful_trades": 0,
                "failed_trades": 0,
                "skipped_trades": 0,
                "buy_count": 0,
                "sell_count": 0,
                "hold_count": 0,
                "best_trade": None,
                "worst_trade": None,
                "success_rate": 0.0,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "message": "No trade_executions table found"
            }
        
        # Get all trades today
        cursor.execute("""
            SELECT 
                trade_id, user_id, token_mint, action, amount, price,
                timestamp, pnl, confidence, reason, status, tx_hash
            FROM trade_executions
            WHERE DATE(timestamp) = DATE('now', 'localtime')
               OR DATE(created_at) = DATE('now', 'localtime')
            ORDER BY timestamp DESC
        """)
        trades = cursor.fetchall()
        
        # Calculate metrics
        total_pnl = 0.0
        successful = 0
        failed = 0
        skipped = 0
        buy_count = 0
        sell_count = 0
        hold_count = 0
        best_trade = None
        worst_trade = None
        best_pnl = float('-inf')
        worst_pnl = float('inf')
        
        for trade in trades:
            trade_dict = dict(trade)
            pnl = parse_pnl(trade_dict.get('pnl'))
            total_pnl += pnl
            
            status = (trade_dict.get('status') or '').lower()
            if status == 'completed':
                successful += 1
            elif status == 'failed':
                failed += 1
            elif status in ('skipped', 'simulated'):
                skipped += 1
            
            action = (trade_dict.get('action') or '').lower()
            if action == 'buy':
                buy_count += 1
            elif action == 'sell':
                sell_count += 1
            elif action == 'hold':
                hold_count += 1
            
            # Track best/worst trades (only for completed buy/sell)
            if status == 'completed' and action in ('buy', 'sell') and pnl != 0:
                if pnl > best_pnl:
                    best_pnl = pnl
                    best_trade = {
                        "trade_id": trade_dict.get('trade_id'),
                        "token": trade_dict.get('token_mint'),
                        "action": action,
                        "pnl": pnl
                    }
                if pnl < worst_pnl:
                    worst_pnl = pnl
                    worst_trade = {
                        "trade_id": trade_dict.get('trade_id'),
                        "token": trade_dict.get('token_mint'),
                        "action": action,
                        "pnl": pnl
                    }
        
        total_trades = len(trades)
        executed_trades = successful + failed
        success_rate = (successful / executed_trades * 100) if executed_trades > 0 else 0.0
        
        return {
            "total_pnl": round(total_pnl, 4),
            "total_trades": total_trades,
            "successful_trades": successful,
            "failed_trades": failed,
            "skipped_trades": skipped,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "hold_count": hold_count,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "success_rate": round(success_rate, 1),
            "date": datetime.now().strftime("%Y-%m-%d")
        }


@app.get("/api/trades-today")
async def get_trades_today(limit: int = 100):
    """
    Get list of all trades made today.
    """
    if not Path(SQLITE_PATH).exists():
        return {"trades": [], "count": 0}
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trade_executions'
        """)
        if not cursor.fetchone():
            return {"trades": [], "count": 0}
        
        cursor.execute("""
            SELECT 
                trade_id, user_id, token_mint, action, amount, price,
                timestamp, pnl, confidence, reason, status, tx_hash,
                error_message, created_at
            FROM trade_executions
            WHERE DATE(timestamp) = DATE('now', 'localtime')
               OR DATE(created_at) = DATE('now', 'localtime')
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        trades = []
        for row in cursor.fetchall():
            trade = dict(row)
            trade['pnl'] = parse_pnl(trade.get('pnl'))
            trade['confidence'] = float(trade.get('confidence') or 0)
            trade['amount'] = float(trade.get('amount') or 0) if trade.get('amount') else None
            trades.append(trade)
        
        return {"trades": trades, "count": len(trades)}


@app.get("/api/pnl-timeline")
async def get_pnl_timeline():
    """
    Get P&L data points over time for graphing.
    Returns hourly aggregated data for today.
    """
    if not Path(SQLITE_PATH).exists():
        return {"timeline": [], "cumulative": []}
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trade_executions'
        """)
        if not cursor.fetchone():
            return {"timeline": [], "cumulative": []}
        
        # Get trades with timestamps for today
        cursor.execute("""
            SELECT timestamp, pnl, action, status
            FROM trade_executions
            WHERE DATE(timestamp) = DATE('now', 'localtime')
               OR DATE(created_at) = DATE('now', 'localtime')
            ORDER BY timestamp ASC
        """)
        
        trades = cursor.fetchall()
        
        if not trades:
            return {"timeline": [], "cumulative": []}
        
        # Aggregate by hour
        hourly_data: Dict[int, float] = {h: 0.0 for h in range(24)}
        cumulative = []
        running_total = 0.0
        
        for trade in trades:
            trade_dict = dict(trade)
            pnl = parse_pnl(trade_dict.get('pnl'))
            timestamp = trade_dict.get('timestamp')
            
            if timestamp:
                try:
                    # Parse timestamp
                    if 'T' in str(timestamp):
                        dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(str(timestamp), "%Y-%m-%d %H:%M:%S")
                    hour = dt.hour
                    hourly_data[hour] += pnl
                except (ValueError, AttributeError):
                    pass
            
            running_total += pnl
            cumulative.append({
                "timestamp": timestamp,
                "pnl": pnl,
                "cumulative_pnl": round(running_total, 4)
            })
        
        # Convert hourly data to timeline format
        timeline = [
            {"hour": h, "label": f"{h:02d}:00", "pnl": round(hourly_data[h], 4)}
            for h in range(24)
        ]
        
        return {
            "timeline": timeline,
            "cumulative": cumulative,
            "total_pnl": round(running_total, 4)
        }


@app.get("/api/token-breakdown")
async def get_token_breakdown():
    """
    Get P&L breakdown by token for today.
    """
    if not Path(SQLITE_PATH).exists():
        return {"tokens": []}
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trade_executions'
        """)
        if not cursor.fetchone():
            return {"tokens": []}
        
        cursor.execute("""
            SELECT 
                token_mint,
                SUM(CAST(COALESCE(pnl, '0') AS REAL)) as total_pnl,
                COUNT(*) as trade_count,
                SUM(CASE WHEN action = 'buy' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN action = 'sell' THEN 1 ELSE 0 END) as sell_count
            FROM trade_executions
            WHERE (DATE(timestamp) = DATE('now', 'localtime')
               OR DATE(created_at) = DATE('now', 'localtime'))
              AND token_mint IS NOT NULL
              AND token_mint != ''
            GROUP BY token_mint
            ORDER BY total_pnl DESC
        """)
        
        tokens = []
        for row in cursor.fetchall():
            token_dict = dict(row)
            # Extract symbol from denom (factory/creator/SYMBOL -> SYMBOL)
            token_mint = token_dict.get('token_mint') or 'Unknown'
            if '/' in token_mint:
                symbol = token_mint.split('/')[-1]
            else:
                symbol = token_mint
            
            tokens.append({
                "token_mint": token_mint,
                "symbol": symbol,
                "total_pnl": round(float(token_dict.get('total_pnl') or 0), 4),
                "trade_count": int(token_dict.get('trade_count') or 0),
                "buy_count": int(token_dict.get('buy_count') or 0),
                "sell_count": int(token_dict.get('sell_count') or 0)
            })
        
        return {"tokens": tokens}


@app.get("/api/action-breakdown")
async def get_action_breakdown():
    """
    Get breakdown of trades by action type (buy/sell/hold) for today.
    """
    if not Path(SQLITE_PATH).exists():
        return {"actions": []}
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trade_executions'
        """)
        if not cursor.fetchone():
            return {"actions": []}
        
        cursor.execute("""
            SELECT 
                action,
                COUNT(*) as count,
                SUM(CAST(COALESCE(pnl, '0') AS REAL)) as total_pnl,
                AVG(confidence) as avg_confidence
            FROM trade_executions
            WHERE DATE(timestamp) = DATE('now', 'localtime')
               OR DATE(created_at) = DATE('now', 'localtime')
            GROUP BY action
        """)
        
        actions = []
        for row in cursor.fetchall():
            action_dict = dict(row)
            actions.append({
                "action": action_dict.get('action') or 'unknown',
                "count": int(action_dict.get('count') or 0),
                "total_pnl": round(float(action_dict.get('total_pnl') or 0), 4),
                "avg_confidence": round(float(action_dict.get('avg_confidence') or 0), 2)
            })
        
        return {"actions": actions}


@app.get("/api/status-breakdown")
async def get_status_breakdown():
    """
    Get breakdown of trades by status (completed/failed/skipped) for today.
    """
    if not Path(SQLITE_PATH).exists():
        return {"statuses": []}
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trade_executions'
        """)
        if not cursor.fetchone():
            return {"statuses": []}
        
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(CAST(COALESCE(pnl, '0') AS REAL)) as total_pnl
            FROM trade_executions
            WHERE DATE(timestamp) = DATE('now', 'localtime')
               OR DATE(created_at) = DATE('now', 'localtime')
            GROUP BY status
        """)
        
        statuses = []
        for row in cursor.fetchall():
            status_dict = dict(row)
            statuses.append({
                "status": status_dict.get('status') or 'unknown',
                "count": int(status_dict.get('count') or 0),
                "total_pnl": round(float(status_dict.get('total_pnl') or 0), 4)
            })
        
        return {"statuses": statuses}


@app.get("/api/user-breakdown")
async def get_user_breakdown():
    """
    Get P&L breakdown by user for today.
    """
    if not Path(SQLITE_PATH).exists():
        return {"users": []}
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trade_executions'
        """)
        if not cursor.fetchone():
            return {"users": []}
        
        cursor.execute("""
            SELECT 
                user_id,
                COUNT(*) as trade_count,
                SUM(CAST(COALESCE(pnl, '0') AS REAL)) as total_pnl,
                SUM(CASE WHEN action = 'buy' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN action = 'sell' THEN 1 ELSE 0 END) as sell_count,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count
            FROM trade_executions
            WHERE DATE(timestamp) = DATE('now', 'localtime')
               OR DATE(created_at) = DATE('now', 'localtime')
            GROUP BY user_id
            ORDER BY total_pnl DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            user_dict = dict(row)
            users.append({
                "user_id": int(user_dict.get('user_id') or 0),
                "trade_count": int(user_dict.get('trade_count') or 0),
                "total_pnl": round(float(user_dict.get('total_pnl') or 0), 4),
                "buy_count": int(user_dict.get('buy_count') or 0),
                "sell_count": int(user_dict.get('sell_count') or 0),
                "completed_count": int(user_dict.get('completed_count') or 0)
            })
        
        return {"users": users}


# ============================================================================
# LLM Usage/Cost Tracking Endpoints
# ============================================================================

def get_llm_db():
    """Get a connection to the LLM usage database."""
    if not Path(LLM_USAGE_DB_PATH).exists():
        return None
    conn = sqlite3.connect(LLM_USAGE_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/api/llm/daily-summary")
async def get_llm_daily_summary(date: Optional[str] = None):
    """
    Get LLM usage summary for a specific date (defaults to today).
    
    Returns total cost, token counts, success rate, and breakdowns by agent/model.
    """
    conn = get_llm_db()
    if conn is None:
        return {
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
            "avg_duration_ms": 0.0,
            "successful_requests": 0,
            "success_rate": 100.0,
            "by_agent": [],
            "by_model": [],
            "message": "No LLM usage database found"
        }
    
    try:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='llm_usage'
        """)
        if not cursor.fetchone():
            return {
                "date": date,
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": 0.0,
                "avg_duration_ms": 0.0,
                "successful_requests": 0,
                "success_rate": 100.0,
                "by_agent": [],
                "by_model": [],
                "message": "No llm_usage table found"
            }
        
        # Total summary
        cursor.execute("""
            SELECT 
                COUNT(*) as total_requests,
                COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                COALESCE(SUM(cost_usd), 0) as total_cost,
                COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests
            FROM llm_usage
            WHERE date(timestamp) = ?
        """, (date,))
        
        row = cursor.fetchone()
        
        total_requests = row["total_requests"] or 0
        successful_requests = row["successful_requests"] or 0
        
        # By agent breakdown
        cursor.execute("""
            SELECT 
                agent,
                COUNT(*) as requests,
                COALESCE(SUM(cost_usd), 0) as cost,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens
            FROM llm_usage
            WHERE date(timestamp) = ?
            GROUP BY agent
            ORDER BY cost DESC
        """, (date,))
        
        agents = [dict(r) for r in cursor.fetchall()]
        
        # By model breakdown
        cursor.execute("""
            SELECT 
                model,
                COUNT(*) as requests,
                COALESCE(SUM(cost_usd), 0) as cost,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens
            FROM llm_usage
            WHERE date(timestamp) = ?
            GROUP BY model
            ORDER BY cost DESC
        """, (date,))
        
        models = [dict(r) for r in cursor.fetchall()]
        
        return {
            "date": date,
            "total_requests": total_requests,
            "total_input_tokens": row["total_input_tokens"] or 0,
            "total_output_tokens": row["total_output_tokens"] or 0,
            "total_cost_usd": round(row["total_cost"] or 0, 6),
            "avg_duration_ms": round(row["avg_duration_ms"] or 0, 2),
            "successful_requests": successful_requests,
            "success_rate": round(
                successful_requests / max(1, total_requests) * 100, 
                1
            ),
            "by_agent": agents,
            "by_model": models
        }
    finally:
        conn.close()


@app.get("/api/llm/hourly-costs")
async def get_llm_hourly_costs(date: Optional[str] = None):
    """
    Get hourly LLM cost breakdown for charting.
    """
    conn = get_llm_db()
    if conn is None:
        return {"hourly": [], "date": date or datetime.now().strftime("%Y-%m-%d")}
    
    try:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='llm_usage'
        """)
        if not cursor.fetchone():
            return {"hourly": [], "date": date}
        
        cursor.execute("""
            SELECT 
                strftime('%H', timestamp) as hour,
                COUNT(*) as requests,
                COALESCE(SUM(cost_usd), 0) as cost,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens
            FROM llm_usage
            WHERE date(timestamp) = ?
            GROUP BY strftime('%H', timestamp)
            ORDER BY hour
        """, (date,))
        
        hourly = [dict(row) for row in cursor.fetchall()]
        
        return {"hourly": hourly, "date": date}
    finally:
        conn.close()


@app.get("/api/llm/cost-timeline")
async def get_llm_cost_timeline(days: int = Query(default=7, ge=1, le=90)):
    """
    Get daily LLM cost breakdown for the last N days.
    """
    conn = get_llm_db()
    if conn is None:
        return {"timeline": [], "days": days}
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='llm_usage'
        """)
        if not cursor.fetchone():
            return {"timeline": [], "days": days}
        
        cursor.execute("""
            SELECT 
                date(timestamp) as date,
                COUNT(*) as requests,
                COALESCE(SUM(cost_usd), 0) as cost,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens
            FROM llm_usage
            WHERE timestamp >= datetime('now', ?)
            GROUP BY date(timestamp)
            ORDER BY date
        """, (f"-{days} days",))
        
        timeline = [dict(row) for row in cursor.fetchall()]
        
        return {"timeline": timeline, "days": days}
    finally:
        conn.close()


@app.get("/api/llm/recent-usage")
async def get_llm_recent_usage(limit: int = Query(default=100, ge=1, le=500)):
    """
    Get recent LLM usage records.
    """
    conn = get_llm_db()
    if conn is None:
        return {"usage": [], "count": 0}
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='llm_usage'
        """)
        if not cursor.fetchone():
            return {"usage": [], "count": 0}
        
        cursor.execute("""
            SELECT 
                id, timestamp, agent, model, user_id,
                input_tokens, output_tokens, cost_usd,
                request_summary, response_summary,
                duration_ms, success, error_message
            FROM llm_usage
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        usage = []
        for row in cursor.fetchall():
            record = dict(row)
            record['success'] = bool(record.get('success', 1))
            usage.append(record)
        
        return {"usage": usage, "count": len(usage)}
    finally:
        conn.close()


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                 NUAH Trading Dashboard                        ║
╠══════════════════════════════════════════════════════════════╣
║  Starting server...                                           ║
║  Database: {SQLITE_PATH[:50]}...
║                                                               ║
║  Open http://localhost:8501 in your browser                   ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8501,
        reload=True,
        log_level="info"
    )


