import pandas as pd
from datetime import datetime
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData
from vnpy.trader.database import get_database
from vnpy.trader.utility import ZoneInfo

# 读取 CSV 数据
csv_file = r"c:\Users\WangZiyu\Desktop\量化\trader\ai\tests\daily_kline.csv"
df = pd.read_csv(csv_file)

# 转换数据
bars = []
for _, row in df.iterrows():
    # 解析证券代码和交易所
    ts_code = row['ts_code']
    symbol, exchange_str = ts_code.split('.')

    # 映射交易所
    exchange_map = {
        'SH': Exchange.SSE,  # 上海证券交易所
        'SZ': Exchange.SZSE,  # 深圳证券交易所
        'BJ': Exchange.BSE,  # 北京证券交易所
        'CFX': Exchange.CFFEX,  # 中国金融期货交易所
        'SHF': Exchange.SHFE,  # 上海期货交易所
        'ZCE': Exchange.CZCE,  # 郑州商品交易所
        'DCE': Exchange.DCE,  # 大连商品交易所
        'INE': Exchange.INE,  # 上海国际能源交易中心
        'GFE': Exchange.GFEX  # 广州期货交易所
    }
    exchange = exchange_map.get(exchange_str, Exchange.SSE)

    # 解析日期 - 确保 trade_date 是字符串类型
    trade_date = str(row['trade_date'])
    dt = datetime.strptime(trade_date, "%Y%m%d")
    dt = dt.replace(tzinfo=ZoneInfo("Asia/Shanghai"))

    # 创建 BarData 对象
    bar = BarData(
        symbol=symbol,
        exchange=exchange,
        datetime=dt,
        interval=Interval.DAILY,
        volume=row['vol'],
        turnover=row['amount'],
        open_interest=0,  # Tushare 日线数据没有持仓量
        open_price=row['open'],
        high_price=row['high'],
        low_price=row['low'],
        close_price=row['close'],
        gateway_name="CSV"
    )
    bars.append(bar)

# 保存到数据库
database = get_database()
database.save_bar_data(bars)

print(f"成功导入 {len(bars)} 条 K 线数据到数据库")