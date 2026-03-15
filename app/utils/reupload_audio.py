import glob, stat
import shutil
import os
import json
from datetime import datetime
from app.utils.log import append_log

def _make_writable(path: str):
    """把檔案改成可寫，避免唯讀導致無法刪除（Windows/跨平台皆可）。"""
    try:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IWRITE)  # 加上可寫權限
    except Exception:
        pass  # 不影響後續嘗試刪除

def _safe_remove(path: str, *, log_id: str) -> bool:
    """
    安全刪檔：先解除唯讀，再嘗試刪除。
    刪除成功/失敗都記錄 log，回傳是否刪除成功。
    """
    try:
        if path and os.path.isfile(path):
            _make_writable(path)       # ← 解除唯讀
            os.remove(path)
            append_log(log_id, f"刪除檔案：{path}")
            return True
        return False
    except PermissionError as e:
        append_log(log_id, f"刪除失敗（PermissionError）：{path} -> {e}")
        return False
    except Exception as e:
        append_log(log_id, f"刪除失敗（Exception）：{path} -> {e}")
        return False

def clean_project_media(project_folder: str, *, log_id: str):
    """
    刪除新專案資料夾中的音檔與逐字稿，並寫入 log。
    僅處理「資料夾內」的檔案，不會跨資料夾刪除。
    """
    if not project_folder or not os.path.isdir(project_folder):
        append_log(log_id, f"清理略過：找不到資料夾 {project_folder}")
        return

    # 依你實際會產生的格式補齊；副檔名大小寫在 Windows 不敏感，但保守起見可加大寫版
    audio_globs = ["*.wav", "*.mp3", "*.m4a", "*.mp4"]
    stt_globs   = ["*.txt", "*.json"]

    removed_count = 0

    # 刪音檔
    for pattern in audio_globs:
        for p in glob.glob(os.path.join(project_folder, pattern)):
            if _safe_remove(p, log_id=log_id):
                removed_count += 1

    # 刪逐字稿 (找根目錄以及「逐字稿」子資料夾)
    transcript_folder = os.path.join(project_folder, "逐字稿")
    folders_to_clean = [project_folder, transcript_folder] if os.path.isdir(transcript_folder) else [project_folder]

    for folder in folders_to_clean:
        for pattern in stt_globs:
            for p in glob.glob(os.path.join(folder, pattern)):
                # 如果是 meta.json 先跳過，等一下看要不要處理
                if os.path.basename(p) == "meta.json":
                    continue
                if _safe_remove(p, log_id=log_id):
                    removed_count += 1

    if removed_count == 0:
        append_log(log_id, f"清理完成：{project_folder} 無可刪除檔案")
    else:
        append_log(log_id, f"清理完成：共刪除 {removed_count} 個媒體及逐字稿檔案")
