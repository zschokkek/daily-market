"""
server.py — tiny static + logging server for Kalshi Wordle

Serves the game and logs which market is chosen (daily target + guesses).

  python3 server.py
  # serves on http://localhost:8000  (serves index.html + pool.json)
  # POST /log  or /api/log  with JSON  -> appends to chosen.log

Log lines are JSON per line, easy to tail:
  tail -f chosen.log | python3 -m json.tool
"""
import json, os, datetime
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

LOG_FILE = os.path.join(os.path.dirname(__file__), "chosen.log")

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        # chosen market endpoint for frontend sync — prefers hidden_pool.json if present (curated production)
        if parsed.path in ("/chosen","/api/chosen"):
            try:
                import pathlib, random, datetime
                pool_path = os.path.join(os.getcwd(), "pool.json")
                hidden_path = os.path.join(os.getcwd(), "hidden_pool.json")
                chosen_path = os.path.join(os.getcwd(), "chosen.txt")
                chosen_name = None
                if os.path.exists(chosen_path):
                    try:
                        chosen_name = pathlib.Path(chosen_path).read_text().strip().splitlines()[-1] if pathlib.Path(chosen_path).read_text().strip() else None
                    except: pass
                pool = json.loads(pathlib.Path(pool_path).read_text()) if os.path.exists(pool_path) else []
                hidden = json.loads(pathlib.Path(hidden_path).read_text()) if os.path.exists(hidden_path) else []
                pick_from = hidden if hidden else pool
                chosen = None
                if chosen_name:
                    for p in pick_from:
                        if p.get("name")==chosen_name:
                            chosen=p; break
                    if not chosen:
                        for p in pool:
                            if p.get("name")==chosen_name:
                                chosen=p; break
                if not chosen and pick_from:
                    # hidden_pool: deterministic daily pick by date (reorder hidden_pool.json to control sequence) — ET midnight
                    if hidden:
                        try:
                            from zoneinfo import ZoneInfo
                            today = datetime.datetime.now(ZoneInfo("America/New_York")).date()
                        except:
                            today = datetime.datetime.now(datetime.timezone.utc).date()
                        ref = datetime.date(2026,8,7)
                        days = (today - ref).days
                        idx = days % len(hidden)
                        chosen = hidden[idx]
                        # map to pool entry so price/vol stay live
                        pool_match = next((p for p in pool if p.get("ticker")==chosen.get("ticker")), None)
                        if pool_match: chosen = pool_match
                    else:
                        chosen = random.choice(sorted(pick_from, key=lambda x: x.get("event_ticker") or x.get("ticker") or ""))
                    try:
                        pathlib.Path(chosen_path).write_text(chosen.get("name","")+"\n")
                    except: pass
                body = json.dumps(chosen or {}).encode()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as e:
                print(f"[CHOSEN ERROR] {e}")
        # autocomplete backend: /autocomplete?q=xxx  or /api/autocomplete
        if parsed.path in ("/autocomplete","/api/autocomplete"):
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query)
            q = (qs.get("q", [""])[0] or "").lower().strip()
            limit = int((qs.get("limit", ["14"])[0] or "14"))
            try:
                pool_path = os.path.join(os.getcwd(), "pool.json")
                if os.path.exists(pool_path):
                    import pathlib
                    pool = json.loads(pathlib.Path(pool_path).read_text())
                    # filter by name/ticker/broad/subcat, exclude already guessed via ?exclude=...
                    filtered = []
                    for p in pool:
                        if q and q not in (p.get("name","").lower() + " " + p.get("ticker","").lower() + " " + p.get("broad","").lower() + " " + p.get("subcat","").lower()):
                            continue
                        filtered.append(p)
                        if len(filtered) >= limit:
                            break
                    # sort by volume desc for relevance when q empty
                    if not q:
                        filtered = sorted(filtered, key=lambda x: x.get("volume",0), reverse=True)[:limit]
                    body = json.dumps(filtered).encode()
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.send_header("Access-Control-Allow-Origin","*")
                    self.end_headers()
                    self.wfile.write(body)
                    # log autocomplete query
                    print(f"[AUTOCOMPLETE] q='{q}' -> {len(filtered)} results")
                    return
            except Exception as e:
                print(f"[AUTOCOMPLETE ERROR] {e}")
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            self.wfile.write(b'[]')
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/log","/api/log"):
            self.send_error(404, "not found")
            return
        length = int(self.headers.get("Content-Length",0) or 0)
        body = self.rfile.read(length).decode() if length else "{}"
        try:
            data = json.loads(body) if body else {}
        except:
            data = {"raw": body}
        entry = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ip": self.client_address[0],
            "path": parsed.path,
            "data": data,
        }
        # append to log
        with open(LOG_FILE,"a") as f:
            f.write(json.dumps(entry)+"\n")
        # python terminal logging — hidden unless --show-market / KALSHI_SHOW_MARKET=1
        if data.get("type")=="chosen":
            target = data.get("target")
            name = target.get("name") if isinstance(target, dict) else str(target)
            if SHOW_MARKET: print(name)
            else: print("[HIDDEN] market chosen (use --show-market to reveal)")
            # also log plain name to file for inspection
            with open(os.path.join(os.getcwd(), "chosen.txt"),"a") as f:
                f.write(name+"\n")
        elif data.get("type")=="guess":
            print(f"[GUESS] {data.get('target')} -> {data.get('guesses')}")
        else:
            name = data.get("target")
            if isinstance(name, dict): name = name.get("name","")
            if name:
                if SHOW_MARKET: print(name)
                else: print("[HIDDEN]")
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin","*")
        super().end_headers()

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--dir", default=os.path.dirname(__file__))
    ap.add_argument("--show-market", action="store_true", help="show hidden market name in logs (otherwise hidden unless KALSHI_SHOW_MARKET=1)")
    args=ap.parse_args()
    SHOW_MARKET = args.show_market or os.environ.get("KALSHI_SHOW_MARKET")=="1" or os.environ.get("SHOW_MARKET")=="1"
    os.chdir(args.dir)
    # log pool size on startup and print chosen market name with python
    try:
        import pathlib, datetime
        pool_path = pathlib.Path("pool.json")
        hidden_path = pathlib.Path("hidden_pool.json")
        if pool_path.exists():
            pool = json.loads(pool_path.read_text())
            hidden = json.loads(hidden_path.read_text()) if hidden_path.exists() else []
            pick_from = hidden if hidden else pool
            from collections import Counter
            cnt = Counter(p.get("broad","?") for p in pool)
            total = len(pool)
            # also log to chosen.log startup entry — ET date for hidden rotation
            try:
                from zoneinfo import ZoneInfo
                et_today = datetime.datetime.now(ZoneInfo("America/New_York")).date()
            except:
                et_today = datetime.datetime.now(datetime.timezone.utc).date()
            startup_entry = {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "startup",
                "poolSize": total,
                "hiddenSize": len(hidden) if hidden else 0,
                "broadCounts": dict(cnt),
                "today": et_today.isoformat(),
            }
            with open(LOG_FILE,"a") as f:
                f.write(json.dumps(startup_entry)+"\n")
            # random chosen — clear cache every time server chooses new market
            import random, pathlib, shutil
            # clear cache: truncate chosen.txt / chosen.log and clear any __pycache__
            for cache_file in [os.path.join(os.getcwd(), "chosen.txt"), os.path.join(os.getcwd(), "chosen.log")]:
                try:
                    if os.path.exists(cache_file):
                        open(cache_file, "w").close()
                        print(f"[CACHE] cleared {os.path.basename(cache_file)}")
                except: pass
            # also clear python cache dirs
            for p in pathlib.Path(os.getcwd()).rglob("__pycache__"):
                try: shutil.rmtree(p, ignore_errors=True)
                except: pass
            if hidden:
                try:
                    from zoneinfo import ZoneInfo
                    today = datetime.datetime.now(ZoneInfo("America/New_York")).date()
                except:
                    today = datetime.datetime.now(datetime.timezone.utc).date()
                ref = datetime.date(2026,8,7)
                days = (today - ref).days
                idx = days % len(hidden)
                chosen = hidden[idx]
                pool_match = next((p for p in pool if p.get("ticker")==chosen.get("ticker")), None)
                if pool_match: chosen = pool_match
                print(f"[HIDDEN POOL] {len(hidden)} curated, today idx {idx} -> {chosen.get('ticker')}")
            else:
                pool_sorted = sorted(pick_from, key=lambda x: x.get("event_ticker") or x.get("ticker") or "")
                chosen = random.choice(pool_sorted) if pool_sorted else None
            if chosen:
                if SHOW_MARKET:
                    print(chosen.get("name",""))
                else:
                    print("[HIDDEN] market chosen (use --show-market to reveal)")
                with open(os.path.join(os.getcwd(), "chosen.txt"),"w") as f:
                    f.write(chosen.get("name","")+"\n")
                # also log to chosen.log fresh
                with open(LOG_FILE,"w") as f:
                    f.write(json.dumps({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "type":"chosen", "target": chosen})+"\n")
        else:
            print("[STARTUP] no pool.json found")
    except Exception as e:
        print(f"[STARTUP] pool log failed: {e}")
    print(f"Serving {args.dir} on http://localhost:{args.port}")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
