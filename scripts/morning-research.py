"""
毎朝の競合アカウント自動分析スクリプト
実行前に以下の環境変数を設定してください：
  GOOGLE_SHEETS_ID: スプレッドシートのID
  GOOGLE_CREDENTIALS_JSON: サービスアカウントJSONの内容（文字列）
  GOOGLE_CREDENTIALS_PATH: サービスアカウントJSONのパス（ローカル実行時）
"""

import os
import json
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
    USE_LEGACY_AUTH = False
except ImportError:
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        GSPREAD_AVAILABLE = True
        USE_LEGACY_AUTH = True
    except ImportError:
        GSPREAD_AVAILABLE = False
        USE_LEGACY_AUTH = False

# Google Sheetsの設定
SHEET_ID = os.environ.get("GOOGLE_SHEETS_ID", "1nViEkwMMvFuZEL6OD38X4cAUQq-erYk8Kl1GEwF0FwQ")
CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]


def get_gspread_client():
    """Google Sheets クライアントを取得"""
    if not GSPREAD_AVAILABLE:
        return None
    if CREDENTIALS_JSON:
        # GitHub ActionsのSecretsからJSON文字列で渡す方式
        creds_dict = json.loads(CREDENTIALS_JSON)
        if USE_LEGACY_AUTH:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(creds_dict, f)
                tmp_path = f.name
            creds = ServiceAccountCredentials.from_json_keyfile_name(tmp_path, SCOPES)
        else:
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)
    elif CREDENTIALS_PATH:
        # ローカル実行：JSONファイルパスで渡す方式
        if USE_LEGACY_AUTH:
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPES)
        else:
            creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
        return gspread.authorize(creds)
    return None


def get_competitor_accounts():
    """スプレッドシートの①競合アカウントリストからアカウント情報を取得"""
    client = get_gspread_client()
    if not client:
        print("警告：認証情報がありません。サンプルデータを使用します。")
        return [{"アカウント名": "@sample", "URL": "https://www.threads.com/@sample", "ジャンル": "AI", "優先度": "高"}]

    sheet = client.open_by_key(SHEET_ID).worksheet("①競合アカウントリスト")
    records = sheet.get_all_records()
    # 優先度「高」のものを優先、なければ全件返す
    high_priority = [r for r in records if r.get("優先度") == "高" and r.get("URL")]
    return high_priority if high_priority else [r for r in records if r.get("URL")]


def append_to_buzz_log(date_str, post_url, hook, memo=""):
    """②バズ投稿ログにデータを追記"""
    client = get_gspread_client()
    if not client:
        print("警告：バズ投稿ログへの書き込みをスキップしました。")
        return
    sheet = client.open_by_key(SHEET_ID).worksheet("②バズ投稿ログ")
    sheet.append_row([date_str, post_url, hook, memo])
    print(f"②バズ投稿ログに追記しました：{date_str}")


def append_to_my_log(post_date, post_url, hook, memo=""):
    """③自分の投稿ログにデータを追記"""
    client = get_gspread_client()
    if not client:
        print("警告：自分の投稿ログへの書き込みをスキップしました。")
        return
    sheet = client.open_by_key(SHEET_ID).worksheet("③自分の投稿ログ")
    sheet.append_row([post_date, post_url, hook, memo])
    print(f"③自分の投稿ログに追記しました：{post_date}")


def generate_morning_prompt(accounts):
    """Claude Codeに競合分析を依頼するプロンプトを生成してファイルに保存"""
    account_list = "\n".join([
        f"- {r['アカウント名']}（{r.get('ジャンル', '')}）：{r['URL']}"
        for r in accounts
    ])
    today = datetime.now().strftime('%Y年%m月%d日')

    prompt = f"""このリポジトリのAGENTS.mdとdocs/をすべて読んでください。
競合アカウント分析モードで動いてください。
本日（{today}）の分析対象：
{account_list}
各アカウントの最新投稿を確認し、伸びていそうな投稿のフックと構成を分析してください。
分析結果をもとに、自分のアカウント用のオリジナル投稿案をツリー投稿（3〜5リプ）で作成してください。
【1投稿目：最重要】フックのみ。スクロールが止まる一文に全力を注いでください。フック案を3パターン出してから最良のものを選んでください。
【2〜5投稿目】事実→意味→使い方→注意点→まとめの構成で。
投稿前に必ず確認を取ってください。"""

    # プロンプトをファイルに保存
    output_path = "prompts/morning-research-prompt.md"
    os.makedirs("prompts", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 毎朝の競合分析プロンプト\n\n")
        f.write(f"生成日時：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(prompt)
    print(f"プロンプトを保存しました：{output_path}")
    return prompt


def main():
    """メイン処理"""
    print(f"=== 毎朝の競合アカウント分析開始 ===")
    print(f"実行日時：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 競合アカウント情報を取得
    accounts = get_competitor_accounts()
    print(f"分析対象アカウント数：{len(accounts)}")
    for acc in accounts:
        print(f"  - {acc.get('アカウント名', 'N/A')}（{acc.get('URL', 'N/A')}）")

    # プロンプトを生成
    prompt = generate_morning_prompt(accounts)
    print("\nプロンプト生成完了。Claude Codeで実行してください。")
    print("\n=== 分析完了 ===")


if __name__ == "__main__":
    main()
