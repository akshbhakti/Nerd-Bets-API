"""The Odds API v4 client. Never log request URLs: they contain apiKey."""
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

BASE = 'https://api.the-odds-api.com/v4'
SPORTS = {'NFL': 'americanfootball_nfl', 'NBA': 'basketball_nba'}

def now_utc():
    return datetime.now(timezone.utc).isoformat()

class ProviderFailure(RuntimeError):
    def __init__(self, kind, detail):
        self.kind = kind
        super().__init__(detail)

class OddsClient:
    def __init__(self, key, transport=None):
        if not key:
            raise ProviderFailure('MISSING_KEY', 'ODDS_API_KEY is not configured')
        self.key = key
        self.http = httpx.Client(timeout=20.0, transport=transport, follow_redirects=False)

    def get(self, path, params=None):
        params = dict(params or {})
        params['apiKey'] = self.key
        for attempt in range(3):
            try:
                response = self.http.get(BASE + path, params=params)
                code = response.status_code
                if code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(0.4 * (2 ** attempt)); continue
                if code == 401: raise ProviderFailure('AUTHENTICATION', 'API rejected credentials (401)')
                if code == 403: raise ProviderFailure('ACCESS_OR_PLAN', 'API rejected market/subscription access (403)')
                if code == 429: raise ProviderFailure('RATE_LIMIT', 'API returned 429')
                if code >= 400: raise ProviderFailure('HTTP_ERROR', f'Provider returned HTTP {code}')
                return response.json(), {
                    'remaining': response.headers.get('x-requests-remaining'),
                    'used': response.headers.get('x-requests-used'),
                    'last': response.headers.get('x-requests-last')}
            except httpx.ConnectError as exc:
                raise ProviderFailure('NETWORK_OR_DNS', type(exc).__name__) from None
            except httpx.TimeoutException:
                if attempt == 2: raise ProviderFailure('TIMEOUT', 'Provider timed out') from None
        raise ProviderFailure('UNKNOWN', 'Request failed after retries')

def initialize(folder):
    p = Path(folder); p.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p / 'snapshots.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS captures
    (id INTEGER PRIMARY KEY, captured_at TEXT, sport TEXT, status TEXT,
    event_count INTEGER, quote_count INTEGER, request_count INTEGER,
    error_kind TEXT, sha256 TEXT, file_path TEXT, quota_json TEXT)''')
    conn.commit(); return conn

def capture(sport='NFL', folder='./data', transport=None):
    """Capture raw pregame FanDuel responses; no projection or ticket certification."""
    sport = sport.upper()
    if sport not in SPORTS: raise ValueError('Sport must be NFL or NBA')
    conn = initialize(folder)
    started = now_utc(); responses = []; quotas = []; failures=[]; calls=0
    try:
        client = OddsClient(os.getenv('ODDS_API_KEY'), transport=transport)
        sport_key = SPORTS[sport]
        events, q = client.get(f'/sports/{sport_key}/events')
        calls += 1; quotas.append(q)
        # Never retroactively label an in-play or completed game as a pregame capture.
        cutoff = datetime.now(timezone.utc)
        events = [e for e in events if datetime.fromisoformat(e['commence_time'].replace('Z','+00:00')) > cutoff]
        for e in events:
            event_id = e['id']
            try:
                market_data, q = client.get(f'/sports/{sport_key}/events/{event_id}/markets', {'bookmakers':'fanduel'})
                calls += 1; quotas.append(q)
                # The endpoint returns recently observed markets; never call this complete provider coverage.
                market_keys = sorted({m['key'] if isinstance(m,dict) else m for b in market_data.get('bookmakers',[]) if b.get('key')=='fanduel' for m in b.get('markets',[])})
                fetched = []
                for offset in range(0,len(market_keys),10):
                    batch = market_keys[offset:offset+10]
                    data, q = client.get(f'/sports/{sport_key}/events/{event_id}/odds',
                         {'bookmakers':'fanduel','markets':','.join(batch),'oddsFormat':'american'})
                    calls += 1; quotas.append(q)
                    fetched.append({'requested_markets':batch,'data':data})
                responses.append({'event':e,'observed_market_keys':market_keys,'odds_batches':fetched})
            except ProviderFailure as exc:
                failures.append({'event_id':event_id,'kind':exc.kind,'message':str(exc)})
        quote_count = sum(len(m.get('outcomes',[])) for r in responses for batch in r['odds_batches']
             for b in batch['data'].get('bookmakers',[]) if b.get('key')=='fanduel' for m in b.get('markets',[]))
        status='PARTIAL' if failures or not events or any(not r['observed_market_keys'] for r in responses) else 'CAPTURED_UNCERTIFIED'
        result={'capture_started_at':started,'captured_at':now_utc(),'sport':sport,'status':status,
            'provider':'The Odds API v4','bookmaker':'fanduel', 'event_count':len(events),
            'quote_count':quote_count,'requests':calls,'quota_headers':quotas,
            'failures':failures,'coverage_warning':'Observed event markets are not proof of exhaustive market coverage.',
            'responses':responses}
    except ProviderFailure as exc:
        result={'capture_started_at':started,'captured_at':now_utc(),'sport':sport,'status':'BLOCKED',
            'provider':'The Odds API v4','bookmaker':'fanduel', 'event_count':0,
            'quote_count':0,'requests':calls,'quota_headers':quotas,'failures':[{'kind':exc.kind,'message':str(exc)}], 'responses':[]}
    raw=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
    digest=hashlib.sha256(raw).hexdigest()
    timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=Path(folder)/f'{sport.lower()}_{timestamp}_{digest[:12]}.json'
    out.write_bytes(raw)
    conn.execute('INSERT INTO captures (captured_at,sport,status,event_count,quote_count,request_count,error_kind,sha256,file_path,quota_json) VALUES (?,?,?,?,?,?,?,?,?,?)',
       (result['captured_at'],sport,result['status'],result['event_count'],result['quote_count'],calls,
        result['failures'][0]['kind'] if result['failures'] else None,digest,str(out),json.dumps(quotas)))
    conn.commit(); conn.close()
    return {k:result[k] for k in ('captured_at','sport','status','event_count','quote_count','requests','failures') } | {'sha256':digest,'file_path':str(out)}
