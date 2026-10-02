from io import StringIO

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from routers.tushare_bars import bars_from_tushare_daily_df, save_bars_to_database

router = APIRouter()


@router.post("/upload/csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    上传 CSV 文件并导入到 vnpy 数据库

    Args:
        file: 上传的 CSV 文件（tushare 格式）

    Returns:
        导入结果信息
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持 CSV 文件")

    try:
        content = await file.read()
        csv_content = content.decode("utf-8")
        df = pd.read_csv(StringIO(csv_content))
        bars = bars_from_tushare_daily_df(df, gateway_name="CSV")
        count = save_bars_to_database(bars)

        return {
            "status": "success",
            "filename": file.filename,
            "imported_count": count,
            "message": f"成功导入 {count} 条 K 线数据到数据库",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}") from e
