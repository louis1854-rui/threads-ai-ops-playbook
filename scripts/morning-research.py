# morning-research v4
# 運用方針: GitHub Actions (cron JST 5:00) で自動起動
# 処理内容:
#   1. 競合アカウントのThreadsページをHTTPで取得（スクリーンショット不使用）
#   2. いいね数・表示数でバズ投稿を抽出（24時間以内）
#   3. バズ原因をAIで分析
#   4. 自分のアカウント向け投稿案を3つ生成
#   5. Googleスプレッドシートに保存

import os, json, re, time
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ---- 設定 --------------------------------------------------------
SHEET_ID          = os.environ.get("GOOGLE_SHEETS_ID", "1nViEkwMMvFuZEL6OD38X4cAUQq-erYk8Kl1GEwF0FwQ")
CREDENTIALS_JSON  = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
JST  = timezone(timedelta(hours=9))
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# 分析対象の競合アカウント（ThreadsのユーザーID）
COMPETITOR_ACCOUNTS = os.environ.get(
    "COMPETITOR_ACCOUNTS",
    ""  # 例: "user1,user2,user3"  -> GitHub Secretsで設定
).split(",")
COMPETITOR_ACCOUNTS = [a.strip() for a in COMPETITOR_ACCOUNTS if a.strip()]

# 自分のアカウント情報（投稿案生成に使用）
OWN_ACCOUNTS = [
    {"name": "haru",  "genre": "ikuji",       "target": "0-3sai mama",  "style": "onesan Hook: ano~"},
    {"name": "lemon", "genre": "ikuji otoku",  "target": "0-2sai mama",  "style": "otoku genki"},
    {"name": "fumin", "genre": "ikuji okane",  "target": "30sai okasan", "style": "osaka-ben"},
]

# バズ判定のしきい値
BUZZ_LIKES_THRESHOLD = int(os.environ.get("BUZZ_LIKES_THRESHOLD", "50"))
TOP_N_POSTS          = int(os.environ.get("TOP_N_POSTS", "5"))


# ---- Googleスプレッドシート接続 -----------------------------------
def get_gspread_client():
    if not GSPREAD_AVAILABLE or not CREDENTIALS_JSON:
        return None
    creds = Credentials.from_service_account_info(json.loads(CREDENTIALS_JSON), scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_sheet(spreadsheet, title):
    for ws in spreadsheet.worksheets():
        if ws.title == title:
            return ws
    ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=10)
    ws.append_row(["日付", "アカウント", "競合元", "投稿テキスト", "いいね数", "表示数", "バズ原因分析", "投稿案1", "投稿案2", "投稿案3"])
    return ws


# ---- Threadsページ取得（HTTPのみ・スクリーンショット不使用）--------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}


def fetch_threads_posts(username):
    """
    Threadsの公開プロフィールページをHTTPで取得し、
    投稿テキスト・いいね数・表示数・投稿時刻を返す。
    Returns: list of {text, likes, views, timestamp}
    """
    url = "https://www.threads.net/@" + username
    posts = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup.find_all("script", type="application/json"):
            try:
                data = json.loads(tag.string or "")
                extracted = _parse_json_ld(data)
                posts.extend(extracted)
            except Exception:
                pass

        if not posts:
            posts = _parse_html_fallback(soup)

    except requests.RequestException as e:
        print("[fetch error] " + username + ": " + str(e))
    return posts


def _parse_json_ld(data):
    posts = []
    if isinstance(data, dict):
        for key in ("edges", "nodes", "items", "data"):
            val = data.get(key)
            if isinstance(val, list):
                for item in val:
                    p = _extract_post_fields(item)
                    if p:
                        posts.append(p)
            elif isinstance(val, dict):
                posts.extend(_parse_json_ld(val))
        p = _extract_post_fields(data)
        if p:
            posts.append(p)
    elif isinstance(data, list):
        for item in data:
            posts.extend(_parse_json_ld(item))
    return posts


def _extract_post_fields(item):
    if not isinstance(item, dict):
        return None
    text = (
        item.get("caption") or item.get("text") or
        item.get("body") or item.get("content") or ""
    )
    if not text:
        return None
    likes = _to_int(
        item.get("like_count") or item.get("likes") or
        item.get("likeCount") or 0
    )
    views = _to_int(
        item.get("view_count") or item.get("views") or
        item.get("viewCount") or item.get("impressions") or 0
    )
    ts_raw = (
        item.get("taken_at") or item.get("timestamp") or
        item.get("created_at") or item.get("publishedAt") or 0
    )
    try:
        ts = datetime.fromtimestamp(float(ts_raw), tz=timezone.utc) if ts_raw else None
    except Exception:
        ts = None
    return {"text": str(text).strip(), "likes": likes, "views": views, "timestamp": ts}


def _parse_html_fallback(soup):
    posts = []
    selectors = [
        "div[data-pressable-container]",
        "article",
        "[role='article']",
        "div[class*='post']",
    ]
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            for card in cards[:20]:
                text = card.get_text(separator=" ", strip=True)
                if len(text) < 10:
                    continue
                likes = _extract_number_near_icon(card, ["いいね", "likes", "heart", "like"])
                views = _extract_number_near_icon(card, ["表示", "views", "view"])
                posts.append({"text": text[:300], "likes": likes, "views": views, "timestamp": None})
            break
    return posts


def _extract_number_near_icon(card, keywords):
    text = card.get_text(" ", strip=True).lower()
    for kw in keywords:
        idx = text.find(kw.lower())
        if idx != -1:
            snippet = text[max(0, idx - 20):idx + 30]
            nums = re.findall(r"[0-9,\.]+[kKmM万]?", snippet)
            for n in nums:
                val = _to_int(n)
                if val > 0:
                    return val
    return 0


def _to_int(val):
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().replace(",", "")
    m = re.match(r"([0-9\.]+)([kKmM万]?)", s)
    if not m:
        return 0
    num = float(m.group(1))
    suffix = m.group(2).lower()
    if suffix == "k":
        num *= 1000
    elif suffix == "m":
        num *= 1000000
    elif suffix == "万":
        num *= 10000
    return int(num)


# ---- バズ投稿フィルタリング ---------------------------------------
def filter_buzz_posts(posts, hours=24):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    filtered = []
    for p in posts:
        ts = p.get("timestamp")
        if ts is not None and ts < cutoff:
            continue
        if p["likes"] >= BUZZ_LIKES_THRESHOLD or p["views"] > 0:
            filtered.append(p)

    scored = sorted(
        filtered,
        key=lambda x: x["likes"] * 2 + x["views"] / 1000,
        reverse=True
    )
    return scored[:TOP_N_POSTS]


# ---- AI分析・投稿案生成 -------------------------------------------
def analyze_and_generate(buzz_posts, acct):
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        return ("AI未設定", [])

    today = datetime.now(JST).strftime("%Y/%m/%d")
    posts_text = ""
    for i, p in enumerate(buzz_posts, 1):
        posts_text += (
            "[投稿" + str(i) + "] いいね:" + str(p["likes"]) + " 表示:" + str(p["views"]) + "\n"
            + p["text"] + "\n\n"
        )

    prompt = (
        "以下は競合Threadsアカウントのバズ投稿（" + today + "）です。\n"
        "いいね数と表示数が多かった上位投稿を掲載しています。\n\n"
        + posts_text
        + "\nあなたのタスクは2つです。\n\n"
        "【タスク1: バズ原因分析】\n"
        "上記の投稿がバズった理由を3〜5点で分析してください。\n"
        "フックの書き方・テーマ選定・感情訴求・構成パターンの観点で簡潔にまとめてください。\n"
        "出力形式:\n---analysis---\n（分析テキスト）\n---analysis_end---\n\n"
        "【タスク2: 投稿案生成】\n"
        "上記のバズ原因を活かし、下記アカウント向けのオリジナル日本語投稿案を3つ作成してください。\n"
        "競合の文章をそのままコピーしないこと。\n\n"
        "アカウント情報:\n"
        "- 名前: " + acct["name"] + "\n"
        "- ジャンル: " + acct["genre"] + "\n"
        "- ターゲット: " + acct["target"] + "\n"
        "- 文体・スタイル: " + acct["style"] + "\n\n"
        "投稿案の形式:\n"
        "- 1行目: 読者が止まるフック\n"
        "- 2〜4行目: 本文（具体的・共感できる内容）\n"
        "- 最終行: 保存・返信・フォローを促す一言\n\n"
        "出力形式:\n---draft1---\n（投稿案1）\n---draft2---\n（投稿案2）\n---draft3---\n（投稿案3）\n---draft_end---"
    )

    try:
        ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = ai.messages.create(
            model="claude-opus-4-5",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text

        analysis_match = re.search(r"---analysis---\s*(.*?)\s*---analysis_end---", raw, re.DOTALL)
        analysis = analysis_match.group(1).strip() if analysis_match else "分析取得失敗"

        draft_parts = re.split(r"---draft\d+---", raw)
        drafts_raw = draft_parts[1:4] if len(draft_parts) >= 4 else draft_parts[1:]
        if drafts_raw:
            drafts_raw[-1] = drafts_raw[-1].split("---draft_end---")[0]
        drafts = [d.strip() for d in drafts_raw if d.strip()][:3]

        return (analysis, drafts)

    except Exception as e:
        print("[AI error] " + str(e))
        return ("AIエラー", [])


# ---- スプレッドシート保存 -----------------------------------------
def save_to_sheet(acct_name, competitor, buzz_posts, analysis, drafts):
    client = get_gspread_client()
    if not client:
        print("[skip] スプレッドシート未接続 (" + acct_name + ")")
        return

    spreadsheet = client.open_by_key(SHEET_ID)
    ws = get_or_create_sheet(spreadsheet, "バズ投稿ログ")
    today = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    for i, p in enumerate(buzz_posts):
        d1 = drafts[0] if len(drafts) > 0 else ""
        d2 = drafts[1] if len(drafts) > 1 else ""
        d3 = drafts[2] if len(drafts) > 2 else ""
        ws.append_row([
            today,
            acct_name,
            competitor,
            p["text"][:500],
            p["likes"],
            p["views"],
            analysis if i == 0 else "",
            d1 if i == 0 else "",
            d2 if i == 0 else "",
            d3 if i == 0 else "",
        ])
    print("[saved] " + acct_name + " / " + competitor
          + ": バズ投稿" + str(len(buzz_posts)) + "件, 投稿案" + str(len(drafts)) + "件")


# ---- メイン -------------------------------------------------------
def main():
    print("=== morning-research v4 ===")
    print("実行時刻 (JST): " + datetime.now(JST).strftime("%Y-%m-%d %H:%M"))

    if not COMPETITOR_ACCOUNTS:
        print("[error] COMPETITOR_ACCOUNTS が未設定です。")
        print("GitHub Secrets に COMPETITOR_ACCOUNTS=user1,user2 の形式で設定してください。")
        return

    for competitor in COMPETITOR_ACCOUNTS:
        print("--- 競合アカウント分析: @" + competitor + " ---")

        posts = fetch_threads_posts(competitor)
        print("  取得投稿数: " + str(len(posts)))

        buzz = filter_buzz_posts(posts, hours=24)
        print("  バズ投稿数: " + str(len(buzz)))

        if not buzz:
            print("  バズ投稿なし -> スキップ")
            continue

        for acct in OWN_ACCOUNTS:
            print("  -> アカウント [" + acct["name"] + "] の投稿案生成中...")
            analysis, drafts = analyze_and_generate(buzz, acct)
            save_to_sheet(acct["name"], competitor, buzz, analysis, drafts)

        time.sleep(2)

    print("=== done ===")


if __name__ == "__main__":
    main()
