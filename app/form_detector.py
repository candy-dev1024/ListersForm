"""
フォーム検出・入力・送信判定。

【是正の核心】送信判定（_evaluate_receipt）:
  旧実装の「エラーが無ければ成功」「汎用文言で成功」「URL文字列一致で成功」を廃止。
  受付確認(確信度=高)は次のいずれかに限定（クライアント合意）:
    (A) 受付番号/問い合わせ番号を検出
    (B) 送信前後でURLが変化し、完了ページパターンに遷移、かつ入力フォームが消失
    (C) 明確な完了文言を検出し、かつ入力フォームが消失
  それ以外（文言のみ／エラー非表示のみ／URL文字列一致のみ 等）は
  すべて「送信処理完了（推定）」に格下げし、確定成功としない。

送信なし検証モード(dry_run)では、送信ボタン操作・JS送信を一切行わず、
入力可否・必須充足・バリデーション制約のみで送信成立可否を判定する。
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, urljoin

from selenium.webdriver.common.by import By

import config
from models import SubmitOutcome

_LABEL_JS = r"""
function labelFor(el){
  try{
    if(el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    if(el.id){var l=document.querySelector('label[for="'+String(el.id).replace(/"/g,'')+'"]'); if(l&&l.innerText) return l.innerText;}
    var lab=el.closest('label'); if(lab&&lab.innerText) return lab.innerText;
    var cell=el.closest('td,dd'); if(cell){var row=cell.closest('tr,dl,div'); if(row){var th=row.querySelector('th,dt,legend,label'); if(th&&th.innerText) return th.innerText;}}
    var prev=el.previousElementSibling, hops=0;
    while(prev&&hops<3){ if(prev.innerText&&prev.innerText.trim()) return prev.innerText; prev=prev.previousElementSibling; hops++; }
    if(el.placeholder) return el.placeholder;
  }catch(e){}
  return '';
}
return labelFor(arguments[0]);
"""

# field_key を長い順に並べたフラットなパターン表（最長一致優先で誤識別を抑える）
_FLAT_PATTERNS = sorted(
    [(len(p), key, p.lower()) for key, pats in config.FIELD_PATTERNS.items() for p in pats],
    key=lambda x: x[0], reverse=True,
)

# post-submit のバリデーション検出に使う「決定的」な語（ラベルの「必須」等は除外）
_DECISIVE_VALIDATION = [
    "入力してください", "正しく入力", "入力内容に誤り", "入力エラー", "未入力です",
    "形式が正しくあり", "必須です", "入力されていません", "を入力して",
    "required", "invalid", "please enter", "please fill", "is required",
]


def _norm_url(u: str) -> str:
    try:
        p = urlparse(u)
        return (p.netloc + p.path).rstrip("/").lower()
    except Exception:
        return (u or "").rstrip("/").lower()


class SkipSite(Exception):
    """サイトごとスキップすべき状況（その他なし等）。"""
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class FormDetector:
    def __init__(self, chrome, form_data: dict, settings: dict | None = None, logger=None):
        self.c = chrome
        self.data = form_data or {}
        self.settings = settings or {}
        self._log = logger or (lambda m: None)
        cfg = self.settings.get("config", {})
        self.skip_if_no_sonota = cfg.get("skip_if_no_sonota", True)
        self.filled_types: set[str] = set()
        self.missing_required: list[str] = []
        self.char_limit_hit = False
        self._pre_text = ""  # 送信前のページ文言（受付番号の「新規表示」判定に使用）

    # ================================================= 問い合わせページ検出
    def find_inquiry_page(self, start_url: str) -> tuple[bool, str, str]:
        cfg = self.settings.get("config", {})
        if cfg.get("direct_mode"):
            if not self.c.navigate(start_url):
                return (False, "", config.REASON_ENVIRONMENT_NETWORK_FAILED)
            return (True, start_url, "")

        base = self._origin(start_url)

        # Step1: 直接URLパターン
        for pat in config.CONTACT_URL_PATTERNS[:config.MAX_DIRECT_INQUIRY_URL_ATTEMPTS]:
            url = urljoin(base + "/", pat.lstrip("/"))
            if self.c.navigate(url) and self._has_contact_form():
                return (True, self.c.current_url(), "")

        # Step2: トップページ → フォーム or リンク探索
        if not self.c.navigate(start_url):
            return (False, "", config.REASON_ENVIRONMENT_NETWORK_FAILED)
        if self._is_google_form(self.c.current_url()):
            return (True, self.c.current_url(), "")
        if self._has_contact_form():
            return (True, self.c.current_url(), "")

        for href in self._contact_links()[:config.MAX_INQUIRY_LINK_ATTEMPTS]:
            if self.c.navigate(href) and self._has_contact_form():
                return (True, self.c.current_url(), "")

        return (False, "", config.REASON_INQUIRY_NOT_FOUND)

    def _origin(self, url: str) -> str:
        try:
            p = urlparse(url)
            return f"{p.scheme or 'https'}://{p.netloc}"
        except Exception:
            return url.rstrip("/")

    def _is_google_form(self, url: str) -> bool:
        return "docs.google.com/forms" in (url or "").lower()

    def _contact_links(self) -> list[str]:
        out = []
        try:
            anchors = self.c.driver.find_elements(By.TAG_NAME, "a")
        except Exception:
            anchors = []
        for a in anchors:
            try:
                txt = (a.text or "").strip()
                href = a.get_attribute("href") or ""
                if not href:
                    continue
                hay = (txt + " " + href).lower()
                if any(k.lower() in hay for k in config.CONTACT_KEYWORDS):
                    if href not in out:
                        out.append(href)
            except Exception:
                continue
        return out

    def _has_contact_form(self) -> bool:
        els = self.c.find_form_elements()
        if not els:
            return False
        has_textarea = False
        has_email = False
        text_inputs = 0
        for e in els:
            try:
                tag = (e.tag_name or "").lower()
                typ = (e.get_attribute("type") or "").lower()
                if tag == "textarea":
                    has_textarea = True
                elif typ == "email":
                    has_email = True
                elif tag == "input" and typ in ("", "text", "tel", "url"):
                    text_inputs += 1
            except Exception:
                continue
        return has_textarea or has_email or text_inputs >= 2

    # ===================================================== NG / CAPTCHA
    def detect_ng_phrases(self) -> tuple[bool, str]:
        text = self.c.page_text()
        for ph in config.NG_PHRASES:
            if ph in text:
                return (True, ph)
        return (False, "")

    def is_captcha_present(self) -> bool:
        return self.c.is_captcha_present()

    # ====================================================== フィールド識別
    def _label_text(self, el) -> str:
        try:
            return self.c.driver.execute_script(_LABEL_JS, el) or ""
        except Exception:
            return ""

    def _meta(self, el) -> str:
        parts = []
        for attr in ("name", "id", "placeholder", "aria-label", "title", "class"):
            try:
                v = el.get_attribute(attr)
            except Exception:
                v = None
            if v:
                parts.append(str(v))
        parts.append(self._label_text(el))
        return " ".join(parts)

    def identify_field_type(self, el, meta: str | None = None) -> str | None:
        meta = (meta if meta is not None else self._meta(el)).lower()
        if not meta.strip():
            # email/tel は type から
            try:
                t = (el.get_attribute("type") or "").lower()
                if t in ("email", "tel", "url"):
                    return {"email": "email", "tel": "phone", "url": "url"}[t]
            except Exception:
                pass
            return None
        for _, key, pat in _FLAT_PATTERNS:
            if pat in meta:
                return key
        # type ヒント
        try:
            t = (el.get_attribute("type") or "").lower()
            if t == "email":
                return "email"
            if t == "tel":
                return "phone"
        except Exception:
            pass
        return None

    def _is_required(self, el, meta: str | None = None) -> bool:
        try:
            if el.get_attribute("required") is not None and el.get_attribute("required") not in ("false",):
                return True
            if (el.get_attribute("aria-required") or "").lower() == "true":
                return True
        except Exception:
            pass
        meta = (meta if meta is not None else self._meta(el))
        if any(k in meta for k in ("必須", "required", "※")):
            return True
        if "*" in meta and ("req" in meta.lower() or "必" in meta):
            return True
        return False

    # ========================================================= フォーム入力
    def fill_form(self, message: str) -> tuple[bool, str]:
        """returns (ok, reason). ok=False かつ reason がスキップ系のこともある。"""
        self.filled_types.clear()
        self.missing_required = []
        self.char_limit_hit = False

        try:
            elements = self.c.find_form_elements()
        except Exception as e:
            return (False, f"{config.REASON_UNKNOWN_ERROR}: {e}")

        if not elements:
            return (False, config.REASON_INQUIRY_NOT_FOUND)

        radios_done: set[str] = set()

        for el in list(elements):
            try:
                tag = (el.tag_name or "").lower()
                typ = (el.get_attribute("type") or "").lower()
                meta = self._meta(el)
                ftype = self.identify_field_type(el, meta)
                required = self._is_required(el, meta)

                if tag == "select":
                    self._fill_select(el, ftype, required)
                    continue
                if typ == "checkbox":
                    # プライバシー/同意・必須チェックボックスのみ
                    if any(k.lower() in meta.lower() for k in config.PRIVACY_KEYWORDS) or required or "必須" in meta:
                        self.c.check_checkbox(el)
                    continue
                if typ == "radio":
                    name = el.get_attribute("name") or id(el)
                    if name in radios_done:
                        continue
                    if self._fill_radio_group(el, meta, ftype):
                        radios_done.add(name)
                    continue

                # text / textarea / email / tel / url / contenteditable
                value = self._value_for(ftype, message, el, meta)
                if value is None:
                    if required and ftype not in self.filled_types:
                        # 必須だが不明 → 可能なら汎用値（氏名/メッセージ）で充足を試みる
                        fallback = message if tag == "textarea" else self.data.get("full_name")
                        if fallback:
                            if self.c.fill_input(el, fallback):
                                self.missing_required_discard(ftype)
                    continue

                # 文字数制限チェック（message）
                if ftype == "message":
                    maxlen = self._maxlength(el)
                    if maxlen and len(value) > maxlen:
                        self.char_limit_hit = True
                        value = value[:maxlen]

                if self.c.fill_input(el, value) and ftype:
                    self.filled_types.add(ftype)
            except SkipSite:
                raise  # サイトスキップ（「その他」なし等）は飲み込まず伝播させる
            except Exception as e:
                self._log(f"[FILL] 要素処理エラー: {str(e)[:80]}")
                continue

        # 必須チェックボックス（個人情報同意含む）を最終確認
        self._check_required_checkboxes()

        # 必須充足の検証
        for key in config.CRITICAL_REQUIRED_FIELDS:
            if key not in self.filled_types and self.data.get(key):
                self.missing_required.append(key)
        if self.missing_required:
            return (False, f"{config.REASON_REQUIRED_FIELDS_MISSING}: {', '.join(self.missing_required)}")

        return (True, "")

    def missing_required_discard(self, ftype):
        if ftype in self.missing_required:
            self.missing_required.remove(ftype)

    def _value_for(self, ftype, message, el, meta):
        if ftype == "message":
            return message
        if ftype in ("inquiry_type", "contact_method", "source"):
            return None  # select/radio で処理
        if ftype and self.data.get(ftype):
            return self.data.get(ftype)
        return None

    def _maxlength(self, el):
        try:
            m = el.get_attribute("maxlength")
            if m and m.isdigit() and int(m) > 0:
                return int(m)
        except Exception:
            pass
        return None

    def _fill_select(self, el, ftype, required):
        if ftype == "contact_method":
            ok, _ = self.c.select_dropdown(el, config.CONTACT_METHOD_PREFERENCE)
            if not ok and required:
                self.c.select_first_valid(el)
            return
        if ftype == "source":
            ok, _ = self.c.select_dropdown(el, config.SOURCE_PREFERENCE)
            if not ok and required:
                self.c.select_first_valid(el)
            return
        # 保有データで選べる select（都道府県など）は保存値で選択を試みる
        if ftype and ftype != "inquiry_type" and self.data.get(ftype):
            ok, _ = self.c.select_dropdown(el, [self.data.get(ftype)])
            if ok:
                return
        # inquiry_type もしくは一般の必須 select
        if ftype == "inquiry_type" or required:
            ok, _ = self.c.select_dropdown(el, config.INQUIRY_TYPE_PREFERENCE)
            if ok:
                return
            # 「その他」等が無い必須ドロップダウン
            if required and self.skip_if_no_sonota:
                raise SkipSite(config.REASON_NO_SONOTA)
            self.c.select_first_valid(el)

    def _fill_radio_group(self, el, meta, ftype) -> bool:
        try:
            name = el.get_attribute("name")
            group = self.c.driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{name}']") if name else [el]
        except Exception:
            group = [el]
        # 連絡方法=メール / 同意=する を優先
        prefer = config.CONTACT_METHOD_PREFERENCE + ["同意する", "承諾する", "はい", "agree"]
        for r in group:
            try:
                lbl = self._label_text(r) + " " + (r.get_attribute("value") or "")
                if any(p in lbl for p in prefer):
                    self.c.check_checkbox(r)
                    return True
            except Exception:
                continue
        # 必須そうなら先頭を選択
        try:
            self.c.check_checkbox(group[0])
            return True
        except Exception:
            return False

    def _check_required_checkboxes(self):
        try:
            boxes = self.c.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        except Exception:
            boxes = []
        for b in boxes:
            try:
                if not b.is_displayed() or b.is_selected():
                    continue
                meta = self._meta(b)
                if any(k.lower() in meta.lower() for k in config.PRIVACY_KEYWORDS) or self._is_required(b, meta):
                    self.c.check_checkbox(b)
            except Exception:
                continue

    # ============================================================ 送信/判定
    def submit_form(self, dry_run: bool = False) -> SubmitOutcome:
        url_before = self.c.current_url()

        if dry_run:
            return self._dry_run_eval(url_before)

        # 送信前の画面文言を控える（受付番号が「送信後に新規表示」されたかの判定用）
        self._pre_text = self.c.page_text()

        max_steps = 4
        steps = 0
        while steps < max_steps:
            submit_btns = self.c.find_clickable_by_texts(config.SUBMIT_BUTTON_KEYWORDS)
            if submit_btns:
                self.c.click(submit_btns[0])
                steps += 1
                self.c.sleep(config.POST_SUBMIT_WAIT)
                return self._after_submit(url_before, steps)

            confirm_btns = self.c.find_clickable_by_texts(config.CONFIRM_BUTTON_KEYWORDS)
            if confirm_btns:
                self.c.click(confirm_btns[0])
                steps += 1
                self.c.sleep(config.POST_SUBMIT_WAIT)
                continue

            break

        # 送信/確認ボタンが見つからない → 最終手段で JS 送信（ただし成功は確証でのみ判定）
        if self.c.use_js_fallback and steps == 0:
            if self._js_submit():
                steps += 1
                self.c.sleep(config.POST_SUBMIT_WAIT)
                out = self._evaluate_receipt(url_before, steps)
                if out.status == config.RESULT_RECEIPT_CONFIRMED:
                    return out
                # 確証が無ければ「JS送信のみ（推定）」に格下げ
                out.status = config.RESULT_SUBMIT_PRESUMED
                out.evidence_type = config.EVIDENCE_PRESUMED_JS
                out.confidence = config.CONFIDENCE_LOW
                out.reason = "JavaScript送信（確証なし）"
                return out

        if steps >= max_steps:
            return SubmitOutcome(status=config.RESULT_FAILED, reason=config.REASON_MAX_STEPS,
                                 url_before=url_before, url_after=self.c.current_url())
        return SubmitOutcome(status=config.RESULT_FAILED, reason=config.REASON_SUBMIT_BUTTON_NOT_FOUND,
                             url_before=url_before, url_after=self.c.current_url())

    def _js_submit(self) -> bool:
        try:
            return bool(self.c.driver.execute_script(
                "var f=document.querySelector('form'); if(f){f.submit(); return true;} return false;"))
        except Exception:
            return False

    def _after_submit(self, url_before: str, steps: int) -> SubmitOutcome:
        # 失敗検出が最優先（偽陽性防止）
        if self.c.is_captcha_present():
            return SubmitOutcome(status=config.RESULT_FAILED, reason=config.REASON_CAPTCHA_DETECTED,
                                 url_before=url_before, url_after=self.c.current_url(), steps=steps)
        verr = self.detect_validation_error()
        if verr:
            return SubmitOutcome(status=config.RESULT_FAILED, reason=verr,
                                 url_before=url_before, url_after=self.c.current_url(),
                                 form_remained="残存", steps=steps)
        # 受付確認の評価（是正ロジック）
        return self._evaluate_receipt(url_before, steps)

    def detect_validation_error(self) -> str | None:
        text = self.c.page_text()
        low = text.lower()
        form_present = self._form_present()
        # URL記載不可
        for k in config.URL_REJECTION_KEYWORDS:
            if k in text:
                return config.REASON_URL_REJECTED
        # 文字数制限
        if self.char_limit_hit:
            return config.REASON_CHARACTER_LIMIT
        for k in config.CHAR_LIMIT_KEYWORDS:
            if k.lower() in low and form_present:
                return config.REASON_CHARACTER_LIMIT
        # 一般バリデーション（決定的な語＋フォーム残存）
        if form_present:
            for k in _DECISIVE_VALIDATION:
                if k.lower() in low:
                    return config.REASON_VALIDATION_ERROR
        return None

    def _form_present(self) -> bool:
        """送信後に入力フォーム（textarea/email/複数text）がまだ存在するか。"""
        try:
            els = self.c.find_form_elements()
        except Exception:
            return False
        has_textarea = any((e.tag_name or "").lower() == "textarea" for e in els)
        has_email = False
        text_inputs = 0
        for e in els:
            try:
                typ = (e.get_attribute("type") or "").lower()
                if typ == "email":
                    has_email = True
                elif typ in ("", "text", "tel", "url"):
                    text_inputs += 1
            except Exception:
                continue
        return has_textarea or has_email or text_inputs >= 2

    def _evaluate_receipt(self, url_before: str, steps: int) -> SubmitOutcome:
        """【是正ロジック】受付確認は客観的証跡がある場合のみ。"""
        url_after = self.c.current_url()
        text = self.c.page_text()
        form_present = self._form_present()
        form_remained = "残存" if form_present else "消失"
        url_changed = _norm_url(url_before) != _norm_url(url_after)
        url_completion = any(p.lower() in (url_after or "").lower() for p in config.COMPLETION_URL_PATTERNS)
        # 遷移先が案内／配信停止／保証等のページの場合は受付確認として扱わない
        non_completion = any(k.lower() in (url_after or "").lower() for k in config.NON_COMPLETION_URL_KEYWORDS)

        # (A) 受付番号（送信後に新規表示された『ラベル＋実番号』に限る。案内/配信停止等の遷移先は除外）
        receipt = self._find_new_receipt(self._pre_text, text)
        if receipt and not non_completion:
            return SubmitOutcome(
                status=config.RESULT_RECEIPT_CONFIRMED, reason="受付確認（送信後に新規表示された受付番号を検出）",
                evidence_type=config.EVIDENCE_RECEIPT_NUMBER, evidence_detail=receipt,
                url_before=url_before, url_after=url_after, form_remained=form_remained,
                confidence=config.CONFIDENCE_HIGH, steps=steps)

        strong = self._first_phrase(text, config.STRONG_SUCCESS_PHRASES)

        # (B) URL遷移（完了ページ）＋フォーム消失（案内/配信停止等の遷移先は除外）
        if url_changed and url_completion and not form_present and not non_completion:
            return SubmitOutcome(
                status=config.RESULT_RECEIPT_CONFIRMED, reason="受付確認（完了URLへ遷移＋フォーム消失）",
                evidence_type=config.EVIDENCE_URL_TRANSITION,
                evidence_detail=url_after, url_before=url_before, url_after=url_after,
                form_remained=form_remained, confidence=config.CONFIDENCE_HIGH, steps=steps)

        # (C) 明確な完了文言＋フォーム消失（案内/配信停止等の遷移先は除外）
        if strong and not form_present and not non_completion:
            return SubmitOutcome(
                status=config.RESULT_RECEIPT_CONFIRMED, reason="受付確認（完了文言＋フォーム消失）",
                evidence_type=config.EVIDENCE_COMPLETION_MSG, evidence_detail=strong,
                url_before=url_before, url_after=url_after, form_remained=form_remained,
                confidence=config.CONFIDENCE_HIGH, steps=steps)

        # --- ここから下は「受付確認としない」（送信処理完了（推定）） ---
        weak = self._first_phrase(text, config.WEAK_SUCCESS_PHRASES)

        if url_changed and url_completion and form_present:
            et, detail, conf = config.EVIDENCE_PRESUMED_URL_ONLY, url_after, config.CONFIDENCE_LOW
        elif strong and form_present:
            et, detail, conf = config.EVIDENCE_PRESUMED_PHRASE_ONLY, strong, config.CONFIDENCE_MEDIUM
        elif url_changed and not form_present and weak:
            et, detail, conf = config.EVIDENCE_WEAK_COMBINED, weak, config.CONFIDENCE_MEDIUM
        elif weak:
            et, detail, conf = config.EVIDENCE_PRESUMED_PHRASE_ONLY, weak, config.CONFIDENCE_LOW
        else:
            et, detail, conf = config.EVIDENCE_PRESUMED_NO_ERROR, "", config.CONFIDENCE_LOW

        return SubmitOutcome(
            status=config.RESULT_SUBMIT_PRESUMED, reason="送信処理は完了（受付確認の証跡なし）",
            evidence_type=et, evidence_detail=detail,
            url_before=url_before, url_after=url_after, form_remained=form_remained,
            confidence=conf, steps=steps)

    def _find_new_receipt(self, pre_text: str, post_text: str) -> str:
        """送信後(post)に『新規表示された受付番号（ラベル＋実番号）』のみを返す。

        受付確認の根拠にできる条件（すべて満たす場合のみ）:
          1) ラベル（受付番号・問い合わせ番号 等）の直後に識別子があること
          2) その識別子が実際の番号であること（数字を1文字以上含む）
             … 案内文中の「受付番号をお知らせします」等の“語のみ”は不可
          3) 送信前(pre)には存在せず、送信後(post)に新規表示されたこと
        条件を満たすものが無ければ空文字（＝受付確認の根拠にしない）。
        """
        pre = pre_text or ""
        for m in re.finditer(config.RECEIPT_NUMBER_REGEX, post_text, re.IGNORECASE):
            ident = m.group(1) or ""
            if not any(ch.isdigit() for ch in ident):
                continue  # 実際の識別番号（数字）が無い＝語のみ → 根拠にしない
            full = m.group(0).replace("\n", " ").strip()
            if full and full in pre:
                continue  # 送信前から表示されている → 新規でない
            return full[:60]
        return ""

    def _first_phrase(self, text: str, phrases: list[str]) -> str:
        low = text.lower()
        for p in phrases:
            if p.lower() in low:
                return p
        return ""

    # ============================================================ dry-run
    def _dry_run_eval(self, url_before: str) -> SubmitOutcome:
        """送信操作を一切行わず、送信成立可否のみ判定（929検証用）。"""
        # 必須充足（fill_form 実行済み前提）
        if self.missing_required:
            return SubmitOutcome(
                status=config.RESULT_FAILED,
                reason=f"{config.REASON_DRYRUN_WOULD_FAIL}／{config.REASON_REQUIRED_FIELDS_MISSING}: "
                       f"{', '.join(self.missing_required)}",
                url_before=url_before, url_after=url_before, form_remained="残存")
        # 文字数制限
        if self.char_limit_hit:
            return SubmitOutcome(
                status=config.RESULT_FAILED,
                reason=f"{config.REASON_DRYRUN_WOULD_FAIL}／{config.REASON_CHARACTER_LIMIT}",
                url_before=url_before, url_after=url_before, form_remained="残存")
        # HTML5 制約（:invalid な必須要素）
        invalid = self._html5_invalid_count()
        if invalid > 0:
            return SubmitOutcome(
                status=config.RESULT_FAILED,
                reason=f"{config.REASON_DRYRUN_WOULD_FAIL}／必須/形式の未充足: {invalid}件",
                url_before=url_before, url_after=url_before, form_remained="残存")
        # 送信可能
        return SubmitOutcome(
            status=config.RESULT_SUBMIT_PRESUMED, reason=config.REASON_DRYRUN_WOULD_SUBMIT,
            evidence_type="検証（送信なし）", url_before=url_before, url_after=url_before,
            form_remained="残存", confidence=config.CONFIDENCE_LOW)

    def _html5_invalid_count(self) -> int:
        try:
            return int(self.c.driver.execute_script("""
                var n=0; var els=document.querySelectorAll('input,textarea,select');
                for(var i=0;i<els.length;i++){
                  var e=els[i];
                  if(e.willValidate && !e.checkValidity() && (e.required || e.value==='')) n++;
                }
                return n;
            """) or 0)
        except Exception:
            return 0
