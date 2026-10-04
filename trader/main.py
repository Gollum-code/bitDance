import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import analytics, chooseStrategy, chat, market_data, tushareStaticsUploud

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 注册路由
app.include_router(chooseStrategy.router, prefix="/strategy")
app.include_router(chat.router, prefix="/chat")
app.include_router(market_data.router, prefix="/api/market", tags=["market"])
app.include_router(tushareStaticsUploud.router, tags=["tushare"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])


@app.get("/")
def read_root():
    return {"Hello": "World"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)