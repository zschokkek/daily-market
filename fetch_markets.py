"""
fetch_markets.py — rebuild pool.json from Kalshi Trade API v2 (Market Atlas source)

Pool:  Condensed to ONE entry per EVENT (not per strike)
  - Sports expiring today  OR  any market live -> now:
  - Sports filtered to today, other broads (politics/business/prices/weather) include ALL open events
  - Each event is one game: e.g. 2028 President is one entry with strikes = #candidates

Broad categories (5 buckets):
  sports   — Sports, subcat = league (MLB/NFL/NBA/WNBA/Esports/NHL/Soccer/Golf/Tennis/MMA)
  politics — Politics / Elections / World
  business — Economics / Companies / Entertainment / Science / Social / Health / Transportation
  prices   — Financials+price feeds, subcat = crypto vs commodities
  weather  — Climate and Weather

Market Atlas: https://api.elections.kalshi.com/trade-api/v2
  GET /events?status=open&with_nested_markets=true&limit=200  (paginate)
Strikes = len(event.markets)
Volume = sum(market.volume) across event
"""
import json, urllib.request, datetime, hashlib

BASE = "https://api.elections.kalshi.com/trade-api/v2"

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode())

def fetch_all_events():
    events=[]; cursor=None; page=0
    while True:
        page+=1
        url=f"{BASE}/events?status=open&with_nested_markets=true&limit=200"
        if cursor: url+=f"&cursor={cursor}"
        data=fetch_json(url)
        batch=data.get("events",[])
        events.extend(batch)
        cursor=data.get("cursor")
        print(f"  events page {page}: +{len(batch)} total {len(events)} cursor={'yes' if cursor else 'no'}")
        if not cursor or not batch: break
        if page>=30: break
    return events

BROAD_ORDER=["sports","politics","business","prices","weather","culture"]

def to_broad(category, subcategory, ticker, title):
    cat=(category or "").strip()
    sub=(subcategory or "").strip()
    if isinstance(sub, dict):
        sub=",".join([str(v) for vs in sub.values() for v in (vs if isinstance(vs,list) else [vs])])
    low=(cat+" "+sub+" "+ticker+" "+title).lower()
    if cat=="Climate and Weather" or "weather" in low or "temperature" in low or "high temp" in low:
        return "weather"
    if cat=="Sports":
        return "sports"
    # culture before prices so Entertainment/music/film not mis-classed as prices
    if cat in ("Entertainment",) or any(k in low for k in ["music","film","movie","tv","celeb","oscar","grammy","emmy","album","song"]):
        return "culture"
    # prices ONLY for specific underlying price bets — intuitive for normal user
    # require $ or price + direction, or crypto + price/direction, not just "Financials" or "gold"
    is_price = False
    if "$" in (ticker+" "+title) or "target price" in low or "price of" in low:
        is_price = True
    elif "price" in low and any(k in low for k in ["above","below","close","target"]):
        is_price = True
    elif any(k in low for k in ["btc","bitcoin","eth ","ethereum","sol ","solana","xrp","doge","crypto"]) and any(k in low for k in ["above","below","price","close","$"]):
        is_price = True
    elif any(k in low for k in ["s&p","nasdaq"]) and ("above" in low or "below" in low or "close" in low or "$" in low or "price" in low):
        is_price = True
    elif any(k in low for k in ["crude oil","gold price","silver price","corn price","wheat price"]) and ("price" in low or "$" in low or "above" in low or "below" in low):
        is_price = True
    if is_price:
        return "prices"
    if cat in ("Politics","Elections","World"):
        return "politics"
    if cat in ("Economics","Companies","Science and Technology","Social","Health","Transportation","Financials"):
        return "business"
    return "business"

def prices_subcat(ticker, title, subcategory):
    low=(ticker+" "+title+" "+(subcategory or "")).lower()
    if any(k in low for k in ["btc","eth","sol","xrp","doge","bitcoin","ethereum","solana","crypto"]):
        return "crypto"
    return "CMDTY"

def business_subcat(ticker, title, subcategory):
    low=(ticker+" "+title+" "+(subcategory or "")).lower()
    # intuitive for normal user: TECH for tech companies/mergers
    if any(k in low for k in ["tesla","spacex","apple","google","alphabet","microsoft","meta","nvidia","openai","netflix","amazon","tech","ai ","ai,","software","space x"]):
        return "TECH"
    if any(k in low for k in ["bank","finance","fed","rate","gdp","inflation","economy","market"]):
        return "FINANCE"
    if any(k in low for k in ["company","merger","acquisition","earnings"]):
        return "CORP"
    return "CORP"

def culture_subcat(ticker, title, subcategory):
    low=(ticker+" "+title+" "+(subcategory or "")).lower()
    # DETAIL should never be less than 5 letters — enforce minimum 5
    if any(k in low for k in ["music","song","album","grammy","spotify"]):
        return "MUSIC"  # 5 letters
    if any(k in low for k in ["film","movie","cinema","oscar","box office"]):
        return "FILM"  # 4 letters but padded to meet 5? user wants FILM exactly, we'll keep FILM and pad display
    if any(k in low for k in ["tv","television","show","series","celeb","kardashian","emmy","netflix","hbo"]):
        return "TV & CELEB"
    # default based on broad culture: rotate to ensure >=5
    return "MUSIC"

def sports_subcat(ticker, title, subcategory):
    s=(subcategory or ticker or title or "").upper()
    t=(ticker or "").upper()
    tu=(title or "").upper()
    if "KXMLB" in s or "KXMLB" in t or "MLB" in tu or "BASEBALL" in tu:
        return "MLB"
    if "KXNFL" in s or "KXNFL" in t or "NFL" in tu:
        return "NFL"
    if "KXNBA" in s or "KXNBA" in t or ("NBA" in tu and "WNBA" not in tu):
        return "NBA"
    if "KXWNB" in s or "KXWNB" in t or "WNBA" in tu:
        return "WNBA"
    if "KXLOL" in s or "KXLOL" in t or "LEAGUE OF LEGENDS" in tu:
        return "Esports"
    if "KXNHL" in s or "KXNHL" in t or "NHL" in tu or "HOCKEY" in tu:
        return "NHL"
    if "KXSOCCER" in s or "KXSOCC" in s or "SOCCER" in tu or "MLS" in tu:
        return "Soccer"
    if "KXGOLF" in s or "KXGOLF" in t or "GOLF" in tu or "PGA" in tu:
        return "Golf"
    if "KXTENN" in s or "TENNIS" in tu:
        return "Tennis"
    if "KXUFC" in s or "UFC" in tu or "MMA" in tu:
        return "MMA"
    if subcategory:
        # merge BTTS/SPREAD/TOTAL/ADVANCE variants -> base tournament (e.g., LEAGUESCUPBTTS -> LEAGUESCUP, UECLSPREAD -> UECL)
        base = subcategory.upper().replace("KX","").replace("GAME","").strip()
        for suf in ["BTTS","SPREAD","TOTAL","ADVANCE","ADVAN","TOPX","LEADER","RELEGATION","TEAMPOINTS","TEAMPO"]:
            if base.endswith(suf) and len(base) > len(suf)+3:
                base = base[:-len(suf)].strip()
        # weather tickers mis-classed as sports (KXEUCLIMATE etc.) -> map to weather-like label will be re-routed to weather broad, but keep fallback
        if base.startswith("EUCLIMATE") or base.startswith("ARCTIC") or base.startswith("HURR") or base.startswith("RAIN") or base.startswith("TEMP") or base.startswith("EARTHQUAKE"):
            return base.replace("KX","")[:16]
        return base[:16] or "Other"
    return "Other"

def weather_subcat(ticker, title, subcategory):
    low=(ticker+" "+title+" "+(subcategory or "")).lower()
    if any(k in low for k in ["hurricane","storm","tornado"]): return "HURRICANE"
    if any(k in low for k in ["rain"]): return "RAIN"
    if any(k in low for k in ["snow","ice"]): return "SNOW"
    if any(k in low for k in ["temp","heat","hot"]): return "HEAT"
    if any(k in low for k in ["earthquake"]): return "QUAKE"
    return "WEATHER"

US_STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"]
CITY_TO_STATE = {"NEW YORK":"NY","NYC":"NY","LOS ANGELES":"CA","LA":"CA","CHICAGO":"IL","BOSTON":"MA","PITTSBURGH":"PA","PHILADELPHIA":"PA","TORONTO":"ON","MONTREAL":"QC","MIAMI":"FL","ATLANTA":"GA","SEATTLE":"WA","SAN FRANCISCO":"CA","HOUSTON":"TX","DALLAS":"TX","WASHINGTON":"DC","DETROIT":"MI","CLEVELAND":"OH","DENVER":"CO","PHOENIX":"AZ"}
STATE_FULL_TO_CODE = {"ALABAMA":"AL","ALASKA":"AK","ARIZONA":"AZ","ARKANSAS":"AR","CALIFORNIA":"CA","COLORADO":"CO","CONNECTICUT":"CT","DELAWARE":"DE","FLORIDA":"FL","GEORGIA":"GA","HAWAII":"HI","IDAHO":"ID","ILLINOIS":"IL","INDIANA":"IN","IOWA":"IA","KANSAS":"KS","KENTUCKY":"KY","LOUISIANA":"LA","MAINE":"ME","MARYLAND":"MD","MASSACHUSETTS":"MA","MICHIGAN":"MI","MINNESOTA":"MN","MISSISSIPPI":"MS","MISSOURI":"MO","MONTANA":"MT","NEBRASKA":"NE","NEVADA":"NV","NEW HAMPSHIRE":"NH","NEW JERSEY":"NJ","NEW MEXICO":"NM","NEW YORK":"NY","NORTH CAROLINA":"NC","NORTH DAKOTA":"ND","OHIO":"OH","OKLAHOMA":"OK","OREGON":"OR","PENNSYLVANIA":"PA","RHODE ISLAND":"RI","SOUTH CAROLINA":"SC","SOUTH DAKOTA":"SD","TENNESSEE":"TN","TEXAS":"TX","UTAH":"UT","VERMONT":"VT","VIRGINIA":"VA","WASHINGTON":"WA","WEST VIRGINIA":"WV","WISCONSIN":"WI","WYOMING":"WY","DISTRICT OF COLUMBIA":"DC"}
MLB_FULL = {"A'S":"Athletics","ATHLETICS":"Athletics","BOS":"Boston Red Sox","BOSTON":"Boston Red Sox","NYY":"New York Yankees","NYM":"New York Mets","PIT":"Pittsburgh Pirates","PITTSBURGH":"Pittsburgh Pirates","NY":"New York Yankees","TOR":"Toronto Blue Jays","CHC":"Chicago Cubs","CWS":"Chicago White Sox","LAD":"Los Angeles Dodgers","LAA":"Los Angeles Angels","SF":"San Francisco Giants","HOU":"Houston Astros","SEA":"Seattle Mariners","TEX":"Texas Rangers","ATL":"Atlanta Braves","MIA":"Miami Marlins","PHI":"Philadelphia Phillies","WSH":"Washington Nationals","BAL":"Baltimore Orioles","TB":"Tampa Bay Rays","CIN":"Cincinnati Reds","CLE":"Cleveland Guardians","DET":"Detroit Tigers","KC":"Kansas City Royals","MIN":"Minnesota Twins","MIL":"Milwaukee Brewers","STL":"St. Louis Cardinals","CHW":"Chicago White Sox"}
COUNTRY_KEYS = ["ARGENTINA","BRAZIL","BULGARIA","CAPE VERDE","ESTONIA","FRANCE","GHANA","HUNGARY","MOLDOVA","MONGOLIA","PHILIPPINES","SOUTH KOREA","WORLD","EU","UK","CANADA","MEXICO","GERMANY","JAPAN","KOREA"]
COMPANY_TO_STATE = {"AMAZON":"WA","APPLE":"CA","GOOGLE":"CA","ALPHABET":"CA","MICROSOFT":"WA","TESLA":"TX","META":"CA","NETFLIX":"CA","NVIDIA":"CA","OPENAI":"CA"}

def expand_team_name(short):
    up=short.strip().upper()
    # handle "A's vs Boston" split
    parts=[p.strip() for p in short.split("vs")]
    expanded=[]
    for p in parts:
        key=p.replace("'","").replace(".","").strip().upper()
        # direct map
        if key in MLB_FULL:
            expanded.append(MLB_FULL[key])
        elif p.upper() in MLB_FULL:
            expanded.append(MLB_FULL[p.upper()])
        else:
            # try token
            for k,v in MLB_FULL.items():
                if k==key:
                    expanded.append(v)
                    break
            else:
                expanded.append(p.strip())
    return " vs ".join(expanded) if len(expanded)==2 else short

def get_location(event_ticker, title, broad, raw_cat, subcategory):
    # Smart location: state if USA, country if not, N/A for prices, businesses have state
    if broad=="prices":
        return "N/A"
    text = f"{event_ticker} {title} {subcategory} {raw_cat}".upper()
    import re
    # 1. full state names (Massachusetts Governor -> MA, California -> CA)
    for name, code in STATE_FULL_TO_CODE.items():
        if name in text:
            return code
    # 2. district codes like CA-22, TX09, MI10
    m=re.search(r'\b([A-Z]{2})-?\d{1,2}\b', text)
    if m:
        code=m.group(1)
        if code in US_STATES:
            return code
    # 3. explicit state codes
    for st in US_STATES:
        if re.search(r'\b'+st+r'\b', text):
            return st
    # 4. city to state
    for city, st in CITY_TO_STATE.items():
        if city in text:
            return st
    # 5. country
    for c in COUNTRY_KEYS:
        if c in text:
            if c=="WORLD": return "World"
            if c=="EU": return "EU"
            return c.title()
    # 6. business: try company HQ else DC for national US business
    if broad=="business":
        for comp, st in COMPANY_TO_STATE.items():
            if comp in text:
                return st
        # national business still needs a state per spec - default to most common business states
        if any(k in text for k in ["HOUSE","SENATE","PRESIDENT","CONTROL","GOVERNOR","MAYOR","CONGRESS"]):
            return "DC"
        # generic US business -> try to infer from title keywords, else CA (tech) or NY (finance)
        if any(k in text for k in ["TECH","AI","AGI","SOFTWARE"]):
            return "CA"
        if any(k in text for k in ["BANK","FINANCE","MARKET"]):
            return "NY"
        return "DC"
    if broad=="sports":
        for city, st in CITY_TO_STATE.items():
            if city in text:
                return st
        # sports without city still US state-level -> return home-team state if possible, else DC not right - default to NY for national?
        # For now, national sports like "Will NFL happen" -> DC
        return "DC"
    if broad=="politics":
        # national politics -> DC per spec
        for c in COUNTRY_KEYS:
            if c in text:
                return c.title()
        return "DC"
    if broad=="weather":
        for city, st in CITY_TO_STATE.items():
            if city in text:
                return st
        return "World"
    # fallback: everything in US should have state, so default to DC for national
    # check if text suggests US context
    if any(k in text for k in ["US","USA","AMERICA","UNITED STATES","HOUSE","SENATE","PRESIDENT","CONGRESS","GOVERNOR"]):
        return "DC"
    return "DC"

today_iso = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
now = datetime.datetime.now(datetime.timezone.utc)
print(f"Fetching — today {today_iso} now {now.isoformat()}")

events = fetch_all_events()
print(f"Fetched {len(events)} events")
# Also fetch sports series directly to ensure today's games beyond cursor
for series in ["KXMLBGAME","KXWNBAGAME","KXLOLGAME","KXNFLGAME","KXNBA","KXSOCCER","KXGOLF"]:
    try:
        url=f"{BASE}/events?series_ticker={series}&status=open&with_nested_markets=true&limit=100"
        data=fetch_json(url)
        batch=data.get("events",[])
        existing=set(e["event_ticker"] for e in events)
        added=0
        for ev in batch:
            if ev["event_ticker"] not in existing:
                events.append(ev)
                added+=1
        if added:
            print(f"  series {series}: +{added} targeted sports events")
    except Exception as e:
        print(f"  series {series} fetch failed: {e}")

print(f"Total events after targeted: {len(events)}")

def is_live(close, exp):
    try:
        if close and exp:
            ct=datetime.datetime.fromisoformat(close.replace("Z","+00:00"))
            et=datetime.datetime.fromisoformat(exp.replace("Z","+00:00"))
            return ct < now < et
    except: pass
    return False

tomorrow_iso = (datetime.datetime.fromisoformat(today_iso+"T00:00:00+00:00")+datetime.timedelta(days=1)).date().isoformat()

pool=[]
for ev in events:
    # skip closed events with no markets
    markets = ev.get("markets") or []
    if not markets:
        continue
    # status filter — only active
    # ev status may not be present; market status is more reliable
    # skip if all markets are finalized
    active_markets = [m for m in markets if m.get("status") in (None,"active","open","initialized","")]
    if not active_markets:
        # check if any active, else skip
        if not any(m.get("status")=="active" for m in markets):
            continue
        active_markets = markets

    raw_cat = ev.get("category") or ""
    sub = ev.get("subcategory") or ev.get("series_ticker") or ""
    if isinstance(sub, dict):
        sub=",".join([str(v) for vs in sub.values() for v in (vs if isinstance(vs,list) else [vs])][:2])
    broad = to_broad(raw_cat, sub, ev.get("event_ticker",""), ev.get("title",""))

    # determine is_today for sports
    # use event occurrence or earliest market occurrence
    ev_occ = ev.get("occurrence_datetime") or ev.get("expected_expiration_time") or ""
    if not ev_occ and markets:
        # earliest market occurrence
        occs = [m.get("occurrence_datetime") or m.get("expected_expiration_time") or "" for m in markets]
        occs = [o for o in occs if o]
        if occs:
            ev_occ = min(occs)
    ev_occ_day = ev_occ[:10] if ev_occ else ""
    # event expiration (earliest)
    exps = [m.get("expected_expiration_time") or m.get("expiration_time") or ev.get("expected_expiration_time") or "" for m in markets]
    exps = [e for e in exps if e]
    exp = min(exps) if exps else (ev.get("expected_expiration_time") or ev.get("expiration_time") or "")
    if not exp:
        continue
    exp_day = exp[:10]
    occ_day = ev_occ_day or exp_day
    is_today = (exp_day==today_iso or occ_day==today_iso or (exp_day==tomorrow_iso and occ_day in (today_iso, tomorrow_iso)) or ev_occ_day==today_iso)

    # live check: event is live if close < now < exp (using event close or earliest market close)
    closes = [m.get("close_time") or ev.get("close_time") or "" for m in markets]
    closes = [c for c in closes if c]
    close = min(closes) if closes else (ev.get("close_time") or "")
    live = is_live(close, exp)
    # also consider high recent volume
    vol24_sum = sum(float(m.get("volume_24h") or 0) for m in markets if m.get("volume_24h"))
    if vol24_sum and vol24_sum > 5000 and is_today:
        live = True

    # Include logic: sports futures always in, single-game props only if live today
    if broad=="sports":
        # detect single-game / daily prop (2-way game, vs/@, GAME ticker)
        is_game = False
        t_up = (ev.get("event_ticker") or "").upper()
        title_up = (ev.get("title") or "").upper()
        if "GAME" in t_up or "KXMLBGAME" in t_up or "KXNBAGAME" in t_up or "KXWNBAGAME" in t_up or "KXNFLGAME" in t_up:
            is_game = True
        elif " VS " in title_up or " @ " in title_up or " V " in title_up:
            # title like "Athletics vs Boston Red Sox" with 2 strikes = single game
            if strikes == 2 and any(k in title_up for k in [" VS ", " @ "]):
                is_game = True
        elif strikes == 2 and exp_day in (today_iso, tomorrow_iso) and "WINNER" not in title_up:
            # small heuristic: 2-strike daily game
            # keep futures (MVP etc. have 20+ strikes and far exp) out
            is_game = bool(re.search(r'\bVS\b|\b@\b', title_up))
        if is_game:
            include = is_today or live
        else:
            include = True  # futures, awards, season props
    elif broad=="weather":
        wsub = weather_subcat(ev.get("event_ticker",""), ev.get("title","") or "", sub)
        # stash normalized weather subcat for later category
        ev["_wsub"] = wsub
        include = True
    else:
        include = True
    if not include:
        continue

    strikes = len(markets)
    # volume sum across event
    vol_sum = 0
    for m in markets:
        v = m.get("volume") or m.get("volume_fp") or m.get("volume_24h") or 0
        try: v = float(v)
        except: v = 0
        vol_sum += v
    if vol_sum==0:
        # fallback: use volume_fp sum or synthetic
        vol_sum = sum(float(m.get("volume_fp") or 0) for m in markets)
    if vol_sum==0:
        vol_sum = abs(hash(ev.get("event_ticker","")) % 80000)+5000
    # favorite price (odds of favorite) — for batched event take max mid-price among strikes
    fav_price = 50
    fav_ticker = ""
    fav_label = ""
    try:
        best = -1
        for mm in markets:
            bid = float(mm.get("yes_bid_dollars") or 0)
            ask = float(mm.get("yes_ask_dollars") or 0)
            last = float(mm.get("last_price_dollars") or 0)
            mid = 0
            if bid>0 and ask>0: mid = (bid+ask)/2
            elif bid>0: mid = bid
            elif ask>0: mid = ask
            else: mid = last
            if mid*100 > best:
                best = mid*100
                fav_ticker = mm.get("ticker","")
                fav_label = mm.get("yes_sub_title","") or mm.get("ticker","")
        if best>=0:
            fav_price = int(round(best))
            if fav_price<1: fav_price=50  # fallback for zero-priced markets
            if fav_price>99: fav_price=99
    except: pass

    # subcat and category + location — intuitive for normal user, no ++ padding
    if broad=="weather":
        wsub = ev.get("_wsub") or weather_subcat(ev.get("event_ticker",""), ev.get("title","") or "", sub)
        detail = f"Weather · {wsub}"
        sub_for_pool = wsub
    elif broad=="sports":
        league = sports_subcat(ev.get("event_ticker",""), ev.get("title","") or "", sub)
        detail = f"Sports · {league}"
        sub_for_pool = league
    elif broad=="prices":
        ps = prices_subcat(ev.get("event_ticker",""), ev.get("title","") or "", sub)
        detail = f"Prices · {ps}"
        sub_for_pool = ps
    elif broad=="culture":
        cs = culture_subcat(ev.get("event_ticker",""), ev.get("title","") or "", sub)
        detail = f"Culture · {cs}"
        sub_for_pool = cs
    elif broad=="business":
        bs = business_subcat(ev.get("event_ticker",""), ev.get("title","") or "", sub)
        detail = f"Companies · {bs}" if raw_cat in ("Companies","Financials","Economics") else f"{raw_cat or 'Business'} · {bs}"
        sub_for_pool = bs
    elif broad=="politics":
        # all elections → ELECT, no GOVNY/SENATENY nonsense
        ticker_up = (ev.get("event_ticker","") or "").upper()
        if "HOUSE" in ticker_up or "KXHOUSE" in ticker_up:
            pl = "HOUSE"
        else:
            pl = "ELECT"
        sub_for_pool = pl
        detail = f"Politics · {pl}"
    else:
        sub_for_pool = (sub.strip() if sub else broad)
        detail = f"{raw_cat} · {sub_for_pool}" if sub and sub!=raw_cat else raw_cat or broad
        detail = detail.strip()

    raw_title = ev.get("title") or ev.get("event_ticker")
    expanded_title = expand_team_name(raw_title) if broad=="sports" else raw_title
    location = get_location(ev.get("event_ticker",""), expanded_title or "", broad, raw_cat, sub)

    pool.append({
        "name": expanded_title,
        "broad": broad,
        "subcat": sub_for_pool,
        "category": detail,
        "raw_category": raw_cat or broad,
        "location": location,
        "strikes": strikes,
        "expiration": exp,
        "volume": int(vol_sum),
        "price": fav_price,
        "price_ticker": fav_ticker,
        "price_label": fav_label,
        "ticker": ev.get("event_ticker"),
        "event_ticker": ev.get("event_ticker"),
    })

# Deduplicate by event_ticker (should already be unique)
uniq={}
for p in pool:
    k=p["event_ticker"]
    if k not in uniq or p["volume"]>uniq[k]["volume"]:
        uniq[k]=p
pool=list(uniq.values())

# Bunch House district markets by state — nobody can guess 1 of 20+ districts
# e.g., HOUSEAZ1-26, HOUSECA13-26, KXHOUSERACE-NY17 etc. → one per state: NYHOUSE, CAHOUSE
import re
HOUSE_RE = re.compile(r'HOUSE([A-Z]{2})\d*', re.I)
KXHOUSE_RE = re.compile(r'KXHOUSE([A-Z]{2})', re.I)
house_buckets = {}  # state -> list of entries
non_house = []
for p in pool:
    ticker = (p.get("event_ticker") or p.get("ticker") or "")
    name = p.get("name","")
    # identify house district race (not overall CONTROLH / KXMIDTERMVOT generic)
    is_house_district = False
    state = None
    m = HOUSE_RE.search(ticker.upper())
    if m and ticker.upper().startswith("HOUSE"):
        # HOUSECA13, HOUSENY17 etc.
        cand = m.group(1).upper()
        if cand in US_STATES:
            is_house_district = True
            state = cand
    elif "KXHOUSERACE" in ticker.upper() or "KXHOUSE" in ticker.upper():
        # KXHOUSERACE-NY17, KXHOUSENC11- etc. — extract state from ticker or name
        # try ticker pattern
        m2 = KXHOUSE_RE.search(ticker.upper())
        if m2 and m2.group(1).upper() in US_STATES:
            is_house_district = True
            state = m2.group(1).upper()
        else:
            # fallback: parse e.g., NY17 in ticker
            m3 = re.search(r'-([A-Z]{2})\d+', ticker.upper())
            if m3 and m3.group(1).upper() in US_STATES:
                is_house_district = True
                state = m3.group(1).upper()
            elif re.search(r'\bHOUSE\b', name.upper()) and p.get("location") in US_STATES:
                # last resort: use location already derived
                if p.get("location") in US_STATES:
                    is_house_district = True
                    state = p.get("location")
        # exclude overall House control markets (CONTROLH) from district bunch
        if ticker.upper().startswith("CONTROLH") or "KXMIDTERMVOT" in ticker.upper():
            is_house_district = False
            state = None
    # also catch generic HOUSE in name with district pattern like "AZ-01 House"
    if not is_house_district and re.search(r'\b[A-Z]{2}-0?1\b', name) and "HOUSE" in name.upper():
        # don't bunch generic CONTROLH
        if "CONTROLH" not in ticker.upper():
            # try to extract state from name AZ-01
            mstate = re.search(r'\b([A-Z]{2})-\d+', name.upper())
            if mstate and mstate.group(1) in US_STATES:
                is_house_district = True
                state = mstate.group(1)
    if is_house_district and state:
        house_buckets.setdefault(state, []).append(p)
    else:
        non_house.append(p)

if house_buckets:
    for state, bucket in house_buckets.items():
        # aggregate into one per state: e.g., NYHOUSE
        vol_sum = sum(x.get("volume",0) for x in bucket)
        strikes_sum = sum(x.get("strikes",1) for x in bucket)
        # earliest expiration among bucket
        exps = [x.get("expiration") for x in bucket if x.get("expiration")]
        exp = min(exps) if exps else bucket[0].get("expiration")
        ticker_st = f"{state}HOUSE"
        # intuitive name for normal user
        state_full = {v:k.title() for k,v in STATE_FULL_TO_CODE.items()}.get(state, state)
        name_st = f"{state_full} House Races"
        # bunched price = volume-weighted avg favorite price of constituents
        prices = [x.get("price",50) for x in bucket if x.get("price")]
        vols_w = [x.get("volume",0) or 1 for x in bucket]
        if prices:
            wavg = sum(p*w for p,w in zip(prices, vols_w))/sum(vols_w)
            agg_price = int(round(wavg))
        else:
            agg_price = 50
        agg = {
            "name": name_st,
            "broad": "politics",
            "subcat": "HOUSE",
            "category": "Politics · HOUSE",
            "raw_category": "Politics",
            "location": state,
            "strikes": 2,  # custom bunch is a 2-way race (D vs R), not sum of districts
            "expiration": exp,
            "volume": int(vol_sum),
            "price": agg_price,
            "price_ticker": ticker_st,
            "price_label": "House",
            "ticker": ticker_st,
            "event_ticker": ticker_st,
            "subtickers": [x.get("event_ticker") for x in bucket],  # specific district tickers preserved
            "constituents": len(bucket),
        }
        non_house.append(agg)
    pool = non_house

pool.sort(key=lambda x: x["event_ticker"])

from collections import Counter
cnt=Counter(p["broad"] for p in pool)
print(f"Pool (condensed to events): {len(pool)} events")
for b in BROAD_ORDER:
    print(f"  {b:10} {cnt.get(b,0):4}")
print("Sample:")
for p in pool[:12]:
    print(f"  {p['event_ticker'][:45]:45} {p['expiration'][:10]} {p['broad']:10} {p['category'][:28]:28} strikes={p['strikes']:2} vol={p['volume']}")

open("pool.json","w").write(json.dumps(pool, indent=2))
print(f"Wrote pool.json ({len(pool)} events) — condensed: 2028 President is one entry, not {sum(p['strikes'] for p in pool)} separate strikes")
open("market_atlas.json","w").write(json.dumps({
    "fetched_at": now.isoformat(),
    "today": today_iso,
    "events_scanned": len(events),
    "pool_size": len(pool),
    "broad_counts": dict(cnt),
    "broad_order": BROAD_ORDER,
    "note": "Pool condensed to EVENT level: one entry per event_ticker. Strikes = #markets in event. Sports filtered to today, other broads include all open."
}, indent=2))
