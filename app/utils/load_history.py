import os
import json
import streamlit as st

# load_history.py is at app/utils/load_history.py
# go up 3 levels to reach project root
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(_THIS_DIR)), "data")

UNIT_CODE_TO_NAME = {
    "1": "服務中心",
    "2": "智能客服中心",
    "3": "直效行銷部",
    "4": "未知",
}

def parse_unit_from_acceptance_id(acceptance_id: str, fallback: str = "未知") -> str:
    """從受理編號最後一碼解析單位代碼，回傳單位中文名；解析失敗回 fallback。"""
    try:
        code = str(acceptance_id).split("_")[-1]
        return UNIT_CODE_TO_NAME.get(code, fallback)
    except Exception:
        return fallback

def parse_code_from_acceptance_id(acceptance_id: str, fallback: str = "未知") -> str:
    """從受理編號最後一碼解析單位代碼，回傳單位代碼；解析失敗回 fallback。"""
    try:
        code = str(acceptance_id).split("_")[-1]
        return code
    except Exception:
        return fallback

# ✅ 自動從 logs 資料夾重建歷史紀錄
def load_history_from_logs(logs_dir=_DEFAULT_LOGS_DIR):
    history = []

    if not os.path.exists(logs_dir):
        return []

    for folder in sorted(os.listdir(logs_dir), reverse=True): #歷 logs_dir 目錄下的所有資料夾與檔案名稱
        folder_path = os.path.join(logs_dir, folder)

        if os.path.isdir(folder_path):
            employee_id = "unknown"
            acceptance_id = folder
            split_mode = False
            qa_audioitem_path = ""
            qa_question_path  = ""

            try:
                # 嘗試讀取 meta.json
                meta_path = os.path.join(folder_path, "meta.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        employee_id = meta.get("employee_id", "unknown")
                        acceptance_id = meta.get("acceptance_id", acceptance_id)
                        split_mode = meta.get("use_speaker_split", "unknown")  # 加入切角色資訊
                        qa_audioitem_path = meta.get("qa_audioitem_path", "")
                        qa_question_path  = meta.get("qa_question_path", "")
            except Exception as e:
                    print(f"❌ 無法讀取 {meta_path}: {e}")

            # 🔧 這次用「清單」收集
            audio_paths = []
            transcript_paths = []
            keyword_path = None
            result_path = None
            qa_result_path = None  # 最新質檢結果 xlsx

            # 掃描根目錄
            for file in os.listdir(folder_path):
                full = os.path.join(folder_path, file)
                if file.endswith((".mp3", ".wav")):
                    audio_paths.append(full)
                elif file.endswith((".txt")):
                    transcript_paths.append(full)
                elif "keyword" in file and file.endswith((".xlsx", ".csv")):
                    keyword_path = full
                elif "比對結果" in file and file.endswith((".xlsx", ".csv")):
                    result_path = full

            # 掃描逐字稿子資料夾（新專案結構）
            transcript_folder = os.path.join(folder_path, "逐字稿")
            if os.path.exists(transcript_folder) and os.path.isdir(transcript_folder):
                for file in os.listdir(transcript_folder):
                    full = os.path.join(transcript_folder, file)
                    if file.endswith((".txt", ".json")):
                        transcript_paths.append(full)

            # 掃描 qa_results 資料夾，找最新的 質檢結果_*.xlsx
            qa_results_folder = os.path.join(folder_path, "qa_results")
            if os.path.exists(qa_results_folder) and os.path.isdir(qa_results_folder):
                qa_xlsx_files = [
                    f for f in os.listdir(qa_results_folder)
                    if f.startswith("質檢結果_") and f.endswith(".xlsx")
                ]
                if qa_xlsx_files:
                    qa_xlsx_files.sort(reverse=True)  # 最新的排前面
                    qa_result_path = os.path.join(qa_results_folder, qa_xlsx_files[0])

            # ✅ 解析出受理單位（由受理編號最後一碼）
            unit_name = parse_unit_from_acceptance_id(acceptance_id, fallback="未知")
            unit_code = str(parse_code_from_acceptance_id(acceptance_id, fallback="4"))

            history.append({
                "專案預覽": folder_path,
                "受理編號": acceptance_id,
                "受理單位": unit_name,
                "受理單位代碼": unit_code,
                "員工編號": employee_id,
                "切角色模式": split_mode,
                "音檔路徑清單": audio_paths,
                "逐字稿路徑清單": transcript_paths,
                "關鍵字路徑": keyword_path,
                "比對結果路徑": result_path,
                "題組路徑清單": [p for p in [qa_audioitem_path, qa_question_path] if p],
                "質檢結果路徑": qa_result_path,
            })

    return history
