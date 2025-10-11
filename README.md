# 🏗️ AIoT 스마트 인프라 대시보드 (Seoul Smart Infra Dashboard)

> **도시 인프라 재건축 사업의 교통영향과 AI 예측 결과를 시각화**하는 Streamlit 기반 통합 분석 플랫폼  
> *(Smart Infrastructure Dashboard for Urban Redevelopment / AIoT-driven Traffic Impact Analysis)*

---

## 📘 프로젝트 개요

서울시 재개발·재건축 구역 데이터를 기반으로  
**교통혼잡도, 버스노선, 인가단계, 토지정보** 등을 통합 분석하고,  
**AI 시뮬레이션과 시각화 기반 의사결정 보조 도구**를 제공합니다.

이 대시보드는 도시 인프라와 AIoT 데이터를 결합해 다음을 목표로 합니다.

- ✅ 교통영향 분석의 실시간화  
- ✅ 정비사업 인허가·협의 효율화  
- ✅ 정책 시뮬레이션 자동화  

---

## 🧱 시스템 구성

| 구분 | 설명 |
|------|------|
| **app.py** | 전체 대시보드 실행 메인 파일 |
| **pages/** | Streamlit 다중 페이지 구성 (1~9번 기능별 구분) |
| **utils/** | 데이터 전처리(`traffic_preproc.py`), 시각화(`traffic_plot.py`) 등 핵심 유틸 |
| **data/** | shapefile, CSV, Excel 기반 교통·사업 데이터 |
| **assets/** | 지도, 로고, 스타일 관련 이미지 및 정적 자원 |

---

## 🗂️ 페이지 구성 (Pages)

| 페이지 | 파일명 | 주요 내용 |
|--------|--------|-----------|
| 1️⃣ 프로젝트 개요 | `1_프로젝트_개요.py` | 대시보드 목적·기능 소개 |
| 2️⃣ 데이터 구조 | `2_데이터_구조.py` | 사용 데이터셋 구조와 관계 |
| 3️⃣ 분석 절차 | `3_분석_절차.py` | 전처리·연결·시각화 프로세스 |
| 4️⃣ 주요 기능 | `5_주요기능.py` | 지도, 혼잡도, 이익지표 등 핵심 대시보드 |
| 5️⃣ 데이터 흐름 | `6_데이터_흐름_및_분석_로직.py` | AIoT 분석 파이프라인 요약 |
| 6️⃣ 활용 및 확장 | `7_활용_및_확장계획.py` | AI 연계, 데이터 확장, UI 개선 로드맵 |
| 7️⃣ 핵심 기술 | `8_핵심기술.py` | 구현된 분석 알고리즘 및 기술 스택 |
| 8️⃣ 데이터 정리 | `9_데이터정리.py` | 사용 데이터셋 요약 및 출처 명시 |

---

## 🧩 주요 기술 스택

| 분류 | 사용 기술 |
|------|------------|
| **Frontend/UI** | Streamlit, Altair, pydeck, Plotly |
| **Backend/Logic** | Python 3.11+, pandas, geopandas, shapely |
| **GIS** | EPSG:5186 ↔ EPSG:4326 변환, Shapefile (Seoul Link 5.5) |
| **AI/Analytics** | 정책요약 LLM API (확장 예정), 혼잡도 예측 기반 KPI 계산 |
| **Visualization** | Altair Line Chart, pydeck Map Layer, Plotly Trend Graph |
| **Infra** | GitHub Actions, Streamlit Cloud / 내부망 배포 병행 |

---

## 🧮 데이터셋 개요

| 데이터명 | 파일명 | 출처 | 용도 |
|-----------|---------|------|------|
| 재개발·재건축 사업정보 | `seoul_redev_projects.csv` | 서울시 재개발재건축(금비씨) | 주요 구역 위치, 단계 |
| 교통 속도(엑셀) | `AverageSpeed(LINK).xlsx` | View-T | 원본 평균속도 |
| 교통 속도(CSV 변환) | `AverageSpeed(LINK)_2023.csv` | View-T | 전처리 결과 |
| 교통량 데이터 | `TrafficVolume_Seoul_2023.csv` | View-T | 노선별 혼잡도 계산 |
| 도로 링크(Shape) | `seoul_link_lev5.5_2023.{shp,shx,dbf,prj}` | View-T | 공간연결 및 반경 분석 |
| 재개발좌표(정제본) | `서울시_재개발재건축_clean_kakao.csv` | 서울시 / Kakao 변환 | x, y 좌표 기반 시각화 |

---

## 📊 주요 기능 요약

- 🗺️ **지도 기반 혼잡 분석**  
  반경 내 교통링크 추출 + 시간대별 평균속도 시각화  

- 📈 **재개발/재건축 영향 분석**  
  특정 구역 선택 → 혼잡 변화 및 예상 이익 분석  

- 🧠 **AI 기반 시나리오**  
  버스 증편, 사업지연 등 입력값에 따른 시뮬레이션 Q&A (확장 중)  

- 📑 **리포트 빌더**  
  KPI·그래프·지도·설명을 PDF로 자동 생성  

---

## ⚙️ 실행 방법



```bash

1️⃣ 의존성 설치
pip install -r requirements.txt


2️⃣ 데이터 준비

# 아래 파일들을 /data/ 폴더에 배치합니다:

seoul_redev_projects.csv

AverageSpeed(LINK)_2023.csv

seoul_link_lev5.5_2023.shp

seoul_link_lev5.5_2023.shx

seoul_link_lev5.5_2023.dbf

seoul_link_lev5.5_2023.prj

TrafficVolume_Seoul_2023.csv

서울시_재개발재건축_clean_kakao.csv

# 필요 시 전처리 스크립트를 실행하여 CSV를 생성합니다:

python utils/traffic_preproc.py

3️⃣ 앱 실행
streamlit run app/app.py

4️⃣ 브라우저에서 확인

👉 http://localhost:8501

```

### 🧠 확장 계획

| 구분 | 내용 |
|------|------|
| **AI 연계** | 정책 리포트 자동요약, Q&A형 시뮬레이션, 지식베이스 유사사례 탐색 |
| **데이터 확장** | 버스혼잡예보 API, 사업일정 DB, 접근성 지표 |
| **UI 개선** | pydeck 범례, 사용자 ROI, 리포트 빌더 |
| **운영/거버넌스** | SSO, RBAC, Streamlit Cloud·내부망 병행 배포 |


