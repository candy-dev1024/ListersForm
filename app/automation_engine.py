"""
自動化エンジン（統括）。

v11 の「X (of X) futures unfinished」不具合の是正:
  - 送信した future は as_completed で必ず全件回収する
  - worker は例外を必ず捕捉し、結果オブジェクトに変換（未捕捉例外を残さない）
  - スレッドごとに専用 ChromeController を生成し、finally で必ず quit する
  - ThreadPoolExecutor は with で確実に shutdown（待機）する

稼働制御（夜間/曜日/除外日）、停止・スキップ、重複除去、結果の逐次書き出しに対応。
"""
from __future__ import annotations

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
import csv_handler
import scheduler
from chrome_controller import ChromeController
from form_detector import FormDetector, SkipSite
from models import ProcessResult, Target


class AutomationEngine:
    def __init__(self, settings: dict, logger=None, progress_cb=None,
                 result_cb=None, exclusion_ini: str = "exclusion_dates.ini"):
        self.settings = settings or {}
        self.cfg = self.settings.get("config", {})
        self.form_data = self.settings.get("form_data", {})
        self.common_message = self.settings.get("common_message", "")
        self._log = logger or (lambda m: None)
        self._progress_cb = progress_cb or (lambda done, total, counts: None)
        self._result_cb = result_cb or (lambda r: None)
        self.exclusion_dates = scheduler.load_exclusion_dates(exclusion_ini)

        self._stop = threading.Event()
        self._skip = threading.Event()
        self._skip_lock = threading.Lock()

    # ----------------------------------------------------------------- 制御
    def stop(self):
        self._stop.set()
        self._log("[ENGINE] 停止要求を受け付けました。")

    def skip_current(self):
        self._skip.set()
        self._log("[ENGINE] スキップ要求を受け付けました（次の安全ポイントで反映）。")

    def _consume_skip(self) -> bool:
        with self._skip_lock:
            if self._skip.is_set():
                self._skip.clear()
                return True
        return False

    # ----------------------------------------------------------------- 入力
    def load_targets(self, path: str) -> list[Target]:
        return csv_handler.load_targets(path)

    def _build_message(self, target: Target) -> str:
        base = self.common_message or ""
        if config.COMPANY_TAG in base:
            return base.replace(config.COMPANY_TAG, target.message_b or "")
        if target.message_b:
            return target.message_b
        return base

    # ------------------------------------------------------------- 稼働制御
    def _wait_until_runnable(self):
        """夜間/曜日/除外日は稼働再開まで待機（停止要求が来たら抜ける）。"""
        logged = False
        while not self._stop.is_set():
            ok, reason = scheduler.check_runnable(self.settings, self.exclusion_dates)
            if ok:
                return
            if not logged:
                self._log(f"[ENGINE] {reason} 稼働再開まで待機します。")
                logged = True
            # 30秒刻みで再判定（停止要求に素早く反応）
            for _ in range(30):
                if self._stop.is_set():
                    return
                time.sleep(1)

    # --------------------------------------------------------------- 実行
    def start(self, targets: list[Target], dry_run: bool = False,
              output_path: str | None = None) -> tuple[str, Counter]:
        self._stop.clear()
        self._skip.clear()
        output_path = output_path or csv_handler.default_output_path("output")
        total = len(targets)
        counts: Counter = Counter()
        workers = max(1, min(int(self.cfg.get("parallel_count", 1)), config.MAX_PARALLEL_COUNT))

        self._log(f"[ENGINE] 開始: {total}件 / 並列{workers} / "
                  f"{'検証(送信なし)' if dry_run else '本番送信'} → {output_path}")

        writer = csv_handler.ResultWriter(output_path)
        try:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(self._safe_process, t, dry_run): t for t in targets}
                done = 0
                for fut in as_completed(futures):
                    t = futures[fut]
                    try:
                        result = fut.result()
                    except Exception as e:  # 念のための最終防御（通常ここには来ない）
                        result = ProcessResult.failed(t.url, f"{config.REASON_UNKNOWN_ERROR}: {str(e)[:120]}")
                    writer.write(result)
                    try:
                        self._result_cb(result)
                    except Exception:
                        pass
                    counts[result.result] += 1
                    done += 1
                    self._progress_cb(done, total, counts)
        finally:
            writer.close()

        self._log(f"[ENGINE] 完了: " + " / ".join(f"{k}:{v}" for k, v in counts.items()))
        return output_path, counts

    def _safe_process(self, target: Target, dry_run: bool) -> ProcessResult:
        """worker本体。例外は必ず結果に変換して返す（future未回収を防ぐ）。"""
        if self._stop.is_set():
            return ProcessResult.skipped(target.url, config.REASON_STOPPED_BY_USER)
        self._wait_until_runnable()
        if self._stop.is_set():
            return ProcessResult.skipped(target.url, config.REASON_STOPPED_BY_USER)
        if self._consume_skip():
            return ProcessResult.skipped(target.url, config.REASON_SKIPPED_BY_USER)
        try:
            return self._process_single_target(target, dry_run)
        except SkipSite as s:
            return ProcessResult.skipped(target.url, s.reason)
        except Exception as e:
            return ProcessResult.failed(target.url, f"{config.REASON_UNKNOWN_ERROR}: {str(e)[:120]}")

    def _process_single_target(self, target: Target, dry_run: bool) -> ProcessResult:
        url = target.url
        message = self._build_message(target)
        chrome = ChromeController(
            headless=bool(self.cfg.get("headless", True)),
            page_load_timeout=config.PAGE_LOAD_TIMEOUT,
            use_js_fallback=True,
            logger=self._log,
        )
        if not chrome.start():
            return ProcessResult.failed(url, config.REASON_ENVIRONMENT_CHROME_FAILED)
        try:
            fd = FormDetector(chrome, self.form_data, self.settings, logger=self._log)

            found, inq_url, reason = fd.find_inquiry_page(url)
            if not found:
                if reason == config.REASON_INQUIRY_NOT_FOUND:
                    return ProcessResult.skipped(url, reason)
                return ProcessResult.failed(url, reason)  # 環境/ネットワーク

            if self._stop.is_set():
                return ProcessResult.skipped(url, config.REASON_STOPPED_BY_USER, inquiry_url=inq_url)

            ng, phrase = fd.detect_ng_phrases()
            if ng:
                return ProcessResult.skipped(url, f"{config.REASON_NG_PHRASE}: {phrase}", inquiry_url=inq_url)

            if fd.is_captcha_present():
                return ProcessResult.failed(url, config.REASON_CAPTCHA_DETECTED, inquiry_url=inq_url)

            try:
                ok, freason = fd.fill_form(message)
            except SkipSite as s:
                return ProcessResult.skipped(url, s.reason, inquiry_url=inq_url)
            if not ok:
                return ProcessResult.failed(url, freason, inquiry_url=inq_url)

            outcome = fd.submit_form(dry_run=dry_run)
            return self._outcome_to_result(url, inq_url, message, outcome)
        finally:
            chrome.stop()

    def _outcome_to_result(self, url, inq_url, message, o) -> ProcessResult:
        if o.status == config.RESULT_RECEIPT_CONFIRMED:
            return ProcessResult.receipt_confirmed(
                url, o.evidence_type, o.evidence_detail, reason=o.reason,
                inquiry_url=inq_url, used_message=message,
                url_before=o.url_before, url_after=o.url_after,
                form_remained=o.form_remained, confidence=o.confidence, steps=o.steps)
        if o.status == config.RESULT_SUBMIT_PRESUMED:
            return ProcessResult.submit_presumed(
                url, evidence_type=o.evidence_type, reason=o.reason,
                inquiry_url=inq_url, used_message=message,
                url_before=o.url_before, url_after=o.url_after,
                form_remained=o.form_remained, evidence_detail=o.evidence_detail,
                confidence=o.confidence, steps=o.steps)
        # 失敗（その他）
        return ProcessResult.failed(
            url, o.reason or config.REASON_UNKNOWN_ERROR, inquiry_url=inq_url,
            url_before=o.url_before, url_after=o.url_after,
            form_remained=o.form_remained, evidence_detail=o.evidence_detail)
