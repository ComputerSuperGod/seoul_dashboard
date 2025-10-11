import streamlit as st
from pathlib import Path

st.set_page_config(page_title="🧪 기술 문서 | AIoT 스마트 인프라 대시보드", layout="wide")
st.title("🧪 기술 문서 (핵심 코드 · 파이프라인 · 핵심 기술)")
st.caption("핵심 모듈 동작 원리, 데이터 파이프라인 상세, 사용 기술/의존성/성능 전략을 문서화")

# ---------------------------------------------------------------------
# 스타일
# ---------------------------------------------------------------------
st.markdown(
    """
    <style>
      .small-muted { color:#9ca3af; font-size:0.9rem; }
      .bullet-muted li { color:#d1d5db; }
      .card { padding: 14px; border-radius: 14px; background: #111827; border: 1px solid #1f2937; }
      hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
      pre, code { font-size: 0.95rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =====================================================================
# 0) 한 눈에 보기
# =====================================================================
with st.container(border=True):
    st.subheader("📌 개요")
    st.markdown(
        """
        - 목적: **재건축 후보지의 교통·사업성**을 AIoT+GIS 데이터로 정량화하여 **의사결정**을 돕는 대시보드.
        - 핵심: **반경 내 링크 매칭 → 시간대 속도/혼잡 분석 → 시나리오·민감도·확률** → **리포트**.
        - 구조: **Streamlit 멀티페이지**(pages/*) + **컴포넌트**(components/*) + **유틸**(utils/*) + **데이터**(data/*).
        """
    )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# =====================================================================
# 1) 시스템 아키텍처
# =====================================================================
with st.container(border=True):
    st.subheader("🏗 시스템 아키텍처")
    colA, colB = st.columns([1.2, 1])
    with colA:
        st.markdown(
            """
            ```text
            [사용자]
               │  (사이드바 입력/프리셋)
               ▼
            [app/app.py]
               │  - 페이지 라우팅, 세션 상태, 데이터 경로
               ▼
            [components/]
               │  - sidebar_4quadrant_guide: 기능 요약
               │  - sidebar_presets: 데모 프리셋 주입
               ▼
            [pages/]
               │  - 1~5: FAQ/개념/가이드/로직/공식
               │  - 6: 발표정리, 7: 기술문서(본 페이지)
               ▼
            [utils/]
               │  - traffic_preproc: Excel→CSV 표준화, 헤더탐지
               │  - traffic_plot: 반경검색+속도차트(Altair/MPL/Plotly)
               ▼
            [data/]
               ├  재건축 후보지 CSV
               ├  AverageSpeed/TrafficVolume
               └  도로망 SHP(lev5.5)
            ```
            """
        )
    with colB:
        st.markdown(
            """
            **특징**
            - 링크ID 표준화(`link_id`)와 좌표계 변환(EPSG:4326/3857)
            - 반경(미터) 기반 **근접 링크 서브셋** 추출
            - 렌더러 스위치: `Altair` 기본, `Matplotlib/Plotly` 옵션
            - **세션 상태**로 선택/프리셋 유지, 캐시로 재연산 최소화
            """
        )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# =====================================================================
# 2) 핵심 코드 설명 (모듈 별)
# =====================================================================
with st.container(border=True):
    st.subheader("🧩 핵심 코드 설명")

    with st.expander("utils/traffic_preproc.py — Excel → Long CSV 표준화", expanded=True):
        st.markdown(
            """
            - **문제**: 보고서형 Excel에서 시간대 헤더(예: `0~1시`) 위치가 다름.
            - **해결**: 상단 15행을 스캔하여 시간대 패턴을 다수 포함한 행을 **헤더 행**으로 자동 탐지.
            - **출력**: `link_id`, `시간대`, `평균속도(km/h)`, `hour`(정수) 컬럼의 **Long 포맷 CSV**.

            ```python
            def _detect_layout(df0, max_scan_rows=15):
                # '0~1시' 패턴 다수 존재하는 행을 시간헤더로 찾음
                # base_header_row, time_row, time_start_col, data_start_row 반환

            def convert_average_speed_excel_to_csv(xlsx_path, out_csv_path):
                # 1) 레이아웃 탐지 → 헤더 구성
                # 2) wide→long melt, '시간대'에서 시작시각 hour 추출
                # 3) 링크 식별자 → 표준 컬럼명 'link_id'

            def ensure_speed_csv(xlsx_path, out_csv_path):
                # CSV 미존재 시 자동 변환 보장
            ```
            """
        )

    with st.expander("utils/traffic_plot.py — 반경 검색 + 시간대 속도 차트", expanded=True):
        st.markdown(
            """
            - **목표**: 중심점(lat/lon)과 반경(m) 내의 도로 **링크**를 찾고, 해당 링크의 **시간대 평균속도**를 시각화.
            - **링크 추출**: SHP를 4326→3857로 변환 후 **거리 계산**으로 반경 필터링.
            - **ID 표준화**: CSV의 `its_link_id`도 자동으로 `link_id`로 통일.
            - **렌더러**: `plot_speed(..., renderer='altair'|'mpl'|'plotly')` 로 통합 API.

            ```python
            def _read_shp_robust(shp_path):
                # pyogrio/fiona + utf-8/cp949/euc-kr 조합을 순차 시도 → 견고한 로더

            def get_nearby_speed_data(csv_path, shp_path, center_lon, center_lat, radius_m=1000):
                # 1) SHP를 4326→3857로 투영, 중심점과 거리 계산
                # 2) 반경 내 k_link_id 집합 만들기
                # 3) CSV의 link_id와 교집합 필터
                # 4) 상위 N개 링크만 정렬 반환

            def altair_nearby_speed(df_plot):
                # legend 선택기로 링크별 속도 추이를 인터랙티브하게 표시
            ```
            """
        )

    with st.expander("app.py — 데이터 병합, 필터, CFI(혼잡빈도강도) 계산", expanded=False):
        st.markdown(
            """
            - **좌표 매칭**: `merge_projects_with_coords(gu)` — 후보지 정보와 좌표 CSV를 조인, 결측은 **구 중심+지터**로 보정.
            - **테이블 필터링/정렬**: 세대수·면적·키워드 범주 필터 및 정렬 옵션.
            - **혼잡빈도강도(CFI)**
                - `compute_cfi_weighted(speed_df, vol_df, boundary_speed=30)` :
                  속도≤경계값일 때의 차량수를 가중 평균하여 CFI% 산출.
                - `compute_cfi_soft(speed_df, vol_df, boundary_mode='percentile', boundary_value=40, tau_kmh=6)` :
                  **시그모이드** 기반 혼잡확률로 부드럽게 추정(교통량 가중).
            ```python
            # 핵심 아이디어(soft)
            p = percentile(속도, boundary_value) if percentile else fixed
            p_cong = 1 / (1 + exp((v - p) / tau))
            CFI = weighted_avg(p_cong, 차량대수) * 100
            ```
            """
        )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# =====================================================================
# 3) 데이터 파이프라인 (상세 단계)
# =====================================================================
with st.container(border=True):
    st.subheader("🔄 데이터 파이프라인 (상세)")
    st.markdown(
        """
        **입력**: 재건축 후보지 CSV, AverageSpeed Excel/CSV, TrafficVolume Excel, 도로망 SHP

        **전처리**
        1. *스키마 통일*: 후보지 CSV에서 컬럼 이질성 보정(세대수/면적/용적률/층수 파싱, %/문자 제거)
        2. *Excel 표준화*: `ensure_speed_csv` 로 평균속도 보고서를 **Long CSV**로 변환
        3. *좌표계/ID 처리*: SHP → EPSG:3857, CSV `link_id`를 문자열화(0/NaN/"-1" 제거)
        4. *근접 링크 추출*: 중심점 기준 반경(m) 내 링크 상위 N개 선택
        5. *속도×교통량 결합*: 시간대 단위로 merge 후 CFI 계산(가중/soft)

        **분석/시각화**
        - pydeck 지도: 링크별 혼잡 색상 (일평균 또는 시간대별)
        - Altair 차트: 링크별 시간대 속도 추이(legend 선택)
        - 4사분면 KPI: 매출/비용/NPV/Payback + 혼잡도 개선율

        **출력**: 대시보드 UI, CSV/PDF 리포트, 발표/기술 페이지
        """
    )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# =====================================================================
# 4) 핵심 기술 스택 & 의존성
# =====================================================================
with st.container(border=True):
    st.subheader("🛠 핵심 기술")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            **데이터/수치**
            - pandas / numpy
            - numpy_financial (NPV)
            - geopandas / shapely
            """
        )
    with c2:
        st.markdown(
            """
            **시각화**
            - pydeck (지도)
            - Altair (기본 차트)
            - Matplotlib/Plotly (옵션)
            """
        )
    with c3:
        st.markdown(
            """
            **앱/엔진**
            - Streamlit 멀티페이지
            - 캐시(`st.cache_data`), 세션 상태
            - 파일 인코딩/엔진 폴백(pyogrio/fiona)
            """
        )

with st.container(border=True):
    st.subheader("📦 requirements (요약)")
    st.code(
        """
        streamlit
        pandas
        numpy
        numpy-financial
        altair
        pydeck
        geopandas
        shapely
        fiona
        pyogrio
        """,
        language="text",
    )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# =====================================================================
# 5) 성능·신뢰성 전략
# =====================================================================
with st.container(border=True):
    st.subheader("⚡ 성능/신뢰성")
    st.markdown(
        """
        - **캐시**: CSV/조인/근접검색 결과 `st.cache_data` 로 재사용.
        - **강인한 SHP 로딩**: pyogrio→fiona, utf-8→cp949→euc-kr 순차 시도.
        - **유효성 체크**: 숫자 파싱(%, 쉼표, 층수 등) 및 0/결측치 필터.
        - **폴백 설계**: Altair 실패 시 Matplotlib/Plotly로 대체 가능.
        - **단위 정합성 주의**: 분양가/공사비(만원/㎡) ↔ 억원 환산 스케일 점검.
        """
    )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# =====================================================================
# 6) 향후 고도화 로드맵
# =====================================================================
with st.container(border=True):
    st.subheader("🚀 향후 고도화")
    st.markdown(
        """
        - **실시간 AIoT 연동**: 교통센서/버스혼잡 API → 시간별 자동 업데이트
        - **고급 교통모형**: OD 기반 시뮬레이션, 신호주기/버스증편 최적화
        - **KPI 확장**: 민원리스크/접근성 지수/환경영향 포함
        - **권한/버전관리**: 사용자 역할별 보기, 설정 템플릿 저장
        - **배포**: Docker/CloudRun, 데이터 캐시 레이어(Parquet/Feather)
        """
    )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# =====================================================================
# 7) 기술 문서 다운로드
# =====================================================================
with st.container(border=True):
    st.subheader("⬇️ 기술 문서(.md) 다운로드")
    md = """
# 기술 문서 (요약)

## 아키텍처
사용자 → app.py → components → pages → utils → data

## 핵심 코드
- traffic_preproc: Excel 레이아웃 자동탐지, long CSV 표준화, link_id 통일
- traffic_plot: SHP 견고 로딩, 반경 필터, 시간대 속도 차트(Altair/MPL/Plotly)
- app.py: 후보지 좌표 매칭, 테이블 필터, CFI 계산(가중/soft)

## 파이프라인
원천데이터 → 전처리(스키마/Excel→CSV/좌표계) → 근접검색 → 속도×교통량 결합 → CFI/KPI → 지도+차트 → 리포트

## 기술 스택
Streamlit, pandas/numpy, numpy-financial, geopandas/shapely, altair, pydeck, fiona/pyogrio

## 성능/신뢰성
캐시, 인코딩 폴백, 단위 정합성, 폴백 렌더러, 데이터 유효성 체크

## 향후 고도화
실시간 AIoT, 고급 교통모형, KPI 확장, 역할권한, Docker 배포
"""
    st.download_button("기술 문서(.md) 다운로드", data=md, file_name="tech_spec.md", mime="text/markdown")

st.caption("© AIoT 스마트 인프라 대시보드 — 핵심 기술 문서")
