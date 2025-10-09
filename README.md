# 🏗️ AIoT 스마트 인프라 대시보드

**목적:** 재건축 후보지의 교통 혼잡도와 사업성을 AIoT + GIS 데이터를 통해 정량적으로 분석하고, 의사결정에 활용할 수 있는 Streamlit 기반 대시보드.

---

## 📘 프로젝트 개요

* **프로젝트 이름:** AIoT Smart Infrastructure Dashboard
* **주요 목표:**

  * 서울시 재건축 대상지의 **교통 혼잡도·수익성** 분석
  * **시나리오 / 민감도 / 확률 분석**을 통한 사업성 비교
  * **데이터 기반 의사결정 지원**을 위한 직관적 시각화

---

## 🗂️ 폴더 구조

```
📦 app/
 ┣ 📜 app.py                      # 메인 실행 파일
 ┣ 📁 components/                 # 사이드바 및 부가 기능
 │  ┣ sidebar_4quadrant_guide.py  # 4사분면 가이드
 │  ┗ sidebar_presets.py          # 프리셋 설정 기능
 ┣ 📁 pages/                      # Streamlit 페이지 구성
 │  ┣ 1_FAQ.py
 │  ┣ 2_재건축이란.py
 │  ┣ 3_재건축_참여_가이드.py
 │  ┣ 4_4사분면 설명(탭 및 로직).py
 │  ┣ 5_4사분면 설명(공식).py
 │  ┣ 6_정리.py                   # 발표용 요약 페이지
 │  ┗ 7_기술문서.py               # 핵심 기술 및 코드 문서
 ┣ 📁 utils/                      # 유틸리티 모듈
 │  ┣ traffic_preproc.py          # 교통 데이터 전처리
 │  ┗ traffic_plot.py             # 속도 시각화 함수
 ┗ 📁 data/                       # 데이터셋 (CSV/XLSX/SHP)
```

---

## 📊 주요 데이터셋

| 파일명                           | 내용            | 용도            |
| ----------------------------- | ------------- | ------------- |
| `seoul_redev_projects.csv`    | 서울시 재건축 대상지   | 지도 및 후보지 선택   |
| `AverageSpeed_Seoul_2023.csv` | 링크별 평균 속도 데이터 | 혼잡도 산출        |
| `TrafficVolume(LINK).xlsx`    | 링크별 교통량       | CFI 계산 보조     |
| `seoul_link_lev5.5_2023.shp`  | 서울 도로망 GIS    | pydeck 지도 시각화 |

---

## 🔄 데이터 파이프라인

1. **입력 단계**: 후보지 CSV, 교통속도 Excel, 도로망 SHP 로드
2. **전처리**: Excel → CSV 자동 변환, 링크ID 표준화, 좌표계 변환
3. **근접 검색**: 중심점 주변 반경 내 링크 추출
4. **혼잡도 계산**: 속도·교통량 병합 후 CFI 산출 (가중 or soft)
5. **시각화**: pydeck 지도 + Altair 차트로 결과 표시
6. **분석**: 4사분면 구조(시나리오·민감도·확률·리포트) 기반 KPI 분석

---

## 🧩 핵심 모듈 요약

### `traffic_preproc.py`

* Excel 보고서의 시간대 헤더(`0~1시`)를 자동 탐지하여 Long CSV로 변환
* 링크ID 통일(`link_id`) 및 시간대별 평균속도 정규화

### `traffic_plot.py`

* 도로망 SHP를 EPSG:3857로 변환 → 반경 내 링크 필터링
* Altair 기반 속도 추이 그래프 + pydeck 시각화 지원

### `app.py`

* Streamlit 세션 관리, 프리셋 적용, 지도 필터 및 KPI 계산
* 혼잡빈도강도(CFI) 계산 (가중평균 / 시그모이드 soft 방식)

---

## 🧠 핵심 기술

* **프레임워크:** Streamlit (멀티페이지 구조)
* **데이터 분석:** pandas / numpy / numpy-financial
* **지리정보:** geopandas / shapely / pyogrio / fiona
* **시각화:** pydeck / Altair / Matplotlib / Plotly
* **성능:** st.cache_data, 세션 상태 관리, 인코딩 폴백

---

## ⚙️ 성능 및 신뢰성 전략

* **캐싱:** 전처리 및 근접검색 결과 캐시로 속도 개선
* **파일 인코딩 복원력:** UTF-8 → CP949 → EUC-KR 순차 시도
* **렌더러 폴백:** Altair 실패 시 Matplotlib/Plotly 자동 대체
* **단위 정합성:** 분양가/공사비(만원/㎡) → 억원 환산 일관성 유지

---

## 🚀 향후 고도화 계획

* **AIoT 실시간 데이터 연동** (교통센서/버스혼잡 API)
* **고급 교통모형** (OD 기반 시뮬레이션, 신호 최적화)
* **KPI 확장** (접근성·환경영향 포함)
* **Docker/Cloud 배포 및 사용자 권한 관리**

---

## 🧾 실행 방법

```bash
# 가상환경 생성 및 패키지 설치
pip install -r requirements.txt

# Streamlit 실행
streamlit run app.py
```

---

## 🧩 주요 의존성

```
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
```

---

## 👤 제작자

**Author:** AIoT Smart Infra Developer (Civil Engineering / Data Science)

**문의:** 프로젝트 구조 또는 기능 개선 제안은 issue로 등록해주세요.
