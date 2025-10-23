# Repository File Audit

This document summarizes the contents of the `seoul_dashboard` repository and highlights notable implementation details for each major file.

## Top-level
- `README.md` – Provides project summary and quick-start notes.
- `requirements.txt` – Python dependencies for the Streamlit dashboard (Streamlit, pandas, geopandas, numpy-financial, etc.).
- `app/` – Streamlit application source code.
- `utils/` – Data preprocessing and visualization helpers for traffic datasets.
- `data/` – Input datasets (CSV, Excel, Shapefile components) used by the dashboard.
- `CSV기반 대시보드_1(백업용).zip`, `lev5.5_based_backup(최종).zip` – Archived backup bundles (not unpacked in repository).

## Application (`app/`)
- `app/app.py`
  - Entry point for the Streamlit dashboard.
  - Handles session state initialization, dataset path configuration, and optional caching reset from the sidebar.
  - Loads CSV/Excel traffic inputs via utilities, computes congestion metrics, and renders multiple visualization modes (Altair, Matplotlib, Plotly fallback).
- `app/components/sidebar_presets.py`
  - Defines reusable scenario presets for sidebar input fields (conservative/base/aggressive) and applies them to `st.session_state`.
- `app/components/sidebar_4quadrant_guide.py`
  - Provides descriptive guidance text for understanding the dashboard’s four-quadrant analysis.
- `app/pages/*.py`
  - Multi-page content for the dashboard (FAQ, conceptual overview, participation guide, quadrant logic/formulae, technical documentation, overall summary).
  - Each file sets up Streamlit page configuration, renders explanatory Markdown sections, and occasionally references shared sidebar navigation where available.

## Utilities (`utils/`)
- `utils/traffic_preproc.py`
  - Converts the Excel-based `AverageSpeed(LINK).xlsx` workbook into a normalized CSV with `link_id`, `hour`, and `평균속도(km/h)` columns.
  - Includes heuristics for detecting header rows and preferred link identifiers (ITS vs 5.5) along with a helper to ensure the CSV exists.
- `utils/traffic_plot.py`
  - Supplies shared plotting routines and shapefile loaders.
  - Handles geographic filtering of road links, prepares time-series speed datasets, and offers Altair/Matplotlib chart renderers with Korean font handling.

## Data (`data/`)
- `AverageSpeed(LINK).xlsx`, `AverageSpeed_Seoul_2023.csv` – Traffic speed source data and converted CSV output.
- `TrafficVolume(LINK).xlsx` – Volume data for congestion calculations.
- `seoul_redev_projects.csv` – Redevelopment project master dataset consumed by the dashboard.
- `서울시_재개발재건축_clean_kakao.csv` – Coordinate mapping for redevelopment sites.
- `seoul_link_lev5.5_2023.*` – GIS shapefile components used to map nearby links (includes `.shp`, `.shx`, `.dbf`, `.prj`).

## Observations
- `app/app.py` imports `streamlit` twice; functionality unaffected but could be cleaned up in a future revision.
- `app/pages` references an optional `components.sidebar_nav` module that is absent from the repository; pages guard against ImportError by falling back to `None`.
- Large binary data and zip files are present; ensure Git LFS or alternative storage is considered if repository size becomes an issue.

No runtime issues were detected during this review; the document is intended as a navigation aid for future contributors.
