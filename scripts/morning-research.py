# morning-research v3
# 運用方針: バズ投稿の収集はClaudeチャット（Chrome拡張）が直接Threadsを開いて行う
# このスクリプトの役割: スプレッドシートへのドラフト保存のみ
import os, json, re
from datetime import datetime, timezone, timedelta
try:
            import gspread; from google.oauth2.service_account import Credentials; GSPREAD_AVAILABLE = True
except ImportError:
            GSPREAD_AVAILABLE = False
        try:
                    import anthropic; ANTHROPIC_AVAILABLE = True
except ImportError:
            ANTHROPIC_AVAILABLE = False

SHEET_ID = os.environ.get("GOOGLE_SHEETS_ID", "1nViEkwMMvFuZEL6OD38X4cAUQq-erYk8Kl1GEwF0FwQ")
CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
JST = timezone(timedelta(hours=9))
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
OWN_ACCOUNTS = [
            {"name": "haru",  "genre": "ikuji",       "target": "0-3sai mama",   "style": "onesan Hook: ano~"},
            {"name": "lemon", "genre": "ikuji otoku",  "target": "0-2sai mama",   "style": "otoku genki"},
            {"name": "fumin", "genre": "ikuji okane",  "target": "30sai okasan",  "style": "osaka-ben"},
]

def gc():
            if not GSPREAD_AVAILABLE or not CREDENTIALS_JSON:
                            return None
                        return gspread.authorize(Credentials.from_service_account_info(json.loads(CREDENTIALS_JSON), scopes=SCOPES))

def get_sheet(spreadsheet, keyword):
            for ws in spreadsheet.worksheets():
                            if keyword in ws.title:
                                                return ws
                                        raise Exception(f"シートが見つかりません: {keyword}")

def save_drafts(name, d, theme, drafts):
            c = gc()
    if not c:
                    print(f"[skip] スプレッドシート未接続 ({name})")
        return
    s = get_sheet(c.open_by_key(SHEET_ID), "バズ投稿ログ")
    for i, dr in enumerate(drafts, 1):
                    s.append_row([d, f"[draft{i}]{name}", theme, dr])
    print(f"[saved] {name}: {len(drafts)}件")

def generate_drafts(buzz_summary, acct):
            if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
                            return []
    ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today = datetime.now(JST).strftime("%Y/%m/%d")
    prompt = (
                    f"競合のバズ投稿まとめ ({today}):\n{buzz_summary}\n\n"
                    f"アカウント: {acct['name']} / ジャンル: {acct['genre']} / "
                    f"ターゲット: {acct['target']} / 文体: {acct['style']}\n\n"
                    "上記バズ投稿のジャンル・テーマを参考に、Threads育児アカウント向けの"
                    "オリジナル日本語投稿案を3つ作成してください。\n"
                    "競合の文体・構成はコピーしないこと。\n"
                    "1行目=フック、2〜4行目=本文。区切り: ---draft1--- ---draft2--- ---draft3---"
    )
    try:
                    msg = ai.messages.create(
                                        model="claude-opus-4-5", max_tokens=2000,
                                        messages=[{"role": "user", "content": prompt}]
                    )
        parts = re.split(r'---draft\d+---', msg.content[0].text)
        return [p.strip() for p in parts if p.strip()][:3]
except Exception as e:
        print(f"[AI error] {e}")
        return []

def main(buzz_summary=""):
            """
                buzz_summary: Claudeチャットがバズ投稿を収集・整形して渡す文字列
                    空の場合は「バズなし」として処理
                        """
    print("=== morning-research v3 ===")
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if not buzz_summary:
                    buzz_summary = "No buzz today."
    print(f"buzz_summary:\n{buzz_summary}")
    for acct in OWN_ACCOUNTS:
                    drafts = generate_drafts(buzz_summary, acct)
        if drafts:
                            save_drafts(acct["name"], today, "buzz-draft", drafts)
    print("=== done ===")

if __name__ == "__main__":
            # コマンドライン引数またはstdinでbuzz_summaryを受け取る
            import sys
    summary = sys.argv[1] if len(sys.argv) > 1 else ""
    main(summary)
