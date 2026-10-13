"""
ListersForm 自動送信ツール — 設定定数（是正版 / Rebuild）

v11 から回収した定数を踏襲しつつ、929件誤判定の根本原因だった
「成功判定」を是正する。

是正の要点:
  旧実装:  エラーが検出されなければ「成功」とみなしていた（＝偽陽性の温床）。
            SUCCESS_KEYWORDS に「ありがとうございます」「ご連絡」等の
            汎用語が含まれ、フォーム周辺の一般文言でも成功扱いになっていた。
  是正後:  「受付確認(RECEIPT_CONFIRMED)」は、客観的な証跡が取れた場合に限る。
            送信操作はしたが確証が無いものは「送信処理完了（推定）」に格下げし、
            決して確定成功として扱わない。
"""

# ---------------------------------------------------------------------------
# NG フレーズ — これらを含むページは送信対象外（スキップ）
# ---------------------------------------------------------------------------
NG_PHRASES = [
    # Core restrictions
    "営業禁止", "営業不可", "営業お断り",
    # Legal / Enforcement
    "法的措置", "法的な処置", "法的処置", "法的手段", "法的対応",
    "特定電子メール", "送信の適正化",
    # Sales blocking
    "広告宣伝", "一方的な営業",
    "営業行為", "売り込み", "売込み", "売りこみ", "セールス",
]

# ---------------------------------------------------------------------------
# 問い合わせページ検出
# ---------------------------------------------------------------------------
CONTACT_KEYWORDS = [
    "お問い合わせ", "お問合せ", "問い合わせ", "問合せ", "お問合わせ",
    "お問い合わせはこちら", "お問い合わせフォーム", "問い合わせフォーム",
    "お客様相談", "ご相談", "資料請求", "お見積り", "お見積もり",
    "ご連絡", "連絡先", "メールでのお問い合わせ",
    "contact", "Contact", "CONTACT", "Contact Us", "contact us", "CONTACT US",
    "inquiry", "Inquiry", "INQUIRY", "enquiry", "Enquiry",
    "get in touch", "Get in Touch", "reach us", "Reach Us",
    "フォーム", "Form", "FORM",
    "お問い合せ", "問合わせ", "お問合", "問合",
    "ご質問", "ご意見", "ご要望", "ご相談窓口",
    "メールフォーム", "送信フォーム", "入力フォーム",
    "お問い合わせへ", "問い合わせへ", "contactへ",
    "お問い合わせする", "問い合わせる", "相談する",
]

CONTACT_URL_PATTERNS = [
    "/contact", "/inquiry",
    "/toiawase", "/otoiawase", "/お問い合わせ", "/問い合わせ",
    "/contact-us", "/contact_us", "/contactus", "/contact.html",
    "/form", "/enquiry", "/お問合せ", "/問合せ", "/support", "/help",
]

# ---------------------------------------------------------------------------
# フォーム選択ルール
# ---------------------------------------------------------------------------
INQUIRY_TYPE_PREFERENCE = [
    "その他", "other", "Others", "その他のお問い合わせ", "一般的なお問い合わせ",
    "その他（自由記入）", "その他お問い合わせ", "その他のご質問", "その他ご質問",
    "一般", "general", "General", "お問い合わせ", "問い合わせ",
    "ご質問", "質問", "サービスについて", "製品について", "情報",
]
CONTACT_METHOD_PREFERENCE = [
    "メール", "メールで回答希望", "メールで連絡希望", "email", "e-mail", "Eメール",
    "メールでの回答", "メールにて", "メールで", "Emailで", "電子メール",
    "メールアドレスへ", "メールで返信", "メール希望",
]
SOURCE_PREFERENCE = [
    "検索エンジン", "検索", "Google", "google", "search engine", "インターネット検索",
    "Web検索", "ホームページ", "ウェブ検索", "ネット検索", "Yahoo", "Bing",
    "インターネット", "ウェブサイト", "HP", "その他", "other",
]

# ---------------------------------------------------------------------------
# ボタン文言
# ---------------------------------------------------------------------------
SUBMIT_BUTTON_KEYWORDS = [
    "送信", "送信する", "送信します", "送る", "送信完了",
    "送信内容を確認のうえ送信", "この内容で送信", "上記内容で送信",
    "入力内容を送信", "フォームを送信", "メールを送信",
    "Submit", "submit", "SUBMIT", "Send", "send", "SEND",
    "送信ボタン", "Submit Form", "Send Message",
    "完了", "申し込む", "申込む", "申込", "登録",
    "送付", "送付する", "メール送信", "問い合わせる",
    "お問い合わせを送信", "内容を送信", "フォーム送信",
    "上記の内容で送信", "この内容で送る", "入力内容で送信",
    "送信 ▶", "送信▶", "▶送信", "→送信", "送信→",
    "送信 >", "> 送信", ">> 送信",
]

CONFIRM_BUTTON_KEYWORDS = [
    "確認", "確認する", "入力内容の確認", "内容を確認", "確認画面へ",
    "次へ", "次に進む", "次のステップへ", "次へ進む",
    "入力内容を確認", "確認画面に進む", "確認ページへ",
    "confirm", "Confirm", "CONFIRM", "Confirmation",
    "next", "Next", "NEXT", "proceed", "Proceed", "continue", "Continue",
    "進む", "先へ進む", "入力確認", "内容確認",
    "確認へ", "確認画面", "内容の確認", "入力内容確認",
    "次のページへ", "次ページへ", "次画面へ",
    "確認する ▶", "確認▶", "▶確認", "→確認", "確認→",
    "次へ ▶", "次へ▶", "▶次へ", "→次へ", "次へ→",
]

BACK_BUTTON_KEYWORDS = ["戻る", "戻るボタン", "前へ戻る", "back", "Back", "前に戻る", "修正する"]

PRIVACY_KEYWORDS = [
    "同意", "プライバシー", "規約", "利用規約", "個人情報", "承諾", "了承",
    "同意します", "理解しました", "個人情報保護", "プライバシーポリシー",
    "個人情報の取り扱い", "上記に同意", "内容に同意", "規約に同意", "ポリシーに同意",
    "同意する", "承諾する", "了承する", "確認しました",
    "privacy", "agree", "acceptance", "consent", "terms", "policy",
    "agree to", "accept", "I agree", "I accept",
    "約款", "ポリシー", "取扱い", "取り扱い",
]

CAPTCHA_KEYWORDS = [
    "recaptcha", "captcha", "CAPTCHA", "reCAPTCHA",
    "g-recaptcha", "h-captcha", "hcaptcha", "turnstile",
    "私はロボットではありません", "I'm not a robot",
]

# ---------------------------------------------------------------------------
# タイムアウト / 探索上限
# ---------------------------------------------------------------------------
PAGE_LOAD_TIMEOUT = 15
ELEMENT_WAIT_TIMEOUT = 6
FORM_SUBMIT_TIMEOUT = 20
POST_SUBMIT_WAIT = 2.5  # 送信後、完了ページ遷移/描画を待つ秒数

MAX_DIRECT_INQUIRY_URL_ATTEMPTS = 8
MAX_INQUIRY_LINK_ATTEMPTS = 5
MAX_RETRIES = 1

DEFAULT_PARALLEL_COUNT = 1
MAX_PARALLEL_COUNT = 8

# ---------------------------------------------------------------------------
# CSV 出力
# ---------------------------------------------------------------------------
CSV_DATETIME_FORMAT = "%Y%m%d%H%M%S"
# 是正版の出力列。クライアント合意の「区分」「証跡」「但し書き」を全て含む。
#   判定区分=結果 / 判定根拠種別 / 検出文言・受付番号 / 確認前後URL /
#   フォーム残存 / 判定日時 / 判定不能理由=理由 / 注意(但し書き)
CSV_COLUMNS = [
    "対象URL", "結果", "確信度",
    "判定根拠種別", "検出文言/受付番号",
    "確認前URL", "確認後URL", "フォーム残存",
    "理由", "お問い合わせURL", "判定日時", "使用メッセージ", "注意",
]

# 判定根拠種別（受付確認で用いる証跡タイプ）
EVIDENCE_URL_TRANSITION = "完了URLへの遷移＋フォーム消失"
EVIDENCE_RECEIPT_NUMBER = "受付番号/問い合わせ番号を検出"
EVIDENCE_COMPLETION_MSG = "明確な完了文言＋フォーム消失"
EVIDENCE_WEAK_COMBINED = "URL遷移＋フォーム消失（文言は汎用）"
EVIDENCE_PRESUMED_NO_ERROR = "エラー非表示のみ（確証なし）"
EVIDENCE_PRESUMED_JS = "JavaScript送信のみ（確証なし）"
EVIDENCE_PRESUMED_PHRASE_ONLY = "一般文言のみ（確証なし）"
EVIDENCE_PRESUMED_URL_ONLY = "URL文字列一致のみ（遷移・消失の裏付けなし／確証なし）"
EVIDENCE_NONE = "なし"

COMPANY_TAG = "【company】"

# ---------------------------------------------------------------------------
# フィールド自動検出パターン
# ---------------------------------------------------------------------------
FIELD_PATTERNS = {
    "company_name": ["会社名", "企業名", "社名", "法人名", "団体名", "組織名",
                     "company", "organization", "organisation", "corp", "firm",
                     "貴社名", "御社名", "会社・団体名"],
    "department": ["部署", "部門", "所属", "課", "グループ",
                   "department", "division", "section", "unit", "部署名", "所属部署"],
    "full_name": ["担当者氏名", "氏名", "お名前", "名前", "ご担当者名", "担当者名",
                  "姓名", "姓・名", "氏名（姓・名）", "フルネーム",
                  "name", "fullname", "full_name", "your name", "contact name",
                  "ご氏名", "お名前（フルネーム）", "代表者名"],
    "last_name": ["姓", "名字", "苗字", "氏",
                  "lastname", "last_name", "family name", "surname",
                  "お名前（姓）", "氏名（姓）"],
    "first_name": ["名", "下の名前",
                   "firstname", "first_name", "given name",
                   "お名前（名）", "氏名（名）"],
    "full_name_kana": ["フリガナ", "ふりがな", "カナ", "かな",
                       "フリガナ（セイ・メイ）", "フリガナ（全角）", "セイメイ",
                       "kana", "fullname_kana", "full_name_kana",
                       "お名前（フリガナ）", "氏名（フリガナ）", "ヨミガナ", "読み仮名"],
    "last_name_kana": ["姓（カナ）", "セイ", "せい", "フリガナ（姓）", "姓フリガナ",
                       "kana_last", "lastname_kana"],
    "first_name_kana": ["名（カナ）", "メイ", "めい", "フリガナ（名）", "名フリガナ",
                        "kana_first", "firstname_kana"],
    "email": ["メール", "メールアドレス", "Eメール", "e-mail", "E-mail",
              "email", "mail", "mailaddress", "mail_address",
              "ご連絡先メール", "連絡先メールアドレス", "PCメールアドレス"],
    "phone": ["電話", "電話番号", "TEL", "tel", "連絡先電話番号",
              "phone", "telephone", "phone number", "contact number",
              "お電話番号", "ご連絡先電話番号", "携帯電話", "携帯番号"],
    "url": ["url", "URL", "ホームページ", "サイト", "ウェブサイト",
            "website", "web", "homepage", "site",
            "会社URL", "貴社URL", "御社URL", "WebサイトURL"],
    "postal_code": ["郵便番号", "〒", "ポスタルコード",
                    "postal", "zip", "zipcode", "zip_code", "postcode",
                    "郵便", "郵便番号（ハイフンなし）"],
    "prefecture": ["都道府県", "県", "都", "府", "道",
                   "prefecture", "state", "region",
                   "お住まいの都道府県", "所在地（都道府県）"],
    "city": ["市区町村", "市", "区", "町", "村", "郡",
             "city", "municipality", "市区町村名", "所在地（市区町村）"],
    "address": ["住所", "所在地", "番地", "丁目", "ビル名", "建物名",
                "address", "street", "location",
                "ご住所", "会社住所", "詳細住所", "番地以降"],
    "subject": ["件名", "タイトル", "表題", "題名",
                "subject", "title", "topic", "お問い合わせ件名", "メール件名"],
    "message": ["本文", "内容", "お問い合わせ内容", "メッセージ", "詳細",
                "message", "inquiry", "content", "body", "description",
                "ご質問内容", "ご相談内容", "お問合せ内容", "備考"],
    "inquiry_type": ["お問い合わせ種類", "種別", "目的", "用件", "カテゴリ",
                     "type", "category", "inquiry type",
                     "問い合わせ内容", "お問い合わせの種類", "ご用件"],
    "contact_method": ["連絡方法", "希望連絡方法", "回答方法", "返信方法",
                       "contact method", "preferred contact",
                       "ご希望の連絡方法", "連絡希望方法"],
    "source": ["どこで知りましたか", "知ったきっかけ", "情報源", "きっかけ",
               "how did you", "source", "referral",
               "当社を知ったきっかけ", "弊社を知ったきっかけ"],
}

CRITICAL_REQUIRED_FIELDS = ["email"]
STANDARD_REQUIRED_FIELDS = ["company_name", "full_name", "email", "message"]

DEFAULT_MESSAGE_MAX_LENGTH = 2000
DEFAULT_FIELD_MAX_LENGTH = 100

# ===========================================================================
# 【是正の核心】送信成功の判定基準
# ===========================================================================
# 旧実装の「エラーが無ければ成功」「汎用文言で成功」を廃止し、
# 以下の3段階で厳密に判定する。
#
#   (A) 受付確認 RECEIPT_CONFIRMED  … 客観的証跡が取れた場合のみ
#         - 完了URLパターンへの遷移、または
#         - 受付番号/問い合わせ番号の検出、または
#         - 強い完了文言 AND 入力フォームが消失
#   (B) 送信処理完了（推定） SUBMIT_PRESUMED … 送信操作はしたが確証なし
#         （旧「エラーなし」「JS送信のみ」はすべてここに格下げ＝確定成功にしない）
#   (C) 失敗 FAILED … バリデーション/URL記載不可/文字数/CAPTCHA/ボタン無し 等
# ---------------------------------------------------------------------------

# (A-1) 完了（サンクス）ページとみなせるURLパターン
COMPLETION_URL_PATTERNS = [
    "thanks", "thankyou", "thank-you", "thank_you",
    "complete", "completed", "completion", "finish", "finished",
    "success", "sent", "done", "accepted",
    "mail-complete", "form-complete", "contact/thanks", "contact/complete",
    "/thx", "comp.html", "thanks.html", "complete.html", "end.html",
    "受付完了", "送信完了", "完了",
]

# (A-2) 受付番号/問い合わせ番号
#   ラベル語だけでは不可。ラベル＋「実際の識別番号（数字を含む）」が必須。
#   （案内文中の「受付番号をお知らせします」等の“語のみ”を受付確認の根拠にしない）
RECEIPT_LABEL_REGEX = (
    r"(?:受付番号|受付\s*No\.?|受付ナンバー|受付ID|受付コード|"
    r"お?問い?合わ?せ番号|お?問い?合わ?せID|整理番号|管理番号|ご相談番号|申込番号|"
    r"(?:reference|ticket|inquiry|case|confirmation)\s*(?:no\.?|number|id|code)?)"
)
# ラベルの直後（区切り数文字以内）に、英数字3文字以上の識別子。数字を含むことはコード側で確認。
RECEIPT_NUMBER_REGEX = RECEIPT_LABEL_REGEX + r"[\s:：#＃=・．.\-]{0,4}([A-Za-z0-9][A-Za-z0-9\-_/]{2,})"

# 旧パターン（参考・未使用）
RECEIPT_NUMBER_PATTERNS = [r"受付番号", r"問い合わせ番号", r"整理番号"]

# 受付確認として扱わない遷移先（案内・配信停止・保証等）。URLに含まれる場合は受付確認にしない。
NON_COMPLETION_URL_KEYWORDS = [
    "unsubscribe", "opt-out", "optout", "opt_out", "mailstop", "stop-mail",
    "配信停止", "haishin", "kaijo", "解除", "退会", "withdraw",
    "保証", "warranty", "hosho", "faq", "annai",
]

# (A-3) 強い完了文言（これ単独＋フォーム消失 で受付確認とみなす）
#   ※ これらは送信前フォームには通常現れない「完了」を明示する語に限定する。
STRONG_SUCCESS_PHRASES = [
    "送信完了", "送信が完了", "送信を完了", "送信いたしました", "送信しました",
    "受け付けました", "受付完了", "受付けました", "受理しました", "受理いたしました",
    "お問い合わせを受け付け", "お問合せを受け付け", "ご相談を受け付け",
    "正常に送信", "メッセージを送信しました", "メールを送信しました",
    "を送信しました", "送信されました", "送信が成功",
    "お問い合わせを承りました", "承りました",
    "送信完了画面", "完了画面",
]

# (A-weak) 弱い文言（これ単独では成功にしない。
#   フォーム消失 AND URL変化 を伴う場合に限り、補助シグナルとして受付確認を許可）
WEAK_SUCCESS_PHRASES = [
    "ありがとうございました", "ありがとうございます",
    "お問い合わせありがとう", "お問合せありがとう", "ご連絡ありがとう",
    "自動返信", "確認メール", "折り返し", "担当者より",
    "数日以内", "営業日以内", "お待ちください", "ご返信",
    "thank you", "thanks", "we have received", "your inquiry has been",
    "submitted", "message sent", "successfully sent",
]

# ---------------------------------------------------------------------------
# 失敗検出
# ---------------------------------------------------------------------------
VALIDATION_ERROR_KEYWORDS = [
    "入力してください", "必須項目", "必須です", "必須入力", "未入力",
    "エラー", "入力エラー", "入力内容に誤り", "正しく入力", "ご確認ください",
    "形式が正しくありません", "正しい形式", "半角для", "半角で入力", "全角で入力",
    "required", "error", "invalid", "please enter", "must be",
    "cannot be blank", "is required", "please fill", "field is required",
]

# URL 記載不可（クライアントが具体的に指摘。旧実装は分岐未接続だった）
URL_REJECTION_KEYWORDS = [
    "URLを含む", "URLは入力できません", "URLの入力はできません", "URLの記載",
    "リンクを含む", "リンクの投稿", "httpを含む", "http を含む",
    "外部リンク", "URLは使用できません", "ＵＲＬ", "url は使用できません",
    "アドレスを含む投稿", "リンクが含まれて",
]

# 文字数制限
CHAR_LIMIT_KEYWORDS = [
    "文字以内", "文字数", "文字を超え", "字以内", "最大文字数",
    "文字までで", "文字数が超え", "文字数制限", "超えています",
    "too long", "maximum length", "exceeds",
]

# ---------------------------------------------------------------------------
# 結果ラベル / 確信度
# ---------------------------------------------------------------------------
RESULT_RECEIPT_CONFIRMED = "受付確認"
RESULT_SUBMIT_PRESUMED = "送信処理完了（推定）"
RESULT_FAILED = "失敗"
RESULT_SKIPPED = "スキップ"

CONFIDENCE_HIGH = "高"
CONFIDENCE_MEDIUM = "中"
CONFIDENCE_LOW = "低"
CONFIDENCE_NONE = "-"

# 推定（未確証）送信に付与する注意表示
CAUTION_PRESUMED = (
    "送信操作は完了しましたが、先方での受付・到達は確認できていません"
    "（推定判定）。確実な到達保証ではありません。"
)

# 受付確認に付与する但し書き（クライアント要求: 画面・CSV双方に明記）
#   受付確認はフォーム上の完了確認であって、メール到達・対応完了の保証ではない。
RECEIPT_DISCLAIMER = (
    "「受付確認」はフォーム上の完了表示・受付番号等に基づく確認であり、"
    "先方へのメール到達・対応完了を保証するものではありません。"
)

# 画面（GUI）に常時表示する注記
SCREEN_DISCLAIMER = RECEIPT_DISCLAIMER

# ---------------------------------------------------------------------------
# 理由テキスト
# ---------------------------------------------------------------------------
REASON_INQUIRY_NOT_FOUND = "お問い合わせページが見つかりませんでした"
REASON_CAPTCHA_DETECTED = "CAPTCHAが検出されました"
REASON_VALIDATION_ERROR = "バリデーションエラー"
REASON_CHARACTER_LIMIT = "文字数制限を超えました"
REASON_URL_REJECTED = "URL入力が拒否されました（URL記載不可）"
REASON_NO_SONOTA = "必須ドロップダウンに「その他」がありません"
REASON_NG_PHRASE = "NGフレーズが検出されました"
REASON_CONFIRMATION_FAILED = "確認フローに失敗しました"
REASON_SUBMIT_BUTTON_NOT_FOUND = "送信ボタンが見つかりませんでした"
REASON_MAX_STEPS = "最大ステップ数を超えました"
REASON_ENVIRONMENT_CHROME_FAILED = "Chrome起動に失敗しました（環境要因）"
REASON_ENVIRONMENT_NETWORK_FAILED = "ネットワーク取得に失敗しました（環境要因）"
REASON_HTTP_BLOCKED = "サイトからのアクセスがブロックされました（403/429）"
REASON_UNKNOWN_ERROR = "不明なエラー"
REASON_STOPPED_BY_USER = "ユーザーによって停止されました"
REASON_SKIPPED_BY_USER = "ユーザーによってスキップされました"
REASON_DUPLICATE_URL = "重複URL（既に処理済み）"
REASON_REQUIRED_FIELDS_MISSING = "必須フィールドが入力できませんでした"
REASON_DRYRUN_WOULD_SUBMIT = "検証モード: 送信可能（送信は実行していません）"
REASON_DRYRUN_WOULD_FAIL = "検証モード: 送信不成立と判定（送信は実行していません）"
