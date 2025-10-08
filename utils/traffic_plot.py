# utils/traffic_plot.py
# ---------------------------------------------------------------------
# 교통 속도 시각화 유틸: Altair 기본(대시보드용), Matplotlib/Plotly 옵션 제공
# - get_nearby_speed_data: 시각화용 데이터 준비
# - altair_nearby_speed: Altair 차트 생성 (기본)
# - plot_speed: renderer 스위치('altair' | 'mpl' | 'plotly')
# - (호환) plot_nearby_speed_from_csv: 기존 함수 유지
# ---------------------------------------------------------------------

from typing import Union, Tuple
from pathlib import Path
import platform
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# Matplotlib(옵션 렌더러 및 폰트 설정용)
import matplotlib
import matplotlib.pyplot as plt

# Altair(기본 렌더러)
import altair as alt


# ---------------------------------------------------------------------
# 한글 폰트 설정(주로 Matplotlib용) + 마이너스 기호 깨짐 방지
# ---------------------------------------------------------------------
def _use_korean_font():
    """OS별 기본 한글 폰트 적용 + 마이너스 기호 깨짐 방지"""
    sysname = platform.system()
    if sysname == "Windows":
        font_name = "Malgun Gothic"
    elif sysname == "Darwin":
        font_name = "AppleGothic"
    else:
        # 리눅스 서버: 설치 여부를 확인하고 대체 폰트 지정
        try:
            import matplotlib.font_manager as fm
            names = {f.name for f in fm.fontManager.ttflist}
            if "NanumGothic" in names:
                font_name = "NanumGothic"
            elif "Noto Sans CJK KR" in names:
                font_name = "Noto Sans CJK KR"
            else:
                font_name = "DejaVu Sans"
        except Exception:
            font_name = "DejaVu Sans"

    matplotlib.rcParams["font.family"] = font_name
    matplotlib.rcParams["axes.unicode_minus"] = False
    plt.rcParams.update({"font.family": font_name})


# ---------------------------------------------------------------------
# Matplotlib 대시보드용 테마(옵션)
# ---------------------------------------------------------------------
def set_dashboard_theme():
    """대시보드용 Matplotlib 테마(밝은 배경, 얇은 점선 그리드, 라운드 캡 등)"""
    _use_korean_font()
    matplotlib.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.titleweight": "bold",
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.grid": True,
            "grid.linestyle": "--",
            "grid.alpha": 0.35,
            "grid.linewidth": 0.7,
            "lines.linewidth": 2.2,
            "lines.antialiased": True,
            "lines.solid_capstyle": "round",
            "lines.markersize": 5,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "figure.autolayout": True,
        }
    )


# ---------------------------------------------------------------------
# Shapefile 로더(인코딩/엔진 문제에 견고)
# ---------------------------------------------------------------------
def _read_shp_robust(shp_path: Union[str, Path]) -> gpd.GeoDataFrame:
    """
    Shapefile 인코딩/엔진 문제를 견고하게 처리:
    1) pyogrio + utf-8
    2) pyogrio + cp949
    3) pyogrio + euc-kr
    4) pyogrio + cp949 (encoding_errors='ignore')
    5) pyogrio + utf-8 (encoding_errors='ignore')
    6) fiona + utf-8
    7) fiona + cp949
    8) fiona + euc-kr
    """
    shp_path = Path(shp_path)
    tries = [
        ("pyogrio", "utf-8", {}),
        ("pyogrio", "cp949", {}),
        ("pyogrio", "euc-kr", {}),
        ("pyogrio", "cp949", {"encoding_errors": "ignore"}),
        ("pyogrio", "utf-8", {"encoding_errors": "ignore"}),
        ("fiona", "utf-8", {}),
        ("fiona", "cp949", {}),
        ("fiona", "euc-kr", {}),
    ]
    errors = []
    for engine, enc, extra in tries:
        try:
            return gpd.read_file(shp_path, engine=engine, encoding=enc, **extra)
        except Exception as e:
            errors.append(
                f"{engine}/{enc}{' ' + str(extra) if extra else ''} -> {e.__class__.__name__}: {e}"
            )

    raise RuntimeError(
        "Shapefile 읽기 실패.\n"
        "다음 조합을 모두 시도했으나 실패했습니다:\n- "
        + "\n- ".join(errors)
        + "\n\n해결책:\n"
          "1) SHP 옆에 '.cpg' 파일을 만들고 내용에 CP949 또는 UTF-8을 명시\n"
          "2) .shp/.shx/.dbf/.prj 4개가 모두 있는지 확인\n"
          "3) fiona/pyogrio 버전을 업데이트\n"
    )


# ---------------------------------------------------------------------
# 데이터 로더 (CSV의 id 컬럼 자동 인식)
# ---------------------------------------------------------------------
def load_speed_long_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # ✅ 항상 link_id 기준으로 통일
    if "its_link_id" in df.columns and "link_id" not in df.columns:
        df = df.rename(columns={"its_link_id": "link_id"})

    df["link_id"] = df["link_id"].astype(str)
    df["hour"] = df["hour"].astype(int)
    return df





# ---------------------------------------------------------------------
# 반경 내 링크들의 시간대별 평균속도 데이터 준비
# ---------------------------------------------------------------------
def get_nearby_speed_data(
        csv_path: Path,
        shp_path: Path,
        center_lon: float,
        center_lat: float,
        radius_m: int = 1000,
        max_links: int = 10,
        # 후보 리스트: 5.5(UP_LINK_ID/DW_LINK_ID) 우선, 그다음 ITS
        shp_up_id_candidates=("UP_LINK_ID", "up_link_id", "up_its_id"),
        shp_dw_id_candidates=("DW_LINK_ID", "dw_link_id", "dw_its_id"),
) -> pd.DataFrame:
    """
    CSV(link_id 또는 its_link_id, 시간대, 평균속도(km/h), hour) + 레벨6 SHP로
    반경 내 링크들의 시간대별 평균속도에 해당하는 데이터프레임 반환
    """
    gdf = _read_shp_robust(shp_path)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=5186, allow_override=True)
    gdf4326 = gdf.to_crs(epsg=4326)
    gdf3857 = gdf4326.to_crs(epsg=3857)

    center = gpd.GeoSeries([Point(center_lon, center_lat)], crs=4326).to_crs(epsg=3857).iloc[0]
    gdf3857["dist_m"] = gdf3857.distance(center)

    near = gdf3857[gdf3857["dist_m"] <= radius_m].copy()
    if near.empty:
        near = gdf3857.sort_values("dist_m").head(50).copy()

    # ── CSV 헤더를 먼저 확인하여 어떤 ID(5.5 vs ITS)를 쓰는지 결정
    # 반경 내 ID 수집 유틸 (여러 후보 컬럼을 한 번에 모아 집합으로)
    def collect_ids(df, cols):
        import pandas as pd
        s_list = []
        for c in cols:
            if c in df.columns:
                s_list.append(df[c])
        if not s_list:
            return set()
        s = pd.concat(s_list, ignore_index=True)
        s = s.dropna().astype(str).str.strip()
        s = s[~s.isin(["0", "-1", "", "nan", "None"])]
        return set(s.tolist())

    # ── 5.5 SHP 기준으로 링크 집합 만들기
    # 우선순위: k_link_id -> link_id -> LINK_ID
    id_col_55 = next((c for c in ["k_link_id", "link_id", "LINK_ID"] if c in gdf3857.columns), None)
    if id_col_55 is None:
        raise RuntimeError(f"SHP에서 5.5 링크ID 컬럼(k_link_id/link_id/LINK_ID)을 찾지 못했습니다. (cols={list(gdf3857.columns)})")

    # 반경 내 피처만 추출(이미 near에 담김)
    ids = near[id_col_55].dropna()

    # 값이 8891093.0 같은 float일 수 있으니 안전하게 문자열 ID로 표준화
    if pd.api.types.is_float_dtype(ids) or ids.dtype.kind in "fc":
        ids = ids.round().astype("Int64").astype(str)
    else:
        ids = ids.astype(str).str.replace(r"\.0$", "", regex=True)

    # 0/-1/빈값 제거
    ids = ids[~ids.isin(["0", "-1", "", "nan", "None"])]

    link_set = set(ids.tolist())

    # CSV 로드 (이 함수가 its_link_id를 link_id로 표준화함)
    speed = load_speed_long_csv(csv_path)  # -> speed['link_id'] (str)

    # 매칭
    df_plot = speed[speed["link_id"].isin(link_set)].copy()
    if df_plot.empty:
        return df_plot

    # 상위 N개 링크만
    keep = df_plot["link_id"].value_counts().head(max_links).index
    df_plot = df_plot[df_plot["link_id"].isin(keep)].copy()
    df_plot = df_plot.sort_values(["link_id", "hour"])
    return df_plot


# ---------------------------------------------------------------------
# Altair 차트(기본)
# ---------------------------------------------------------------------
def altair_nearby_speed(df_plot: pd.DataFrame, height: int = 800):
    if df_plot.empty:
        return (
            alt.Chart(pd.DataFrame({"msg": ["반경 내 속도 데이터가 없습니다."]}))
            .mark_text(size=14)
            .encode(text="msg:N")
            .properties(height=height)
        )

    # 표준화된 'link_id' 컬럼 사용 (없으면 its_link_id로 fallback)
    id_col = "link_id" if "link_id" in df_plot.columns else "its_link_id"

    selection = alt.selection_point(fields=[id_col], bind="legend")

    chart = (
        alt.Chart(df_plot)
        .mark_line(point=True)
        .encode(
            x=alt.X("hour:Q", title="시간대 시작 시각 (시)"),
            y=alt.Y("평균속도(km/h):Q", title="평균속도 (km/h)"),
            color=alt.Color(f"{id_col}:N", title="링크"),  # ✅ 이 부분에서 id_col 사용
            opacity=alt.condition(selection, alt.value(1.0), alt.value(0.25)),
            tooltip=[
                alt.Tooltip(f"{id_col}:N", title="링크"),
                alt.Tooltip("hour:Q", title="시"),
                alt.Tooltip("평균속도(km/h):Q", title="속도(km/h)", format=".1f"),
            ],
        )
        .add_params(selection)
        .properties(title="주변 링크 시간대별 평균속도", width="container", height=height)
        .configure_view(strokeWidth=0, continuousHeight=height, discreteHeight=height)
        .configure_axis(labelFontSize=12, titleFontSize=12,
                        labelFontWeight="normal", titleFontWeight="bold")
        .configure_legend(orient="bottom", direction="horizontal",
                          title=None, labelFontSize=11, labelFontWeight="normal")
        .configure_title(fontWeight="bold", fontSize=14)
    )
    return chart


# ---------------------------------------------------------------------
# 공통 진입점: renderer 스위치
# ---------------------------------------------------------------------
def plot_speed(
    csv_path: Path,
    shp_path: Path,
    center_lon: float,
    center_lat: float,
    radius_m: int = 1000,
    max_links: int = 10,
    renderer: str = "altair",
    chart_height: int = 800,
    shp_up_id_candidates=("UP_LINK_ID", "up_link_id", "up_its_id"),
    shp_dw_id_candidates=("DW_LINK_ID", "dw_link_id", "dw_its_id"),
):
    """
    동일 데이터로 Altair/Matplotlib/Plotly 중 원하는 렌더러로 그려서 반환
    - Altair: Altair Chart 반환
    - Matplotlib/Plotly: Figure 반환
    """
    df_plot = get_nearby_speed_data(
        csv_path=csv_path,
        shp_path=shp_path,
        center_lon=center_lon,
        center_lat=center_lat,
        radius_m=radius_m,
        max_links=max_links,
        shp_up_id_candidates=shp_up_id_candidates,
        shp_dw_id_candidates=shp_dw_id_candidates,
    )

    if renderer == "altair":
        return altair_nearby_speed(df_plot, height=chart_height), df_plot

    # id 컬럼 결정(표준화 우선)
    id_col = "link_id" if "link_id" in df_plot.columns else "its_link_id"

    if renderer == "mpl":
        set_dashboard_theme()
        fig, ax = plt.subplots(figsize=(9, 5))
        if df_plot.empty:
            ax.set_title("반경 내 링크에 대응하는 속도 데이터가 없습니다.")
            return fig, df_plot
        for lid, sub in df_plot.groupby(id_col):
            ax.plot(sub["hour"], sub["평균속도(km/h)"], marker="o", label=str(lid))
        ax.set_xlabel("시간대 시작 시각 (시)")
        ax.set_ylabel("평균속도 (km/h)")
        ax.set_title("주변 링크 시간대별 평균속도")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4)
        ax.grid(True)
        return fig, df_plot

    elif renderer == "plotly":
        import plotly.express as px
        if df_plot.empty:
            import plotly.graph_objects as go
            fig = go.Figure().update_layout(
                title="반경 내 링크에 대응하는 속도 데이터가 없습니다."
            )
            return fig, df_plot
        fig = px.line(
            df_plot,
            x="hour",
            y="평균속도(km/h)",
            color=id_col,
            markers=True,
            labels={
                "hour": "시간대 시작 시각 (시)",
                id_col: "링크",
                "평균속도(km/h)": "평균속도 (km/h)",
            },
            title="주변 링크 시간대별 평균속도",
        ).update_layout(
            template="simple_white",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=50, b=40),
            legend=dict(orientation="h", y=-0.2),
            font=dict(size=12),
        )
        fig.update_traces(line=dict(width=2.2))
        return fig, df_plot

    else:
        raise ValueError("renderer must be one of: 'altair', 'mpl', 'plotly'")


# ---------------------------------------------------------------------
# (호환) 기존 Matplotlib 함수 유지: 내부적으로 plot_speed 사용
# ---------------------------------------------------------------------
def plot_nearby_speed_from_csv(
        csv_path: Path,
        shp_path: Path,
        center_lon: float,
        center_lat: float,
        radius_m: int = 1000,
        max_links: int = 10,
):
    """
    기존 코드 호환용. Matplotlib Figure 반환.
    새 코드에선 plot_speed(..., renderer='altair') 사용 권장.
    """
    fig_or_chart, df_plot = plot_speed(
        csv_path=csv_path,
        shp_path=shp_path,
        center_lon=center_lon,
        center_lat=center_lat,
        radius_m=radius_m,
        max_links=max_links,
        renderer="mpl",
    )
    return fig_or_chart, df_plot



