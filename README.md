# ListersForm 自動送信ツール（是正版）

お問い合わせフォームへの自動送信ツール。v11 の成功判定の是正版です。

## 是正の要点（929件 誤判定への対応）

旧実装は「エラーが検出されなければ成功」「汎用文言（『ありがとうございます』等）で成功」
としており、これが「成功929件 / 実際の返信約20件」の乖離の原因でした。

本版では送信結果を次の4区分で判定します。

| 区分 | 意味 |
|---|---|
| 受付確認 | 客観的証跡（受付番号／完了URLへの遷移＋フォーム消失／明確な完了文言＋フォーム消失）が取れた場合のみ |
| 送信処理完了（推定） | 送信操作は完了したが受付の確証がない（旧「エラーなし」「JS送信のみ」等はここ） |
| 失敗 | バリデーション／URL記載不可／文字数制限／CAPTCHA／送信ボタン無し 等 |
| スキップ | NGフレーズ検出／問い合わせページ未検出／「その他」なし 等 |

**「受付確認」としない条件（明記）**: 一般的な文言のみ／エラー非表示のみ／
URLに thanks・complete 等の文字列が含まれるのみ。

> 「受付確認」はフォーム上の完了表示・受付番号等に基づく確認であり、
> 先方へのメール到達・対応完了を保証するものではありません。（画面・結果CSVに明記）

## 構成

```
app/
  config.py            定数（NG語・成功/失敗検出・フィールド対応・出力列 等）
  models.py            結果データモデル（区分・証跡・確信度・注意）
  chrome_controller.py Selenium/Chrome 制御（起動の堅牢化）
  form_detector.py     問い合わせページ検出・入力・★送信/受付確認の是正ロジック
  automation_engine.py 統括（並列処理の是正・稼働制御・停止/スキップ）
  csv_handler.py       入力リスト読込・結果CSV出力
  scheduler.py         時間帯/曜日/除外日の停止制御
  cli.py               コマンドライン実行
  main_gui.py          GUI（customtkinter）
tools/
  triage_existing_csv.py  既存の10/7結果CSVを「誤判定の可能性」で切り分け
```

## セットアップ

- Python 3.11（exe は 3.11 でビルド）/ Google Chrome 必須
- 依存インストール:

```
pip install -r requirements.txt
```

ChromeDriver は実行時に Selenium Manager（Selenium 4.6+ 標準）が自動解決します。
失敗時は webdriver-manager にフォールバックします。

## 実行

GUI:
```
python app/main_gui.py
```

CLI（送信なし検証＝安全モード）:
```
python app/cli.py --settings listersform_settings.json --input リスト.csv --dry-run
```

CLI（本番送信・並列4）:
```
python app/cli.py --settings listersform_settings.json --input リスト.csv --parallel 4
```

### 入力リスト
- A列: 対象URL
- B列: 個別本文（空欄なら共通本文を使用。本文内の `【company】` をB列文面に差し替え）
- `.csv`（UTF-8 / CP932 自動判定）および `.xlsx` に対応

### 結果CSV（列）
対象URL / 結果 / 確信度 / 判定根拠種別 / 検出文言・受付番号 / 確認前URL / 確認後URL /
フォーム残存 / 理由 / お問い合わせURL / 判定日時 / 使用メッセージ / 注意

## 929件の切り分け（既存CSVから即時）

```
python tools/triage_existing_csv.py "ツール実行結果_20261007144132.csv" "output/切り分け.csv"
```

結果（確認済み）: 成功929件のうち 誤判定の可能性=高 201 / 中 725 / 低 3。

## ビルド（exe）

```
pip install pyinstaller
pyinstaller build.spec
# → dist/ListersForm.exe
```

## 送信なし検証モード（929検証・重複送信防止）

`--dry-run`（CLI）/ GUIの「送信なし検証」では、送信ボタン操作・送信リクエストを
一切行わず、入力可否・必須充足・HTML5妥当性・URL記載可否・文字数制限のみで
送信成立可否を判定します。
# ListersForm
