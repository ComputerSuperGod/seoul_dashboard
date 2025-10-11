# pages/9_데이터 정리.py
# 📦 데이터 정리 (데이터셋 개요 / 스키마 / 적재상태)

from __future__ import annotations
from pathlib import Path
import streamlit as st
import pandas as pd

st.set_page_config(page_title="데이터 정리 | AIoT 스마트 인프라 대시보드", layout="wide")

# ────────────────────────────────────────────────────────────────
# 경로/상수
# ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[1]  # 프로젝트 루트
DATA_DIR = BASE_DIR / "data"

# ✅ 출처 매핑
SOURCE_MAP = {
    "seoul_redev_projects.csv": "서울시 재개발 재건축(금비씨)",
    "AverageSpeed(LINK).xlsx": "View-T",
    "AverageSpeed(LINK)_2023.csv": "View-T (변환)",
    "TrafficVolume_Seoul_2023.csv": "View-T",
    # SHP 세트(확장자 4종)
    "seoul_link_lev5.5_2023.shp": "View-T",
    "seoul_link_lev5.5_2023.shx": "View-T",
    "seoul_link_lev5.5_2023.dbf": "View-T",
    "seoul_link_lev5.5_2023.prj": "View-T",
    "서울시_재개발재건축_clean_kakao.csv": "서울시 재개발 재건축(x,y 변환 컬럼 포함)",
}

# 스캔 대상(세트 단위 표기를 위해 group 정의)
DATASETS = [
    dict(
        group="정비사업 목록",
        files=["seoul_redev_projects.csv"],
        required=True,
        desc="사업 기본정보/세대수/면적 등"
    ),
    dict(
        group="평균속도(원본 엑셀)",
        files=["AverageSpeed(LINK).xlsx"],
        required=False,
        desc="보고서형 원천자료 (있으면 CSV 자동 변환)"
    ),
    dict(
        group="평균속도(정규화 CSV)",
        files=["AverageSpeed(LINK)_2023.csv"],
        required=True,
        desc="링크×시간대 평균속도(long) — 대시보드 사용"
    ),
    dict(
        group="교통량(선택)",
        files=["TrafficVolume_Seoul_2023.csv"],
        required=False,
        desc="링크×시간대 교통량(대수) — 고급지표용"
    ),
    dict(
        group="도로 Shapefile(5.5 레벨)",
        files=[
            "seoul_link_lev5.5_2023.shp",
            "seoul_link_lev5.5_2023.shx",
            "seoul_link_lev5.5_2023.dbf",
            "seoul_link_lev5.5_2023.prj",
        ],
        required=True,
        desc="링크 지오메트리 (4종 모두 필요)"
    ),
    dict(
        group="정비구역 좌표(클린)",
        files=["서울시_재개발재건축_clean_kakao.csv"],
        required=True,
        desc="정비구역명/자치구 기준 좌표 매핑"
    ),
]

# ────────────────────────────────────────────────────────────────
# UI
# ────────────────────────────────────────────────────────────────
st.title("📦 데이터 정리")
tabs = st.tabs(["데이터셋 개요", "스키마/예시", "적재 상태"])

# ----------------------------------------------------------------
# 탭1 — 데이터셋 개요 (출처 포함)
# ----------------------------------------------------------------
with tabs[0]:
    rows = []
    for ds in DATASETS:
        # ✅ 단순화된 상태 표시
        status = "✅" if ds["required"] else "—"

        sources = [SOURCE_MAP.get(f, "") for f in ds["files"]]
        src_unique = list({s for s in sources if s})
        src_display = src_unique[0] if len(src_unique) == 1 else (" / ".join(src_unique) if src_unique else "")
        rows.append({
            "항목": ds["group"],
            "파일/세트": ", ".join(ds["files"]),
            "필수여부": "필수" if ds["required"] else "선택",
            "상태": status,
            "출처": src_display,
            "설명": ds["desc"],
        })
    df_overview = pd.DataFrame(rows, columns=["항목","파일/세트","필수여부","상태","출처","설명"])
    st.dataframe(df_overview, use_container_width=True, hide_index=True)

    st.caption("표기: ✅=필수 데이터, —=선택 데이터")


# ----------------------------------------------------------------
# 탭2 — 스키마/예시
# ----------------------------------------------------------------
with tabs[1]:
    st.subheader("스키마 요약")
    schema_rows = [
        dict(파일="seoul_redev_projects.csv", 주요컬럼="사업번호, 정비구역명칭/조합명, 자치구, 분양세대총수, 정비구역면적(㎡), 용적률, 층수...", 비고="app.py에서 normalize_projects()로 정규화"),
        dict(파일="AverageSpeed(LINK)_2023.csv", 주요컬럼="link_id, 시간대, 평균속도(km/h), hour", 비고="utils/traffic_preproc.convert_average_speed_excel_to_csv()"),
        dict(파일="TrafficVolume_Seoul_2023.csv", 주요컬럼="link_id, hour, 차량대수", 비고="선택"),
        dict(파일="seoul_link_lev5.5_2023.{shp,shx,dbf,prj}", 주요컬럼="k_link_id/link_id/LINK_ID, geometry", 비고="WGS84 변환 후 사용"),
        dict(파일="서울시_재개발재건축_clean_kakao.csv", 주요컬럼="사업번호, 정비구역명칭/조합명, 자치구, lat, lon, full_address", 비고="좌표/주소 병합"),
    ]
    st.dataframe(pd.DataFrame(schema_rows), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------
# 탭3 — 적재 상태(간소화 버전)
# ----------------------------------------------------------------
with tabs[2]:
    st.subheader("파일 요약 (출처 중심)")

    files = []
    for ds in DATASETS:
        for f in ds["files"]:
            files.append({
                "파일": f,
                "출처": SOURCE_MAP.get(f, ""),
                "구분": ds["group"],
                "필수여부": "필수" if ds["required"] else "선택",
                "설명": ds["desc"],
            })

    df_files = pd.DataFrame(files, columns=["파일", "출처", "구분", "필수여부", "설명"])
    st.dataframe(df_files, use_container_width=True, hide_index=True)

    st.caption("※ 파일 존재 여부 대신 출처 중심의 정보만 표시합니다.")
