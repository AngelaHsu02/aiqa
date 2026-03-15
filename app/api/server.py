from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.utils.lockfile import if_release_lock_holder, LOCK_FILE
import socket, os, json

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

LOCAL_IP = get_local_ip()
print(f"release_lock API啟動於IP：{LOCAL_IP}")

app = FastAPI()

# ✅ 正確的 CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ #前端網址
        f"http://{LOCAL_IP}:8501",
        "http://localhost:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/release_lock")
async def release_lock(request: Request):
    raw = await request.body()
    data = {}
    try:
        if raw:
            data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        print(f"[api] JSON parse failed: {e}. raw={raw!r}")


    print(f"📬 收到請求：{data}")
    current_user = data.get("current_user")

    if current_user:
        lock_released = if_release_lock_holder(current_user)
        return {
            "status": "success" if lock_released else "failed",
            "current_user": current_user,
            "message": "鎖已釋放" if lock_released else "無權釋放鎖",
            "lock_file": os.path.abspath(LOCK_FILE)
        }
    return {"status": "failed", "reason": "No userid", "lock_file": os.path.abspath(LOCK_FILE)}

print("✅ FastAPI 啟動完成，準備接收釋放鎖請求")
