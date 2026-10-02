import os
import tushare as ts

token = os.getenv("TUSHARE_TOKEN", "")
if not token:
    raise SystemExit("请设置 TUSHARE_TOKEN 环境变量")

pro = ts.pro_api(token)

url = os.getenv("TUSHARE_HTTP_URL", "")
if url:
    pro._DataApi__http_url = url

print("tushare token 已配置，可调用 pro 接口")