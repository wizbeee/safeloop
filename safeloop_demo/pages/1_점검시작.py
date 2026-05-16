"""
Step 1~2 — 학교 식별 + 인증 + 공간 선택/등록.

학교 찾기 3가지 방식(탭):
1) GPS 자동 (편의용 — HTTPS 필요)
2) 학교명 검색
3) 지역 단계 검색 (시도 시군구 학교)

인증은 '학교 식별번호'(정보공시 코드, 자동 표시) + '담당자 인증번호'(수동 입력) 2요소.
"""
from __future__ import annotations

import uuid

import streamlit as st

from modules.data_loader import (
    get_school_by_code,
    issue_auth_code,
    list_schools,
    list_sido,
    list_sigungu,
    search_schools_by_name,
    verify_auth_code,
)
from modules.session import ensure_state
from modules.ui import (
    apply_theme, divider, hero, numeric_input_patch, render_sidebar, section,
)

st.set_page_config(page_title="점검 시작 · SafeLoop", page_icon="static/icon-192.png",
                   layout="centered", initial_sidebar_state="collapsed")
apply_theme()
ensure_state()
render_sidebar(active_key="inspect")

# 역할 가드 — '점검 시작' 은 학교·실 담당자가 본교 점검을 시작하는 페이지.
# 교육청 담당자는 본인이 직접 점검하지 않으므로 수신함으로 유도.
if st.session_state.get("role") == "교육청":
    st.warning(
        "**교육청 담당자 모드** — '점검 시작' 은 학교·실 담당자가 본교 점검을 "
        "수행하는 화면입니다. 교육청 관점에서는 학교가 제출한 점검 결과를 "
        "'교육청 수신함' 에서 확인·검증하세요."
    )
    if st.button("교육청 수신함으로 이동", key="inspect_guard_inbox",
                  type="primary", width="stretch"):
        st.switch_page("pages/7_교육청수신함.py")
    st.stop()

hero("단계 1 — 점검 시작", "점검 시작", "학교를 찾아 인증한 뒤, 점검할 공간을 선택하세요.")

# 미저장 점검 작업 알림 — 다른 페이지에서 점검 진행 중에 여기 들어왔다면 사용자 의식 환기
from modules.session import has_unsaved_inspection_work as _has_unsaved
if _has_unsaved():
    st.warning(
        "**저장되지 않은 점검 작업이 있습니다** — 새 공간 선택·등록 시 사라집니다. "
        "현재 작업을 보관하려면 **결과 저장 페이지**에서 먼저 저장한 뒤 이 페이지로 돌아오세요."
    )
    if st.button("결과 저장 페이지로 돌아가기", key="goto_save_unsaved",
                  width="stretch"):
        st.switch_page("pages/3_결과저장.py")

# 자동 로그인 — 쿠키에 학교 정보가 저장되어 있고 아직 인증 전이면 자동 인증 시도
if not st.session_state.get("school_auth_verified") and not st.session_state.get("school"):
    from modules.auth import get_remembered_school, verify_school_token
    _remembered_code = get_remembered_school()
    if _remembered_code:
        _school = get_school_by_code(_remembered_code)
        _expected = issue_auth_code(_remembered_code) if _school else None
        if _school and _expected and verify_school_token(_remembered_code, _expected):
            st.session_state["school"] = _school
            st.session_state["school_auth_verified"] = True
            try:
                from modules.storage import load_school_profile
                profile = load_school_profile(_remembered_code)
                if profile.get("eduline"):
                    st.session_state["eduline"] = profile["eduline"]
            except Exception:
                pass
            st.toast(f"자동 로그인 — {_school.get('학교명', '')}", icon=None)

# 실 담당자 자동 로그인 — 쿠키에서 (school_code, manager_id) 읽어 학교 자동 인식.
# PIN 은 보안상 자동 입력하지 않고, 매니저 명단 selectbox 의 기본값으로만 사용.
# 사용자는 본인 PIN 만 입력하면 즉시 인증 가능 (본인 학교 재선택 불필요).
if (st.session_state.get("role") == "실"
        and not st.session_state.get("school")
        and not st.session_state.get("space_manager")):
    from modules.auth import get_remembered_manager
    _remembered_mgr = get_remembered_manager()
    if _remembered_mgr:
        _rem_school_code, _rem_manager_id = _remembered_mgr
        _rem_school = get_school_by_code(_rem_school_code)
        if _rem_school:
            st.session_state["school"] = _rem_school
            # 매니저 인증 단계 selectbox 기본 선택용
            st.session_state["_remembered_mgr_id"] = _rem_manager_id
            st.toast(f"자동 인식 — {_rem_school.get('학교명', '')}", icon=None)

# 1-7 수정: 공간이 이미 선택된 경우 상단에 즉시 이동 가능한 바로가기 표시
_active_sp = st.session_state.get("active_space")
from modules.session import is_authenticated_for_role as _is_auth_role
if _active_sp and _is_auth_role() and st.session_state.get("school"):
    _nick = _active_sp.get("nickname") or "별칭 없음"
    colQ1, colQ2 = st.columns([3, 2])
    with colQ1:
        st.markdown(
            f"<div style='border:1px solid #E5E5E8;border-left:3px solid #D50000;"
            f"border-radius:6px;padding:10px 14px;background:#FFF;margin-bottom:10px;'>"
            f"<span style='font-size:11px;letter-spacing:0.2em;color:#D50000;font-weight:600;'>"
            f"진행 중</span> "
            f"<b style='margin-left:6px;'>{_active_sp['type']}</b>"
            f"<span style='color:#6B6B70;'> · {_nick}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with colQ2:
        if st.button("AI 점검으로 바로 이동", type="primary",
                      key="quick_goto_ai", width="stretch"):
            st.switch_page("pages/2_AI점검.py")

# ─────────────────────────────────────────
# 1) 학교 찾기
# ─────────────────────────────────────────
section("01", "학교 찾기")

current = st.session_state.get("school")
if current:
    st.markdown(
        f"<div class='sl-card sl-card-accent'>"
        f"<div style='font-size:12px;color:#6B6B70;letter-spacing:0.1em;margin-bottom:4px;'>선택된 학교</div>"
        f"<div style='font-size:18px;font-weight:700;color:#0A0A0B;margin-bottom:4px;'>{current.get('학교명')}</div>"
        f"<div style='font-size:13px;color:#6B6B70;'>{current.get('시도교육청')} · {current.get('지역')} · "
        f"{current.get('학교급')} · {current.get('설립구분')}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.button("다른 학교 선택", key="change_school"):
        st.session_state["school"] = None
        st.session_state["school_auth_verified"] = False
        st.rerun()

if not current:
    tab_name, tab_region, tab_gps = st.tabs([
        "학교명으로", "지역으로", "GPS (참고용)"
    ])

    # -- 학교명 검색 --
    with tab_name:
        q = st.text_input("학교명", placeholder="예: 원촌중학교", key="search_q",
                          label_visibility="collapsed")
        if q:
            df = search_schools_by_name(q)
            if df.empty:
                st.info("검색 결과가 없습니다. 다른 키워드로 시도하세요.")
            else:
                # 1-2 수정: 결과가 많을 때 페이지네이션 + 정렬
                total_hits = len(df)
                df = df.sort_values("학교명").reset_index(drop=True)
                PAGE_SIZE = 20
                page_key = f"_page_search_{q}"
                cur_page = int(st.session_state.get(page_key, 1))
                total_pages = max(1, (total_hits + PAGE_SIZE - 1) // PAGE_SIZE)
                cur_page = max(1, min(cur_page, total_pages))

                caption_txt = f"{total_hits}개 일치"
                if total_hits > PAGE_SIZE:
                    caption_txt += f" · {cur_page}/{total_pages} 페이지 (페이지당 {PAGE_SIZE}개)"
                st.caption(caption_txt)

                start = (cur_page - 1) * PAGE_SIZE
                page_df = df.iloc[start:start + PAGE_SIZE]

                for i, row in page_df.iterrows():
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(
                            f"**{row['학교명']}** "
                            f"<span class='sl-pill'>{row['학교급']}</span>"
                            f"<span class='sl-pill'>{row['설립구분']}</span> \n"
                            f"<span style='color:#6B6B70;font-size:12px'>"
                            f"{row['시도교육청']} · {row['지역']}</span>",
                            unsafe_allow_html=True,
                        )
                    with c2:
                        if st.button("선택", key=f"pick_name_{i}_{row['정보공시 학교코드']}"):
                            full = get_school_by_code(row["정보공시 학교코드"])
                            st.session_state["school"] = full
                            st.session_state["school_auth_verified"] = False
                            st.rerun()

                # 페이지네이션 컨트롤
                if total_hits > PAGE_SIZE:
                    nav_prev, nav_info, nav_next = st.columns([1, 2, 1])
                    with nav_prev:
                        if st.button("이전", key=f"pg_prev_{q}",
                                      disabled=(cur_page <= 1),
                                      width="stretch"):
                            st.session_state[page_key] = cur_page - 1
                            st.rerun()
                    with nav_info:
                        st.caption(
                            f"<div style='text-align:center;padding-top:6px;'>"
                            f"{cur_page} / {total_pages}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    with nav_next:
                        if st.button("다음 ", key=f"pg_next_{q}",
                                      disabled=(cur_page >= total_pages),
                                      width="stretch"):
                            st.session_state[page_key] = cur_page + 1
                            st.rerun()

    # -- 지역 단계 검색 --
    with tab_region:
        c1, c2 = st.columns(2)
        with c1:
            sido = st.selectbox("시도교육청", ["선택"] + list_sido(), key="sel_sido_tab")
        with c2:
            if sido != "선택":
                sgg = st.selectbox("시군구", ["선택"] + list_sigungu(sido), key="sel_sigungu_tab")
            else:
                sgg = "선택"
        if sido != "선택" and sgg != "선택":
            df = list_schools(sido, sgg)
            q2 = st.text_input("학교명 추가 필터 (선택)", key="region_q",
                               placeholder="이 지역 내 학교명 필터", label_visibility="collapsed")
            if q2:
                df = df[df["학교명"].str.contains(q2, na=False)]
            if df.empty:
                st.info("해당 지역에 학교가 없습니다.")
            else:
                st.caption(f"{len(df)}개 학교")
                for i, row in df.head(80).iterrows():
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(
                            f"**{row['학교명']}** "
                            f"<span class='sl-pill'>{row['학교급']}</span>"
                            f"<span class='sl-pill'>{row['설립구분']}</span> \n"
                            f"<span style='color:#6B6B70;font-size:12px'>{row['지역']}</span>",
                            unsafe_allow_html=True,
                        )
                    with c2:
                        if st.button("선택", key=f"pick_region_{i}_{row['정보공시 학교코드']}"):
                            full = get_school_by_code(row["정보공시 학교코드"])
                            st.session_state["school"] = full
                            st.session_state["school_auth_verified"] = False
                            st.rerun()

    # -- GPS (참고용 — 학교 선택은 다른 탭으로) --
    with tab_gps:
        st.markdown(
            "<div class='sl-card'>"
            "<b>현재 위치 확인 (참고용)</b><br>"
            "<span style='color:#6B6B70;font-size:13px'>"
            "GPS는 위치 표시만 제공합니다. <b>학교 선택은 ‘학교명으로’ 또는 ‘지역으로’ 탭</b>에서 진행하세요. "
            "iOS Safari에선 HTTPS 접속이 필요합니다."
            "</span></div>",
            unsafe_allow_html=True,
        )
        try:
            from streamlit_geolocation import streamlit_geolocation # type: ignore
            loc = streamlit_geolocation()
            if loc and loc.get("latitude") and loc.get("longitude"):
                st.success(f"현재 위치: {loc['latitude']:.5f}, {loc['longitude']:.5f}")
            else:
                st.caption("브라우저 위치 권한을 허용해주세요.")
        except Exception:
            st.warning("GPS 컴포넌트를 사용할 수 없습니다. 학교명/지역 탭을 이용하세요.")

# ─────────────────────────────────────────
# 2) 인증 — 역할별 분기
# role="실" : 학교 인증번호 대신 매니저 PIN (학교 담당자가 발급)
# role="학교"/그 외: 학교 인증번호 (기존 흐름)
# ─────────────────────────────────────────
_role = st.session_state.get("role", "학교")

# ─────────────────────────────────────────
# 2-A) 실 담당자 인증 — manager_id 선택 + PIN 입력
# ─────────────────────────────────────────
if (_role == "실" and st.session_state.get("school")
        and not st.session_state.get("space_manager")):
    divider()
    section("02", "실 담당자 인증",
            "본인 매니저 ID 선택 + 학교 담당자가 발급한 6자리 PIN 입력")

    from modules.managers import (
        list_managers, ensure_demo_manager, DEMO_PIN, authenticate_manager,
    )
    from modules.auth import remember_manager

    school = st.session_state["school"]
    school_code = school.get("정보공시 학교코드")

    # 시연 모드 — 매니저가 없으면 데모 매니저 자동 등록 + 안내
    # 학교에 이미 등록된 공간이 있으면 모두 데모 매니저에게 자동 할당해서
    # 시연 흐름이 "본인에게 할당된 공간이 없습니다" 안내에서 막히지 않도록 한다.
    if st.session_state.get("demo_mode"):
        try:
            registered = st.session_state.get("registered_spaces", []) or []
            demo_space_ids = [
                s.get("space_id") for s in registered
                if s.get("school_code") == school_code and s.get("space_id")
            ]
            ensure_demo_manager(
                school_code,
                name="시연 담당교사",
                assigned_space_ids=demo_space_ids,
            )
        except Exception:
            pass

    managers = list_managers(school_code)

    if not managers:
        st.warning(
            "이 학교에 등록된 실 담당자가 없습니다. **학교 담당자**가 먼저 "
            "[설정] 페이지에서 실 담당자를 등록하고 PIN을 발급해야 합니다."
        )
        if st.button("학교 담당자로 전환해서 등록하러 가기",
                      key="switch_to_school_for_register",
                      width="stretch"):
            st.session_state["role"] = "학교"
            st.session_state["school_auth_verified"] = False
            st.rerun()
    else:
        # manager_id 선택 — 매니저 명단을 "이름 (M001)" 형식으로 표시
        mgr_options = {
            f"{m['name']} ({m['manager_id']})": m["manager_id"]
            for m in managers
        }
        # 쿠키에 기억된 매니저가 있으면 그 위치를 selectbox 기본값으로
        _options_list = list(mgr_options.keys())
        _default_idx = 0
        _remembered_mid = st.session_state.get("_remembered_mgr_id")
        if _remembered_mid:
            for _i, _label in enumerate(_options_list):
                if mgr_options[_label] == _remembered_mid:
                    _default_idx = _i
                    break
        colA, colB = st.columns([3, 2])
        with colA:
            picked_label = st.selectbox(
                "본인 이름 선택", _options_list,
                index=_default_idx,
                key="_space_mgr_picker",
                help="학교 담당자가 등록한 명부에서 본인을 찾으세요.",
            )
            picked_mid = mgr_options.get(picked_label, "")
            pin_input = st.text_input(
                "PIN (6자리 숫자)",
                type="password",
                max_chars=6, placeholder="예: 000000",
                key="_space_mgr_pin",
                help="학교 담당자가 발급한 PIN. 분실 시 학교 담당자에게 재발급 요청.",
            )
            numeric_input_patch("PIN (6자리 숫자)")
            remember_me = st.checkbox(
                "이 기기에서 자동 로그인 (30일)",
                value=False,
                key="_space_mgr_remember",
                help="본인 지급 기기에서만 체크. 공용 PC·외부 기기에서는 해제.",
            )
            submit_mgr = st.button(
                "실 담당자 인증", type="primary", width="stretch",
                key="_space_mgr_submit",
            )

        with colB:
            if st.session_state.get("demo_mode"):
                st.markdown(
                    f"<div class='sl-card' style='background:#FFF2F2; border-color:#F8D0D0;'>"
                    f"<div class='sl-num' style='margin-bottom:2px;'>시연 모드 전용</div>"
                    f"<div style='font-size:13px; color:#6B6B70;'>데모 매니저 PIN</div>"
                    f"<div style='font-family:monospace; font-size:28px; font-weight:800; color:#D50000; letter-spacing:0.08em; margin:4px 0;'>{DEMO_PIN}</div>"
                    f"<div style='font-size:11px; color:#9A9A9F;'>실 운영 시 학교 담당자가 발급.</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button("자동 입력", key="_space_mgr_autofill",
                              width="stretch"):
                    st.session_state["_space_mgr_pin"] = DEMO_PIN
                    st.rerun()
            else:
                st.caption("실 운영 모드 — PIN은 학교 담당자가 발급합니다.")

        if submit_mgr:
            if not picked_mid:
                st.error("본인 이름을 선택하세요.")
            elif not pin_input or len(pin_input) != 6 or not pin_input.isdigit():
                st.error("PIN은 6자리 숫자여야 합니다.")
            else:
                result = authenticate_manager(school_code, picked_mid, pin_input)
                if result:
                    # 실 담당자 인증은 space_manager 객체 존재로 표현 — school_auth_verified
                    # 는 학교 인증번호 통과 전용이므로 set 하지 않는다 (의미 분리).
                    st.session_state["space_manager"] = result
                    if remember_me:
                        remember_manager(school_code, picked_mid, pin_input)
                    st.success(f"{result.get('name', picked_mid)} 님 인증되었습니다.")
                    st.rerun()
                else:
                    st.error("PIN이 일치하지 않거나 비활성 매니저입니다.")

# ─────────────────────────────────────────
# 2-B) 학교/일반 담당자 인증 — 기존 6자리 학교 인증번호
# ─────────────────────────────────────────
if (_role != "실" and st.session_state.get("school")
        and not st.session_state.get("school_auth_verified")):
    divider()
    section("02", "담당자 인증",
            "학교 식별번호는 공개 정보로 자동 표시됩니다. 담당자 인증번호만 입력하세요.")

    school = st.session_state["school"]
    code = school.get("정보공시 학교코드")
    expected = issue_auth_code(code)

    # 식별번호 (자동 표시)
    st.markdown(
        f"<div class='sl-card'>"
        f"<div style='font-size:11px; letter-spacing:0.2em; color:#6B6B70; margin-bottom:4px;'>학교 식별번호 (자동)</div>"
        f"<div style='font-family:monospace; font-size:20px; font-weight:700; color:#0A0A0B; letter-spacing:0.04em;'>{code}</div>"
        f"<div style='font-size:12px; color:#9A9A9F; margin-top:4px;'>교육부 정보공시가 부여한 공개 식별자입니다. 입력 불필요.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 1-4: 플래그를 expander 바깥에서 설정 — 한 번이라도 페이지 보면 이후 접힘
    _was_seen = st.session_state.get("_seen_auth_help", False)
    with st.expander("담당자 인증번호가 없으신가요? (발급 절차 안내)", expanded=not _was_seen):
        st.markdown(
            "**담당자 인증번호**는 점검을 등록할 자격이 있는 **담당 교사·시설관리자**를 증명하는 "
            "6자리 숫자 비밀번호입니다.\n\n"
            "##### 발급 절차 (실 운영 시)\n"
            "1. **학교 교육청 신청** — 학교 측에서 점검 담당 교사·시설관리자를 지정해 "
            "교육청 시설안전 담당 부서에 인증번호 신청 (공문 또는 SafeLoop 신청 양식)\n"
            "2. **교육청 발급** — 교육청이 학교 코드 기반으로 6자리 인증번호 자동 생성 "
            "공문·이메일·시도교육청 행정망(K-에듀파인 등)으로 학교에 회신\n"
            "3. **학교 내부 전달** — 학교 행정실 담당 교사에게 인증번호 전달\n"
            "4. **분실·재발급** — 인증번호 분실 시 학교가 교육청에 재발급 요청 (학교 단위 1회 재발급 권장)\n\n"
            "##### 운영 시 받는 곳\n"
            "- **교사 본인** — 학교 행정실 또는 교육청 시설안전 담당자\n"
            "- **시설관리자** — 학교장 직접 전달 또는 행정실 보관함\n"
            "- **교감·교장** — 교육청 시설안전 담당 직접 발급\n\n"
            "##### 중요 안내\n"
            "- **학교 코드**(예: `S120002870`)는 위에 자동 표시됩니다 — 공개 정보, 입력 불필요\n"
            "- **담당자 인증번호**는 비공개 — 외부 공유 금지\n"
            "- **이 앱은 현재 시연 모드**이므로 실제 발급 체계가 없어, "
            "우측의 <span style='color:#D50000;font-weight:700'>시연 모드 번호</span>를 "
            "그대로 입력하거나 **자동 입력** 버튼을 누르면 됩니다",
            unsafe_allow_html=True,
        )
    st.session_state["_seen_auth_help"] = True

    # 인증번호 (수동 입력 + 시연용 자동 입력)
    colA, colB = st.columns([3, 2])

    # 입력값 소스: 자동입력 버튼 누르면 세션에 저장 위젯에 주입
    default_val = st.session_state.get("_auth_prefill", "")

    with colA:
        auth_input = st.text_input(
            "담당자 인증번호 (6자리 숫자)",
            value=default_val,
            max_chars=6, placeholder="예: 000000",
            help="실제 운영: 교육청 발급. 시연 중: 우측 빨강 카드 번호 입력 or '자동 입력' 버튼.",
            key="auth_input",
        )
        # 모바일 숫자 키패드 강제 (iOS·Android 모두)
        numeric_input_patch("담당자 인증번호")
        remember_school_login = st.checkbox(
            "이 기기에서 자동 로그인 (30일)",
            value=False,
            key="remember_school_login",
            help="본인 지급 기기에서만 체크하세요. 공용 PC·외부 기기에서는 해제 권장.",
        )
        submit = st.button("인증 확인", type="primary", width="stretch")

    with colB:
        if st.session_state.get("demo_mode"):
            st.markdown(
                f"<div class='sl-card' style='background:#FFF2F2; border-color:#F8D0D0;'>"
                f"<div class='sl-num' style='margin-bottom:2px;'>시연 모드 전용</div>"
                f"<div style='font-size:13px; color:#6B6B70;'>이 학교의 인증번호</div>"
                f"<div style='font-family:monospace; font-size:28px; font-weight:800; color:#D50000; letter-spacing:0.08em; margin:4px 0;'>{expected}</div>"
                f"<div style='font-size:11px; color:#9A9A9F;'>실제 운영 시 비공개.</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            # 시연 모드: 자동 입력 버튼 단일 — 항상 expected 값으로 덮어씀
            # (이전 버전의 "이미 입력된 값 확인" 분기는 사용자 혼란만 줘서 제거)
            if st.button("자동 입력", key="auto_fill_auth",
                          width="stretch"):
                st.session_state["_auth_prefill"] = expected
                st.rerun()
        else:
            st.caption("시연 모드 OFF — 인증번호는 교육청·학교장 발급분을 사용하세요.")

    if submit:
        if not auth_input or len(auth_input) != 6 or not auth_input.isdigit():
            st.error("인증번호는 6자리 숫자여야 합니다.")
        elif verify_auth_code(code, auth_input):
            st.session_state["school_auth_verified"] = True
            st.session_state["_auth_prefill"] = ""
            # 학교 프로필 자동 로드 (결재라인 등)
            try:
                from modules.storage import load_school_profile
                profile = load_school_profile(code)
                if profile.get("eduline"):
                    st.session_state["eduline"] = profile["eduline"]
            except Exception:
                pass
            # 자동 로그인 체크 시 30일 쿠키 발급
            if remember_school_login:
                from modules.auth import remember_school
                remember_school(code, auth_input)
            st.success("인증되었습니다.")
            st.rerun()
        else:
            st.error("인증번호가 일치하지 않습니다.")

# ─────────────────────────────────────────
# 3) 공간 선택 / 등록
# role="실" : 본인 assigned_space_ids 와 매칭되는 공간만 표시, 새 공간 등록 불가
# 그 외 : 학교의 모든 등록 공간 + 새 공간 등록 가능
#
# 가드 — 역할별 인증 방식이 달라 통합 헬퍼로 검사 (학교 인증번호 또는 매니저 PIN)
# ─────────────────────────────────────────
if _is_auth_role():
    divider()

    _role = st.session_state.get("role", "학교")
    _space_mgr = st.session_state.get("space_manager") or {}
    _is_space_role = (_role == "실")

    if _is_space_role:
        section("03", "내 담당 공간 선택",
                f"{_space_mgr.get('name', '실 담당자')} 님이 담당하는 공간만 표시됩니다.")
    else:
        section("03", "점검할 공간 선택")

    spaces = st.session_state.get("registered_spaces", [])
    school_code = st.session_state["school"].get("정보공시 학교코드")
    spaces_here = [s for s in spaces if s.get("school_code") == school_code]

    # 실 담당자 — 본인 담당 공간만 필터링
    if _is_space_role:
        my_space_ids = set(_space_mgr.get("assigned_space_ids") or [])
        if my_space_ids:
            spaces_here = [s for s in spaces_here if s.get("space_id") in my_space_ids]
        else:
            spaces_here = [] # 담당 공간 0개 학교 담당자에게 요청 안내
        # 실 담당자는 새 공간 등록 권한 없음 단일 탭만
        tab_pick = st.container()
        tab_new = None
    else:
        tab_pick, tab_new = st.tabs(["등록된 공간", "새 공간 등록"])

    with tab_pick:
        if not spaces_here:
            if _is_space_role:
                # 실 담당자: 본인에게 할당된 공간이 없는 경우
                if not (_space_mgr.get("assigned_space_ids") or []):
                    st.warning(
                        "본인에게 **할당된 공간이 없습니다**. "
                        "학교 담당자가 [설정] 페이지에서 담당 공간을 할당해야 합니다."
                    )
                else:
                    st.warning(
                        "할당된 공간이 아직 학교에 **등록되지 않았습니다**. "
                        "학교 담당자가 [점검 시작 · 새 공간 등록]에서 공간을 먼저 만든 뒤 "
                        "[설정]에서 본인에게 할당해야 합니다."
                    )
                if st.button("학교 담당자로 전환", key="space_role_to_school",
                              width="stretch"):
                    st.session_state["role"] = "학교"
                    st.session_state["space_manager"] = None
                    st.session_state["school_auth_verified"] = False
                    st.rerun()
            else:
                st.info("아직 등록된 공간이 없습니다. 오른쪽 탭에서 새 공간을 등록하세요.")
        else:
            for sp in spaces_here:
                c1, c2 = st.columns([5, 1])
                with c1:
                    nick = sp.get("nickname") or "별칭 없음"
                    st.markdown(
                        f"<div class='sl-card' style='margin-bottom:8px; padding:14px 16px;'>"
                        f"<b>{sp['type']}</b> · <span style='color:#6B6B70'>{nick}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with c2:
                    _confirm_key = f"_confirm_switch_{sp['space_id']}"
                    if st.button("선택", key=f"pick_space_{sp['space_id']}"):
                        from modules.session import (
                            has_unsaved_inspection_work, reset_inspection,
                        )
                        prev = st.session_state.get("active_space") or {}
                        # 다른 공간으로 전환할 때만 검사
                        if prev.get("space_id") and prev.get("space_id") != sp["space_id"]:
                            if has_unsaved_inspection_work() \
                                    and not st.session_state.get(_confirm_key):
                                # 첫 클릭 — 경고 표시 후 다음 클릭에서 진행
                                st.session_state[_confirm_key] = True
                                st.rerun()
                            reset_inspection()
                        st.session_state.pop(_confirm_key, None)
                        st.session_state["active_space"] = sp
                        st.rerun()
                    if st.session_state.get(_confirm_key):
                        st.warning(
                            "현재 점검 중인 작업이 **저장되지 않았습니다**. "
                            "다른 공간으로 전환하면 사진·점수·결과가 사라집니다.\n\n"
                            "**'선택'** 을 한 번 더 누르면 그래도 진행하고, "
                            "취소하려면 결과 저장 페이지에서 먼저 저장하세요."
                        )
                        if st.button("취소 (현재 작업 유지)",
                                      key=f"cancel_switch_{sp['space_id']}",
                                      width="stretch"):
                            st.session_state.pop(_confirm_key, None)
                            st.rerun()

    # 실 담당자(_role="실")에겐 새 공간 등록 권한이 없음 tab_new=None.
    # 학교 담당자만 아래 블록이 실행됨.
    if tab_new is not None:
      with tab_new:
        SPACE_TYPES = [
            "화학실", "물리실", "생명과학실", "지구과학실",
            "기술실", "가정실", "음악실", "미술실",
            "강당", "체육관", "급식실", "일반교실", "특별교실(과목 불명)",
        ]
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            sp_type = st.selectbox("공간 유형", SPACE_TYPES)
        with c2:
            sp_nickname = st.text_input("별칭 (선택)", placeholder="예: 3층 화학실 A", max_chars=40)
        with c3:
            sp_floor = st.number_input(
                "층수", min_value=1, max_value=20, value=1, step=1,
                help="3층 이상이면 완강기·창문 추락방지 항목이 자동 적용됩니다.",
            )
        _confirm_new_key = "_confirm_new_space"
        if st.button("등록·선택", type="primary"):
            from modules.session import (
                has_unsaved_inspection_work, reset_inspection,
            )
            prev = st.session_state.get("active_space") or {}
            if prev.get("space_id") and has_unsaved_inspection_work() \
                    and not st.session_state.get(_confirm_new_key):
                st.session_state[_confirm_new_key] = True
                st.rerun()
            if prev.get("space_id"):
                reset_inspection()
            st.session_state.pop(_confirm_new_key, None)
            new_sp = {
                "space_id": uuid.uuid4().hex[:10],
                "school_code": school_code,
                "type": sp_type,
                "nickname": sp_nickname.strip() or None,
                "floor": int(sp_floor),
            }
            st.session_state.setdefault("registered_spaces", []).append(new_sp)
            st.session_state["active_space"] = new_sp
            # 시연 모드 — 새 공간이 생기면 데모 실 담당자에게도 자동 할당
            # (ensure_demo_manager 는 멱등 + 공간 합집합 처리 안전하게 매번 호출 가능)
            if st.session_state.get("demo_mode"):
                try:
                    from modules.managers import ensure_demo_manager
                    ensure_demo_manager(
                        school_code,
                        name="시연 담당교사",
                        assigned_space_ids=[new_sp["space_id"]],
                    )
                except Exception:
                    pass
            st.rerun()
        if st.session_state.get(_confirm_new_key):
            st.warning(
                "현재 점검 중인 작업이 **저장되지 않았습니다**. "
                "새 공간을 등록·선택하면 사진·점수·결과가 사라집니다.\n\n"
                "**'등록·선택'** 을 한 번 더 누르면 그래도 진행하고, "
                "취소하려면 결과 저장 페이지에서 먼저 저장하세요."
            )
            if st.button("취소 (현재 작업 유지)",
                          key="cancel_new_space",
                          width="stretch"):
                st.session_state.pop(_confirm_new_key, None)
                st.rerun()

    if st.session_state.get("active_space"):
        divider()
        nick = st.session_state["active_space"].get("nickname") or "별칭 없음"
        st.markdown(
            f"<div class='sl-card sl-card-accent'>"
            f"<div class='sl-num'>현재 선택</div>"
            f"<div style='font-size:18px; font-weight:700;'>"
            f"{st.session_state['active_space']['type']} "
            f"<span style='font-weight:500; color:#6B6B70'>· {nick}</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("AI 점검으로 이동", type="primary", width="stretch"):
            st.switch_page("pages/2_AI점검.py")
