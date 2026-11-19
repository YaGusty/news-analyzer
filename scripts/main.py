"""
Master CLI Entrypoint for News Analyzer
A unified command center for economic calendar lookup, macro scenario forecasting,
post-news flash analysis, interactive terminal menu, and Discord alerts for NAS100, S&P 500, and Dow Jones.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.calendar_fetcher import get_calendar_events, print_cli_table, BKK_TZ
from scripts.analyzer import analyze_forecast, analyze_flash
from scripts.discord_notifier import (
    test_webhook,
    send_discord_payload,
    format_forecast_embed,
    format_flash_embed,
    format_weekly_radar_embed,
    load_webhook_url
)
from scripts.alert_scheduler import (
    get_daemon_status,
    start_background_daemon,
    stop_background_daemon,
    record_manual_alert_sent,
    run_daemon_loop,
    run_scheduler_tick,
    check_and_send_weekly_radar,
    load_alert_history
)


def run_calendar_cmd(args):
    print("\n--- 🔴 Fetching Red Folder Calendar ---")
    events = get_calendar_events(force_refresh=args.refresh, high_only=not args.all)
    if args.today:
        from datetime import datetime
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
    if analysis.get('tldr'):
        print(f"\n{analysis['tldr']}")
    print(f"Markdown Report: {analysis['report_path']}")
    
    if analysis.get('subcomponents'):
        print("\n[🔍 Key Sub-Components to Watch]")
        for s in analysis['subcomponents']:
            print(f"• {s}")

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
    
    if analysis.get('domino_thinking'):
        print("\n[🧠 Domino Critical Thinking]")
        print(analysis['domino_thinking'])
    
    if args.discord:
        print("\nDispatching Forecast Embed to Discord...")
        payload = format_forecast_embed(analysis)
        ok, msg = send_discord_payload(payload, args.webhook)
        print(f"Discord Result: {msg}")
        if ok:
            record_manual_alert_sent("forecast", analysis['event'], time_bkk=analysis.get('time_bkk'))
            print("[✓] Recorded into Alert History to prevent automated scheduler duplication.")


def run_flash_cmd(args):
    print(f"\n--- ⚡ Analyzing Post-News Flash: {args.event} ---")
    flash = analyze_flash(
        event_name=args.event,
        actual=args.actual,
        consensus=args.consensus,
        previous=args.previous
    )
    
    badge = flash.get('deviation_badge', flash['verdict'])
    print(f"Event: {flash['event']}")
    print(f"Verdict: {badge}")
    print(f"Actual: {flash['actual']} vs Expected: {flash['consensus']} (Diff: {flash.get('deviation_str', '-')}) | Previous: {flash['previous']}")
    if flash.get('tldr'):
        print(f"\n{flash['tldr']}")
    print(f"Markdown Report: {flash['report_path']}")
    print(f"\n[Summary]\n{flash['summary']}")
    if flash.get('domino_forward'):
        print(f"\n[🔗 Forward Domino Impact]\n{flash['domino_forward']}")
    print(f"\n[Market Reaction Dynamics]\n{flash['market_reaction']}")
    print(f"\n[Fed Rate Path]\n{flash['fed_outlook']}")
    
    if args.discord:
        print("\nDispatching Flash Report to Discord...")
        payload = format_flash_embed(flash)
        ok, msg = send_discord_payload(payload, args.webhook)
        print(f"Discord Result: {msg}")
        if ok:
            record_manual_alert_sent("flash", flash['event'], actual=flash['actual'])
            print("[✓] Recorded into Alert History to prevent automated scheduler duplication.")


def run_interactive_menu():
    """Interactive command center menu for easy manual execution."""
    from scripts.market_pulse import get_market_pulse, format_pulse_text
    from scripts.reaction_logger import compute_reaction_statistics, print_reaction_report
    
    while True:
        st = get_daemon_status()
        status_badge = "🟢 RUNNING" if st["running"] else "⚪ STOPPED"
        
        print("\n" + "=" * 70)
        print("  🔴 NEWS ANALYZER — MACRO INTELLIGENCE COMMAND CENTER")
        print(f"  [24/7 Background Daemon: {status_badge} (PID: {st['pid'] or '-'})]")
        print("=" * 70)
        print("  [1] 📅 ตารางข่าวกล่องแดง (Red Folder Economic Calendar)")
        print("  [2] 🚀 หน้าต่างเฝ้าข่าวสด (Live Sniping Console - Real-time)")
        print("  [3] 📊 บรรยากาศตลาดสด (Market Pulse: NQ, ES, YM, DXY, US10Y)")
        print("  [4] 🔮 วิเคราะห์คาดการณ์ล่วงหน้า (Pre-News Forecast Matrix)")
        print("  [5] ⚡ วิเคราะห์ด่วนหลังตัวเลขออก (Post-News Flash Reaction)")
        print("  [6] 📡 ส่งสรุป Weekly Radar เข้า Discord ทันที")
        print("  [7] ⚙️  จัดการ Background Daemon 24/7 (เปิด / ปิด / ดู Log)")
        print("  [8] 📈 ดูสถิติปฏิกิริยาราคาย้อนหลัง 10 ปี (2015-2025 Reaction Benchmark)")
        print("  [9] 🔔 ทดสอบการเชื่อมต่อ Discord Webhook")
        print("  [0] 🚪 ออกจากโปรแกรม (Exit)")
        print("=" * 70)
        
        try:
            choice = input("เลือกคำสั่ง [0-9]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 สวัสดีครับ")
            break
            
        if choice == "0":
            print("\n👋 ออกจากโปรแกรมเรียบร้อยครับ")
            break
            
        elif choice == "1":
            print("\nตัวเลือก: [1] เฉพาะวันนี้  [2] ทั้งสัปดาห์  [3] รีเฟรชดึงใหม่")
            sub = input("เลือก [1-3] (default: 2): ").strip()
            events = get_calendar_events(force_refresh=(sub == "3"), high_only=True)
            if sub == "1":
                from datetime import datetime
                now_bkk = datetime.now(BKK_TZ).date()
                events = [e for e in events if datetime.fromtimestamp(e["timestamp_utc"], tz=BKK_TZ).date() == now_bkk]
            print_cli_table(events)
            
        elif choice == "2":
            print("\n[*] เข้าสู่ Live Sniping Console (กด Ctrl+C เพื่อกลับสู่เมนูหลัก)")
            try:
                run_daemon_loop()
            except KeyboardInterrupt:
                print("\n[!] กลับสู่เมนูหลัก...")
                
        elif choice == "3":
            print("\nกำลังดึงข้อมูลบรรยากาศตลาดสด...")
            pulse = get_market_pulse()
            print(f"\n{format_pulse_text(pulse)}")
            
        elif choice == "4":
            evt = input("\nระบุชื่อข่าว (เช่น CPI, Nonfarm, Retail Sales, FOMC): ").strip()
            if not evt:
                print("[!] ไม่ได้ระบุชื่อข่าว")
                continue
            cons = input("ตัวเลข Consensus คาดการณ์ (กด Enter ถ้าต้องการให้ระบบดึงอัตโนมัติ): ").strip() or None
            prev = input("ตัวเลข Previous ครั้งก่อน (กด Enter ถ้าต้องการให้ระบบดึงอัตโนมัติ): ").strip() or None
            send_dc = input("ส่งบทวิเคราะห์เข้า Discord ด้วยหรือไม่? (y/n): ").strip().lower() == "y"
            
            class DummyArgs:
                event = evt
                consensus = cons
                previous = prev
                period = None
                discord = send_dc
                webhook = None
            run_forecast_cmd(DummyArgs)
            
        elif choice == "5":
            evt = input("\nระบุชื่อข่าว (เช่น CPI, Nonfarm, Retail Sales): ").strip()
            if not evt:
                print("[!] ไม่ได้ระบุชื่อข่าว")
                continue
            act = input("ตัวเลขจริงที่เพิ่งประกาศ (Actual เช่น 2.6%, 150k): ").strip()
            if not act:
                print("[!] จำเป็นต้องระบุตัวเลข Actual")
                continue
            cons = input("ตัวเลขคาดการณ์ (Consensus เช่น 2.4%): ").strip() or None
            prev = input("ตัวเลขครั้งก่อน (Previous เช่น 2.3%): ").strip() or None
            send_dc = input("ส่ง Flash Reaction เข้า Discord ด้วยหรือไม่? (y/n): ").strip().lower() == "y"
            
            class DummyFlashArgs:
                event = evt
                actual = act
                consensus = cons
                previous = prev
                discord = send_dc
                webhook = None
            run_flash_cmd(DummyFlashArgs)
            
        elif choice == "6":
            print("\nกำลังส่ง Weekly Radar เข้า Discord...")
            events = get_calendar_events(force_refresh=True, high_only=True)
            payload = format_weekly_radar_embed(events)
            ok, msg = send_discord_payload(payload)
            print(f"ผลลัพธ์: {msg}")
            
        elif choice == "7":
            st = get_daemon_status()
            print(f"\n[Background 24/7 Daemon Status]")
            print(f"สถานะ: {'🟢 RUNNING' if st['running'] else '⚪ STOPPED'}")
            print(f"PID:   {st['pid'] or '-'}")
            print(f"Log:   {st['log_file']}")
            if st["log_tail"]:
                print("\n--- บันทึกเหตุการณ์ล่าสุด (10 บรรทัดล่าสุด) ---")
                for line in st["log_tail"]:
                    print(f"  {line}")
            print("\nตัวเลือกจัดการ: [1] สั่งเปิดทำงานในพื้นหลัง  [2] สั่งหยุดทำงาน  [0] กลับสู่เมนู")
            d_sub = input("เลือก [0-2]: ").strip()
            if d_sub == "1":
                ok, msg = start_background_daemon()
                print(f"[*] {msg}")
            elif d_sub == "2":
                ok, msg = stop_background_daemon()
                print(f"[*] {msg}")
                
        elif choice == "8":
            print("\nเลือกช่วงปีที่ต้องการวิเคราะห์: 2024, 2023, 2020-2025, 2015-2019, all, live")
            yr = input("ระบุปี (default: all): ").strip() or "all"
            stats = compute_reaction_statistics(year=yr)
            print_reaction_report(stats)
            
        elif choice == "9":
            print("\nกำลังทดสอบการส่งสัญญาณเข้า Discord Webhook...")
            test_webhook()
            
        else:
            print("[!] ตัวเลือกไม่ถูกต้อง กรุณาเลือก 0-9")
            
        input("\nกด Enter เพื่อดำเนินการต่อ...")


def main():
    parser = argparse.ArgumentParser(
        description="News Analyzer: Macro Forecaster & Discord Intelligence for NQ, ES, YM"
    )
    subparsers = parser.add_subparsers(dest="command")
    
    # Menu subcommand
    subparsers.add_parser("menu", help="Launch interactive terminal command center")
    
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
    p_sched.add_argument("--daemon", action="store_true", help="Run continuously in background loop")
    p_sched.add_argument("--check-once", action="store_true", help="Run a single check and exit")
    p_sched.add_argument("--interval", type=int, default=60, help="Loop interval in seconds (default: 60)")
    p_sched.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    p_sched.add_argument("--status", action="store_true", help="Show daemon status and log tail")
    p_sched.add_argument("--start-bg", action="store_true", help="Start background daemon process")
    p_sched.add_argument("--stop", action="store_true", help="Stop background daemon process")

    # Reaction subcommand (Verified Quantitative Reactions)
    year_choices = [str(y) for y in range(2015, 2026)] + ["2015-2019", "2020-2025", "all", "live"]
    p_rx = subparsers.add_parser("reaction", help="View quantitative event price reactions & statistics")
    p_rx.add_argument("--year", type=str, default="all", choices=year_choices, help="Year to analyze (2015-2025, 2015-2019, all, or live)")
    p_rx.add_argument("--summary", action="store_true", help="Show statistical distribution and whipsaw rate")

    # Backtest subcommand (Redirected to Verified Reaction Tracker)
    p_bt = subparsers.add_parser("backtest", help="View verified quantitative reaction benchmark")
    p_bt.add_argument("--year", type=str, default="all", choices=year_choices, help="Year to analyze (2015-2025, 2015-2019, all, or live)")

    args = parser.parse_args()
    
    if args.command == "menu" or args.command is None:
        run_interactive_menu()
    elif args.command == "calendar":
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
        elif args.start_bg:
            ok, msg = start_background_daemon()
            print(f"[*] {msg}")
        elif args.stop:
            ok, msg = stop_background_daemon()
            print(f"[*] {msg}")
        elif args.daemon:
            run_daemon_loop(args.webhook, args.interval)
        else:
            result = run_scheduler_tick(args.webhook)
            print(f"[{result['timestamp']}] Check Complete: {result['events_monitored']} events monitored. Pre-alerts: {result['pre_alerts_sent']}, Flash: {result['flash_alerts_sent']} | Mode: {result['mode']}")
    elif args.command in ("reaction", "backtest"):
        from scripts.reaction_logger import compute_reaction_statistics, print_reaction_report
        target_year = getattr(args, "year", "2024")
        stats = compute_reaction_statistics(year=target_year)
        print_reaction_report(stats)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
