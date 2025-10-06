# utils/traffic_preproc.py
import re
from pathlib import Path
import pandas as pd

def _detect_layout(df0, max_scan_rows=15):
    """
    보고서형 평균속도 엑셀의 헤더 위치 자동 탐지.
    반환: (base_header_row, time_header_row, time_start_col, data_start_row)
    예) base_header_row=5, time_header_row=6, data_start_row=7
    """
    time_row = None
    time_start_col = None

    for r in range(max_scan_rows):
        row_vals = df0.iloc[r].astype(str).tolist()
        # "0~1시" 형태가 많이 있는 행을 시간헤더로 간주
        hits = [bool(re.fullmatch(r"\d{1,2}~\d{1,2}시", v.strip())) for v in row_vals]
        if sum(hits) >= 8:  # 시간대가 여러 개 존재
            time_row = r
            time_start_col = hits.index(True)
            break

    if time_row is None:
        raise ValueError("시간대 헤더 행(예: '0~1시')을 찾지 못했습니다. 파일 포맷을 확인하세요.")

    base_header_row = time_row - 1
    data_start_row = time_row + 1
    return base_header_row, time_row, time_start_col, data_start_row


def convert_average_speed_excel_to_csv(xlsx_path: Path, out_csv_path: Path) -> pd.DataFrame:
    """
    AverageSpeed(LINK).xlsx → 정규화 CSV 저장.
    출력 컬럼: [its_link_id, 시간대, 평균속도(km/h), hour]
    """
    xlsx_path = Path(xlsx_path)
    out_csv_path = Path(out_csv_path)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)

    df0 = pd.read_excel(xlsx_path, header=None)
    base_r, time_r, time_c0, data_r0 = _detect_layout(df0)

    # 헤더 구성
    base_headers = df0.iloc[base_r, :time_c0].tolist()
    time_headers = df0.iloc[time_r, time_c0:].tolist()
    headers = base_headers + time_headers

    # 데이터 영역
    data = df0.iloc[data_r0:, :len(headers)].copy()
    data.columns = [str(c).strip() for c in headers]
    data = data.dropna(how="all")

    # 링크 컬럼 찾기 (ITS LINK ID 우선)
    link_col = None
    for c in data.columns[:time_c0]:
        cu = str(c).upper()
        if ("ITS" in cu and "LINK" in cu) or cu in {"LINK_ID", "LINKID"}:
            link_col = c
            break
    if link_col is None:
        # 한글 백업
        for c in data.columns[:time_c0]:
            if "링크" in str(c):
                link_col = c
                break
    if link_col is None:
        # 최후: 첫번째 식별자 성격 컬럼
        link_col = data.columns[0]

    # 시간대 컬럼
    time_cols = [c for c in data.columns[time_c0:] if re.fullmatch(r"\d{1,2}~\d{1,2}시", str(c).strip())]

    # wide → long
    df_long = data[[link_col] + time_cols].copy()
    df_long[link_col] = df_long[link_col].astype(str).str.strip()
    df_long = df_long.melt(id_vars=[link_col], var_name="시간대", value_name="평균속도(km/h)")

    # hour(시작시각) 생성
    def to_hour_bucket(s: str):
        s = str(s)
        if "~" in s and "시" in s:
            try:
                return int(s.split("~")[0])
            except Exception:
                return None
        return None

    df_long["hour"] = df_long["시간대"].map(to_hour_bucket)
    df_long = df_long.dropna(subset=["hour"])
    df_long["hour"] = df_long["hour"].astype(int)
    df_long = df_long.rename(columns={link_col: "its_link_id"})

    # 저장
    df_long.to_csv(out_csv_path, index=False)
    return df_long


def ensure_speed_csv(xlsx_path: Path, out_csv_path: Path) -> Path:
    """
    xlsx가 있으면 CSV 생성/갱신 보장. 이미 있으면 그대로 둠.
    반환: CSV 경로
    """
    out_csv_path = Path(out_csv_path)
    if not out_csv_path.exists():
        convert_average_speed_excel_to_csv(xlsx_path, out_csv_path)
    return out_csv_path
