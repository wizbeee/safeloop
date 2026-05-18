"""
Step 3~5 — 사진 촬영 + AI 3단계 파이프라인 + 설비 사용자 확정 + 현장 점검.

촬영 UI — 샷별 카드 (명칭 가이드 문구 카메라 촬영 결과):
공간 무관 공통 6샷. 각 샷마다 독립된 카메라 위젯. 최소 3샷 이상 확보 시 AI 분석 활성화.
"""
from __future__ import annotations


import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.ai_vision import (
    api_key_available, current_provider_label,
    has_cached_demo_results, load_demo_pipeline_for_samples, samples_hit_cache,
    run_stage1, run_stage2, run_stage3,
)
from modules.image_quality import analyze_and_optimize
from modules.laws import CATEGORIES
from modules.recommend import recommend_from_scores
from modules.score import calculate_safety_score
from modules.session import ensure_state, require_school
from modules.ui import (
    apply_theme, divider, friendly_error, hero, mask_school_name,
    render_sidebar, section, confirm_button,
)

st.set_page_config(page_title="AI 점검 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="collapsed")
apply_theme()
ensure_state()
render_sidebar(active_key="ai")

school = require_school()
if not school:
    if st.button("학교 찾기로", key="ai_noschool_back",
                  width="stretch"):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

space = st.session_state.get("active_space")
if not space:
    st.warning("점검할 공간이 선택되지 않았습니다.")
    if st.button("공간 선택으로", key="ai_nospace_back",
                  width="stretch"):
        st.switch_page("pages/1_점검시작.py")
    st.stop()

hero(
    "단계 2 — AI 점검",
    "AI 점검",
    f"{mask_school_name(school['학교명'])} · {space['type']}"
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
        "guide": "교탁(또는 실험대) 앞에 서서 학생석을 향해 촬영하세요.",
        "required": True,
    },
    {
        "key": "center_window",
        "no": "03",
        "title": "공간 중앙 창문쪽",
        "guide": "공간 한가운데에 서서 창문 방향을 촬영하세요.",
        "required": True,
    },
    {
        "key": "center_corridor",
        "no": "04",
        "title": "공간 중앙 복도쪽",
        "guide": "공간 한가운데에서 복도(반대편 벽) 방향을 촬영하세요.",
        "required": True,
    },
    {
        "key": "center_front_door",
        "no": "05",
        "title": "공간 중앙 앞문쪽",
        "guide": "공간 한가운데에서 앞문 방향을 촬영하세요.",
        "required": True,
    },
    {
        "key": "center_back_door",
        "no": "06",
        "title": "공간 중앙 뒷문쪽",
        "guide": "공간 한가운데에서 뒷문(또는 후면 벽) 방향을 촬영하세요.",
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
        "title": "보완 촬영 · 모호 판정 항목만 (선택)",
        "guide": "AI가 **모호** 또는 **부재 의심** 으로 판정한 설비만 가까이 추가 촬영하세요. "
                 "예: 가려진 캐비닛 뒤·사각지대.",
        "required": False,
    },
]


from modules.storage import (
    save_draft_shots, load_draft_shots, has_draft, draft_summary, clear_draft,
)


def _shots_dict() -> dict:
    """세션에 샷별 저장소 초기화 — 각 샷은 사진 리스트."""
    return {s["key"]: [] for s in SHOTS}


# 세션 초기화 + 구 스키마 마이그레이션 (dict list)
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


def _persist_draft() -> None:
    """샷 변경 시마다 호출 — 디스크에 자동 백업 (학교+공간 단위).

    백업 실패는 사용자 흐름을 차단하지 않지만, 토스트로 알림.
    실패가 반복되면 작업 손실 위험이므로 사용자가 인지하고 다른 조치
    (수동 다운로드 등) 를 할 수 있도록.
    """
    try:
        save_draft_shots(school_code, shots_state, space_id)
    except (OSError, IOError, PermissionError) as e:
        # 디스크/권한 문제 — 사용자에게 명시
        st.toast(f"드래프트 자동 백업 실패: {e.__class__.__name__}", icon=None)
    except Exception as e: # noqa: BLE001 — 그 외는 토스트만, 흐름 유지
        st.toast(f"드래프트 백업 중 예외: {e.__class__.__name__}", icon=None)


empty_now = sum(len(v) for v in shots_state.values()) == 0
# 시연 합성 응답 보호 — _synth_demo 마커가 있으면 사진이 비어 보여도 정리하지 않음.
# 시연 자동시작 경로에서 합성 응답을 먼저 set 한 후 페이지 진입 시 일시적으로 shots 가
# 비어보일 수 있는데, 그때 정리되면 사용자가 점검표를 영영 못 봄.
_s2_now = st.session_state.get("stage2_result") or {}
_s3_now = st.session_state.get("stage3_result") or {}
_is_synth_demo_result = bool(
    (isinstance(_s2_now, dict) and _s2_now.get("_synth_demo"))
    or (isinstance(_s3_now, dict) and _s3_now.get("_synth_demo"))
)
has_stale_results = (
    empty_now
    and not _is_synth_demo_result
    and any(
        st.session_state.get(k)
        for k in ["stage1_result", "stage2_result", "stage3_result"]
    )
)
if has_stale_results and not st.session_state.get("_draft_restored"):
    # 사진 없는데 이전 AI 결과만 남은 경우 확실히 초기화
    for _k in ["stage1_result", "stage2_result", "stage2_confirmed",
                "stage3_result", "item_scores",
                "score_result", "recommendations"]:
        st.session_state[_k] = None
    st.toast("이전 분석 결과를 정리했습니다 (사진이 비어있음)", icon=None)

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
                      width="stretch"):
            restored = load_draft_shots(school_code, space_id)
            for k, v in restored.items():
                shots_state[k] = v
            st.session_state["_draft_restored"] = True
            st.rerun()
    with rc2:
        if st.button("새로 시작", key="discard_draft", width="stretch"):
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
    ("shoot_1", "01 입구 대각선", "entrance_diag"),
    ("shoot_2", "02 앞 정면", "front_view"),
    ("shoot_3", "03 창문쪽", "center_window"),
    ("shoot_4", "04 복도쪽", "center_corridor"),
    ("shoot_5", "05 앞문쪽", "center_front_door"),
    ("shoot_6", "06 뒷문쪽", "center_back_door"),
    ("shoot_7", "07 천장", "ceiling"),
    ("shoot_8", "08 뒷문 대각선", "back_door_diag"), # 선택
    ("ai_run", "AI 분석", None),
    ("supplement", "보완", "close_supplement"),
    ("review", "결과", None),
]
_STEP_KEYS = [s[0] for s in WIZARD_STEPS]
_SHOT_OF_STEP = {s[0]: s[2] for s in WIZARD_STEPS}

if "wizard_step" not in st.session_state:
    st.session_state["wizard_step"] = "shoot_1"
# 방어: 잘못된 스텝 값 리셋
if st.session_state["wizard_step"] not in _STEP_KEYS:
    st.session_state["wizard_step"] = "shoot_1"

# 자동재생 진입 — 필수 컷 중 일정 비율 이상 채워지면 ai_run 스텝으로 점프
# 샘플 폴더에 7컷 전체가 없는 경우(시연용)도 진행 가능하도록 임계 80%.
#
# 주의(2026-04-26): 새 시연 흐름에서는 app.py 가 시연 시작 시 stage2/3 합성 응답을
# 직접 주입하고 _autoplay_consumed=True + wizard_step="supplement" 로 설정하므로
# 아래 블록은 보통 skip 됩니다. 다음 환경에서만 실행됨:
# - 외부에서 _autoplay 만 켜고 _autoplay_consumed 안 켠 경우
# - 또는 새 흐름으로 마이그레이션 안 된 진입점에서 호출 시 fallback
# 죽은 코드 같지만 fallback 안전망으로 유지.
if st.session_state.get("_autoplay") and not st.session_state.get("_autoplay_consumed"):
    _required_keys_auto = [
        "entrance_diag", "front_view", "center_window", "center_corridor",
        "center_front_door", "center_back_door", "ceiling",
    ]
    _filled = sum(1 for k in _required_keys_auto
                  if st.session_state.get("shots", {}).get(k))
    if _filled >= 5: # 7개 중 5개 이상 = 71% 이상이면 진행 (3장 광각 + 천장만 있어도 가능)
        st.session_state["wizard_step"] = "ai_run"
        st.session_state["_autoplay_consumed"] = True

# 모드 토글은 고급 옵션 — 기본은 위저드(한 구도씩 단계별).
# 모드 이중성 노출이 사용자 혼란 원인이므로 expander 안으로 숨김.
with st.expander("화면 모드 변경 (선택)", expanded=False):
    st.caption(
        "기본은 **위저드 모드** (한 구도씩 단계별로 안내). "
        "PC 큰 화면에서 모든 구도를 한 번에 보고 싶으면 클래식 모드로 전환할 수 있습니다."
    )
    classic_mode = st.toggle(
        "클래식 모드 (전체 한 번에 보기)",
        value=st.session_state.get("classic_mode", False),
        key="classic_mode",
        help="OFF(기본): 한 구도씩 위저드. ON: 모든 구도가 한 화면.",
    )

# 모드 전환 감지 — 위저드로 돌아올 때 현재 진행에 맞춰 wizard_step 자동 재계산
_prev_classic = st.session_state.get("_prev_classic_mode")
if _prev_classic is not None and _prev_classic != classic_mode and not classic_mode:
    # 클래식 위저드 전환 시점만 처리 (위저드 클래식은 단계 무관)
    if st.session_state.get("score_result"):
        st.session_state["wizard_step"] = "review"
    elif st.session_state.get("stage2_result"):
        st.session_state["wizard_step"] = "supplement"
    elif any(len(v) > 0 for v in (st.session_state.get("shots") or {}).values()):
        st.session_state["wizard_step"] = "ai_run"
    else:
        st.session_state["wizard_step"] = "shoot_1"
st.session_state["_prev_classic_mode"] = classic_mode

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
    if count:
        status_html = f"<span class='sl-status-ok'>{count}장 촬영됨</span>"
    elif s["required"]:
        status_html = (
            "<span class='sl-status-empty' "
            "style='color:#D50000;font-weight:600;'>촬영 필요 (필수)</span>"
        )
    else:
        status_html = "<span class='sl-status-empty'>촬영 대기 (선택)</span>"
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
                             width="stretch")
                    if st.button("삭제", key=f"del_{key}_{idx}", width="stretch"):
                        photos.pop(idx)
                        _persist_draft()
                        st.rerun()

        counter_key = f"cam_ctr_{key}"
        if counter_key not in st.session_state:
            st.session_state[counter_key] = 0
        upload_widget_key = f"up_{key}_{st.session_state[counter_key]}"
        camera_widget_key = f"cam_{key}_{st.session_state[counter_key]}"

        # 두 입력 방식 — 카메라 직접 촬영 + 갤러리·파일 업로드
        # 사용자는 모바일에서는 카메라, PC 에서는 파일 업로드 선택
        cam_tab, upload_tab = st.tabs([
            "카메라로 직접 촬영", "갤러리·파일에서 업로드",
        ])

        new_photos: list = []

        with cam_tab:
            st.markdown(
                "<div style='font-size:12px;color:#6B6B70;margin-bottom:4px;'>"
                "<b>촬영 시작</b> 버튼을 누르면 카메라가 바로 실행됩니다 "
                "(허용 후 사용 가능 · 모바일에서 가장 편함)."
                "</div>",
                unsafe_allow_html=True,
            )
            cam_shot = st.camera_input(
                "촬영 시작",
                key=camera_widget_key,
                label_visibility="visible",
            )
            if cam_shot is not None:
                new_photos.append((cam_shot.name or f"{key}_cam.jpg",
                                    cam_shot.getvalue()))

        with upload_tab:
            st.markdown(
                "<div style='font-size:12px;color:#6B6B70;margin-bottom:4px;'>"
                "<b>파일 선택</b> 버튼을 누르면 갤러리·파일 탐색기가 열립니다 "
                "(여러 사진 동시 선택 가능)."
                "</div>",
                unsafe_allow_html=True,
            )
            snaps = st.file_uploader(
                "파일 선택",
                type=["jpg", "jpeg", "png", "webp", "heic"],
                accept_multiple_files=True,
                key=upload_widget_key,
                label_visibility="visible",
            )
            if snaps:
                heic_warned = False
                for f in snaps:
                    fname_lower = (f.name or "").lower()
                    # HEIC (iPhone 기본 포맷) 안내 — 일부 PC 브라우저에서 미리보기 미지원
                    if fname_lower.endswith(".heic") and not heic_warned:
                        st.warning(
                            "**HEIC 파일 안내** — iPhone 기본 카메라 포맷입니다. "
                            "AI 분석은 가능하나 일부 PC 브라우저에서 미리보기가 안 보일 수 있습니다. "
                            "iPhone 설정 카메라 형식 **'호환성 우선'**(JPEG) 으로 바꾸면 PC에서도 즉시 미리보기 가능."
                        )
                        heic_warned = True
                    new_photos.append((f"{key}_{len(photos)+1}.jpg", f.getvalue()))

        if new_photos:
            added = 0
            rejected = 0
            existing_bytes = {p["bytes"] for p in photos}
            for fname, b in new_photos:
                if b not in existing_bytes:
                    photos.append({
                        "name": fname,
                        "bytes": b,
                        "source": "camera",
                    })
                    existing_bytes.add(b)
                    added += 1
                else:
                    rejected += 1
            if rejected:
                st.toast(
                    f"중복 사진 {rejected}장은 건너뜀 (같은 바이트)",
                    icon=None,
                )
            if added:
                st.session_state[counter_key] += 1
                _persist_draft()
                st.rerun()
            elif rejected:
                st.session_state[counter_key] += 1
                st.rerun()

        if photos:
            if st.button("이 구도 전체 비우기", key=f"clear_shot_{key}"):
                shots_state[key] = []
                st.session_state[counter_key] = st.session_state.get(counter_key, 0) + 1
                _persist_draft()
                st.rerun()

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)


def _prefill_item_scores_from_stage2(stage2_confirmed: dict,
                                      items: list,
                                      current_scores: dict) -> dict:
    """stage2_confirmed 의 detected/absent 정보를 점검표 라디오 기본값으로 매핑.

    Stage 2 status 별 점수 매핑 (P0 — 이전엔 status 무시했음):
      - 존재확인 / 상태양호 → 1.0 (양호)
      - 상태불량               → 0.5 (불량)
      - likely_absent_equipment → 0.0 (부재)

    덮어쓰기 정책 (P1-#17):
      - 사용자가 명시적으로 정정한 항목(stage2_confirmed.user_corrections 에
        기록된 std)은 기존 점수가 있어도 덮어쓴다. 두 번째 [반영하기] 가
        no-op 이 되지 않도록 함.
      - 그 외 항목은 사용자 라디오 직접 입력 보존 (덮어쓰지 않음).
    """
    from modules.laws import find_std_match

    # 표준 설비명 std_name → 점수(1.0/0.5/0.0) 매핑.
    # 같은 std 가 여러 번 등장 시 더 낮은 점수가 이긴다 (안전 평가는 보수적).
    std_to_score: dict[str, float] = {}

    def _record(std: str, score: float) -> None:
        if std not in std_to_score or score < std_to_score[std]:
            std_to_score[std] = score

    for eq in (stage2_confirmed.get("detected_equipment") or []):
        if not isinstance(eq, dict):
            name, status = str(eq), "존재확인"
        else:
            name = eq.get("name", "")
            status = eq.get("status", "존재확인")
        std = find_std_match(name)
        if not std:
            continue
        if status == "상태불량":
            _record(std, 0.5)
        else:
            # 존재확인·상태양호·알 수 없는 값은 모두 양호로 (보수적 fallback).
            _record(std, 1.0)

    for eq in (stage2_confirmed.get("likely_absent_equipment") or []):
        name = eq.get("name", "") if isinstance(eq, dict) else str(eq)
        std = find_std_match(name)
        if std:
            _record(std, 0.0)

    # 사용자 명시 정정 — 두 번째 [반영하기] 에서도 덮어쓰기 강제.
    forced_stds: set[str] = set()
    for corr in (stage2_confirmed.get("user_corrections") or []):
        item = corr.get("item") if isinstance(corr, dict) else None
        name = (item.get("name") if isinstance(item, dict) else None) or ""
        std = find_std_match(name)
        if std:
            forced_stds.add(std)

    new_scores = dict(current_scores or {})
    for itm in items:
        no = str(itm.get("no", ""))
        if not no:
            continue
        title = itm.get("title", "")
        std = find_std_match(title)
        if not std or std not in std_to_score:
            continue
        if no in new_scores and std not in forced_stds:
            continue  # 기존 입력 보존 (단 사용자 정정 항목은 덮어쓰기)
        new_scores[no] = std_to_score[std]
    return new_scores


def _render_wizard_nav(prev_step: str | None, next_step: str | None,
                        next_label: str = "다음", next_disabled: bool = False,
                        next_type: str = "primary") -> None:
    """하단 이전/다음 버튼."""
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    c_prev, c_spacer, c_next = st.columns([1, 2, 1])
    with c_prev:
        if prev_step:
            if st.button("이전", key=f"nav_prev_{step}", width="stretch"):
                _go_to_step(prev_step)
    with c_next:
        if next_step:
            if st.button(next_label, key=f"nav_next_{step}",
                         width="stretch", disabled=next_disabled,
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
        "입구 대각선 앞 정면 중앙 4방향(창문/복도/앞문/뒷문) 천장 (뒷문 대각선, 있을 때) 순. "
        "AI 가 이 다각도 사진들로 <b>공간 레이아웃 + 안전 장비 위치</b>를 동시에 식별합니다. "
        "AI가 모호 판정한 항목만 맨 아래 <b>보완 촬영(선택)</b> 을 사용하세요."
        "</div>",
        unsafe_allow_html=True,
    )
    # 모바일 카메라 작동 안내 (iPhone Safari 는 HTTPS 환경에서만 카메라 가능)
    st.info(
        "**모바일 사용 시** — 촬영 버튼이 카메라 앱을 열지 않으면 다음을 확인하세요:\n\n"
        "- **iPhone Safari**: HTTPS 환경(https://...) 으로 접속해야 카메라 호출됨\n"
        "- **Android Chrome**: 첫 진입 시 카메라 권한 허용 필요\n"
        "- 그래도 안 되면 갤러리에서 사진 선택으로 대체 가능 (동일 기능)"
    )
else:
    _render_progress(step)

# 시연 모드 — 더미 이미지 일괄 채움 (실 사진 사용 X)
if st.session_state.get("demo_mode"):
    with st.expander("시연 모드 · 더미 이미지 일괄 채움", expanded=True):
        DEMO_SPACE_OPTIONS = [
            "일반교실", "화학실", "물리실", "생명과학실", "지구과학실",
            "기술실", "가정실", "음악실", "미술실",
        ]
        # 현재 등록된 공간이 있으면 그 유형을 기본값으로
        _current_type = (space or {}).get("type") if space else None
        _default_idx = (DEMO_SPACE_OPTIONS.index(_current_type)
                         if _current_type in DEMO_SPACE_OPTIONS else 1)
        sample_choice = st.selectbox(
            "어느 공간으로 더미 이미지를 만들까요?",
            DEMO_SPACE_OPTIONS,
            index=_default_idx,
            key="sample_choice",
        )
        st.caption(
            "DEMO 라벨 + 공간/위치 텍스트가 박힌 가공 이미지 7장을 즉석 생성합니다. "
            "실제 사진이 아니라 시연용 더미입니다 (저작권·프라이버시 우려 없음)."
        )
        if st.button("더미 이미지 7컷 채우기", width="stretch",
                      key="demo_fill_shots_btn"):
            # 방어 가드 — 시연 모드가 아니면 더미 채움 절대 금지 (UI 가드 + 이중화).
            # 운영 모드에서는 실 사진만 허용 → 더미가 실 데이터로 오염되는 사고 방지.
            if not st.session_state.get("demo_mode"):
                st.error(
                    "운영 모드에서는 더미 이미지를 사용할 수 없습니다. "
                    "[설정]에서 시연 모드를 켠 후 진행하세요."
                )
                st.stop()
            # 1) 더미 7컷 생성 — 실패 시 명시적 에러 (silent fail 금지)
            try:
                from modules.demo_image import make_all_demo_shots
                new_shots = make_all_demo_shots(sample_choice)
            except Exception as e:
                st.error(
                    f"더미 이미지 생성 실패 — {e.__class__.__name__}: {e}\n\n"
                    "PIL 폰트 로드 또는 sample_images 폴더 접근 문제일 수 있습니다."
                )
                st.stop()
            # 2) 세션 shots 직접 교체 (참조 + 본체 모두) — 마이그레이션 충돌 방지
            _new_shots_full = {s["key"]: new_shots.get(s["key"], []) for s in SHOTS}
            st.session_state["shots"] = _new_shots_full
            # shots_state 참조도 갱신 (이후 같은 핸들러 내에서 사용 가능하도록)
            shots_state.clear()
            shots_state.update(_new_shots_full)
            # 3) 이전 AI 결과 클리어 — 새 사진으로 새 분석 받도록
            for k in ["stage1_result", "stage2_result", "stage2_confirmed",
                       "stage3_result", "item_scores", "score_result",
                       "recommendations"]:
                st.session_state[k] = None
            # 4) 더미 hash 기준 Stage 2/3 캐시 자동 보장 — 다음 단계 즉시 작동
            try:
                from modules.ai_vision import ensure_demo_cache_for_shots
                ensure_demo_cache_for_shots(_new_shots_full, sample_choice)
            except Exception as e:
                # 캐시 보장 실패해도 즉석 합성 폴백이 있으므로 흐름 유지
                st.toast(
                    f"캐시 보장 경고 ({e.__class__.__name__}) — 즉석 합성으로 대체",
                    icon=None,
                )
            # 5) draft 저장 — school/space 미인증이면 silent skip (시연 모드 가능)
            try:
                _persist_draft()
            except Exception:
                pass
            # 6) 채움 결과 — 필수 7컷 확인 후 사용자에게 명확한 안내
            _filled_n = sum(
                1 for k in ("entrance_diag", "front_view", "center_window",
                            "center_corridor", "center_front_door",
                            "center_back_door", "ceiling")
                if _new_shots_full.get(k)
            )
            if _filled_n < 7:
                st.warning(
                    f"더미 채움 결과 필수 {_filled_n}/7컷 — "
                    "코드 버그일 수 있습니다. 다른 공간 선택 후 재시도해 보세요."
                )
            # 7) 위저드 모드면 ai_run 으로 이동 — 사용자가 다음에 뭘 할지 명확
            if not classic_mode:
                st.session_state["wizard_step"] = "ai_run"
            st.toast(
                f"{sample_choice} 더미 이미지 채움 완료 ({_filled_n}/7컷)",
                icon=None,
            )
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

        is_last_required = (step == "shoot_7") # 7번까지 필수, 8번(뒷문 대각선) 은 선택
        next_label = (
            "다음 구도" if step != "shoot_8" else
            "AI 분석 단계로"
        )
        # 8번 (뒷문 대각선) 은 선택이므로 미촬영이어도 진행 허용
        if step == "shoot_8":
            next_step = "ai_run"
            next_label = "AI 분석 단계로"

        _render_wizard_nav(
            prev_step=prev_step,
            next_step=next_step,
            next_label=next_label,
            next_disabled=(not shot_done),
        )

        if step == "shoot_7" and shot_done:
            st.caption(
                "**뒷문이 있다면** 다음 단계(08 뒷문 대각선)에서 한 장 더 찍어주세요. "
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
                        st.image(ps[0]["bytes"], width="stretch")
                    else:
                        if shot.get("required"):
                            st.warning("미촬영")
                        else:
                            st.caption("(선택 — 건너뜀)")

        _render_wizard_nav(
            prev_step="shoot_8",
            next_step=None,
        ) # 다음은 AI 실행 버튼이 대신함

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
        # 마지막 재분석 시점의 보완 사진 개수 추적 — 새로 추가됐는데 재분석 안 했으면 알림
        last_reanalyzed_count = st.session_state.get(
            "_supplement_reanalyzed_count", 0
        )
        needs_reanalysis = (
            len(supplement_photos) > last_reanalyzed_count
        )

        if supplement_photos:
            if needs_reanalysis:
                st.error(
                    "**보완 사진이 추가되었지만 아직 재분석하지 않았습니다.** "
                    "지금 결과 단계로 넘어가면 보완 사진이 점수·점검표에 반영되지 않습니다. "
                    "아래 **'보완 사진으로 AI 재분석'** 을 먼저 눌러주세요."
                )
            if st.button("보완 사진으로 AI 재분석 (즉시)", type="primary",
                         width="stretch", key="rerun_ai_supplement"):
                # 재분석 트리거 + 카운트 갱신.
                # P0 (B1): 트리거 소비는 ai_run 블록 안의 line 916 에서 일어남.
                # supplement 단계에서 rerun 만 하면 step 이 그대로 supplement
                # 라 트리거가 영영 안 소비됨 → 사용자가 버튼 눌러도 무반응.
                # ai_run 으로 명시적으로 이동시켜 트리거가 소비되도록 함.
                st.session_state["_trigger_rerun_supplement"] = True
                st.session_state["_supplement_reanalyzed_count"] = (
                    len(supplement_photos)
                )
                _go_to_step("ai_run")

        # supplement 단계의 [이전] 버튼은 여기서 (상단), [결과 단계로] 는
        # 페이지 가장 아래에 표시 (사용자가 결과 다 보고 마지막에 누르도록).
        _c_prev, _c_spacer = st.columns([1, 4])
        with _c_prev:
            if st.button("이전 (재분석)", key="nav_prev_supplement_top",
                          width="stretch"):
                _go_to_step("ai_run")
        if not supplement_photos:
            st.caption(
                "보완 촬영이 필요 없다면 아래 결과를 확인하고 "
                "페이지 가장 아래의 **[결과 단계로 ]** 버튼을 누르세요."
            )

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
# 위저드에서는 `ai_run` 스텝에서만 실행 UI를 노출.
# 실행 완료 시 자동으로 `supplement` 스텝으로 이동.
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
    is_demo = bool(st.session_state.get("demo_mode"))
    # Stage 1 호출 제거 후 Stage 2 캐시(`{img_hash}_{space_type}`) 정확 매칭 검사
    _opt_all = (
        [analyze_and_optimize(b).optimized_bytes for b in all_photos]
        if all_photos else []
    )
    _user_space = (space or {}).get("type")
    cache_match = samples_hit_cache(_opt_all, space_type=_user_space)
    cached_demo = cache_match and is_demo
    cached_possible = (
        has_cached_demo_results()
        and is_demo
        and not cache_match
    )

    # 시연 모드: API 키·캐시 무관하게 모든 기능 사용 가능 (즉석 합성 폴백 보장).
    # 운영 모드: 원래대로 API 키 필수.
    if is_demo:
        if key_ok:
            st.info(
                "**시연 모드 + API 키 감지** — 실제 API 호출로 진행합니다. "
                "키가 없어도 시연 모드는 합성 데이터로 끝까지 작동합니다."
            )
        elif cached_demo:
            st.info(
                "**시연 모드 — 캐시 폴백 활성화**\n\n"
                "현재 업로드된 사진이 이전에 분석된 캐시와 일치합니다. "
                "API 호출 없이 즉시 결과를 재현합니다."
            )
        else:
            st.info(
                "**시연 모드 — 합성 데이터로 진행**\n\n"
                "API 키 없이 진행 가능합니다. AI 분석 시작 시 공간 유형에 맞는 "
                "합성 응답이 즉시 생성되어 모든 단계를 끝까지 체험할 수 있습니다."
            )
    elif not key_ok and not cached_demo:
        provider_id = st.session_state.get("ai_provider") or "anthropic"
        env_var = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(
            provider_id, "API_KEY"
        )
        hint_cache = (
            "\n\n이전에 분석한 샘플 캐시가 남아 있습니다 — "
            "**샘플 사진(화학실/물리실)을 그대로 불러오면** 즉시 재현됩니다."
            if cached_possible else ""
        )
        st.warning(
            f"**AI 키가 감지되지 않았습니다** ({provider_id})\n\n"
            f"두 가지 방법 중 하나로 해결할 수 있습니다:\n"
            f"- `safeloop_app/.env` 에 `{env_var}=sk-...` 추가\n"
            f"- 사이드바 **설정 AI 공급자** 에서 키 입력"
            + hint_cache
            + "\n\n(또는 [설정]에서 **시연 모드**를 켜면 API 없이 전체 흐름 체험 가능)"
        )
    # 시연 모드는 키·캐시 무관 항상 진행 가능. 운영 모드는 키 또는 캐시 일치 필요.
    if key_ok or cached_demo or is_demo:
        col_a, col_b = st.columns([1, 3])
        with col_a:
            use_cache = st.checkbox("캐시 사용", value=True,
                                     help="동일 사진 재분석 시 API 호출 생략.")
        # 보완 재분석 트리거 자동 처리
        triggered_by_supplement = st.session_state.pop("_trigger_rerun_supplement", False)
        # 시연 자동 재생 트리거 (홈에서 넘어온 경우) — 1회만
        triggered_by_autoplay = (
            st.session_state.pop("_autoplay_run_ai", False)
            and analysis_ready
            and not st.session_state.get("stage3_result")
        )
        if triggered_by_autoplay:
            st.info("시연 시작 — 더미 이미지로 AI 분석을 즉시 실행합니다...")
        # 누락된 필수 컷 안내 — 어느 구도가 비었는지 명시
        missing_required = [s for s in SHOTS if s["required"] and not shots_state.get(s["key"])]
        if missing_required:
            missing_titles = " / ".join(f"{s['no']} {s['title']}" for s in missing_required)
            st.warning(
                f"**필수 컷 {len(missing_required)}건 누락** — {missing_titles}\n\n"
                f"필수 사진은 안전 점검의 정확도를 보장하기 위해 권장됩니다. "
                f"가능한 한 7컷 모두 촬영해주세요."
            )
        with col_b:
            run_disabled = not analysis_ready
            btn_label = (" AI 분석 시작 (설비 탐지 맞춤 점검표 생성)"
                         if analysis_ready else f"필수 {_MIN_REQUIRED_FILLED}컷 이상 촬영 후 활성화")
            user_clicked = st.button(btn_label, type="primary", width="stretch",
                                      disabled=run_disabled, key="run_ai_btn")
            if user_clicked or (triggered_by_supplement and analysis_ready) or triggered_by_autoplay:
                images = all_photos
                labels = all_labels
                # 사진 수 기반 예상 시간
                n_imgs = len(images)
                est_total = int(5 + 1.5 * n_imgs + 8 + 2.5 * n_imgs + 4)

                # 1) API 키 없을 때 시연 캐시 폴백 우선 시도
                if not key_ok:
                    # 시연 모드: 캐시가 있든 없든 합성 응답을 보장 (캐시 미스면 즉석 합성)
                    # → API 호출 0건 + 점검표가 항상 끝까지 표시됨.
                    cached_pipeline = load_demo_pipeline_for_samples(
                        [analyze_and_optimize(b).optimized_bytes for b in images],
                        space_type=space["type"],
                    )
                    if (not cached_pipeline) and is_demo:
                        # 캐시 없으면 즉석 합성 후 재시도
                        try:
                            from modules.ai_vision import ensure_demo_cache_for_shots
                            ensure_demo_cache_for_shots(
                                shots_state, space["type"],
                            )
                            cached_pipeline = load_demo_pipeline_for_samples(
                                [analyze_and_optimize(b).optimized_bytes for b in images],
                                space_type=space["type"],
                            )
                        except Exception:
                            cached_pipeline = None

                    if cached_pipeline:
                        st.session_state["stage1_result"] = cached_pipeline["stage1"]
                        st.session_state["stage2_result"] = cached_pipeline["stage2"]
                        st.session_state["stage2_confirmed"] = None
                        st.session_state["stage3_result"] = cached_pipeline["stage3"]
                        # 시연 모드는 supplement 를 건너뛰고 점검표(review)로 직행
                        # → 사용자가 핵심 결과물(맞춤 점검표)을 즉시 확인.
                        # 운영 모드(키 없는데 캐시만 적중하는 드문 케이스)는 기존대로 supplement.
                        if not classic_mode:
                            _go_to_step("review" if is_demo else "supplement")
                        st.toast(
                            ("시연 모드: 합성 응답으로 점검표까지 진행"
                             if is_demo else "캐시된 결과로 재현 완료"),
                            icon=None,
                        )
                        st.rerun()
                    elif is_demo:
                        st.error(
                            "시연 합성 응답 생성 실패 — 잠시 후 다시 시도하거나 "
                            "[설정]에서 공간 유형을 변경해 보세요."
                        )
                        st.stop()
                    else:
                        st.error(
                            "이 사진은 캐시에 없습니다. API 키를 설정하거나 "
                            "[설정]에서 **시연 모드**를 켜고 진행하세요."
                        )
                        st.stop()

                st.info(
                    f"예상 소요 시간 약 **{est_total}초** "
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

                # Stage 1 (공간 유형 식별) 은 호출하지 않음 — 담당자가 1_점검시작 페이지에서
                # 드롭다운으로 명시 선택했으므로 그 정보를 그대로 사용 (AI 비용·시간 절감).
                space_type = space["type"]
                s1 = {
                    "space_type_primary": space_type,
                    "confidence": 1.0,
                    "evidence": ["담당자가 점검 시작 페이지에서 명시 선택"],
                    "secondary_hypothesis": None,
                    "notes": "사용자 등록 정보 (Stage 1 AI 식별 생략 — 신뢰도 100%)",
                    "_elapsed_sec": 0.0,
                    "_provider": "user-input",
                    "_cached": False,
                    "_skipped": True,
                }
                st.session_state["stage1_result"] = s1

                prog = st.progress(0, text="① 안전 설비 탐지 중…")
                pipeline_ok = False
                try:
                    s2 = run_stage2(images, space_type, use_cache=use_cache,
                                    image_labels=labels)
                    st.session_state["stage2_result"] = s2
                    st.session_state["stage2_confirmed"] = None
                    # B5: 재분석 시 detected/absent 항목 수가 변할 수 있어
                    # 이전 stage2_user_marks 가 잘못된 항목에 매핑될 위험.
                    # 사용자 정정은 초기화 — 새 결과로 다시 보도록.
                    st.session_state.pop("stage2_user_marks", None)
                    # 라디오 위젯도 재생성 (prefill 적용)
                    st.session_state["_radio_counter"] = (
                        st.session_state.get("_radio_counter", 0) + 1
                    )
                    prog.progress(50, text=f"① 안전 설비 탐지 완료 · {s2.get('_elapsed_sec','?')}초")

                    prog.progress(60, text="② 맞춤 점검표 생성 중…")
                    s3 = run_stage3(s1, s2, use_cache=use_cache)
                    st.session_state["stage3_result"] = s3
                    prog.progress(100, text=f"② 맞춤 점검표 생성 완료 · {s3.get('_elapsed_sec','?')}초")
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

                # try 바깥에서 페이지 이동 (rerun이 except 블록을 막지 않도록).
                # 시연 모드는 supplement 를 건너뛰고 review 로 직행 → 점검표 즉시 표시.
                # 운영 모드는 기존대로 supplement 에서 정정 후 사용자가 review 진입.
                if pipeline_ok and not classic_mode:
                    _go_to_step("review" if is_demo else "supplement")

# 결과 데이터 참조 (모든 스텝에서 필요)
s1 = st.session_state.get("stage1_result")
s2 = st.session_state.get("stage2_result")
s3 = st.session_state.get("stage3_result")

# P1-#16: Stage 3 응답이 max_tokens 한계로 잘려 _recover_truncated_json 으로
# 부분 복구된 경우 사용자에게 명시. 안 알리면 27 항목 중 일부만 받고도
# 정상 결과로 인식해 누락 항목이 무점검으로 발송될 위험.
if isinstance(s3, dict) and s3.get("_truncated_recovered"):
    _recovered_n = len((s3 or {}).get("items") or [])
    st.warning(
        f"**AI 응답이 길어 일부만 복구되었습니다** — 점검표 {_recovered_n}개 항목만 "
        f"표시됩니다. 누락된 항목은 [전체 초기화] 후 재분석 또는 보완 촬영 후 "
        f"재분석으로 다시 받을 수 있습니다. 결과 저장 전 누락 항목 확인 권장."
    )

# 스텝별 게이트
_show_stage1 = classic_mode or step in ("ai_run", "supplement", "review")
_show_stage2_confirm = classic_mode or step in ("supplement", "review")
_show_checklist_and_score = classic_mode or step == "review"

if s1 and _show_stage1:
    st.markdown("<div class='sl-num' style='margin-top:18px;'>결과 01</div>"
                "<div class='sl-h'>점검 공간</div>", unsafe_allow_html=True)
    if s1.get("_skipped"):
        # 사용자 등록 정보 사용 — Stage 1 호출 생략
        col1, col2 = st.columns([2, 3])
        with col1:
            st.metric("공간 유형", s1.get("space_type_primary", "-"))
        with col2:
            st.markdown(
                "<div style='padding:14px 18px;background:#FAFAFA;"
                "border:1px solid #E5E5E8;border-left:3px solid #4CAF50;"
                "border-radius:6px;font-size:13px;line-height:1.7;'>"
                "<b style='color:#4CAF50;'>담당자 등록 정보</b><br>"
                "점검 시작 페이지에서 담당자가 직접 선택한 공간 유형입니다. "
                "AI 가 사진으로 공간을 다시 추정하지 않고 등록 정보를 그대로 사용합니다."
                "</div>",
                unsafe_allow_html=True,
            )
    else:
        # 호환: 구 캐시 등에서 _skipped 플래그 없는 경우
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.metric("공간 유형", s1.get("space_type_primary", "-"))
        with col2:
            conf = s1.get("confidence", 0) or 0
            st.metric("신뢰도", f"{float(conf)*100:.0f}%")
        with col3:
            tag = "캐시" if s1.get("_cached") else "신규"
            st.metric(f"처리 시간({tag})", f"{s1.get('_elapsed_sec','?')}초")
    if s1.get("evidence"):
        with st.expander("판단 근거"):
            for ev in s1["evidence"]:
                st.markdown(f"- {ev}")

# (C) 단계 2 결과 사용자 확정 — 카드 + "반영하기" 일괄 적용 패턴
if s2 and _show_stage2_confirm:
    # supplement 단계 상단 큐 — 사용자가 점검표가 어디 있는지 즉시 알 수 있도록.
    # supplement 만 보고 끝나서 점검표를 못 찾는 사용자 혼동 차단.
    if step == "supplement" and s3:
        _cue_l, _cue_r = st.columns([3, 1])
        with _cue_l:
            st.markdown(
                "<div style='padding:12px 16px;background:#F0F7FF;"
                "border:1px solid #B3D4FF;border-left:4px solid #1976D2;"
                "border-radius:6px;font-size:13px;color:#0A0A0B;line-height:1.6;'>"
                "<b style='color:#1976D2;'>맞춤 점검표 준비 완료</b><br>"
                "AI 가 탐지한 설비를 아래에서 검토·정정한 뒤 <b>[반영하기]</b> 를 누르면 "
                "점검표가 표시됩니다. 정정 없이 바로 점검표를 보고 싶으면 오른쪽 "
                "<b>[점검표 바로 보기]</b> 를 누르세요."
                "</div>",
                unsafe_allow_html=True,
            )
        with _cue_r:
            if st.button("점검표 바로 보기", type="primary",
                          width="stretch", key="cue_to_review_top"):
                _go_to_step("review")
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    st.markdown("<div class='sl-num' style='margin-top:18px;'>결과 02</div>"
                "<div class='sl-h'>설비 탐지 · 사용자 확정</div>"
                "<div class='sl-h-sub'>AI 결과를 확인하고 표시한 뒤 <b>'반영하기'</b> 를 눌러 점검표에 적용하세요. "
                "체크해도 항목은 사라지지 않으며, 반영 전까지 자유롭게 수정 가능합니다.</div>",
                unsafe_allow_html=True)

    # 시연 합성 응답 명시 — 사용자에게 "이게 진짜 AI 결과냐" 의문 차단
    if s2.get("_synth_demo"):
        st.markdown(
            "<div style='padding:10px 14px;background:#FFF8E1;border:1px solid #FFE082;"
            "border-left:4px solid #F57C00;border-radius:6px;font-size:12px;color:#6B4500;"
            "line-height:1.6;margin-bottom:10px;'>"
            "<b>시연 합성 응답</b> — 이 결과는 <b>실제 AI 호출이 아닌</b>, "
            "법령 표준 설비 목록(LAW_BASIS)에 기반한 자동 합성 응답입니다. "
            "더미 이미지의 SHA 해시가 캐시 적중하지 않아 실 API 호출 시 결과가 달라질 수 있어, "
            "시연용 풍부한 응답을 즉석 합성합니다.<br>"
            "실 사용 시(샘플 사진 업로드 또는 API 키 설정 후)에는 진짜 AI 분석 결과가 표시됩니다."
            "</div>",
            unsafe_allow_html=True,
        )

    detected = s2.get("detected_equipment", []) or []
    absent = s2.get("likely_absent_equipment", []) or []
    ambiguous = s2.get("ambiguous_items", []) or []

    # 사용자 마킹 상태 (체크해도 항목은 유지)
    # detected "remove" (제거 표시) / 부재 "actually_exists" / 모호 라디오 선택
    if "stage2_user_marks" not in st.session_state:
        st.session_state["stage2_user_marks"] = {
            "detected_remove": {}, # {idx: bool}
            "absent_exists": {}, # {idx: bool}
            "ambig_decision": {}, # {idx: str}
        }
    marks = st.session_state["stage2_user_marks"]

    tab_d, tab_a, tab_m = st.tabs(
        [f"탐지 {len(detected)}", f"부재 {len(absent)}", f"모호 {len(ambiguous)}"]
    )

    with tab_d:
        st.caption(
            "AI 가 사진에서 실제로 확인한 설비입니다. **잘못 탐지된 것** 만 체크하세요 "
            "'반영하기' 클릭 시 점검표에서 제거됩니다."
        )
        for i, item in enumerate(detected):
            ref = item.get("image_ref") or item.get("note_ref") or "-"
            loc = item.get("location") or ""
            cat = item.get("category", "")
            status = item.get("status", "")
            name = item.get("name", "?")
            # 카드 컨테이너
            col_chk, col_info = st.columns([1, 12])
            with col_chk:
                marks["detected_remove"][i] = st.checkbox(
                    " ", key=f"chk_remove_{i}",
                    value=marks["detected_remove"].get(i, False),
                    label_visibility="collapsed",
                )
            with col_info:
                loc_html = f" · {loc}" if loc else ""
                st.markdown(
                    f"<div style='padding:6px 8px;font-size:13.5px;'>"
                    f"<b>{name}</b> "
                    f"<span style='font-size:11px;color:#6B6B70;'>"
                    f"· {status} · {cat}</span>"
                    f"<div style='font-size:11px;color:#9A9A9F;margin-top:2px;'>"
                    f"출처: {ref}{loc_html}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    with tab_a:
        st.caption(
            "AI 가 '없다' 고 판정한 설비입니다. **실제로 존재한다면** 체크하세요 "
            "'반영하기' 클릭 시 탐지됨으로 이동합니다."
        )
        for i, item in enumerate(absent):
            cat = item.get("category", "")
            name = item.get("name", "?")
            reason = item.get("reason", "")
            col_chk, col_info = st.columns([1, 12])
            with col_chk:
                marks["absent_exists"][i] = st.checkbox(
                    " ", key=f"chk_exists_{i}",
                    value=marks["absent_exists"].get(i, False),
                    label_visibility="collapsed",
                )
            with col_info:
                st.markdown(
                    f"<div style='padding:6px 8px;font-size:13.5px;'>"
                    f"<b>{name}</b> "
                    f"<span style='font-size:11px;color:#6B6B70;'>· {cat}</span>"
                    f"<div style='font-size:11px;color:#9A9A9F;margin-top:2px;'>"
                    f"AI 판정 이유: {reason}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    with tab_m:
        st.caption(
            "AI 가 확신하지 못한 항목입니다. 각 항목별로 판정한 뒤 '반영하기' 클릭."
        )
        for i, item_text in enumerate(ambiguous):
            st.markdown(
                f"<div style='padding:6px 8px;font-size:13.5px;'>{item_text}</div>",
                unsafe_allow_html=True,
            )
            marks["ambig_decision"][i] = st.radio(
                f"판정 #{i+1}",
                ["판단 유보", "존재함 (탐지)", "없음 (부재)"],
                key=f"radio_ambig_{i}",
                index=["판단 유보", "존재함 (탐지)", "없음 (부재)"].index(
                    marks["ambig_decision"].get(i, "판단 유보")
                ),
                horizontal=True,
                label_visibility="collapsed",
            )

    # 반영 직후 큰 success 박스 (rerun 후 1회 표시) — 사용자 인지 강화
    _just_applied = st.session_state.pop("_stage2_just_applied", None)
    if _just_applied:
        st.success(
            f"### 반영 완료\n\n"
            f"{_just_applied['msg']}\n\n"
            f"아래로 스크롤하여 **현장 점검 입력** 섹션을 펼치고 "
            f"각 항목을 양호/불량/부재로 입력하세요."
        )

    # ─── 반영하기 버튼 (일괄 적용) ───
    pending_changes = (
        sum(1 for v in marks["detected_remove"].values() if v)
        + sum(1 for v in marks["absent_exists"].values() if v)
        + sum(1 for v in marks["ambig_decision"].values() if v != "판단 유보")
    )

    apply_col1, apply_col2 = st.columns([3, 1])
    with apply_col1:
        if pending_changes:
            st.markdown(
                f"<div style='padding:8px 14px;background:#FFF6F6;"
                f"border:1px solid #F8D0D0;border-radius:6px;font-size:13px;'>"
                f"<b>아직 반영되지 않은 수정 {pending_changes}건</b> — "
                f"우측 '반영하기' 버튼을 눌러야 점검표에 적용됩니다."
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            already = st.session_state.get("stage2_confirmed")
            n_done = len((already or {}).get("user_corrections", []))
            if n_done:
                st.markdown(
                    f"<div style='padding:8px 14px;background:#F0F7F0;"
                    f"border:1px solid #C8E6C9;border-radius:6px;font-size:13px;'>"
                    f"사용자 수정 <b>{n_done}건</b> 반영 완료"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("AI 결과를 그대로 사용하려면 별도 작업 없이 다음 단계로 진행하세요.")
    with apply_col2:
        # 변경 0건이면 disabled 대신 "변경 없이 다음 단계" 라벨로 변경 — 사용자가
        # 라디오를 안 건드리고 클릭했을 때 무반응 대신 명확한 안내가 가도록.
        _btn_label = "반영하기" if pending_changes else "변경 없음 다음 단계"
        _btn_help = (
            "왼쪽 '부재' 카드의 항목을 '존재확인'으로 바꾸거나 '모호' 카드에서 "
            "판정을 정한 뒤 누르세요." if pending_changes == 0 else None
        )
        if st.button(_btn_label, type="primary", key="apply_stage2_marks",
                      width="stretch", help=_btn_help):
            if pending_changes == 0:
                # 변경 없이 다음 단계로 — stage2_result 를 그대로 confirmed 로 복사
                st.session_state["stage2_confirmed"] = {
                    "detected_equipment": list(detected),
                    "likely_absent_equipment": list(absent),
                    "ambiguous_items": list(ambiguous),
                    "ambiguous_resolutions": [
                        {"text": t, "decision": "판단 유보"} for t in ambiguous
                    ],
                    "user_corrections": [],
                }
                # 점검표 라디오 자동 prefill (detected 양호 / absent 부재)
                _s3_items = (
                    (st.session_state.get("stage3_result") or {}).get("items")
                    or []
                )
                if _s3_items:
                    st.session_state["item_scores"] = (
                        _prefill_item_scores_from_stage2(
                            st.session_state["stage2_confirmed"],
                            _s3_items,
                            st.session_state.get("item_scores") or {},
                        )
                    )
                    st.session_state["_radio_counter"] = (
                        st.session_state.get("_radio_counter", 0) + 1
                    )
                # 명확한 시각 피드백 — 단순 toast 가 아닌 큰 success 박스
                st.session_state["_stage2_just_applied"] = {
                    "count": 0,
                    "msg": "AI 결과를 그대로 적용했습니다. 아래 [현장 점검 입력] 으로 이동하세요.",
                }
                st.rerun()
                # 아래 변경 적용 블록은 실행되지 않음 (rerun 으로 종료)
            # ── 변경 있는 경우: 기존 적용 로직 ──
            # 적용: detected 에서 제거 표시된 것 빼기, 부재 탐지 이동, 모호 분류
            new_detected = []
            user_corrections = []
            for i, item in enumerate(detected):
                if marks["detected_remove"].get(i):
                    user_corrections.append({"type": "remove_detected", "item": item})
                else:
                    new_detected.append(dict(item))
            new_absent = []
            for i, item in enumerate(absent):
                if marks["absent_exists"].get(i):
                    new_detected.append({
                        "category": item.get("category", ""),
                        "name": item.get("name", ""),
                        "status": "존재확인(사용자 수정)",
                        "note": "사용자가 부재탐지로 수정",
                    })
                    user_corrections.append({"type": "absent_to_detected", "item": item})
                else:
                    new_absent.append(dict(item))
            resolved = []
            for i, item_text in enumerate(ambiguous):
                d = marks["ambig_decision"].get(i, "판단 유보")
                resolved.append({"text": item_text, "decision": d})
                if d != "판단 유보":
                    user_corrections.append({
                        "type": f"ambig_resolved_{d}",
                        "item": item_text,
                    })
            st.session_state["stage2_confirmed"] = {
                "detected_equipment": new_detected,
                "likely_absent_equipment": new_absent,
                "ambiguous_items": list(ambiguous),
                "ambiguous_resolutions": resolved,
                "user_corrections": user_corrections,
            }
            # 점검표 라디오 자동 prefill — 사용자 정정이 점검표에 즉시 반영됨
            _s3_items = (
                (st.session_state.get("stage3_result") or {}).get("items")
                or []
            )
            if _s3_items:
                st.session_state["item_scores"] = (
                    _prefill_item_scores_from_stage2(
                        st.session_state["stage2_confirmed"],
                        _s3_items,
                        st.session_state.get("item_scores") or {},
                    )
                )
                # 라디오 위젯 새로 생성되어 prefill 값 적용되도록 카운터 +1
                st.session_state["_radio_counter"] = (
                    st.session_state.get("_radio_counter", 0) + 1
                )
            # 명확한 시각 피드백 — rerun 후 큰 success 박스로 표시
            st.session_state["_stage2_just_applied"] = {
                "count": len(user_corrections),
                "msg": (
                    f"사용자 수정 {len(user_corrections)}건 반영 완료. "
                    f"점검표 라디오에 양호/부재가 자동 채워졌습니다. "
                    f"아래 [현장 점검 입력] 으로 이동하세요."
                ),
            }
            st.rerun()

# ─────────────────────────────────────────
# supplement 단계 — 결과 카드 다 본 후 가장 아래 [결과 단계로] 버튼
# (review 단계에서는 점검표 + 점수가 이어서 표시되므로 별도 nav 불필요)
# ─────────────────────────────────────────
if step == "supplement" and _show_stage2_confirm and s2:
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='padding:10px 14px;background:#F5F5F5;"
        "border:1px solid #E5E5E8;border-radius:6px;font-size:12.5px;color:#6B6B70;"
        "margin-bottom:10px;'>"
        "위 [결과 02 설비 탐지] 에서 정정한 사항을 [반영하기] 까지 끝낸 뒤 "
        "아래 버튼으로 다음 단계(점검표 입력 + 점수 계산)로 이동하세요."
        "</div>",
        unsafe_allow_html=True,
    )
    _nav_l, _nav_r = st.columns([2, 1])
    with _nav_l:
        if st.button("이전 (재분석)", key="nav_prev_supplement_bottom",
                      width="stretch"):
            _go_to_step("ai_run")
    with _nav_r:
        if st.button("결과 단계로", type="primary", width="stretch",
                      key="nav_to_review_bottom"):
            _go_to_step("review")

# 단계 3 결과
if s3 and _show_checklist_and_score:
    divider()
    st.markdown("<div class='sl-num'>결과 03</div>"
                "<div class='sl-h'>맞춤 점검표</div>", unsafe_allow_html=True)
    items = s3.get("items", []) or []
    st.caption(f"{s3.get('checklist_name','-')} · 총 {len(items)}개 항목")
    if s3.get("rationale"):
        st.info(f"맞춤화 근거: {s3['rationale']}")

    # AI 가 사진에서 실제 인식한 설비명 (Stage 2 detected_equipment)
    _confirmed = st.session_state.get("stage2_confirmed") or {}
    _detected_names = {
        x.get("name", "") for x in
        (_confirmed.get("detected_equipment") or s2.get("detected_equipment", []) or [])
    }

    def _is_photo_based(item_title: str, item_category: str) -> bool:
        """이 점검 항목이 실제 사진에서 인식된 설비를 다루는지."""
        haystack = f"{item_title} {item_category}"
        for name in _detected_names:
            if name and name in haystack:
                return True
        return False

    # 사용자 정정 사항을 점검표에 시각적으로 반영 — '반영하기' 버튼이 어떻게 점검표에 영향 주는지 명시
    _user_corrections = (_confirmed.get("user_corrections") or [])
    if _user_corrections:
        _removed = [c["item"].get("name", "") for c in _user_corrections
                    if c.get("type") == "remove_detected"]
        _added = [c["item"].get("name", "") for c in _user_corrections
                  if c.get("type") == "absent_to_detected"]
        _ambig = [c for c in _user_corrections
                  if str(c.get("type", "")).startswith("ambig_resolved")]
        _bullets = []
        if _removed:
            _bullets.append(
                f"- **AI 오탐 정정** ({len(_removed)}건): "
                f"{', '.join(_removed)} 관련 점검 항목은 무시해도 됩니다"
            )
        if _added:
            _bullets.append(
                f"- **AI 누락 정정** ({len(_added)}건): "
                f"{', '.join(_added)} 점검표에서 '사진 기반' 배지로 표시됩니다"
            )
        if _ambig:
            _bullets.append(f"- **모호 항목 판정** ({len(_ambig)}건)")
        st.success(
            "**사용자 정정 사항이 점검표에 반영되었습니다**\n\n"
            + "\n".join(_bullets)
        )

    # 카테고리별 묶기
    by_cat: dict[str, list[dict]] = {}
    for itm in items:
        cat = itm.get("category", "기타")
        by_cat.setdefault(cat, []).append(itm)

    if items:
        # 가로 스크롤 없는 컴팩트 테이블 (요약만)
        with st.expander(f"점검표 미리보기 (전체 {len(items)}개 — 카테고리별 정리)",
                          expanded=False):
            summary_rows = []
            for cat, cat_items in by_cat.items():
                photo_ct = sum(1 for x in cat_items
                                if _is_photo_based(x.get("title", ""), x.get("category", "")))
                summary_rows.append({
                    "카테고리": cat,
                    "항목 수": len(cat_items),
                    "사진 기반": f"{photo_ct}건",
                    "표준 권장": f"{len(cat_items) - photo_ct}건",
                })
            st.dataframe(pd.DataFrame(summary_rows), width="stretch",
                          hide_index=True)
            st.caption(
                "**사진 기반** = AI 가 사진에서 실제로 인식한 설비를 점검 / "
                "**표준 권장** = 해당 공간에 법령상 필요해 AI 가 권장한 점검"
            )

    # ─────────────────────────────────────────
    # (D) 현장 점검 — 카테고리별 expander 로 그룹화
    # ─────────────────────────────────────────
    divider()
    section("03", "현장 점검 입력",
            f"카테고리 {len(by_cat)}개 · 총 {len(items)}개 항목 — 카테고리를 펼쳐 입력하세요")

    # 시연 모드 + 점수 미계산 시 다음 단계 안내 (사용자가 어디로 가야 할지 명확히)
    if (st.session_state.get("demo_mode")
            and not st.session_state.get("score_result")):
        st.info(
            "**시연 진행 안내** — 다음 순서로 진행하세요:\n\n"
            "1⃣ 아래 **'전체 \"양호\"로 채우기'** 클릭 (또는 카테고리별 직접 입력)\n"
            "2⃣ 페이지 하단의 **'안전 점수 계산 · 추천 생성'** 버튼 클릭\n"
            "3⃣ 사이드바 **'결과 저장'** 으로 이동 결과 저장 + 다운로드"
        )

    # 라디오 위젯 카운터 — 시연 모드 일괄 채우기 버튼이 작동하려면 라디오 key 도
    # 카운터로 동적 변경해야 함 (Streamlit 은 같은 key 위젯의 사용자 선택값을 보존).
    # 카운터 +1 시 모든 점검표 라디오가 새 위젯으로 재생성되어 index= 가 적용됨.
    _radio_counter = st.session_state.get("_radio_counter", 0)

    if st.session_state.get("demo_mode"):
        col_a, col_b, col_c = st.columns(3)
        # B4: 라벨 가변 위젯 보호 위해 명시 key 부여.
        if col_a.button("전체 '양호'로 채우기", width="stretch",
                         key="demo_all_good"):
            st.session_state["item_scores"] = {str(itm.get("no")): 1.0 for itm in items}
            st.session_state["_radio_counter"] = _radio_counter + 1
            st.rerun()
        if col_b.button("무작위 샘플 채우기", width="stretch",
                         key="demo_random"):
            import random
            random.seed(42)
            st.session_state["item_scores"] = {
                str(itm.get("no")): random.choice([1.0, 1.0, 0.5, 0.0]) for itm in items
            }
            st.session_state["_radio_counter"] = _radio_counter + 1
            st.rerun()
        if col_c.button("입력 초기화", width="stretch",
                         key="demo_clear_scores"):
            st.session_state["item_scores"] = {}
            st.session_state["_radio_counter"] = _radio_counter + 1
            st.rerun()

    scores: dict[str, float] = dict(st.session_state.get("item_scores") or {})

    # 점검표 UI — 카드 + 좌측 색상 띠 + 상태 배지 + 방법·기준·근거 expander
    # 점검자 시점 개선 사항:
    #  1. 카테고리 펼치면 progress bar 로 진행률 한눈에
    #  2. 각 항목이 카드 (테두리) — 항목 간 구분 명확
    #  3. 좌측 색상 띠 + 우측 상태 배지로 현재 상태 즉시 인식 (양호=초록·불량=주황·부재=빨강)
    #  4. 항목명 큰 글씨 + 위치 정보 굵게 (점검자가 어디 가야 하는지)
    #  5. 점검 방법·기준·법령 근거는 [점검 방법 보기] expander 로 접어 시각 위계 강화
    #  6. 미입력 항목은 점선 회색 배지로 명확히 표시 (누락 방지)
    _STATUS_COLORS = {
        1.0: "#2E7D32",   # 양호 - 초록
        0.5: "#F59E0B",   # 불량 - 주황
        0.0: "#D50000",   # 부재 - 빨강
        -1.0: "#9A9A9F",  # 해당 없음 - 회색
    }
    _STATUS_LABELS = {1.0: "양호", 0.5: "불량", 0.0: "부재", -1.0: "해당 없음"}
    _OPTS = [1.0, 0.5, 0.0, -1.0]

    for cat, cat_items in by_cat.items():
        cat_filled = sum(1 for itm in cat_items
                         if str(itm.get("no")) in scores)
        cat_total = len(cat_items)
        cat_progress = cat_filled / cat_total if cat_total else 0.0

        with st.expander(
            f"**{cat}** — {cat_filled} / {cat_total} 입력  ({int(cat_progress*100)}%)",
            expanded=(cat_filled < cat_total),
        ):
            # 카테고리 진행률 바
            st.progress(cat_progress)
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            for itm in cat_items:
                no = str(itm.get("no"))
                title = itm.get("title", "")
                location = itm.get("location") or ""
                basis = itm.get("basis") or ""
                method = itm.get("method", "")
                criterion = itm.get("criterion", "")
                photo_based = _is_photo_based(title, itm.get("category", ""))

                # 현재 상태 파싱 — 미입력은 None
                current_raw = scores.get(no)
                try:
                    current = float(current_raw) if current_raw is not None else None
                except (TypeError, ValueError):
                    current = None

                # 상태에 따른 색상 + 배지 HTML
                if current is None:
                    band_color = "#E5E5E8"
                    status_html = (
                        "<span style='background:#FAFAFA;color:#9A9A9F;"
                        "padding:3px 12px;border-radius:999px;"
                        "font-size:11px;font-weight:600;"
                        "border:1px dashed #C8C8C8;'>미입력</span>"
                    )
                else:
                    band_color = _STATUS_COLORS.get(current, "#E5E5E8")
                    label = _STATUS_LABELS.get(current, "")
                    status_html = (
                        f"<span style='background:{band_color};color:white;"
                        f"padding:3px 12px;border-radius:999px;"
                        f"font-size:11px;font-weight:700;'>{label}</span>"
                    )

                # 사진 기반 / 표준 권장 라벨
                if photo_based:
                    kind_html = (
                        "<span style='background:#E8F5E9;color:#2E7D32;"
                        "padding:2px 7px;border-radius:999px;font-size:10px;"
                        "font-weight:600;margin-left:6px;'>사진 기반</span>"
                    )
                else:
                    kind_html = (
                        "<span style='background:#FAFAFA;color:#6B6B70;"
                        "padding:2px 7px;border-radius:999px;font-size:10px;"
                        "font-weight:500;margin-left:6px;'>표준 권장</span>"
                    )

                # 항목 카드 — 테두리 + 좌측 색상 띠
                with st.container(border=True):
                    # 상단: 번호 + 제목 (좌측 색상 띠) + 상태 배지 (우측)
                    col_title, col_status = st.columns([5, 2])
                    with col_title:
                        st.markdown(
                            f"<div style='border-left:4px solid {band_color};"
                            f"padding:2px 0 2px 12px;'>"
                            f"<span style='color:#D50000;font-weight:700;"
                            f"font-size:13px;'>{itm.get('no')}.</span> "
                            f"<span style='font-size:15.5px;font-weight:600;"
                            f"color:#0A0A0B;'>{title}</span>"
                            f"{kind_html}</div>",
                            unsafe_allow_html=True,
                        )
                    with col_status:
                        st.markdown(
                            f"<div style='text-align:right;padding-top:4px;'>"
                            f"{status_html}</div>",
                            unsafe_allow_html=True,
                        )

                    # 위치 정보 — 점검자가 가야 할 곳 (강조)
                    if location:
                        st.markdown(
                            f"<div style='color:#0A0A0B;font-size:13px;"
                            f"margin-top:8px;padding-left:16px;"
                            f"border-left:4px solid transparent;'>"
                            f"위치: <b>{location}</b></div>",
                            unsafe_allow_html=True,
                        )

                    # 라디오 (충족도) — 미입력 시 index=None
                    st.markdown("<div style='height:6px'></div>",
                                unsafe_allow_html=True)
                    idx = _OPTS.index(current) if current in _OPTS else None
                    val = st.radio(
                        "충족도",
                        options=_OPTS,
                        format_func=lambda x: _STATUS_LABELS[x],
                        index=idx, horizontal=True,
                        key=f"score_{no}_v{_radio_counter}",
                        label_visibility="collapsed",
                        help="**해당 없음**: 이 공간에 실제로 존재하지 않는 설비 "
                              "(예: 일반교실의 시약장). 점수 계산에서 제외됩니다.",
                    )
                    if val is not None:
                        scores[no] = val

                    # 점검 방법·기준·법령 근거 — expander (펴서 확인, 시각 위계 강화)
                    if method or criterion or basis:
                        with st.expander("점검 방법·기준·근거 보기",
                                          expanded=False):
                            if method:
                                st.markdown(f"- **점검 방법**: {method}")
                            if criterion:
                                st.markdown(f"- **합격 기준**: {criterion}")
                            if basis:
                                st.markdown(f"- **법령 근거**: {basis}")

                # 카드 간 간격
                st.markdown("<div style='height:6px'></div>",
                            unsafe_allow_html=True)
    st.session_state["item_scores"] = scores

    # (E) 점수 계산
    divider()

    # 매핑 결과 미리보기 + 매핑 실패 시 수동 매핑 UI
    # 별칭 사전(STANDARD_ALIASES)을 활용해 AI가 다른 용어를 써도 매칭됨
    from modules.laws import STANDARD_ITEMS, find_std_match

    def _map_items_to_std(items_list: list[dict]) -> tuple[dict, list[str]]:
        """AI 점검표 항목 표준 항목 매핑 + 매핑 실패 목록 반환."""
        t2s = {}
        unmapped_items = []
        for itm in items_list:
            haystack = (itm.get("title", "") + " " + itm.get("category", "")
                        + " " + (itm.get("basis") or ""))
            matched_std = find_std_match(haystack)
            if matched_std:
                t2s[str(itm.get("no"))] = matched_std
            else:
                unmapped_items.append(str(itm.get("no")))
        return t2s, unmapped_items

    auto_map, unmapped = _map_items_to_std(items)
    total_items = len(items)
    mapped_ratio = (len(auto_map) / total_items) if total_items else 0

    # 매핑이란? — 사용자에게 친절하게 설명
    with st.expander("자동 매핑 / 수동 매핑이 무엇인가요?", expanded=False):
        st.markdown(
            "**자동 매핑** — AI 가 생성한 점검표(예: '흄후드 작동 상태 점검')를 "
            "법령에 정의된 **표준 설비**(예: '흄후드') 목록과 자동으로 연결하는 작업입니다. "
            "이름 매칭으로 진행되어, AI 가 다른 표현을 쓰면(예: '국소배기 시스템') 자동 연결이 안 될 수 있습니다.\n\n"
            "**수동 매핑** — 자동 매핑이 못 찾은 항목을 사용자가 직접 표준 설비와 연결하는 작업입니다. "
            "예: AI 항목 '실험대 하단 배기' 표준 설비 '국소배기장치' 로 연결.\n\n"
            "**왜 매핑이 필요한가?** — 점수 계산은 표준 설비 가중치 기반으로 산정됩니다. "
            "매핑이 안 된 항목은 점수 계산에서 제외(부재 처리)되므로, 수동 매핑을 추가하면 점수 정확도가 올라갑니다."
        )

    # 매핑 실패가 있으면 수동 매핑 UI 노출
    if total_items and (mapped_ratio < 0.7 or unmapped):
        pct = int(mapped_ratio * 100)
        st.warning(
            f"자동 매핑 결과: **{len(auto_map)}/{total_items}** 항목만 표준 설비에 자동 연결되었습니다 "
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

    # ─── 자기보고 vs AI 탐지 불일치 검증 ───
    # 사용자가 "양호" 로 채운 항목 중, AI 가 "부재" 로 분류한 설비가 있으면 빨간 경고.
    # 학교가 무성의하게 만점 처리하는 것을 방지 (안전 점검의 본래 목적 보호).
    s2_eff = (st.session_state.get("stage2_confirmed")
              or st.session_state.get("stage2_result")
              or {})
    absent_names = set()
    for it_ab in (s2_eff.get("likely_absent_equipment") or []):
        nm = (it_ab.get("name") or "").strip()
        if nm:
            absent_names.add(nm)

    self_good_but_absent: list[str] = []
    for itm in items:
        no = str(itm.get("no"))
        # 사용자가 "양호" (1.0) 로 답했지만 AI 가 "부재" 로 분류한 설비
        if scores.get(no) == 1.0:
            std = auto_map.get(no) or (st.session_state.get("_manual_std_map") or {}).get(no)
            if std and std in absent_names:
                self_good_but_absent.append(f"{itm.get('title', '')} (표준: {std})")

    if self_good_but_absent:
        st.error(
            f"**자기보고 vs AI 탐지 불일치 — {len(self_good_but_absent)}건**\n\n"
            "AI 는 사진에서 **부재** 로 분류했는데 사용자는 **양호** 로 답한 항목입니다. "
            "이 상태로 점수를 계산하면 실제 안전 상태와 다른 결과가 나올 수 있습니다.\n\n"
            "**조치 권장**:\n"
            "- 해당 설비가 실제로 있다면 보완 사진 추가 (사진 기반 재분석)\n"
            "- 사진엔 안 보이지만 다른 곳에 있다면 위 STAGE 2 카드의 '존재확인' 으로 수정 후 '반영하기'\n"
            "- 실제로 없다면 해당 항목을 '미흡'(0.5) 또는 '없음'(0.0) 으로 변경\n\n"
            f"**불일치 항목**: {', '.join(self_good_but_absent[:5])}"
            + (f" 외 {len(self_good_but_absent)-5}건" if len(self_good_but_absent) > 5 else "")
        )

    # 미입력 항목 경고 — 점수 계산 전 누락 방지 안내
    # 새 점검표 UI(index=None 기본)로 인해 미입력 시 scores 에 키 자체가 없음.
    # 점수 계산에선 미입력 = 0.0(부재) 로 처리되므로 사용자가 의도 없이
    # 점수가 낮게 나오는 혼란 방지용 안내. 강제 차단 X — 진행은 가능.
    _missing_items = [itm for itm in items if str(itm.get("no")) not in scores]
    _missing_count = len(_missing_items)
    if _missing_count > 0:
        _sample_titles = [itm.get("title", "") for itm in _missing_items[:3]]
        _sample_txt = ", ".join(_sample_titles)
        if _missing_count > 3:
            _sample_txt += f" 외 {_missing_count - 3}개"
        st.warning(
            f"**미입력 {_missing_count}개 항목** — 점수 계산 시 **부재(0점)** 로 "
            f"처리됩니다.\n\n"
            f"위 카테고리를 펼쳐 미입력 항목(점선 회색 배지)을 확인하거나, "
            f"실제로 해당 설비가 없으면 **'해당 없음'** 으로 명시하면 점수에서 "
            f"제외됩니다. 의도된 부재라면 그대로 진행해도 됩니다.\n\n"
            f"미입력 예시: {_sample_txt}"
        )
        _btn_label = (
            f"안전 점수 계산 · 추천 생성  (미입력 {_missing_count}개 부재 처리)"
        )
    else:
        _btn_label = "안전 점수 계산 · 추천 생성"

    if st.button(_btn_label, type="primary", width="stretch",
                  key="calc_safety_score"):
        title_to_std = dict(auto_map)
        # 수동 매핑 오버라이드 (사용자 지정이 자동 매핑을 덮어씀)
        for k, v in (st.session_state.get("_manual_std_map") or {}).items():
            title_to_std[k] = v

        std_scores: dict[str, float] = {}
        excluded_count = 0
        for no, val in scores.items():
            # -1.0 = "해당 없음" 사용자 지정 — 점수 계산에서 제외
            if val == -1.0:
                excluded_count += 1
                continue
            std = title_to_std.get(no)
            if std and std not in std_scores:
                std_scores[std] = val
        if excluded_count:
            st.info(
                f"'해당 없음'으로 지정된 {excluded_count}개 항목은 "
                f"점수 계산에서 제외되었습니다."
            )

        # 매핑 결과 명시 — 사용자가 "전체 양호" 답했는데 점수가 낮아 보일 때
        # "X/Y 만 점수 반영, 나머지는 미매핑(부재 처리)" 명확히 알림.
        # 자동 매핑률이 낮을수록 점수가 직관과 어긋날 수 있음.
        _filled_count = sum(1 for v in scores.values() if v != -1.0)
        _mapped_count = len(std_scores)
        _unmapped_user = _filled_count - _mapped_count - excluded_count
        if _unmapped_user > 0:
            st.warning(
                f"**점수 반영 항목: {_mapped_count}개 / 입력 항목: {_filled_count}개**\n\n"
                f"입력하신 {_filled_count}개 항목 중 **{_mapped_count}개만** 표준 설비와 "
                f"매핑되어 점수에 반영되고, 나머지 **{_unmapped_user}개는 미매핑**이라 "
                f"점수 계산에서 제외됩니다.\n\n"
                f"**왜 점수가 낮아 보일 수 있나요?** — '전체 양호' 클릭 시 모든 항목을 양호로 답하지만, "
                f"매핑 안 된 항목은 표준 설비 자체가 '부재' 로 처리되어 점수가 낮아집니다. "
                f"위의 **'수동 매핑'** 으로 미매핑 항목을 직접 지정하면 점수가 올라갑니다."
            )

        if not std_scores:
            st.error(
                "매핑된 표준 설비가 하나도 없어 점수 계산이 불가합니다. "
                "위의 '수동 매핑' 을 펼쳐 1건 이상 지정하거나 AI 점검표를 재생성하세요."
            )
            st.stop()

        # 공간 유형(+층수) 을 점수·추천에 전달 — 해당 공간에 적용 항목만 사용.
        # 층수가 3 미만이면 완강기/창문 추락방지 같은 min_floor 항목 자동 제외.
        _space_type = (space or {}).get("type")
        _floor = (space or {}).get("floor")
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
    # 점검 커버리지 — 사용자가 표준 설비 중 몇 %를 점검했는지
    _cov = sr.get("coverage") or {}
    _cov_ratio = (_cov.get("ratio") or 0) * 100
    c3.metric("점검 커버리지", f"{_cov_ratio:.0f}%",
              delta=f"{_cov.get('checked', 0)}/{_cov.get('applicable', 0)} 표준 설비",
              delta_color="off")

    # 커버리지가 낮으면 경고 — 점수가 높아도 일부만 점검한 것
    if _cov_ratio < 70 and _cov.get("applicable", 0) > 0:
        st.warning(
            f"**점검 커버리지가 낮습니다** ({_cov_ratio:.0f}%). "
            f"이 공간에 적용되는 표준 설비 **{_cov.get('applicable', 0)}개** 중 "
            f"**{_cov.get('checked', 0)}개만 점검**되었습니다. "
            f"나머지 **{_cov.get('applicable', 0) - _cov.get('checked', 0)}개**는 "
            f"점검표에 없어 점수에 반영되지 못했습니다.\n\n"
            f"**개선 방법** — AI 점검표를 재생성하거나 위의 '수동 매핑' 으로 "
            f"미매핑 점검 항목을 표준 설비와 직접 연결하세요. "
            f"커버리지 70% 이상 권장."
        )

    desc = sr.get("grade_description", "") or ""
    if desc:
        # 등급 설명을 truncation 없이 카드로 표시
        st.markdown(
            f"<div style='border:1px solid #E5E5E8;border-left:3px solid #D50000;"
            f"background:#FAFAFA;border-radius:6px;padding:12px 16px;margin:8px 0;"
            f"font-size:13.5px;line-height:1.7;color:#0A0A0B;'>"
            f"<b style='color:#D50000;'>등급 설명</b> · {desc}"
            f"</div>",
            unsafe_allow_html=True,
        )

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
    st.plotly_chart(fig, width="stretch")

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
        st.plotly_chart(fig2, width="stretch")

    divider()
    colL, colR = st.columns([1, 1])
    with colL:
        if st.button("다른 공간 이어서 점검", width="stretch",
                      key="goto_next_space"):
            from modules.session import reset_inspection
            reset_inspection()
            st.session_state["shots"] = _shots_dict()
            st.switch_page("pages/1_점검시작.py")
    with colR:
        if st.button("결과 저장·발송으로", type="primary", width="stretch",
                      key="goto_save"):
            st.switch_page("pages/3_결과저장.py")
