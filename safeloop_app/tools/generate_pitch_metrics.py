"""발표·PPT 용 검증 수치 자동 생성 스크립트.

코덱스 검토에서 제안된 "AI가 추가 보완한 항목 24개" 등 구체 수치를 자동
산출하여 PPT/발표용 CSV·JSON·Markdown 표로 export.

데이터 소스:
- modules/laws.py:LAW_BASIS (공간별 표준 항목)
- _archive_v8_contest/validation/V1_점검표비교_v3.xlsx (교육부 표준 매핑)

산출물 (tools/_pitch_metrics_out/ 아래):
- space_coverage.csv — 공간별 SafeLoop 표준 항목 수
- ai_supplement.csv  — AI 보완 항목 명단 (교육부 표준에 없는 것)
- mapping_summary.json — 공통/부분공통/AI보완 분포
- pitch_table.md     — PPT 에 바로 복붙할 수 있는 markdown 표

사용법:
    cd safeloop_app
    python tools/generate_pitch_metrics.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "tools" / "_pitch_metrics_out"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _law_basis_metrics() -> dict:
    """LAW_BASIS 기반 공간별 표준 항목 수 산출."""
    from modules.laws import ALL_SPACES, items_for_space

    coverage = {}
    for sp in ALL_SPACES:
        items = items_for_space(sp)
        coverage[sp] = {
            "space": sp,
            "safeloop_items": len(items),
            "items": items,
        }
    return coverage


def _moe_mapping_metrics() -> dict | None:
    """교육부 표준 매핑 데이터 — archive 폴더에 있을 때만."""
    xlsx = ROOT.parent / "_archive_v8_contest" / "validation" / "V1_점검표비교_v3.xlsx"
    if not xlsx.exists():
        return None
    try:
        import pandas as pd
    except ImportError:
        return None

    df = pd.read_excel(xlsx, "AI매핑_교육부", header=4)
    df.columns = ["no", "카테고리", "AI맞춤항목", "매핑유형", "근거"]
    df = df.dropna(subset=["AI맞춤항목"]).reset_index(drop=True)

    summary = {
        "total_ai_items": int(len(df)),
        "moe_standard_count": 8,  # 시트 설명상 교육부 표준 실험실 8항목
        "mapping_distribution": df["매핑유형"].value_counts().to_dict(),
        "category_distribution": df["카테고리"].value_counts().to_dict(),
        "ai_supplement_count": int((df["매핑유형"] == "AI보완").sum()),
        "ai_supplement_items": [
            {
                "category": r["카테고리"],
                "name": r["AI맞춤항목"],
                "rationale": r["근거"],
            }
            for _, r in df[df["매핑유형"] == "AI보완"].iterrows()
        ],
    }
    return summary


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown_table(path: Path, coverage: dict, mapping: dict | None) -> None:
    lines = [
        "# SafeLoop 발표·PPT 용 비교 수치 (자동 생성)\n",
        "## 공간별 SafeLoop 표준 점검 항목 수\n",
        "| 공간 | 표준 항목 수 |",
        "|---|---:|",
    ]
    for sp, info in sorted(
        coverage.items(),
        key=lambda x: -x[1]["safeloop_items"],
    ):
        lines.append(f"| {sp} | {info['safeloop_items']} |")

    if mapping:
        d = mapping["mapping_distribution"]
        ai_n = mapping["ai_supplement_count"]
        total = mapping["total_ai_items"]
        moe = mapping["moe_standard_count"]
        lines += [
            "",
            "## 교육부 표준 vs SafeLoop AI 맞춤 (실험실 영역)\n",
            f"- 교육부 표준 실험실: **{moe}항목**",
            f"- SafeLoop AI 맞춤: **{total}항목**",
            f"- 매핑 유형:",
            f"  - 공통: {d.get('공통', 0)}항목 (교육부·SafeLoop 모두 포함)",
            f"  - 부분공통: {d.get('부분공통', 0)}항목 (의미 유사·세분화 차이)",
            f"  - **AI 보완: {ai_n}항목** (교육부 표준에 없는 SafeLoop 추가)",
            "",
            "## AI 보완 항목 목록 (대상급 발표 포인트)\n",
            "| 카테고리 | 항목 | 근거 |",
            "|---|---|---|",
        ]
        for it in mapping["ai_supplement_items"]:
            rationale = (it["rationale"] or "")[:80].replace("\n", " ")
            lines.append(f"| {it['category']} | **{it['name']}** | {rationale} |")
        lines += [
            "",
            "## 발표 한 줄 문장 예시\n",
            f"> 기존 교육부 표준 점검표는 실험실 영역 {moe}항목만 포착했지만, ",
            f"> SafeLoop 는 법령 기반 {total}항목으로 확장하여 **{ai_n}개 항목을 추가 보완**합니다.",
            f"> (예: 흄후드·MSDS·세안기·시약장·비상샤워·가스차단밸브·화재감지기·연기감지기 등)",
        ]

    lines += [
        "",
        "---",
        "*자동 생성: `tools/generate_pitch_metrics.py`*",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print("[1/4] LAW_BASIS 공간별 항목 수 산출...")
    coverage = _law_basis_metrics()

    rows = [
        {"space": sp, "safeloop_items": info["safeloop_items"]}
        for sp, info in sorted(
            coverage.items(),
            key=lambda x: -x[1]["safeloop_items"],
        )
    ]
    write_csv(OUT_DIR / "space_coverage.csv", rows, ["space", "safeloop_items"])
    print(f"  -> {OUT_DIR / 'space_coverage.csv'}")

    print("[2/4] 교육부 표준 매핑 분석...")
    mapping = _moe_mapping_metrics()
    if mapping:
        rows = [
            {
                "no": i + 1,
                "category": it["category"],
                "ai_item": it["name"],
                "rationale": it["rationale"],
            }
            for i, it in enumerate(mapping["ai_supplement_items"])
        ]
        write_csv(
            OUT_DIR / "ai_supplement.csv",
            rows,
            ["no", "category", "ai_item", "rationale"],
        )
        print(f"  -> {OUT_DIR / 'ai_supplement.csv'}")
        write_json(OUT_DIR / "mapping_summary.json", mapping)
        print(f"  -> {OUT_DIR / 'mapping_summary.json'}")
    else:
        print("  (skip — archive 폴더 또는 pandas 없음)")

    print("[3/4] PPT용 markdown 표 생성...")
    write_markdown_table(OUT_DIR / "pitch_table.md", coverage, mapping)
    print(f"  -> {OUT_DIR / 'pitch_table.md'}")

    print("[4/4] 핵심 수치 요약")
    print("=" * 60)
    print(f"  공간별 SafeLoop 표준 (상위 5):")
    for sp, info in sorted(
        coverage.items(),
        key=lambda x: -x[1]["safeloop_items"],
    )[:5]:
        print(f"    - {sp}: {info['safeloop_items']}항목")
    if mapping:
        d = mapping["mapping_distribution"]
        print()
        print(f"  교육부 표준 실험실 vs SafeLoop AI:")
        print(f"    - 교육부: {mapping['moe_standard_count']}항목")
        print(f"    - SafeLoop AI: {mapping['total_ai_items']}항목")
        print(f"      (공통 {d.get('공통', 0)} + 부분공통 {d.get('부분공통', 0)} "
              f"+ AI보완 {mapping['ai_supplement_count']})")
    print("=" * 60)
    print(f"\n발표용 표는 {OUT_DIR / 'pitch_table.md'} 에서 복사하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
