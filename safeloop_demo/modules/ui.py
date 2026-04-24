"""
공통 UI 테마 및 헬퍼.

세이프루프 브랜드: Swiss International 스타일.
- 색상: #0A0A0B (잉크), #D50000 (포인트), #FFFFFF (배경), #E5E5E8 (보더), #6B6B70 (서브)
- 이모지 대신 번호·얇은 구분선 사용
- 모바일(태블릿·폰) 우선, 터치 타겟 44px 최소
"""
from __future__ import annotations

import streamlit as st


_CSS = """
<style>
/* ───────── 글로벌 ───────── */
html, body, [class*="css"], .stApp, .main, .block-container {
    font-family: 'Pretendard', 'Inter', -apple-system, BlinkMacSystemFont,
                 'Segoe UI', 'Noto Sans KR', sans-serif;
    -webkit-font-smoothing: antialiased;
    color: #0A0A0B;
}
.main .block-container { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 960px; }
h1, h2, h3, h4 { letter-spacing: -0.02em; font-weight: 700; }
h1 { font-size: 28px; }
h2 { font-size: 22px; }
h3 { font-size: 18px; }

/* 기본 텍스트 */
p, li, label, div[data-testid="stMarkdownContainer"] { color: #0A0A0B; }

/* 상단 내비게이션 줄 숨김 (배포 깔끔) */
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

/* ───────── 히어로 ───────── */
.sl-hero { padding: 24px 0 12px 0; border-bottom: 1px solid #E5E5E8; margin-bottom: 24px; }
.sl-kicker {
    font-size: 11px; letter-spacing: 0.32em; font-weight: 600;
    color: #D50000; text-transform: uppercase; margin-bottom: 10px;
}
.sl-title { font-size: 32px; font-weight: 800; line-height: 1.15; color: #0A0A0B; margin: 0 0 8px 0; letter-spacing: -0.03em; }
.sl-subtitle { font-size: 14px; color: #6B6B70; margin: 0 0 4px 0; }

/* ───────── 섹션 헤더 ───────── */
.sl-section { margin-top: 28px; margin-bottom: 12px; }
.sl-num {
    display: inline-block; font-size: 11px; letter-spacing: 0.32em;
    color: #D50000; font-weight: 600; margin-bottom: 6px;
    text-transform: uppercase;
}
.sl-h { font-size: 20px; font-weight: 700; color: #0A0A0B; margin: 0 0 4px 0; letter-spacing: -0.02em; }
.sl-h-sub { font-size: 13px; color: #6B6B70; margin: 0 0 12px 0; }

/* ───────── 카드 ───────── */
.sl-card {
    border: 1px solid #E5E5E8; border-radius: 6px; padding: 18px 20px;
    background: #FFF; margin-bottom: 14px;
}
.sl-card-accent { border-left: 3px solid #D50000; }

/* ───────── 분리선 ───────── */
hr, .sl-hr { border: 0; border-top: 1px solid #E5E5E8; margin: 24px 0; }

/* ───────── 버튼 ───────── */
div.stButton > button {
    border-radius: 4px; font-weight: 600; letter-spacing: -0.01em;
    transition: all 0.15s ease; min-height: 44px;
}
div.stButton > button[kind="primary"],
div.stButton > button[kind="primary"] * {
    background: #0A0A0B; color: #FFF !important; border-color: #0A0A0B;
}
div.stButton > button[kind="primary"]:hover,
div.stButton > button[kind="primary"]:hover * {
    background: #D50000; color: #FFF !important; border-color: #D50000;
}
div.stButton > button[kind="secondary"],
div.stButton > button[kind="secondary"] * {
    background: #FFF; color: #0A0A0B !important; border-color: #D1D1D4;
}
div.stButton > button[kind="secondary"]:hover { border-color: #0A0A0B; }
div.stButton > button:focus-visible { outline: 2px solid #D50000; outline-offset: 2px; }

/* 다운로드 버튼도 동일 톤 */
.stDownloadButton > button,
.stDownloadButton > button * {
    border-radius: 4px; font-weight: 600; min-height: 44px;
    background: #FFF; border-color: #D1D1D4; color: #0A0A0B !important;
}
.stDownloadButton > button:hover { border-color: #0A0A0B; background: #FAFAFA; }

/* ───────── 입력 요소 ───────── */
input, textarea, select { font-family: inherit !important; border-radius: 4px !important; }
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
    min-height: 44px; font-size: 15px;
}
label { font-weight: 500; color: #0A0A0B; }

/* 라디오 버튼 (양호/불량/부재 등) */
div[role="radiogroup"] > label { padding: 6px 14px; border: 1px solid transparent; border-radius: 999px; }

/* ───────── 메트릭 ───────── */
[data-testid="stMetric"] {
    background: #FFF; border: 1px solid #E5E5E8;
    border-radius: 6px; padding: 14px 18px;
}
[data-testid="stMetricLabel"] { font-size: 11px !important; letter-spacing: 0.12em; text-transform: uppercase; color: #6B6B70 !important; font-weight: 600; }
[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 800 !important; color: #0A0A0B !important; }
[data-testid="stMetricDelta"] { font-size: 12px !important; color: #6B6B70 !important; }

/* ───────── 탭 ───────── */
.stTabs [data-baseweb="tab-list"] { gap: 2px; border-bottom: 1px solid #E5E5E8; }
.stTabs [data-baseweb="tab"] {
    font-weight: 600; padding: 10px 14px; border-radius: 0;
    color: #6B6B70; background: transparent;
}
.stTabs [aria-selected="true"] { color: #0A0A0B; border-bottom: 2px solid #D50000; }

/* ───────── 모바일 ───────── */
@media (max-width: 768px) {
    .main .block-container { padding: 1.2rem 1rem 3rem 1rem; }
    .sl-title { font-size: 26px; }
    h1 { font-size: 24px; }
    div.stButton > button, .stDownloadButton > button { min-height: 48px; font-size: 15px; }
    [data-testid="stMetricValue"] { font-size: 22px !important; }
}

/* ───────── 사이드바 — 정제된 내비게이션 ───────── */
[data-testid="stSidebar"] {
    border-right: 1px solid #E5E5E8;
    background: #FAFAFA;
}
[data-testid="stSidebar"] .block-container {
    padding: 1.2rem 1rem 2rem 1rem;
}

/* Streamlit 기본 페이지 nav 숨김 (우리 render_sidebar로 대체) */
[data-testid="stSidebarNav"] { display: none; }

/* st.page_link 를 깔끔한 nav 항목으로 스타일링 */
[data-testid="stSidebar"] [data-testid="stPageLink"] {
    margin: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a {
    display: flex !important;
    align-items: center;
    padding: 9px 12px !important;
    margin: 1px 0 !important;
    border-radius: 6px !important;
    text-decoration: none !important;
    font-size: 13.5px !important;
    color: #6B6B70 !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    transition: all 0.12s ease;
    line-height: 1.3 !important;
    min-height: 36px;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
    background: #FFFFFF !important;
    color: #0A0A0B !important;
    border-color: #E5E5E8 !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {
    background: #0A0A0B !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-color: #0A0A0B !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] * {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a > div {
    background: transparent !important;
    color: inherit !important;
    font-size: inherit !important;
    font-weight: inherit !important;
}
/* page_link 의 svg 아이콘 (사용 안 할 때) */
[data-testid="stSidebar"] [data-testid="stPageLink"] svg { display: none; }

/* 사이드바 내부 버튼 (예: 세션 초기화) — 보조 톤 */
[data-testid="stSidebar"] div.stButton > button {
    background: transparent;
    color: #6B6B70;
    border: 1px solid #E5E5E8;
    font-size: 12px;
    min-height: 32px;
    padding: 6px 10px;
    font-weight: 500;
    border-radius: 6px;
}
[data-testid="stSidebar"] div.stButton > button:hover {
    background: #FFFFFF;
    color: #0A0A0B;
    border-color: #D1D1D4;
}
[data-testid="stSidebar"] div.stButton > button[kind="primary"],
[data-testid="stSidebar"] div.stButton > button[kind="primary"] * {
    background: #0A0A0B; color: #FFFFFF !important; border-color: #0A0A0B;
}

/* ───────── 표 ───────── */
[data-testid="stDataFrame"] { border: 1px solid #E5E5E8; border-radius: 6px; overflow: hidden; }

/* ───────── 알림 ───────── */
[data-testid="stAlert"] { border-radius: 6px; border: 1px solid #E5E5E8; }

/* 카메라 / 업로더 박스 */
[data-testid="stCameraInput"] > div, [data-testid="stFileUploader"] > section {
    border: 1px dashed #D1D1D4; border-radius: 6px; padding: 12px; background: #FAFAFA;
}

/* ───────── 커스텀 컴포넌트 ───────── */
.sl-pill {
    display: inline-block; padding: 2px 10px; font-size: 11px; font-weight: 600;
    letter-spacing: 0.06em; border-radius: 999px; background: #FAFAFA;
    border: 1px solid #E5E5E8; color: #6B6B70; margin-right: 6px;
}
.sl-pill-red { background: #FFF2F2; color: #D50000; border-color: #F8D0D0; }
.sl-pill-dark { background: #0A0A0B; color: #FFF; border-color: #0A0A0B; }

.sl-dot {
    display: inline-block; width: 6px; height: 6px; border-radius: 50%;
    background: #D1D1D4; margin-right: 6px; vertical-align: middle;
}
.sl-dot-on { background: #D50000; }

.sl-shot-head {
    display: flex; align-items: baseline; gap: 14px; margin-bottom: 6px;
}
.sl-shot-num {
    font-size: 11px; letter-spacing: 0.2em; color: #D50000;
    font-weight: 700; min-width: 24px;
}
.sl-shot-title { font-size: 17px; font-weight: 700; color: #0A0A0B; }
.sl-shot-guide { font-size: 13px; color: #6B6B70; line-height: 1.55; margin-bottom: 10px; }

.sl-status-ok { color: #1B8A3A; font-weight: 600; font-size: 12px; }
.sl-status-empty { color: #9A9A9F; font-weight: 500; font-size: 12px; }

/* ───────── 키보드 포커스 강화 ───────── */
*:focus-visible {
    outline: 2px solid #D50000 !important;
    outline-offset: 2px !important;
    border-radius: 4px;
}

/* ───────── 모바일 사이드바 햄버거 가독성 ───────── */
@media (max-width: 768px) {
    [data-testid="collapsedControl"] svg {
        width: 28px !important; height: 28px !important;
    }
}

/* ───────── 인쇄 (Ctrl+P / 보고서 출력 친화) ───────── */
@media print {
    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    [data-testid="collapsedControl"],
    .stButton, .stDownloadButton,
    div[role="radiogroup"],
    div[data-testid="stToolbar"] {
        display: none !important;
    }
    .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    .sl-card { box-shadow: none !important; page-break-inside: avoid; }
    .sl-hero, .sl-section { page-break-after: avoid; }
    h1, h2, h3 { page-break-after: avoid; }
    table { page-break-inside: avoid; }
    @page { size: A4; margin: 1.5cm; }
    .sl-kicker, .sl-num { color: #000 !important; }
    .sl-card-accent { border-left: 2px solid #000 !important; }
    a { color: #000 !important; text-decoration: underline; }
}
</style>
"""


_PWA_META = """
<link rel="manifest" href="./app/static/manifest.json">
<meta name="theme-color" content="#D50000">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="SafeLoop">
<link rel="apple-touch-icon" href="./app/static/icon-192.png">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">

<!-- Open Graph / 소셜 공유 -->
<meta property="og:title" content="세이프루프 SafeLoop — 학교 안전 순환 시스템">
<meta property="og:description" content="공공데이터로 시작해, 공공데이터로 돌아옵니다. AI 비전 기반 학교 맞춤 안전 점검.">
<meta property="og:type" content="website">
<meta property="og:image" content="./app/static/icon-512.png">
<meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="SafeLoop · 세이프루프">
<meta name="twitter:description" content="학교 안전 점검 한 사이클을 AI가 자동화합니다.">
<meta name="description" content="제8회 교육 공공데이터 AI 활용대회 — AI 비전으로 학교 공간을 인식하고 법령 기반 맞춤 점검표를 자동 생성하는 순환 시스템.">

<!-- favicon -->
<link rel="icon" type="image/png" sizes="192x192" href="./app/static/icon-192.png">
<link rel="icon" type="image/png" sizes="512x512" href="./app/static/icon-512.png">
"""


def apply_theme() -> None:
    """페이지 최상단에서 호출 — 공통 CSS + PWA 메타 주입."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(_PWA_META, unsafe_allow_html=True)


# ─────────────────────────────────────────
# 공용 사이드바 — 역할/컨텍스트 + 빠른 액션
# ─────────────────────────────────────────
def render_sidebar(active_key: str = "") -> None:
    """모든 페이지가 호출하는 공통 사이드바 (Streamlit page_link 기반).

    Swiss International 톤:
      - 회색 배경(#FAFAFA)에 흰색 항목 카드처럼 부유
      - 활성 페이지는 검정 배경 + 흰 글자 (1개만 두드러짐)
      - 그룹 라벨은 작은 키커 (대문자 letter-spacing)
      - 빠른액션·추천 뱃지 등 시각 노이즈 제거
    """
    # 세션 활동 갱신 + 장기 idle 안내
    from modules.session import stamp_activity, session_age_minutes
    age_min = session_age_minutes()
    stamp_activity()

    role = st.session_state.get("role", "학교")
    school = st.session_state.get("school")
    space = st.session_state.get("active_space")

    with st.sidebar:
        # ── 헤더 ──
        st.markdown(
            "<div style='padding:2px 4px 14px 4px;'>"
            "<div style='font-size:10px; letter-spacing:0.4em; color:#D50000; "
            "font-weight:700;'>SAFELOOP</div>"
            "<div style='font-size:12px; color:#9A9A9F; margin-top:2px;'>"
            "학교 안전 순환 시스템</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── 컨텍스트 카드 (학교·공간) ──
        if school or space:
            ctx_html = "<div style='background:#FFFFFF; border:1px solid #E5E5E8; " \
                        "border-left:2px solid #D50000; border-radius:6px; " \
                        "padding:10px 12px; margin-bottom:14px;'>"
            if school:
                ctx_html += (
                    f"<div style='font-size:13px; font-weight:600; color:#0A0A0B; "
                    f"line-height:1.3;'>{school.get('학교명','-')}</div>"
                    f"<div style='font-size:11px; color:#9A9A9F; margin-top:2px;'>"
                    f"{school.get('학교급','-')} · {school.get('설립구분','-')}</div>"
                )
            if space:
                nick = space.get("nickname") or "별칭 없음"
                ctx_html += (
                    f"<div style='font-size:11px; color:#6B6B70; margin-top:6px; "
                    f"padding-top:6px; border-top:1px solid #F0F0F2;'>"
                    f"{space.get('type','-')} · {nick}</div>"
                )
            ctx_html += "</div>"
            st.markdown(ctx_html, unsafe_allow_html=True)

        # ── 메뉴 그룹 ──
        groups = [
            ("점검", [
                ("app.py",                "홈"),
                ("pages/1_점검시작.py",     "점검 시작"),
                ("pages/2_AI점검.py",       "AI 점검"),
                ("pages/3_결과저장.py",     "결과 저장"),
            ]),
            ("조회", [
                ("pages/4_본교현황.py",     "본교 현황"),
                ("pages/5_전국대시보드.py",  "전국 대시보드"),
                ("pages/10_점검이력.py",    "점검 이력"),
            ]),
            ("운영", [
                ("pages/6_데이터순환.py",     "데이터 순환"),
                ("pages/7_교육청수신함.py",   "교육청 수신함"),
                ("pages/11_정책시뮬레이터.py", "정책 시뮬레이터"),
            ]),
            ("기타", [
                ("pages/8_설정.py",        "설정"),
                ("pages/9_프로젝트소개.py", "프로젝트 소개"),
            ]),
        ]

        for group_label, items in groups:
            st.markdown(
                f"<div style='font-size:10px; letter-spacing:0.2em; color:#9A9A9F; "
                f"font-weight:600; margin:14px 4px 6px 4px; text-transform:uppercase;'>"
                f"{group_label}</div>",
                unsafe_allow_html=True,
            )
            for target, label in items:
                # st.page_link — Streamlit이 활성 페이지 자동 감지 (aria-current=page)
                try:
                    st.page_link(target, label=label)
                except Exception:
                    # page_link 실패 시 fallback
                    if st.button(label, key=f"sb_fb_{target}", use_container_width=True):
                        st.switch_page(target)

        # ── 푸터 (idle 알림 + 역할) ──
        st.markdown("<div style='margin-top:22px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='padding-top:12px; border-top:1px solid #E5E5E8; "
            f"font-size:10px; color:#9A9A9F; letter-spacing:0.06em;'>"
            f"역할 · {role} 담당자"
            f"</div>",
            unsafe_allow_html=True,
        )

        if age_min > 30:
            st.markdown(
                f"<div style='margin-top:10px; padding:8px 10px; background:#FFF2F2; "
                f"border:1px solid #F8D0D0; border-radius:4px; font-size:11px; "
                f"color:#D50000;'>"
                f"마지막 활동 {age_min:.0f}분 경과 — 일부 입력 초기화 가능"
                f"</div>",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────
# 반응형 컬럼 헬퍼
# ─────────────────────────────────────────
def desktop_columns(spec: list[float] | int = 2):
    """데스크톱에선 좌-우 분할, 모바일에선 자동 세로 스택."""
    return st.columns(spec)


# ─────────────────────────────────────────
# 확인 모달 (2단계 클릭) — 파괴적 액션 안전
# ─────────────────────────────────────────
def confirm_button(label: str, key: str, message: str = "이 작업은 되돌릴 수 없습니다.",
                    use_container_width: bool = False) -> bool:
    """2단계 확인 버튼 — 첫 클릭 시 인라인 카드로 변환, 두 번째 클릭 시 실행.

    버튼 디자인이 갑자기 폭증하지 않도록 카드 안에 작게 배치.
    """
    confirm_key = f"_confirm_{key}"
    if st.session_state.get(confirm_key):
        st.markdown(
            f"<div style='border:1px solid #F8D0D0; background:#FFF2F2; "
            f"border-radius:6px; padding:12px 14px; margin:6px 0;'>"
            f"<div style='font-size:13px; color:#0A0A0B; margin-bottom:8px;'>"
            f"<b style='color:#D50000;'>확인 필요</b> · {message}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        cc1, cc2 = st.columns(2, gap="small")
        with cc1:
            if st.button(f"진행", key=f"{key}_yes", type="primary",
                          use_container_width=True):
                st.session_state[confirm_key] = False
                return True
        with cc2:
            if st.button("취소", key=f"{key}_no", use_container_width=True):
                st.session_state[confirm_key] = False
                st.rerun()
        return False
    if st.button(label, key=f"{key}_init", use_container_width=use_container_width):
        st.session_state[confirm_key] = True
        st.rerun()
    return False


# ─────────────────────────────────────────
# 친절 에러 박스
# ─────────────────────────────────────────
def friendly_error(operation: str, exc: Exception, hint: str = "") -> None:
    st.error(f"❌ **{operation} 중 오류가 발생했습니다.**")
    if hint:
        st.info(f"💡 {hint}")
    with st.expander("기술 상세 보기 (개발자/지원팀용)"):
        st.code(f"{type(exc).__name__}: {exc}")
        st.exception(exc)


# ─────────────────────────────────────────
# 빈 상태 안내 카드 (D-C3)
# ─────────────────────────────────────────
def empty_state(title: str, description: str = "",
                 action_label: str = "", action_target: str = "") -> None:
    st.markdown(
        f"<div style='text-align:center; padding:40px 20px; "
        f"border:1px dashed #D1D1D4; border-radius:8px; background:#FAFAFA;'>"
        f"<div style='font-size:18px; font-weight:700; color:#0A0A0B; margin-bottom:8px;'>"
        f"{title}</div>"
        f"<div style='font-size:13px; color:#6B6B70;'>{description}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if action_label and action_target:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button(action_label, type="primary", use_container_width=True,
                          key=f"empty_action_{action_target}"):
                st.switch_page(action_target)


# ─────────────────────────────────────────
# 모바일 숫자 키패드 (text_input 보강)
# ─────────────────────────────────────────
def numeric_input_patch(label_substring: str) -> None:
    """이미 렌더링된 text_input에 inputmode=numeric 주입."""
    safe = label_substring.replace("'", "")
    st.markdown(
        f"""
        <script>
        (function(){{
            const labels = window.parent.document.querySelectorAll('label');
            for (const lab of labels) {{
                if (lab.textContent && lab.textContent.includes('{safe}')) {{
                    const inp = lab.parentElement && lab.parentElement.querySelector('input');
                    if (inp) {{
                        inp.setAttribute('inputmode', 'numeric');
                        inp.setAttribute('pattern', '[0-9]*');
                        inp.setAttribute('autocomplete', 'one-time-code');
                    }}
                }}
            }}
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )



def hero(kicker: str, title: str, subtitle: str = "") -> None:
    """페이지 상단 히어로. 이모지 대신 얇은 키커 라벨로 위계 표시."""
    sub = f"<p class='sl-subtitle'>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"<div class='sl-hero'>"
        f"<div class='sl-kicker'>{kicker}</div>"
        f"<h1 class='sl-title'>{title}</h1>"
        f"{sub}"
        f"</div>",
        unsafe_allow_html=True,
    )


def section(num: str, title: str, subtitle: str = "") -> None:
    """번호 키커 + 섹션 제목."""
    sub = f"<div class='sl-h-sub'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"<div class='sl-section'>"
        f"<div class='sl-num'>{num}</div>"
        f"<div class='sl-h'>{title}</div>"
        f"{sub}"
        f"</div>",
        unsafe_allow_html=True,
    )


def pill(text: str, tone: str = "default") -> str:
    """인라인 pill 태그 HTML 반환."""
    cls = {"red": "sl-pill sl-pill-red", "dark": "sl-pill sl-pill-dark"}.get(tone, "sl-pill")
    return f"<span class='{cls}'>{text}</span>"


def divider() -> None:
    st.markdown("<hr class='sl-hr'/>", unsafe_allow_html=True)
