"""
교육청 담당자 수신함 — 학교에서 메일·카톡·드라이브 등으로 받은 .safeloop /
.json 첨부를 업로드해 통합 검토·집계.

발송 경로 (4가지):
  A. 이메일 (Gmail/Naver/Daum/Outlook 웹·앱)
  B. 카톡 (PC 카톡 또는 모바일 카톡)
  C. 클라우드 드라이브 공유 링크 (Google Drive · OneDrive · 학교 NAS)
  D. 사내 행정 시스템 첨부

모든 경로의 공통점: SafeLoop 외부에서 파일 전송 교육청 담당자가 본 페이지에
**수동 업로드** 자동 복호화 + 통합 분석.
"""
from __future__ import annotations

import datetime
import json

import pandas as pd
import streamlit as st

from modules.auth import is_authenticated_session
from modules.session import ensure_state
from modules.storage import (
    EDU_RECEIPT_DIR,
    bulk_delete_edu_inbox,
    bulk_mark_edu_inbox_read,
    bulk_toggle_edu_inbox_star,
    delete_edu_inbox_item,
    is_edu_inbox_read,
    is_edu_inbox_starred,
    list_edu_inbox,
    mark_edu_inbox_read,
    save_uploaded_edu_inbox,
    toggle_edu_inbox_star,
)
from modules.ui import apply_theme, divider, empty_state, hero, render_sidebar, section

st.set_page_config(page_title="교육청 수신함 · SafeLoop", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="auto")
apply_theme()
ensure_state()
render_sidebar(active_key="edu_inbox")

# 인증 가드
if not is_authenticated_session("edu"):
    st.warning(
        "**교육청 담당자 인증이 필요합니다** — 홈으로 돌아가 PIN 입력 또는 "
        "자동 로그인을 해주세요."
    )
    if st.button("홈으로 돌아가서 인증", type="primary",
                  width="stretch", key="edu_inbox_back_home"):
        st.session_state["_show_pin_edu"] = True
        st.switch_page("app.py")
    st.stop()

st.session_state["role"] = "교육청"

hero("EDU OFFICE", "교육청 담당자 수신함",
     "메일·카톡·드라이브로 받은 .safeloop / .json 파일을 여기 업로드 자동 복호화·집계")

# ─────────────────────────────────────────
# 업로드 흐름 안내 — 사용자가 헷갈리지 않도록 명시
# ─────────────────────────────────────────
with st.expander("어떻게 받은 파일을 여기 올리나요?", expanded=False):
    st.markdown(
        """
        SafeLoop 은 메일 서버·카톡 봇과 연동되지 않은 **자체 도구**입니다.
        학교가 보낸 파일은 본인 받은편지함·카톡 채팅 등에 도착하며, 본 수신함에는
        **직접 업로드** 해야 통합 분석이 시작됩니다.

        **수신 업로드 4단계**
        1. 학교가 메일/카톡/드라이브로 PDF + `.safeloop` 발송
        2. 본인 받은편지함·카톡·드라이브에서 첨부 다운로드
        3. 아래 **새 데이터 업로드** 박스에 `.safeloop` (또는 `.json`) 끌어다 놓기
        4. SafeLoop 가 자동 복호화 시도·학교코드 인식 시도별 폴더로 분류

        **여러 건 한꺼번에 업로드 가능** — 분기·월별로 모은 파일 한 번에 처리.
        """
    )

# ─────────────────────────────────────────
# 신규 업로드 박스
# ─────────────────────────────────────────
with st.expander("새 데이터 업로드 (메일·카톡·드라이브로 받은 .safeloop / .json)",
                  expanded=False):
    uploaded_files = st.file_uploader(
        "데이터 파일 (여러 개 동시 업로드 가능)",
        type=["safeloop", "json"], accept_multiple_files=True,
        key="edu_inbox_upload",
    )
    if uploaded_files:
        if st.button(f"{len(uploaded_files)}개 파일 수신함에 저장",
                      type="primary", width="stretch",
                      key="edu_inbox_save_uploads"):
            ok_count, fail_count = 0, 0
            details = []
            for f in uploaded_files:
                r = save_uploaded_edu_inbox(f.getvalue(), f.name)
                if r.get("ok"):
                    ok_count += 1
                    details.append(f"{r.get('school_name','?')} ({r.get('sido','-')})")
                else:
                    fail_count += 1
                    details.append(f"{f.name} — {r.get('reason')}")
            st.success(f"수신 완료 — 성공 {ok_count}건 / 실패 {fail_count}건")
            for d in details:
                st.write(d)
            st.rerun()

# ─────────────────────────────────────────
# 수신함 데이터 로드 + 읽음·별표 상태 부착
# 시연 모드 + 수신함 비어있으면 데모 데이터 2건 자동 생성 (단일 + 통합).
# 교육청 시연이 빈 화면에서 막히지 않도록 보장.
# ─────────────────────────────────────────
if st.session_state.get("demo_mode"):
    try:
        from modules.storage import ensure_demo_edu_inbox
        _added = ensure_demo_edu_inbox()
        if _added:
            st.toast(f"시연 데이터 {_added}건 자동 생성", icon=None)
    except Exception:
        pass

inbox = list_edu_inbox()
for _it in inbox:
    _it["read_at"] = is_edu_inbox_read(_it.get("sido", ""), _it.get("file", ""))
    _it["unread"] = _it["read_at"] is None
    _it["starred"] = is_edu_inbox_starred(_it.get("sido", ""), _it.get("file", ""))

# ─────────────────────────────────────────
# 통계 KPI — 전체·신규·평균
# ─────────────────────────────────────────
def _to_dt(s: str | None):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", ""))
    except Exception:
        return None

now = datetime.datetime.now()
today_count = sum(1 for x in inbox
                   if (_to_dt(x.get("received_at")) or now).date() == now.date())
this_week_count = sum(1 for x in inbox
                       if (now - (_to_dt(x.get("received_at")) or now)).days <= 7)
unique_schools = len({x.get("school_code") for x in inbox if x.get("school_code")})

unread_count = sum(1 for x in inbox if x.get("unread"))
starred_count = sum(1 for x in inbox if x.get("starred"))

avg_score = (sum(x.get("score") or 0 for x in inbox) / len(inbox)) if inbox else 0

# KPI 7개 — 2줄 분할 (처리 현황 4 / 전체 통계 3).
# 모바일 393px 에서 한 줄 7컬럼은 컬럼당 56px 미만이라 텍스트 잘림.
# 2줄 분할 시 컬럼당 90~100px 확보 — 모바일·PC 모두 가독성 양호.
st.markdown(
    "<div style='font-size:11px;letter-spacing:0.18em;color:#6B6B70;"
    "font-weight:600;margin:6px 0 4px 2px;'>처리 현황</div>",
    unsafe_allow_html=True,
)
k1, k2, k3, k4 = st.columns(4)
k1.metric("총 수신", f"{len(inbox)}건")
k2.metric("미검토 ", f"{unread_count}건",
          delta=("새 건 있음" if unread_count else "모두 검토"),
          delta_color=("inverse" if unread_count else "normal"))
k3.metric("별표", f"{starred_count}건")
k4.metric("오늘 신규", f"{today_count}건")

st.markdown(
    "<div style='font-size:11px;letter-spacing:0.18em;color:#6B6B70;"
    "font-weight:600;margin:14px 0 4px 2px;'>전체 통계</div>",
    unsafe_allow_html=True,
)
k5, k6, k7 = st.columns(3)
k5.metric("이번주 신규", f"{this_week_count}건")
k6.metric("학교 수", f"{unique_schools}곳")
k7.metric("평균 점수", f"{avg_score:.1f}점")

if not inbox:
    divider()
    empty_state(
        title="아직 수신된 데이터가 없습니다",
        description="위 '새 데이터 업로드' 박스에 학교가 보낸 .safeloop 또는 "
                    ".json 파일을 끌어다 놓으세요.",
    )
    st.stop()

divider()

# ─────────────────────────────────────────
# 필터 + 정렬 + 검색
# ─────────────────────────────────────────
section("01", "검색·필터·정렬", f"총 {len(inbox)}건 중")

# 빠른 토글 — 메일 클라이언트 패턴 (미열람만 / 별표만)
quick_col1, quick_col2, quick_col3 = st.columns([1, 1, 4])
with quick_col1:
    only_unread = st.toggle("미검토만",
                              value=False, key="edu_inbox_only_unread",
                              help="아직 '검토 완료 처리' 안 한 건만 표시")
with quick_col2:
    only_starred = st.toggle("별표만",
                              value=False, key="edu_inbox_only_starred",
                              help="후속 조치 필요로 표시한 건만")
with quick_col3:
    group_by_time = st.selectbox(
        "시간 그룹",
        options=["(그룹화 안 함)", "오늘 / 이번주 / 이번달 / 이전"],
        index=0, key="edu_inbox_time_group",
        help="수신 시각으로 시간 묶음 헤더 자동 표시",
    )

f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 2, 2])

with f_col1:
    q = st.text_input("학교명 검색",
                       placeholder="예: 가락중학교 / 충남삼성고 (부분 일치)",
                       key="edu_inbox_q")

with f_col2:
    sidos = sorted({x["sido"] for x in inbox})
    sel_sidos = st.multiselect("시도 필터", options=sidos, default=[],
                                placeholder="(전체)",
                                key="edu_inbox_sido")

with f_col3:
    grades = sorted({x.get("grade") for x in inbox if x.get("grade")})
    sel_grades = st.multiselect("등급 필터", options=grades, default=[],
                                 placeholder="(전체)",
                                 key="edu_inbox_grade")

with f_col4:
    sort_by = st.selectbox(
        "정렬",
        options=["미검토·별표 우선 (기본)",
                 "수신일시 (최근순)", "수신일시 (오래된순)",
                 "점수 (높은순)", "점수 (낮은순 — 위험 우선)",
                 "학교명 (가나다)"],
        index=0, key="edu_inbox_sort",
    )

# 점수 범위 슬라이더 — 항상 0-100 초기값
# (데이터 1건일 때 min=max 가 되는 41-41 같은 어색한 초기값 방지)
s_lo, s_hi = st.slider(
    "점수 범위",
    min_value=0, max_value=100, value=(0, 100), step=1,
    key="edu_inbox_score_range",
    help="0-100 사이에서 점수 범위 좁히기. 기본값은 전체 (0-100).",
)

# 필터 적용
filtered = list(inbox)
if only_unread:
    filtered = [x for x in filtered if x.get("unread")]
if only_starred:
    filtered = [x for x in filtered if x.get("starred")]
if q:
    qlow = q.strip().lower()
    filtered = [x for x in filtered
                 if qlow in (x.get("school", "") or "").lower()]
if sel_sidos:
    filtered = [x for x in filtered if x.get("sido") in sel_sidos]
if sel_grades:
    filtered = [x for x in filtered if x.get("grade") in sel_grades]
filtered = [x for x in filtered
            if (x.get("score") is None) or (s_lo <= x.get("score") <= s_hi)]

# 정렬
if sort_by.startswith("미검토·별표 우선"):
    # 메일 클라이언트 기본 정렬 — (별표 또는 미열람) 우선 그 안에서 최근순
    filtered.sort(
        key=lambda x: (
            0 if x.get("starred") else 1,
            0 if x.get("unread") else 1,
            -(int((x.get("received_at") or "0").replace("-", "").replace(":", "")
                   .replace("T", "").replace(".", "").replace(" ", "")[:14] or 0)),
        )
    )
elif sort_by.startswith("수신일시 "):
    filtered.sort(key=lambda x: x.get("received_at") or "", reverse=True)
elif sort_by.startswith("수신일시 "):
    filtered.sort(key=lambda x: x.get("received_at") or "")
elif sort_by.startswith("점수 "):
    filtered.sort(key=lambda x: x.get("score") or 0, reverse=True)
elif sort_by.startswith("점수 "):
    filtered.sort(key=lambda x: x.get("score") if x.get("score") is not None else 999)
elif sort_by.startswith("학교명"):
    filtered.sort(key=lambda x: x.get("school") or "")

st.caption(f"필터 결과: **{len(filtered)}건**")

if not filtered:
    st.info("조건에 맞는 수신 건이 없습니다. 필터를 조정해보세요.")
    st.stop()

# ─────────────────────────────────────────
# 페이지네이션 (대량 데이터 대응)
# ─────────────────────────────────────────
PAGE_SIZE = 30
total_pages = (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE
if total_pages > 1:
    pg_col1, pg_col2 = st.columns([3, 1])
    with pg_col2:
        page = st.number_input(
            f"페이지 (1 ~ {total_pages})",
            min_value=1, max_value=total_pages, value=1,
            key="edu_inbox_page",
        )
else:
    page = 1
start = (page - 1) * PAGE_SIZE
page_items = filtered[start:start + PAGE_SIZE]

# ─────────────────────────────────────────
# 일괄 작업 — 다중 선택 + 일괄 삭제
# ─────────────────────────────────────────
divider()
section("02", "수신 목록 + 일괄 작업",
        f"{start + 1}~{min(start + PAGE_SIZE, len(filtered))} / {len(filtered)}건")

# ─── 시간 그룹화 헤더 표시 (활성화된 경우) ───
def _time_bucket(received_at: str) -> str:
    if not received_at:
        return "이전"
    try:
        dt = datetime.datetime.fromisoformat(str(received_at).replace("Z", ""))
    except Exception:
        return "이전"
    today = datetime.datetime.now().date()
    if dt.date() == today:
        return "오늘"
    if (today - dt.date()).days <= 7:
        return "이번주"
    if dt.year == today.year and dt.month == today.month:
        return "이번달"
    return "이전"

if group_by_time.startswith("오늘"):
    # 시간 그룹별로 카드 카운트만 헤더로 표시 (테이블은 그대로 한 화면)
    bucket_counts: dict[str, int] = {"오늘": 0, "이번주": 0, "이번달": 0, "이전": 0}
    for it in page_items:
        bucket_counts[_time_bucket(it.get("received_at", ""))] += 1
    chips = []
    for b in ["오늘", "이번주", "이번달", "이전"]:
        cnt = bucket_counts[b]
        if cnt:
            chips.append(
                f"<span style='display:inline-block;padding:4px 10px;margin-right:6px;"
                f"background:#F7F7F8;border:1px solid #E5E5E8;border-radius:14px;"
                f"font-size:12px;color:#0A0A0B;'><b>{b}</b> · {cnt}건</span>"
            )
    if chips:
        st.markdown(
            f"<div style='margin:6px 0 12px 0;'>{''.join(chips)}</div>",
            unsafe_allow_html=True,
        )

# 테이블 — 별표 + 상태 컬럼 추가, 시간 그룹 컬럼도 표시
# record_type 별 표시 — 단일 점검 vs 학교 단위 통합 보고서 구분
def _type_label(x: dict) -> str:
    rt = x.get("record_type") or "safeloop_edu_submission"
    if rt == "safeloop_consolidated_submission":
        n = x.get("spaces_count", 0)
        return f"통합 ({n}공간)"
    return "단일"


df = pd.DataFrame([
    {
        "선택": False,
        "": "" if x.get("starred") else "",
        "상태": "미검토" if x.get("unread") else "검토",
        "유형": _type_label(x),
        "그룹": _time_bucket(x.get("received_at", "")),
        "수신일시": (x.get("received_at", "") or "")[:16].replace("T", " "),
        "시도": x.get("sido", ""),
        "학교명": x.get("school", ""),
        "공간": (x.get("space_type", "") or "") +
                (f" ({x['space_nickname']})" if x.get("space_nickname") else ""),
        "점수": x.get("score", "-"),
        "등급": x.get("grade", "-"),
        "_idx": start + i,
    }
    for i, x in enumerate(page_items)
])

edited = st.data_editor(
    df.drop(columns=["_idx"]),
    width="stretch",
    hide_index=True,
    column_config={
        "선택": st.column_config.CheckboxColumn("선택", default=False, width="small"),
        "": st.column_config.TextColumn(
            "별표", width="small",
            help="후속 조치 필요로 마킹한 건. 일괄 별표 토글로 부착·해제",
        ),
        "상태": st.column_config.TextColumn(
            "상태", width="small",
            help="미검토 = 학교는 발송했지만 아직 '검토 완료 처리' 누르지 않은 건",
        ),
        "유형": st.column_config.TextColumn(
            "유형", width="small",
            help="단일 = 공간 한 곳의 점검 / 통합 = 학교 단위 여러 공간 묶음 보고서",
        ),
        "그룹": st.column_config.TextColumn("그룹", width="small"),
        "수신일시": st.column_config.TextColumn("수신일시", width="medium"),
        "시도": st.column_config.TextColumn("시도", width="small"),
        "학교명": st.column_config.TextColumn("학교명", width="medium"),
        "공간": st.column_config.TextColumn("공간", width="medium"),
        "점수": st.column_config.NumberColumn("점수", width="small"),
        "등급": st.column_config.TextColumn("등급", width="small"),
    },
    key="edu_inbox_table",
    height=520,
    disabled=["", "상태", "유형", "그룹", "수신일시", "시도",
              "학교명", "공간", "점수", "등급"],
)

selected_indices = [start + i for i, row in edited.iterrows() if row.get("선택")]
selected_items = [filtered[i] for i in selected_indices]

# ─── 일괄 액션 — 메일 클라이언트 패턴 (읽음 처리 + 별표 토글 + 삭제) ───
st.markdown("##### 일괄 액션")
a1, a2, a3, a4, a5 = st.columns([1.2, 2, 2, 2, 2])
with a1:
    st.metric("선택됨", f"{len(selected_items)}건")
with a2:
    if st.button(
        "일괄 검토 완료",
        width="stretch",
        disabled=(len(selected_items) == 0),
        key="edu_inbox_bulk_read",
        help="선택한 건들을 한 번에 '검토 완료 처리' — 학교 측에 수신 확인 자동 반영",
    ):
        n = bulk_mark_edu_inbox_read(selected_items)
        st.toast(f"{n}건 검토 완료 처리됨", icon=None)
        st.rerun()
with a3:
    n_unstarred = sum(1 for it in selected_items if not it.get("starred"))
    if st.button(
        "일괄 별표 부착" if n_unstarred else "일괄 별표 해제",
        width="stretch",
        disabled=(len(selected_items) == 0),
        key="edu_inbox_bulk_star",
    ):
        target = bool(n_unstarred) # 안 된 게 있으면 부착, 모두 별표면 해제
        n = bulk_toggle_edu_inbox_star(selected_items, target)
        st.toast(f"별표 {'부착' if target else '해제'} {n}건", icon=None)
        st.rerun()
with a4:
    if st.button(
        f"선택 {len(selected_items)}건 삭제",
        type="secondary", width="stretch",
        disabled=(len(selected_items) == 0),
        key="edu_inbox_delete_selected",
    ):
        st.session_state["_confirm_delete_pending"] = selected_items
with a5:
    if st.session_state.get("_confirm_delete_pending"):
        pending = st.session_state["_confirm_delete_pending"]
        st.warning(
            f"**{len(pending)}건** 영구 삭제 — 복구 불가"
        )
        cf1, cf2 = st.columns(2)
        with cf1:
            if st.button("삭제", type="primary", width="stretch",
                          key="edu_inbox_delete_confirm"):
                n = bulk_delete_edu_inbox(pending)
                st.session_state["_confirm_delete_pending"] = None
                st.success(f"{n}건 삭제 완료")
                st.rerun()
        with cf2:
            if st.button("취소", width="stretch", key="edu_inbox_delete_cancel"):
                st.session_state["_confirm_delete_pending"] = None
                st.rerun()

# ─────────────────────────────────────────
# 상세 조회 — 위 테이블의 "선택" 첫 번째 체크 항목 자동 표시
# (드롭다운으로 100건 중 고르는 패턴은 비효율 — 메일 클라이언트 인박스처럼
# 체크 = 상세 조회 트리거)
# ─────────────────────────────────────────
divider()
section("03", "상세 조회",
        "위 표에서 보고 싶은 행의 **선택** 체크박스를 켜면 아래에 상세가 표시됩니다")

# 선택된 첫 번째 항목을 상세로
detail_target = selected_items[0] if selected_items else None

if detail_target is None:
    st.info(
        "위 표에서 행의 **선택** 체크박스를 켜주세요. "
        "여러 건 체크 시 첫 번째 건이 상세 표시됩니다."
    )
else:
    sido_name = detail_target.get("sido", "")
    fname = detail_target.get("file", "")
    target = EDU_RECEIPT_DIR / sido_name / fname
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")
        st.stop()

    # 미리보기와 검토 완료 분리:
    # - 단순 행 체크박스(상세 표시) = 미리보기 — read marker 저장 X
    # - 명시적 "검토 완료 처리" 버튼 클릭 시만 read marker 저장 학교 측 "수신 확인"
    # 이전 동작(첫 열람 = 자동 검토 완료) 은 학교가 "교육청이 정식 검토" 로 오해 야기.
    _was_unread = is_edu_inbox_read(sido_name, fname) is None

    school = data.get("school_identified") or {}
    space = data.get("space") or {}

    # 헤더 카드
    col_a, col_b = st.columns([3, 1])
    starred_now = is_edu_inbox_starred(sido_name, fname)
    with col_a:
        star_icon=None if starred_now else ""
        st.markdown(
            f"<div style='padding:14px 18px;border:1px solid #E5E5E8;"
            f"border-left:4px solid #D50000;border-radius:6px;background:#FFF;'>"
            f"<div style='font-size:18px;font-weight:700;color:#0A0A0B;margin-bottom:4px;'>"
            f"{star_icon} {school.get('name','-')}</div>"
            f"<div style='font-size:13px;color:#6B6B70;line-height:1.7;'>"
            f"코드 <code>{school.get('code','-')}</code> · "
            f"{school.get('sido','-')} · {school.get('region','-')}<br>"
            f"공간: <b>{space.get('type','-')}</b> "
            f"({space.get('nickname') or '-'})<br>"
            f"종합 점수: <b style='color:#D50000'>{data.get('safety_score','-')}점</b> · "
            f"등급 <b>{data.get('grade','-')}</b>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
    with col_b:
        # ─── 검토 완료 처리 — 학교 측 "수신 확인" 트리거 ───
        # 단순 미리보기와 분리: 명시적 클릭 시만 read marker 저장.
        # 이미 검토 완료된 건은 비활성화 (재처리 불필요).
        _read_at = is_edu_inbox_read(sido_name, fname)
        if _read_at is None:
            if st.button(
                "검토 완료 처리",
                type="primary",
                width="stretch",
                key=f"edu_inbox_confirm_{fname}",
                help="학교 측에 '수신 확인 완료' 표시가 자동 반영됩니다. 단순 미리보기 시에는 누르지 마세요.",
            ):
                mark_edu_inbox_read(sido_name, fname)
                st.toast("검토 완료 처리 — 학교 측에 자동 반영됨", icon=None)
                st.rerun()
        else:
            st.markdown(
                f"<div style='padding:6px 10px;background:#F0F7F0;"
                f"border:1px solid #C8E6C9;border-radius:6px;font-size:12px;"
                f"color:#2E7D32;text-align:center;'>"
                f"검토 완료<br>{(_read_at or '')[:16].replace('T',' ')}"
                f"</div>",
                unsafe_allow_html=True,
            )

        # 별표 토글 + 단건 삭제
        if st.button(
            "별표 해제" if starred_now else "별표 부착",
            width="stretch",
            key=f"edu_inbox_star_{fname}",
        ):
            toggle_edu_inbox_star(sido_name, fname)
            st.rerun()
        if st.button("이 건 삭제", width="stretch",
                      key=f"edu_inbox_del_one_{fname}"):
            if delete_edu_inbox_item(sido_name, fname):
                st.success(f"삭제: {fname}")
                st.rerun()

    with st.expander("카테고리 점수 / 설비 / 점검표 / 추천", expanded=False):
        cat = data.get("category_scores") or {}
        cat_df = pd.DataFrame([
            {"카테고리": k, "점수": v.get("score", 0),
             "가중치합": v.get("weight_sum", 0)} for k, v in cat.items()
        ])
        if not cat_df.empty:
            st.markdown("**카테고리 점수**")
            st.dataframe(cat_df, width="stretch", hide_index=True)

        det = data.get("detected_equipment") or []
        if det:
            st.markdown("**탐지된 설비**")
            st.dataframe(pd.DataFrame(det), width="stretch", hide_index=True)

        absent = data.get("absent_equipment") or []
        if absent:
            st.markdown("**부재 설비**")
            st.dataframe(pd.DataFrame(absent), width="stretch", hide_index=True)

        recs = data.get("recommendations") or []
        if recs:
            st.markdown("**AI 추천**")
            st.dataframe(pd.DataFrame(recs), width="stretch", hide_index=True)

        items = data.get("checklist_items") or []
        if items:
            st.markdown("**점검표**")
            st.dataframe(pd.DataFrame(items), width="stretch", hide_index=True)

    # 다운로드
    st.markdown("##### 다운로드")
    col_x, col_y = st.columns(2)
    with col_x:
        st.download_button(
            "데이터 JSON 다운로드",
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=fname,
            mime="application/json",
            width="stretch",
            key=f"dl_inbox_json_{fname}",
        )
    with col_y:
        try:
            from modules.storage import build_pdf_report
            synth_master = {
                "school": {
                    "name": school.get("name"),
                    "code": school.get("code"),
                    "sido": school.get("sido"),
                    "region": school.get("region"),
                    "level": school.get("level"),
                    "establishment": school.get("establishment"),
                },
                "space": space,
                "ai_pipeline": {"stage1": {"space_type_primary": space.get("type"),
                                            "confidence": 1.0}},
                "inspection": {
                    "score_result": {
                        "score": data.get("safety_score"),
                        "grade": data.get("grade"),
                        "grade_description": data.get("grade_description", ""),
                        "category_scores": data.get("category_scores", {}),
                    },
                },
                "recommendations": data.get("recommendations", []),
                "approval": {"eduline": {}, "internal_approval_confirmed": True},
                "timestamp": data.get("submission_timestamp", ""),
            }
            pdf_bytes = build_pdf_report(synth_master)
            st.download_button(
                "PDF 보고서 다운로드",
                pdf_bytes,
                file_name=fname.replace(".json", ".pdf"),
                mime="application/pdf",
                width="stretch",
                key=f"dl_inbox_pdf_{fname}",
            )
        except Exception as e:
            st.caption(f"PDF 생성 실패: {e}")

# ─────────────────────────────────────────
# 필터 결과 일괄 내보내기 (CSV)
# ─────────────────────────────────────────
divider()
section("04", "필터 결과 내보내기", "현재 필터 적용된 결과를 CSV 로 다운로드")

export_df = pd.DataFrame([
    {
        "수신일시": (x.get("received_at", "") or "")[:16].replace("T", " "),
        "시도": x.get("sido", ""),
        "학교명": x.get("school", ""),
        "학교코드": x.get("school_code", ""),
        "공간": x.get("space_type", ""),
        "점수": x.get("score", ""),
        "등급": x.get("grade", ""),
        "파일명": x.get("file", ""),
    }
    for x in filtered
])
csv_bytes = export_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    f"필터 결과 {len(filtered)}건 CSV 다운로드",
    csv_bytes,
    file_name=f"교육청수신함_필터결과_{datetime.datetime.now():%Y%m%d_%H%M}.csv",
    mime="text/csv",
    width="stretch",
    key="dl_filtered_csv",
)
