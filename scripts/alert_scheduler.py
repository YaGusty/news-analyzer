"""
Automated Alert Scheduler for News Analyzer
Monitors the Red Folder economic calendar and automatically dispatches:
1. Weekly Radar Kickoff (via dedicated weekly_radar workflow or Monday 07:00 AM BKK trigger)
2. T-60 Minutes Pre-News Alert (Forecast + Live Market Pulse)
3. T+5 Minutes Post-News Flash Alert (Actual Release Reaction & Active Sniping)
Prevents duplicate alerts using persistent history in data/calendar/alert_history.json.
Provides 24/7 crash-proof daemon loop, PID tracking, and file logging.
"""

import sys
import os
import json
import time
import argparse
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = PROJECT_ROOT / "data" / "calendar" / "alert_history.json"
PID_FILE = PROJECT_ROOT / "data" / "scheduler.pid"
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_FILE = LOG_DIR / "scheduler.log"

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


# ---------------------------------------------------------------------------
# Logging & Process Management (24/7 Resilience)
# ---------------------------------------------------------------------------

def get_scheduler_logger():
    """Configure and return logger with rotating file and safe stream output."""
    logger = logging.getLogger("NewsScheduler")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Rotating File Handler (5 MB, 3 backups)
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        # Console output only when a real terminal is attached
        try:
            if sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
                ch = logging.StreamHandler(sys.stdout)
                ch.setFormatter(formatter)
                logger.addHandler(ch)
        except Exception:
            pass
            
    return logger


def is_pid_running(pid: int) -> bool:
    """Check if process ID is actively running."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                return exit_code.value == 259  # STILL_ACTIVE
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def kill_pid(pid: int) -> bool:
    """Terminate process cleanly."""
    if not is_pid_running(pid):
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, False, pid)  # PROCESS_TERMINATE
            if handle:
                kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)
                return True
        except Exception:
            pass
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            return True
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 15)  # SIGTERM
            return True
        except Exception:
            return False


def write_pid_file(pid: int = None):
    """Write current PID to file."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    curr_pid = pid or os.getpid()
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(curr_pid))


def read_pid_file() -> int | None:
    """Read PID from file if exists and valid."""
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.isdigit():
                    return int(content)
        except Exception:
            return None
    return None


def remove_pid_file():
    """Remove PID file safely."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


def get_daemon_status() -> dict:
    """Retrieve full background daemon status, PID, and latest logs."""
    pid = read_pid_file()
    running = False
    if pid:
        if is_pid_running(pid):
            running = True
        else:
            remove_pid_file()
            pid = None
            
    log_tail = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                log_tail = [line.strip() for line in lines[-12:] if line.strip()]
        except Exception:
            pass
            
    return {
        "running": running,
        "pid": pid,
        "log_file": str(LOG_FILE),
        "log_tail": log_tail
    }


def start_background_daemon() -> tuple[bool, str]:
    """Launch detached background daemon process without a window."""
    status = get_daemon_status()
    if status["running"]:
        return False, f"Daemon is already running (PID: {status['pid']})"
        
    python_exe = sys.executable
    cmd = [python_exe, str(PROJECT_ROOT / "scripts" / "main.py"), "scheduler", "--daemon"]
    
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=(sys.platform != "win32")
    )
    write_pid_file(proc.pid)
    time.sleep(1.0)
    if is_pid_running(proc.pid):
        return True, f"Daemon successfully started in background (PID: {proc.pid})"
    else:
        return False, "Daemon process exited immediately. Check data/logs/scheduler.log for errors."


def stop_background_daemon() -> tuple[bool, str]:
    """Stop the background daemon process."""
    status = get_daemon_status()
    if not status["running"]:
        remove_pid_file()
        return False, "Daemon is not currently running."
        
    pid = status["pid"]
    success = kill_pid(pid)
    remove_pid_file()
    if success:
        return True, f"Daemon stopped successfully (PID: {pid})"
    return False, f"Failed to terminate daemon (PID: {pid})"


# ---------------------------------------------------------------------------
# Alert History & Universal De-duplication
# ---------------------------------------------------------------------------

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


def record_manual_alert_sent(alert_type: str, event_title: str, time_bkk: str = None, actual: str = None):
    """
    Record manually sent alert into history to prevent automated scheduler duplication.
    Cross-references current calendar events to bind exact event_ids.
    """
    history = load_alert_history()
    now_utc = datetime.now(timezone.utc)
    t_clean = event_title.strip().lower()
    
    events = get_calendar_events(high_only=True)
    matched_ids = []
    for e in events:
        e_title = e.get("title", "").strip().lower()
        if t_clean in e_title or e_title in t_clean:
            e_id = str(e.get("id") or f"{e['title']}_{e.get('date_utc', '')}")
            matched_ids.append((e_id, e.get("title"), e.get("date_bkk")))
            
    # Generic fallback key for today
    today_key = f"manual_{t_clean}_{now_utc.strftime('%Y%m%d')}"
    
    if alert_type == "forecast":
        if "forecast_sent" not in history:
            history["forecast_sent"] = {}
        history["forecast_sent"][today_key] = {
            "event": event_title,
            "triggered_at": now_utc.isoformat(),
            "time_bkk": time_bkk or "-",
            "source": "manual"
        }
        for e_id, name, bkk in matched_ids:
            history["forecast_sent"][e_id] = {
                "event": name,
                "triggered_at": now_utc.isoformat(),
                "time_bkk": bkk or time_bkk or "-",
                "source": "manual"
            }
    elif alert_type == "flash":
        if "flash_sent" not in history:
            history["flash_sent"] = {}
        history["flash_sent"][today_key] = {
            "event": event_title,
            "actual": str(actual),
            "triggered_at": now_utc.isoformat(),
            "source": "manual"
        }
        for e_id, name, _ in matched_ids:
            history["flash_sent"][e_id] = {
                "event": name,
                "actual": str(actual),
                "triggered_at": now_utc.isoformat(),
                "source": "manual"
            }
            
    save_alert_history(history)


# ---------------------------------------------------------------------------
# Alert Dispatch Engines
# ---------------------------------------------------------------------------

def check_and_send_weekly_radar(history: dict, webhook_url: str = None, force: bool = False) -> bool:
    """
    Check if weekly radar should be dispatched for this week.
    Automatically fires every Monday morning (from 07:00 AM BKK time).
    """
    logger = get_scheduler_logger()
    now_bkk = datetime.now(BKK_TZ)
    week_id = now_bkk.strftime("%Y-W%W")
    
    if not force:
        if week_id in history.get("weekly_sent", []):
            return False
            
        # Automatic trigger: Monday from 07:00 BKK onwards (or Tuesday fallback)
        if now_bkk.weekday() not in (0, 1):
            return False
        if now_bkk.weekday() == 0 and now_bkk.hour < 7:
            return False
        
    logger.info(f"📡 Dispatching Automated Weekly Radar for {week_id}...")
    events = get_calendar_events(force_refresh=True, high_only=True)
    payload = format_weekly_radar_embed(events)
    
    ok, msg = send_discord_payload(payload, webhook_url)
    logger.info(f"Weekly Radar Dispatch: {msg}")
    
    if ok:
        if "weekly_sent" not in history:
            history["weekly_sent"] = []
        if week_id not in history["weekly_sent"]:
            history["weekly_sent"].append(week_id)
        save_alert_history(history)
        return True
    return False


def check_and_send_pre_news_alerts(events: list, history: dict, webhook_url: str = None) -> int:
    """
    Check for events occurring within 5 to 65 minutes.
    Dispatch T-60 pre-news forecast embed with live market pulse.
    """
    logger = get_scheduler_logger()
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
                logger.info(f"🔴 T-60 Alert Triggered for: {event['title']} ({minutes_until:.1f} mins away)")
                
                # Generate forecast with live market pulse
                analysis = analyze_forecast(
                    event_name=event["title"],
                    consensus=str(event["forecast"]) if event.get("forecast") is not None else None,
                    previous=str(event["previous"]) if event.get("previous") is not None else None,
                    period=str(event.get("period", ""))
                )
                
                payload = format_forecast_embed(analysis)
                ok, msg = send_discord_payload(payload, webhook_url)
                logger.info(f"Forecast Alert Dispatch: {msg}")
                
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
    1. Active Sniping ([-3 mins, +3 mins]): Poll every 5s
    2. Delayed Sniping ([+3 mins, +10 mins]): Poll every 10s
    3. Pre-News Window ([-60 mins, -3 mins]): Poll every 5m (300s)
    4. Normal Idle Window (> 1h): Sleep up to 15m
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
            sleep_time = min(300, max(5, int(secs_until - 180)))
            return sleep_time, f"👀 PRE_NEWS (Next: {nearest_event['title']} in {mins_until:.1f}m | Check every 5m)"
            
        # More than 1 hour away:
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
    Check for events in release window ([-3 mins, +45 mins]).
    Active 5-second polling loop captures release in real time.
    """
    logger = get_scheduler_logger()
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
            logger.info(f"🎯 Active Sniping Window: {event['title']} (T{diff_secs:+.0f}s). Polling every 5s...")
            start_loop = time.time()
            max_loop_secs = 360  # max 6 minutes wait
            while time.time() - start_loop < max_loop_secs:
                loop_now_ts = datetime.now(timezone.utc).timestamp()
                loop_diff = loop_now_ts - event_ts
                
                if loop_diff >= -10:
                    new_acts = fetch_actual_fast(event["title"])
                    act_candidate = new_acts.get(event["title"].lower())
                    if act_candidate is not None and str(act_candidate).strip() != "":
                        actual = act_candidate
                        logger.info(f"⚡ Captured actual for {event['title']}: {actual} (at T{loop_diff:+.0f}s)")
                        break
                        
                time.sleep(5)
                
        # 2. General Check: If event released within last 45 minutes and actual is missing
        if 0 <= minutes_passed <= 45 and (actual is None or str(actual).strip() == ""):
            new_acts = fetch_actual_fast(event["title"])
            actual = new_acts.get(event["title"].lower())
            
        # 3. If actual is present and within [-3m, 45m], dispatch flash report!
        if actual is not None and str(actual).strip() != "" and -3 <= minutes_passed <= 45:
            logger.info(f"⚡ [INSTANT FLASH] Triggered for: {event['title']} (Actual: {actual})")
            
            flash = analyze_flash(
                event_name=event["title"],
                actual=str(actual),
                consensus=str(event.get("forecast", "N/A")),
                previous=str(event.get("previous", "N/A"))
            )
            
            payload = format_flash_embed(flash)
            ok, msg = send_discord_payload(payload, webhook_url)
            logger.info(f"Flash Alert Dispatch: {msg}")
            
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
    """Run a single check pass across calendar, weekly radar, T-60 alerts, and instant flashes."""
    now_bkk = datetime.now(BKK_TZ).strftime("%Y-%m-%d %H:%M:%S")
    
    history = load_alert_history()
    events = get_calendar_events(high_only=True)
    
    # 1. Weekly Radar Check (Monday morning trigger)
    weekly_sent = check_and_send_weekly_radar(history, webhook_url, force=False)
    
    # 2. Pre-News Forecast Alerts (T-60m)
    pre_count = check_and_send_pre_news_alerts(events, history, webhook_url)
    
    # 3. Post-News Flash Analysis & Active Sniping
    flash_count = check_and_send_post_news_flashes(events, history, webhook_url)
    
    sleep_secs, mode_desc = get_adaptive_interval(events)
    
    return {
        "status": "ok",
        "timestamp": now_bkk,
        "weekly_radar_sent": weekly_sent,
        "pre_alerts_sent": pre_count,
        "flash_alerts_sent": flash_count,
        "events_monitored": len(events),
        "adaptive_interval": sleep_secs,
        "mode": mode_desc
    }


def run_daemon_loop(webhook_url: str = None, default_interval: int = 60):
    """
    24/7 Crash-Resilient Background Loop.
    Catches unexpected network / parsing errors, recovers after backoff, and logs all events.
    """
    logger = get_scheduler_logger()
    write_pid_file()
    
    logger.info("[*] Starting News Analyzer Alert Daemon (24/7 Adaptive Timing Engine)...")
    logger.info("    • 🚀 Active Sniping Window ([-3m, +3m]): Poll every 5s")
    logger.info("    • 👀 Pre-News Window ([-60m, -3m]): Check every 5m")
    logger.info("    • 💤 Normal Idle Window (> 1h): Sleep up to 15m")
    logger.info("    • 📡 Weekly Radar: Auto-dispatches Monday 07:00 AM BKK")
    logger.info(f"    • 📝 Persistent Log: {LOG_FILE}")
    logger.info("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            try:
                result = run_scheduler_tick(webhook_url)
                events = get_calendar_events(high_only=True)
                sleep_secs, mode_desc = get_adaptive_interval(events, default_interval=default_interval)
                logger.info(f"[{datetime.now(BKK_TZ).strftime('%H:%M:%S')}] {mode_desc}")
                time.sleep(sleep_secs)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"[!] Daemon tick error (auto-recovering in 30s): {e}", exc_info=True)
                time.sleep(30)
    except KeyboardInterrupt:
        logger.info("\n[!] Daemon stopped by user.")
    except BaseException as be:
        logger.error(f"[!] Daemon terminated by BaseException: {type(be).__name__}: {be}", exc_info=True)
        raise
    finally:
        logger.info("[!] Daemon loop exited, cleaning up PID file.")
        remove_pid_file()


def main():
    parser = argparse.ArgumentParser(description="Automated Alert Scheduler for News Analyzer")
    parser.add_argument("--check-once", action="store_true", help="Run a single check and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuous background loop with Adaptive Timing")
    parser.add_argument("--interval", type=int, default=60, help="Default interval in seconds (default: 60s)")
    parser.add_argument("--send-weekly", action="store_true", help="Force send weekly radar now")
    parser.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    parser.add_argument("--status", action="store_true", help="Show daemon status and log tail")
    parser.add_argument("--start-bg", action="store_true", help="Start background daemon process")
    parser.add_argument("--stop", action="store_true", help="Stop background daemon process")
    args = parser.parse_args()
    
    if args.status:
        st = get_daemon_status()
        state_str = "🟢 RUNNING" if st["running"] else "⚪ STOPPED"
        print(f"\n[News Analyzer Daemon Status]")
        print(f"Status:   {state_str}")
        print(f"PID:      {st['pid'] or 'None'}")
        print(f"Log File: {st['log_file']}")
        if st["log_tail"]:
            print(f"\n--- Recent Log Output (Last 10 lines) ---")
            for line in st["log_tail"]:
                print(f"  {line}")
        print()
        return

    if args.start_bg:
        ok, msg = start_background_daemon()
        print(f"[*] {msg}")
        return

    if args.stop:
        ok, msg = stop_background_daemon()
        print(f"[*] {msg}")
        return

    history = load_alert_history()
    
    if args.send_weekly:
        check_and_send_weekly_radar(history, args.webhook, force=True)
        return
        
    if args.check_once:
        result = run_scheduler_tick(args.webhook)
        print(f"[{result['timestamp']}] Check Complete: {result['events_monitored']} events monitored. Pre-alerts: {result['pre_alerts_sent']}, Flash: {result['flash_alerts_sent']} | Mode: {result['mode']}")
        return
        
    if args.daemon:
        run_daemon_loop(args.webhook, args.interval)
    else:
        result = run_scheduler_tick(args.webhook)
        print(f"[{result['timestamp']}] Check Complete: {result['events_monitored']} events monitored. Pre-alerts: {result['pre_alerts_sent']}, Flash: {result['flash_alerts_sent']} | Mode: {result['mode']}")


if __name__ == "__main__":
    main()
