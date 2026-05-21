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


def _synth_coverage_metrics() -> dict:
    """합성 응답의 공간별 LAW_BASIS 매칭률 산출 — recall/precision-like.

    coverage (recall-like): 표준 항목 중 합성 응답에 포함된 비율
    precision-like: 합성 detected 중 표준 항목과 매칭되는 비율
    """
    from modules.laws import ALL_SPACES, items_for_space
    from modules.demo_responses import synth_stage2_for_space

    out = {}
    space_targets = [
        "화학실", "물리실", "생명과학실", "지구과학실",
        "기술실", "가정실", "음악실", "미술실", "일반교실",
    ]
    for sp in space_targets:
        if sp not in ALL_SPACES:
            continue
        s2 = synth_stage2_for_space(sp)
        detected = s2.get("detected_equipment", []) or []
        detected_names = {(d.get("name") or "").strip() for d in detected if d.get("name")}
        standard = set(items_for_space(sp))

        hit = standard & detected_names
        coverage_pct = (len(hit) / len(standard) * 100) if standard else 0.0
        # precision-like: 합성 detected 중 표준 매칭 비율
        # (모두 LAW_BASIS 기반 매핑이므로 100% 에 가까움 — 합성 로직 검증용)
        precision_pct = (len(hit) / len(detected_names) * 100) if detected_names else 0.0

        out[sp] = {
            "standard_count": len(standard),
            "detected_count": len(detected_names),
            "matched_count": len(hit),
            "coverage_pct": round(coverage_pct, 1),
            "precision_pct": round(precision_pct, 1),
            "missing_from_synth": sorted(standard - detected_names)[:10],
        }
    return out


def _real_api_cache_summary() -> dict | None:
    """_ai_cache 폴더의 실 API 응답 캐시 분석 (있을 때만)."""
    cdir = ROOT / "school_storage" / "_ai_cache"
    if not cdir.exists():
        return None

    total = 0
    synth = 0
    real_api = 0
    by_space: dict[str, dict[str, int]] = {}

    for f in cdir.glob("stage2_*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        total += 1
        is_synth = bool(d.get("_synth_demo"))
        if is_synth:
            synth += 1
        else:
            real_api += 1
        # 파일명에서 공간 추출 (마지막 _공간.json)
        stem = f.stem
        parts = stem.rsplit("_", 1)
        sp = parts[1] if len(parts) == 2 else "기타"
        by_space.setdefault(sp, {"synth": 0, "real_api": 0})
        by_space[sp]["synth" if is_synth else "real_api"] += 1

    if total == 0:
        return None

    return {
        "total_cached": total,
        "synth_count": synth,
        "real_api_count": real_api,
        "by_space": by_space,
        "note": "현재 캐시는 시연용 합성 응답 위주. "
                "실 학교 사진 + 실 API 호출 기반의 정확도(precision/recall) 측정은 "
                "교육청 시범사업 단계에서 진행 예정.",
    }


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


def write_markdown_table(
    path: Path,
    coverage: dict,
    mapping: dict | None,
    synth_metrics: dict | None = None,
    cache_summary: dict | None = None,
) -> None:
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

    # ─── 합성 응답 정량 검증 (Q&A 대비) ───
    if synth_metrics:
        lines += [
            "",
            "## AI 합성 응답 정량 검증 (공간별 LAW_BASIS 매칭률)\n",
            "법령 기반 표준 항목 대비 합성 응답 detected 매칭률.",
            "Coverage(recall-like) = 표준 항목 중 합성 응답에 포함된 비율,",
            "Precision-like = 합성 detected 중 표준과 매칭된 비율.\n",
            "| 공간 | 표준 | 합성 detected | 매칭 | Coverage | Precision-like |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for sp, m in sorted(
            synth_metrics.items(),
            key=lambda x: -x[1]["coverage_pct"],
        ):
            lines.append(
                f"| {sp} | {m['standard_count']} | {m['detected_count']} | "
                f"{m['matched_count']} | **{m['coverage_pct']}%** | "
                f"{m['precision_pct']}% |"
            )
        # 평균
        avg_cov = sum(m["coverage_pct"] for m in synth_metrics.values()) / len(synth_metrics)
        avg_prec = sum(m["precision_pct"] for m in synth_metrics.values()) / len(synth_metrics)
        lines += [
            "",
            f"**평균 Coverage: {avg_cov:.1f}%** · "
            f"**평균 Precision-like: {avg_prec:.1f}%**",
            "",
            "> 위 수치는 시연 모드 합성 응답(LAW_BASIS 기반)에 한정됩니다.",
            "> 실 학교 사진 + 실 Claude Vision API 호출 기반의 정확도",
            "> (precision/recall) 측정은 교육청 시범사업 단계에서 진행 예정.",
        ]

    # ─── 캐시 분포 (시연·실 API 분리) ───
    if cache_summary:
        lines += [
            "",
            "## AI 응답 캐시 분포 (정직성)\n",
            f"- 총 캐시: {cache_summary['total_cached']}건",
            f"- 시연 합성 응답: {cache_summary['synth_count']}건",
            f"- 실 API 응답: {cache_summary['real_api_count']}건",
            "",
            f"> {cache_summary['note']}",
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

    print("[3/5] 합성 응답 정량 검증 (공간별 매칭률)...")
    synth_metrics = _synth_coverage_metrics()
    if synth_metrics:
        rows = [
            {
                "space": sp,
                "standard_count": m["standard_count"],
                "detected_count": m["detected_count"],
                "matched_count": m["matched_count"],
                "coverage_pct": m["coverage_pct"],
                "precision_like_pct": m["precision_pct"],
            }
            for sp, m in synth_metrics.items()
        ]
        write_csv(
            OUT_DIR / "synth_coverage.csv",
            rows,
            ["space", "standard_count", "detected_count",
             "matched_count", "coverage_pct", "precision_like_pct"],
        )
        print(f"  -> {OUT_DIR / 'synth_coverage.csv'}")

    print("[4/5] 캐시 분포 분석...")
    cache_summary = _real_api_cache_summary()
    if cache_summary:
        write_json(OUT_DIR / "cache_distribution.json", cache_summary)
        print(f"  -> {OUT_DIR / 'cache_distribution.json'}")

    print("[5/5] PPT용 markdown 표 생성...")
    write_markdown_table(
        OUT_DIR / "pitch_table.md",
        coverage,
        mapping,
        synth_metrics=synth_metrics,
        cache_summary=cache_summary,
    )
    print(f"  -> {OUT_DIR / 'pitch_table.md'}")

    print("\n핵심 수치 요약")
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
