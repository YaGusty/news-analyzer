"""
Master CLI Entrypoint for News Analyzer
A unified command center for economic calendar lookup, macro scenario forecasting,
post-news flash analysis, and Discord alerts for NAS100, S&P 500, and Dow Jones.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.calendar_fetcher import get_calendar_events, print_cli_table
from scripts.analyzer import analyze_forecast, analyze_flash
from scripts.discord_notifier import (
    test_webhook,
    send_discord_payload,
    format_forecast_embed,
    format_flash_embed,
    format_weekly_radar_embed,
    load_webhook_url
)


def run_calendar_cmd(args):
    print("\n--- 🔴 Fetching Red Folder Calendar ---")
    events = get_calendar_events(force_refresh=args.refresh, high_only=not args.all)
    if args.today:
        from datetime import datetime
        from scripts.calendar_fetcher import BKK_TZ
        now_bkk = datetime.now(BKK_TZ).date()
        events = [e for e in events if datetime.fromtimestamp(e["timestamp_utc"], tz=BKK_TZ).date() == now_bkk]
        
    print_cli_table(events)
    
    if args.discord:
        print("\nDispatching Weekly Radar to Discord...")
        payload = format_weekly_radar_embed(events)
        ok, msg = send_discord_payload(payload, args.webhook)
        print(f"Discord Result: {msg}")


def run_forecast_cmd(args):
    print(f"\n--- 🔴 Modeling Macro Forecast: {args.event} ---")
    analysis = analyze_forecast(
        event_name=args.event,
        consensus=args.consensus,
        previous=args.previous,
        period=args.period
    )
    
    period_str = f"({analysis['period']})" if analysis.get('period') else ""
    print(f"Event: {analysis['event']} {period_str}")
    print(f"Time (BKK): {analysis['time_bkk']} | NY: {analysis['time_ny']}")
    print(f"Consensus: {analysis['consensus']} | Previous: {analysis['previous']}")
    print(f"Markdown Report: {analysis['report_path']}")
    print("\n[NAS100 Sensitivity]")
    print(analysis['nas100_impact'])
    print("\n[S&P 500 Sensitivity]")
    print(analysis['sp500_impact'])
    print("\n[Dow Jones Sensitivity]")
    print(analysis['dow_impact'])
    if analysis.get('pulse_text'):
        print(f"\n{analysis['pulse_text']}")
    else:
        print("\n[Intermarket DXY / US10Y]")
        print(analysis['intermarket'])
    print("\n[3-Scenario Matrix]")
    print(f"🔴 Hot:    {analysis['scenario_hot']}")
    print(f"🟢 Cool:   {analysis['scenario_cool']}")
    print(f"🟡 Inline: {analysis['scenario_inline']}")
    
    if args.discord:
        print("\nDispatching Forecast Embed to Discord...")
        payload = format_forecast_embed(analysis)
        ok, msg = send_discord_payload(payload, args.webhook)
        print(f"Discord Result: {msg}")


def run_flash_cmd(args):
    print(f"\n--- ⚡ Analyzing Post-News Flash: {args.event} ---")
    flash = analyze_flash(
        event_name=args.event,
        actual=args.actual,
        consensus=args.consensus,
        previous=args.previous
    )
    
    print(f"Event: {flash['event']}")
    print(f"Actual: {flash['actual']} vs Expected: {flash['consensus']} (Previous: {flash['previous']})")
    print(f"Verdict: {flash['verdict']}")
    print(f"Markdown Report: {flash['report_path']}")
    print(f"\n[Summary]\n{flash['summary']}")
    print(f"\n[Market Reaction Dynamics]\n{flash['market_reaction']}")
    print(f"\n[Fed Rate Path]\n{flash['fed_outlook']}")
    
    if args.discord:
        print("\nDispatching Flash Report to Discord...")
        payload = format_flash_embed(flash)
        ok, msg = send_discord_payload(payload, args.webhook)
        print(f"Discord Result: {msg}")


def main():
    parser = argparse.ArgumentParser(
        description="News Analyzer: Macro Forecaster & Discord Intelligence for NQ, ES, YM"
    )
    subparsers = parser.add_subparsers(dest="command")
    
    # Calendar / Radar subcommand
    p_cal = subparsers.add_parser("calendar", help="View upcoming Red Folder economic events")
    p_cal.add_argument("--today", action="store_true", help="Show today only")
    p_cal.add_argument("--all", action="store_true", help="Show all USD events (not just High Impact)")
    p_cal.add_argument("--refresh", action="store_true", help="Force refresh calendar cache")
    p_cal.add_argument("--discord", action="store_true", help="Send Weekly Radar to Discord")
    p_cal.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    
    # Forecast subcommand
    p_fc = subparsers.add_parser("forecast", help="Analyze & forecast impact of upcoming news")
    p_fc.add_argument("event", type=str, help="Event name (e.g. CPI, NFP, Retail Sales, FOMC, PPI, GDP)")
    p_fc.add_argument("--consensus", type=str, default=None, help="Consensus estimate")
    p_fc.add_argument("--previous", type=str, default=None, help="Previous release")
    p_fc.add_argument("--period", type=str, default=None, help="Period (e.g. Oct, Q3)")
    p_fc.add_argument("--discord", action="store_true", help="Send Forecast Embed to Discord")
    p_fc.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    
    # Flash subcommand
    p_fl = subparsers.add_parser("flash", help="Analyze actual release number immediately post-news")
    p_fl.add_argument("event", type=str, help="Event name (e.g. CPI, Retail Sales, NFP)")
    p_fl.add_argument("actual", type=str, help="Released actual number (e.g. 0.4%, 2.6%, 150k)")
    p_fl.add_argument("--consensus", type=str, default=None, help="Consensus estimate")
    p_fl.add_argument("--previous", type=str, default=None, help="Previous release")
    p_fl.add_argument("--discord", action="store_true", help="Send Flash Report to Discord")
    p_fl.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    
    # Test Discord
    p_test = subparsers.add_parser("test-discord", help="Test connection to Discord Webhook")
    p_test.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL to test")

    # Pulse subcommand
    p_pulse = subparsers.add_parser("pulse", help="View real-time pre-news market pulse (DXY, US10Y, VIX, NQ, ES, YM)")
    p_pulse.add_argument("--json", action="store_true", help="Output raw JSON")

    # Scheduler subcommand
    p_sched = subparsers.add_parser("scheduler", help="Run automated alert monitor for T-60 alerts & weekly radar")
    p_sched.add_argument("--daemon", action="store_true", help="Run continuously in background")
    p_sched.add_argument("--check-once", action="store_true", help="Run a single check and exit")
    p_sched.add_argument("--interval", type=int, default=60, help="Loop interval in seconds (default: 60)")
    p_sched.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")

    args = parser.parse_args()
    
    if args.command == "calendar":
        run_calendar_cmd(args)
    elif args.command == "forecast":
        run_forecast_cmd(args)
    elif args.command == "flash":
        run_flash_cmd(args)
    elif args.command == "test-discord":
        test_webhook(args.webhook)
    elif args.command == "pulse":
        from scripts.market_pulse import get_market_pulse, format_pulse_text
        import json
        pulse = get_market_pulse()
        if args.json:
            print(json.dumps(pulse, ensure_ascii=False, indent=2))
        else:
            print(f"\n{format_pulse_text(pulse)}\n")
    elif args.command == "scheduler":
        from scripts.alert_scheduler import run_scheduler_tick
        import time
        if args.daemon:
            print(f"[*] Starting News Analyzer Alert Daemon (interval: {args.interval}s)...")
            try:
                while True:
                    run_scheduler_tick(args.webhook)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n[!] Stopped.")
        else:
            result = run_scheduler_tick(args.webhook)
            print(f"Check Complete: {result['events_monitored']} events monitored. Pre-alerts: {result['pre_alerts_sent']}, Flash: {result['flash_alerts_sent']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
