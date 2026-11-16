"""
Economic Calendar Fetcher for News Analyzer
Fetches Tier-1 / Red Folder US Economic News using TradingView & ForexFactory data
with local caching, timezone conversion (NY & Bangkok), and filtering.
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
CACHE_DIR = PROJECT_ROOT / "data" / "calendar"
CACHE_FILE = CACHE_DIR / "cache_events.json"


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "cache_duration_hours": 3,
        "high_impact_keywords": [
            "cpi", "pce", "nonfarm", "payroll", "unemployment", "fomc", 
            "interest rate", "powell", "gdp", "ppi", "retail sales", 
            "ism", "jobless claims"
        ]
    }


def get_ny_timezone(dt_utc: datetime) -> timezone:
    """Return EDT (UTC-4) or EST (UTC-5) depending on US daylight saving time."""
    year = dt_utc.year
    march_1 = datetime(year, 3, 1, 2, 0, tzinfo=timezone.utc)
    dst_start = march_1 + timedelta(days=(6 - march_1.weekday()) % 7 + 7)
    nov_1 = datetime(year, 11, 1, 2, 0, tzinfo=timezone.utc)
    dst_end = nov_1 + timedelta(days=(6 - nov_1.weekday()) % 7)
    
    if dst_start <= dt_utc < dst_end:
        return timezone(timedelta(hours=-4), name="EDT")
    return timezone(timedelta(hours=-5), name="EST")


BKK_TZ = timezone(timedelta(hours=7), name="BKK")


def parse_date_to_utc(date_str: str) -> datetime:
    """Parse various ISO date strings to UTC datetime."""
    # Handle '2026-11-15T16:30:00-05:00' or '2026-11-16T13:30:00.000Z'
    clean_str = date_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean_str)
        return dt.astimezone(timezone.utc)
    except Exception:
        # Fallback format parsing
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(clean_str[:19], fmt[: len(clean_str[:19])])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                continue
    return datetime.now(timezone.utc)


def format_relative_time(target_utc: datetime, now_utc: datetime) -> str:
    """Format human readable countdown or elapsed time."""
    delta = target_utc - now_utc
    total_seconds = int(delta.total_seconds())
    
    if total_seconds > 0:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 24:
            days = hours // 24
            rem_hours = hours % 24
            return f"in {days}d {rem_hours}h"
        elif hours > 0:
            return f"in {hours}h {minutes}m"
        else:
            return f"in {minutes}m (UPCOMING)"
    else:
        past_seconds = abs(total_seconds)
        hours = past_seconds // 3600
        minutes = (past_seconds % 3600) // 60
        if hours > 24:
            days = hours // 24
            return f"{days}d ago"
        elif hours > 0:
            return f"{hours}h {minutes}m ago"
        else:
            return f"{minutes}m ago (RELEASED)"


def is_high_impact(event: dict, keywords: list) -> bool:
    """Determine if an event is high impact (Red Folder)."""
    importance = event.get("importance")
    if importance == 1 or str(importance).lower() in ("1", "high"):
        return True
        
    impact = event.get("impact", "")
    if str(impact).lower() == "high":
        return True
        
    title = event.get("title", "").lower()
    indicator = event.get("indicator", "").lower()
    
    for kw in keywords:
        if kw in title or kw in indicator:
            return True
            
    return False


def fetch_from_tradingview(days_back=1, days_forward=8):
    """Fetch US economic calendar from TradingView endpoint."""
    now = datetime.now(timezone.utc)
    start_dt = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000Z")
    end_dt = (now + timedelta(days=days_forward)).strftime("%Y-%m-%dT23:59:59.000Z")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }
    params = {
        "from": start_dt,
        "to": end_dt,
        "countries": "US",
    }
    
    url = "https://economic-calendar.tradingview.com/events"
    resp = requests.get(url, headers=headers, params=params, timeout=12)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", [])


def fetch_from_forexfactory():
    """Fallback fetch from ForexFactory JSON."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    raw_events = resp.json()
    
    normalized = []
    for item in raw_events:
        if item.get("country") == "USD":
            actual_val = item.get("actual")
            if actual_val == "" or actual_val is None:
                actual_val = None
            normalized.append({
                "id": f"ff_{item.get('title')}_{item.get('date')}",
                "title": item.get("title"),
                "indicator": item.get("title"),
                "country": "US",
                "importance": 1 if item.get("impact") == "High" else 0,
                "impact": item.get("impact"),
                "previous": item.get("previous"),
                "forecast": item.get("forecast"),
                "actual": actual_val,
                "date": item.get("date"),
                "comment": "ForexFactory High Impact Event",
                "source": "ForexFactory",
                "source_url": "https://www.forexfactory.com/calendar"
            })
    return normalized


def calculate_deviation(actual_val, forecast_val) -> dict:
    """
    Calculate numerical difference (Actual - Forecast) and determine if BEAT / MISS / IN_LINE.
    Handles '%', 'k', 'K', 'M', 'B', etc.
    """
    if actual_val is None or forecast_val is None:
        return {"delta": None, "delta_str": "-", "direction": "UNKNOWN"}
        
    s_act = str(actual_val).strip()
    s_fc = str(forecast_val).strip()
    
    if not s_act or not s_fc or s_act in ("-", "N/A") or s_fc in ("-", "N/A"):
        return {"delta": None, "delta_str": "-", "direction": "UNKNOWN"}
        
    try:
        suffix = ""
        for u in ("%", "k", "K", "M", "B", "T"):
            if u in s_act or u in s_fc:
                suffix = u
                break
                
        def clean_num(s):
            for ch in ("%", "k", "K", "M", "B", "T", ",", " "):
                s = s.replace(ch, "")
            return float(s)
            
        n_act = clean_num(s_act)
        n_fc = clean_num(s_fc)
        delta = n_act - n_fc
        
        if abs(delta) >= 10:
            delta_str = f"{delta:+.0f}{suffix}"
        elif abs(delta) >= 1:
            delta_str = f"{delta:+.1f}{suffix}"
        else:
            delta_str = f"{delta:+.2f}{suffix}"
            
        tolerance = 0.05 * abs(n_fc if n_fc != 0 else 1)
        if abs(delta) < tolerance:
            direction = "IN_LINE"
        elif delta > 0:
            direction = "BEAT"
        else:
            direction = "MISS"
            
        return {
            "delta": delta,
            "delta_str": delta_str,
            "direction": direction,
            "actual_num": n_act,
            "forecast_num": n_fc,
            "suffix": suffix
        }
    except Exception:
        return {"delta": None, "delta_str": "-", "direction": "UNKNOWN"}


def fetch_actual_fast(event_title=None) -> dict:
    """
    High-speed, low-timeout fetch specifically designed to check recent actual releases.
    Bypasses standard 3-hour cache and merges any newly found actual into the cache.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }
    now = datetime.now(timezone.utc)
    start_dt = (now - timedelta(hours=2)).strftime("%Y-%m-%dT00:00:00.000Z")
    end_dt = (now + timedelta(hours=2)).strftime("%Y-%m-%dT23:59:59.000Z")
    
    params = {
        "from": start_dt,
        "to": end_dt,
        "countries": "US",
    }
    
    new_actuals = {}
    
    # 1. Fast check TradingView
    try:
        url = "https://economic-calendar.tradingview.com/events"
        resp = requests.get(url, headers=headers, params=params, timeout=4)
        if resp.status_code == 200:
            for item in resp.json().get("result", []):
                act = item.get("actual")
                if act is not None and str(act).strip() != "":
                    t = item.get("title", "").strip().lower()
                    new_actuals[t] = act
    except Exception:
        pass
        
    # 2. Fast check ForexFactory if TradingView has no actuals
    if not new_actuals:
        try:
            ff_headers = {"User-Agent": "Mozilla/5.0"}
            ff_url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            ff_resp = requests.get(ff_url, headers=ff_headers, timeout=4)
            if ff_resp.status_code == 200:
                for item in ff_resp.json():
                    if item.get("country") == "USD":
                        act = item.get("actual")
                        if act is not None and str(act).strip() != "":
                            t = item.get("title", "").strip().lower()
                            new_actuals[t] = act
        except Exception:
            pass
            
    # Update cache_events.json in-place
    if new_actuals and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            updated = False
            for item in cached_data:
                t = item.get("title", "").strip().lower()
                for match_title, act_val in new_actuals.items():
                    if match_title in t or t in match_title:
                        if item.get("actual") != act_val:
                            item["actual"] = act_val
                            updated = True
            if updated:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cached_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
    return new_actuals


def get_calendar_events(force_refresh=False, high_only=True):
    """Retrieve calendar events, using cache if fresh."""
    config = load_config()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    cache_duration_secs = config.get("cache_duration_hours", 3) * 3600
    cache_valid = False
    raw_events = []
    
    if not force_refresh and CACHE_FILE.exists():
        try:
            mtime = CACHE_FILE.stat().st_mtime
            if time.time() - mtime < cache_duration_secs:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    raw_events = json.load(f)
                    cache_valid = True
        except Exception:
            cache_valid = False

    # Proactive Live Sniping: If cache is valid but an event occurred recently (<30 mins) without actual, check fast
    if not force_refresh and cache_valid and raw_events:
        now_ts = datetime.now(timezone.utc).timestamp()
        needs_quick_check = False
        for it in raw_events:
            dt = parse_date_to_utc(it.get("date", "")).timestamp()
            if 0 <= (now_ts - dt) <= 1800 and it.get("actual") is None:
                needs_quick_check = True
                break
        if needs_quick_check:
            new_acts = fetch_actual_fast()
            if new_acts:
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        raw_events = json.load(f)
                except Exception:
                    pass
    
    if not force_refresh and CACHE_FILE.exists():
        try:
            mtime = CACHE_FILE.stat().st_mtime
            if time.time() - mtime < cache_duration_secs:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    raw_events = json.load(f)
                    cache_valid = True
        except Exception:
            cache_valid = False
            
    if not cache_valid:
        try:
            raw_events = fetch_from_tradingview()
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(raw_events, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # Fallback to ForexFactory or stale cache
            try:
                raw_events = fetch_from_forexfactory()
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(raw_events, f, ensure_ascii=False, indent=2)
            except Exception:
                if CACHE_FILE.exists():
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        raw_events = json.load(f)
                else:
                    raw_events = []

    # Process and normalize events
    now_utc = datetime.now(timezone.utc)
    keywords = config.get("high_impact_keywords", [])
    
    processed = []
    for item in raw_events:
        is_red = is_high_impact(item, keywords)
        if high_only and not is_red:
            continue
            
        dt_utc = parse_date_to_utc(item.get("date", ""))
        ny_tz = get_ny_timezone(dt_utc)
        dt_ny = dt_utc.astimezone(ny_tz)
        dt_bkk = dt_utc.astimezone(BKK_TZ)
        
        status = "PASSED" if dt_utc < now_utc else "UPCOMING"
        relative_str = format_relative_time(dt_utc, now_utc)
        
        date_bkk_formatted = f"{dt_bkk.strftime('%Y-%m-%d %H:%M')} น. (ไทย)"
        time_bkk_short_formatted = f"{dt_bkk.strftime('%d/%m %H:%M')} น."
        
        processed.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "indicator": item.get("indicator", item.get("title")),
            "is_red_folder": is_red,
            "importance": item.get("importance", 0),
            "date_utc": dt_utc.isoformat(),
            "date_ny": dt_ny.strftime("%Y-%m-%d %I:%M %p %Z"),
            "date_bkk": date_bkk_formatted,
            "time_bkk_short": time_bkk_short_formatted,
            "timestamp_utc": dt_utc.timestamp(),
            "time_relative": relative_str,
            "status": status,
            "previous": item.get("previous"),
            "forecast": item.get("forecast"),
            "actual": item.get("actual"),
            "period": item.get("period", item.get("referencePeriod")),
            "comment": item.get("comment", ""),
            "source": item.get("source", ""),
            "source_url": item.get("source_url", "")
        })
        
    # Sort chronologically
    processed.sort(key=lambda x: x["timestamp_utc"])
    return processed


def print_cli_table(events):
    """Print clean formatted table to stdout."""
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="🔴 Red Folder US Economic Calendar (News Analyzer)", show_lines=True)
        table.add_column("Status / Relative", style="bold yellow", width=18)
        table.add_column("Event Title", style="bold white", width=32)
        table.add_column("Thai Time (BKK)", style="cyan", width=22)
        table.add_column("NY Time (ET)", style="magenta", width=20)
        table.add_column("Consensus", justify="right", style="green", width=12)
        table.add_column("Previous", justify="right", style="dim", width=12)
        table.add_column("Actual", justify="right", style="bold red", width=12)
        
        for e in events:
            actual_str = str(e["actual"]) if e["actual"] is not None else "-"
            forecast_str = str(e["forecast"]) if e["forecast"] is not None else "-"
            previous_str = str(e["previous"]) if e["previous"] is not None else "-"
            
            status_style = "[green]" if "ago" in e["time_relative"] else "[yellow bold]"
            rel_display = f"{status_style}{e['time_relative']}[/]"
            
            table.add_row(
                rel_display,
                e["title"],
                e["date_bkk"],
                e["date_ny"],
                forecast_str,
                previous_str,
                actual_str
            )
        console.print(table)
    except ImportError:
        # Standard ASCII format
        print(f"{'STATUS':<16} | {'EVENT':<30} | {'BKK TIME':<22} | {'FORECAST':<10} | {'PREV':<10}")
        print("-" * 95)
        for e in events:
            print(f"{e['time_relative']:<16} | {e['title'][:29]:<30} | {e['date_bkk']:<22} | {str(e['forecast']):<10} | {str(e['previous']):<10}")


def main():
    parser = argparse.ArgumentParser(description="Economic Calendar Fetcher for News Analyzer")
    parser.add_argument("--refresh", action="store_true", help="Force refresh cache from API")
    parser.add_argument("--all", action="store_true", help="Show all USD events (not just Red Folder high impact)")
    parser.add_argument("--today", action="store_true", help="Filter events for today only")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()
    
    events = get_calendar_events(force_refresh=args.refresh, high_only=not args.all)
    
    if args.today:
        now_bkk = datetime.now(BKK_TZ).date()
        events = [e for e in events if datetime.fromtimestamp(e["timestamp_utc"], tz=BKK_TZ).date() == now_bkk]
        
    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
    else:
        print_cli_table(events)


if __name__ == "__main__":
    main()
