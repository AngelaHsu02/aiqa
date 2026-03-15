"""
app_logger.py
─────────────────────────────────────────────────────────────────────────────
統一的 logging 工具，解決：
  1. 多人同時使用時，log 可識別 user@IP
  2. Streamlit 重渲染造成的重複 log（去重複）
  3. Exception 完整記錄 traceback
  4. 格式統一易讀、易用 grep 篩選

使用方式（在 web.py 每個使用者操作前取得 logger）：
    from app.utils.app_logger import get_user_logger
    log = get_user_logger(
        user_id = st.session_state.get("employee_id", "unknown"),
        ip      = st.session_state.get("client_ip",  "unknown"),
    )
    log.info("上傳音檔")
    log.error("轉文字失敗", exc_info=True)   # ← 自動帶 traceback
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import os
import traceback
import threading
from logging.handlers import TimedRotatingFileHandler

# ─── 設定 ───────────────────────────────────────────────────────────────────
# app_logger.py is at app/utils/app_logger.py
# go up 3 levels to reach project root: utils -> app -> project root
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR  = os.path.dirname(_THIS_DIR)
BASE_DIR  = os.path.dirname(_APP_DIR)
_LOG_DIR  = os.path.join(BASE_DIR, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")
_LOG_FORMAT = "%(asctime)s [%(levelname)-5s] [%(user)s@%(ip)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

os.makedirs(_LOG_DIR, exist_ok=True)

# ─── 去重複過濾器（同一 session 同一訊息 1 秒內只記一次）─────────────────────
_dedup_lock = threading.Lock()
_recent: dict[str, float] = {}   # key → timestamp
_DEDUP_WINDOW = 2.0               # 秒

class _DedupFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        import time
        key = f"{record.getMessage()}"
        now = time.monotonic()
        with _dedup_lock:
            last = _recent.get(key, 0)
            if now - last < _DEDUP_WINDOW:
                return False       # 過濾掉重複
            _recent[key] = now
        return True

# ─── 根 logger（只初始化一次）────────────────────────────────────────────────
def _build_root_logger() -> logging.Logger:
    logger = logging.getLogger("app")
    if logger.handlers:             # 已初始化，直接返回
        return logger

    logger.setLevel(logging.DEBUG)

    # 1) 寫檔（每天 00:00 換新檔，保留 30 天）
    file_handler = TimedRotatingFileHandler(
        _LOG_FILE,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    file_handler.addFilter(_DedupFilter())
    logger.addHandler(file_handler)

    # 2) 同步輸出到 console（保留原本的 terminal 可視性）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    console_handler.addFilter(_DedupFilter())
    logger.addHandler(console_handler)

    return logger

_root_logger = _build_root_logger()


# ─── 公開 API ─────────────────────────────────────────────────────────────────
def get_user_logger(user_id: str = "unknown", ip: str = "unknown") -> logging.LoggerAdapter:
    """
    取得帶有 user@IP 前綴的 logger adapter。
    每次呼叫都可以更新 user_id / ip（不會重建 handler）。

    範例：
        log = get_user_logger("00891", "192.168.1.10")
        log.info("開始轉文字")
        log.warning("音檔為空")
        try:
            ...
        except Exception:
            log.error("轉文字失敗", exc_info=True)   # ← 帶 traceback
    """
    adapter = logging.LoggerAdapter(
        _root_logger,
        extra={"user": user_id or "unknown", "ip": ip or "unknown"},
    )
    return adapter


def log_exception(user_id: str, ip: str, msg: str, exc: Exception):
    """
    快捷：記錄 Exception，自動附上完整 traceback。
    等同 log.error(msg, exc_info=True)。
    """
    logger = get_user_logger(user_id, ip)
    logger.error("%s | %s: %s\n%s", msg,
                 type(exc).__name__, exc,
                 traceback.format_exc())
