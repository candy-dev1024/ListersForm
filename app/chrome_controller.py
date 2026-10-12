"""
Chrome / Selenium 制御層。

v11 の Chrome 起動不安定（56/1572 が「Chrome起動に失敗」）への対策として、
  1) Selenium Manager による自動ドライバ解決（Selenium 4.6+ 標準）
  2) 失敗時 webdriver-manager へフォールバック
  3) 例外は確実に捕捉し、必ず quit() する
を実装する。
"""
from __future__ import annotations

import time as _time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException, TimeoutException, StaleElementReferenceException,
    ElementNotInteractableException, NoSuchElementException,
)

import config


class ChromeController:
    def __init__(self, headless: bool = True,
                 page_load_timeout: int = config.PAGE_LOAD_TIMEOUT,
                 element_wait: int = config.ELEMENT_WAIT_TIMEOUT,
                 use_js_fallback: bool = True,
                 logger=None):
        self.headless = headless
        self.page_load_timeout = page_load_timeout
        self.element_wait = element_wait
        self.use_js_fallback = use_js_fallback
        self.driver = None
        self._log = logger or (lambda m: None)

    # ------------------------------------------------------------------ start
    def _build_options(self) -> Options:
        o = Options()
        if self.headless:
            o.add_argument("--headless=new")
        o.add_argument("--no-sandbox")
        o.add_argument("--disable-dev-shm-usage")
        o.add_argument("--disable-gpu")
        o.add_argument("--window-size=1280,1696")
        o.add_argument("--disable-blink-features=AutomationControlled")
        o.add_argument("--lang=ja-JP")
        o.add_argument("--log-level=3")
        o.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        o.add_experimental_option("useAutomationExtension", False)
        o.page_load_strategy = "eager"  # DOMContentLoaded で進む（低速サイト対策）
        return o

    def start(self) -> bool:
        # 1) Selenium Manager (標準)
        try:
            self.driver = webdriver.Chrome(options=self._build_options())
        except Exception as e1:
            self._log(f"[CHROME_INIT] 標準初期化に失敗、webdriver-manager を試行: {e1}")
            # 2) webdriver-manager フォールバック
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=self._build_options())
            except Exception as e2:
                self._log(f"[CHROME_INIT] webdriver-manager も失敗: {e2}")
                self.driver = None
                return False
        try:
            self.driver.set_page_load_timeout(self.page_load_timeout)
            self.driver.set_script_timeout(self.page_load_timeout)
        except Exception:
            pass
        return True

    def stop(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None

    # --------------------------------------------------------------- navigate
    def navigate(self, url: str, retries: int = config.MAX_RETRIES) -> bool:
        last = None
        for attempt in range(retries + 1):
            try:
                self.driver.get(url)
                return True
            except TimeoutException:
                # eager 戦略でも時間切れ → 部分ロードで続行
                self._log(f"[NAVIGATE] タイムアウト（部分ロードで続行）: {url}")
                return True
            except WebDriverException as e:
                last = e
                self._log(f"[NAVIGATE] 失敗({attempt+1}/{retries+1}): {str(e)[:120]}")
                _time.sleep(1.0)
        if last:
            self._log(f"[NAVIGATE] 最終的に失敗: {url}")
        return False

    def current_url(self) -> str:
        try:
            return self.driver.current_url or ""
        except Exception:
            return ""

    def page_text(self) -> str:
        try:
            return self.driver.find_element(By.TAG_NAME, "body").text or ""
        except Exception:
            try:
                return self.driver.execute_script("return document.body.innerText;") or ""
            except Exception:
                return ""

    def page_source(self) -> str:
        try:
            return self.driver.page_source or ""
        except Exception:
            return ""

    # ------------------------------------------------------------- find/fill
    def find_form_elements(self) -> list:
        els = []
        try:
            els += self.driver.find_elements(By.CSS_SELECTOR,
                                             "input, textarea, select, [contenteditable='true']")
        except Exception:
            pass
        # iframe 内も1階層だけ確認（Google reCAPTCHA等は除外されるのでフォームのみ）
        return [e for e in els if self._is_usable(e)]

    def _is_usable(self, el) -> bool:
        try:
            if not el.is_displayed():
                return False
            t = (el.get_attribute("type") or "").lower()
            if t in ("hidden", "submit", "button", "image", "reset"):
                return False
            return True
        except Exception:
            return False

    def fill_input(self, el, value: str) -> bool:
        if value is None:
            return False
        try:
            tag = (el.tag_name or "").lower()
            editable = el.get_attribute("contenteditable")
            if editable == "true":
                self.driver.execute_script(
                    "arguments[0].innerText = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));",
                    el, value)
                return True
            try:
                el.clear()
            except Exception:
                pass
            el.send_keys(value)
            # 一部SPAは input イベントを要求
            try:
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", el)
            except Exception:
                pass
            return True
        except (ElementNotInteractableException, StaleElementReferenceException):
            if self.use_js_fallback:
                try:
                    self.driver.execute_script(
                        "arguments[0].value = arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                        "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                        el, value)
                    return True
                except Exception:
                    return False
            return False
        except Exception:
            return False

    def select_dropdown(self, el, preferences: list[str]) -> tuple[bool, str]:
        """優先リストに合う option を選ぶ。無ければ (False, '') を返す（呼び出し側で判断）。"""
        try:
            sel = Select(el)
            options = sel.options
            texts = [(o.text or "").strip() for o in options]
            # 優先語に前方/部分一致
            for pref in preferences:
                for i, t in enumerate(texts):
                    if pref and pref in t:
                        try:
                            sel.select_by_index(i)
                            return (True, t)
                        except Exception:
                            continue
            return (False, "")
        except Exception:
            return (False, "")

    def select_first_valid(self, el) -> tuple[bool, str]:
        """先頭の「選択してください」等を避けて最初の有効 option を選ぶ。"""
        try:
            sel = Select(el)
            placeholders = ("選択", "選んで", "please", "select", "---", "--", "")
            for o in sel.options:
                val = (o.get_attribute("value") or "").strip()
                txt = (o.text or "").strip()
                if not val and not txt:
                    continue
                if any(p and p in txt.lower() for p in ("選択してください", "選んでください")):
                    continue
                if txt.lower() in placeholders or val == "":
                    continue
                sel.select_by_visible_text(o.text)
                return (True, txt)
        except Exception:
            pass
        return (False, "")

    def check_checkbox(self, el) -> bool:
        try:
            if not el.is_selected():
                try:
                    el.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False

    def click(self, el) -> bool:
        try:
            el.click()
            return True
        except Exception:
            if self.use_js_fallback:
                try:
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
                except Exception:
                    return False
            return False

    def find_clickable_by_texts(self, texts: list[str]) -> list:
        """ボタン/リンク/submit で、テキストまたはvalueが texts のいずれかに一致する要素。"""
        out = []
        try:
            cands = self.driver.find_elements(
                By.CSS_SELECTOR,
                "button, a, input[type='submit'], input[type='button'], "
                "[role='button'], .btn, .button")
        except Exception:
            cands = []
        for c in cands:
            try:
                if not c.is_displayed():
                    continue
                label = (c.text or "").strip() or (c.get_attribute("value") or "").strip()
                if not label:
                    label = (c.get_attribute("aria-label") or "").strip()
                if not label:
                    continue
                if any(t and t in label for t in texts):
                    out.append(c)
            except Exception:
                continue
        return out

    def find_elements_by_text(self, texts: list[str]) -> list:
        out = []
        try:
            all_els = self.driver.find_elements(By.XPATH, "//*[normalize-space(text())]")
        except Exception:
            all_els = []
        for e in all_els:
            try:
                tx = (e.text or "").strip()
                if tx and any(t and t in tx for t in texts):
                    out.append(e)
            except Exception:
                continue
        return out

    # ----------------------------------------------------------- CAPTCHA/等
    def is_captcha_present(self) -> bool:
        """表示されている（＝実際に突破が必要な）CAPTCHAのみ True。"""
        # iframe ベース（reCAPTCHA/hCaptcha/Turnstile）
        try:
            frames = self.driver.find_elements(
                By.CSS_SELECTOR,
                "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], "
                "iframe[src*='turnstile'], iframe[title*='recaptcha']")
            for fr in frames:
                try:
                    if fr.is_displayed() and fr.size.get("height", 0) > 10:
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        # 明示的ウィジェット
        try:
            widgets = self.driver.find_elements(
                By.CSS_SELECTOR, ".g-recaptcha, .h-captcha, .cf-turnstile")
            for w in widgets:
                try:
                    if w.is_displayed():
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def sleep(self, sec: float):
        _time.sleep(sec)
