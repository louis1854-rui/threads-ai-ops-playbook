# Threads AI Ops Playbook

AIニュースをリサーチし、Threads向けの通常投稿・ツリー投稿・図解投稿を作成し、Codexがブラウザ操作で投稿まで進めるための公開用プレイブックです。

このリポジトリにはログイン情報、Cookie、APIキー、個人アカウント情報は含めません。利用者は自分の環境でThreadsにログイン済みのChromeを用意し、Codexにこのリポジトリを読ませて運用します。

## できること

- 当日または指定日のAIニュースをWebで調査する
- Threads向けの単発投稿を作る
- 1投稿目で続きを匂わせるツリー投稿を3〜5件のリプ付きで作る
- 図解投稿用の画像企画・生成プロンプト・投稿文を作る
- Chrome上のログイン済みThreadsを操作して投稿する
- 投稿後にURL、使った情報源、改善メモを記録する

## 必要なもの

- Codex
- Chrome
- Codex Chrome Extension
- Threadsにログイン済みのChromeプロファイル
- Web検索ができる環境
- 画像生成機能または画像生成API
- GitHubへ公開する場合はGitHubアカウントと権限

## 最短の使い方

1. このリポジトリをCodexに渡す
2. Codexへ次のように依頼する

```text
このリポジトリのAGENTS.mdとdocs/を読んで、今日のAI最新情報でThreads投稿を作ってください。
単発ではなくツリー投稿にしてください。1投稿目は続きを匂わせ、リプを3〜5件作ってください。
図解投稿も1枚作ってください。
投稿前に必ず確認を取り、確認後はChromeのログイン済みThreadsから投稿してください。
```

3. Codexが調査、下書き、画像生成、投稿確認、ブラウザ投稿、投稿URL記録まで進める

## 重要な安全ルール

- Codexにパスワード、2FAコード、Cookie、セッション情報を渡さない
- 公開投稿、削除、課金、APIキー作成、外部送信の前には必ず確認を取る
- ニュース投稿では日付と出典を確認する
- 不確かな内容は断定しない
- 他媒体の記事本文や画像を無断転載しない

## 推奨ディレクトリ

- `AGENTS.md`: Codexが最初に読む運用ルール
- `docs/automation-workflow.md`: 自動化の全体手順
- `docs/sns-growth-playbook.md`: Threads/SNSを伸ばすためのノウハウ
- `docs/content-patterns.md`: 投稿パターンと型
- `docs/browser-operations.md`: Chrome/Threads操作の実務手順
- `docs/security-and-compliance.md`: 公開運用の安全基準
- `prompts/codex-runbook.md`: Codexへ投げる実行プロンプト
- `templates/content-brief.md`: 投稿前の企画ブリーフ
- `templates/post-log.md`: 投稿後ログ

## 運用の考え方

このリポジトリは「完全自動で勝手に投稿する仕組み」ではなく、「Codexが調査と制作を自動化し、人間の確認後に投稿する仕組み」です。SNS運用では速さも大事ですが、誤情報や意図しない公開のリスクが大きいため、投稿直前の承認を標準にしています。

