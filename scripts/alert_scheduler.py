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
    from scripts.calendar_fetcher import get_calendar_events, BKK_TZ, fetch_actual_fast
    from scripts.analyzer import analyze_forecast, analyze_flash
    from scripts.discord_notifier import (
        format_forecast_embed,
        format_flash_embed,
        format_weekly_radar_embed,
        send_discord_payload,
        load_webhook_url
    )
except ImportError:
    from calendar_fetcher import get_calendar_events, BKK_TZ, fetch_actual_fast
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


def get_adaptive_interval(events: list, default_interval: int = 60) -> tuple[int, str]:
    """
    Calculate dynamic sleep interval based on user specifications:
    1. ช่วงข่าวออก ([-3 mins, +3 mins]): เช็คทุก 5 วินาที (Active Sniping)
    2. ก่อนข่าวออก 1 ชม. ([-60 mins, -3 mins]): เช็คทุก 5 นาที (300 วินาที)
    3. เวลาปกติ (ไม่มีข่าวใน 1 ชม.): เช็คทุก 15 นาที หรือคำนวณจนถึง T-60m
    
    Returns: (sleep_seconds, mode_description)
    """
    now_ts = datetime.now(timezone.utc).timestamp()
    rf_events = [e for e in events if e.get("is_red_folder")]
    if not rf_events:
        return 900, "IDLE (No Red Folder events found | Sleep 15m)"
        
    nearest_diff = None
    nearest_event = None
    
    for e in rf_events:
        e_ts = e.get("timestamp_utc", 0)
        diff = now_ts - e_ts  # negative = upcoming, positive = passed
        
        # 1. Active Sniping Window: 3 mins before (-180s) to 3 mins after (+180s)
        if -180 <= diff <= 180:
            if e.get("actual") is None:
                return 5, f"🚀 SNIPING (Active News Window: {e['title']} | T{diff:+.0f}s | Poll every 5s)"
                
        # If slightly delayed (3 to 10 mins after release) and still awaiting actual
        if 180 < diff <= 600 and e.get("actual") is None:
            return 10, f"⏳ SNIPING_DELAYED (Waiting for delayed actual: {e['title']} | T+{diff:.0f}s | Poll every 10s)"
            
        # Find next upcoming event
        if diff < 0:
            if nearest_diff is None or diff > nearest_diff:
                nearest_diff = diff
                nearest_event = e

    # 2. Pre-News Watch Window: 1 hour before (-3600s) to 3 mins before (-180s)
    if nearest_diff is not None:
        secs_until = abs(nearest_diff)
        mins_until = secs_until / 60
        
        if 180 < secs_until <= 3600:
            # Within 1 hour before news: check every 5 minutes (300s)
            # Ensure we do not sleep past the start of the 3-minute sniping window
            sleep_time = min(300, max(5, int(secs_until - 180)))
            return sleep_time, f"👀 PRE_NEWS (Next: {nearest_event['title']} in {mins_until:.1f}m | Check every 5m)"
            
        # More than 1 hour away:
        # Sleep until T-60m window starts, capped at 15 minutes (900s) to keep schedule fresh
        secs_until_t60 = secs_until - 3600
        sleep_time = min(900, max(60, int(secs_until_t60)))
        return sleep_time, f"💤 NORMAL (Next: {nearest_event['title']} in {mins_until:.1f}m | Sleep {sleep_time//60}m)"

    return 900, "IDLE (All today's events completed | Sleep 15m)"


def get_sniping_interval(events: list, default_interval: int = 60) -> int:
    """Compatibility wrapper returning integer sleep seconds."""
    secs, _ = get_adaptive_interval(events, default_interval)
    return secs


def check_and_send_post_news_flashes(events: list, history: dict, webhook_url: str = None) -> int:
    """
    Check for events that passed or are currently in release window ([-3 mins, +45 mins]).
    During [-3 mins, +5 mins], enters active 5-second polling loop to catch the release in real time!
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
        diff_secs = now_ts - event_ts  # negative: upcoming, positive: passed
        minutes_passed = diff_secs / 60
        
        if event_id in flash_sent:
            continue
            
        actual = event.get("actual")
        
        # 1. Critical Active Sniping: If within [-3 mins, +5 mins] and actual not yet found
        if -180 <= diff_secs <= 300 and (actual is None or str(actual).strip() == ""):
            print(f"[Scheduler] 🎯 Active Sniping Window: {event['title']} (T{diff_secs:+.0f}s). Polling every 5s...")
            start_loop = time.time()
            max_loop_secs = 360  # max 6 minutes wait
            while time.time() - start_loop < max_loop_secs:
                loop_now_ts = datetime.now(timezone.utc).timestamp()
                loop_diff = loop_now_ts - event_ts
                
                # Check actual once release time is near or reached
                if loop_diff >= -10:
                    new_acts = fetch_actual_fast(event["title"])
                    act_candidate = new_acts.get(event["title"].lower())
                    if act_candidate is not None and str(act_candidate).strip() != "":
                        actual = act_candidate
                        print(f"[Scheduler] ⚡ Captured actual for {event['title']}: {actual} (at T{loop_diff:+.0f}s)")
                        break
                        
                time.sleep(5)
                
        # 2. General Check: If event released within the last 45 minutes and actual is missing
        if 0 <= minutes_passed <= 45 and (actual is None or str(actual).strip() == ""):
            new_acts = fetch_actual_fast(event["title"])
            actual = new_acts.get(event["title"].lower())
            
        # 3. If actual is present and within [-3m, 45m], dispatch flash report!
        if actual is not None and str(actual).strip() != "" and -3 <= minutes_passed <= 45:
            print(f"[Scheduler] ⚡ [INSTANT FLASH] Triggered for: {event['title']} (Actual: {actual})")
            
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
                    "triggered_at": datetime.now(timezone.utc).isoformat()
                }
                history["flash_sent"] = flash_sent
                save_alert_history(history)
                sent_count += 1
                
    return sent_count


def run_scheduler_tick(webhook_url: str = None) -> dict:
    """Run a single check pass across calendar, T-60 alerts, and instant flashes."""
    now_bkk = datetime.now(BKK_TZ).strftime("%Y-%m-%d %H:%M:%S")
    
    history = load_alert_history()
    events = get_calendar_events(high_only=True)
    
    pre_count = check_and_send_pre_news_alerts(events, history, webhook_url)
    flash_count = check_and_send_post_news_flashes(events, history, webhook_url)
    
    sleep_secs, mode_desc = get_adaptive_interval(events)
    
    return {
        "status": "ok",
        "timestamp": now_bkk,
        "pre_alerts_sent": pre_count,
        "flash_alerts_sent": flash_count,
        "events_monitored": len(events),
        "adaptive_interval": sleep_secs,
        "mode": mode_desc
    }


def main():
    parser = argparse.ArgumentParser(description="Automated Alert Scheduler for News Analyzer")
    parser.add_argument("--check-once", action="store_true", help="Run a single check and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuous background loop with Adaptive Timing")
    parser.add_argument("--interval", type=int, default=60, help="Default interval in seconds (default: 60s)")
    parser.add_argument("--send-weekly", action="store_true", help="Force send weekly radar now")
    parser.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    args = parser.parse_args()
    
    history = load_alert_history()
    
    if args.send_weekly:
        check_and_send_weekly_radar(history, args.webhook)
        return
        
    if args.check_once:
        result = run_scheduler_tick(args.webhook)
        print(f"[{result['timestamp']}] Check Complete: {result['events_monitored']} events monitored. Pre-alerts: {result['pre_alerts_sent']}, Flash: {result['flash_alerts_sent']} | Mode: {result['mode']}")
        return
        
    if args.daemon:
        print(f"[*] Starting News Analyzer Alert Daemon (Adaptive News Timing Engine)...")
        print(f"    • 🚀 Active Sniping Window ([-3m, +3m]): Poll every 5s")
        print(f"    • 👀 Pre-News Window ([-60m, -3m]): Check every 5m")
        print(f"    • 💤 Normal Idle Window (> 1h): Sleep up to 15m")
        print("Press Ctrl+C to stop.\n")
        try:
            while True:
                result = run_scheduler_tick(args.webhook)
                events = get_calendar_events(high_only=True)
                sleep_secs, mode_desc = get_adaptive_interval(events, default_interval=args.interval)
                print(f"[{datetime.now(BKK_TZ).strftime('%H:%M:%S')}] {mode_desc}")
                time.sleep(sleep_secs)
        except KeyboardInterrupt:
            print("\n[!] Daemon stopped by user.")
    else:
        # Default behavior: run check-once
        result = run_scheduler_tick(args.webhook)
        print(f"[{result['timestamp']}] Check Complete: {result['events_monitored']} events monitored. Pre-alerts: {result['pre_alerts_sent']}, Flash: {result['flash_alerts_sent']} | Mode: {result['mode']}")


if __name__ == "__main__":
    main()
