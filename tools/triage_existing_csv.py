"""
10/7 実行分（既存の結果CSV）の第一次切り分け。

既存CSVの「理由」列には、どの判定経路で「成功」になったかが残っているため、
送信操作を再実行しなくても、誤判定の可能性を信頼度別に分類できる。

分類（成功行のみ）:
  誤判定の可能性=高 : 「エラーなし」「JavaScript送信(リダイレクトなし)」「フォールバック」
                      → 積極的な受付確証がゼロ（エラーが出なかっただけ）
  誤判定の可能性=中 : 「成功メッセージ検出」
                      → 完了文言を検出したが、汎用語の誤検出の可能性があり受付確認証跡は未取得
  誤判定の可能性=低 : 「リダイレクト検出」
                      → 送信後に別ページへ遷移を確認（比較的確か）

使い方:
  python -I triage_existing_csv.py <入力CSV> <出力CSV>
"""
import sys
import csv
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def classify(result: str, reason: str):
    """returns (再判定区分, 確信度, 誤判定の可能性, コメント)"""
    result = (result or "").strip()
    reason = (reason or "").strip()

    if result == "成功":
        has_redirect = "リダイレクト検出" in reason
        if has_redirect:
            return ("送信処理完了（推定）", "中", "低",
                    "送信後にページ遷移を確認（比較的確か）。ただし受付番号等の確証は未取得。")
        if "エラーなし" in reason:
            return ("送信処理完了（推定）", "低", "高",
                    "エラーが検出されなかっただけで成功扱い＝積極的な受付確証なし。誤判定の可能性が高い。")
        if "JavaScript送信" in reason:
            return ("送信処理完了（推定）", "低", "高",
                    "JavaScriptで送信を試行しただけで確証なし。誤判定の可能性が高い。")
        if "フォールバック" in reason:
            return ("送信処理完了（推定）", "低", "高",
                    "フォールバック送信で確証なし。誤判定の可能性が高い。")
        if "成功メッセージ検出" in reason:
            return ("送信処理完了（推定）", "中", "中",
                    "完了文言を検出したが、汎用語（『ありがとうございます』『ご連絡』等）"
                    "での誤検出の可能性あり。受付確認の証跡は未取得。")
        return ("送信処理完了（推定）", "低", "中", "判定経路不明。要再検証。")

    if result == "失敗":
        return ("失敗", "-", "-", reason)
    if result == "スキップ":
        return ("スキップ", "-", "-", reason)
    return (result, "-", "-", reason)


def main():
    in_path = sys.argv[1]
    out_path = sys.argv[2]

    rows = []
    with open(in_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        in_cols = reader.fieldnames
        for row in reader:
            rows.append(row)

    out_cols = ["対象URL", "元の結果", "元の理由", "再判定区分", "確信度",
                "誤判定の可能性", "コメント", "お問い合わせURL", "タイムスタンプ"]

    risk = Counter()
    bucket = Counter()
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_cols)
        writer.writeheader()
        for row in rows:
            res = (row.get("結果") or "").strip()
            rea = (row.get("理由") or "").strip()
            cat, conf, misrisk, comment = classify(res, rea)
            bucket[res] += 1
            if res == "成功":
                risk[misrisk] += 1
            writer.writerow({
                "対象URL": row.get("対象URL", ""),
                "元の結果": res,
                "元の理由": rea,
                "再判定区分": cat,
                "確信度": conf,
                "誤判定の可能性": misrisk,
                "コメント": comment,
                "お問い合わせURL": row.get("お問い合わせURL", ""),
                "タイムスタンプ": row.get("タイムスタンプ", ""),
            })

    total = len(rows)
    print(f"入力: {in_path}")
    print(f"出力: {out_path}")
    print(f"総行数: {total}")
    print("\n=== 元の結果の内訳 ===")
    for k, v in bucket.most_common():
        print(f"  {k:6s}: {v:5d} ({100*v/total:5.1f}%)")

    succ = bucket.get("成功", 0)
    print(f"\n=== 『成功』{succ}件の誤判定の可能性（再判定） ===")
    order = ["高", "中", "低"]
    for k in order:
        v = risk.get(k, 0)
        label = {"高": "誤判定の可能性=高（受付確証ゼロ）",
                 "中": "誤判定の可能性=中（文言一致のみ）",
                 "低": "誤判定の可能性=低（遷移確認あり）"}[k]
        pct = 100 * v / succ if succ else 0
        print(f"  {label}: {v:5d} ({pct:5.1f}%)")

    high = risk.get("高", 0)
    mid = risk.get("中", 0)
    print(f"\n→ 少なくとも {high} 件は受付確証ゼロで、誤って成功計上された可能性が高い。")
    print(f"→ さらに {mid} 件は文言一致のみで、受付確認の証跡が取れていない。")


if __name__ == "__main__":
    main()
