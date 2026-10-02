import os

# AI 问答 API Key（Kimi / Moonshot）
# 通过环境变量 MOONSHOT_API_KEY 注入，避免把真实 key 提交到仓库
token = os.environ.get("MOONSHOT_API_KEY", "")

kimi_url = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
