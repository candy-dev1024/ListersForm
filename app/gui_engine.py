"""
GUI向けエンジン（元UIが前提とするAPIを提供）。

判定の中身は是正済みの AutomationEngine._process_single_target を再利用し、
GUI用に「状態・統計・一時停止・スキップ・コールバック」を付与する。
"""
from __future__ import annotations

import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
import csv_handler
import scheduler
from automation_engine import AutomationEngine
from models import ProcessResult

SETTINGS_FILENAME = "listersform_settings.json"

DEFAULT_CONFIG = {
    "parallel_count": 1,
    "headless": True,
    "direct_mode": False,
    "duplicate_check": False,
    "time_restriction_enabled": False,
    "time_restriction_start": "21:00",
    "time_restriction_end": "07:00",
    "day_restriction_enabled": False,
    "day_restriction_days": [],
}


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class GuiEngine:
    def __init__(self):
        self.config = dict(DEFAULT_CONFIG)
        self.form_data: dict = {}
        self.common_message: str = ""
        self._targets = []

        # UIコールバック（属性で差し込む）
        self.on_log_update = None
        self.on_progress_update = None
        self.on_status_update = None

        self._stop = threading.Event()
        self._pause = threading.Event()
        self._skip = threading.Event()
        self._skip_lock = threading.Lock()
        self._running = False
        self._state = "待機中"
        self._stats = Counter()
        self._thread = None
        self._last_output = ""

    # ---- 設定 ----
    def set_config(self, d): self.config.update(d or {})
    def set_form_data(self, d): self.form_data = dict(d or {})
    def set_common_message(self, m): self.common_message = m or ""

    # ---- 入力 ----
    def load_targets(self, path):
        self._targets = csv_handler.load_targets(path)
        return self._targets

    # ---- 状態 ----
    def get_status(self) -> dict:
        return {
            "is_running": self._running,
            "is_paused": self._pause.is_set(),
            "state": self._state,
            "statistics": {
                "success": self._stats.get("success", 0),
                "failed": self._stats.get("failed", 0),
                "skipped": self._stats.get("skipped", 0),
            },
        }

    # ---- 制御 ----
    def start(self, dry_run: bool = False):
        if self._running:
            return
        self._stop.clear(); self._pause.clear(); self._skip.clear()
        self._stats = Counter()
        self._running = True
        self._thread = threading.Thread(target=self._run, args=(dry_run,), daemon=True)
        self._thread.start()

    def stop(self): self._stop.set()
    def pause(self): self._pause.set()
    def resume(self): self._pause.clear()

    def skip_current(self):
        with self._skip_lock:
            self._skip.set()

    # ---- コールバック送出 ----
    def _emit_log(self, m):
        cb = self.on_log_update
        if cb:
            try: cb(m)
            except Exception: pass

    def _emit_progress(self, c, t):
        cb = self.on_progress_update
        if cb:
            try: cb(c, t)
            except Exception: pass

    def _set_state(self, s):
        self._state = s
        cb = self.on_status_update
        if cb:
            try: cb(s)
            except Exception: pass

    def _wait_pause(self):
        shown = False
        while self._pause.is_set() and not self._stop.is_set():
            if not shown:
                self._set_state("一時停止中"); shown = True
            time.sleep(0.3)
        if shown and not self._stop.is_set():
            self._set_state("実行中")

    def _tally(self, r: ProcessResult):
        if r.result in (config.RESULT_RECEIPT_CONFIRMED, config.RESULT_SUBMIT_PRESUMED):
            self._stats["success"] += 1
        elif r.result == config.RESULT_FAILED:
            self._stats["failed"] += 1
        elif r.result == config.RESULT_SKIPPED:
            self._stats["skipped"] += 1

    # ---- 実行本体 ----
    def _run(self, dry_run):
        settings = {"config": self.config, "form_data": self.form_data,
                    "common_message": self.common_message}
        inner = AutomationEngine(settings, logger=self._emit_log,
                                 exclusion_ini=os.path.join(_base_dir(), "exclusion_dates.ini"))
        # 停止・スキップのイベントを共有
        inner._stop = self._stop
        inner._skip = self._skip
        inner._skip_lock = self._skip_lock

        out_dir = os.path.join(_base_dir(), "output")
        out_path = csv_handler.default_output_path(out_dir)
        self._last_output = out_path
        writer = csv_handler.ResultWriter(out_path)
        total = len(self._targets)
        done = 0
        workers = max(1, min(int(self.config.get("parallel_count", 1)), config.MAX_PARALLEL_COUNT))
        self._set_state("実行中")
        self._emit_progress(0, total)
        try:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {}
                for t in self._targets:
                    if self._stop.is_set():
                        break
                    self._wait_pause()
                    if self._stop.is_set():
                        break
                    futures[ex.submit(inner._safe_process, t, dry_run)] = t
                for fut in as_completed(futures):
                    t = futures[fut]
                    try:
                        r = fut.result()
                    except Exception as e:
                        r = ProcessResult.failed(t.url, f"{config.REASON_UNKNOWN_ERROR}: {str(e)[:120]}")
                    writer.write(r)
                    self._tally(r)
                    done += 1
                    self._emit_progress(done, total)
        finally:
            writer.close()
            self._running = False
            st = self._stats
            self._emit_log(
                f"完了: 受付確認/推定(成功) {st.get('success',0)} / "
                f"失敗 {st.get('failed',0)} / スキップ {st.get('skipped',0)} … {out_path}")
            self._set_state("停止" if self._stop.is_set() else "完了")
