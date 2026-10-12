"""
CustomTkinterを使用したメインGUIアプリケーション（是正版・UIは従来版に準拠）
"""
import json
import os
import sys
from datetime import time as dt_time

import customtkinter as ctk
from tkinter import filedialog, messagebox

import config
from gui_engine import GuiEngine, SETTINGS_FILENAME

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FIELDS = [
    ("company_name", "会社名"), ("department", "部署名"),
    ("full_name", "氏名（姓名）"), ("full_name_kana", "フリガナ（セイメイ）"),
    ("last_name", "姓"), ("first_name", "名"),
    ("last_name_kana", "セイ"), ("first_name_kana", "メイ"),
    ("email", "メールアドレス"), ("phone", "電話番号"),
    ("url", "企業URL"), ("postal_code", "郵便番号"),
    ("prefecture", "都道府県"), ("city", "市区町村"),
    ("address", "番地・建物名"), ("subject", "件名"),
]
DAYS = ["月", "火", "水", "木", "金", "土", "日"]
STATS = [("success", "成功"), ("failed", "失敗"), ("skipped", "スキップ")]


# ============================== 設定ファイル ==============================
def _settings_file_path():
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
        else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, SETTINGS_FILENAME)


def save_settings_file(engine):
    data = {"config": engine.config, "form_data": engine.form_data,
            "common_message": engine.common_message}
    try:
        p = _settings_file_path(); tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        pass


def load_settings_file(engine):
    try:
        p = _settings_file_path()
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            engine.set_config(data.get("config", {}))
            engine.set_form_data(data.get("form_data", {}))
            engine.set_common_message(data.get("common_message", ""))
    except Exception:
        pass


def _center(win, parent):
    try:
        win.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - win.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(x,0)}+{max(y,0)}")
    except Exception:
        pass


# ============================== 設定モーダル ==============================
class ConfigModal(ctk.CTkToplevel):
    """設定モーダルウィンドウ"""

    def __init__(self, parent, current_config):
        super().__init__(parent)
        self.title("設定")
        self.geometry("600x700")
        self.minsize(560, 640)
        self.config_data = dict(current_config or {})
        self.result = None
        self.transient(parent)
        self.grab_set()
        self._create_widgets()
        _center(self, parent)

    def _section(self, parent, title, desc):
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", pady=(14, 0))
        if desc:
            ctk.CTkLabel(parent, text=desc, text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w")

    def _create_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        frm = ctk.CTkScrollableFrame(self)
        frm.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))

        c = self.config_data
        self._section(frm, "ダイレクトモード", "対象URLを直接お問い合わせページとして扱う")
        self.direct_mode_var = ctk.BooleanVar(value=bool(c.get("direct_mode", False)))
        ctk.CTkCheckBox(frm, text="ダイレクトモードを有効化", variable=self.direct_mode_var).pack(anchor="w", pady=4)

        self._section(frm, "ヘッドレスモード", "Chromeをバックグラウンドで実行（ウィンドウを表示しない）")
        self.headless_var = ctk.BooleanVar(value=bool(c.get("headless", True)))
        ctk.CTkCheckBox(frm, text="ヘッドレスモードを有効化", variable=self.headless_var).pack(anchor="w", pady=4)

        self._section(frm, "並列処理", f"並列実行数（1-{config.MAX_PARALLEL_COUNT}）")
        self.parallel_var = ctk.IntVar(value=int(c.get("parallel_count", 1)))
        self.parallel_label = ctk.CTkLabel(frm, text=f"数: {self.parallel_var.get()}")
        self.parallel_label.pack(anchor="w")
        sl = ctk.CTkSlider(frm, from_=1, to=config.MAX_PARALLEL_COUNT,
                           number_of_steps=config.MAX_PARALLEL_COUNT - 1, variable=self.parallel_var,
                           command=lambda v: self.parallel_label.configure(text=f"数: {int(float(v))}"))
        sl.pack(fill="x", pady=4)

        self._section(frm, "重複防止", "以前に成功したURLをスキップする")
        self.duplicate_var = ctk.BooleanVar(value=bool(c.get("duplicate_check", False)))
        ctk.CTkCheckBox(frm, text="重複チェックを有効化", variable=self.duplicate_var).pack(anchor="w", pady=4)

        self._section(frm, "時間制限", "指定時間中は実行しない（例：21:00-07:00）")
        self.time_restriction_var = ctk.BooleanVar(value=bool(c.get("time_restriction_enabled", False)))
        ctk.CTkCheckBox(frm, text="時間制限を有効化", variable=self.time_restriction_var).pack(anchor="w", pady=4)
        tf = ctk.CTkFrame(frm, fg_color="transparent"); tf.pack(fill="x", pady=2)
        ctk.CTkLabel(tf, text="開始:").pack(side="left")
        self.time_start_entry = ctk.CTkEntry(tf, width=90, placeholder_text="HH:MM")
        self.time_start_entry.insert(0, c.get("time_restriction_start", "21:00")); self.time_start_entry.pack(side="left", padx=(4, 14))
        ctk.CTkLabel(tf, text="終了:").pack(side="left")
        self.time_end_entry = ctk.CTkEntry(tf, width=90, placeholder_text="HH:MM")
        self.time_end_entry.insert(0, c.get("time_restriction_end", "07:00")); self.time_end_entry.pack(side="left", padx=4)

        self._section(frm, "曜日制限", "指定した曜日は実行しない")
        self.day_restriction_var = ctk.BooleanVar(value=bool(c.get("day_restriction_enabled", False)))
        ctk.CTkCheckBox(frm, text="曜日制限を有効化", variable=self.day_restriction_var).pack(anchor="w", pady=4)
        df = ctk.CTkFrame(frm, fg_color="transparent"); df.pack(fill="x", pady=2)
        sel = set(c.get("day_restriction_days", []) or [])
        self.day_vars = []
        for i, name in enumerate(DAYS):
            v = ctk.BooleanVar(value=(i in sel))
            self.day_vars.append(v)
            ctk.CTkCheckBox(df, text=name, variable=v, width=48).pack(side="left", padx=2)

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        ctk.CTkButton(bf, text="保存", command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(bf, text="キャンセル", fg_color="gray", command=self.destroy).pack(side="left", padx=6)

    def _save(self):
        try:
            cfg = {
                "direct_mode": bool(self.direct_mode_var.get()),
                "headless": bool(self.headless_var.get()),
                "parallel_count": int(self.parallel_var.get()),
                "duplicate_check": bool(self.duplicate_var.get()),
                "time_restriction_enabled": bool(self.time_restriction_var.get()),
                "time_restriction_start": self.time_start_entry.get().strip() or "21:00",
                "time_restriction_end": self.time_end_entry.get().strip() or "07:00",
                "day_restriction_enabled": bool(self.day_restriction_var.get()),
                "day_restriction_days": [i for i, v in enumerate(self.day_vars) if v.get()],
            }
            # HH:MM 妥当性チェック
            for key in ("time_restriction_start", "time_restriction_end"):
                h, m = map(int, cfg[key].split(":"))
                dt_time(h, m)
            self.result = cfg
            self.destroy()
        except Exception as e:
            messagebox.showerror("エラー", f"無効な設定: {e}")


# ========================== メッセージ編集モーダル ==========================
class MessageEditorModal(ctk.CTkToplevel):
    """メッセージ編集モーダルウィンドウ"""

    def __init__(self, parent, form_data, common_message):
        super().__init__(parent)
        self.title("フォームデータとメッセージの編集")
        self.geometry("800x900")
        self.minsize(720, 760)
        self.form_data = dict(form_data or {})
        self.common_message = common_message or ""
        self.result = None
        self.transient(parent)
        self.grab_set()
        self._create_widgets()
        _center(self, parent)

    def _create_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        frm = ctk.CTkScrollableFrame(self)
        frm.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))

        ctk.CTkLabel(frm, text="会社情報", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", pady=(2, 8))
        self.entries = {}
        for key, label in FIELDS:
            row = ctk.CTkFrame(frm, fg_color="transparent"); row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row)
            e.insert(0, self.form_data.get(key, "")); e.pack(side="left", fill="x", expand=True)
            self.entries[key] = e

        ctk.CTkLabel(frm, text="共通メッセージテンプレート", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", pady=(14, 0))
        ctk.CTkLabel(frm, text=f"{config.COMPANY_TAG} タグを使用してサイトごとの会社名を置換できます",
                     text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.message_text = ctk.CTkTextbox(frm, height=260)
        self.message_text.pack(fill="both", expand=True, pady=6)
        self.message_text.insert("1.0", self.common_message)

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        ctk.CTkButton(bf, text="保存", command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(bf, text="キャンセル", fg_color="gray", command=self.destroy).pack(side="left", padx=6)

    def _save(self):
        fd = {k: e.get().strip() for k, e in self.entries.items()}
        if not fd.get("company_name"):
            messagebox.showerror("エラー", "会社名は必須です"); return
        if not fd.get("email"):
            messagebox.showerror("エラー", "メールアドレスは必須です"); return
        self.result = {"form_data": fd, "common_message": self.message_text.get("1.0", "end-1c")}
        self.destroy()


# ============================== メインウィンドウ ==============================
class ListersFormGUI(ctk.CTk):
    """メインアプリケーションウィンドウ"""

    def __init__(self):
        super().__init__()
        self.title("ListersForm - フォーム自動送信ツール")
        self.geometry("1400x900")

        self.engine = GuiEngine()
        self.engine.on_progress_update = self._on_progress_update
        self.engine.on_log_update = self._on_log_update
        self.engine.on_status_update = self._on_status_update
        load_settings_file(self.engine)
        self.csv_loaded = False

        self._create_widgets()
        for line in [
            "ListersFormへようこそ！",
            "対象CSV/Excelファイルを読み込み、フォームデータを設定して開始してください。",
            "【対応形式】",
            "  • 旧形式CSV: URL, オプションメッセージ",
            "  • 新形式CSV/Excel: URL, 第2URL, 会社名, 担当者, メッセージ",
            "  • Excel（.xlsx）: シート2に共通フォーム情報を配置可能",
            "=" * 80,
        ]:
            self._log(line)
        self._update_status_display()

    def _create_widgets(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._create_sidebar()
        self._create_main_area()

    def _create_sidebar(self):
        sb = ctk.CTkFrame(self, width=260, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(0, weight=1)
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(inner, text="ListersForm", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(inner, text="対象CSVファイル", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        self.csv_label = ctk.CTkLabel(inner, text="ファイル未読み込み", text_color="gray")
        self.csv_label.pack(anchor="w")
        ctk.CTkButton(inner, text="CSV読み込み", command=self._load_csv).pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(inner, text="進捗", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        self.progress_label = ctk.CTkLabel(inner, text="0 / 0")
        self.progress_label.pack(anchor="w")
        self.progress_bar = ctk.CTkProgressBar(inner); self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(inner, text="統計", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        self.stats_labels = {}
        for key, label in STATS:
            row = ctk.CTkFrame(inner, fg_color="transparent"); row.pack(fill="x")
            ctk.CTkLabel(row, text=label).pack(side="left")
            val = ctk.CTkLabel(row, text="0", anchor="e")
            val.pack(side="right")
            self.stats_labels[key] = val

        ctk.CTkLabel(inner, text="操作", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(12, 0))
        self.start_btn = ctk.CTkButton(inner, text="開始", fg_color="green", hover_color="darkgreen", command=self._start)
        self.start_btn.pack(fill="x", pady=3)
        self.pause_btn = ctk.CTkButton(inner, text="一時停止", state="disabled", command=self._pause)
        self.pause_btn.pack(fill="x", pady=3)
        self.stop_btn = ctk.CTkButton(inner, text="停止", fg_color="red", hover_color="darkred", state="disabled", command=self._stop)
        self.stop_btn.pack(fill="x", pady=3)
        self.skip_btn = ctk.CTkButton(inner, text="スキップ", state="disabled", command=self._skip)
        self.skip_btn.pack(fill="x", pady=3)

        ctk.CTkButton(inner, text="フォームデータとメッセージ編集", command=self._edit_message).pack(fill="x", pady=(12, 3))
        ctk.CTkButton(inner, text="設定", command=self._open_config).pack(fill="x", pady=3)

        self.status_label = ctk.CTkLabel(inner, text="状態: 待機中", text_color="gray")
        self.status_label.pack(side="bottom", anchor="w", pady=(12, 0))

    def _create_main_area(self):
        main = ctk.CTkFrame(self)
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 0))
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        ctk.CTkLabel(header, text="実行ログ", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="ログクリア", width=100, command=self._clear_log).pack(side="right")

        self.log_text = ctk.CTkTextbox(main)
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))

    # ---- 操作 ----
    def _load_csv(self):
        path = filedialog.askopenfilename(
            title="対象CSV/Excelファイルを選択",
            filetypes=[("対象リスト", "*.csv *.xlsx *.xlsm"), ("すべて", "*.*")])
        if not path:
            return
        try:
            targets = self.engine.load_targets(path)
            self.csv_loaded = True
            self.csv_label.configure(text=f"{len(targets)}件のデータを読み込み", text_color="white")
            self._log(f"✓ ファイルから{len(targets)}件のデータを読み込みました")
        except Exception as e:
            self.csv_loaded = False
            self._log(f"✗ ファイルの読み込みに失敗: {e}")
            messagebox.showerror("エラー", f"読み込み失敗: {e}")

    def _start(self):
        if not self.csv_loaded:
            messagebox.showwarning("警告", "まず対象CSVファイルを読み込んでください"); return
        if not self.engine.form_data.get("company_name"):
            if messagebox.askyesno("フォームデータ未設定", "フォームデータが設定されていません。今すぐ設定しますか？"):
                self._edit_message()
            return
        try:
            self.engine.start()
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal", text="一時停止")
            self.stop_btn.configure(state="normal")
            self.skip_btn.configure(state="normal")
            self._log("▶ 自動化を開始しました")
        except Exception:
            messagebox.showerror("エラー", "自動化の開始に失敗しました")

    def _pause(self):
        if self.engine.get_status()["is_paused"]:
            self.engine.resume()
            self.pause_btn.configure(text="一時停止")
            self._log("▶ 再開しました")
        else:
            self.engine.pause()
            self.pause_btn.configure(text="再開")
            self._log("⏸ 一時停止しました")

    def _stop(self):
        self.engine.stop()
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="一時停止")
        self.stop_btn.configure(state="disabled")
        self.skip_btn.configure(state="disabled")
        self._log("■ 停止中...")

    def _skip(self):
        if self.engine.get_status()["is_running"]:
            self.engine.skip_current()
            self._log("⏭ 現在のサイトのスキップをリクエストしました")

    def _edit_message(self):
        modal = MessageEditorModal(self, self.engine.form_data, self.engine.common_message)
        self.wait_window(modal)
        if modal.result:
            self.engine.set_form_data(modal.result["form_data"])
            self.engine.set_common_message(modal.result["common_message"])
            save_settings_file(self.engine)
            self._log("✓ フォームデータとメッセージを更新しました")
            messagebox.showinfo("成功", "フォームデータとメッセージを正常に更新しました")

    def _open_config(self):
        modal = ConfigModal(self, self.engine.config)
        self.wait_window(modal)
        if modal.result:
            self.engine.set_config(modal.result)
            save_settings_file(self.engine)
            self._log("✓ 設定を更新しました")
            messagebox.showinfo("成功", "設定を正常に更新しました")

    def _clear_log(self):
        self.log_text.delete("1.0", "end")
        self._log("ログをクリアしました")

    def _log(self, message):
        try:
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
        except Exception:
            pass

    # ---- エンジンコールバック ----
    def _on_log_update(self, message):
        self.after(0, lambda: self._log(message))

    def _on_progress_update(self, current, total):
        def update():
            self.progress_label.configure(text=f"{current} / {total}")
            self.progress_bar.set((current / total) if total else 0)
        self.after(0, update)

    def _on_status_update(self, status):
        self.after(0, lambda: self.status_label.configure(text=f"状態: {status}"))

    def _update_status_display(self):
        try:
            st = self.engine.get_status()
            stats = st["statistics"]
            for key, _ in STATS:
                self.stats_labels[key].configure(text=str(stats.get(key, 0)))
            if st["is_running"]:
                if self.start_btn.cget("state") != "disabled":
                    self.start_btn.configure(state="disabled")
                    self.pause_btn.configure(state="normal")
                    self.stop_btn.configure(state="normal")
                    self.skip_btn.configure(state="normal")
            else:
                if self.start_btn.cget("state") == "disabled":
                    self.start_btn.configure(state="normal")
                    self.pause_btn.configure(state="disabled", text="一時停止")
                    self.stop_btn.configure(state="disabled")
                    self.skip_btn.configure(state="disabled")
        except Exception:
            pass
        self.after(600, self._update_status_display)


def main():
    """メインエントリーポイント"""
    app = ListersFormGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
