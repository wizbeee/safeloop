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
        print(f"  [OK]   {name}: {msg}")
    except Exception as e:
        fail += 1
        results.append((name, False, str(e)))
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")


print("=" * 60)
print("  SafeLoop Smoke Test")
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
from modules.ai_providers import ALL_PROVIDERS, providers_status
status = providers_status()
check("providers_status", lambda: f"{len(status)}개 공급자 발견")
for p in status:
    label = "키 있음" if p["available"] else "키 없음(정상)"
    check(f"  {p['id']}", lambda l=label: l)

# 6. 점수·추천
print("\n[6/8] 점수·추천 핵심 함수")
from modules.score import calculate_safety_score, get_grade
from modules.recommend import recommend_from_scores
test_scores = {"비상샤워": 1.0, "세안기": 0.5, "MSDS비치": 0.0}
result = calculate_safety_score(test_scores)
check("calculate_safety_score", lambda: f"점수 {result['score']}, 등급 {result['grade']}")
check("get_grade", lambda: f"95→{get_grade(95)}, 75→{get_grade(75)}, 50→{get_grade(50)}")
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

# 결과
print("\n" + "=" * 60)
print(f"  결과: {ok}건 통과 / {fail}건 실패 (총 {ok + fail}건)")
print("=" * 60)
sys.exit(0 if fail == 0 else 1)
