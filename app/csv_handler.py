"""
入力リスト読み込み / 結果CSV出力。

入力: A列=対象URL, B列=個別本文（空欄なら共通本文を使用）
      .csv（UTF-8 / CP932 自動判定）と .xlsx に対応。
出力: config.CSV_COLUMNS, UTF-8(BOM) で Excel 互換。
      ファイル名 ツール実行結果_YYYYMMDDHHMMSS.csv
"""
from __future__ import annotations

import csv
import os
from datetime import datetime

import config
from models import Target, ProcessResult


def _looks_like_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith("http://") or s.startswith("https://") or s.startswith("www.")


def _read_csv_rows(path: str) -> list[list[str]]:
    # エンコーディング自動判定（UTF-8系 → CP932 の順）
    for enc in ("utf-8-sig", "utf-8", "cp932"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return [row for row in csv.reader(f)]
        except (UnicodeDecodeError, UnicodeError):
            continue
    # 最終手段
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return [row for row in csv.reader(f)]


def _read_xlsx_rows(path: str) -> list[list[str]]:
    try:
        import openpyxl
    except ImportError as e:
        raise RuntimeError("xlsx を読むには openpyxl が必要です") from e
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for r in ws.iter_rows(values_only=True):
        rows.append(["" if c is None else str(c) for c in r])
    wb.close()
    return rows


def load_targets(path: str) -> list[Target]:
    """A列URL / B列本文 のリストを読み込む。ヘッダ行は自動でスキップ。"""
    ext = os.path.splitext(path)[1].lower()
    rows = _read_xlsx_rows(path) if ext in (".xlsx", ".xlsm") else _read_csv_rows(path)

    targets: list[Target] = []
    seen = set()
    for i, row in enumerate(rows):
        if not row:
            continue
        url = (row[0] if len(row) >= 1 else "").strip()
        msg = (row[1] if len(row) >= 2 else "").strip()
        if not url:
            continue
        # 1行目がヘッダらしければスキップ
        if i == 0 and not _looks_like_url(url):
            continue
        if not _looks_like_url(url):
            # URLでない行は無視（ヘッダ・注記など）
            continue
        if url.lower().startswith("www."):
            url = "https://" + url
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        targets.append(Target(url=url, message_b=msg))
    return targets


def default_output_path(out_dir: str = ".") -> str:
    ts = datetime.now().strftime(config.CSV_DATETIME_FORMAT)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"ツール実行結果_{ts}.csv")


class ResultWriter:
    """逐次追記できる結果ライター（途中共有に対応）。"""

    def __init__(self, path: str):
        self.path = path
        self._f = open(path, "w", encoding="utf-8-sig", newline="")
        self._w = csv.DictWriter(self._f, fieldnames=config.CSV_COLUMNS)
        self._w.writeheader()
        self._f.flush()

    def write(self, result: ProcessResult):
        self._w.writerow(result.to_csv_row())
        self._f.flush()  # 途中で共有を求められても最新が読める

    def close(self):
        try:
            self._f.close()
        except Exception:
            pass


def write_all(path: str, results: list[ProcessResult]):
    w = ResultWriter(path)
    try:
        for r in results:
            w.write(r)
    finally:
        w.close()
