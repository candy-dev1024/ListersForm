"""
フェーズ2（方式B）: 静的HTML検証。

クライアント合意の最も保守的な方式:
  - JavaScript は実行しない（HTMLを取得して読むだけ）
  - 入力欄への値の入力、送信/確認ボタン操作、送信リクエスト、下書き保存は一切行わない
  - 通信は対象ページの HTTP GET のみ

既存の結果CSVの「お問い合わせURL」（無ければ「対象URL」）を対象に、
取得したHTMLから静的に判断できる範囲で「送信が成立しない可能性が高い行」を切り分ける。
HTML取得のみでは判断できないもの（動的生成フォーム等）は「判定不能（動的生成等）」とする。

使い方:
  python phase2_static_check.py --input <結果CSV> --settings <設定JSON> --output <出力CSV>
     [--all] [--limit N] [--delay 1.0]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import config  # noqa: E402

# 最長一致でフィールド種別を判定（form_detector と同方針）
_FLAT = sorted(
    [(len(p), k, p.lower()) for k, ps in config.FIELD_PATTERNS.items() for p in ps],
    key=lambda x: x[0], reverse=True,
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ListersFormStaticCheck/1.0; validation GET only)"}

_PREF_NAMES = set("""北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県
千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県
滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県
愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県""".split())


def _looks_like_prefecture(opts) -> bool:
    """選択肢の内容から都道府県selectかどうかを判定（ラベル未関連でも拾う）。"""
    return sum(1 for o in opts if (o or "").strip() in _PREF_NAMES) >= 3


def identify_type(meta: str) -> str | None:
    meta = (meta or "").lower()
    for _, key, pat in _FLAT:
        if pat in meta:
            return key
    return None


def _label_text(soup, el) -> str:
    try:
        if el.get("aria-label"):
            return el.get("aria-label")
        eid = el.get("id")
        if eid:
            lab = soup.find("label", attrs={"for": eid})
            if lab and lab.get_text(strip=True):
                return lab.get_text(" ", strip=True)
        plab = el.find_parent("label")
        if plab and plab.get_text(strip=True):
            return plab.get_text(" ", strip=True)
        cell = el.find_parent(["td", "dd"])
        if cell:
            row = cell.find_parent(["tr", "dl", "div"])
            if row:
                head = row.find(["th", "dt", "legend", "label"])
                if head and head.get_text(strip=True):
                    return head.get_text(" ", strip=True)
    except Exception:
        pass
    return el.get("placeholder") or ""


def _meta(soup, el) -> str:
    parts = []
    for a in ("name", "id", "placeholder", "aria-label", "title", "class"):
        v = el.get(a)
        if v:
            parts.append(" ".join(v) if isinstance(v, list) else str(v))
    parts.append(_label_text(soup, el))
    return " ".join(parts)


def _is_required(el, meta: str) -> bool:
    if el.has_attr("required"):
        return True
    if (el.get("aria-required") or "").lower() == "true":
        return True
    return any(k in meta for k in ("必須", "※")) or "required" in meta.lower()


def _maxlen(el):
    try:
        m = el.get("maxlength")
        if m and str(m).isdigit() and int(m) > 0:
            return int(m)
    except Exception:
        pass
    return None


def evaluate_form_html(html: str, message_len: int, available_types: set[str]) -> dict:
    """ネットワーク非依存の中核。HTML文字列を評価して判定を返す。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")

    inputs = soup.find_all(["input", "textarea", "select"])
    # フォームらしさ
    textareas = [e for e in inputs if e.name == "textarea"]
    emails = [e for e in soup.find_all("input") if (e.get("type") or "").lower() == "email"]
    text_inputs = [e for e in soup.find_all("input")
                   if (e.get("type") or "text").lower() in ("", "text", "tel", "url")]
    form_found = bool(textareas) or bool(emails) or len(text_inputs) >= 2
    if not form_found:
        return {"verdict": "判定不能（動的生成等）",
                "basis": "HTML取得のみではフォーム要素を検出できず（JSによる動的生成等の可能性）",
                "required": 0, "unmapped_labels": [], "sonota_options": "", "max_len": "", "msg_len": message_len}

    coverable = set(available_types) | {"message", "inquiry_type", "contact_method", "source"}

    def short_label(el):
        lab = _label_text(soup, el).strip() or (el.get("name") or el.get("id") or el.get("placeholder") or "不明")
        return (" ".join(str(lab).split()))[:24] or "不明"

    required_count = 0
    unmapped_labels = []   # 対応データに紐付け不可の必須項目（ラベル）
    sonota_options = ""    # 必須『用件』選択肢（その他なしのとき）
    sonota_block = False
    char_block = False
    max_len = ""

    for el in inputs:
        typ = (el.get("type") or "").lower()
        if typ in ("hidden", "submit", "button", "image", "reset"):
            continue
        meta = _meta(soup, el)
        required = _is_required(el, meta)

        if el.name == "select":
            if required:
                required_count += 1
                opts = [o.get_text(" ", strip=True) for o in el.find_all("option") if o.get_text(strip=True)]
                ftype = identify_type(meta)
                is_pref = _looks_like_prefecture(opts)
                # 連絡方法/流入は選択ルール、保有データ型（都道府県等）は保存値で選択可能
                if ftype in ("contact_method", "source") or (ftype in available_types) \
                        or (is_pref and "prefecture" in available_types):
                    pass
                else:
                    # 用件/種別 もしくは不明な必須select → 「その他／一般」等が無ければ阻害
                    has_pref = any(any(p in o for p in config.INQUIRY_TYPE_PREFERENCE) for o in opts)
                    if not has_pref:
                        sonota_block = True
                        if not sonota_options:
                            sonota_options = " / ".join(opts[:8])
            continue

        if typ in ("checkbox", "radio"):
            continue  # 同意/選択はルールで対応するため未充足要因から除外

        # text / textarea / email / tel / url
        if required:
            required_count += 1
            if el.name == "textarea":
                pass  # テキストエリアは本文として必ず入力されるため未充足にしない
            else:
                ftype = identify_type(meta)
                if ftype is None or (ftype not in coverable):
                    unmapped_labels.append(short_label(el))

        if el.name == "textarea":
            ml = _maxlen(el)
            if ml and message_len and message_len > ml:
                char_block = True
                if max_len == "" or ml < max_len:
                    max_len = ml

    blockers = []
    if unmapped_labels:
        blockers.append(
            f"必須項目を汎用値で代替入力＝形式不一致の可能性（{', '.join(unmapped_labels[:5])}／計{len(unmapped_labels)}件）")
    if char_block:
        blockers.append(f"本文{message_len}字＞文字数上限{max_len}字")
    if sonota_block:
        blockers.append("必須『用件』選択に「その他／一般」等なし")

    if blockers:
        verdict = "送信不成立の可能性＝高"
        basis = "／".join(blockers)
    else:
        verdict = "静的に阻害要因なし（受付確認は本番検証が必要）"
        basis = "必須項目はマッピング可能／文字数・選択肢に明らかな問題なし"

    return {"verdict": verdict, "basis": basis, "required": required_count,
            "unmapped_labels": unmapped_labels, "sonota_options": sonota_options,
            "max_len": max_len, "msg_len": message_len}


def fetch(url: str, timeout: int = 12):
    import requests
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        # requests は charset 未指定時 ISO-8859-1 を既定にするため日本語が文字化けする。
        # 明示 charset が無い/ISO-8859-1 の場合は内容から推定したエンコーディングに切替。
        if (r.encoding is None) or (r.encoding.lower() == "iso-8859-1"):
            r.encoding = r.apparent_encoding or r.encoding
        return (r.status_code, r.text, "")
    except Exception as e:
        return (0, "", f"{type(e).__name__}: {str(e)[:80]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="フェーズ2 方式B 静的HTML検証（JS非実行・送信なし）")
    ap.add_argument("--input", required=True, help="既存の結果CSV（対象URL/結果/理由/お問い合わせURL 列）")
    ap.add_argument("--settings", required=True, help="設定JSON（common_message, form_data）")
    ap.add_argument("--output", required=True, help="出力CSV")
    ap.add_argument("--all", action="store_true", help="成功行以外も対象にする")
    ap.add_argument("--limit", type=int, default=0, help="先頭N件のみ（0=全件）")
    ap.add_argument("--delay", type=float, default=1.0, help="各GET間の待機秒（サイト負荷配慮）")
    args = ap.parse_args(argv)

    with open(args.settings, encoding="utf-8-sig") as f:
        settings = json.load(f)
    message_len = len(settings.get("common_message", "") or "")
    available = {k for k, v in (settings.get("form_data") or {}).items() if str(v).strip()}

    rows = []
    with open(args.input, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    if not args.all:
        rows = [r for r in rows if (r.get("結果") or "").strip() == "成功"]
    if args.limit:
        rows = rows[:args.limit]

    out_cols = ["対象URL", "お問い合わせURL", "元の結果", "元の理由", "HTTPステータス",
                "静的判定", "根拠（全要因）", "未充足の可能性がある必須項目", "用件の選択肢",
                "本文長", "文字数上限", "備考"]
    from collections import Counter
    tally = Counter()

    with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_cols)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            url = (r.get("お問い合わせURL") or r.get("対象URL") or "").strip()
            if not url:
                status, html, err = 0, "", "URLなし"
            else:
                status, html, err = fetch(url)

            diag = {}
            if status == 0 or err:
                verdict, basis = "判定不能（取得失敗）", err or "接続不可"
            elif status == 403:
                verdict, basis = "判定不能（アクセス制限 403）", "サイト側でGETが拒否されました"
            elif status == 404:
                verdict, basis = "判定不能（ページ不在 404）", "ページが存在しません"
            elif status != 200:
                verdict, basis = f"判定不能（HTTP {status}）", ""
            else:
                diag = evaluate_form_html(html, message_len, available)
                verdict, basis = diag["verdict"], diag["basis"]

            tally[verdict] += 1
            w.writerow({
                "対象URL": r.get("対象URL", ""),
                "お問い合わせURL": r.get("お問い合わせURL", ""),
                "元の結果": r.get("結果", ""),
                "元の理由": r.get("理由", ""),
                "HTTPステータス": status,
                "静的判定": verdict,
                "根拠（全要因）": basis,
                "未充足の可能性がある必須項目": "; ".join(diag.get("unmapped_labels", [])),
                "用件の選択肢": diag.get("sonota_options", ""),
                "本文長": diag.get("msg_len", ""),
                "文字数上限": diag.get("max_len", ""),
                "備考": err if (status == 0 or err) else "",
            })
            print(f"\r検証 {i}/{len(rows)}", end="", flush=True)
            if args.delay:
                time.sleep(args.delay)

    print("\n=== フェーズ2（静的）判定の内訳 ===")
    for k, v in tally.most_common():
        print(f"  {v:5d}  {k}")
    print(f"出力: {args.output}")
    print("※ JavaScriptは実行しておらず、入力・送信・送信リクエストは一切行っていません。")


if __name__ == "__main__":
    main()
