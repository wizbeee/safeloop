"""
법령 근거 매핑 — 표준 항목 × 핵심 법령 + 공간 적용 메타.

핵심 법령:
- 학교보건법
- 교육시설법 (교육시설 등의 안전 및 유지관리 등에 관한 법률)
- 학교안전법 (학교안전사고 예방 및 보상에 관한 법률)
- 산업안전보건법 (산안법)
- 소방시설법
- 위험물안전관리법
- 전기설비기술기준 / 전기용품 안전관리법

각 항목의 근거는 validation/V1_점검표비교_v3.xlsx 매핑 결과를 참고하여 정리.
실제 법령 조항은 국가법령정보센터 기준으로 표기.

각 항목에 `applicable_spaces` 메타가 추가되어, AI 점검표 생성·점수 계산이
공간 유형에 맞는 항목만 사용하도록 한다.
"""
from __future__ import annotations


# ─────────────────────────────────────────
# 공간 유형 정의
# ─────────────────────────────────────────
ALL_SPACES = [
    "화학실", "물리실", "생명과학실", "지구과학실",
    "기술실", "가정실", "음악실", "미술실",
    "일반교실", "특별교실(과목 불명)",
]

# 실험·실습이 이뤄지는 특별교실 (개인보호구·환기 등 공통 적용)
LAB_SPACES = [
    "화학실", "물리실", "생명과학실", "지구과학실",
    "기술실", "가정실", "미술실",
]

# 화학물질을 다루는 공간 (시약장·MSDS·세안기 등)
CHEM_SPACES = ["화학실", "생명과학실", "미술실"]

# 가스를 사용하는 공간 (가스차단·누출감지)
GAS_SPACES = ["화학실", "가정실"]


# ─────────────────────────────────────────
# 표준 항목 × 법령 + 공간 적용
# ─────────────────────────────────────────
LAW_BASIS: dict[str, dict] = {
    # ───── 비상 대응 ─────
    "비상샤워": {
        "category": "비상 대응",
        "weight": 10,
        "law": "교육시설법 시행규칙",
        "article": "교육시설 안전·유지관리기준 제47조",
        "note": "실험실 비상샤워 설치 기준",
        "applicable_spaces": ["화학실", "생명과학실"],
    },
    "세안기": {
        "category": "비상 대응",
        "weight": 10,
        "law": "교육시설법 시행규칙",
        "article": "교육시설 안전·유지관리기준 제47조",
        "note": "실험실 세안기 설치 기준",
        "applicable_spaces": CHEM_SPACES,
    },
    "가스차단밸브": {
        "category": "비상 대응",
        "weight": 9,
        "law": "위험물안전관리법",
        "article": "제5조, 제17조",
        "note": "가스 공급 비상 차단 의무",
        "applicable_spaces": GAS_SPACES + ["기술실"],
    },
    "소화기": {
        "category": "비상 대응",
        "weight": 10,
        "law": "소방시설법",
        "article": "제11조 및 별표 4",
        "note": "특정소방대상물 소화설비 설치 기준",
        "applicable_spaces": ALL_SPACES,
    },
    "소화포": {
        "category": "비상 대응",
        "weight": 6,
        "law": "학교보건법",
        "article": "시행규칙 제3조",
        "note": "과학실 화재 대응 용품",
        "applicable_spaces": ["화학실", "생명과학실", "가정실"],
    },
    "응급처치함": {
        "category": "비상 대응",
        "weight": 7,
        "law": "학교보건법",
        "article": "제9조",
        "note": "학교 응급처치 준비물",
        "applicable_spaces": ALL_SPACES,
    },
    # NEW — 모든 공간 / 학교 1대 의무. 일반교실은 가까운 AED 위치 안내 표지 점검
    "AED표지": {
        "category": "비상 대응",
        "weight": 7,
        "law": "응급의료에 관한 법률",
        "article": "제47조의2",
        "note": "공공·다중이용시설 AED 위치 표지 의무",
        "applicable_spaces": ALL_SPACES,
    },
    # NEW — 3층 이상 의무 (피난기구)
    "완강기": {
        "category": "비상 대응",
        "weight": 9,
        "law": "소방시설법",
        "article": "별표 4 / 시행규칙 제2조의2",
        "note": "3층 이상 학교 시설 피난기구 의무 설치",
        "applicable_spaces": ALL_SPACES,
        "min_floor": 3,
    },

    # ───── 환기·배기 ─────
    "흄후드": {
        "category": "환기·배기",
        "weight": 9,
        "law": "산업안전보건법",
        "article": "제114조, 제118조",
        "note": "유해물질 국소배기 설비",
        "applicable_spaces": ["화학실", "생명과학실"],
    },
    "국소배기장치": {
        "category": "환기·배기",
        "weight": 8,
        "law": "산업안전보건법",
        "article": "제114조",
        "note": "유해가스·증기 배출",
        "applicable_spaces": ["화학실", "기술실", "미술실"],
    },
    "기계환기구": {
        "category": "환기·배기",
        "weight": 6,
        "law": "학교보건법",
        "article": "시행규칙 제3조 별표 4의2",
        "note": "교실 공기 질 기준",
        "applicable_spaces": ALL_SPACES,
    },
    "천장디퓨저": {
        "category": "환기·배기",
        "weight": 4,
        "law": "학교보건법",
        "article": "시행규칙 제3조",
        "note": "공조 설비 보조",
        "applicable_spaces": ALL_SPACES,
    },
    # NEW — 자연환기·CO2 농도 운영 점검 (시설 존재 여부와 별개)
    "환기상태(CO2)": {
        "category": "환기·배기",
        "weight": 6,
        "law": "학교보건법",
        "article": "시행규칙 제3조 별표 4의2 (CO2 1,000ppm 이하)",
        "note": "수업 중 환기·CO2 농도 관리",
        "applicable_spaces": ALL_SPACES,
    },

    # ───── 보관·격리 ─────
    "시약장(잠금)": {
        "category": "보관·격리",
        "weight": 9,
        "law": "산업안전보건법",
        "article": "제114조 및 시행규칙",
        "note": "유해화학물질 잠금 보관 의무",
        "applicable_spaces": CHEM_SPACES,
    },
    "가스용기보관함": {
        "category": "보관·격리",
        "weight": 8,
        "law": "위험물안전관리법",
        "article": "시행규칙 별표 4",
        "note": "고압가스 보관함 기준",
        "applicable_spaces": ["화학실"],
    },
    "폐액용기": {
        "category": "보관·격리",
        "weight": 7,
        "law": "산업안전보건법",
        "article": "제114조",
        "note": "폐수·폐액 별도 수거",
        "applicable_spaces": CHEM_SPACES,
    },
    "개인보호구함": {
        "category": "보관·격리",
        "weight": 5,
        "law": "산업안전보건법",
        "article": "제38조",
        "note": "PPE 지급·보관",
        "applicable_spaces": LAB_SPACES,
    },

    # ───── 감지·경보 ─────
    "화재감지기": {
        "category": "감지·경보",
        "weight": 10,
        "law": "소방시설법",
        "article": "제11조, 별표 4",
        "note": "자동화재탐지설비 기준",
        "applicable_spaces": ALL_SPACES,
    },
    "가스누출감지기": {
        "category": "감지·경보",
        "weight": 10,
        "law": "위험물안전관리법",
        "article": "시행규칙 별표 4",
        "note": "가스 누출 경보",
        "applicable_spaces": GAS_SPACES,
    },
    "비상벨": {
        "category": "감지·경보",
        "weight": 8,
        "law": "교육시설법",
        "article": "제10조 및 시행규칙",
        "note": "비상 호출 설비 (실험·실습실 권장)",
        "applicable_spaces": LAB_SPACES + ["일반교실"],
    },
    "연기감지기": {
        "category": "감지·경보",
        "weight": 9,
        "law": "소방시설법",
        "article": "별표 4",
        "note": "연기 감지 화재 경보",
        "applicable_spaces": ALL_SPACES,
    },

    # ───── 개인보호구 ─────
    "보안경": {
        "category": "개인보호구",
        "weight": 8,
        "law": "산업안전보건법",
        "article": "제38조",
        "note": "실험자 보안경 착용",
        "applicable_spaces": LAB_SPACES,
    },
    "실험복": {
        "category": "개인보호구",
        "weight": 7,
        "law": "산업안전보건법",
        "article": "제38조",
        "note": "유해물질 접촉 방지 의복",
        "applicable_spaces": LAB_SPACES,
    },
    "장갑": {
        "category": "개인보호구",
        "weight": 7,
        "law": "산업안전보건법",
        "article": "제38조",
        "note": "화학물질 접촉 방지",
        "applicable_spaces": ["화학실", "생명과학실", "가정실", "미술실"],
    },
    "방독면": {
        "category": "개인보호구",
        "weight": 6,
        "law": "산업안전보건법",
        "article": "제38조, 제114조",
        "note": "독성가스 호흡기 보호",
        "applicable_spaces": ["화학실"],
    },
    "실험화": {
        "category": "개인보호구",
        "weight": 5,
        "law": "산업안전보건법",
        "article": "제38조",
        "note": "낙하물·비산 방지 신발",
        "applicable_spaces": ["화학실", "기술실"],
    },

    # ───── 안내·표지 ─────
    "MSDS비치": {
        "category": "안내·표지",
        "weight": 8,
        "law": "산업안전보건법",
        "article": "제114조",
        "note": "물질안전보건자료 비치·교육",
        "applicable_spaces": CHEM_SPACES + ["기술실", "가정실"],
    },
    "안전수칙게시": {
        "category": "안내·표지",
        "weight": 5,
        "law": "학교안전법",
        "article": "제8조",
        "note": "안전교육 및 게시 의무",
        "applicable_spaces": ALL_SPACES,
    },
    "비상대응 포스터": {
        "category": "안내·표지",
        "weight": 4,
        "law": "학교안전법",
        "article": "제8조",
        "note": "비상 행동요령 게시",
        "applicable_spaces": ALL_SPACES,
    },
    "가스차단 표지": {
        "category": "안내·표지",
        "weight": 4,
        "law": "위험물안전관리법",
        "article": "시행규칙 별표",
        "note": "비상 밸브 위치 표시",
        "applicable_spaces": GAS_SPACES,
    },
    # NEW — 모든 공간 의무 (피난 유도)
    "비상구 표시등": {
        "category": "안내·표지",
        "weight": 8,
        "law": "소방시설법",
        "article": "별표 4 (유도등·유도표지)",
        "note": "피난구 유도등 의무 설치",
        "applicable_spaces": ALL_SPACES,
    },

    # ───── 시설·전기 (NEW 카테고리) ─────
    "콘센트 안전": {
        "category": "시설·전기",
        "weight": 7,
        "law": "전기설비기술기준",
        "article": "제13조 (접지) · KC 인증",
        "note": "3구·접지·KC 인증 콘센트",
        "applicable_spaces": ALL_SPACES,
    },
    "멀티탭 안전": {
        "category": "시설·전기",
        "weight": 6,
        "law": "전기용품 안전관리법",
        "article": "제3조",
        "note": "KC 인증·과부하 방지·문어발 사용 금지",
        "applicable_spaces": ALL_SPACES,
    },
    "조명 안전": {
        "category": "시설·전기",
        "weight": 4,
        "law": "학교보건법",
        "article": "시행규칙 제3조 (조도)",
        "note": "조도 기준·형광등 안정기·깜빡임",
        "applicable_spaces": ALL_SPACES,
    },
    "책걸상 안전": {
        "category": "시설·전기",
        "weight": 5,
        "law": "학교안전법",
        "article": "제8조",
        "note": "날카로운 모서리·흔들림·파손 점검",
        "applicable_spaces": ALL_SPACES,
    },
    "창문 추락방지": {
        "category": "시설·전기",
        "weight": 8,
        "law": "교육시설법 시행규칙",
        "article": "교육시설 안전·유지관리기준 제20조",
        "note": "2층 이상 추락 방지 장치 의무",
        "applicable_spaces": ALL_SPACES,
        "min_floor": 2,
    },
}

STANDARD_ITEMS: list[str] = list(LAW_BASIS.keys())

# AI가 표준 설비명과 다른 표현을 써도 매핑되도록 하는 별칭 사전.
# 자동 매핑 단계에서 별칭 일치 시 표준 설비로 연결됨.
STANDARD_ALIASES: dict[str, list[str]] = {
    "비상샤워": ["비상 샤워", "안전샤워", "안전 샤워", "긴급샤워", "응급샤워", "응급 샤워",
              "emergency shower", "safety shower", "deluge shower", "샤워 부스"],
    "세안기": ["눈세척기", "세안시설", "세안 시설", "비상 세안기", "응급 세안기",
              "eye wash", "eyewash", "eye-wash station", "eyewash station",
              "안구 세척", "눈 세척"],
    "가스차단밸브": ["가스 차단", "메인 가스 밸브", "가스 메인", "가스 차단기",
                  "가스차단", "비상 가스 차단", "가스 밸브", "main gas valve",
                  "gas shutoff", "gas shut-off"],
    "소화기": ["분말 소화기", "ABC소화기", "ABC 소화기", "분말식 소화기",
              "소화 장비", "소화 장치", "fire extinguisher", "extinguisher",
              "이산화탄소 소화기", "CO2 소화기", "할론 소화기"],
    "소화포": ["소화 담요", "fire blanket", "방화 담요", "소화 매트", "방염포",
              "fire-fighting blanket"],
    "응급처치함": ["구급함", "응급함", "응급키트", "응급 키트", "first-aid",
                "first aid", "구급 상자", "응급 상자", "구급상자", "first aid kit",
                "응급 처치 키트"],
    "AED표지": ["AED 안내", "심장충격기 표지", "심장충격기 위치", "AED 위치",
              "AED 안내 표지", "자동심장충격기", "automated external defibrillator",
              "AED sign", "심장 제세동기"],
    "완강기": ["피난기구", "비상탈출 기구", "탈출 기구", "피난 기구", "피난 사다리",
              "descending lifeline", "escape device"],
    "흄후드": ["흄 후드", "fume hood", "Fume Hood", "후드 작동",
              "국소배기 후드", "흄 hood", "fume cupboard", "draft chamber",
              "유해가스 후드", "실험실 후드"],
    "국소배기장치": ["국소 배기", "국소배기", "배기 후드", "배기 시스템",
                  "환기 후드", "배기 장치", "국소 배기 장치", "local exhaust",
                  "local ventilation", "LEV"],
    "기계환기구": ["기계 환기구", "환기 시설", "강제 환기", "환기 팬",
                "mechanical ventilation", "환기 시스템", "전열 교환기", "ERV"],
    "천장디퓨저": ["천장 디퓨저", "천장 환기구", "디퓨저", "급기구",
                "ceiling diffuser", "공조 디퓨저", "공조 그릴"],
    "환기상태(CO2)": ["CO2 농도", "이산화탄소", "환기 상태", "공기질", "실내 공기질",
                   "indoor air quality", "IAQ", "CO2 측정기", "공기질 모니터"],
    "시약장(잠금)": ["시약장", "약품 보관함", "약품 캐비닛", "잠금 시약장", "시약 보관함",
                  "chemical cabinet", "reagent cabinet", "약품장", "독극물 보관함"],
    "가스용기보관함": ["가스 용기 보관함", "가스통 보관", "가스 보관함", "가스 캐비닛",
                    "gas cylinder cabinet", "고압가스 보관함"],
    "폐액용기": ["폐액 용기", "폐액 통", "폐액 보관", "실험 폐기물",
              "waste container", "chemical waste", "폐화학물질"],
    "개인보호구함": ["개인 보호구함", "PPE 보관함", "PPE 보관", "보호구 보관함",
                  "ppe box", "PPE box", "PPE cabinet", "personal protective equipment"],
    "화재감지기": ["화재 감지기", "감지기", "fire detector",
                "화재 경보기", "차동식 감지기", "정온식 감지기", "감열식 감지기",
                "heat detector", "fire alarm sensor"],
    "가스누출감지기": ["가스 누출 감지기", "가스 누출", "가스 감지기", "gas detector",
                    "gas leak detector", "LPG 감지기", "도시가스 감지기"],
    "비상벨": ["비상 벨", "비상 호출", "긴급 호출", "비상 알람",
              "emergency bell", "panic button", "비상 버튼", "긴급 버튼"],
    "연기감지기": ["연기 감지기", "smoke detector", "smoke alarm", "광전식 감지기",
                "이온화식 감지기"],
    "보안경": ["보호 안경", "안전 안경", "고글", "safety goggles", "safety glasses",
              "보안 안경", "실험용 안경"],
    "실험복": ["실험 가운", "lab coat", "실험 복", "보호 의류", "white coat",
              "방염 가운", "labcoat"],
    "장갑": ["보호 장갑", "실험 장갑", "내화학 장갑", "lab gloves", "nitrile gloves",
            "라텍스 장갑", "니트릴 장갑"],
    "방독면": ["방독 마스크", "마스크", "방진 마스크", "respirator", "gas mask",
              "방진방독면", "정화통 마스크"],
    "실험화": ["실험 신발", "안전화", "실험 부츠", "safety shoes", "lab shoes",
              "절연화", "정전화"],
    "MSDS비치": ["MSDS", "물질안전보건자료", "물질 안전 보건 자료", "msds",
                "safety data sheet", "SDS", "GHS"],
    "안전수칙게시": ["안전 수칙", "안전수칙", "수칙 게시", "실험 수칙",
                  "safety rules", "safety guide", "수칙 안내", "유의사항"],
    "비상대응 포스터": ["비상 대응", "비상대응 안내", "대응 포스터", "비상 안내",
                    "emergency response", "대응 절차", "비상 행동요령"],
    "가스차단 표지": ["가스 차단 표지", "가스 표지", "가스 안내", "gas shutoff sign"],
    "비상구 표시등": ["비상구", "EXIT", "비상구 안내", "유도등", "피난 유도",
                  "exit sign", "emergency exit", "피난 안내", "비상 출구"],
    "콘센트 안전": ["콘센트", "안전 커버", "콘센트 커버", "GFCI", "누전 차단",
                "outlet cover", "ELCB"],
    "멀티탭 안전": ["멀티탭", "멀티 탭", "전원 탭", "콘센트 멀티탭",
                "power strip", "extension cord"],
    "조명 안전": ["조명", "전등", "조명 시설", "형광등", "LED 조명",
                "lighting", "luminaire"],
    "책걸상 안전": ["책상", "걸상", "의자", "책걸상", "학생 의자",
                "desk", "chair", "school furniture"],
    "창문 추락방지": ["창문 안전", "추락 방지", "창문 잠금", "추락방지",
                  "window guard", "fall prevention", "창문 안전 장치"],
}


def find_std_match(text: str) -> str | None:
    """텍스트에서 표준 설비명 또는 별칭을 찾아 표준 설비명을 반환.

    매칭 우선순위:
    1) 표준 설비명 직접 포함
    2) 별칭 사전의 별칭 포함
    """
    haystack = text.lower()
    for std in STANDARD_ITEMS:
        if std.lower() in haystack:
            return std
    for std, aliases in STANDARD_ALIASES.items():
        for a in aliases:
            if a.lower() in haystack:
                return std
    return None


CATEGORIES: list[str] = [
    "비상 대응",
    "환기·배기",
    "보관·격리",
    "감지·경보",
    "개인보호구",
    "안내·표지",
    "시설·전기",
]


# ─────────────────────────────────────────
# Helper
# ─────────────────────────────────────────
def items_by_category(category: str) -> list[str]:
    return [name for name, info in LAW_BASIS.items() if info["category"] == category]


def law_for(item_name: str) -> dict:
    return LAW_BASIS.get(item_name, {})


def items_for_space(space_type: str | None,
                     floor: int | None = None) -> list[str]:
    """주어진 공간 유형·층수에 적용되는 표준 항목 이름 리스트.

    - applicable_spaces 에 포함되지 않으면 제외
    - min_floor 가 있으면 floor 가 그 이상일 때만 포함 (정보 없으면 보수적으로 포함)
    """
    if not space_type:
        return list(LAW_BASIS.keys())
    out: list[str] = []
    for name, info in LAW_BASIS.items():
        spaces = info.get("applicable_spaces") or ALL_SPACES
        if space_type not in spaces:
            continue
        min_floor = info.get("min_floor")
        if min_floor is not None and floor is not None and floor < min_floor:
            continue
        out.append(name)
    return out


CORE_LAWS = [
    "학교보건법",
    "교육시설법",
    "학교안전법",
    "산업안전보건법",
    "소방시설법",
    "위험물안전관리법",
    "전기설비기술기준",
    "응급의료에 관한 법률",
]
