"""
시연 모드 합성 응답 — 9개 공간 모두에 대해 풍부한 Stage 2/3 캐시를 자동 생성.

배경:
- 시연 시작 시 `make_all_demo_shots()` 가 PIL 더미 이미지 7컷을 만들고,
  사용자는 그걸로 AI 분석을 진행한다.
- 그러나 더미 이미지의 SHA 해시는 sample_images/ 의 실 사진 해시와 다르므로
  기존 Stage 2/3 캐시가 적중하지 않는다.
- 이 모듈은 LAW_BASIS 의 `applicable_spaces` 메타를 활용해 공간별 표준 설비
  목록을 자동으로 detected_equipment 응답으로 합성하여, 시연 시 풍부한
  AI 결과가 즉시 보이도록 한다.

호출 시점:
- `app.py` 의 시연 시작 핸들러에서 `make_all_demo_shots()` 직후
- `modules.ai_vision.ensure_demo_cache_for_shots()` 가 본 모듈을 사용

원칙:
- 합성 응답에 `_synth_demo: True` 마커를 두어 실 AI 응답과 구분 가능
- 화학실은 기존 풍부한 캐시(`stage2_anthropic_1d7f982033668292_화학실.json`)
  를 우선 재사용 (자연스러운 노트·도면 참조 등 풍부한 콘텐츠)
- 기존 캐시 없는 공간만 자동 합성
"""
from __future__ import annotations

from typing import Any

from .laws import LAW_BASIS


# 합성 응답 버전 — 로직 변경 시 +1 하여 디스크 캐시 자동 무효화 트리거.
# v2 (2026-05): synth_stage3 의 카테고리당 1개·8개 제한 제거 → 모든 detected 매핑
SYNTH_VERSION = "v2"


# 공간별 설비 상태 분포 — Stage 2 프롬프트 스키마(존재확인/상태양호/상태불량) 준수.
# absent/ambig 분류는 synth_stage2_for_space 가 결정적으로 보장 (아래 forced_* 참고).
# 가중치(weight) 기준: 높은 설비는 거의 양호, 낮은 설비는 일부 불량.
def _status_for_weight(weight: int, idx: int) -> str:
    """가중치·순서에 따라 결정적 상태 반환."""
    bucket = idx % 20  # 0..19
    if weight >= 9:
        return "상태양호" if bucket < 4 else "존재확인"
    if weight >= 7:
        if bucket < 3:
            return "상태불량"
        if bucket < 8:
            return "상태양호"
        return "존재확인"
    # weight ≤ 6
    if bucket < 4:
        return "상태불량"
    if bucket < 10:
        return "상태양호"
    return "존재확인"


# 설비별 시연용 노트 (관찰 결과 텍스트) — 자연스러움 위해
_NOTE_TEMPLATES = {
    "흄후드": "실험대 후면에 대형 흄후드 1대 확인, 배기덕트 천장 연결",
    "국소배기장치": "실험대 상부에 국소배기 후드 다수 설치",
    "기계환기구": "벽면 상단에 기계환기 흡입구 확인, 가동 상태 양호",
    "천장디퓨저": "천장 전체에 사각형 공조 디퓨저 다수 배치",
    "환기상태(CO2)": "수업 중 자연환기 가능, CO2 농도 측정기 별도 미확인",
    "비상샤워": "출입구 인접 위치에 비상샤워 1대 설치 확인",
    "세안기": "싱크대 옆에 세안기 부착, 노즐 청결",
    "소화기": "벽면 하단에 ABC 분말소화기 비치, 위치 표지 명확",
    "소화포": "비상 대응 캐비닛 내 소화포 1매 비치",
    "응급처치함": "녹색 십자 표시 응급처치함 1대 벽면 부착",
    "AED표지": "복도 인접 AED 위치 안내 표지 부착",
    "완강기": "창가 측 벽면에 완강기 1대 설치 (3층 이상 의무)",
    "가스차단밸브": "출입문 옆 가스 메인 차단 밸브 노출 설치",
    "가스용기보관함": "외부 환기 가능 위치에 가스용기 보관함 1기",
    "시약장(잠금)": "시약장 잠금 장치 확인, 라벨 부착",
    "폐액용기": "지정 라벨 부착된 폐액 수거 용기 비치",
    "개인보호구함": "PPE 보관함 1개 비치, 보안경·장갑 수량 충분",
    "화재감지기": "천장에 원형 화재감지기 다수 배치",
    "연기감지기": "천장에 연기감지기 균일 배치",
    "가스누출감지기": "가스 사용 구역 천장에 누출감지기 설치",
    "비상벨": "출입문 옆 비상호출 버튼 확인",
    "보안경": "PPE 보관함 내 보안경 다수 비치",
    "실험복": "PPE 보관함 내 실험복 행거 비치",
    "장갑": "PPE 보관함 내 라텍스·니트릴 장갑 비치",
    "방독면": "비상 PPE 캐비닛 내 방독면 1점 보관",
    "실험화": "PPE 보관함 내 실험화 비치",
    "MSDS비치": "출입구 옆 MSDS 바인더 1권 비치, 갱신일 확인 필요",
    "안전수칙게시": "벽면 안전수칙 포스터 부착, 가독성 양호",
    "비상대응 포스터": "비상 대응 절차 포스터 출입구 옆 부착",
    "가스차단 표지": "가스 밸브 옆 차단 안내 표지 부착",
    "비상구 표시등": "출입문 상단에 녹색 비상구 표시등 점등 확인",
}


def synth_stage2_for_space(space_type: str) -> dict[str, Any]:
    """LAW_BASIS 기준으로 detected/absent/ambiguous 3분류 자동 합성.

    Returns dict with keys:
      detected_equipment, likely_absent_equipment, ambiguous_items,
      summary, _synth_demo
    """
    # 해당 공간에 적용되는 표준 설비 추출 (가중치 내림차순)
    items: list[tuple[str, dict]] = []
    for name, meta in LAW_BASIS.items():
        if space_type in meta.get("applicable_spaces", []):
            items.append((name, meta))
    items.sort(key=lambda x: -x[1].get("weight", 0))

    detected: list[dict[str, Any]] = []
    absent: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    # 시연 풍부함을 위해 absent 1건 + ambig 2건을 결정적으로 보장.
    # 가장 가중치 낮은 항목들에서 선택 — 실제 학교도 보조 설비가 누락되기 쉬움.
    # 항목 수가 작으면 보장 건수도 줄여 detected 가 0 되지 않도록 함.
    n = len(items)
    forced_absent_idx: set[int] = {n - 1} if n >= 5 else set()
    forced_ambig_idx: set[int] = (
        {n - 2, n - 3} if n >= 6
        else ({n - 2} if n >= 4 else set())
    )

    for idx, (name, meta) in enumerate(items):
        ref_no = (idx % 7) + 1  # 7컷 분배
        category = meta.get("category", "기타")

        if idx in forced_absent_idx:
            # "AI 가 탐지 못 함 → 사용자 정정 기회" 시연 시나리오의 핵심.
            absent.append({
                "category": category,
                "name": name,
                "image_ref": f"{ref_no:02d}-1",
                "reason": (
                    "사진 7컷 전수 검토 결과 미확인 — 설치 여부 추가 확인 필요"
                ),
            })
            continue
        if idx in forced_ambig_idx:
            # "탐지했으나 사진상 확신 어려움 → 사용자가 존재/부재 결정" 시나리오.
            ambiguous.append({
                "category": category,
                "name": name,
                "image_ref": f"{ref_no:02d}-1",
                "reason": (
                    f"{name} 추정 형태가 일부 보이나 각도·조명으로 확정 어려움"
                ),
            })
            continue

        status = _status_for_weight(meta.get("weight", 5), idx)
        detected.append({
            "category": category,
            "name": name,
            "status": status,
            "image_ref": f"{ref_no:02d}-1",
            "note": _NOTE_TEMPLATES.get(name, f"{name} 관찰"),
        })

    # 요약은 평이한 관찰 문장 — 시연/시뮬레이션 표식은 `_synth_demo` 플래그로만.
    # (이전 코드는 summary 에 "시뮬레이션" 문구를 박아 PDF·발송본까지 흘러갔음.)
    summary = (
        f"{space_type} 사진 7컷 검토 — 표준 설비 {len(detected)}개 확인, "
        f"{len(absent)}개 미확인, {len(ambiguous)}개 판정 모호."
    )
    return {
        "detected_equipment": detected,
        "likely_absent_equipment": absent,
        "ambiguous_items": ambiguous,
        "summary": summary,
        "_synth_demo": True,
    }


def synth_stage3_for_space(space_type: str, stage2: dict[str, Any]) -> dict[str, Any]:
    """공간별 점검표 자동 생성 — Stage 2 detected_equipment 를 기반으로 항목 합성.

    탐지된 모든 설비를 점검 항목으로 매핑 (설비명 중복만 제거).
    실 API 호출 시 27 표준 항목 + 추가 항목까지 생성되는 풍부도를 시연에서도 재현.
    """
    # 설비명 중복만 제거 (같은 흄후드 여러 대 등) — 카테고리 제한·개수 제한 없음
    seen_name: set[str] = set()
    items: list[dict[str, Any]] = []
    no = 0
    for det in stage2.get("detected_equipment", []):
        name = det.get("name", "").strip()
        if not name or name in seen_name:
            continue
        seen_name.add(name)
        no += 1
        cat = det.get("category", "기타")
        meta = LAW_BASIS.get(name, {})
        items.append({
            "no": no,
            "category": cat,
            "title": f"{name} 상태 및 정상 동작 확인",
            "method": f"{name} 의 위치·표지·작동 상태 육안 점검",
            "criterion": "설치 기준 부합 + 손상·결함 없음 + 가시 위치에 부착",
            "basis": f"{meta.get('law', '학교안전법')} {meta.get('article', '')}".strip(),
            "item_type": "상태점검",
            "priority": "상" if meta.get("weight", 5) >= 8 else ("중" if meta.get("weight", 5) >= 6 else "하"),
            "location": f"{space_type} 내 {name} 설치 위치",
        })

    return {
        "space_type": space_type,
        "checklist_name": f"{space_type} 맞춤형 안전 점검표 (시연용 합성)",
        "items": items,
        "_synth_demo": True,
        "_synth_version": SYNTH_VERSION,
    }
