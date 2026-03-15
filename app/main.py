import os
import time
import signal
import subprocess
import threading
from dotenv import load_dotenv
import socket
import sys
import site
import streamlit, fastapi, uvicorn

load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))   # app\ 資料夾
BASE_DIR = os.path.dirname(APP_DIR)                    # 上一層（專案根目錄）
print(f"APP_DIR: {APP_DIR}")
print(f"BASE_DIR: {BASE_DIR}")


procs = []

# 獲取本機IP
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 嘗試連接到一個非內網 IP，不會真的發送資料，但可以取得正確的 local IP
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    return local_ip

LOCAL_IP = get_local_ip()
print(f"web啟動於IP：{LOCAL_IP}")

def popen(cmd, cwd=None):
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(cmd, cwd=cwd, shell=True, creationflags=flags)

def run_file_server():
    return popen(f"{sys.executable} -m http.server 8503", cwd=BASE_DIR)

def run_api():
    return popen(f"{sys.executable} -m uvicorn app.api.server:app --host 0.0.0.0 --port 8505", cwd=BASE_DIR)

def run_streamlit():
    return popen("streamlit run app/ui/web.py --server.port 8501", cwd=BASE_DIR)

def monitor():
    while True:
        alive = [p.poll() is None for p in procs if p]
        if not all(alive):
            break
        time.sleep(1)
    shutdown_all()

def shutdown_all():
    for p in procs:
        if not p:
            continue
        try:
            if os.name == "nt":
                os.kill(p.pid, signal.CTRL_BREAK_EVENT)
            time.sleep(0.3)
            if p.poll() is None:
                p.terminate()
            time.sleep(0.3)
            if p.poll() is None:
                p.kill()
        except Exception:
            pass

def main():
    print("=== Python 相關路徑偵測 ===")
    print("sys.executable:", sys.executable)
    print("sys.prefix:", sys.prefix)
    print("sys.base_prefix:", sys.base_prefix)
    print("sys.path:")
    for p in sys.path:
        print("   ", p)

    print("site.getsitepackages():", site.getsitepackages() if hasattr(site, "getsitepackages") else "N/A")
    print("site.USER_SITE:", site.USER_SITE)
    print("streamlit 來源:", streamlit.__file__)
    print("fastapi 來源:", fastapi.__file__)
    print("uvicorn 來源:", uvicorn.__file__)


    # 依序啟動
    fs = run_file_server(); procs.append(fs)
    api = run_api();        procs.append(api)
    web = run_streamlit();  procs.append(web)

    print(f"✅ File server: http://{LOCAL_IP}:8503")
    print(f"✅ API server : http://{LOCAL_IP}:8505")
    print(f"✅ Web app    : http://{LOCAL_IP}:8501")
    print("Ctrl+C to exit")

    t = threading.Thread(target=monitor, daemon=True)
    t.start()
    try:
        while t.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_all()

if __name__ == "__main__":
    main()
