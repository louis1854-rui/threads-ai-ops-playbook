# morning-research v2
import os, json, re, time
from datetime import datetime, timezone, timedelta
try:
    import gspread; from google.oauth2.service_account import Credentials; GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
try:
    import requests; REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
try:
    import anthropic; ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
SHEET_ID = os.environ.get("GOOGLE_SHEETS_ID", "1nViEkwMMvFuZEL6OD38X4cAUQq-erYk8Kl1GEwF0FwQ")
CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BUZZ_THRESHOLD = 10; JST = timezone(timedelta(hours=9))
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
OWN_ACCOUNTS = [{"name": "haru", "genre": "ikuji", "target": "0-3sai mama", "style": "onesan Hook: ano~"},
    {"name": "lemon", "genre": "ikuji otoku", "target": "0-2sai mama", "style": "otoku genki"},
    {"name": "fumin", "genre": "ikuji okane", "target": "30sai okasan", "style": "osaka-ben"}]
def gc(): return gspread.authorize(Credentials.from_service_account_info(json.loads(CREDENTIALS_JSON), scopes=SCOPES)) if GSPREAD_AVAILABLE and CREDENTIALS_JSON else None
def get_competitor_accounts():
    c = gc()
    if not c: return []
    rows = c.open_by_key(SHEET_ID).worksheet("①競合アカウントリスト").get_all_values()
    if not rows: return []
    h = rows[0]
    recs = [{h[i]: r[i] for i in range(min(len(h),len(r))) if h[i]} for r in rows[1:] if any(r)]
    high = [r for r in recs if r.get("優先度")=="高" and r.get("URL")]
    return high or [r for r in recs if r.get("URL")]
def bl(d, u, h, m=""): c=gc(); c and c.open_by_key(SHEET_ID).worksheet("②バズ投稿ログ").append_row([d,u,h,m])
def pd(name, d, theme, drafts):
    c=gc()
    if not c: return
    s=c.open_by_key(SHEET_ID).worksheet("②バズ投稿ログ")
    [s.append_row([d,f"[draft{i}]{name}",theme,dr]) for i,dr in enumerate(drafts,1)]
    print(f"[draft] {name}: {len(drafts)}")
def ml(d, u, h, m=""): c=gc(); c and c.open_by_key(SHEET_ID).worksheet("③自分の投稿ログ").append_row([d,u,h,m])
def fetch_threads_posts(profile_url):
    if not REQUESTS_AVAILABLE: return []
    m = re.search(r'threads\.(?:com|net)/@([\w._-]+)', profile_url)
    if not m: return []
    un, h = m.group(1), {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "X-IG-App-ID": "238260118697367"}
    try:
        r = requests.get(f"https://www.threads.net/api/v1/users/username_info/?username={un}", headers=h, timeout=10)
        if r.status_code != 200: return []
        uid = r.json().get("user",{}).get("pk") or r.json().get("user",{}).get("id")
        if not uid: return []
        time.sleep(1)
        r2 = requests.get(f"https://www.threads.net/api/v1/feeds/user_threads_feed/?userid={uid}&count=20", headers=h, timeout=10)
        if r2.status_code != 200: return []
        cutoff, posts = datetime.now(timezone.utc)-timedelta(hours=24), []
        for t in r2.json().get("threads",[]):
            for item in t.get("thread_items",[]):
                p = item.get("post",{})
                pt = datetime.fromtimestamp(p.get("taken_at",0), tz=timezone.utc)
                if pt < cutoff: continue
                cap = p.get("caption") or {}
                txt = cap.get("text","") if isinstance(cap,dict) else ""
                pid = p.get("pk","")
                posts.append({"username":un,"text":txt,"likes":p.get("like_count",0),"url":f"https://www.threads.com/@{un}/post/{pid}" if pid else ""})
        print(f"  {un}: {len(posts)} posts"); return posts
    except Exception as e: print(f"  {un}: error: {e}"); return []
def filter_buzz(posts, thr=BUZZ_THRESHOLD): return [p for p in posts if p.get("likes",0)>=thr]
def generate_drafts(summary, acct):
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY: return []
    ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today = datetime.now(JST).strftime("%Y/%m/%d")
    p = (f"Competitor buzz ({today}):\n{summary}\n\n"
         f"Acct:{acct['name']} Genre:{acct['genre']} Target:{acct['target']} Style:{acct['style']}\n\n"
         "Create 3 original Japanese post drafts for Threads parenting content.\n"
         "Do NOT copy competitor FORMAT. Use buzz GENRE only as reference.\n"
         "post1=hook(1 line) + post2-4=body. Mark: ---draft1--- ---draft2--- ---draft3---")
    try:
        msg = ai.messages.create(model="claude-opus-4-5", max_tokens=2000, messages=[{"role":"user","content":p}])
        return [d.strip() for d in re.split(r'---draft\d+---', msg.content[0].text) if d.strip()][:3]
    except Exception as e: print(f"  AI:{e}"); return []
def main():
    print("=== morning-research v2 ===")
    today = datetime.now(JST).strftime("%Y-%m-%d")
    accts = get_competitor_accounts()
    if not accts: return
    buzz, lines = [], []
    for acc in accts:
        url, name = acc.get("URL",""), acc.get("アカウント名", acc.get("URL",""))
        for p in filter_buzz(fetch_threads_posts(url)):
            bl(today, p["url"], p["text"][:100], f"likes:{p['likes']}|{name}")
            buzz.append(p); lines.append(f"- {name}: likes={p['likes']} '{p['text'][:80]}'")
        time.sleep(2)
    summary = "\n".join(lines) if lines else "No buzz today."
    print(f"buzz:{len(buzz)}")
    for acct in OWN_ACCOUNTS:
        drafts = generate_drafts(summary, acct)
        if drafts: pd(acct["name"], today, "buzz-draft", drafts)
    print("=== done ===")
if __name__ == "__main__": main()
