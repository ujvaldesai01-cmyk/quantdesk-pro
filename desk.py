#!/usr/bin/env python3
"""Unified Trading Desk CLI for day-trader-skill with Dual-Market Support.

Provides a single command center for both Indian Markets (NSE/BSE) and US Markets (NYSE/NASDAQ):
  python desk.py status                  # Show account, active market, watchlist, and plan
  python desk.py switch in               # Switch active market to Indian Markets (NSE/BSE, ₹ INR)
  python desk.py switch us               # Switch active market to US Markets (NYSE/NASDAQ, $ USD)
  python desk.py scan                    # Scan personal watchlist for opening-range breakouts
  python desk.py scan --daily            # Run pre-market daily chart scan
  python desk.py news RELIANCE.NS        # Check breaking headlines & disclosures
  python desk.py entry RELIANCE.NS       # Check if a bar has closed above range
  python desk.py plan                    # Plan entry, stop-loss, target & cutoff close
  python desk.py sim                     # 10,000 Monte Carlo replays + ASCII fan chart
  python desk.py size                    # Size position to budget & max loss limit
  python desk.py risk                    # Pre-trade risk check (PASS / BLOCK)
  python desk.py ticket                  # View execution ticket with bracket legs
  python desk.py alerts                  # Check or set price alerts
  python desk.py test-loop               # Run an instant full simulated trade cycle!
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

# Configure UTF-8 encoding on Windows to support Indian Rupee symbol (₹) cleanly
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

CONFIG_PATH = os.path.join(ROOT, "trader", "config.json")
WATCHLIST_FILE = os.path.join(ROOT, "trader", "my_watchlist.txt")
WATCHLIST_IN_FILE = os.path.join(ROOT, "trader", "my_watchlist_in.txt")
WATCHLIST_US_FILE = os.path.join(ROOT, "trader", "my_watchlist_us.txt")
PLAN_PATH = os.path.join(ROOT, "trader", "plan.json")
PLAN_IN_PATH = os.path.join(ROOT, "trader", "plan_in.json")
PLAN_US_PATH = os.path.join(ROOT, "trader", "plan_us.json")
ENTRY_PATH = os.path.join(ROOT, "trader", "entry.json")
ORDERS_PATH = os.path.join(ROOT, "trader", "orders.json")
ORDERS_IN_PATH = os.path.join(ROOT, "trader", "orders_in.json")
ORDERS_US_PATH = os.path.join(ROOT, "trader", "orders_us.json")
TIMEMACHINE_PATH = os.path.join(ROOT, "trader", "timemachine.json")


def run_script(rel_path, args=None, capture=False):
    full_path = os.path.join(ROOT, rel_path)
    cmd = [PYTHON, full_path] + (args or [])
    if capture:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return subprocess.run(cmd, cwd=ROOT).returncode


def load_json(path):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_active_market():
    cfg = load_json(CONFIG_PATH) or {}
    return cfg.get("active_market", "IN").upper()


def switch_market(target):
    target = target.upper()
    if target in ("IN", "INDIA", "INDIAN", "NSE", "BSE"):
        target_code = "IN"
    elif target in ("US", "USA", "AMERICA", "NYSE", "NASDAQ"):
        target_code = "US"
    else:
        print(f"Unknown market '{target}'. Please specify 'IN' (Indian Markets) or 'US' (US Markets).")
        return False

    cfg = load_json(CONFIG_PATH) or {}
    cur_market = cfg.get("active_market", "IN").upper()

    # Save current active plan & orders to corresponding market file based on symbol
    cur_plan = load_json(PLAN_PATH)
    if cur_plan:
        sym = str(cur_plan.get("symbol", "")).upper()
        if sym.endswith((".NS", ".BO")):
            save_json(PLAN_IN_PATH, cur_plan)
        else:
            save_json(PLAN_US_PATH, cur_plan)

    cur_orders = load_json(ORDERS_PATH)
    if cur_orders:
        first_ord = (cur_orders.get("orders") or [{}])[0] if isinstance(cur_orders, dict) else {}
        sym = str(first_ord.get("symbol", "")).upper()
        if sym.endswith((".NS", ".BO")):
            save_json(ORDERS_IN_PATH, cur_orders)
        else:
            save_json(ORDERS_US_PATH, cur_orders)

    cfg["active_market"] = target_code



    # Sync market settings to top-level in config.json
    mkt_settings = (cfg.get("markets") or {}).get(target_code, {})
    if mkt_settings:
        cfg["budget"] = mkt_settings.get("budget", 100000 if target_code == "IN" else 5000)
        cfg["currency"] = mkt_settings.get("currency", "INR" if target_code == "IN" else "USD")
        cfg["currency_symbol"] = mkt_settings.get("currency_symbol", "₹" if target_code == "IN" else "$")
        cfg["max_loss_per_trade_usd"] = mkt_settings.get("max_loss_per_trade", 1000 if target_code == "IN" else 50)
        cfg["max_daily_loss_usd"] = mkt_settings.get("max_daily_loss", 3000 if target_code == "IN" else 150)
        cfg["no_entries_before"] = mkt_settings.get("no_entries_before", "09:30" if target_code == "IN" else "09:45")
        cfg["no_entries_after"] = mkt_settings.get("no_entries_after", "15:10" if target_code == "IN" else "15:30")
        cfg["flat_by"] = mkt_settings.get("flat_by", "15:15" if target_code == "IN" else "15:55")
        cfg["broker"] = mkt_settings.get("broker", "zerodha_kite" if target_code == "IN" else "alpaca")

    save_json(CONFIG_PATH, cfg)

    # Copy market-specific watchlist, plan, orders to active files
    if target_code == "IN":
        if os.path.isfile(WATCHLIST_IN_FILE):
            shutil.copyfile(WATCHLIST_IN_FILE, WATCHLIST_FILE)
        if os.path.isfile(PLAN_IN_PATH):
            shutil.copyfile(PLAN_IN_PATH, PLAN_PATH)
        if os.path.isfile(ORDERS_IN_PATH):
            shutil.copyfile(ORDERS_IN_PATH, ORDERS_PATH)
        print("=" * 68)
        print("  SWITCHED TO: 🇮🇳 INDIAN MARKETS (NSE / BSE)")
        print("  Currency   : ₹ INR")
        print("  Hours      : 09:15 - 15:30 IST (MIS Day Square-off: 15:15 IST)")
        print("  Broker     : Zerodha Kite Connect / NSE MIS Intraday Bracket")
        print("  Watchlist  : Top liquid Nifty 50 bluechips (RELIANCE.NS, TCS.NS...)")
        print("=" * 68)
    else:
        if os.path.isfile(WATCHLIST_US_FILE):
            shutil.copyfile(WATCHLIST_US_FILE, WATCHLIST_FILE)
        if os.path.isfile(PLAN_US_PATH):
            shutil.copyfile(PLAN_US_PATH, PLAN_PATH)
        if os.path.isfile(ORDERS_US_PATH):
            shutil.copyfile(ORDERS_US_PATH, ORDERS_PATH)
        print("=" * 68)
        print("  SWITCHED TO: 🇺🇸 US MARKETS (NYSE / NASDAQ)")
        print("  Currency   : $ USD")
        print("  Hours      : 09:30 - 16:00 ET (Flat-by Cutoff: 15:55 ET)")
        print("  Broker     : Alpaca Paper Trading Bracket Orders")
        print("  Watchlist  : Top US Equities (AAPL, TSLA, NVDA, MSFT...)")
        print("=" * 68)

    return True


def get_watchlist_symbols():
    if os.path.isfile(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]
            if lines:
                return ",".join(lines)
    active_mkt = get_active_market()
    if active_mkt == "IN":
        return "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,SBIN.NS,BHARTIARTL.NS,ITC.NS,LT.NS,TATAMOTORS.NS"
    return "TSLA,NVDA,AAPL,AMD,MSFT,AMZN,META,GOOGL,PLTR,QQQ,SPY"


def cmd_status():
    cfg = load_json(CONFIG_PATH) or {}
    active_mkt = cfg.get("active_market", "IN").upper()
    curr_sym = cfg.get("currency_symbol", "₹" if active_mkt == "IN" else "$")

    print("=" * 68)
    print("                    QUANTDESK COMMAND CENTER")
    print("=" * 68)
    if active_mkt == "IN":
        print(f" Active Market Mode  : 🇮🇳 INDIAN MARKETS (NSE / BSE)")
        print(f" Currency            : {curr_sym} INR")
        print(f" Trading Hours       : 09:15 - 15:30 IST")
        print(f" Intraday Square-off : {cfg.get('flat_by', '15:15')} IST (MIS Intraday)")
        print(f" Broker Mode         : {cfg.get('broker', 'zerodha_kite').upper()} (Paper: {cfg.get('paper', True)})")
    else:
        print(f" Active Market Mode  : 🇺🇸 US MARKETS (NYSE / NASDAQ)")
        print(f" Currency            : {curr_sym} USD")
        print(f" Trading Hours       : 09:30 - 16:00 ET")
        print(f" Flat-by Cutoff      : {cfg.get('flat_by', '15:55')} ET")
        print(f" Broker Mode         : {cfg.get('broker', 'alpaca').upper()} (Paper: {cfg.get('paper', True)})")

    print("-" * 68)
    budget = cfg.get('budget', 100000 if active_mkt == "IN" else 5000)
    max_loss = cfg.get('max_loss_per_trade_usd', 1000 if active_mkt == "IN" else 50)
    max_daily = cfg.get('max_daily_loss_usd', 3000 if active_mkt == "IN" else 150)
    print(f" Account Budget      : {curr_sym}{budget:,.0f}")
    print(f" Max Risk / Trade    : {curr_sym}{max_loss:,.0f}")
    print(f" Max Daily Loss      : {curr_sym}{max_daily:,.0f}")
    print("-" * 68)

    symbols = get_watchlist_symbols().split(",")
    print(f" Active Watchlist ({len(symbols)} tickers): {', '.join(symbols[:12])}{'...' if len(symbols) > 12 else ''}")
    print("-" * 68)

    entry = load_json(ENTRY_PATH)
    plan = load_json(PLAN_PATH)
    orders = load_json(ORDERS_PATH)

    if plan:
        print(" Active Trade Plan:")
        print(f"   Ticker   : {plan.get('symbol')} ({plan.get('setup')})")
        print(f"   Entry    : {curr_sym}{plan.get('entry')}")
        print(f"   Stop     : {curr_sym}{plan.get('stop')} ({plan.get('stop_rule')})")
        print(f"   Target   : {curr_sym}{plan.get('target')} ({plan.get('target_r')}R)")
        print(f"   Risk/Sh  : {curr_sym}{plan.get('risk_per_share')} | R:R: {plan.get('reward_risk')}")
        print(f"   Cutoff   : {plan.get('flat_by')} ({'IST' if active_mkt == 'IN' else 'ET'})")
    elif entry:
        print(f" Active Trigger: {entry.get('symbol')} ({entry.get('status')}) at {curr_sym}{entry.get('price')}")
    else:
        print(" No active trade plan in trader/plan.json.")

    if orders:
        ord_list = orders.get("orders", []) if isinstance(orders, dict) else (orders if isinstance(orders, list) else [])
        print(f" Staged Orders       : {len(ord_list)} order(s) ready in trader/orders.json")

    print("=" * 68)
    print(" Market Switch Commands:")
    print("   python desk.py switch in        # Switch to 🇮🇳 Indian Markets (NSE/BSE)")
    print("   python desk.py switch us        # Switch to 🇺🇸 US Markets (NYSE/NASDAQ)")
    print(" Quick Operations:")
    print("   python desk.py scan             # Scan watchlist for breakouts")
    print("   python desk.py news <TICKER>    # Check breaking news & disclosures")
    print("   python desk.py sim              # Run Time Machine Monte Carlo simulation")
    print("   python desk.py test-loop        # Run full simulated trade cycle")
    print("=" * 68)


def cmd_scan(args):
    symbols = args.symbols or get_watchlist_symbols()
    if args.daily:
        print(f"[*] Running pre-market daily scan for {symbols}...")
        subargs = ["daily", "--symbols", symbols]
        if args.offline:
            subargs.extend(["--offline", args.offline])
        run_script("trader-scanner/scan.py", subargs)
    else:
        print(f"[*] Running 15-minute Opening Range Breakout scan for {symbols}...")
        subargs = ["orb", "--symbols", symbols]
        if args.at:
            subargs.extend(["--at", args.at])
        if args.offline:
            subargs.extend(["--offline", args.offline])
        if args.now:
            subargs.extend(["--now", args.now])
        run_script("trader-scanner/scan.py", subargs)


def cmd_news(args):
    ticker = args.ticker.upper()
    active_mkt = get_active_market()
    if active_mkt == "IN" and not (ticker.endswith(".NS") or ticker.endswith(".BO")):
        ticker = ticker + ".NS"
    print(f"[*] Fetching breaking headlines & disclosures for {ticker}...")
    run_script("trader-news/news.py", ["--tickers", ticker, "--hours", str(args.hours)])


def cmd_entry(args):
    ticker = args.ticker.upper()
    active_mkt = get_active_market()
    if active_mkt == "IN" and not (ticker.endswith(".NS") or ticker.endswith(".BO")):
        ticker = ticker + ".NS"
    print(f"[*] Checking breakout entry trigger for {ticker}...")
    subargs = ["check", ticker, "--write"]
    if args.setup:
        subargs.extend(["--setup", args.setup])
    if args.level:
        subargs.extend(["--level", str(args.level)])
    if args.interval:
        subargs.extend(["--interval", args.interval])
    if args.now:
        subargs.extend(["--now", args.now])
    if args.offline:
        subargs.extend(["--offline", args.offline])
    run_script("trader-entry/entry.py", subargs)


def cmd_plan(args):
    active_mkt = get_active_market()
    print("[*] Formulating Exit Plan (Stop-Loss, Target, Cutoff)...")
    subargs = ["plan", "--write"]
    symbol = args.symbol
    if symbol:
        symbol = symbol.upper()
        if active_mkt == "IN" and not (symbol.endswith(".NS") or symbol.endswith(".BO")):
            symbol = symbol + ".NS"
        subargs.extend(["--symbol", symbol])
    if args.entry:
        subargs.extend(["--entry", str(args.entry)])
    if args.or_high and args.or_low:
        subargs.extend(["--or-high", str(args.or_high), "--or-low", str(args.or_low)])
    if args.stop:
        subargs.extend(["--stop", args.stop])
    if args.target:
        subargs.extend(["--target", args.target])
    flat_by = args.flat_by or ("15:15" if active_mkt == "IN" else "15:55")
    subargs.extend(["--flat-by", flat_by])
    run_script("trader-exit/exit.py", subargs)


def cmd_sim(args):
    active_mkt = get_active_market()
    print("[*] Launching Time Machine: 10,000 Monte Carlo Replays + Past Hit Rate...")
    subargs = ["run", "--write"]
    symbol = args.symbol
    if symbol:
        symbol = symbol.upper()
        if active_mkt == "IN" and not (symbol.endswith(".NS") or symbol.endswith(".BO")):
            symbol = symbol + ".NS"
        subargs.extend(["--symbol", symbol])
    if args.date:
        subargs.extend(["--date", args.date])
    if args.entry and args.stop and args.target:
        subargs.extend(["--entry", str(args.entry), "--stop", str(args.stop), "--target", str(args.target)])
    if args.entry_time:
        subargs.extend(["--entry-time", args.entry_time])
    if args.replays:
        subargs.extend(["--replays", str(args.replays)])
    if args.seed is not None:
        subargs.extend(["--seed", str(args.seed)])
    if args.offline:
        subargs.extend(["--offline", args.offline])
    until = args.until or ("15:30" if active_mkt == "IN" else "16:00")
    subargs.extend(["--until", until])

    ret = run_script("trader-timemachine/timemachine.py", subargs)
    if ret == 0:
        print("\n[*] Generating ASCII Fan Chart...")
        run_script("trader-timemachine/timemachine.py", ["chart", "--from", TIMEMACHINE_PATH])


def cmd_size(args):
    print("[*] Sizing order according to your budget and max loss per trade...")
    subargs = ["--write"]
    if args.limit:
        subargs.append("--limit")
    if args.now:
        subargs.extend(["--now", args.now])
    run_script("trader-budget/size.py", subargs)


def cmd_risk(args):
    print("[*] Running pre-trade risk firewall...")
    subargs = []
    if args.now:
        subargs.extend(["--now", args.now])
    run_script("trader-risk/check.py", subargs)


def cmd_ticket(args):
    print("[*] Rendering broker order ticket...")
    run_script("trader-broker/ticket.py", ["show"])


def cmd_alerts(args):
    if args.add_plan:
        print("[*] Adding alerts from active plan (Stop, Target, Flat-by cutoff)...")
        run_script("trader-alerts/alerts.py", ["add", "--from-plan"])
    elif args.quote:
        sym = args.quote.upper()
        if get_active_market() == "IN" and not (sym.endswith(".NS") or sym.endswith(".BO")):
            sym = sym + ".NS"
        print(f"[*] Getting fresh quote for {sym}...")
        run_script("trader-alerts/alerts.py", ["quote", sym, "--write"])
    else:
        print("[*] Checking active price alerts...")
        run_script("trader-alerts/alerts.py", ["check"])


def cmd_test_loop(market_arg=None):
    active_mkt = (market_arg or get_active_market()).upper()

    if active_mkt == "IN":
        print("=" * 70)
        print("    RUNNING INDIAN MARKET DRY RUN (SIMULATED 7-STEP CYCLE)")
        print("=" * 70)
        print("Simulating NSE session on real RELIANCE.NS market data in INR (₹)...\n")

        # Step 1: Scanner
        print("--- [STEP 1/7] CHART SCANNER: Scanning NSE Watchlist ---")
        run_script("trader-scanner/scan.py", [
            "daily", "--symbols", "RELIANCE.NS,TCS.NS,INFY.NS"
        ])

        # Step 2: News
        print("\n--- [STEP 2/7] NEWS RADAR: Checking RELIANCE.NS Headlines ---")
        run_script("trader-news/news.py", ["--tickers", "RELIANCE.NS", "--hours", "24"])

        # Step 3: Entry
        print("\n--- [STEP 3/7] ENTRY TIMER: Checking Confirmed 5-Min Close ---")
        reliance_fixture = os.path.join(ROOT, "tests", "fixtures", "trader-entry", "RELIANCE.NS-5m.json")
        run_script("trader-entry/entry.py", [
            "check", "RELIANCE.NS", "--offline", reliance_fixture, "--now", "2026-10-23 04:05Z", "--write"
        ])

        # Step 4: Exit Plan
        print("\n--- [STEP 4/7] EXIT PLANNER: Formulating Stop, Target & 15:15 IST Square-off ---")
        run_script("trader-exit/exit.py", [
            "plan", "--symbol", "RELIANCE.NS", "--entry", "1195.00", "--or-high", "1194.30", "--or-low", "1183.00",
            "--stop", "or-low", "--target", "1R", "--flat-by", "15:15", "--write"
        ])

        # Step 5: Budget Sizing
        print("\n--- [STEP 5/7] BUDGET SIZING: Sizing to ₹1,00,000 budget & ₹1,000 Max Loss ---")
        run_script("trader-budget/size.py", ["--write"])

        # Step 6: Risk Firewall
        print("\n--- [STEP 6/7] RISK FIREWALL (10 GATES FOR NSE) ---")
        run_script("trader-risk/check.py", ["--now", "2026-10-23 04:30Z"])

        # Step 7: Execution Ticket
        print("\n--- [STEP 7/7] ZERODHA KITE / NSE MIS INTRADAY TICKET ---")
        run_script("trader-broker/ticket.py", ["show"])

        print("\n" + "=" * 70)
        print("SUCCESS: Indian Market 7-Step Cycle Passed Cleanly from Scan to Ticket!")
        print("=" * 70)

    else:
        print("=" * 70)
        print("      RUNNING US MARKET DRY RUN (SIMULATED 7-STEP CYCLE)")
        print("=" * 70)
        print("Simulating Monday 2026-10-19 10:15 AM ET on real TSLA market data...\n")

        # Step 1: Scanner
        print("--- [STEP 1/7] CHART SCANNER: Finding Opening-Range Breakouts ---")
        wall_fixture = os.path.join(ROOT, "tests", "fixtures", "trader-scanner", "wall5m-2026-10-19.json.gz")
        run_script("trader-scanner/scan.py", [
            "orb", "--offline", wall_fixture, "--now", "2026-10-19 10:15", "--symbols", "TSLA,NVDA,AAPL", "--min-price", "0"
        ])

        # Step 2: News
        print("\n--- [STEP 2/7] NEWS MONITOR: Checking TSLA Breaking News & Filings ---")
        run_script("trader-news/news.py", ["--tickers", "TSLA", "--no-sec", "--hours", "12"])

        # Step 3: Entry
        print("\n--- [STEP 3/7] ENTRY TIMER: Checking Confirmed 5-Min Close ---")
        entry_fixture = os.path.join(ROOT, "tests", "fixtures", "trader-entry", "TSLA-2026-10-19-5m.json")
        run_script("trader-entry/entry.py", [
            "check", "TSLA", "--offline", entry_fixture, "--now", "2026-10-19 10:15", "--write"
        ])

        # Step 4: Exit Plan
        print("\n--- [STEP 4/7] EXIT PLANNER: Formulating Stop, Target & Cutoff ---")
        run_script("trader-exit/exit.py", [
            "plan", "--symbol", "TSLA", "--entry", "364.18", "--or-high", "362.18", "--or-low", "354.47",
            "--stop", "or-mid", "--target", "1R", "--flat-by", "15:55", "--now", "2026-10-19 10:15", "--write"
        ])

        # Step 5: Budget Sizing
        print("\n--- [STEP 5/7] BUDGET SIZING: Sizing to $5,000 account & $50 Max Loss ---")
        run_script("trader-budget/size.py", ["--now", "2026-10-19 10:15", "--write"])

        # Step 6: Risk Firewall
        print("\n--- [STEP 6/7] RISK FIREWALL & EXECUTION TICKET ---")
        run_script("trader-risk/check.py", ["--now", "2026-10-19 10:15"])

        # Step 7: Order Ticket
        print("\n--- [STEP 7/7] ALPACA PAPER ORDER TICKET ---")
        run_script("trader-broker/ticket.py", ["show"])

        print("\n" + "=" * 70)
        print("SUCCESS: US Market 7-Step Cycle Passed Cleanly from Scan to Ticket!")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Unified Trading Desk CLI with Dual-Market Support (Indian & US)")
    parser.add_argument("--market", choices=["in", "us", "IN", "US"], help="Run command with specific market override")
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Show trading desk status, active market, and active plan")

    # switch
    p_switch = subparsers.add_parser("switch", help="Switch active market between Indian Markets ('in') and US Markets ('us')")
    p_switch.add_argument("target", choices=["in", "us", "IN", "US", "india", "usa"], help="Target market: 'in' or 'us'")

    # scan
    p_scan = subparsers.add_parser("scan", help="Run chart scanner")
    p_scan.add_argument("--daily", action="store_true", help="Run pre-market daily scan")
    p_scan.add_argument("--symbols", help="Comma-separated symbols to scan")
    p_scan.add_argument("--at", help="Cut the clock at HH:MM")
    p_scan.add_argument("--now", help="Simulate date/time")
    p_scan.add_argument("--offline", help="Path to offline chart fixture")

    # news
    p_news = subparsers.add_parser("news", help="Check breaking news & filings")
    p_news.add_argument("ticker", help="Stock ticker (e.g. RELIANCE.NS or TSLA)")
    p_news.add_argument("--hours", type=int, default=12, help="Hours of news to fetch")

    # entry
    p_entry = subparsers.add_parser("entry", help="Check bar-by-bar entry trigger")
    p_entry.add_argument("ticker", help="Stock ticker (e.g. RELIANCE.NS or TSLA)")
    p_entry.add_argument("--setup", choices=["orb", "level"], default="orb")
    p_entry.add_argument("--level", type=float)
    p_entry.add_argument("--interval", choices=["5m", "1m"], default="5m")
    p_entry.add_argument("--now")
    p_entry.add_argument("--offline")

    # plan
    p_plan = subparsers.add_parser("plan", help="Formulate exit plan")
    p_plan.add_argument("--symbol")
    p_plan.add_argument("--entry", type=float)
    p_plan.add_argument("--or-high", type=float)
    p_plan.add_argument("--or-low", type=float)
    p_plan.add_argument("--stop", default="or-mid")
    p_plan.add_argument("--target", default="1R")
    p_plan.add_argument("--flat-by")

    # sim / timemachine
    p_sim = subparsers.add_parser("sim", help="Run 10,000 Monte Carlo replays")
    p_sim.add_argument("--symbol")
    p_sim.add_argument("--date")
    p_sim.add_argument("--entry", type=float)
    p_sim.add_argument("--stop", type=float)
    p_sim.add_argument("--target", type=float)
    p_sim.add_argument("--entry-time")
    p_sim.add_argument("--replays", type=int, default=10000)
    p_sim.add_argument("--seed", type=int, default=19)
    p_sim.add_argument("--until")
    p_sim.add_argument("--offline")

    # size
    p_size = subparsers.add_parser("size", help="Size order based on max loss")
    p_size.add_argument("--limit", action="store_true")
    p_size.add_argument("--now")

    # risk
    p_risk = subparsers.add_parser("risk", help="Check order against risk firewall")
    p_risk.add_argument("--now")

    # ticket
    subparsers.add_parser("ticket", help="Show execution tickets")

    # alerts
    p_alerts = subparsers.add_parser("alerts", help="Manage price alerts")
    p_alerts.add_argument("--add-plan", action="store_true", help="Add alerts from active plan")
    p_alerts.add_argument("--quote", help="Get quote for ticker")

    # test-loop
    p_loop = subparsers.add_parser("test-loop", help="Run complete end-to-end simulated trade cycle")
    p_loop.add_argument("--market", choices=["in", "us", "IN", "US"], help="Run test loop on specific market")

    args = parser.parse_args()

    if args.market:
        switch_market(args.market)

    if not args.command or args.command == "status":
        cmd_status()
    elif args.command == "switch":
        switch_market(args.target)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "news":
        cmd_news(args)
    elif args.command == "entry":
        cmd_entry(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "sim":
        cmd_sim(args)
    elif args.command == "size":
        cmd_size(args)
    elif args.command == "risk":
        cmd_risk(args)
    elif args.command == "ticket":
        cmd_ticket(args)
    elif args.command == "alerts":
        cmd_alerts(args)
    elif args.command == "test-loop":
        cmd_test_loop(getattr(args, "market", None))


if __name__ == "__main__":
    main()
