"""
Step 3~5 — 사진 촬영 + AI 3단계 파이프라인 + 설비 사용자 확정 + 현장 점검.

촬영 UI — 샷별 카드 (명칭 → 가이드 문구 → 카메라 → 촬영 결과):
공간 무관 공통 6샷. 각 샷마다 독립된 카메라 위젯. 최소 3샷 이상 확보 시 AI 분석 활성화.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.ai_vision import (
    api_key_available, current_provider_label,
    has_cached_demo_results, load_demo_pipeline_for_samples, samples_hit_cache,
    run_stage1, run_stage1_cross_check, run_stage2, run_stage3,
)
from modules.image_quality import analyze_and_optimize
from modules.laws import CATEGORIES
from modules.recommend import recommend_from_scores
from modules.score import calculate_safety_score
from modules.session import ensure_state, require_school
from modules.ui import (
    apply_theme, divider, friendly_error, hero, render_sidebar, section,
    confirm_button,
)

st.set_page_config(page_title="AI 점검 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="collapsed")
apply_theme()
ensure_state()
render_sidebar(active_key="ai")

school = require_school()
if not school:
    if st.button("← 학교 찾기로", key="ai_noschool_back",
                  use_container_width=True):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

space = st.session_state.get("active_space")
if not space:
    st.warning("점검할 공간이 선택되지 않았습니다.")
    if st.button("← 공간 선택으로", key="ai_nospace_back",
                  use_container_width=True):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

hero(
    "STEP 02",
    "AI 점검",
    f"{school['학교명']} · {space['type']}"
    + (f" · {space.get('nickname')}" if space.get("nickname") else ""),
)

# 카메라 capture 속성 주입 — 페이지당 1회만 (샷 카드마다 재삽입 시 DOM 중복)
st.markdown(
    """
    <script>
    (function(){
        function patch(){
            const inputs = window.parent.document.querySelectorAll('section[data-testid="stFileUploaderDropzone"] input[type="file"]');
            inputs.forEach(el => {
                if (!el.hasAttribute('capture')) {
                    el.setAttribute('accept', 'image/*');
                    el.setAttribute('capture', 'environment');
                }
            });
        }
        patch();
        setTimeout(patch, 300);
        setTimeout(patch, 1000);
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# 촬영 샷 정의 — 7컷 기본(공간 맵핑) + 1컷 선택(뒷문 있을 때) + 보완 1컷
#
# 다각도 + 천장으로 AI 가 공간 레이아웃과 안전 장비 위치를 동시에 추론.
# 별도 "위치샷" 강제 촬영은 없음 — AI 가 모호 판정 시 보완 단계에서 안내.
# ─────────────────────────────────────────
SHOTS: list[dict] = [
    {
        "key": "entrance_diag",
        "no": "01",
        "title": "입구 대각선 · 들어왔을 때 첫인상",
        "guide": "출입문 안쪽에 서서 공간 안쪽을 사선 광각으로 촬영하세요. "
                 "출입 동선과 공간 전체 분위기가 한 프레임에 담기게.",
        "required": True,
    },
    {
        "key": "front_view",
        "no": "02",
        "title": "교탁(실험대) 앞 · 학생석 정면",
        "guide": "교탁(또는 실험대) 앞에 서서 학생석을 향해 촬영하세요. "
                 "칠판·게시판·앞문·앞쪽 콘센트가 한 프레임에 담기게.",
        "required": True,
    },
    {
        "key": "center_window",
        "no": "03",
        "title": "공간 중앙 → 창문쪽",
        "guide": "공간 한가운데에 서서 창문 방향을 촬영하세요. "
                 "창문·완강기 보관함(고층)·창가 환기구가 보이도록.",
        "required": True,
    },
    {
        "key": "center_corridor",
        "no": "04",
        "title": "공간 중앙 → 복도쪽",
        "guide": "공간 한가운데에서 복도(반대편 벽) 방향을 촬영하세요. "
                 "게시판·복도쪽 콘센트·청소도구함·소화기가 보이도록.",
        "required": True,
    },
    {
        "key": "center_front_door",
        "no": "05",
        "title": "공간 중앙 → 앞문쪽",
        "guide": "공간 한가운데에서 앞문 방향을 촬영하세요. "
                 "앞문·비상구 표시등·출입 동선이 보이도록.",
        "required": True,
    },
    {
        "key": "center_back_door",
        "no": "06",
        "title": "공간 중앙 → 뒷문쪽",
        "guide": "공간 한가운데에서 뒷문(또는 후면 벽) 방향을 촬영하세요. "
                 "후면 게시·뒷문 비상구·청소도구·악기·표본 보관 등.",
        "required": True,
    },
    {
        "key": "ceiling",
        "no": "07",
        "title": "천장 (위로 향해)",
        "guide": "스마트폰을 위로 향해 천장 한 장. "
                 "화재감지기·연기감지기·스프링클러·환기구·조명이 함께 보이도록.",
        "required": True,
    },
    {
        "key": "back_door_diag",
        "no": "08",
        "title": "뒷문 대각선 (뒷문이 있을 때만)",
        "guide": "뒷문이 있다면 뒷문 안쪽에서 공간 안쪽을 사선으로. "
                 "뒷문에서 본 출입 동선·반대편 비상구를 함께 확인. 뒷문 없으면 건너뛰세요.",
        "required": False,
    },
    {
        "key": "close_supplement",
        "no": "09",
        "title": "보완 촬영 · AI가 모호 판정한 항목만 (선택)",
        "guide": "기본 7~8컷을 올려 AI 분석을 먼저 실행하세요. AI 가 특정 설비를 "
                 "'모호' 또는 '부재 의심' 으로 표시한 경우에만, 해당 영역(예: 가려진 캐비닛 뒤, "
                 "사각지대)을 추가 촬영하세요.",
        "required": False,
    },
]


from modules.storage import (
    save_draft_shots, load_draft_shots, has_draft, draft_summary, clear_draft,
)


def _shots_dict() -> dict:
    """세션에 샷별 저장소 초기화 — 각 샷은 사진 리스트."""
    return {s["key"]: [] for s in SHOTS}


# 세션 초기화 + 구 스키마 마이그레이션 (dict → list)
if "shots" not in st.session_state:
    st.session_state["shots"] = _shots_dict()
else:
    migrated = {}
    for s in SHOTS:
        v = st.session_state["shots"].get(s["key"])
        if v is None:
            migrated[s["key"]] = []
        elif isinstance(v, dict):
            migrated[s["key"]] = [v]
        elif isinstance(v, list):
            migrated[s["key"]] = v
        else:
            migrated[s["key"]] = []
    st.session_state["shots"] = migrated

shots_state: dict = st.session_state["shots"]

# ─────────────────────────────────────────
# 드래프트 복원 안내 (새로고침/재진입 시) — 학교+공간 단위
# ─────────────────────────────────────────
school_code = school.get("정보공시 학교코드", "")
space_id = (space or {}).get("space_id", "")
empty_now = sum(len(v) for v in shots_state.values()) == 0
has_stale_results = empty_now and any(
    st.session_state.get(k) for k in ["stage1_result", "stage2_result", "stage3_result"]
)
if has_stale_results and not st.session_state.get("_draft_restored"):
    # 사진 없는데 이전 AI 결과만 남은 경우 → 확실히 초기화
    for _k in ["stage1_result", "stage2_result", "stage2_confirmed",
                "stage3_result", "stage1_cross_check", "item_scores",
                "score_result", "recommendations"]:
        st.session_state[_k] = None
    st.toast("이전 분석 결과를 정리했습니다 (사진이 비어있음)", icon="ℹ️")

if empty_now and has_draft(school_code, space_id) and not st.session_state.get("_draft_restored"):
    summary = draft_summary(school_code, space_id) or {}
    n = summary.get("photo_count", 0)
    when = (summary.get("updated_at") or "")[:16].replace("T", " ")
    st.markdown(
        f"<div style='border:1px solid #E5E5E8; border-left:3px solid #D50000; "
        f"background:#FFF; border-radius:6px; padding:14px 18px; margin:8px 0 14px 0; "
        f"display:flex; align-items:center; justify-content:space-between; gap:14px;'>"
        f"<div>"
        f"<div style='font-size:11px; letter-spacing:0.2em; color:#D50000; "
        f"font-weight:600;'>중단된 작업 발견</div>"
        f"<div style='font-size:14px; color:#0A0A0B; margin-top:4px;'>"
        f"이 학교 촬영본 <b>{n}장</b>이 임시 저장되어 있습니다 · {when}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    rc1, rc2, _ = st.columns([1, 1, 3])
    with rc1:
        if st.button("이어서 작업", type="primary", key="restore_draft",
                      use_container_width=True):
            restored = load_draft_shots(school_code, space_id)
            for k, v in restored.items():
                shots_state[k] = v
            st.session_state["_draft_restored"] = True
            st.rerun()
    with rc2:
        if st.button("새로 시작", key="discard_draft", use_container_width=True):
            clear_draft(school_code, space_id)
            st.session_state["_draft_restored"] = True
            st.rerun()

total_photos = sum(len(v) for v in shots_state.values())
required_filled = sum(1 for s in SHOTS if s["required"] and shots_state.get(s["key"]))
required_total = sum(1 for s in SHOTS if s["required"])

# ─────────────────────────────────────────
# 위저드 상태 (한 구도씩 한 화면) — 7~8컷 + 보완
# ─────────────────────────────────────────
WIZARD_STEPS = [
    ("shoot_1", "01 입구 대각선",  "entrance_diag"),
    ("shoot_2", "02 앞 정면",       "front_view"),
    ("shoot_3", "03 창문쪽",        "center_window"),
    ("shoot_4", "04 복도쪽",        "center_corridor"),
    ("shoot_5", "05 앞문쪽",        "center_front_door"),
    ("shoot_6", "06 뒷문쪽",        "center_back_door"),
    ("shoot_7", "07 천장",          "ceiling"),
    ("shoot_8", "08 뒷문 대각선",   "back_door_diag"),    # 선택
    ("ai_run",  "AI 분석",          None),
    ("supplement", "보완",          "close_supplement"),
    ("review",  "결과",             None),
]
_STEP_KEYS = [s[0] for s in WIZARD_STEPS]
_SHOT_OF_STEP = {s[0]: s[2] for s in WIZARD_STEPS}

if "wizard_step" not in st.session_state:
    st.session_state["wizard_step"] = "shoot_1"
# 방어: 잘못된 스텝 값 리셋
if st.session_state["wizard_step"] not in _STEP_KEYS:
    st.session_state["wizard_step"] = "shoot_1"

# 🎬 자동재생 진입 — 필수 컷 중 일정 비율 이상 채워지면 ai_run 스텝으로 점프
# 샘플 폴더에 7컷 전체가 없는 경우(시연용)도 진행 가능하도록 임계 80%
if st.session_state.get("_autoplay") and not st.session_state.get("_autoplay_consumed"):
    _required_keys_auto = [
        "entrance_diag", "front_view", "center_window", "center_corridor",
        "center_front_door", "center_back_door", "ceiling",
    ]
    _filled = sum(1 for k in _required_keys_auto
                  if st.session_state.get("shots", {}).get(k))
    if _filled >= 5:  # 7개 중 5개 이상 = 71% 이상이면 진행 (3장 광각 + 천장만 있어도 가능)
        st.session_state["wizard_step"] = "ai_run"
        st.session_state["_autoplay_consumed"] = True

# 2-3 수정: 토글 라벨을 명확히 하고, 현재 모드를 보조 안내로 함께 표시
col_toggle_l, col_toggle_r = st.columns([3, 2])
with col_toggle_l:
    _mode_hint = (
        "모드: 전체 한 번에 보기 (모든 구도가 한 화면)"
        if st.session_state.get("classic_mode", False)
        else "모드: 위저드 (한 구도씩 단계별 진행)"
    )
    st.caption(_mode_hint)
with col_toggle_r:
    classic_mode = st.toggle(
        "클래식 모드 (전체 한 번에 보기)",
        value=st.session_state.get("classic_mode", False),
        key="classic_mode",
        help="OFF(기본): 한 구도씩 단계별 위저드. ON: 모든 구도가 한 화면에 보임.",
    )
step = st.session_state["wizard_step"]


def _go_to_step(target: str) -> None:
    """스텝 이동 · rerun."""
    if target in _STEP_KEYS:
        st.session_state["wizard_step"] = target
        st.rerun()


def _render_progress(current: str) -> None:
    """상단 진행 인디케이터 · 현재/완료/대기 색 구분."""
    cur_idx = _STEP_KEYS.index(current) if current in _STEP_KEYS else 0
    pieces = []
    for i, (k, label, _) in enumerate(WIZARD_STEPS):
        if i < cur_idx:
            color, weight = "#0A0A0B", "500"
        elif i == cur_idx:
            color, weight = "#D50000", "700"
        else:
            color, weight = "#9A9A9F", "500"
        pieces.append(
            f"<span style='color:{color};font-weight:{weight};'>{label}</span>"
        )
    sep = "<span style='color:#D1D1D4;margin:0 10px;'>—</span>"
    st.markdown(
        "<div style='font-size:13px;margin:0 0 18px 0;letter-spacing:0.02em;"
        "padding:10px 14px;border:1px solid #E5E5E8;border-radius:6px;"
        "background:#FAFAFA;'>" + sep.join(pieces) + "</div>",
        unsafe_allow_html=True,
    )


def _render_shot_card(s: dict) -> None:
    """샷 카드 한 장 렌더(기존 루프 본문 추출)."""
    key = s["key"]
    photos = shots_state.setdefault(key, [])
    count = len(photos)
    status_html = (
        f"<span class='sl-status-ok'>● {count}장 촬영됨</span>"
        if count else "<span class='sl-status-empty'>○ 촬영 대기</span>"
    )
    required_label = "필수" if s["required"] else "선택"
    required_pill_class = "sl-pill-red" if s["required"] else "sl-pill"

    st.markdown(
        f"<div class='sl-card' style='margin-bottom:0;'>"
        f"<div class='sl-shot-head'>"
        f"<div class='sl-shot-num'>{s['no']}</div>"
        f"<div class='sl-shot-title'>{s['title']}</div>"
        f"<div style='margin-left:auto;'>"
        f"<span class='sl-pill {required_pill_class}'>{required_label}</span>"
        f"{status_html}"
        f"</div></div>"
        f"<div class='sl-shot-guide'>{s['guide']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.container():
        if photos:
            thumb_cols = st.columns(min(4, max(1, count)))
            for idx, p in enumerate(photos):
                with thumb_cols[idx % len(thumb_cols)]:
                    st.image(p["bytes"], caption=f"{s['no']}-{idx+1}",
                             use_container_width=True)
                    if st.button("삭제", key=f"del_{key}_{idx}", use_container_width=True):
                        photos.pop(idx)
                        _persist_draft()
                        st.rerun()

        counter_key = f"cam_ctr_{key}"
        if counter_key not in st.session_state:
            st.session_state[counter_key] = 0
        cam_widget_key = f"cam_{key}_{st.session_state[counter_key]}"

        st.markdown(
            "<div style='font-size:12px;color:#6B6B70;margin-bottom:4px;'>"
            "버튼을 누르면 <b>카메라가 바로 실행</b>됩니다 (PC는 파일 선택 창)."
            "</div>",
            unsafe_allow_html=True,
        )
        snap = st.file_uploader(
            f"이 구도 촬영하기 · {s['title']}",
            type=["jpg", "jpeg", "png", "webp", "heic"],
            accept_multiple_files=True,
            key=cam_widget_key,
            label_visibility="collapsed",
        )
        if snap:
            added = 0
            rejected = 0
            existing_bytes = {p["bytes"] for p in photos}
            for f in snap:
                new_bytes = f.getvalue()
                if new_bytes not in existing_bytes:
                    photos.append({
                        "name": f"{key}_{len(photos)+1}.jpg",
                        "bytes": new_bytes,
                        "source": "camera",
                    })
                    existing_bytes.add(new_bytes)
                    added += 1
                else:
                    rejected += 1
            # 2-7 수정: 중복으로 거부된 사진을 toast 로 명시
            if rejected:
                st.toast(
                    f"중복 사진 {rejected}장은 건너뜀 (같은 바이트)",
                    icon="ℹ️",
                )
            if added:
                st.session_state[counter_key] += 1
                _persist_draft()
                st.rerun()
            elif rejected:
                # 중복만 있었던 경우에도 입력 위젯은 리셋해줘야 반복 업로드 가능
                st.session_state[counter_key] += 1
                st.rerun()

        if photos:
            if st.button("이 구도 전체 비우기", key=f"clear_shot_{key}"):
                shots_state[key] = []
                st.session_state[counter_key] = st.session_state.get(counter_key, 0) + 1
                _persist_draft()
                st.rerun()

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)


def _render_wizard_nav(prev_step: str | None, next_step: str | None,
                        next_label: str = "다음 →", next_disabled: bool = False,
                        next_type: str = "primary") -> None:
    """하단 이전/다음 버튼."""
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    c_prev, c_spacer, c_next = st.columns([1, 2, 1])
    with c_prev:
        if prev_step:
            if st.button("← 이전", key=f"nav_prev_{step}", use_container_width=True):
                _go_to_step(prev_step)
    with c_next:
        if next_step:
            if st.button(next_label, key=f"nav_next_{step}",
                         use_container_width=True, disabled=next_disabled,
                         type=next_type):
                _go_to_step(next_step)


# ─────────────────────────────────────────
# (A) 촬영 · 위저드 or 클래식
# ─────────────────────────────────────────
if classic_mode:
    section(
        "01", "사진 촬영",
        f"누적 {total_photos}장 · 필수 구도 {required_filled}/{required_total} 충족"
        + (" · AI 분석 가능" if total_photos >= required_total and required_filled >= required_total
           else ""),
    )
    st.markdown(
        "<div style='font-size:13px; color:#6B6B70; margin-bottom:12px; line-height:1.65;'>"
        "<b style='color:#0A0A0B;'>기본 7~8컷</b>으로 공간 전체와 천장까지 한 번에 담습니다. "
        "입구 대각선 → 앞 정면 → 중앙 4방향(창문/복도/앞문/뒷문) → 천장 → (뒷문 대각선, 있을 때) 순. "
        "AI 가 이 다각도 사진들로 <b>공간 레이아웃 + 안전 장비 위치</b>를 동시에 식별합니다. "
        "AI가 모호 판정한 항목만 맨 아래 <b>보완 촬영(선택)</b> 을 사용하세요. "
        "<b>iPhone 은 HTTPS 접속 필요.</b>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    _render_progress(step)

# 시연 모드 — 샘플 일괄 로드 (시연 모드일 땐 펼침)
if st.session_state.get("demo_mode"):
    with st.expander("시연 모드 · 샘플 사진 일괄 로드", expanded=True):
        SAMPLE_FOLDERS = {
            "화학실 샘플": "chemistry_lab",
            "물리실 샘플": "physics_lab",
            "일반교실 샘플 (폴백: 화학실)": "classroom",
            "미술실 샘플 (폴백: 화학실)": "art_lab",
        }
        sample_choice = st.radio(
            "샘플 공간",
            list(SAMPLE_FOLDERS.keys()),
            horizontal=True,
            key="sample_choice",
        )
        st.caption(
            "기본 7컷 (입구·앞·중앙 4방향·천장) 위치에 가용한 사진을 분배합니다. "
            "샘플이 부족하면 일부 컷이 비어 있을 수 있고, 폴더가 없으면 화학실로 폴백합니다."
        )
        if st.button("샘플 불러와서 7컷에 분배", use_container_width=True):
            root = Path(__file__).resolve().parent.parent / "sample_images"
            folder = SAMPLE_FOLDERS[sample_choice]
            sub_path = root / folder
            if not sub_path.exists() or not list(sub_path.glob("*.jpg")):
                sub_path = root / "chemistry_lab"  # 폴백
            paths = sorted(sub_path.glob("*.jpg"))
            # 모든 샷 키 비움
            for s in SHOTS:
                shots_state[s["key"]] = []
            # 7컷 필수 키에 순서대로 분배 (샘플이 부족하면 일부 비어 있음)
            target_keys = [
                "entrance_diag", "front_view", "center_window", "center_corridor",
                "center_front_door", "center_back_door", "ceiling",
            ]
            for i, p in enumerate(paths[:len(target_keys)]):
                shots_state[target_keys[i]].append({
                    "name": p.name, "bytes": p.read_bytes(), "source": "sample",
                })
            for k in ["stage1_result", "stage2_result", "stage2_confirmed", "stage3_result"]:
                st.session_state[k] = None
            _persist_draft()
            st.rerun()

def _reset_all() -> None:
    st.session_state["shots"] = _shots_dict()
    for _s in SHOTS:
        _ck = f"cam_ctr_{_s['key']}"
        if _ck in st.session_state:
            st.session_state[_ck] += 1
    for _k in ["stage1_result", "stage2_result", "stage2_confirmed", "stage3_result",
               "item_scores", "score_result", "recommendations"]:
        st.session_state[_k] = None
    st.session_state["wizard_step"] = "shoot_1"
    clear_draft(school_code, space_id)
    st.session_state["_draft_restored"] = False
    st.rerun()


_SHOT_BY_KEY = {s["key"]: s for s in SHOTS}

if classic_mode:
    # ─── 클래식: 기존처럼 전체 샷을 한 화면에 ───
    _has_ai_result = bool(st.session_state.get("stage2_result"))
    for s in SHOTS:
        if s["key"] == "close_supplement" and not _has_ai_result:
            continue
        _render_shot_card(s)
    colR1, colR2 = st.columns([4, 1])
    with colR2:
        if confirm_button("전체 초기화", key="reset_shots_classic",
                           message="촬영한 모든 사진과 AI 결과가 삭제됩니다."):
            _reset_all()
else:
    # ─── 위저드: 스텝별 한 화면 ───
    SHOOT_STEPS = ("shoot_1", "shoot_2", "shoot_3", "shoot_4",
                    "shoot_5", "shoot_6", "shoot_7", "shoot_8")

    if step in SHOOT_STEPS:
        shot = _SHOT_BY_KEY[_SHOT_OF_STEP[step]]
        _render_shot_card(shot)
        shot_done = bool(shots_state.get(shot["key"])) or not shot["required"]

        # 스텝 인덱스 기반 prev/next
        idx = SHOOT_STEPS.index(step)
        prev_step = SHOOT_STEPS[idx - 1] if idx > 0 else None
        # 마지막 촬영 단계 다음은 ai_run
        next_step = SHOOT_STEPS[idx + 1] if idx < len(SHOOT_STEPS) - 1 else "ai_run"

        is_last_required = (step == "shoot_7")  # 7번까지 필수, 8번(뒷문 대각선) 은 선택
        next_label = (
            "다음 구도 →" if step != "shoot_8" else
            "AI 분석 단계로 →"
        )
        # 8번 (뒷문 대각선) 은 선택이므로 미촬영이어도 진행 허용
        if step == "shoot_8":
            next_step = "ai_run"
            next_label = "AI 분석 단계로 →"

        _render_wizard_nav(
            prev_step=prev_step,
            next_step=next_step,
            next_label=next_label,
            next_disabled=(not shot_done),
        )

        if step == "shoot_7" and shot_done:
            st.caption(
                "💡 **뒷문이 있다면** 다음 단계(08 뒷문 대각선)에서 한 장 더 찍어주세요. "
                "뒷문이 없으면 바로 'AI 분석 단계로' 진행하셔도 됩니다."
            )
        elif step == "shoot_8":
            st.caption("뒷문이 없으면 건너뛰고 바로 AI 분석으로 진행하세요.")
        elif not shot_done:
            st.caption("이 구도를 최소 한 장 촬영하면 다음으로 진행할 수 있어요.")

    elif step == "ai_run":
        # 촬영 요약 + AI 실행 안내
        st.markdown(
            "<div class='sl-card'>"
            "<div class='sl-shot-head'>"
            "<div class='sl-shot-num'>AI</div>"
            "<div class='sl-shot-title'>사진 확인 및 AI 분석</div>"
            "</div>"
            "<div class='sl-shot-guide'>"
            "아래 7~8장을 AI가 분석해 공간 유형 판정 + 안전 설비 위치까지 한 번에 식별합니다. "
            "사진을 다시 찍으려면 ‘이전’으로 돌아가세요."
            "</div></div>",
            unsafe_allow_html=True,
        )
        # 모든 기본 촬영 컷 한눈에 보여주기
        all_keys = [s["key"] for s in SHOTS if s["key"] != "close_supplement"]
        # 4개씩 그리드
        rows = [all_keys[i:i+4] for i in range(0, len(all_keys), 4)]
        for row_keys in rows:
            cols = st.columns(len(row_keys))
            for i, k in enumerate(row_keys):
                shot = _SHOT_BY_KEY[k]
                with cols[i]:
                    label = shot["title"].split(" · ")[0]
                    st.markdown(
                        f"<div style='font-size:11px;color:#6B6B70;margin-bottom:4px;'>"
                        f"{shot['no']} · {label}</div>",
                        unsafe_allow_html=True,
                    )
                    ps = shots_state.get(k, [])
                    if ps:
                        st.image(ps[0]["bytes"], use_container_width=True)
                    else:
                        if shot.get("required"):
                            st.warning("미촬영")
                        else:
                            st.caption("(선택 — 건너뜀)")

        _render_wizard_nav(
            prev_step="shoot_8",
            next_step=None,
        )  # 다음은 AI 실행 버튼이 대신함

    elif step == "supplement":
        # AI 결과 요약 + 보완 촬영 카드 + 재분석
        s2 = st.session_state.get("stage2_result") or {}
        absent = s2.get("likely_absent_equipment", []) or []
        ambiguous = s2.get("ambiguous_items", []) or []
        st.markdown(
            "<div class='sl-card'>"
            "<div class='sl-shot-head'>"
            "<div class='sl-shot-num'>04</div>"
            "<div class='sl-shot-title'>보완 촬영 (선택)</div>"
            "</div>"
            "<div class='sl-shot-guide'>"
            f"AI가 <b>{len(absent)}개 설비를 ‘없음’</b>, <b>{len(ambiguous)}개 항목을 ‘모호’</b>로 판정했습니다. "
            "실제로 존재하는데 AI가 못 본 것만 근접 촬영하세요. 없으면 건너뛰어도 됩니다."
            "</div></div>",
            unsafe_allow_html=True,
        )
        _render_shot_card(_SHOT_BY_KEY["close_supplement"])

        supplement_photos = shots_state.get("close_supplement", [])
        if supplement_photos:
            if st.button("보완 사진으로 AI 재분석 (즉시)", type="primary",
                         use_container_width=True, key="rerun_ai_supplement"):
                # 즉시 stage1·2·3 재실행 (ai_run 거치지 않음)
                st.session_state["_trigger_rerun_supplement"] = True
                st.rerun()

        _render_wizard_nav(
            prev_step="ai_run",
            next_step="review",
            next_label="결과 단계로 →",
        )
        if not supplement_photos:
            st.caption("보완 촬영이 필요 없다면 그대로 ‘결과 단계로’ 진행해도 됩니다.")

    elif step == "review":
        # 결과 단계는 아래 (B)/(C)/(D)/(E) 블록이 렌더
        pass

    # 초기화 링크 (위저드에서도 접근)
    with st.expander("처음부터 다시 시작"):
        if confirm_button("모든 사진/결과 초기화", key="reset_wizard",
                           message="이 공간의 촬영본·AI 분석·점검 입력이 모두 사라집니다."):
            _reset_all()

# ─────────────────────────────────────────
# (B) AI 3단계 파이프라인
#     위저드에서는 `ai_run` 스텝에서만 실행 UI를 노출.
#     실행 완료 시 자동으로 `supplement` 스텝으로 이동.
# ─────────────────────────────────────────

# 공통 헬퍼 — 모든 샷을 평탄화 (실행·결과 모두 필요)
def _flatten_photos_with_labels() -> tuple[list[bytes], list[str]]:
    photos: list[bytes] = []
    labels: list[str] = []
    for s in SHOTS:
        for idx, p in enumerate(shots_state.get(s["key"], []), start=1):
            photos.append(p["bytes"])
            labels.append(f"{s['no']}-{idx} ({s['title']})")
    return photos, labels


def _persist_draft() -> None:
    """샷 변경 시마다 호출 — 디스크에 자동 백업 (학교+공간 단위)."""
    try:
        save_draft_shots(school_code, shots_state, space_id)
    except Exception:
        pass  # 백업 실패는 사용자 흐름 차단하지 않음


all_photos, all_labels = _flatten_photos_with_labels()
total_filled = len(all_photos)
# 7컷 전체 강제하지 않음 — 최소 5컷 (입구·앞·중앙 4방향 중 충분히 채워야)
# AI 가 부족분은 보완 단계에서 안내
_MIN_REQUIRED_FILLED = 5
analysis_ready = total_filled >= _MIN_REQUIRED_FILLED and required_filled >= _MIN_REQUIRED_FILLED

_show_ai_run = classic_mode or step == "ai_run"

if _show_ai_run:
    divider()
    section(
        "02", "AI 자동 분석 · 맞춤 점검표 생성",
        f"Claude 비전 AI가 사진에서 공간 유형과 설비를 직접 식별합니다 · "
        f"누적 {total_filled}장 · 필수 구도 {required_filled}/{required_total}"
        + (" · <b style=\"color:#D50000\">실행 준비 완료</b>" if analysis_ready
           else f" · 필수 {required_total}컷을 먼저 채우세요"),
    )

    key_ok = api_key_available()
    # 2-12 수정: 단순히 "캐시 파일이 있음" 이 아니라 "현재 사진이 캐시와 정확 매칭" 인지 확인
    _opt_for_cache = (
        [analyze_and_optimize(b).optimized_bytes for b in all_photos[:3]]
        if len(all_photos) >= 3 else []
    )
    cache_match = samples_hit_cache(_opt_for_cache)
    cached_demo = cache_match and st.session_state.get("demo_mode", True)
    cached_possible = (
        has_cached_demo_results()
        and st.session_state.get("demo_mode", True)
        and not cache_match
    )

    if not key_ok and not cached_demo:
        provider_id = st.session_state.get("ai_provider") or "anthropic"
        env_var = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(
            provider_id, "API_KEY"
        )
        hint_cache = (
            "\n\n💡 이전에 분석한 샘플 캐시가 남아 있습니다 — "
            "**샘플 사진(화학실/물리실)을 그대로 불러오면** 즉시 재현됩니다."
            if cached_possible else ""
        )
        st.warning(
            f"**AI 키가 감지되지 않았습니다** ({provider_id})\n\n"
            f"세 가지 방법 중 하나로 해결할 수 있습니다:\n"
            f"- `safeloop_demo/.env` 에 `{env_var}=sk-...` 추가\n"
            f"- 사이드바 **설정 → AI 공급자** 에서 키 입력\n"
            f"- 시연 모드: 샘플 사진을 한 번 분석해두면 다음부턴 캐시로 즉시 재현"
            + hint_cache
        )
    elif not key_ok and cached_demo:
        st.info(
            "🎬 **시연 모드 — 캐시 폴백 활성화**\n\n"
            "현재 업로드된 사진이 이전에 분석된 캐시와 일치합니다. "
            "API 호출 없이 즉시 결과를 재현합니다."
        )
    if key_ok or cached_demo:
        col_a, col_b = st.columns([1, 3])
        with col_a:
            use_cache = st.checkbox("캐시 사용", value=True,
                                     help="동일 사진 재분석 시 API 호출 생략.")
        # 보완 재분석 트리거 자동 처리
        triggered_by_supplement = st.session_state.pop("_trigger_rerun_supplement", False)
        # 🎬 시연 자동 재생 트리거 (홈에서 넘어온 경우) — 1회만
        triggered_by_autoplay = (
            st.session_state.pop("_autoplay_run_ai", False)
            and analysis_ready
            and not st.session_state.get("stage3_result")
        )
        if triggered_by_autoplay:
            st.info("🎬 시연 자동 재생 — 샘플 사진으로 AI 분석을 즉시 실행합니다...")
        with col_b:
            run_disabled = not analysis_ready
            btn_label = ("▶  AI 분석 시작 (공간 식별 → 설비 탐지 → 점검표 생성)"
                         if analysis_ready else f"필수 {_MIN_REQUIRED_FILLED}컷 이상 촬영 후 활성화")
            user_clicked = st.button(btn_label, type="primary", use_container_width=True,
                                      disabled=run_disabled, key="run_ai_btn")
            if user_clicked or (triggered_by_supplement and analysis_ready) or triggered_by_autoplay:
                images = all_photos
                labels = all_labels
                # 사진 수 기반 예상 시간
                n_imgs = len(images)
                est_total = int(5 + 1.5 * n_imgs + 8 + 2.5 * n_imgs + 4)

                # 1) API 키 없을 때 시연 캐시 폴백 우선 시도
                if not key_ok:
                    cached_pipeline = load_demo_pipeline_for_samples(
                        [analyze_and_optimize(b).optimized_bytes for b in images]
                    )
                    if cached_pipeline:
                        st.session_state["stage1_result"] = cached_pipeline["stage1"]
                        st.session_state["stage2_result"] = cached_pipeline["stage2"]
                        st.session_state["stage2_confirmed"] = None
                        st.session_state["stage3_result"] = cached_pipeline["stage3"]
                        st.toast("시연 모드: 캐시된 결과로 재현 완료", icon="🎬")
                        if not classic_mode:
                            _go_to_step("supplement")
                        st.rerun()
                    else:
                        st.error(
                            "이 사진은 캐시에 없습니다. API 키를 설정하거나 "
                            "시연 모드 샘플 사진(화학실/물리실)을 사용하세요."
                        )
                        st.stop()

                st.info(
                    f"⏱ 예상 소요 시간 약 **{est_total}초** "
                    f"(사진 {n_imgs}장 · 캐시 적중 시 즉시). "
                    f"공급자: {current_provider_label()}"
                )

                # 이미지 품질 사전 검사
                if st.session_state.get("image_quality_check", True):
                    issues_found: list[str] = []
                    for label, img_bytes in zip(labels, images):
                        rep = analyze_and_optimize(img_bytes)
                        if rep.issues:
                            issues_found.append(f"**{label}** — " + "; ".join(rep.issues))
                    if issues_found:
                        st.error(
                            "다음 사진들은 AI 인식이 어려울 수 있습니다. 재촬영을 권장합니다:\n\n"
                            + "\n".join(f"- {x}" for x in issues_found)
                            + "\n\n그래도 진행하려면 설정에서 '이미지 품질 사전 검사'를 끄세요."
                        )
                        st.stop()

                prog = st.progress(0, text="단계 1/3 · 공간 유형 식별 중…")
                pipeline_ok = False
                try:
                    # 교차 검증 (선택)
                    if st.session_state.get("cross_check", False):
                        cc = run_stage1_cross_check(images, use_cache=use_cache)
                        st.session_state["stage1_cross_check"] = cc
                        # 합의 결과를 stage1_result로 사용
                        if cc.get("consensus"):
                            anth = cc.get("by_provider", {}).get("anthropic", {})
                            s1 = anth or next(iter(cc["by_provider"].values()))
                            s1 = dict(s1)
                            s1["space_type_primary"] = cc["consensus"]
                            s1["_cached"] = False
                            s1["_cross_check_agreement"] = cc["agreement"]
                        else:
                            s1 = run_stage1(images, use_cache=use_cache, image_labels=labels)
                    else:
                        s1 = run_stage1(images, use_cache=use_cache, image_labels=labels)
                    st.session_state["stage1_result"] = s1
                    prog.progress(33, text=f"단계 1 완료 · {s1.get('_elapsed_sec','?')}초")

                    space_type = s1.get("space_type_primary") or space["type"]
                    prog.progress(40, text="단계 2/3 · 안전 설비 탐지 중…")
                    s2 = run_stage2(images, space_type, use_cache=use_cache,
                                    image_labels=labels)
                    st.session_state["stage2_result"] = s2
                    st.session_state["stage2_confirmed"] = None
                    prog.progress(66, text=f"단계 2 완료 · {s2.get('_elapsed_sec','?')}초")

                    prog.progress(75, text="단계 3/3 · 맞춤 점검표 생성 중…")
                    s3 = run_stage3(s1, s2, use_cache=use_cache)
                    st.session_state["stage3_result"] = s3
                    prog.progress(100, text=f"단계 3 완료 · {s3.get('_elapsed_sec','?')}초")
                    pipeline_ok = True
                except Exception as e:
                    err_msg = str(e).lower()
                    if "rate" in err_msg or "429" in err_msg:
                        hint = "API 호출 한도를 초과했습니다. 1~2분 후 다시 시도하세요."
                    elif "auth" in err_msg or "401" in err_msg or "403" in err_msg:
                        hint = "API 키가 잘못되었거나 만료되었습니다. 설정 페이지에서 키를 확인하세요."
                    elif "timeout" in err_msg or "503" in err_msg or "502" in err_msg:
                        hint = "공급자 서버가 일시적으로 응답하지 않습니다. 잠시 후 재시도하세요."
                    elif "network" in err_msg or "connection" in err_msg:
                        hint = "네트워크 연결을 확인해 주세요."
                    else:
                        hint = "잠시 후 다시 시도하세요. 반복되면 사진을 줄이거나 공급자를 교체해 보세요."
                    friendly_error("AI 점검표 생성", e, hint=hint)

                # try 바깥에서 페이지 이동 (rerun이 except 블록을 막지 않도록)
                if pipeline_ok and not classic_mode:
                    _go_to_step("supplement")

# 결과 데이터 참조 (모든 스텝에서 필요)
s1 = st.session_state.get("stage1_result")
s2 = st.session_state.get("stage2_result")
s3 = st.session_state.get("stage3_result")

# 스텝별 게이트
_show_stage1 = classic_mode or step in ("ai_run", "supplement", "review")
_show_stage2_confirm = classic_mode or step in ("supplement", "review")
_show_checklist_and_score = classic_mode or step == "review"

if s1 and _show_stage1:
    st.markdown("<div class='sl-num' style='margin-top:18px;'>결과 01</div>"
                "<div class='sl-h'>공간 유형 식별</div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.metric("공간 유형", s1.get("space_type_primary", "-"))
    with col2:
        conf = s1.get("confidence", 0) or 0
        st.metric("신뢰도", f"{float(conf)*100:.0f}%")
    with col3:
        tag = "캐시" if s1.get("_cached") else "신규"
        st.metric(f"처리 시간({tag})", f"{s1.get('_elapsed_sec','?')}초")
    # 교차검증 결과 표시 (ERROR 경우 포함)
    cc = st.session_state.get("stage1_cross_check")
    if cc and cc.get("by_provider"):
        agree = cc.get("agreement")
        has_error = any("error" in r for r in cc["by_provider"].values())
        if has_error:
            errs = [f"{pid}: {r['error'][:60]}" for pid, r in cc["by_provider"].items()
                    if "error" in r]
            st.warning(f"교차검증 일부 공급자 실패 — {'; '.join(errs)}")
        elif agree:
            st.success(f"교차검증 합의 ✓ — 두 공급자 모두 '{cc.get('consensus')}'로 판정")
        else:
            results_str = ", ".join(
                f"{pid}={r.get('space_type_primary', 'ERROR')}"
                for pid, r in cc["by_provider"].items()
            )
            st.warning(f"교차검증 불일치 — {results_str}")

    if s1.get("evidence"):
        with st.expander("판단 근거"):
            for ev in s1["evidence"]:
                st.markdown(f"- {ev}")

# (C) 단계 2 결과 사용자 확정
if s2 and _show_stage2_confirm:
    st.markdown("<div class='sl-num' style='margin-top:18px;'>결과 02</div>"
                "<div class='sl-h'>설비 탐지 · 사용자 확정</div>"
                "<div class='sl-h-sub'>AI 결과를 확인하고 필요 시 수정하세요. 수정 내역은 AI 재학습에 활용됩니다.</div>",
                unsafe_allow_html=True)

    detected = s2.get("detected_equipment", []) or []
    absent = s2.get("likely_absent_equipment", []) or []
    ambiguous = s2.get("ambiguous_items", []) or []

    confirmed = st.session_state.get("stage2_confirmed") or {
        "detected_equipment": [dict(x) for x in detected],
        "likely_absent_equipment": [dict(x) for x in absent],
        "ambiguous_items": list(ambiguous),
        "user_corrections": [],
    }

    tab_d, tab_a, tab_m = st.tabs(
        [f"탐지 {len(detected)}개", f"부재 {len(absent)}개", f"모호 {len(ambiguous)}개"]
    )

    with tab_d:
        st.caption("AI가 사진에서 실제로 확인한 설비입니다. `출처 사진`은 AI가 판단 근거로 삼은 사진입니다.")
        keep_d = []
        for i, item in enumerate(confirmed["detected_equipment"]):
            key = f"detected_{i}"
            ref = item.get("image_ref") or item.get("note_ref") or "-"
            checked = st.checkbox(
                f"**{item.get('name','?')}** — {item.get('status','')} · "
                f"{item.get('category','')}  \n"
                f"<span style='color:#9A9A9F;font-size:11px'>출처 사진: {ref}</span>",
                value=True, key=key,
            )
            if checked:
                keep_d.append(item)
            else:
                confirmed["user_corrections"].append({"type": "remove_detected", "item": item})
        confirmed["detected_equipment"] = keep_d

    with tab_a:
        st.caption("AI가 '없다'고 판단한 설비입니다. 실제로 있다면 체크하세요 → 탐지됨으로 이동합니다.")
        keep_a = []
        move_to_detected = []
        for i, item in enumerate(confirmed["likely_absent_equipment"]):
            key = f"absent_{i}"
            actually_exists = st.checkbox(
                f"**{item.get('name','?')}** — 실제로 존재함",
                value=False, key=key, help=item.get("reason", ""),
            )
            if actually_exists:
                move_to_detected.append({
                    "category": item.get("category", ""),
                    "name": item.get("name", ""),
                    "status": "존재확인(사용자 수정)",
                    "note": "사용자가 부재→탐지로 수정",
                })
                confirmed["user_corrections"].append({"type": "absent_to_detected", "item": item})
            else:
                keep_a.append(item)
        confirmed["likely_absent_equipment"] = keep_a
        confirmed["detected_equipment"].extend(move_to_detected)

    with tab_m:
        st.caption("AI가 확신하지 못한 항목입니다. 하나씩 판단해 주세요.")
        resolved = []
        for i, item_text in enumerate(confirmed["ambiguous_items"]):
            key = f"ambig_{i}"
            decision = st.radio(
                item_text,
                ["판단 유보", "존재함 (탐지)", "없음 (부재)"],
                key=key, horizontal=True,
            )
            resolved.append({"text": item_text, "decision": decision})
            if decision != "판단 유보":
                confirmed["user_corrections"].append({
                    "type": f"ambig_resolved_{decision}",
                    "item": item_text,
                })
        confirmed["ambiguous_resolutions"] = resolved

    # 자동 저장 (매 rerun) — 별도 버튼 불필요
    st.session_state["stage2_confirmed"] = confirmed
    st.caption(
        f"수정 사항은 자동 저장됩니다 · "
        f"기록된 사용자 수정 {len(confirmed.get('user_corrections', []))}건"
    )

# 단계 3 결과
if s3 and _show_checklist_and_score:
    divider()
    st.markdown("<div class='sl-num'>결과 03</div>"
                "<div class='sl-h'>맞춤 점검표</div>", unsafe_allow_html=True)
    items = s3.get("items", []) or []
    st.caption(f"{s3.get('checklist_name','-')} · 총 {len(items)}개 항목")
    if s3.get("rationale"):
        st.info(f"맞춤화 근거: {s3['rationale']}")
    if items:
        df = pd.DataFrame(items)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ─────────────────────────────────────────
    # (D) 현장 점검
    # ─────────────────────────────────────────
    divider()
    section("03", "현장 점검 입력", "AI가 생성한 점검표에 현장 결과를 입력하세요.")

    if st.session_state.get("demo_mode"):
        col_a, col_b, col_c = st.columns(3)
        if col_a.button("전체 '양호'로 채우기", use_container_width=True):
            st.session_state["item_scores"] = {str(itm.get("no")): 1.0 for itm in items}
            st.rerun()
        if col_b.button("무작위 샘플 채우기", use_container_width=True):
            import random
            random.seed(42)
            st.session_state["item_scores"] = {
                str(itm.get("no")): random.choice([1.0, 1.0, 0.5, 0.0]) for itm in items
            }
            st.rerun()
        if col_c.button("입력 초기화", use_container_width=True):
            st.session_state["item_scores"] = {}
            st.rerun()

    scores: dict[str, float] = dict(st.session_state.get("item_scores") or {})
    for itm in items:
        no = str(itm.get("no"))
        basis = itm.get("basis") or ""
        basis_html = (f"<div style='color:#9A9A9F;font-size:11px;margin-top:2px;'>"
                      f"근거: {basis}</div>" if basis else "")
        st.markdown(
            f"<div style='padding:10px 0 2px 0;'>"
            f"<b style='color:#D50000'>{itm.get('no')}.</b> {itm.get('title','')}"
            f"{basis_html}</div>",
            unsafe_allow_html=True,
        )
        try:
            current = float(scores.get(no, 1.0))
        except (TypeError, ValueError):
            current = 1.0
        idx = [1.0, 0.5, 0.0].index(current) if current in [1.0, 0.5, 0.0] else 0
        val = st.radio(
            "충족도",
            options=[1.0, 0.5, 0.0],
            format_func=lambda x: {1.0: "양호", 0.5: "불량", 0.0: "부재"}[x],
            index=idx, horizontal=True, key=f"score_{no}",
            label_visibility="collapsed",
        )
        scores[no] = val
    st.session_state["item_scores"] = scores

    # (E) 점수 계산
    divider()

    # 2-16 수정: 매핑 결과 미리보기 + 매핑 실패 시 수동 매핑 UI
    from modules.laws import STANDARD_ITEMS

    def _map_items_to_std(items_list: list[dict]) -> tuple[dict, list[str]]:
        """AI 점검표 항목 → 표준 항목 매핑 + 매핑 실패 목록 반환."""
        t2s = {}
        unmapped_items = []
        for itm in items_list:
            haystack = (itm.get("title", "") + " " + itm.get("category", "")
                        + " " + (itm.get("basis") or ""))
            matched_std = None
            for std in STANDARD_ITEMS:
                if std in haystack:
                    matched_std = std
                    break
            if matched_std:
                t2s[str(itm.get("no"))] = matched_std
            else:
                unmapped_items.append(str(itm.get("no")))
        return t2s, unmapped_items

    auto_map, unmapped = _map_items_to_std(items)
    total_items = len(items)
    mapped_ratio = (len(auto_map) / total_items) if total_items else 0

    # 매핑 실패가 있으면 수동 매핑 UI 노출
    if total_items and (mapped_ratio < 0.7 or unmapped):
        pct = int(mapped_ratio * 100)
        st.warning(
            f"⚠ 자동 매핑 결과: **{len(auto_map)}/{total_items}** 항목만 표준 설비에 자동 연결되었습니다 "
            f"({pct}%). 미매핑 항목을 수동으로 지정하면 점수·추천 정확도가 향상됩니다."
        )
        with st.expander(f"수동 매핑 · 미매핑 {len(unmapped)}건 지정", expanded=False):
            manual_map = dict(st.session_state.get("_manual_std_map") or {})
            for itm in items:
                no = str(itm.get("no"))
                if no not in unmapped:
                    continue
                current = manual_map.get(no, "(미지정)")
                opts = ["(미지정)"] + STANDARD_ITEMS
                idx = opts.index(current) if current in opts else 0
                sel = st.selectbox(
                    f"{no}. {itm.get('title','')}",
                    options=opts, index=idx, key=f"map_sel_{no}",
                )
                if sel != "(미지정)":
                    manual_map[no] = sel
                elif no in manual_map:
                    manual_map.pop(no)
            st.session_state["_manual_std_map"] = manual_map

    if st.button("안전 점수 계산 · 추천 생성", type="primary", use_container_width=True):
        title_to_std = dict(auto_map)
        # 수동 매핑 오버라이드 (사용자 지정이 자동 매핑을 덮어씀)
        for k, v in (st.session_state.get("_manual_std_map") or {}).items():
            title_to_std[k] = v

        std_scores: dict[str, float] = {}
        for no, val in scores.items():
            std = title_to_std.get(no)
            if std and std not in std_scores:
                std_scores[std] = val

        if not std_scores:
            st.error(
                "매핑된 표준 설비가 하나도 없어 점수 계산이 불가합니다. "
                "위의 '수동 매핑' 을 펼쳐 1건 이상 지정하거나 AI 점검표를 재생성하세요."
            )
            st.stop()

        # 공간 유형(+층수) 을 점수·추천에 전달 — 해당 공간에 적용 항목만 사용
        _space_type = (space or {}).get("type")
        _floor = None  # TODO: 층수 입력 UI 가 생기면 여기 결합
        result = calculate_safety_score(std_scores, space_type=_space_type, floor=_floor)
        st.session_state["score_result"] = result
        st.session_state["recommendations"] = recommend_from_scores(
            std_scores, space_type=_space_type, floor=_floor
        )
        st.success(
            f"계산 완료 · 공간({_space_type or '전체'}) 적용 표준 설비 {len(std_scores)}건"
        )
        st.rerun()

# 점수 결과
sr = st.session_state.get("score_result")
if sr and _show_checklist_and_score:
    divider()
    section("04", "안전 점수 결과")

    c1, c2, c3 = st.columns(3)
    c1.metric("종합 점수", f"{sr['score']}점")
    c2.metric("등급", sr["grade"])
    desc = sr.get("grade_description", "") or ""
    c3.metric("등급 설명", desc[:24] + ("…" if len(desc) > 24 else ""))

    # 게이지
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=sr["score"],
        domain={'x': [0, 1], 'y': [0, 1]}, title=None,
        gauge={
            'axis': {'range': [0, 100], 'tickcolor': "#6B6B70"},
            'bar': {'color': "#D50000"},
            'steps': [
                {'range': [0, 60], 'color': "#FFEBEB"},
                {'range': [60, 80], 'color': "#FFF5E0"},
                {'range': [80, 100], 'color': "#E8F5E9"},
            ],
            'bordercolor': "#E5E5E8",
        }
    ))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=20),
                      paper_bgcolor="#FFFFFF", font=dict(family="Inter, Pretendard, sans-serif"))
    st.plotly_chart(fig, use_container_width=True)

    # 레이더
    cats = sr.get("category_scores") or {}
    if cats:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatterpolar(
            r=[cats[c]["score"] for c in CATEGORIES if c in cats],
            theta=[c for c in CATEGORIES if c in cats],
            fill="toself", line_color="#D50000", fillcolor="rgba(213,0,0,0.15)",
            name="카테고리 점수",
        ))
        fig2.update_layout(
            polar={'radialaxis': {'visible': True, 'range': [0, 100], 'gridcolor': "#E5E5E8"}},
            showlegend=False, height=340, margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig2, use_container_width=True)

    divider()
    colL, colR = st.columns([1, 1])
    with colL:
        if st.button("다른 공간 이어서 점검", use_container_width=True):
            from modules.session import reset_inspection
            reset_inspection()
            st.session_state["shots"] = _shots_dict()
            st.switch_page("pages/1_점검시작.py")
    with colR:
        if st.button("결과 저장·발송으로 →", type="primary", use_container_width=True):
            st.switch_page("pages/3_결과저장.py")
