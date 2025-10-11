# pages/7_활용 및 확장계획.py
# 🚀 AIoT 스마트 인프라 대시보드 — 활용 및 확장 계획

from __future__ import annotations
from pathlib import Path
import json
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(page_title="활용 및 확장 계획 | AIoT 스마트 인프라 대시보드", layout="wide")

# ────────────────────────────────────────────────────────────────
# 공통 스타일
# ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.katex-display { text-align: left !important; margin-left: 0 !important; }
.block-container { text-align: left !important; }
div[data-testid="stMarkdownContainer"] .katex-display { text-align: left !important; margin-left: 0 !important; margin-right: auto !important; }
div[data-testid="stMarkdownContainer"] .katex-display > .katex { display: inline-block !important; }
.small-muted { color: #7a7a7a; font-size: 0.9rem; }
.kpi-card { padding: 16px; border-radius: 16px; background: #111827; border: 1px solid #1f2937; }
.kpi-title { font-size: 0.9rem; color: #9ca3af; margin-bottom: 6px; }
.kpi-value { font-size: 1.2rem; font-weight: 700; color: #e5e7eb; }
.section-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; }
hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────
# 헤더 & 요약
# ────────────────────────────────────────────────────────────────
st.title("🚀 활용 및 확장 계획")
st.caption("현업 활용 시나리오 정리와 함께, AI 연계 · 데이터 확장 · UI 개선 · 협업/배포 로드맵을 정리합니다.")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>AI 연계</div><div class='kpi-value'>정책요약·시뮬</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>데이터 확장</div><div class='kpi-value'>버스·혼잡예보</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>UI 개선</div><div class='kpi-value'>범례·분석범위</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>협업/배포</div><div class='kpi-value'>Cloud·내부망</div></div>", unsafe_allow_html=True)

st.divider()

# ────────────────────────────────────────────────────────────────
# 탭 구성
# ────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "5️⃣ 활용 시나리오",
    "확장 로드맵 (AI·데이터·UI·배포)",
    "기술 백로그",
    "마일스톤 타임라인",
    "리스크 & 대응",
    "운영/거버넌스"
])

# ----------------------------------------------------------------
# 탭1 — 활용 시나리오
# ----------------------------------------------------------------
with tab1:
    st.subheader("5️⃣ 활용 시나리오")
    st.markdown("""
- **의사결정 보조**: 정비구역 후보 비교, 주변 혼잡 영향 추정, 버스 증편/인프라 투자에 따른 KPI 변화 확인  
- **보고 자동화**: 선택된 구역별 **최종 리포트 템플릿**으로 PDF/슬라이드 생성  
- **사전협의 지원**: 지자체·교통기관과의 협의용 **증거 기반 그래프/지표** 제공  
- **모니터링**: 기준년도 대비 추세(속도→혼잡%), 사업 단계 업데이트, 공공데이터 주기 수집
    """)
    st.info("팁: [app.py]의 3-3/3-4사분면 결과와 이 페이지의 로드맵을 연동하면, '시나리오 저장→자동 보고서' 플로우를 만들 수 있습니다.")

# ----------------------------------------------------------------
# 탭2 — 확장 로드맵
# ----------------------------------------------------------------
with tab2:
    st.subheader("🧭 확장 로드맵")
    lcol, rcol = st.columns([1.2, 1])

    with lcol:
        st.markdown("### ✅ 1) AI 연계")
        st.markdown("""
- **정책 리포트 자동 요약**: 구/사업/시나리오별 핵심쟁점 요약, 근거 도표 캡션 자동 생성  
- **시뮬레이션 분석 Q&A**: *“버스 20% 증편 시 NPV≥0になる 임계 분양가?”* 등 질의응답  
- **지식베이스 연동**: 과거 심의결과/지침 PDF 임베딩 → 유사사례 비교
        """)

        st.markdown("### ✅ 2) 데이터 확장")
        st.markdown("""
- **버스 노선/배차/혼잡 예보**(도시교통공사·국가교통DB): 시간대 `w(h)` 추정 정밀화  
- **재건축 일정/인가 단계 DB**: 사업 일정·리스크 가중치 반영  
- **POI/토지이용/학교·병원 접근성**: 보행/대중교통 접근성 KPI 추가
        """)

        st.markdown("### ✅ 3) UI 개선")
        st.markdown("""
- **pydeck 색상 범례**: 절대/상대 스케일, 히스토그램 미니뷰  
- **사용자 정의 분석 범위**: 반경·다각형 ROI, 링크 포함/제외 목록  
- **리포트 빌더**: 로고·표지·요약·부록 자동 구성
        """)

        st.markdown("### ✅ 4) 협업/배포")
        st.markdown("""
- **Streamlit Cloud / 내부망** 동시 지원, SSO 연동  
- **GitHub Actions** CI/CD: 데이터 스냅샷·테스트·배포 자동화  
- **역할 기반 접근제어(RBAC)**: 보기/편집/내보내기 권한 분리
        """)

    with rcol:
        st.markdown("### 🗺 로드맵 개요 (Graphviz)")
        st.graphviz_chart("""
digraph G {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fillcolor="#111827", color="#1f2937", fontcolor="white", fontsize=10];
    subgraph cluster_ai { label="AI 연계"; a1[label="정책요약"]; a2[label="시뮬 Q&A"]; a3[label="지식베이스"]; }
    subgraph cluster_data { label="데이터 확장"; d1[label="버스·예보"]; d2[label="일정DB"]; d3[label="접근성"]; }
    subgraph cluster_ui { label="UI 개선"; u1[label="범례"]; u2[label="ROI"]; u3[label="리포트빌더"]; }
    subgraph cluster_ops { label="협업/배포"; o1[label="Cloud/내부망"]; o2[label="CI/CD"]; o3[label="RBAC"]; }
    a1->a2->a3; d1->d2->d3; u1->u2->u3; o1->o2->o3;
}
        """)

# ----------------------------------------------------------------
# 탭3 — 기술 백로그
# ----------------------------------------------------------------
with tab3:
    st.subheader("🧩 기술 백로그")

    default_backlog = [
        {"분류":"AI", "작업":"시나리오 설명 자동요약(요지·근거·한계)", "우선순위":"High", "난이도":5, "예상주":"2"},
        {"분류":"AI", "작업":"민감도/확률 Q&A 프롬프트 템플릿", "우선순위":"Medium", "난이도":3, "예상주":"1"},
        {"분류":"데이터", "작업":"버스 혼잡예보 API 어댑터", "우선순위":"High", "난이도":4, "예상주":"2"},
        {"분류":"데이터", "작업":"사업일정 크롤러 & 정규화", "우선순위":"Medium", "난이도":3, "예상주":"2"},
        {"분류":"UI", "작업":"pydeck 범례/히스토그램", "우선순위":"High", "난이도":2, "예상주":"1"},
        {"분류":"UI", "작업":"다각형 ROI 및 링크 화이트리스트", "우선순위":"Medium", "난이도":3, "예상주":"1"},
        {"분류":"배포", "작업":"GitHub Actions 파이프라인", "우선순위":"High", "난이도":2, "예상주":"1"},
        {"분류":"보안", "작업":"SSO+RBAC 연동", "우선순위":"High", "난이도":4, "예상주":"2"},
    ]
    if "roadmap_backlog" not in st.session_state:
        st.session_state.roadmap_backlog = pd.DataFrame(default_backlog)

    edited = st.data_editor(
        st.session_state.roadmap_backlog,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "분류": st.column_config.SelectboxColumn(options=["AI","데이터","UI","배포","보안","기타"]),
            "우선순위": st.column_config.SelectboxColumn(options=["High","Medium","Low"]),
            "난이도": st.column_config.NumberColumn(min_value=1, max_value=5, step=1),
            "예상주": st.column_config.TextColumn(help="예상 소요(주)")
        }
    )
    st.session_state.roadmap_backlog = edited

    # 간단 토네이도(우선순위×난이도 가중치)
    def score(row):
        base = {"High":3, "Medium":2, "Low":1}.get(row["우선순위"], 1)
        return base * float(row["난이도"])
    sc = edited.copy()
    sc["스코어"] = sc.apply(score, axis=1)
    chart = alt.Chart(sc).mark_bar().encode(
        x=alt.X("스코어:Q"),
        y=alt.Y("작업:N", sort="-x"),
        color="분류:N",
        tooltip=["분류","작업","우선순위","난이도","스코어"]
    ).properties(height=280, title="우선순위 스코어(참고)")
    st.altair_chart(chart, use_container_width=True)

    colx, coly = st.columns([1,1])
    with colx:
        if st.button("백로그 JSON 내보내기"):
            st.download_button(
                "download_backlog.json",
                data=json.dumps(edited.to_dict(orient="records"), ensure_ascii=False, indent=2),
                file_name="backlog.json",
                mime="application/json",
                use_container_width=True
            )
    with coly:
        up = st.file_uploader("백로그 JSON 불러오기", type=["json"])
        if up:
            try:
                st.session_state.roadmap_backlog = pd.DataFrame(json.load(up))
                st.success("불러오기 완료")
            except Exception as e:
                st.error(f"불러오기 실패: {e}")

# ----------------------------------------------------------------
# 탭4 — 마일스톤 타임라인
# ----------------------------------------------------------------
with tab4:
    st.subheader("📅 마일스톤 타임라인")

    # 1) 기본 DF 준비
    default_ms = pd.DataFrame([
        {"마일스톤":"M1: 기초 배포", "시작":"2025-01-01", "종료":"2025-01-31", "분류":"배포"},
        {"마일스톤":"M2: UI 범례/ROI", "시작":"2025-02-01", "종료":"2025-02-28", "분류":"UI"},
        {"마일스톤":"M3: 버스 예보 연동", "시작":"2025-03-01", "종료":"2025-03-31", "분류":"데이터"},
        {"마일스톤":"M4: AI 리포트", "시작":"2025-04-01", "종료":"2025-04-30", "분류":"AI"},
        {"마일스톤":"M5: 보안/SSO", "시작":"2025-05-01", "종료":"2025-05-31", "분류":"보안"},
    ])
    if "milestones_df" not in st.session_state:
        st.session_state.milestones_df = default_ms.copy()

    # 2) ✅ DateColumn 호환을 위해 'datetime.date' 로 변환
    ms_df = st.session_state.milestones_df.copy()
    ms_df["시작"] = pd.to_datetime(ms_df["시작"], errors="coerce").dt.date
    ms_df["종료"] = pd.to_datetime(ms_df["종료"], errors="coerce").dt.date

    # 3) 에디터
    edit_ms = st.data_editor(
        ms_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "분류": st.column_config.SelectboxColumn(options=["AI","데이터","UI","배포","보안","기타"]),
            # ✅ DateColumn 사용 (실제 데이터가 datetime.date 여야 함)
            "시작": st.column_config.DateColumn(),
            "종료": st.column_config.DateColumn(),
        }
    )

    # 4) 세션에 저장(다음 렌더링을 위해 그대로 유지)
    st.session_state.milestones_df = edit_ms.copy()

    # 5) Gantt-like 차트 렌더링을 위해 다시 pandas datetime 으로 변환
    try:
        ms = edit_ms.copy()
        ms["시작"] = pd.to_datetime(ms["시작"], errors="coerce")
        ms["종료"] = pd.to_datetime(ms["종료"], errors="coerce")
        ms = ms.dropna(subset=["시작","종료"])  # 안전장치
        ms["일수"] = (ms["종료"] - ms["시작"]).dt.days + 1

        chart = alt.Chart(ms).mark_bar().encode(
            y=alt.Y("마일스톤:N", sort=None),
            x=alt.X("시작:T", title="기간"),
            x2="종료:T",
            color="분류:N",
            tooltip=["마일스톤","분류","시작","종료","일수"]
        ).properties(height=280, title="로드맵 타임라인")
        st.altair_chart(chart, use_container_width=True)
    except Exception as e:
        st.warning(f"타임라인 렌더링 오류: {e}")

    # ----------------------------------------------------------------
    # 탭5 — 리스크 & 대응
    # ----------------------------------------------------------------
    with tab5:
        st.subheader("🛡 리스크 & 대응")
        st.markdown("""
    **1) 데이터 품질/지연**
    - 위험: API 지연·결측·단위 불일치  
    - 대응: 소스 이중화, 스키마 밸리데이션(great_expectations/ pandera), 최근 스냅샷 폴백, 품질지표 대시보드

    **2) 모델/추정 로직**
    - 위험: 과적합, 데이터 드리프트, 민감도 오설정  
    - 대응: 기준선/대안모형 병행, 드리프트 모니터링(PSI/KS), 주기적 백테스트, 파라미터 버저닝

    **3) 운영/성능**
    - 위험: 배포 실패, 과부하, 지도 렌더 지연  
    - 대응: 헬스체크·오토스케일, 캐시 레이어(st.cache_*), 대용량 레이어 샘플링, CDN 타일 캐싱

    **4) 보안·법무**
    - 위험: 개인정보/위치정보 처리, 라이선스 위반  
    - 대응: 비식별·집계, 최소권한(RBAC), 접근로그/감사, 라이선스 SBOM 관리

    **5) 재무/조직**
    - 위험: 비용 초과, 역할 공백  
    - 대응: 단계적 롤아웃, 예산 게이트, RACI 명시, 공급업체 백업
    """)

        # 선택형: 간단 리스크 레지스터 편집기
        default_risks = pd.DataFrame([
            {"리스크": "데이터 지연", "영향": "High", "가능성": "Medium", "대응": "스냅샷 폴백/알림"},
            {"리스크": "지도 성능", "영향": "Medium", "가능성": "Medium", "대응": "샘플링/캐시"},
            {"리스크": "모델 드리프트", "영향": "High", "가능성": "Low", "대응": "주기 백테스트"},
        ])
        if "risk_df" not in st.session_state:
            st.session_state.risk_df = default_risks

        st.markdown("#### 리스크 레지스터")
        st.session_state.risk_df = st.data_editor(
            st.session_state.risk_df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "영향": st.column_config.SelectboxColumn(options=["High", "Medium", "Low"]),
                "가능성": st.column_config.SelectboxColumn(options=["High", "Medium", "Low"]),
            }
        )

    # ----------------------------------------------------------------
    # 탭6 — 운영/거버넌스
    # ----------------------------------------------------------------
    with tab6:
        st.subheader("🏛 운영/거버넌스")
        st.markdown("""
    **의사결정 체계**
    - SteerCo(월1): 전략/예산, KPI 리뷰  
    - WG(주1): 기능·데이터 우선순위, 릴리즈 플랜  
    - On-call(상시): 장애 대응, RTO/RPO

    **변경관리**
    - RFC → 승인 → 릴리즈 노트 → 롤백 시나리오  
    - 데이터 스키마 변경은 마이그레이션 스크립트 필수

    **보안·권한**
    - SSO 연동, RBAC(보기/편집/내보내기)  
    - 비밀관리(예: Vault), 접근로그 및 감사 트레일

    **지표/운영 리뷰**
    - 제품 KPI(채택률·세션·보고서 생성량)  
    - 데이터 KPI(지연·결측률·검증 실패율)  
    - 모델 KPI(MAPE/드리프트·재학습 주기)
    """)

        # 선택형: RACI 매트릭스 편집기
        default_raci = pd.DataFrame([
            {"업무": "데이터 파이프라인", "R": "Data Eng", "A": "Platform Lead", "C": "Product", "I": "SteerCo"},
            {"업무": "모델 개선", "R": "Data Sci", "A": "Product Lead", "C": "Domain Expert", "I": "SteerCo"},
            {"업무": "배포/인프라", "R": "Platform", "A": "CTO/IT", "C": "Security", "I": "All"},
        ])
        if "raci_df" not in st.session_state:
            st.session_state.raci_df = default_raci

        st.markdown("#### RACI 매트릭스")
        st.session_state.raci_df = st.data_editor(
            st.session_state.raci_df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "R": st.column_config.TextColumn(help="Responsible"),
                "A": st.column_config.TextColumn(help="Accountable"),
                "C": st.column_config.TextColumn(help="Consulted"),
                "I": st.column_config.TextColumn(help="Informed"),
            }
        )


