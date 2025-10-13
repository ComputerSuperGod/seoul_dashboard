# utils/traffic_preproc.py
from __future__ import annotations
from pathlib import Path

__all__ = ["ensure_speed_csv", "convert_average_speed_excel_to_csv"]

def ensure_speed_csv(xlsx_path, out_csv_path) -> str:
    """
    평균속도 CSV(out_csv_path)가 없으면 생성하고, 경로 문자열을 반환합니다.
    - 외부 라이브러리 임포트나 I/O는 함수 내부에서만 수행됩니다.
    """
    p = Path(out_csv_path)
    if not p.exists():
        convert_average_speed_excel_to_csv(xlsx_path, out_csv_path)
    return str(p)


def convert_average_speed_excel_to_csv(xlsx_path, out_csv_path) -> str:
    """
    엑셀(xlsx)을 매우 단순한 규칙으로 CSV(long)로 변환합니다.
    - 헤더 탐지 로직을 최소화해, import 실패 원인을 제거
    - 필요시 이 함수를 이후에 고도화하세요.
    최종 컬럼: link_id, 시간대, 평균속도(km/h), hour
    """
    # 외부 라이브러리 임포트는 여기서만 수행 (import 단계 실패 방지)
    import re
    import pandas as pd

    df0 = pd.read_excel(xlsx_path, header=None)

    # 헤더 행(시간대) 후보 탐색: "~" 포함 셀 다수인 첫 행
    header_row = None
    for i in range(min(len(df0), 200)):
        row = df0.iloc[i].astype(str)
        if (row.str.contains("~").sum() >= 2):
            header_row = i
            break
    if header_row is None:
        raise ValueError("시간대 헤더 행을 찾지 못했습니다. (예: '0~1시')")

    # 컬럼 이름 세팅
    df = df0.copy()
    df.columns = df.iloc[header_row].astype(str).tolist()
    df = df.drop(index=list(range(header_row + 1)))  # 헤더 아래부터 데이터로 가정

    # 첫 컬럼을 link_id로 간주
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "link_id"})

    # wide -> long
    value_cols = [c for c in df.columns if c != "link_id"]
    df_long = df.melt(id_vars=["link_id"], value_vars=value_cols,
                      var_name="시간대", value_name="평균속도(km/h)")

    # 시간대 → hour (예: "0~1시" → 0)
    def to_hour_bucket(s: str):
        s = str(s)
        m = re.match(r"^\s*(\d{1,2})\s*~", s)
        return int(m.group(1)) if m else None

    df_long["hour"] = df_long["시간대"].map(to_hour_bucket)
    df_long = df_long.dropna(subset=["hour"]).copy()
    df_long["hour"] = df_long["hour"].astype(int)

    # 저장
    out_path = Path(out_csv_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_long.to_csv(out_path, index=False, encoding="utf-8")
    return str(out_path)
