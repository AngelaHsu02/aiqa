import base64
import os
import streamlit as st
import urllib.parse
from urllib.parse import quote
import os
import socket

def local_path_to_download_button(path): #處理 str
    if not path or not os.path.exists(path):
        return "無檔案"

    else:
        filename = os.path.basename(path)
        filetype = filename.split('.')[-1].lower()

        # 根據副檔名決定 MIME
        mime_map = {
            "txt": "text/plain",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "mp3": "audio/mpeg",
            "wav": "audio/wav"
        }
        mime_type = mime_map.get(filetype, "application/octet-stream")

        with open(path, "rb") as f:
            content = f.read()

        b64 = base64.b64encode(content).decode()
        href = f'data:{mime_type};base64,{b64}'

        return f'<a href="{href}" download="{filename}">{filename} ⬇️</a>'

def local_path_to_http_url(path) -> str: # # 只回傳純 URL
    """本機路徑 → 純 HTTP URL 字串（供 LinkColumn 等需要純 URL 的場合使用）"""
    # File server 從專案根目錄 (BASE_DIR) serve，相對路徑必須從根目錄算
    _this = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.dirname(os.path.dirname(_this))
    host = os.environ.get("SERVER_HOST") or socket.gethostbyname(socket.gethostname())
    base_url = f"http://{host}:8503"
    rel_path = os.path.relpath(path, start=BASE_DIR)
    rel_path = rel_path.replace("\\", "/")
    rel_path = urllib.parse.quote(rel_path)
    return f"{base_url}/{rel_path}"

def local_path_to_http(path): #處理 str ## 包裝成 HTML <a>
    filename = os.path.basename(path)
    return f'<a href="{local_path_to_http_url(path)}" download target="_blank">{filename}</a>'

# --- 新增：包裝器，能同時處理 str / list / None ---
def local_paths_to_download_button(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return local_path_to_download_button(val)
    if isinstance(val, (list, tuple, set)):
        items = [p for p in val if isinstance(p, str)]
        return "<br>".join(local_path_to_download_button(p) for p in items) if items else ""
    return ""

def local_paths_to_http(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return local_path_to_http(val)
    if isinstance(val, (list, tuple, set)):
        items = [p for p in val if isinstance(p, str)]
        return "<br>".join(local_path_to_http(p) for p in items) if items else ""
    return ""

# if __name__ == "__main__":
#     path = r"D:\00890396\Desktop\Python\Audit\demo\logs\20250418_162220_1\比對結果_20250418_162234.xlsx"
#     # path = "D:\\00890396\\Desktop\\Python\\Audit\\demo\\logs\\20250418_162220_1\\比對結果_20250418_162234.xlsx"
#     print(f'http:{local_path_to_http(path)}')
