"""
News fetcher — multi-source with graceful fallbacks.
Sources (in priority order):
  1. yfinance get_news(count=10)  — works with yfinance >= 1.x
  2. Yahoo Finance RSS feed       — works with any yfinance, no auth
  3. Moneycontrol RSS             — for Indian stocks
  4. Reuters / ET RSS             — for global/Indian news
"""
import time, xml.etree.ElementTree as ET
from datetime import datetime
try:
    import urllib.request as _ur
except ImportError:
    import urllib.request as _ur

# ── Category & sentiment ─────────────────────────────────────────────────────
_CATS = [
    (['result','profit','revenue','earnings','quarterly','q1','q2','q3','q4','fy','net income'],
     'Earnings', '📊'),
    (['dividend','bonus','buyback','split','rights issue','special dividend'],
     'Corporate', '💰'),
    (['merger','acquisition','takeover','deal','stake','buy out'],
     'M&A', '🤝'),
    (['rbi','fed','sebi','rate','repo','inflation','gdp','policy','monetary','interest rate','rate hike','rate cut'],
     'Policy', '🏦'),
    (['war','crisis','sanction','geopolit','conflict','tension','ukraine','russia','china','israel','iran','ceasefire'],
     'Geopolitical', '⚠️'),
    (['crash','circuit','halt','suspension','fraud','scam','default','bankruptcy','insolvency'],
     'Risk', '🚨'),
    (['ipo','listing','nfo','fundraise','public offer','primary market'],
     'IPO', '🚀'),
    (['upgrade','downgrade','target','outperform','buy rating','sell rating','overweight','underweight','initiate'],
     'Analyst', '🎯'),
    (['nasdaq','dow jones','s&p','ftse','nikkei','hang seng','world market','global market','asian market'],
     'Global Mkt', '🌍'),
    (['oil','gold','crude','commodity','silver','currency','forex','dollar','rupee','yen','euro','bitcoin','crypto'],
     'Commodity', '🛢️'),
]
_POS = ['rise','rises','rose','rally','gain','surge','upgrade','strong','beat','record',
        'high','growth','bullish','above','outperform','soar','jump','climb','robust','boost',
        'expand','optimism','profit','positive','recovery','rebound','all-time high']
_NEG = ['fall','falls','fell','drop','loss','crash','decline','downgrade','weak','miss',
        'below','cut','risk','crisis','war','bearish','sell','down','plunge','slump',
        'concern','halt','suspend','default','fraud','disappoints','lower','pressure','fear']

def _cat(title):
    t = title.lower()
    for kws, cat, icon in _CATS:
        if any(k in t for k in kws):
            return cat, icon
    return 'Market', '📰'

def _sent(title):
    t = title.lower()
    p = sum(1 for w in _POS if w in t)
    n = sum(1 for w in _NEG if w in t)
    if p > n:   return 'positive', min(92, 55 + p * 10)
    if n > p:   return 'negative', max(8,  45 - n * 10)
    return 'neutral', 50

def _age(ts):
    s = time.time() - float(ts)
    if s < 60:    return 'just now'
    if s < 3600:  return f"{int(s/60)}m ago"
    if s < 86400: return f"{int(s/3600)}h ago"
    return f"{int(s/86400)}d ago"

def _make(title, source, url, ts, sym):
    cat, icon = _cat(title)
    sent, score = _sent(title)
    return {'title': title, 'source': source, 'url': url,
            'age': _age(ts), 'ts': float(ts),
            'category': cat, 'icon': icon,
            'sentiment': sent, 'score': score, 'symbol': sym}

# ── Source 1: yfinance get_news ───────────────────────────────────────────────
def _yf_news(sym, count=8):
    try:
        import yfinance as yf
        t    = yf.Ticker(sym)
        # yfinance 1.x uses get_news(count=N)
        try:
            raw = t.get_news(count=count)
        except TypeError:
            raw = t.get_news()  # yfinance 0.2.x fallback
        if not raw:
            return []
        out = []
        for item in raw[:count]:
            # Handle both yf 0.2.x and 1.x news item formats
            title = (item.get('title') or item.get('content',{}).get('title',''))
            if not title:
                continue
            source = (item.get('publisher') or
                      item.get('content',{}).get('provider',{}).get('displayName','Yahoo Finance'))
            url    = (item.get('link') or
                      item.get('content',{}).get('canonicalUrl',{}).get('url','#'))
            ts     = (item.get('providerPublishTime') or
                      item.get('content',{}).get('pubDate') or time.time())
            # pubDate may be string like "2025-02-20T10:30:00Z"
            if isinstance(ts, str):
                try:
                    from datetime import datetime
                    ts = datetime.fromisoformat(ts.replace('Z','+00:00')).timestamp()
                except:
                    ts = time.time()
            out.append(_make(title, source, url, ts, sym))
        return out
    except Exception as e:
        print(f"[NEWS] yf.get_news {sym}: {e}")
        return []

# ── Source 2: Yahoo Finance RSS (no auth) ─────────────────────────────────────
def _rss_yahoo(sym, count=5):
    # Encode special chars: ^ → %5E, . → keep as is
    sym_enc = sym.replace('^','%5E').replace('&','%26')
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym_enc}&region=US&lang=en-US"
    return _parse_rss(url, sym, count, 'Yahoo Finance RSS')

# ── Source 3: Moneycontrol RSS ────────────────────────────────────────────────
def _rss_mc(count=5):
    return _parse_rss('https://www.moneycontrol.com/rss/latestnews.xml', 'MC_GENERAL', count, 'Moneycontrol')

# ── Source 4: Economic Times ──────────────────────────────────────────────────
def _rss_et(count=5):
    return _parse_rss('https://economictimes.indiatimes.com/markets/rss.cms', 'MARKET_GENERAL', count, 'Economic Times')

# ── Source 5: Reuters ─────────────────────────────────────────────────────────
def _rss_reuters(count=5):
    return _parse_rss('https://feeds.reuters.com/reuters/businessNews', 'GLOBAL_GENERAL', count, 'Reuters')

def _parse_rss(url, sym, count, source_name):
    try:
        req = _ur.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0',
            'Accept': 'application/rss+xml, application/xml, text/xml'
        })
        with _ur.urlopen(req, timeout=6) as resp:
            xml_data = resp.read().decode('utf-8', errors='ignore')
        root = ET.fromstring(xml_data)
        ns   = {'media':'http://search.yahoo.com/mrss/'}
        items = root.findall('.//item')
        out   = []
        for item in items[:count]:
            title = (item.findtext('title') or '').strip()
            if not title: continue
            link  = (item.findtext('link') or '#').strip()
            pub   = item.findtext('pubDate') or ''
            try:
                from email.utils import parsedate_to_datetime
                ts = parsedate_to_datetime(pub).timestamp()
            except:
                ts = time.time() - 3600
            src = item.findtext('source') or source_name
            out.append(_make(title, src, link, ts, sym))
        return out
    except Exception as e:
        print(f"[NEWS] RSS {url[:40]}: {e}")
        return []

# ── Main public function ──────────────────────────────────────────────────────
def fetch_news(symbols: list, max_per_symbol: int = 5) -> list:
    all_news = []
    seen     = set()

    def _add(items):
        for item in items:
            key = item['title'][:55].lower().strip()
            if key and key not in seen:
                seen.add(key)
                all_news.append(item)

    # Fetch per-symbol news
    for sym in symbols[:8]:
        items = _yf_news(sym, count=max_per_symbol)
        if not items:
            items = _rss_yahoo(sym, count=max_per_symbol)
        _add(items)

    # If still under 10, pull general market news from RSS feeds
    if len(all_news) < 10:
        for feed_fn in [_rss_mc, _rss_et, _rss_reuters]:
            if len(all_news) >= 15:
                break
            _add(feed_fn(count=5))

    # Sort newest first
    all_news.sort(key=lambda x: x['ts'], reverse=True)
    return all_news[:25]