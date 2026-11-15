"""
Automated Alert Scheduler for News Analyzer
Monitors the Red Folder economic calendar and automatically dispatches:
1. Weekly Radar Kickoff (Mondays / Start of week)
2. T-60 Minutes Pre-News Alert (Forecast + Live Market Pulse)
3. T+5 Minutes Post-News Flash Alert (Actual Release Reaction)
Prevents duplicate alerts using persistent history in data/calendar/alert_history.json.
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = PROJECT_ROOT / "data" / "calendar" / "alert_history.json"

try:
    from scripts.calendar_fetcher import get_calendar_events, BKK_TZ
    from scripts.analyzer import analyze_forecast, analyze_flash
    from scripts.discord_notifier import (
        format_forecast_embed,
        format_flash_embed,
        format_weekly_radar_embed,
        send_discord_payload,
        load_webhook_url
    )
except ImportError:
    from calendar_fetcher import get_calendar_events, BKK_TZ
    from analyzer import analyze_forecast, analyze_flash
    from discord_notifier import (
        format_forecast_embed,
        format_flash_embed,
        format_weekly_radar_embed,
        send_discord_payload,
        load_webhook_url
    )


def load_alert_history() -> dict:
    """Load sent alert history."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"weekly_sent": [], "forecast_sent": {}, "flash_sent": {}}
    return {"weekly_sent": [], "forecast_sent": {}, "flash_sent": {}}


def save_alert_history(history: dict):
    """Save sent alert history."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def check_and_send_weekly_radar(history: dict, webhook_url: str = None) -> bool:
    """Check if weekly radar should be dispatched for this week."""
    now_bkk = datetime.now(BKK_TZ)
    # Week identifier e.g. "2026-W46"
    week_id = now_bkk.strftime("%Y-W%W")
    
    if week_id in history.get("weekly_sent", []):
        return False
        
    # Check if Monday or forced check
    # Send on Monday or if never sent for this week
    print(f"[Scheduler] Dispatching Weekly Radar for {week_id}...")
    events = get_calendar_events(force_refresh=True, high_only=True)
    payload = format_weekly_radar_embed(events)
    
    ok, msg = send_discord_payload(payload, webhook_url)
    print(f"[Scheduler] Weekly Radar Dispatch: {msg}")
    
    if ok:
        if "weekly_sent" not in history:
            history["weekly_sent"] = []
        history["weekly_sent"].append(week_id)
        save_alert_history(history)
        return True
    return False


def check_and_send_pre_news_alerts(events: list, history: dict, webhook_url: str = None) -> int:
    """
    Check for events occurring within 10 to 65 minutes.
    Dispatch T-60 pre-news forecast embed with live market pulse.
    """
    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()
    forecast_sent = history.get("forecast_sent", {})
    sent_count = 0
    
    for event in events:
        if not event.get("is_red_folder"):
            continue
            
        event_id = str(event.get("id") or f"{event['title']}_{event['date_utc']}")
        event_ts = event.get("timestamp_utc", 0)
        seconds_until = event_ts - now_ts
        minutes_until = seconds_until / 60
        
        # Trigger window: Between 5 and 65 minutes before event
        if 5 <= minutes_until <= 65:
            if event_id not in forecast_sent:
                print(f"[Scheduler] 🔴 T-60 Alert Triggered for: {event['title']} ({minutes_until:.1f} mins away)")
                
                # Generate forecast with live market pulse
                analysis = analyze_forecast(
                    event_name=event["title"],
                    consensus=str(event["forecast"]) if event.get("forecast") is not None else None,
                    previous=str(event["previous"]) if event.get("previous") is not None else None,
                    period=str(event.get("period", ""))
                )
                
                payload = format_forecast_embed(analysis)
                ok, msg = send_discord_payload(payload, webhook_url)
                print(f"[Scheduler] Forecast Alert Dispatch: {msg}")
                
                if ok:
                    forecast_sent[event_id] = {
                        "event": event["title"],
                        "triggered_at": now_utc.isoformat(),
                        "time_bkk": event.get("date_bkk")
                    }
                    history["forecast_sent"] = forecast_sent
                    save_alert_history(history)
                    sent_count += 1
                    
    return sent_count


def check_and_send_post_news_flashes(events: list, history: dict, webhook_url: str = None) -> int:
    """
    Check for events that passed within the last 30 minutes with actual figures.
    """
    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()
    flash_sent = history.get("flash_sent", {})
    sent_count = 0
    
    for event in events:
        if not event.get("is_red_folder"):
            continue
            
        event_id = str(event.get("id") or f"{event['title']}_{event['date_utc']}")
        event_ts = event.get("timestamp_utc", 0)
        seconds_passed = now_ts - event_ts
        minutes_passed = seconds_passed / 60
        
        # Trigger window: Between 2 and 35 minutes after event release
        if 2 <= minutes_passed <= 35:
            if event_id not in flash_sent:
                actual = event.get("actual")
                if actual is not None and str(actual).strip() != "":
                    print(f"[Scheduler] ⚡ T+5 Flash Triggered for: {event['title']} (Actual: {actual})")
                    
                    flash = analyze_flash(
                        event_name=event["title"],
                        actual=str(actual),
                        consensus=str(event.get("forecast", "N/A")),
                        previous=str(event.get("previous", "N/A"))
                    )
                    
                    payload = format_flash_embed(flash)
                    ok, msg = send_discord_payload(payload, webhook_url)
                    print(f"[Scheduler] Flash Alert Dispatch: {msg}")
                    
                    if ok:
                        flash_sent[event_id] = {
                            "event": event["title"],
                            "actual": str(actual),
                            "triggered_at": now_utc.isoformat()
                        }
                        history["flash_sent"] = flash_sent
                        save_alert_history(history)
                        sent_count += 1
                        
    return sent_count


def run_scheduler_tick(webhook_url: str = None) -> dict:
    """Run a single check pass across calendar, T-60 alerts, and T+5 flashes."""
    now_bkk = datetime.now(BKK_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_bkk} BKK] Checking economic events...")
    
    history = load_alert_history()
    events = get_calendar_events(high_only=True)
    
    pre_count = check_and_send_pre_news_alerts(events, history, webhook_url)
    flash_count = check_and_send_post_news_flashes(events, history, webhook_url)
    
    return {
        "status": "ok",
        "timestamp": now_bkk,
        "pre_alerts_sent": pre_count,
        "flash_alerts_sent": flash_count,
        "events_monitored": len(events)
    }


def main():
    parser = argparse.ArgumentParser(description="Automated Alert Scheduler for News Analyzer")
    parser.add_argument("--check-once", action="store_true", help="Run a single check and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuous background loop")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds (default: 60s)")
    parser.add_argument("--send-weekly", action="store_true", help="Force send weekly radar now")
    parser.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    args = parser.parse_args()
    
    history = load_alert_history()
    
    if args.send_weekly:
        check_and_send_weekly_radar(history, args.webhook)
        return
        
    if args.check_once:
        result = run_scheduler_tick(args.webhook)
        print(f"Check Complete: {result['events_monitored']} events monitored. Pre-alerts: {result['pre_alerts_sent']}, Flash: {result['flash_alerts_sent']}")
        return
        
    if args.daemon:
        print(f"[*] Starting News Analyzer Alert Daemon (interval: {args.interval}s)...")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                run_scheduler_tick(args.webhook)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[!] Daemon stopped by user.")
    else:
        # Default behavior: run check-once
        result = run_scheduler_tick(args.webhook)
        print(f"Check Complete: {result['events_monitored']} events monitored. Pre-alerts: {result['pre_alerts_sent']}, Flash: {result['flash_alerts_sent']}")


if __name__ == "__main__":
    main()
