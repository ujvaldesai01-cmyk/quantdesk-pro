#!/usr/bin/env python3
"""Local Web Server for Day Trader Platform with Dual-Market Support.
Serves the web UI and provides REST API endpoints to run all 11 skills
across both Indian Markets (NSE/BSE) and US Markets (NYSE/NASDAQ).
"""

import datetime
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.parse

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 8080))
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
SCANNER_PATH = os.path.join(ROOT, "trader", "watchlist.json")
RISK_PATH = os.path.join(ROOT, "trader", "state", "risk.json")
WEB_DIR = os.path.join(ROOT, "web")


def load_json(path):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def get_active_market():
    cfg = load_json(CONFIG_PATH) or {}
    return cfg.get("active_market", "IN").upper()


def get_watchlist(market=None):
    mkt = (market or get_active_market()).upper()
    target_file = WATCHLIST_IN_FILE if mkt == "IN" else WATCHLIST_US_FILE
    if os.path.isfile(target_file):
        with open(target_file, "r", encoding="utf-8") as f:
            syms = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]
            if syms:
                return syms
    if os.path.isfile(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            syms = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]
            if syms:
                return syms
    if mkt == "IN":
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "TATAMOTORS.NS"]
    return ["AAPL", "AMZN", "AMD", "GOOGL", "META", "MSFT", "NVDA", "PLTR", "QQQ", "SPY", "TSLA"]


def get_market_clocks():
    try:
        import zoneinfo
        tz_ist = zoneinfo.ZoneInfo("Asia/Kolkata")
        tz_ny = zoneinfo.ZoneInfo("America/New_York")
        ist = datetime.datetime.now(tz_ist)
        ny = datetime.datetime.now(tz_ny)
    except Exception:
        utc = datetime.datetime.now(datetime.timezone.utc)
        ist = utc + datetime.timedelta(hours=5, minutes=30)
        ny = utc + datetime.timedelta(hours=-4)

    # 1. Indian Standard Time (IST: UTC+5:30)
    ist_time = ist.time()
    is_in_open = (ist.weekday() < 5 and datetime.time(9, 15) <= ist_time < datetime.time(15, 30))
    is_in_pre = (ist.weekday() < 5 and datetime.time(9, 0) <= ist_time < datetime.time(9, 15))
    is_in_post = (ist.weekday() < 5 and datetime.time(15, 30) <= ist_time < datetime.time(16, 0))

    if is_in_open:
        in_status = "NSE OPEN"
    elif is_in_pre:
        in_status = "NSE PRE-MKT"
    elif is_in_post:
        in_status = "POST-MARKET"
    else:
        in_status = "NSE CLOSED"

    clock_in = {
        "market": "IN",
        "name": "Mumbai / NSE",
        "time": ist.strftime("%H:%M:%S IST"),
        "date": ist.strftime("%Y-%m-%d"),
        "is_market_open": is_in_open,
        "is_pre_market": is_in_pre,
        "is_post_market": is_in_post,
        "status_text": in_status,
        "timezone": "IST"
    }

    # 2. US Eastern Time (ET: New York)
    ny_time = ny.time()
    is_us_open = (ny.weekday() < 5 and datetime.time(9, 30) <= ny_time < datetime.time(16, 0))
    is_us_pre = (ny.weekday() < 5 and datetime.time(4, 0) <= ny_time < datetime.time(9, 30))
    is_us_post = (ny.weekday() < 5 and datetime.time(16, 0) <= ny_time < datetime.time(20, 0))

    if is_us_open:
        us_status = "NYSE OPEN"
    elif is_us_pre:
        us_status = "NYSE PRE-MKT"
    elif is_us_post:
        us_status = "POST-MARKET"
    else:
        us_status = "MARKET CLOSED"

    clock_us = {
        "market": "US",
        "name": "New York / NYSE",
        "time": ny.strftime("%H:%M:%S ET"),
        "date": ny.strftime("%Y-%m-%d"),
        "is_market_open": is_us_open,
        "is_pre_market": is_us_pre,
        "is_post_market": is_us_post,
        "status_text": us_status,
        "timezone": "ET"
    }

    active_mkt = get_active_market()
    return {
        "in": clock_in,
        "us": clock_us,
        "active": clock_in if active_mkt == "IN" else clock_us
    }


def get_market_info(market=None):
    mkt = (market or get_active_market()).upper()
    if mkt == "IN":
        return {
            "code": "IN",
            "name": "Indian Markets (NSE / BSE)",
            "short_name": "Indian Markets",
            "exchange": "NSE",
            "currency": "INR",
            "currency_symbol": "₹",
            "flag": "🇮🇳",
            "timezone": "IST",
            "hours": "09:15 - 15:30 IST",
            "flat_by": "15:15 IST",
            "broker_label": "Zerodha Kite Connect (NSE MIS)",
            "default_ticker": "RELIANCE.NS"
        }
    return {
        "code": "US",
        "name": "US Markets (NYSE / NASDAQ)",
        "short_name": "US Markets",
        "exchange": "NYSE",
        "currency": "USD",
        "currency_symbol": "$",
        "flag": "🇺🇸",
        "timezone": "ET",
        "hours": "09:30 - 16:00 ET",
        "flat_by": "15:55 ET",
        "broker_label": "Alpaca Paper Trading",
        "default_ticker": "TSLA"
    }


class TradingDeskHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_json(self.get_full_status())
        elif parsed.path == "/api/health":
            self.send_json({"status": "ok", "live": True, "active_market": get_active_market()})
        elif parsed.path == "/api/timemachine":
            tm = load_json(TIMEMACHINE_PATH) or {}
            self.send_json(tm)
        elif parsed.path == "/api/news":
            query = urllib.parse.parse_qs(parsed.query)
            active_mkt = get_active_market()
            default_sym = "RELIANCE.NS" if active_mkt == "IN" else "TSLA"
            ticker = query.get("ticker", [default_sym])[0].upper()
            if active_mkt == "IN" and not (ticker.endswith(".NS") or ticker.endswith(".BO")):
                ticker = ticker + ".NS"
            cmd = [PYTHON, os.path.join(ROOT, "desk.py"), "news", ticker]
            res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.send_json({"output": res.stdout + "\n" + res.stderr, "ticker": ticker})
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if parsed.path == "/api/set-market":
            target = data.get("market", "IN").upper()
            cmd = [PYTHON, os.path.join(ROOT, "desk.py"), "switch", target]
            res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.send_json({
                "success": (res.returncode == 0),
                "output": res.stdout + "\n" + res.stderr,
                "active_market": get_active_market(),
                "status": self.get_full_status()
            })
        elif parsed.path == "/api/run":
            cmd_type = data.get("command")
            output, code = self.execute_command(cmd_type, data)
            self.send_json({
                "success": (code == 0),
                "code": code,
                "output": output,
                "status": self.get_full_status()
            })
        elif parsed.path == "/api/save-config":
            try:
                new_cfg = data.get("config", {})
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(new_cfg, f, indent=2)
                self.send_json({"success": True, "config": new_cfg, "status": self.get_full_status()})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)
        elif parsed.path == "/api/save-watchlist":
            try:
                symbols = data.get("symbols", [])
                active_mkt = get_active_market()
                # Save to active watchlist file
                with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(symbols) + "\n")
                # Also save to market-specific watchlist file
                mkt_file = WATCHLIST_IN_FILE if active_mkt == "IN" else WATCHLIST_US_FILE
                with open(mkt_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(symbols) + "\n")
                self.send_json({"success": True, "symbols": symbols, "market": active_mkt})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def get_full_status(self):
        active_mkt = get_active_market()
        clocks = get_market_clocks()
        return {
            "active_market": active_mkt,
            "market_info": get_market_info(active_mkt),
            "config": load_json(CONFIG_PATH) or {},
            "watchlist": get_watchlist(active_mkt),
            "watchlist_in": get_watchlist("IN"),
            "watchlist_us": get_watchlist("US"),
            "scanner": load_json(SCANNER_PATH),
            "plan": load_json(PLAN_PATH),
            "entry": load_json(ENTRY_PATH),
            "orders": load_json(ORDERS_PATH),
            "timemachine_summary": self.get_tm_summary(),
            "risk": load_json(RISK_PATH),
            "clock": clocks["active"],
            "clocks": clocks
        }

    def get_tm_summary(self):
        tm = load_json(TIMEMACHINE_PATH)
        if not tm or "mc" not in tm:
            return None
        mc = tm["mc"]
        plan = tm.get("plan", {})
        return {
            "symbol": plan.get("symbol"),
            "entry": plan.get("entry"),
            "stop": plan.get("stop"),
            "target": plan.get("target"),
            "p_target": mc.get("p_target"),
            "p_stop": mc.get("p_stop"),
            "p_neither": mc.get("p_neither"),
            "p_green": mc.get("p_green"),
            "median_close": mc.get("median_close"),
            "p5_close": mc.get("p5_close"),
            "p95_close": mc.get("p95_close"),
            "avg_R": mc.get("avg_R"),
            "replays": mc.get("replays"),
            "seed": mc.get("seed")
        }

    def execute_command(self, cmd_type, data):
        desk_py = os.path.join(ROOT, "desk.py")
        cmd = [PYTHON, desk_py]
        active_mkt = get_active_market()

        if cmd_type == "test-loop":
            cmd.extend(["test-loop", "--market", active_mkt])
        elif cmd_type == "switch-market":
            target = data.get("market", "IN")
            cmd.extend(["switch", target])
        elif cmd_type == "scan-daily":
            cmd.extend(["scan", "--daily"])
            symbols = data.get("symbols")
            if symbols:
                cmd.extend(["--symbols", symbols])
        elif cmd_type == "scan-orb":
            cmd.append("scan")
            symbols = data.get("symbols")
            if symbols:
                cmd.extend(["--symbols", symbols])
        elif cmd_type == "scan-fixture":
            if active_mkt == "IN":
                cmd.extend(["scan", "--daily", "--symbols", "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS"])
            else:
                wall_fixture = os.path.join(ROOT, "tests", "fixtures", "trader-scanner", "wall5m-2026-10-19.json.gz")
                cmd.extend(["scan", "--offline", wall_fixture, "--now", "2026-10-19 10:15", "--symbols", "TSLA,NVDA,AAPL,MSFT,AMD,PLTR"])
        elif cmd_type == "news":
            default_t = "RELIANCE.NS" if active_mkt == "IN" else "TSLA"
            ticker = data.get("ticker", default_t).upper()
            if active_mkt == "IN" and not (ticker.endswith(".NS") or ticker.endswith(".BO")):
                ticker = ticker + ".NS"
            cmd.extend(["news", ticker])
        elif cmd_type == "sim":
            if active_mkt == "IN":
                ticker = data.get("symbol", "RELIANCE.NS").upper()
                if not (ticker.endswith(".NS") or ticker.endswith(".BO")):
                    ticker = ticker + ".NS"
                entry = str(data.get("entry", 1195.00))
                stop = str(data.get("stop", 1183.00))
                target = str(data.get("target", 1207.00))
                cmd.extend(["sim", "--symbol", ticker, "--date", "2026-10-23", "--entry", entry, "--stop", stop, "--target", target, "--entry-time", "09:35 AM", "--until", "15:30"])
            else:
                ticker = data.get("symbol", "TSLA").upper()
                entry = str(data.get("entry", 364.18))
                stop = str(data.get("stop", 358.32))
                target = str(data.get("target", 370.04))
                cmd.extend(["sim", "--symbol", ticker, "--date", "2026-10-19", "--entry", entry, "--stop", stop, "--target", target, "--entry-time", "10:15 AM", "--until", "16:00"])
        elif cmd_type == "plan":
            if active_mkt == "IN":
                ticker = data.get("symbol", "RELIANCE.NS").upper()
                if not (ticker.endswith(".NS") or ticker.endswith(".BO")):
                    ticker = ticker + ".NS"
                entry = str(data.get("entry", 1195.00))
                or_high = str(data.get("or_high", 1194.30))
                or_low = str(data.get("or_low", 1183.00))
                cmd.extend(["plan", "--symbol", ticker, "--entry", entry, "--or-high", or_high, "--or-low", or_low, "--stop", "or-low", "--target", "1R", "--flat-by", "15:15"])
            else:
                ticker = data.get("symbol", "TSLA").upper()
                entry = str(data.get("entry", 364.18))
                or_high = str(data.get("or_high", 362.18))
                or_low = str(data.get("or_low", 354.47))
                cmd.extend(["plan", "--symbol", ticker, "--entry", entry, "--or-high", or_high, "--or-low", or_low, "--stop", "or-mid", "--target", "1R", "--flat-by", "15:55"])
        elif cmd_type == "size":
            cmd.append("size")
        elif cmd_type == "risk":
            cmd.append("risk")
        elif cmd_type == "ticket":
            cmd.append("ticket")
        else:
            return f"Unknown command: {cmd_type}", 1

        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        return (res.stdout + "\n" + res.stderr).strip(), res.returncode


def run_server():
    os.makedirs(WEB_DIR, exist_ok=True)
    server_address = ("0.0.0.0", PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, TradingDeskHandler)
    print(f"QuantDesk Web Server running live at http://0.0.0.0:{PORT} (Dual-Market Engine)")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
