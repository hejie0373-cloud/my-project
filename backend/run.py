"""
一键启动后端服务
右键 → Run 'run' 即可启动，Ctrl+C 停止
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8009,
        reload=True,          # 代码改动自动重启
        log_level="info",
    )
