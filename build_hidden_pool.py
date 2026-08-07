"""
build_hidden_pool.py — generate a curated hidden_pool.json for production hidden picks

Why: picking hidden randomly from full pool.json (1696 events) can surface buggy
or boring markets (low volume, 1 strike, extreme price, confusing LOC).
This builds a vetted subset (~270) you can manually edit.

Usage:
  python3 build_hidden_pool.py                 # rebuild hidden_pool.json from current pool.json
  python3 build_hidden_pool.py --check         # audit current hidden_pool vs pool
  # then edit hidden_pool.json or hidden_tickers.txt and commit
  # to force a single known hidden (e.g., for debugging) put exactly one entry in hidden_pool.json

Guards for hidden (avoid bugs):
  volume >= 20k, price 5-94, strikes 2-50, name >=20 chars & >=3 words
  balanced across broads: politics 80 / sports 70 / business 60 / culture 40 / prices 10 / weather ~10
  keeps World vs Peru fixes, IN vs India, etc. (requires pool.json built with word-boundary geo)
"""
import json, random, sys
from pathlib import Path
from collections import Counter

POOL = Path(__file__).parent / "pool.json"
HIDDEN = Path(__file__).parent / "hidden_pool.json"
TXT = Path(__file__).parent / "hidden_tickers.txt"

def is_good(p):
    if p.get("volume", 0) < 20000: return False
    if p.get("price", 50) < 5 or p.get("price", 50) > 94: return False
    if p.get("strikes", 2) < 2 or p.get("strikes", 2) > 50: return False
    if len(p.get("name","")) < 20: return False
    if len(p.get("name","").split()) < 3: return False
    # exclude any remaining N/A location that is not prices (prices are always N/A)
    # (weather/business/etc should have real LOC)
    # but keep prices as is
    return True

def build():
    pool = json.loads(POOL.read_text())
    candidates = [p for p in pool if is_good(p)]
    print(f"candidates {len(candidates)}/{len(pool)} pass guards")
    targets = {"politics": 80, "sports": 70, "business": 60, "culture": 40, "prices": 10, "weather": 10}
    by_broad = {b: [p for p in candidates if p["broad"]==b] for b in targets}
    hidden = []
    random.seed(42)
    for broad, want in targets.items():
        lst = sorted(by_broad[broad], key=lambda x: x["volume"], reverse=True)
        pool_broad = lst[:want*3] if len(lst) > want*3 else lst
        if len(pool_broad) <= want:
            chosen = pool_broad
        else:
            top = pool_broad[:want//2]
            rest = pool_broad[want//2:]
            chosen = top + random.sample(rest, want - len(top))
        hidden.extend(chosen)
        print(f"  {broad:9} {len(chosen):3} / {len(by_broad[broad]):3} (want {want})")
    random.shuffle(hidden)
    HIDDEN.write_text(json.dumps(hidden, indent=2))
    TXT.write_text("\n".join(f"{p['ticker']} | {p['broad']} | {p['location']} | {p['name']}" for p in hidden) + "\n")
    print(f"Wrote {HIDDEN} ({len(hidden)}) and {TXT}")
    print(Counter(p["broad"] for p in hidden))

def check():
    if not HIDDEN.exists():
        print("hidden_pool.json missing — run build_hidden_pool.py")
        return
    pool = {p["ticker"]: p for p in json.loads(POOL.read_text())}
    hidden = json.loads(HIDDEN.read_text())
    missing = [p for p in hidden if p["ticker"] not in pool]
    stale_loc = []
    for p in hidden:
        cur = pool.get(p["ticker"])
        if cur and cur["location"] != p["location"]:
            stale_loc.append((p["ticker"], p["location"], cur["location"]))
    print(f"hidden {len(hidden)}, missing from pool {len(missing)}, stale LOC {len(stale_loc)}")
    for m in missing[:5]: print(" missing", m["ticker"], m["name"][:60])
    for t in stale_loc[:10]: print(" stale", t)

if __name__ == "__main__":
    if "--check" in sys.argv: check()
    else: build()
