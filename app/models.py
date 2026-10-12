"""
結果データモデル。

クライアント合意の「区分」＋「証跡」を型として表現する:
  受付確認 / 送信処理完了（推定） / 失敗 / スキップ
各行に 確信度・判定根拠種別・検出文言/受付番号・確認前後URL・フォーム残存・
判定日時・注意(但し書き) を保持する。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import config


@dataclass
class ProcessResult:
    target_url: str
    result: str = config.RESULT_FAILED        # 受付確認/送信処理完了（推定）/失敗/スキップ
    confidence: str = config.CONFIDENCE_NONE   # 高/中/低/-
    evidence_type: str = config.EVIDENCE_NONE  # 判定根拠種別
    evidence_detail: str = ""                  # 検出した完了文言 or 受付番号
    url_before: str = ""                       # 確認前URL
    url_after: str = ""                        # 確認後URL
    form_remained: str = "-"                   # 残存/消失/-
    reason: str = ""                           # 理由 / 判定できなかった理由
    inquiry_url: str = ""                       # 実際に送信/検証したお問い合わせURL
    timestamp: str = ""                         # 判定日時
    used_message: str = ""
    caution: str = ""                           # 注意（但し書き）
    steps: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- ファクトリ -------------------------------------------------------
    @classmethod
    def receipt_confirmed(cls, url, evidence_type, evidence_detail, *, reason="受付確認",
                          inquiry_url="", used_message="", url_before="", url_after="",
                          form_remained="消失", confidence=config.CONFIDENCE_HIGH, steps=1):
        return cls(
            target_url=url, result=config.RESULT_RECEIPT_CONFIRMED,
            confidence=confidence, evidence_type=evidence_type, evidence_detail=evidence_detail,
            url_before=url_before, url_after=url_after, form_remained=form_remained,
            reason=reason, inquiry_url=inquiry_url, used_message=used_message, steps=steps,
            caution=config.RECEIPT_DISCLAIMER,
        )

    @classmethod
    def submit_presumed(cls, url, *, evidence_type, reason, inquiry_url="", used_message="",
                        url_before="", url_after="", form_remained="-",
                        evidence_detail="", confidence=config.CONFIDENCE_LOW, steps=1):
        return cls(
            target_url=url, result=config.RESULT_SUBMIT_PRESUMED,
            confidence=confidence, evidence_type=evidence_type, evidence_detail=evidence_detail,
            url_before=url_before, url_after=url_after, form_remained=form_remained,
            reason=reason, inquiry_url=inquiry_url, used_message=used_message, steps=steps,
            caution=config.CAUTION_PRESUMED,
        )

    @classmethod
    def failed(cls, url, reason, *, inquiry_url="", url_before="", url_after="",
               form_remained="-", evidence_detail=""):
        return cls(
            target_url=url, result=config.RESULT_FAILED,
            confidence=config.CONFIDENCE_NONE, evidence_type=config.EVIDENCE_NONE,
            evidence_detail=evidence_detail, url_before=url_before, url_after=url_after,
            form_remained=form_remained, reason=reason, inquiry_url=inquiry_url,
        )

    @classmethod
    def skipped(cls, url, reason, *, inquiry_url=""):
        return cls(
            target_url=url, result=config.RESULT_SKIPPED,
            confidence=config.CONFIDENCE_NONE, reason=reason, inquiry_url=inquiry_url,
        )

    # ---- 出力 -------------------------------------------------------------
    def to_csv_row(self) -> dict:
        return {
            "対象URL": self.target_url,
            "結果": self.result,
            "確信度": self.confidence,
            "判定根拠種別": self.evidence_type,
            "検出文言/受付番号": self.evidence_detail,
            "確認前URL": self.url_before,
            "確認後URL": self.url_after,
            "フォーム残存": self.form_remained,
            "理由": self.reason,
            "お問い合わせURL": self.inquiry_url,
            "判定日時": self.timestamp,
            "使用メッセージ": self.used_message,
            "注意": self.caution,
        }

    @property
    def is_confirmed(self) -> bool:
        return self.result == config.RESULT_RECEIPT_CONFIRMED

    @property
    def is_presumed(self) -> bool:
        return self.result == config.RESULT_SUBMIT_PRESUMED


@dataclass
class Target:
    """入力1行: A列=URL, B列=個別本文(空欄なら共通本文)"""
    url: str
    message_b: str = ""


@dataclass
class SubmitOutcome:
    """form_detector の送信判定が返す内部結果。"""
    status: str                              # config.RESULT_*
    reason: str = ""
    evidence_type: str = config.EVIDENCE_NONE
    evidence_detail: str = ""
    url_before: str = ""
    url_after: str = ""
    form_remained: str = "-"
    confidence: str = config.CONFIDENCE_NONE
    steps: int = 1
