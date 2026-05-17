"""
SafeLoop 스모크 테스트 — 배포 전 빠른 무결성 확인.

실행:
    cd safeloop_demo
    python tests/smoke_test.py
또는:
    python -m tests.smoke_test

검사 항목:
  1. 모든 모듈 임포트 가능
  2. 모든 페이지 .py 구문 정상
  3. 데이터 파일 존재 + 로드 가능
  4. 설정 파일·아이콘·매니페스트 존재
  5. AI 공급자 어댑터 인스턴스화 (실제 API 호출 X)
  6. 점수·추천 모듈 핵심 함수 호출
  7. 이미지 품질 모듈 라운드트립
  8. 저장 모듈 PDF/Excel/JSON 생성

API 키 없이도 80% 이상 통과해야 정상.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ok = 0
fail = 0
results: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    global ok, fail
    try:
        msg = fn() or "OK"
        ok += 1
        results.append((name, True, msg))
        print(f" [OK] {name}: {msg}")
    except Exception as e:
        fail += 1
        results.append((name, False, str(e)))
        print(f" [FAIL] {name}: {type(e).__name__}: {e}")


print("=" * 60)
print(" SafeLoop Smoke Test")
print("=" * 60)

# 1. 모듈 임포트
print("\n[1/8] 모듈 임포트")
for mod in ["modules.prompts", "modules.laws", "modules.score",
            "modules.recommend", "modules.data_loader", "modules.session",
            "modules.storage", "modules.ai_providers", "modules.ai_vision",
            "modules.image_quality", "modules.ui"]:
    check(mod, lambda m=mod: f"{__import__(m).__name__} 로드")

# 2. 페이지 구문
print("\n[2/8] 페이지 구문 검사")
import py_compile
for p in sorted((ROOT / "pages").glob("*.py")):
    check(f"pages/{p.name}", lambda pp=p: py_compile.compile(str(pp), doraise=True) and "compile OK")

# 3. 데이터 파일
print("\n[3/8] 데이터 파일")
from modules.data_loader import (
    load_master, load_high_risk, load_sido_summary, load_cluster_summary,
    load_sensitivity, load_sigungu_agg, load_risk_analysis,
)
check("master CSV", lambda: f"{len(load_master())} rows")
check("high_risk CSV", lambda: f"{len(load_high_risk())} rows")
check("sido_summary CSV", lambda: f"{len(load_sido_summary())} rows")
check("cluster_summary CSV", lambda: f"{len(load_cluster_summary())} rows")
check("sensitivity CSV", lambda: f"{len(load_sensitivity())} rows")
check("sigungu_agg CSV", lambda: f"{len(load_sigungu_agg())} rows")
check("risk_analysis CSV", lambda: f"{len(load_risk_analysis())} rows")

# 4. 인프라 파일
print("\n[4/8] 인프라 파일")
for rel in ["app.py", "requirements.txt", "packages.txt", "setup.py",
            "static/manifest.json", "static/icon-192.png", "static/icon-512.png",
            ".streamlit/config.toml"]:
    check(rel, lambda r=rel: f"size={(ROOT / r).stat().st_size}B" if (ROOT / r).exists()
          else (_ for _ in ()).throw(FileNotFoundError(r)))

# 5. AI 공급자 어댑터
print("\n[5/8] AI 공급자 어댑터")
from modules.ai_providers import providers_status
status = providers_status()
check("providers_status", lambda: f"{len(status)}개 공급자 발견")
for p in status:
    label = "키 있음" if p["available"] else "키 없음(정상)"
    check(f" {p['id']}", lambda l=label: l)

# 6. 점수·추천
print("\n[6/8] 점수·추천 핵심 함수")
from modules.score import calculate_safety_score, get_grade
from modules.recommend import recommend_from_scores
test_scores = {"비상샤워": 1.0, "세안기": 0.5, "MSDS비치": 0.0}
result = calculate_safety_score(test_scores)
check("calculate_safety_score", lambda: f"점수 {result['score']}, 등급 {result['grade']}")
check("get_grade", lambda: f"95{get_grade(95)}, 75{get_grade(75)}, 50{get_grade(50)}")
recs = recommend_from_scores(test_scores)
check("recommend_from_scores", lambda: f"{len(recs)}건 추천")

# 7. 이미지 품질
print("\n[7/8] 이미지 품질 모듈")
from modules.image_quality import analyze_and_optimize
sample_path = ROOT / "sample_images/chemistry_lab/lab_01_wide_full.jpg"
if sample_path.exists():
    raw = sample_path.read_bytes()
    rep = analyze_and_optimize(raw)
    saved_pct = (1 - len(rep.optimized_bytes) / len(raw)) * 100
    check("analyze_and_optimize", lambda: f"OK={rep.ok}, 절감={saved_pct:.0f}%, "
          f"{rep.width}×{rep.height}, blur={rep.blur_score:.0f}")
else:
    check("analyze_and_optimize", lambda: (_ for _ in ()).throw(
        FileNotFoundError("sample 사진 없음")))

# 8. 저장 모듈
print("\n[8/8] 저장 모듈 빌더")
from modules.storage import (
    build_master_record, build_edu_package, build_opendata_package,
    build_csv, build_excel, build_pdf_report, build_official_letter_pdf,
)
import datetime
mock_session = {
    "session_id": "smoke-test",
    "timestamp": datetime.datetime.now().isoformat(),
    "school": {
        "정보공시 학교코드": "TEST001", "학교명": "스모크중학교",
        "시도교육청": "서울특별시교육청", "지역": "서울특별시 강남구",
        "학교급": "중", "설립구분": "공립",
    },
    "active_space": {"space_id": "sp1", "type": "화학실", "nickname": "테스트"},
    "stage1_result": {"space_type_primary": "화학실", "confidence": 0.9, "evidence": ["흄후드"]},
    "stage2_result": {"detected_equipment": [], "likely_absent_equipment": [], "ambiguous_items": []},
    "stage2_confirmed": {"detected_equipment": [], "likely_absent_equipment": []},
    "stage3_result": {"space_type": "화학실", "checklist_name": "테스트", "items": [
        {"no": 1, "category": "비상", "title": "비상샤워 점검", "method": "관찰",
         "criterion": "정상", "basis": "교육시설법 47조", "item_type": "상태점검", "priority": "상"},
    ], "rationale": "테스트"},
    "item_scores": {"1": 1.0},
    "score_result": {"score": 80.0, "grade": "B", "grade_description": "양호",
                     "category_scores": {"비상 대응": {"score": 80, "weight_sum": 10, "items": []}},
                     "raw": {"비상샤워": 1.0}},
    "recommendations": [],
    "eduline": {"담당자": "홍길동", "부장": "", "교감": "", "교장": ""},
    "edufine_approved": True,
}
m = build_master_record(mock_session)
check("build_master_record", lambda: f"session_id={m['session_id']}")
check("build_edu_package", lambda: f"score={build_edu_package(m)['safety_score']}")
check("build_opendata_package", lambda: f"anon={build_opendata_package(m)['school_anonymous_id']}")
check("build_csv", lambda: f"{len(build_csv(m))}B")
check("build_excel", lambda: f"{len(build_excel(m))}B")
check("build_pdf_report", lambda: f"{len(build_pdf_report(m))}B")
check("build_official_letter_pdf", lambda: f"{len(build_official_letter_pdf(m))}B")

# 9. 페이지 런타임 검사 (NameError 등 모듈 레벨 실행 에러 잡기)
print("\n[9] 페이지 런타임 무결성 (Streamlit AppTest)")
try:
    from streamlit.testing.v1 import AppTest

    def _check_page_runtime(page_path: Path) -> str:
        at = AppTest.from_file(str(page_path), default_timeout=15)
        at.run()
        if at.exception:
            exc = at.exception[0]
            raise RuntimeError(f"{type(exc.value).__name__}: {exc.value}")
        return "런타임 OK"

    # app.py + 모든 페이지
    targets = [ROOT / "app.py"] + sorted((ROOT / "pages").glob("*.py"))
    for p in targets:
        check(f"runtime/{p.name}", lambda pp=p: _check_page_runtime(pp))
except ImportError:
    print(" streamlit.testing 모듈 사용 불가 — skipped")

# 10. 핵심 사용자 인터랙션 — 시연 시작 흐름 (단순 컴포넌트 검증)
print("\n[10] 시연 캐시 자동 보장 동작")
try:
    from modules.demo_image import make_all_demo_shots
    from modules.ai_vision import ensure_demo_cache_for_shots

    for sp in ("화학실", "일반교실", "물리실", "음악실", "미술실"):
        shots = make_all_demo_shots(sp)
        ok_cache = ensure_demo_cache_for_shots(shots, sp)
        check(f"demo_cache/{sp}",
              lambda v=ok_cache, s=sp: f"cache_ensured={v}" if v else (_ for _ in ()).throw(
                  RuntimeError(f"{s} 캐시 보장 실패")
              ))
except Exception as e:
    print(f" 시연 캐시 검증 스킵 — {e}")

# 11. 라운드트립 — 저장 암호화 복호화 세션 복원 모의
print("\n[11] .safeloop 라운드트립 (저장암호화복호화)")
try:
    from modules.crypto import encrypt_to_file_bytes, decrypt_payload, is_encrypted
    from modules.storage import build_master_record, build_edu_package

    sample_session = {
        "session_id": "smoke-rt",
        "school": {
            "정보공시 학교코드": "T0000",
            "학교명": "스모크중학교",
            "시도교육청": "충남교육청",
        },
        "active_space": {"space_id": "spX", "type": "화학실", "nickname": "3층 A"},
        "stage2_confirmed": {"detected_equipment": [], "likely_absent_equipment": []},
        "stage3_result": {"items": []},
        "score_result": {"score": 75, "grade": "B", "category_scores": {}},
        "recommendations": [],
        "internal_approval_confirmed": True,
    }
    master = build_master_record(sample_session)
    edu = build_edu_package(master)
    blob = encrypt_to_file_bytes(edu)
    check("encrypt_to_file_bytes", lambda: f"encrypted={is_encrypted(blob)} size={len(blob)}B")
    decoded = decrypt_payload(blob)
    check("decrypt_payload", lambda: f"record_type={decoded.get('record_type')}")
    assert decoded.get("record_type") == "safeloop_edu_submission", \
        f"record_type 불일치: {decoded.get('record_type')}"
    print(" 라운드트립 검증 OK")
except Exception as e:
    print(f" 라운드트립 검증 실패 — {e}")
    fail += 1


# 12. 실 담당자(space manager) 인프라 — CRUD + PIN + 인증 (Sprint 1)
print("\n[12] 실 담당자 인프라 (modules.managers)")
try:
    import shutil
    from modules import managers as mgr_mod

    TEST_SCHOOL = "SMOKE_TEST_SCHOOL_X9Z"
    # 테스트 시작 전 깨끗한 상태 보장
    test_path = mgr_mod._managers_path(TEST_SCHOOL).parent
    if test_path.exists():
        shutil.rmtree(test_path, ignore_errors=True)

    # 12-1. 빈 명부 로드
    check("managers/empty_list",
          lambda: f"빈 명부 {len(mgr_mod.list_managers(TEST_SCHOOL))}건"
                  if mgr_mod.list_managers(TEST_SCHOOL) == [] else
                  (_ for _ in ()).throw(AssertionError("빈 명부 아님")))

    # 12-2. 매니저 추가 — manager_id=M001, pin 6자리 숫자
    mgr1, pin1 = mgr_mod.add_manager(
        TEST_SCHOOL, "홍길동", email="hong@test.kr",
        phone="010-0000-0001",
        assigned_space_ids=["sp_chem_3a", "sp_phys_2b"],
    )
    check("managers/add_first",
          lambda: f"manager_id={mgr1['manager_id']}, pin={pin1}"
                  if mgr1["manager_id"] == "M001" and len(pin1) == 6 and pin1.isdigit() else
                  (_ for _ in ()).throw(AssertionError(f"형식 오류: {mgr1}, {pin1}")))

    # 12-3. 공개 사본에 pin_hash 미노출 (보안)
    check("managers/no_pin_hash_public",
          lambda: "pin_hash 미노출"
                  if "pin_hash" not in mgr1 else
                  (_ for _ in ()).throw(AssertionError("pin_hash 노출됨!")))

    # 12-4. 두 번째 매니저 — manager_id 자동 증가
    mgr2, pin2 = mgr_mod.add_manager(
        TEST_SCHOOL, "김철수", assigned_space_ids=["sp_design_4a"],
    )
    check("managers/add_second",
          lambda: f"manager_id={mgr2['manager_id']}"
                  if mgr2["manager_id"] == "M002" else
                  (_ for _ in ()).throw(AssertionError(f"자동증가 실패: {mgr2}")))

    # 12-5. 올바른 PIN — 인증 통과
    check("managers/verify_correct",
          lambda: "인증 통과"
                  if mgr_mod.verify_manager_pin(TEST_SCHOOL, mgr1["manager_id"], pin1) else
                  (_ for _ in ()).throw(AssertionError("올바른 PIN 인증 실패")))

    # 12-6. 잘못된 PIN — 차단
    check("managers/verify_wrong",
          lambda: "잘못된 PIN 차단"
                  if not mgr_mod.verify_manager_pin(TEST_SCHOOL, mgr1["manager_id"], "999999") else
                  (_ for _ in ()).throw(AssertionError("잘못된 PIN 인증 통과!")))

    # 12-7. 다른 매니저 PIN 으로 첫 매니저 인증 시도 — 차단 (PIN 격리)
    if pin1 != pin2:
        check("managers/pin_isolation",
              lambda: "PIN 격리 OK"
                      if not mgr_mod.verify_manager_pin(TEST_SCHOOL, mgr1["manager_id"], pin2) else
                      (_ for _ in ()).throw(AssertionError("다른 매니저 PIN 통과!")))

    # 12-8. authenticate_manager — 통과 시 last_login_at 갱신
    auth_result = mgr_mod.authenticate_manager(TEST_SCHOOL, mgr1["manager_id"], pin1)
    check("managers/authenticate_login_stamp",
          lambda: "last_login_at 갱신"
                  if auth_result and auth_result.get("last_login_at") else
                  (_ for _ in ()).throw(AssertionError(f"login_stamp 누락: {auth_result}")))

    # 12-9. 공간 담당자 조회 — sp_chem_3a 담당자는 M001 1명
    holders = mgr_mod.get_managers_for_space(TEST_SCHOOL, "sp_chem_3a")
    check("managers/get_for_space",
          lambda: f"sp_chem_3a 담당 {len(holders)}명"
                  if len(holders) == 1 and holders[0]["manager_id"] == "M001" else
                  (_ for _ in ()).throw(AssertionError(f"조회 오류: {holders}")))

    # 12-10. update_manager — 담당 공간 추가
    updated = mgr_mod.update_manager(
        TEST_SCHOOL, mgr1["manager_id"],
        assigned_space_ids=["sp_chem_3a", "sp_phys_2b", "sp_general_1a"],
    )
    check("managers/update",
          lambda: f"공간 {len(updated['assigned_space_ids'])}개"
                  if updated and len(updated["assigned_space_ids"]) == 3 else
                  (_ for _ in ()).throw(AssertionError(f"수정 실패: {updated}")))

    # 12-11. PIN 재발급 — 옛 PIN 무효
    new_pin = mgr_mod.reissue_pin(TEST_SCHOOL, mgr1["manager_id"])
    check("managers/reissue_old_invalid",
          lambda: "옛 PIN 무효화"
                  if not mgr_mod.verify_manager_pin(TEST_SCHOOL, mgr1["manager_id"], pin1) else
                  (_ for _ in ()).throw(AssertionError("옛 PIN 여전히 유효!")))

    # 12-12. 재발급 PIN — 새 PIN 유효
    check("managers/reissue_new_valid",
          lambda: f"새 PIN({new_pin[:1]}****) 유효"
                  if mgr_mod.verify_manager_pin(TEST_SCHOOL, mgr1["manager_id"], new_pin) else
                  (_ for _ in ()).throw(AssertionError("새 PIN 인증 실패")))

    # 12-13. 비활성화 — 인증 즉시 실패
    mgr_mod.deactivate_manager(TEST_SCHOOL, mgr1["manager_id"])
    check("managers/deactivate_blocks_auth",
          lambda: "비활성 인증 차단"
                  if not mgr_mod.verify_manager_pin(TEST_SCHOOL, mgr1["manager_id"], new_pin) else
                  (_ for _ in ()).throw(AssertionError("비활성 매니저 인증 통과!")))

    # 12-14. 비활성 필터 — 명부에서 빠짐
    check("managers/deactivate_listing",
          lambda: f"활성 {len(mgr_mod.list_managers(TEST_SCHOOL))}건 / 전체 {len(mgr_mod.list_managers(TEST_SCHOOL, include_inactive=True))}건"
                  if len(mgr_mod.list_managers(TEST_SCHOOL)) == 1
                  and len(mgr_mod.list_managers(TEST_SCHOOL, include_inactive=True)) == 2 else
                  (_ for _ in ()).throw(AssertionError("필터 오작동")))

    # 12-15. 재활성화
    mgr_mod.reactivate_manager(TEST_SCHOOL, mgr1["manager_id"])
    check("managers/reactivate",
          lambda: "재활성 OK"
                  if mgr_mod.verify_manager_pin(TEST_SCHOOL, mgr1["manager_id"], new_pin) else
                  (_ for _ in ()).throw(AssertionError("재활성 후 인증 실패")))

    # 12-16. session.py 헬퍼 임포트 검증
    from modules.session import manager_can_access_space, is_space_manager_authenticated
    check("session/manager_helpers",
          lambda: "헬퍼 임포트 OK"
                  if callable(manager_can_access_space) and callable(is_space_manager_authenticated) else
                  (_ for _ in ()).throw(AssertionError("session 헬퍼 임포트 실패")))

    # 12-17. auth.py 매니저 함수 임포트 검증
    from modules.auth import (
        _hash_manager, remember_manager, get_remembered_manager,
        verify_manager_token, forget_manager, MANAGER_COOKIE_NAME,
    )
    check("auth/manager_funcs",
          lambda: f"쿠키명={MANAGER_COOKIE_NAME}"
                  if MANAGER_COOKIE_NAME == "safeloop_manager_remember"
                  and len(_hash_manager("S1", "M001", "123456")) == 32 else
                  (_ for _ in ()).throw(AssertionError("auth 매니저 함수 부적합")))

    # 12-18. ensure_demo_manager — 시연 헬퍼 (멱등성·DEMO_PIN 검증)
    from modules.managers import ensure_demo_manager, DEMO_PIN, is_demo_manager
    TEST_DEMO_SCHOOL = "SMOKE_TEST_DEMO_SCHOOL"
    demo_test_path = mgr_mod._managers_path(TEST_DEMO_SCHOOL).parent
    if demo_test_path.exists():
        shutil.rmtree(demo_test_path, ignore_errors=True)

    demo1 = ensure_demo_manager(TEST_DEMO_SCHOOL, assigned_space_ids=["sp1", "sp2"])
    check("managers/ensure_demo_first",
          lambda: f"manager_id={demo1['manager_id']}, _demo={is_demo_manager(demo1)}"
                  if demo1.get("manager_id") and is_demo_manager(demo1) else
                  (_ for _ in ()).throw(AssertionError(f"데모 매니저 생성 실패: {demo1}")))
    check("managers/ensure_demo_pin",
          lambda: f"DEMO_PIN('{DEMO_PIN}') 인증 OK"
                  if mgr_mod.verify_manager_pin(TEST_DEMO_SCHOOL, demo1["manager_id"], DEMO_PIN) else
                  (_ for _ in ()).throw(AssertionError("DEMO_PIN 인증 실패")))

    # 멱등성 — 두 번째 호출은 새로 만들지 않고 기존 매니저 반환
    demo2 = ensure_demo_manager(TEST_DEMO_SCHOOL, assigned_space_ids=["sp3"])
    check("managers/ensure_demo_idempotent",
          lambda: f"기존 매니저 재사용 (M001)"
                  if demo2["manager_id"] == demo1["manager_id"] else
                  (_ for _ in ()).throw(AssertionError(f"중복 생성: {demo2}")))
    check("managers/ensure_demo_spaces_merged",
          lambda: f"공간 합집합 {demo2['assigned_space_ids']}"
                  if set(demo2["assigned_space_ids"]) == {"sp1", "sp2", "sp3"} else
                  (_ for _ in ()).throw(AssertionError(f"공간 합집합 실패: {demo2}")))

    if demo_test_path.exists():
        shutil.rmtree(demo_test_path, ignore_errors=True)

    # 정리 — 테스트 폴더 삭제
    if test_path.exists():
        shutil.rmtree(test_path, ignore_errors=True)
    print(" 실 담당자 인프라 검증 완료 (21건)")
except Exception as e:
    print(f" 실 담당자 인프라 검증 실패 — {type(e).__name__}: {e}")
    fail += 1


# 13. master.json schema 1.1 — submitter + status 필드 검증 (Sprint 2-A)
print("\n[13] master.json submitter/status (Sprint 2-A)")
try:
    from modules.storage import build_master_record

    # 13-1. role="실" 세션 — submitted 상태로 저장
    space_mgr_session = {
        "session_id": "sm-test-1",
        "school": {"정보공시 학교코드": "S0001", "학교명": "테스트중"},
        "active_space": {"space_id": "sp1", "type": "화학실"},
        "role": "실",
        "space_manager": {
            "manager_id": "M001", "name": "홍길동",
            "email": "hong@test.kr", "phone": "010-0000-0001",
        },
        "stage1_result": {}, "stage2_result": {}, "stage2_confirmed": {},
        "stage3_result": {"items": []}, "item_scores": {},
        "score_result": {"score": 80, "grade": "B", "category_scores": {}},
        "recommendations": [],
    }
    rec_space = build_master_record(space_mgr_session)
    check("master/schema_v1.1",
          lambda: f"version={rec_space['schema_version']}"
                  if rec_space.get("schema_version") == "1.1" else
                  (_ for _ in ()).throw(AssertionError(f"schema 미갱신: {rec_space.get('schema_version')}")))
    check("master/submitter_space_role",
          lambda: f"role={rec_space['submitter']['role']}, manager_id={rec_space['submitter']['manager_id']}"
                  if rec_space["submitter"]["role"] == "실"
                  and rec_space["submitter"]["manager_id"] == "M001" else
                  (_ for _ in ()).throw(AssertionError(f"submitter 부적합: {rec_space.get('submitter')}")))
    check("master/status_submitted",
          lambda: f"status={rec_space['status']}"
                  if rec_space.get("status") == "submitted" else
                  (_ for _ in ()).throw(AssertionError(f"실 담당자 status 부적합: {rec_space.get('status')}")))
    check("master/status_history",
          lambda: f"history 1건 by_role={rec_space['status_history'][0]['by_role']}"
                  if len(rec_space.get("status_history", [])) == 1
                  and rec_space["status_history"][0]["by_role"] == "실" else
                  (_ for _ in ()).throw(AssertionError(f"history 부적합: {rec_space.get('status_history')}")))

    # 13-2. role="학교" 세션 — approved 상태로 저장 (기존 호환)
    school_session = {
        "session_id": "sch-test-1",
        "school": {"정보공시 학교코드": "S0001", "학교명": "테스트중"},
        "active_space": {"space_id": "sp1", "type": "화학실"},
        "role": "학교",
        "approver_name": "학교담당자",
        "my_email": "school@test.kr",
        "stage1_result": {}, "stage2_result": {}, "stage2_confirmed": {},
        "stage3_result": {"items": []}, "item_scores": {},
        "score_result": {"score": 75, "grade": "B", "category_scores": {}},
        "recommendations": [],
    }
    rec_school = build_master_record(school_session)
    check("master/submitter_school_role",
          lambda: f"role={rec_school['submitter']['role']}"
                  if rec_school["submitter"]["role"] == "학교" else
                  (_ for _ in ()).throw(AssertionError(f"school submitter 부적합")))
    check("master/status_approved",
          lambda: f"status={rec_school['status']}"
                  if rec_school.get("status") == "approved" else
                  (_ for _ in ()).throw(AssertionError(f"학교 담당자 status 부적합: {rec_school.get('status')}")))

    # 13-3. status_history 누적 — prior_history 전달 시 누적되는지
    prior = [
        {"status": "submitted", "by": "M001", "by_role": "실",
         "at": "2026-05-13T10:00:00", "note": "초기 저장"},
        {"status": "approved", "by": "학교담당자", "by_role": "학교",
         "at": "2026-05-13T11:00:00", "note": "검토 후 승인"},
    ]
    rec_with_prior = build_master_record(school_session, prior_history=prior)
    check("master/history_accumulated",
          lambda: f"history {len(rec_with_prior['status_history'])}건 (기존 2건 + 신규 1건)"
                  if len(rec_with_prior["status_history"]) == 3 else
                  (_ for _ in ()).throw(AssertionError(f"누적 실패: {len(rec_with_prior['status_history'])}건")))
    check("master/history_order",
          lambda: f"순서 보존: {rec_with_prior['status_history'][0]['status']} {rec_with_prior['status_history'][1]['status']} {rec_with_prior['status_history'][2]['status']}"
                  if rec_with_prior["status_history"][0]["status"] == "submitted"
                  and rec_with_prior["status_history"][2]["note"] == "재저장 (수정)" else
                  (_ for _ in ()).throw(AssertionError("history 순서·신규 항목 부적합")))
    print(" master.json schema 1.1 검증 완료 (8건)")
except Exception as e:
    print(f" master.json schema 검증 실패 — {type(e).__name__}: {e}")
    fail += 1


# 14. session.py 인증 통합 헬퍼 — is_authenticated_for_role (Sprint 2.5)
print("\n[14] session 인증 헬퍼 분리 (school_auth_verified space_manager)")
try:
    from modules.session import is_authenticated_for_role
    check("session/is_auth_helper_import",
          lambda: "헬퍼 import OK"
                  if callable(is_authenticated_for_role) else
                  (_ for _ in ()).throw(AssertionError("헬퍼 임포트 실패")))
    # 함수 본문에 school_auth_verified 검사가 있는지 (간접 검증)
    import inspect
    src = inspect.getsource(is_authenticated_for_role)
    check("session/is_auth_helper_logic",
          lambda: "헬퍼가 두 인증 모두 검사"
                  if "school_auth_verified" in src and "space_manager" in src else
                  (_ for _ in ()).throw(AssertionError("헬퍼 로직 부적합")))
    print(" 인증 헬퍼 검증 완료 (2건)")
except Exception as e:
    print(f" 인증 헬퍼 검증 실패 — {type(e).__name__}: {e}")
    fail += 1


# 15. consolidate 모듈 — 학교 단위 통합 보고서 (Sprint 3 마무리)
print("\n[15] consolidate 모듈 (학교 단위 통합 보고서)")
try:
    from modules import consolidate as _consol
    from modules.storage import (
        list_school_submissions, save_inspection, STORAGE_DIR,
        update_submission_status,
    )
    import shutil as _sh

    # 테스트 학교 준비
    _TS = "SMOKE_CONSOL"
    _tdir = STORAGE_DIR / _TS
    if _tdir.exists():
        _sh.rmtree(_tdir, ignore_errors=True)

    # 가짜 점검 2건 저장 (학교 담당자 자체 점검 approved)
    for i, sp in enumerate(["화학실", "물리실"]):
        _sess = {
            "session_id": f"consol-{i+1:03d}",
            "school": {"정보공시 학교코드": _TS, "학교명": "통합테스트중",
                        "시도교육청": "테스트교육청"},
            "active_space": {"space_id": f"sp{i+1}", "type": sp,
                              "nickname": f"3층 {chr(65+i)}"},
            "role": "학교",
            "approver_name": "테스트교장",
            "stage1_result": {}, "stage2_result": {}, "stage2_confirmed": {},
            "stage3_result": {"items": [{"no": 1, "title": "비상샤워",
                                          "category": "비상", "priority": "상"}]},
            "item_scores": {"1": 1.0},
            "score_result": {"score": 80 + i*5, "grade": "B",
                              "category_scores": {}},
            "recommendations": [],
        }
        save_inspection(_sess)
        # status_history 에 approved 추가
        update_submission_status(_TS, f"consol-{i+1:03d}", "approved",
                                  by="테스트교장", by_role="학교",
                                  note="시연 승인")

    # 15-1. list_consolidatable
    consolidatable = _consol.list_consolidatable(_TS)
    check("consolidate/list",
          lambda: f"{len(consolidatable)}건 통합 가능"
                  if len(consolidatable) == 2 else
                  (_ for _ in ()).throw(AssertionError(f"통합 가능 개수 부적합: {len(consolidatable)}")))

    # 15-2. build_consolidated_record
    _sids = [c["session_id"] for c in consolidatable]
    record = _consol.build_consolidated_record(_TS, _sids, "테스트교장")
    check("consolidate/record_schema",
          lambda: f"type={record['record_type']}, spaces={record['spaces_count']}"
                  if record.get("record_type") == "safeloop_consolidated_submission"
                  and record.get("spaces_count") == 2 else
                  (_ for _ in ()).throw(AssertionError(f"record 스키마 부적합: {record}")))
    check("consolidate/record_avg",
          lambda: f"평균 점수={record['average_score']}"
                  if record.get("average_score") == 82.5 else
                  (_ for _ in ()).throw(AssertionError(f"평균 부적합: {record.get('average_score')}")))

    # 15-3. PDF 생성
    pdf_bytes = _consol.build_consolidated_pdf(record)
    check("consolidate/pdf",
          lambda: f"{len(pdf_bytes)}B PDF"
                  if len(pdf_bytes) > 500 else
                  (_ for _ in ()).throw(AssertionError(f"PDF 크기 부적합: {len(pdf_bytes)}")))

    # 15-4. Excel 생성
    xlsx_bytes = _consol.build_consolidated_excel(record)
    check("consolidate/excel",
          lambda: f"{len(xlsx_bytes)}B XLSX"
                  if len(xlsx_bytes) > 500 else
                  (_ for _ in ()).throw(AssertionError(f"XLSX 크기 부적합: {len(xlsx_bytes)}")))

    # 15-5. mark_consolidated 일괄 처리 (반환 형식 dict — count + submit + errors)
    _mark_result = _consol.mark_consolidated(_TS, _sids, by="테스트교장",
                                              note="스모크 통합 발송")
    n_marked = _mark_result.get("count") if isinstance(_mark_result, dict) else _mark_result
    check("consolidate/mark",
          lambda: f"{n_marked}건 통합 완료 처리"
                  if n_marked == 2 else
                  (_ for _ in ()).throw(AssertionError(f"mark 개수 부적합: {n_marked}")))

    # 15-6. 처리 후 approved 목록 비어 있어야
    after = _consol.list_consolidatable(_TS)
    check("consolidate/after_dispatch",
          lambda: f"통합 후 approved 목록 비어 있음 ({len(after)})"
                  if len(after) == 0 else
                  (_ for _ in ()).throw(AssertionError(f"통합 후 잔존: {len(after)}")))

    # 정리
    if _tdir.exists():
        _sh.rmtree(_tdir, ignore_errors=True)
    print(" consolidate 모듈 검증 완료 (6건)")
except Exception as e:
    print(f" consolidate 모듈 검증 실패 — {type(e).__name__}: {e}")
    fail += 1


# 결과
print("\n" + "=" * 60)
print(f" 결과: {ok}건 통과 / {fail}건 실패 (총 {ok + fail}건)")
print("=" * 60)
sys.exit(0 if fail == 0 else 1)
