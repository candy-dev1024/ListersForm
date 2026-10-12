"""
コマンドライン実行エントリ。

例:
  python cli.py --settings listersform_settings.json --input リスト.csv --dry-run
  python cli.py --settings listersform_settings.json --input リスト.csv --parallel 4
"""
from __future__ import annotations

import argparse
import json
import sys

import config
import csv_handler
from automation_engine import AutomationEngine


def _load_settings(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="ListersForm 自動送信ツール（是正版 / CLI）")
    ap.add_argument("--settings", required=True, help="設定JSON（form_data, common_message, config）")
    ap.add_argument("--input", required=True, help="送信先リスト（A列URL / B列本文）CSV または XLSX")
    ap.add_argument("--output", default=None, help="結果CSVの出力先（省略時 output/ に自動命名）")
    ap.add_argument("--exclusion", default="exclusion_dates.ini", help="除外日ファイル")
    ap.add_argument("--parallel", type=int, default=None, help="並列数（設定JSONを上書き）")
    ap.add_argument("--dry-run", action="store_true",
                    help="送信なし検証モード（送信操作・送信リクエストを一切行わない）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--headless", dest="headless", action="store_true", help="ヘッドレス実行")
    g.add_argument("--no-headless", dest="headless", action="store_false", help="画面表示あり")
    ap.set_defaults(headless=None)
    args = ap.parse_args(argv)

    settings = _load_settings(args.settings)
    settings.setdefault("config", {})
    if args.parallel is not None:
        settings["config"]["parallel_count"] = args.parallel
    if args.headless is not None:
        settings["config"]["headless"] = args.headless

    def log(m):
        print(m, flush=True)

    def progress(done, total, counts):
        summary = " ".join(f"{k}:{v}" for k, v in counts.items())
        print(f"\r進捗 {done}/{total}  [{summary}]", end="", flush=True)

    engine = AutomationEngine(settings, logger=log, progress_cb=progress,
                              exclusion_ini=args.exclusion)
    targets = engine.load_targets(args.input)
    if not targets:
        print("対象URLが読み込めませんでした。入力ファイルを確認してください。")
        return 2

    print(f"対象 {len(targets)} 件 / モード: "
          f"{'検証（送信なし）' if args.dry_run else '本番送信'}")
    out_path, counts = engine.start(targets, dry_run=args.dry_run, output_path=args.output)
    print()
    print("=== 完了 ===")
    for k in (config.RESULT_RECEIPT_CONFIRMED, config.RESULT_SUBMIT_PRESUMED,
              config.RESULT_FAILED, config.RESULT_SKIPPED):
        print(f"  {k}: {counts.get(k, 0)}")
    print(f"結果CSV: {out_path}")
    print(config.RECEIPT_DISCLAIMER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
