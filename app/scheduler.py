"""
稼働制御: 時間帯停止・曜日停止・除外日（祝日/共有日）停止。

settings.config の構造:
  time_restriction_enabled, time_restriction_start "HH:MM", time_restriction_end "HH:MM"
     → start〜end の時間帯は「稼働しない」(夜間停止など。日跨ぎ可)
  day_restriction_enabled, day_restriction_days [0=月 .. 6=日]
     → 指定曜日は稼働しない
  exclusion_dates.ini の [exclusion_dates] 配下の YYYY-MM-DD は稼働しない
"""
from __future__ import annotations

import os
from datetime import datetime, time


def load_exclusion_dates(ini_path: str) -> set[str]:
    dates: set[str] = set()
    if not ini_path or not os.path.exists(ini_path):
        return dates
    try:
        with open(ini_path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith(";") or s.startswith("#") or s.startswith("["):
                    continue
                # 先頭が日付形式のものだけ採用
                token = s.split()[0]
                if len(token) == 10 and token[4] == "-" and token[7] == "-":
                    dates.add(token)
    except Exception:
        pass
    return dates


def _parse_hhmm(s: str, default: time) -> time:
    try:
        hh, mm = s.split(":")
        return time(int(hh), int(mm))
    except Exception:
        return default


def _in_wraparound(now_t: time, start: time, end: time) -> bool:
    """start〜end の時間帯に now が入っているか（日跨ぎ対応）。"""
    if start <= end:
        return start <= now_t < end
    # 日跨ぎ（例 20:00〜08:00）
    return now_t >= start or now_t < end


def check_runnable(settings: dict, exclusion_dates: set[str],
                   now: datetime | None = None) -> tuple[bool, str]:
    """
    returns (runnable, reason)
      runnable=False のとき reason に停止理由。
    """
    now = now or datetime.now()
    cfg = (settings or {}).get("config", {})

    # 除外日
    if now.strftime("%Y-%m-%d") in exclusion_dates:
        return (False, f"除外日のため停止中（{now.strftime('%Y-%m-%d')}）")

    # 曜日停止
    if cfg.get("day_restriction_enabled"):
        days = cfg.get("day_restriction_days") or []
        if now.weekday() in days:
            names = "月火水木金土日"
            return (False, f"停止曜日のため停止中（{names[now.weekday()]}曜）")

    # 時間帯停止
    if cfg.get("time_restriction_enabled"):
        start = _parse_hhmm(cfg.get("time_restriction_start", "20:00"), time(20, 0))
        end = _parse_hhmm(cfg.get("time_restriction_end", "08:00"), time(8, 0))
        if _in_wraparound(now.time(), start, end):
            return (False,
                    f"稼働時間外のため停止中（停止帯 {start.strftime('%H:%M')}〜{end.strftime('%H:%M')}）")

    return (True, "")
