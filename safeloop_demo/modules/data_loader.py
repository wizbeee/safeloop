"""
데이터 로더 — CSV 캐싱·학교 검색·익명화.

검색 API:
- search_schools_by_name(query) 이름 부분 일치
- list_sido() 시도 목록
- list_sigungu(sido) 시군구 목록
- list_schools(sido, sigungu) 학교 리스트
- get_school_by_code(code) 식별자 조회
- anonymize_code(code) 해시 익명화
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def _strip_bom(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.lstrip("\ufeff").strip() for c in df.columns]
    return df


def _safe_read_csv(name: str, **kwargs) -> pd.DataFrame:
    """CSV 누락 시 친절한 에러 + 재현 가이드."""
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"데이터 파일이 없습니다: data/{name}\n"
            f"git pull로 데이터를 받았는지 확인하세요. "
            f"또는 'SafeLoop_데모앱_이관세트/data/' 에서 복사해 주세요."
        )
    return pd.read_csv(path, **kwargs)


@st.cache_data(show_spinner=False)
def load_master() -> pd.DataFrame:
    return _strip_bom(_safe_read_csv("master_school_data.csv",
                                       dtype={"정보공시 학교코드": str}))


@st.cache_data(show_spinner=False)
def load_high_risk() -> pd.DataFrame:
    return _strip_bom(_safe_read_csv("high_risk_schools.csv",
                                       dtype={"정보공시 학교코드": str}))


@st.cache_data(show_spinner=False)
def load_sido_summary() -> pd.DataFrame:
    return _strip_bom(_safe_read_csv("sido_summary.csv"))


@st.cache_data(show_spinner=False)
def load_cluster_summary() -> pd.DataFrame:
    return _strip_bom(_safe_read_csv("cluster_summary.csv"))


@st.cache_data(show_spinner=False)
def load_sensitivity() -> pd.DataFrame:
    return _strip_bom(_safe_read_csv("sensitivity_result.csv"))


# ─────────────────────────────────────────
# 시도교육청별 안전점검 담당부서 공통 이메일 (시연용)
# - 학교 담당자가 교육청 담당자 이메일을 몰라도, 시도교육청만 알면 발송 가능
# - 정식 출시 시 각 교육청과 협의해 실 주소 등록
# ─────────────────────────────────────────
SIDO_EDU_EMAIL: dict[str, str] = {
    "서울특별시교육청": "safety@sen.go.kr",
    "부산광역시교육청": "safety@pen.go.kr",
    "대구광역시교육청": "safety@dge.go.kr",
    "인천광역시교육청": "safety@ice.go.kr",
    "광주광역시교육청": "safety@gen.go.kr",
    "대전광역시교육청": "safety@dje.go.kr",
    "울산광역시교육청": "safety@use.go.kr",
    "세종특별자치시교육청": "safety@sje.go.kr",
    "경기도교육청": "safety@goe.go.kr",
    "강원특별자치도교육청": "safety@gwe.go.kr",
    "충청북도교육청": "safety@cbe.go.kr",
    "충청남도교육청": "safety@cne.go.kr",
    "전북특별자치도교육청": "safety@jbe.go.kr",
    "전라남도교육청": "safety@jne.go.kr",
    "경상북도교육청": "safety@gbe.go.kr",
    "경상남도교육청": "safety@gne.go.kr",
    "제주특별자치도교육청": "safety@jje.go.kr",
}


def get_sido_edu_email(sido: str | None) -> str | None:
    """시도교육청 이름으로 안전점검 담당부서 공통 이메일 조회. 없으면 None."""
    if not sido:
        return None
    return SIDO_EDU_EMAIL.get(sido.strip())


@st.cache_data(show_spinner=False)
def estimated_national_safety_score() -> dict:
    """전국 평균 안전 점수 추정.

    high_risk 의 위험도_점수를 0~100 안전 점수로 변환 (위험도 안전 ).
    반환:
      {
        "mean": 전국 평균 안전 점수(0~100),
        "sido_means": {시도교육청명: 평균 안전 점수},
        "school_score": {학교코드: 안전 점수} # 학교별 빠른 조회용
      }
    """
    df = load_high_risk()
    if df.empty or "위험도_점수" not in df.columns:
        return {"mean": 0.0, "sido_means": {}, "school_score": {}}
    rmax = float(df["위험도_점수"].max())
    rmin = float(df["위험도_점수"].min())
    if rmax == rmin:
        df = df.assign(안전점수_추정=100.0)
    else:
        df = df.assign(
            안전점수_추정=((rmax - df["위험도_점수"]) / (rmax - rmin) * 100).round(1)
        )
    sido_means = df.groupby("시도교육청")["안전점수_추정"].mean().round(1).to_dict()
    school_score = dict(zip(
        df["정보공시 학교코드"].astype(str),
        df["안전점수_추정"].astype(float),
    ))
    return {
        "mean": float(round(df["안전점수_추정"].mean(), 1)),
        "sido_means": {k: float(v) for k, v in sido_means.items()},
        "school_score": school_score,
    }


@st.cache_data(show_spinner=False)
def load_sigungu_agg() -> pd.DataFrame:
    return _strip_bom(_safe_read_csv("sigungu_agg.csv"))


@st.cache_data(show_spinner=False)
def load_risk_analysis() -> pd.DataFrame:
    return _strip_bom(_safe_read_csv("risk_analysis_result.csv",
                                       dtype={"정보공시 학교코드": str}))


# ─────────────────────────────────────────
# 검색 API
# ─────────────────────────────────────────
def list_sido() -> list[str]:
    df = load_master()
    return sorted(df["시도교육청"].dropna().unique().tolist())


def list_sigungu(sido: str) -> list[str]:
    df = load_master()
    subset = df[df["시도교육청"] == sido]
    sigungu = subset["지역"].dropna().apply(_extract_sigungu).unique().tolist()
    return sorted([s for s in sigungu if s])


def _extract_sigungu(region: str) -> str:
    """'서울특별시 강남구' '강남구' 추출."""
    if not isinstance(region, str):
        return ""
    parts = region.strip().split()
    return parts[-1] if len(parts) >= 2 else region


def list_schools(sido: str, sigungu: str) -> pd.DataFrame:
    df = load_master()
    subset = df[df["시도교육청"] == sido].copy()
    subset["시군구"] = subset["지역"].apply(_extract_sigungu)
    subset = subset[subset["시군구"] == sigungu]
    return subset[["정보공시 학교코드", "학교명", "학교급", "설립구분", "지역"]].reset_index(drop=True)


def search_schools_by_name(query: str, limit: int = 50) -> pd.DataFrame:
    df = load_master()
    if not query:
        return df.head(0)
    mask = df["학교명"].astype(str).str.contains(re.escape(query), na=False, case=False)
    return df.loc[mask, ["정보공시 학교코드", "학교명", "학교급", "설립구분", "시도교육청", "지역"]].head(limit).reset_index(drop=True)


def get_school_by_code(code: str) -> dict | None:
    df = load_master()
    hit = df[df["정보공시 학교코드"] == str(code)]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


def get_school_risk(code: str) -> dict | None:
    try:
        df = load_risk_analysis()
    except FileNotFoundError:
        return None
    hit = df[df["정보공시 학교코드"] == str(code)]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


# ─────────────────────────────────────────
# 익명화
# ─────────────────────────────────────────
_ANON_SALT = "safeloop-2026-demo"


def anonymize_code(code: str) -> str:
    """학교 코드를 해시 익명화(공공데이터 환원용)."""
    if not code:
        return ""
    digest = hashlib.sha256(f"{_ANON_SALT}|{code}".encode("utf-8")).hexdigest()
    return f"ANON-{digest[:12].upper()}"


@lru_cache(maxsize=1024)
def pseudo_school_name(code: str) -> str:
    """대시보드 B(공공 공개용) 전용 가명 이름."""
    if not code:
        return "학교_미상"
    h = int(hashlib.sha256(f"{_ANON_SALT}|{code}".encode("utf-8")).hexdigest(), 16)
    return f"학교_{h % 100000:05d}"


# ─────────────────────────────────────────
# 인증번호 (시연용)
# ─────────────────────────────────────────
def issue_auth_code(school_code: str) -> str:
    """학교 코드 기반 고정 인증번호 (6자리) — 시연용."""
    h = hashlib.sha256(f"SAFELOOP-AUTH|{school_code}".encode("utf-8")).hexdigest()
    num = int(h[:8], 16) % 1_000_000
    return f"{num:06d}"


def verify_auth_code(school_code: str, code: str) -> bool:
    return str(code).strip() == issue_auth_code(school_code)
