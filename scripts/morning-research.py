"""
毎朝の競合アカウント自動分析スクリプト
実行前に以下の環境変数を設定してください：
  GOOGLE_SHEETS_ID: スプレッドシートのID
  GOOGLE_CREDENTIALS_PATH: サービスアカウントJSONのパス
"""

import subprocess
import os
from datetime import datetime

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# Google Sheetsの設定
SHEET_ID = os.environ.get("GOOGLE_SHEETS_ID", "1nViEkwMMvFuZEL6OD38X4cAUQq-erYk8Kl1GEwF0FwQ")
CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")

def get_competitor_urls():
    """スプレッドシートから競合URLリストを取得"""
    if not GSPREAD_AVAILABLE or not CREDENTIALS_PATH:
        print("警告：gspreadが未インストールまたは認証情報がありません。サンプルデータを使用します。")
        return [("@yuta_ikuji", "https://www.threads.com/@yuta_ikuji")]

    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("competitor-list")
    records = sheet.get_all_records()
    return [(r["アカウント名"], r["URL"]) for r in records if r.get("優先度") == "高"]

def run_claude_analysis(accounts):
    """Claude Codeに競合分析を依頼するプロンプトを生成"""
    account_list = "\n".join([f"- {name}：{url}" for name, url in accounts])
    today = datetime.now().strftime('%Y年%m月%d日')

    prompt = f"""
このリポジトリのAGENTS.mdとdocs/をすべて読んでください。

競合アカウント分析モードで動いてください。

本日（{today}）の分析対象：
{account_list}

各アカウントの前日または最新の投稿を確認し、伸びていそうな投稿のフックと構成を分析してください。
分析結果をもとに、自分のアカウント用のオリジナル投稿案を2投稿ツリーで作成してください。
【1投稿目：最重要】フックのみ。スクロールが止まる一文に全力を注いでください。フック案を3パターン出してから最良のものを選んでください。
【2投稿目】PR内容。商品・サービスの詳細につながる内容にしてください。
投稿前に必ず確認を取ってください。
"""

    print("=== 本日の競合分析プロンプト ===")
    print(prompt)

    # プロンプトをファイルに保存（Claude Codeが読み込めるように）
    output_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"morning-prompt-{datetime.now().strftime('%Y%m%d')}.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\nプロンプトを保存しました：{output_path}")

if __name__ == "__main__":
    print(f"実行日時：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
    accounts = get_competitor_urls()
    print(f"分析対象：{len(accounts)}アカウント")
    run_claude_analysis(accounts)
