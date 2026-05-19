"""
설정 페이지.

- 학교 프로필 · 결재라인 기본값
- 공간 사전 등록 (일괄)
- 시연 모드 토글
- API 상태 확인
- 세션 초기화
"""
from __future__ import annotations

import uuid

import streamlit as st

from modules.ai_vision import api_key_available, current_provider_label
from modules.ai_providers import ALL_PROVIDERS, providers_status, test_provider_connection
from modules.session import ensure_state, reset_all
from modules.ui import apply_theme, confirm_button, divider, hero, render_sidebar, section

st.set_page_config(page_title="설정 · SafeLoop", page_icon="static/icon-192.png",
                   layout="centered", initial_sidebar_state="auto")
apply_theme()
ensure_state()
render_sidebar(active_key="settings")

hero("SETTINGS", "설정", "운영 모드 · 공간 사전 등록 · AI 공급자 · 시스템 상태")

# ─────────────────────────────────────────
# 모드 — 시연 종료 / 시작
# ─────────────────────────────────────────
section("01", "운영 모드")
_in_demo = st.session_state.get("demo_mode", False)
if _in_demo:
    st.markdown(
        "<div style='padding:10px 14px;background:#FFF6F6;border:1px solid #F8D0D0;"
        "border-radius:6px;font-size:13px;color:#0A0A0B;line-height:1.6;'>"
        "<b>현재 시연 모드입니다</b> — 더미 이미지·자동 채움이 허용됩니다. "
        "실 사용으로 전환하려면 아래 버튼을 누르세요."
        "</div>",
        unsafe_allow_html=True,
    )
    # 시연 종료 시 cleanup 옵션 (P1-#12).
    # 시연 데이터(데모 매니저·합성 응답 캐시·시연 수신함 파일)가 실 사용
    # 데이터와 섞이지 않도록 함께 정리할 수 있게.
    _cleanup_demo = st.checkbox(
        "시연 데이터(데모 매니저·합성 응답 캐시·시연 수신함)도 함께 삭제",
        value=True,
        key="end_demo_cleanup",
        help="체크 해제 시 시연 모드만 끄고 데이터는 디스크에 남습니다.",
    )
    if st.button("시연 종료 (실 사용으로 전환)", key="end_demo_mode",
                  width="stretch"):
        st.session_state["demo_mode"] = False
        # 세션의 더미 사진·AI 결과를 항상 비움 — 운영 모드에 시연 흔적이
        # 잔존하지 않도록 (디스크 정리는 _cleanup_demo 체크박스로 선택).
        try:
            from modules.storage import clear_draft as _clear_draft
            _sc = (st.session_state.get("school") or {}).get("정보공시 학교코드") or ""
            _sp = (st.session_state.get("active_space") or {}).get("space_id") or ""
            if _sc and _sp:
                _clear_draft(_sc, _sp)
        except Exception:
            pass
        for _k in ("shots", "stage1_result", "stage2_result",
                    "stage2_confirmed", "stage3_result",
                    "item_scores", "score_result", "recommendations"):
            if _k in st.session_state:
                st.session_state[_k] = (
                    {} if _k in ("shots", "item_scores") else None
                )
        if _cleanup_demo:
            try:
                from modules.storage import cleanup_demo_artifacts
                _c = cleanup_demo_artifacts()
                _total = _c["managers"] + _c["edu_inbox"] + _c["ai_cache"]
                st.toast(
                    f"시연 종료 — 시연 데이터 {_total}건 정리 "
                    f"(매니저 {_c['managers']}, 수신함 {_c['edu_inbox']}, "
                    f"캐시 {_c['ai_cache']})",
                    icon=None,
                )
            except Exception as e:
                st.warning(f"시연 모드만 종료되었습니다. cleanup 실패: {e}")
        else:
            st.toast("시연 종료 — 이제 실 사용 모드입니다", icon=None)
        st.rerun()
else:
    st.markdown(
        "<div style='padding:10px 14px;background:#FAFAFA;border:1px solid #E5E5E8;"
        "border-radius:6px;font-size:13px;color:#0A0A0B;line-height:1.6;'>"
        "현재 <b>실 사용 모드</b>입니다. 시연 자료(더미 이미지·합성 응답)는 "
        "표시되지 않습니다."
        "</div>",
        unsafe_allow_html=True,
    )
    # 시연 진입점은 [설정] 에 일원화 — demo_mode=True 로 토글하면 홈에서
    # 시연 시작 카드와 자동재생 흐름이 활성화됨.
    if st.button("시연 모드 시작 (체험·발표용)", key="start_demo_mode",
                  width="stretch"):
        st.session_state["demo_mode"] = True
        st.toast(
            "시연 모드 시작 — 홈으로 가서 [시연 시작] 버튼을 누르세요.",
            icon=None,
        )
        st.switch_page("app.py")

# ─────────────────────────────────────────
# SQLite 인덱스 — 점검 데이터 빠른 검색·집계
# ─────────────────────────────────────────
st.markdown("---")
from modules.db import get_index_stats, rebuild_index
from modules.storage import STORAGE_DIR as _STORAGE_DIR
_idx1, _idx2 = st.columns([3, 1])
with _idx1:
    _stats = get_index_stats()
    st.markdown(
        f"**SQLite 인덱스**: {_stats['inspections']}건 등록 · "
        f"마지막 재구축 {_stats['last_rebuild'] or '없음'}"
    )
    st.caption(
        "점검 저장 시 자동 갱신. 외부 도구로 master.json 직접 추가했거나 "
        "인덱스가 손상된 경우 [재구축] 으로 디스크 전체 재스캔."
    )
with _idx2:
    if st.button("인덱스 재구축", key="rebuild_index_btn",
                  width="stretch", help="모든 master.json 재스캔 — 수 초 소요"):
        with st.spinner("인덱스 재구축 중…"):
            _res = rebuild_index(_STORAGE_DIR)
        st.success(f"{_res['inspections']}건 재구축 완료")
        for _err in (_res.get("errors") or [])[:5]:
            st.caption(f"[건너뜀] {_err}")
        st.rerun()

# ─────────────────────────────────────────
# SMTP 메일 발송 연결 시험 (학교 담당자가 교육청에 메일 보낼 때 사용)
# ─────────────────────────────────────────
st.markdown("---")
from modules.mailer import smtp_configured, test_smtp_connection
_sm1, _sm2 = st.columns([3, 1])
with _sm1:
    if smtp_configured():
        st.markdown(
            "**SMTP 메일 발송**: 설정됨. 통합 발송 시 교육청 이메일로 "
            "PDF·Excel·JSON 자동 첨부 발송 가능."
        )
    else:
        st.markdown(
            "**SMTP 메일 발송**: 미설정. `.env` 에 `SMTP_USER` (Gmail 주소) + "
            "`SMTP_PASS` (Gmail 앱 비밀번호) 를 등록하면 통합 발송 시 교육청에 "
            "메일이 함께 발송됩니다."
        )
        st.caption(
            "Gmail 앱 비밀번호: Google 계정 → 보안 → 2단계 인증 활성화 → "
            "앱 비밀번호 → '기타 (SafeLoop)' → 16자리 복사."
        )
with _sm2:
    if st.button("SMTP 연결 시험", key="test_smtp",
                  disabled=not smtp_configured(), width="stretch",
                  help="실제 메일은 보내지 않고 서버 연결·로그인만 시험."):
        with st.spinner("SMTP 서버 연결 중…"):
            _res = test_smtp_connection()
        if _res.get("ok"):
            st.success(f"연결 성공 — {_res.get('host')}")
        else:
            st.error(f"연결 실패 — {_res.get('error')}")

# 역할 변경 — 3택 (실 / 학교 / 교육청)
_ROLE_LABELS = {
    "실": "실 담당자",
    "학교": "학교 담당자",
    "교육청": "교육청 담당자",
}
_current_role = st.session_state.get("role", "학교")
current_role_display = _ROLE_LABELS.get(_current_role, "학교 담당자")
with st.expander(f"역할 변경 (현재: {current_role_display})", expanded=False):
    st.caption(
        "역할은 처음 한 번 정하면 일반적으로 바꿀 일이 거의 없습니다. "
        "다른 역할로 작업할 일이 있을 때만 변경하세요. "
        "전환 시 인증·세션 데이터가 초기화됩니다."
    )
    _options = ["실 담당자", "학교 담당자", "교육청 담당자"]
    _options_key = {"실 담당자": "실", "학교 담당자": "학교",
                     "교육청 담당자": "교육청"}
    _idx = _options.index(current_role_display) if current_role_display in _options else 1
    new_role = st.radio(
        "역할 선택",
        _options,
        horizontal=True,
        index=_idx,
        label_visibility="collapsed",
    )
    target_role = _options_key[new_role]
    if target_role != _current_role:
        if st.button("역할 변경 적용", key="apply_role_change",
                      width="stretch"):
            from modules.auth import (
                clear_authentication, forget_manager, forget_school,
            )
            from modules.session import reset_inspection
            # 다른 역할로 전환 시 모든 인증·자동 로그인·세션 데이터 해제 (보안)
            clear_authentication() # 교육청 PIN 인증 해제 + 쿠키 삭제
            forget_school() # 학교 자동 로그인 쿠키 삭제
            forget_manager() # 실 담당자 자동 로그인 쿠키 삭제
            reset_inspection() # 점검 진행 중 데이터 정리
            # 학교·매니저 세션 명시적 초기화
            for _k in ("school", "eduline", "space_manager",
                        "_show_pin_edu", "_auto_login_checked",
                        "_remembered_mgr_id"):
                st.session_state[_k] = None
            st.session_state["school_auth_verified"] = False
            st.session_state["role"] = target_role
            st.toast(f"{new_role} 모드로 전환했습니다 — 다시 로그인이 필요합니다",
                      icon=None)
            st.switch_page("app.py")

# ─────────────────────────────────────────
# 이메일 등록 — 역할별 분리
#  - 실 담당자: 본인 이메일만 (학교 담당자가 PIN/안내 보내기 위한 수신처)
#  - 학교 담당자: 본인 이메일 + 우리 학교 교육청 담당자 이메일
#  - 교육청 담당자: 본인 이메일만 (학교에게 회신용)
# ─────────────────────────────────────────
st.markdown("---")
section("01-2", "이메일 등록",
        "역할별로 필요한 이메일만 표시됩니다.")

_role_email = st.session_state.get("role", "학교")

# 본인 이메일 (모든 역할 공통)
_my_email_label = {
    "실": "본인 이메일 (학교 담당자가 PIN·안내 보낼 수신처)",
    "학교": "본인 이메일 (백업·교육청 회신 수신처)",
    "교육청": "본인 이메일 (학교에게 답장 보낼 발신처)",
}.get(_role_email, "본인 이메일")

my_email = st.text_input(
    _my_email_label,
    value=st.session_state.get("my_email", ""),
    placeholder="예: teacher@school.go.kr",
    key="my_email_input",
)

# 학교 담당자만 — 교육청 담당자 이메일 (발송 대상)
edu_office_email = st.session_state.get("edu_office_email", "")
if _role_email == "학교":
    edu_office_email = st.text_input(
        "교육청 담당자 이메일 (학교가 보내는 대상)",
        value=edu_office_email,
        placeholder="예: officer@sen.go.kr",
        key="edu_office_email_input",
        help="점검 결과를 발송할 관할 교육청 담당자 이메일.",
    )

if st.button("이메일 저장", key="save_emails", width="stretch"):
    st.session_state["my_email"] = (my_email or "").strip()
    if _role_email == "학교":
        st.session_state["edu_office_email"] = (edu_office_email or "").strip()
    st.toast("이메일 저장 완료", icon=None)

# ─────────────────────────────────────────
# 온보딩 다시 보기 버튼
# ─────────────────────────────────────────
st.markdown("---")
oc1, oc2 = st.columns([3, 1])
with oc1:
    st.caption(
        "첫 방문 시 홈에 표시된 3단계 플로우 안내를 다시 보고 싶을 때 사용하세요."
    )
with oc2:
    if st.button("온보딩 다시 보기", key="show_onboarding_again",
                  width="stretch"):
        st.session_state["_onboarding_done"] = False
        st.toast("홈으로 이동하면 온보딩 안내가 다시 표시됩니다.", icon=None)
        st.switch_page("app.py")

# ─────────────────────────────────────────
# 공간 사전 등록 (이전 02 결재라인 기본값 섹션은 삭제 —
# 실제 결재는 K에듀파인에서 이뤄지므로 이 앱에서 관리할 필요 없음)
# ─────────────────────────────────────────
divider()
section("02", "공간 사전 등록")
st.caption("첫 점검 전에 학교 내 공간 목록을 미리 등록할 수 있습니다.")

school = st.session_state.get("school")
_role_here = st.session_state.get("role", "학교")
if _role_here == "실":
    st.info(
        "**실 담당자 모드** — 공간 등록은 학교 담당자의 권한입니다. "
        "본인 담당 공간이 보이지 않으면 학교 담당자에게 공간 등록 + 본인 할당을 요청하세요."
    )
elif not school:
    st.warning("먼저 학교를 선택하세요. (점검 시작 페이지)")
else:
    SPACE_TYPES = [
        "화학실", "물리실", "생명과학실", "지구과학실",
        "기술실", "가정실", "음악실", "미술실",
        "강당", "체육관", "급식실", "일반교실", "특별교실(과목 불명)",
    ]
    col_type, col_nick = st.columns([1, 2])
    with col_type:
        new_type = st.selectbox("공간 유형", SPACE_TYPES)
    with col_nick:
        new_nick = st.text_input("별칭 (선택)", placeholder="예: 3층 화학실 A")

    if st.button("공간 추가"):
        st.session_state.setdefault("registered_spaces", []).append({
            "space_id": uuid.uuid4().hex[:10],
            "school_code": school.get("정보공시 학교코드"),
            "type": new_type,
            "nickname": new_nick.strip() or None,
        })
        # toast 는 rerun 후에도 잠시 표시되어 사용자가 인지 가능
        st.toast(f"'{new_type}'{' (' + new_nick + ')' if new_nick.strip() else ''} 등록 완료",
                  icon=None)
        st.rerun()

    # 등록된 공간 목록
    spaces = [s for s in st.session_state.get("registered_spaces", [])
              if s.get("school_code") == school.get("정보공시 학교코드")]
    if spaces:
        st.markdown("##### 등록된 공간")
        for idx, sp in enumerate(spaces):
            colA, colB = st.columns([5, 1])
            with colA:
                st.markdown(f"- **{sp['type']}** · {sp.get('nickname') or '별칭 없음'} "
                            f"<span style='color:#888;font-size:11px'>({sp['space_id']})</span>",
                            unsafe_allow_html=True)
            with colB:
                if st.button("삭제", key=f"del_sp_{sp['space_id']}"):
                    st.session_state["registered_spaces"] = [
                        s for s in st.session_state["registered_spaces"]
                        if s["space_id"] != sp["space_id"]
                    ]
                    st.rerun()

# ─────────────────────────────────────────
# 02-2 실 담당자 명부 관리 — 학교 담당자 전용
#
# 학교 담당자가 공간별 담당 교사를 등록·PIN 발급·관리.
# 실 담당자는 본인이 등록한 PIN 으로 1_점검시작 페이지에서 인증해 점검·제출.
# ─────────────────────────────────────────
divider()
section(
    "02-2", "실 담당자 명부 관리",
    "공간별 담당 교사를 등록·PIN 발급·관리합니다. "
    "실 담당자는 본인 PIN 으로 점검·제출할 수 있습니다.",
)

if st.session_state.get("role") == "교육청":
    st.caption(
        "교육청 담당자 모드 — 본 섹션은 학교 담당자가 우리 학교의 "
        "공간별 담당 교사를 관리하는 화면입니다."
    )
elif st.session_state.get("role") == "실":
    st.info(
        "**실 담당자 모드** — 본인을 포함한 실 담당자 명부 등록·관리는 "
        "학교 담당자의 권한입니다. PIN 분실 시 학교 담당자에게 재발급을 요청하세요."
    )
elif not school:
    st.caption("먼저 학교를 선택하세요. (점검 시작 페이지)")
else:
    from modules.managers import (
        add_manager, deactivate_manager, is_demo_manager, list_managers,
        reactivate_manager, reissue_pin, update_manager,
    )

    _mgr_school_code = school.get("정보공시 학교코드")

    # 학교 등록 공간 담당 공간 선택 옵션
    _spaces_for_mgr = [
        s for s in st.session_state.get("registered_spaces", [])
        if s.get("school_code") == _mgr_school_code
    ]
    _space_options = {
        (
            f"{s['type']}"
            + (f" · {s['nickname']}" if s.get("nickname") else "")
            + f" ({s['space_id'][:6]})"
        ): s["space_id"]
        for s in _spaces_for_mgr
    }

    # ── 발급 직후 PIN 1회 표시 (보안: 평문은 화면에서만, 저장 안 됨) ──
    _newly_issued = st.session_state.pop("_newly_issued_manager_pin", None)
    if _newly_issued:
        st.success(
            f"**{_newly_issued['name']}** 등록 완료 · "
            f"매니저 ID `{_newly_issued['manager_id']}` · "
            f"**PIN: `{_newly_issued['pin']}`**"
        )
        st.warning(
            "**PIN 은 지금 한 번만 표시됩니다.** "
            "메모해서 본인에게 전달하세요. 분실 시 [PIN 재발급] 으로 "
            "새로 발급 가능하지만 이전 PIN 은 즉시 무효화됩니다."
        )
        # PIN 백업 다운로드 — 화면 잠시 떠나도 분실 방지
        import datetime as _dt_pin
        _pin_txt = (
            f"SafeLoop 실 담당자 인증 정보\n"
            f"=================================\n"
            f"학교: {school.get('학교명', '-')}\n"
            f"학교 코드: {school.get('정보공시 학교코드', '-')}\n"
            f"---------------------------------\n"
            f"이름: {_newly_issued['name']}\n"
            f"매니저 ID: {_newly_issued['manager_id']}\n"
            f"PIN (6자리): {_newly_issued['pin']}\n"
            f"---------------------------------\n"
            f"발급일시: {_dt_pin.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"이 정보를 본인에게 안전하게 전달하세요.\n"
            f"PIN 분실 시 학교 담당자가 [PIN 재발급] 으로 새 PIN 을 만들 수 있으나,\n"
            f"이전 PIN 은 즉시 무효화됩니다.\n"
        )
        _pin_fn = (
            f"SafeLoop_PIN_{_newly_issued['manager_id']}_"
            f"{_newly_issued['name']}_"
            f"{_dt_pin.datetime.now().strftime('%Y%m%d-%H%M')}.txt"
        )
        st.download_button(
            "PIN 정보 다운로드 (TXT 백업)",
            data=_pin_txt.encode("utf-8"),
            file_name=_pin_fn,
            mime="text/plain",
            key=f"dl_pin_{_newly_issued['manager_id']}",
            width="stretch",
            help="화면을 떠나기 전 다운로드 본인에게 전달 (메모 + 보안 폐기).",
        )

    # ── 현재 명부 ──
    # 시연 매니저(_demo:True)는 시연 모드가 켜져 있을 때만 명부에 노출.
    # 실 사용 모드에선 시연 흔적이 보이지 않도록 필터.
    _all_managers_raw = list_managers(_mgr_school_code, include_inactive=True)
    if st.session_state.get("demo_mode"):
        _all_managers = _all_managers_raw
    else:
        _all_managers = [m for m in _all_managers_raw if not m.get("_demo")]
    _actives = [m for m in _all_managers if m.get("active", True)]
    _inactives = [m for m in _all_managers if not m.get("active", True)]

    _summary_txt = f"등록된 실 담당자 ({len(_actives)}명 활성"
    if _inactives:
        _summary_txt += f", {len(_inactives)}명 비활성"
    _summary_txt += ")"
    st.markdown(f"##### {_summary_txt}")

    if not _all_managers:
        st.info("아직 등록된 실 담당자가 없습니다. 아래에서 추가하세요.")
    else:
        for _m in _all_managers:
            _mid = _m["manager_id"]
            _is_active = _m.get("active", True)
            _is_demo = is_demo_manager(_m)
            _border = "1px solid #E5E5E8" if _is_active else "1px solid #D5D5D5"
            _bg = "#FFFFFF" if _is_active else "#F5F5F5"
            _opacity = "1.0" if _is_active else "0.6"

            _badges_html = ""
            if not _is_active:
                _badges_html += "<span style='color:#999;margin-left:8px;'>(비활성)</span>"
            if _is_demo:
                _badges_html += (
                    "<span style='font-size:10px;color:#D50000;"
                    "background:#FFF2F2;border:1px solid #F8D0D0;"
                    "padding:1px 6px;border-radius:4px;margin-left:8px;'>"
                    "시연용</span>"
                )

            _email_disp = _m.get("email") or "이메일 없음"
            _spaces_count = len(_m.get("assigned_space_ids") or [])

            st.markdown(
                f"<div style='border:{_border};background:{_bg};border-radius:6px;"
                f"padding:10px 14px;margin-bottom:6px;opacity:{_opacity};'>"
                f"<b>{_m['name']}</b> "
                f"<code style='font-size:11px;color:#6B6B70;'>{_mid}</code>"
                f"{_badges_html}"
                f"<div style='font-size:12px;color:#6B6B70;margin-top:2px;'>"
                f"{_email_disp} · 담당 공간 {_spaces_count}개"
                f"</div></div>",
                unsafe_allow_html=True,
            )

            # 액션 4개
            _ac1, _ac2, _ac3, _ac4 = st.columns(4)
            with _ac1:
                # B10: 시연 매니저는 "담당 공간 변경"도 차단 — 시연 시나리오의
                # 공간 할당이 발표 중 실수로 깨지지 않도록.
                if st.button(
                    "담당 공간 변경", key=f"mgr_edit_{_mid}",
                    width="stretch", disabled=_is_demo,
                    help=("시연용 매니저는 보호됨 — 시연 흐름 유지"
                           if _is_demo else None),
                ):
                    st.session_state["_edit_mgr_id"] = _mid
                    st.rerun()
            # 시연 매니저(_demo:True) 보호 — PIN 재발급/비활성화 모두 차단.
            # 발표 도중 실수로 누르면 안내된 시연 PIN `000000` 이 무력화되어
            # 시연이 깨지는 사고 방지 (P1).
            _reissue_disabled = not _is_active or _is_demo
            _reissue_help = (
                "시연용 매니저는 보호됨 — 시연 PIN(000000) 유지"
                if _is_demo
                else ("이전 PIN 즉시 무효화됨" if _is_active
                       else "비활성 매니저는 PIN 발급 불가")
            )
            with _ac2:
                if st.button(
                    "PIN 재발급", key=f"mgr_reissue_{_mid}",
                    width="stretch", disabled=_reissue_disabled,
                    help=_reissue_help,
                ):
                    _new_pin = reissue_pin(_mgr_school_code, _mid)
                    if _new_pin:
                        st.session_state["_newly_issued_manager_pin"] = {
                            "manager_id": _mid,
                            "name": _m["name"],
                            "pin": _new_pin,
                        }
                        st.rerun()
                    else:
                        st.error("PIN 재발급 실패")
            with _ac3:
                if _is_active:
                    if st.button(
                        "비활성화", key=f"mgr_off_{_mid}",
                        width="stretch", disabled=_is_demo,
                        help=(
                            "시연용 매니저는 보호됨 — 시연 흐름 유지"
                            if _is_demo else None
                        ),
                    ):
                        deactivate_manager(_mgr_school_code, _mid)
                        st.toast(f"{_m['name']} 비활성화", icon=None)
                        st.rerun()
                else:
                    if st.button("재활성화", key=f"mgr_on_{_mid}",
                                  width="stretch"):
                        reactivate_manager(_mgr_school_code, _mid)
                        st.toast(f"{_m['name']} 재활성화", icon=None)
                        st.rerun()
            with _ac4:
                _last = _m.get("last_login_at")
                st.caption(
                    f"마지막 로그인: {_last[:16] if _last else '없음'}",
                )

            # 담당 공간 편집 패널 (선택된 매니저만 펼침)
            if st.session_state.get("_edit_mgr_id") == _mid:
                with st.container(border=True):
                    st.markdown(f"**{_m['name']} 의 담당 공간 변경**")
                    if not _space_options:
                        st.warning(
                            "할당 가능한 공간이 없습니다. "
                            "먼저 위 02 섹션에서 공간을 등록하세요."
                        )
                        if st.button("닫기", key=f"_close_edit_{_mid}"):
                            st.session_state.pop("_edit_mgr_id", None)
                            st.rerun()
                    else:
                        _current_ids = set(_m.get("assigned_space_ids") or [])
                        _new_labels = st.multiselect(
                            "담당할 공간 선택 (복수 가능)",
                            options=list(_space_options.keys()),
                            default=[
                                label for label, sid in _space_options.items()
                                if sid in _current_ids
                            ],
                            key=f"_edit_spaces_{_mid}",
                        )
                        _new_ids = [_space_options[lbl] for lbl in _new_labels]
                        _b1, _b2 = st.columns(2)
                        if _b1.button(
                            "저장", key=f"_save_edit_{_mid}",
                            type="primary", width="stretch",
                        ):
                            update_manager(
                                _mgr_school_code, _mid,
                                assigned_space_ids=_new_ids,
                            )
                            st.session_state.pop("_edit_mgr_id", None)
                            st.toast(f"{_m['name']} 담당 공간 변경 완료", icon=None)
                            st.rerun()
                        if _b2.button(
                            "취소", key=f"_cancel_edit_{_mid}",
                            width="stretch",
                        ):
                            st.session_state.pop("_edit_mgr_id", None)
                            st.rerun()

    # ── 신규 등록 폼 ──
    st.markdown("---")
    with st.expander(
        "새 실 담당자 등록",
        expanded=not bool(_actives),
    ):
        if not _spaces_for_mgr:
            st.warning(
                "먼저 위 02 섹션에서 **공간을 등록**하세요. "
                "공간이 있어야 담당 교사를 할당할 수 있습니다."
            )
        else:
            with st.form("_add_manager_form", clear_on_submit=True):
                _new_name = st.text_input(
                    "이름 *",
                    placeholder="예: 김선생님",
                    help="실 담당자 본인 이름. 명부에 표시되며 인증 화면 selectbox 에 노출됨.",
                )
                _col_email, _col_phone = st.columns(2)
                with _col_email:
                    _new_email = st.text_input(
                        "이메일 (선택)",
                        placeholder="예: kim@school.kr",
                    )
                with _col_phone:
                    _new_phone = st.text_input(
                        "전화 (선택)",
                        placeholder="예: 010-0000-0000",
                    )
                _new_space_labels = st.multiselect(
                    "담당 공간 선택 (복수 가능)",
                    options=list(_space_options.keys()),
                    help="이 실 담당자가 점검·제출할 수 있는 공간들. "
                          "나중에 [담당 공간 변경] 으로 수정 가능.",
                )
                _submitted = st.form_submit_button(
                    "등록 + PIN 발급",
                    type="primary",
                    width="stretch",
                )
                if _submitted:
                    if not _new_name or not _new_name.strip():
                        st.error("이름을 입력하세요.")
                    else:
                        try:
                            _new_ids = [
                                _space_options[lbl] for lbl in _new_space_labels
                            ]
                            _pub, _plain_pin = add_manager(
                                _mgr_school_code,
                                name=_new_name.strip(),
                                email=_new_email.strip(),
                                phone=_new_phone.strip(),
                                assigned_space_ids=_new_ids,
                            )
                            st.session_state["_newly_issued_manager_pin"] = {
                                "manager_id": _pub["manager_id"],
                                "name": _pub["name"],
                                "pin": _plain_pin,
                            }
                            st.rerun()
                        except Exception as _e:
                            st.error(f"등록 실패: {_e}")

# ─────────────────────────────────────────
# 02-3 결재 정책 — 단일/이중 결재 선택 (학교 담당자 전용)
#
# 학교마다 결재 흐름이 다름:
# - 단일 결재 (기본): 에듀파인 결재 완료된 파일을 SafeLoop 으로 그대로 발송.
# SafeLoop 안에 결재 입력 화면 없음. 가장 단순.
# - 이중 결재: 에듀파인 결재 + SafeLoop 안에서도 결재자 정보 기록.
# 자체 감사·추적 이력을 추가로 남기고 싶은 학교용.
# ─────────────────────────────────────────
divider()
section(
    "02-3",
    "결재 정책",
    "결재는 K-에듀파인 등 외부 시스템에서 진행됩니다. "
    "SafeLoop 안에서도 결재 정보를 한 번 더 기록할지 학교가 선택할 수 있습니다.",
)

if st.session_state.get("role") == "교육청":
    st.caption(
        "교육청 담당자 모드 — 결재 정책은 학교 담당자가 설정합니다."
    )
elif st.session_state.get("role") == "실":
    st.info(
        "**실 담당자 모드** — 결재 정책은 학교 담당자의 권한입니다. "
        "본인 점검 제출 시에는 결재 입력 화면이 없습니다 (학교 담당자가 검토·발송)."
    )
elif not school:
    st.caption("먼저 학교를 선택하세요. (점검 시작 페이지)")
else:
    from modules.storage import get_school_dual_approval, set_school_dual_approval
    _approval_school_code = school.get("정보공시 학교코드") or ""
    _cur_dual = get_school_dual_approval(_approval_school_code)

    _mode_label = (
        "이중 결재 (에듀파인 + SafeLoop 자체 기록)"
        if _cur_dual else
        "단일 결재 (에듀파인만 — 권장)"
    )
    st.markdown(
        f"<div style='padding:10px 14px;border:1px solid #E5E5E8;"
        f"border-left:3px solid #D50000;border-radius:6px;background:#FAFAFA;'>"
        f"<div style='font-size:11px;letter-spacing:0.2em;color:#6B6B70;"
        f"font-weight:600;margin-bottom:4px;'>현재 정책</div>"
        f"<b>{_mode_label}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    _new_dual = st.toggle(
        "SafeLoop 안에서도 결재 정보 기록 (이중 결재)",
        value=_cur_dual,
        key="_school_dual_approval_toggle",
        help=(
            "ON: 결과 저장 페이지에 결재자·일자 입력 칸이 나타나고, 입력 시 공문 "
            "PDF 가 함께 만들어집니다. OFF: 에듀파인 결재 완료된 파일만 발송 — "
            "더 단순한 흐름."
        ),
    )

    if _new_dual != _cur_dual:
        if st.button("정책 변경 적용", key="_apply_dual_approval",
                      type="primary", width="stretch"):
            set_school_dual_approval(_approval_school_code, _new_dual)
            st.toast(
                ("이중 결재로 전환" if _new_dual else "단일 결재(에듀파인만)로 전환")
                + " — 결과 저장 페이지에서 확인 가능",
                icon=None,
            )
            st.rerun()

    # 정책 설명 카드
    if _cur_dual:
        st.caption(
            "**이중 결재**: 학교 담당자가 결과 저장 페이지에서 결재자 이름을 "
            "입력하면 SafeLoop 안에도 결재 기록이 남고, `결재첨부_공문.pdf` 가 "
            "함께 생성됩니다. 에듀파인 결재는 외부에서 별도 진행."
        )
    else:
        st.caption(
            "**단일 결재 (기본)**: SafeLoop 안에서는 결재 입력을 받지 않습니다. "
            "에듀파인에서 결재 완료된 파일을 첨부해 교육청에 발송하세요. "
            "가장 단순하고 빠른 흐름 — 대부분 학교 권장."
        )

# ─────────────────────────────────────────
# 02-4 실 담당자 등록 정책 — 셀프 가입 (self) vs 사전 배정 (admin)
#
# 학교마다 운영 방식이 다름:
# - 사전 배정 (admin, 기본): 학교 담당자가 모든 실 담당자 + 공간 등록 + PIN 발급.
#   실 담당자는 PIN 으로 점검만. 통제 ↑.
# - 셀프 가입 (self): 학교 인증번호만 알려주면 실 담당자가 본인 정보 + 공간을
#   직접 등록. 학교 담당자 부담 ↓.
# 두 방식 모두 등록은 1회만, 2회부터는 자동 로그인 30일 또는 PIN 으로 점검만.
# ─────────────────────────────────────────
divider()
section(
    "02-4",
    "실 담당자 등록 정책",
    "실 담당자를 학교 담당자가 직접 등록할지(통제), "
    "또는 실 담당자가 본인 정보를 셀프 가입할지(자율) 학교가 선택합니다.",
)

if st.session_state.get("role") == "교육청":
    st.caption("교육청 담당자 모드 — 등록 정책은 학교 담당자가 설정합니다.")
elif st.session_state.get("role") == "실":
    st.info(
        "**실 담당자 모드** — 등록 정책은 학교 담당자의 권한입니다."
    )
elif not school:
    st.caption("먼저 학교를 선택하세요.")
else:
    from modules.storage import (
        get_school_registration_mode, set_school_registration_mode,
    )
    _reg_school_code = school.get("정보공시 학교코드") or ""
    _cur_mode = get_school_registration_mode(_reg_school_code)

    _MODE_LABEL = {
        "admin": "사전 배정 — 학교 담당자가 직접 등록 (통제)",
        "self": "셀프 가입 — 실 담당자가 본인 등록 (자율)",
    }
    st.markdown(
        f"<div style='padding:10px 14px;border:1px solid #E5E5E8;"
        f"border-left:3px solid #D50000;border-radius:6px;background:#FAFAFA;'>"
        f"<div style='font-size:11px;letter-spacing:0.2em;color:#6B6B70;"
        f"font-weight:600;margin-bottom:4px;'>현재 등록 정책</div>"
        f"<b>{_MODE_LABEL[_cur_mode]}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    _new_mode = st.radio(
        "등록 정책 선택",
        options=["admin", "self"],
        format_func=lambda m: _MODE_LABEL[m],
        index=0 if _cur_mode == "admin" else 1,
        key="_school_reg_mode_radio",
        label_visibility="collapsed",
    )

    if _new_mode != _cur_mode:
        if st.button("등록 정책 변경 적용", key="_apply_reg_mode",
                      type="primary", width="stretch"):
            set_school_registration_mode(_reg_school_code, _new_mode)
            st.toast(
                f"등록 정책 변경됨 — {_MODE_LABEL[_new_mode]}", icon=None,
            )
            st.rerun()

    # 정책별 안내
    if _cur_mode == "admin":
        st.caption(
            "**사전 배정 (기본)** — 위 02-2 [실 담당자 명부 관리] 에서 학교 "
            "담당자가 직접 실 담당자를 등록하고 PIN 을 발급해 전달합니다. "
            "공간도 02 [공간 사전 등록] 에서 학교 담당자가 등록·할당. "
            "실 담당자는 받은 PIN 으로 점검만 가능."
        )
    else:
        st.caption(
            "**셀프 가입** — 학교 담당자가 학교 인증번호(6자리)만 실 담당자에게 "
            "알려주면, 실 담당자가 [실 담당자] 카드 진입 시 본인 이름·이메일·"
            "담당 공간을 직접 등록합니다. PIN 은 자동 발급되며 다음 로그인부터 "
            "사용. 학교 담당자 명부에 자동으로 추가됨."
        )

# ─────────────────────────────────────────
# AI 공급자 (이전 04 03 으로 번호 재정렬)
# ─────────────────────────────────────────
divider()
section("03", "AI 공급자",
        "Claude · Gemini · GPT 중 선택. "
        "프롬프트·파이프라인은 동일하며 호출 대상만 교체됩니다.")

_providers = providers_status()
_avail_map = {p["id"]: p for p in _providers}

# 현재 선택
current_choice = st.session_state.get("ai_provider") or next(
    (p["id"] for p in _providers if p["available"]), "anthropic"
)

options = [p["id"] for p in _providers]

def _fmt(pid: str) -> str:
    p = _avail_map[pid]
    mark = "사용 가능" if p["available"] else "키 필요"
    src = f" · {p['key_source']}" if p.get("key_source") else ""
    return f"{p['label']} — {mark}{src}"

sel = st.selectbox(
    "공급자 선택",
    options=options,
    index=options.index(current_choice) if current_choice in options else 0,
    format_func=_fmt,
    key="_ai_provider_selectbox",
)
st.session_state["ai_provider"] = sel

# 선택된 공급자의 키 입력
selected = _avail_map[sel]
key_field = f"api_key_{sel}"
existing = st.session_state.get(key_field, "")
placeholder = "환경변수에서 자동 감지됨" if selected["key_source"] == "환경변수" and not existing \
    else "sk-..."
new_key = st.text_input(
    f"{selected['label']} API 키",
    value=existing,
    placeholder=placeholder,
    type="password",
    help=f"환경변수 {selected['env_var']} 로도 설정 가능",
)
if new_key != existing:
    st.session_state[key_field] = new_key.strip()

st.caption("키는 입력 즉시 세션에 저장됩니다. 아래 버튼은 공급자에 실제 ping 호출로 연결 확인만 합니다.")
if st.button("연결 확인 (ping)"):
    if not api_key_available():
        st.error("이 공급자의 API 키가 감지되지 않습니다.")
    else:
        with st.spinner(f"{selected['label']} 에 ping 호출 중…"):
            ok, msg = test_provider_connection(sel)
        if ok:
            st.success(f"{selected['label']} — {msg}")
        else:
            st.error(f"{selected['label']} — {msg}")

# 전체 공급자 상태 요약
st.markdown("##### 전체 공급자 상태")
for p in _providers:
    status = "사용 가능" if p["available"] else "키 없음"
    src = f" · {p['key_source']}" if p.get("key_source") else ""
    st.markdown(f"- **{p['label']}** — {status}{src}")

st.markdown("##### 추가 옵션")
img_check = st.toggle(
    "이미지 품질 사전 검사 (블러·어두움 · 자동 회전·리사이즈)",
    value=st.session_state.get("image_quality_check", True),
    help="흐리거나 어두운 사진을 AI에 보내기 전에 차단합니다.",
)
st.session_state["image_quality_check"] = img_check

verify_space = st.toggle(
    "AI 공간 유형 검증 (사용자 선택과 비교)",
    value=st.session_state.get("verify_space_type", True),
    help="AI 가 사진을 분석해 공간 유형을 추정하고, 점검 시작에서 선택한 "
         "공간과 다르면 경고합니다. 메인 분석은 항상 사용자 선택을 기준으로 진행. "
         "OFF 시 Stage 1 호출 생략 (비용·시간 절감 약 5~10초·$0.015/회).",
)
st.session_state["verify_space_type"] = verify_space

divider()
section("04", "AI 시스템 상태")
if api_key_available():
    st.success(f"AI 파이프라인 사용 가능 — 현재 공급자: {current_provider_label()}")
else:
    st.error("현재 선택된 공급자의 API 키가 없습니다. 위 섹션에서 키를 입력하세요.")

# ─────────────────────────────────────────
# 운영자 도구 (관리자만)
# 환경변수 SAFELOOP_ADMIN=1 또는 URL ?admin=1 로 활성화.
# 일반 학교·교육청 사용자에게는 디스크 사용량·캐시 정리·세션 전용 모드 등의
# 운영성 옵션이 보이지 않도록 차단 — 데이터 저장 원칙 안내도 운영자 책임으로 분리.
# ─────────────────────────────────────────
import os as _os
_is_admin = _os.environ.get("SAFELOOP_ADMIN") == "1"
try:
    _qp_admin = st.query_params
    _is_admin = _is_admin or str(_qp_admin.get("admin", "0")) in ("1", "true", "True")
except Exception:
    pass

if _is_admin:
    divider()
    section("05", "운영자 도구 — 디스크 사용량 · 캐시 정리",
            "로컬/자체 호스팅 환경 전용. Streamlit Cloud는 재시작 시 초기화.")
    with st.expander("관리자 도구 열기", expanded=False):
        st.caption(
            "이 정보는 **현재 Streamlit 서버가 실행 중인 호스트의 로컬 파일 시스템** 기준입니다. "
            "Streamlit Cloud 환경에선 컨테이너 재시작마다 초기화되므로 관리 의미는 제한적이며, "
            "주로 **로컬 개발·자체 호스팅 운영** 시 캐시 누적 점검용입니다."
        )

        from modules.storage import storage_usage, cleanup_old_cache
        usage = storage_usage()
        def _fmt(b: int) -> str:
            if b < 1024:
                return f"{b}B"
            if b < 1024 * 1024:
                return f"{b/1024:.1f}KB"
            return f"{b/1024/1024:.2f}MB"

        uc1, uc2, uc3 = st.columns(3)
        uc1.metric("로컬 저장소", _fmt(usage["school_storage"]))
        uc2.metric("AI 캐시", _fmt(usage["ai_cache"]))
        uc3.metric("교육청 수신함", _fmt(usage["edu_receipt"]))

        cdays = st.slider("캐시 보존 기간(일)", 7, 90, 30, step=1)
        if st.button(f"{cdays}일 이전 AI 캐시 정리"):
            n, freed = cleanup_old_cache(days=cdays)
            if n:
                st.success(f"{n}개 파일 삭제 · {_fmt(freed)} 회수")
            else:
                st.info("정리할 파일이 없습니다.")
            st.rerun()

        # 로컬 저장소 정리 (위험 경고 + confirm_button)
        st.markdown("---")
        st.markdown(
            "<div style='border:1px solid #F8D0D0;background:#FFF6F6;"
            "border-radius:6px;padding:10px 14px;font-size:12px;color:#D50000;'>"
            "<b>로컬 저장소 정리</b>는 실제 점검 이력 폴더를 통째로 삭제합니다. "
            "복구 불가 — 신중히 사용하세요. (`_ai_cache`, `_drafts` 등 시스템 폴더는 보호됩니다.)"
            "</div>",
            unsafe_allow_html=True,
        )
        sdays = st.slider("로컬 저장소 보존 기간(일)", 30, 365, 90, step=10,
                           key="school_storage_days")
        from modules.storage import cleanup_school_storage
        if confirm_button(
            f"{sdays}일 이전 로컬 저장소 점검 이력 삭제",
            key="cleanup_school_storage",
            message=f"{sdays}일 이상 지난 모든 학교의 점검 세션 폴더를 삭제합니다. "
                    f"이 작업은 되돌릴 수 없습니다.",
        ):
            n_s, freed_s = cleanup_school_storage(days=sdays)
            if n_s:
                st.success(f"세션 폴더 {n_s}개 삭제 · {_fmt(freed_s)} 회수")
            else:
                st.info("정리할 세션 폴더가 없습니다.")
            st.rerun()

divider()
_sess_sec = "06" if _is_admin else "05"
section(_sess_sec, "세션 관리",
        "모든 세션 데이터(학교 선택·공간·촬영·AI 결과 등)를 초기화합니다.")
if confirm_button("전체 세션 초기화", key="reset_all_settings",
                   message="학교 선택·공간·촬영본·AI 결과 등 모든 세션 데이터 삭제."):
    reset_all()
    st.success("초기화 완료")
    st.rerun()
