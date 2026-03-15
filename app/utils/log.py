import os
from datetime import datetime, timedelta
import stat
import subprocess


# log.py is at app/utils/log.py
# go up 3 levels to reach project root: utils -> app -> project root
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR  = os.path.dirname(_THIS_DIR)
BASE_DIR  = os.path.dirname(_APP_DIR)
PROJECT_LOG_DIR = os.path.join(BASE_DIR, "data", "project_data")

# 建立受理編號專案資料夾（若尚未存在）
def init_project_log_folder(acceptance_id):
    folder_path = os.path.join(PROJECT_LOG_DIR, acceptance_id)
    os.makedirs(folder_path, exist_ok=True)
    print(folder_path)
    return folder_path

# 儲存操作日誌（附加模式）
def append_log(acceptance_id, message):
    folder_path_a = init_project_log_folder(acceptance_id)
    log_path = os.path.join(folder_path_a, "操作紀錄.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # with open(log_path, "a", encoding="utf-8") as f:
    #     f.write(f"[{timestamp}] {message}\n")

    # 🔓 強制解除唯讀再寫入
    if os.path.exists(log_path):
        os.chmod(log_path, stat.S_IWRITE)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

    # ✅ 寫完後再設回唯讀（如果你仍然要保護）
    os.chmod(log_path, stat.S_IREAD)

#設定唯讀
def write_and_protect(file_path, content_bytes):
    # 如果檔案存在，先暫時解除唯讀才能寫入
    if os.path.exists(file_path):
        os.chmod(file_path, stat.S_IWRITE)
    with open(file_path, "wb") as f:
        f.write(content_bytes)
    # 設為唯讀，防止未來被修改
    os.chmod(file_path, stat.S_IREAD)
    # # 不可刪除
    # subprocess.run([
    #     "icacls", file_path,
    #     "/inheritance:r",  # 取消繼承
    #     "/grant:r", "Users:R",  # 給「使用者」只讀權限
    # ], shell=True)

# ✅ 只做「唯讀 + 防刪除」的權限保護，不寫入內容（用於日誌 log）
def protect_file(file_path):
    if not os.path.exists(file_path):
        return
    os.chmod(file_path, stat.S_IREAD)  # 設定唯讀
    # # 不可刪除
    # subprocess.run([
    #     "icacls", file_path,
    #     "/inheritance:r",
    #     "/grant:r", "Users:R",     # 只讀權限
    # ], shell=True)

# if __name__ == "__main__":
#     acceptance_id = "2025005"
#     folder_path = init_project_log_folder(acceptance_id)
#     log_keywords_path = os.path.join(folder_path,"testkw2.xlsx")
#     uploaded_keywords = r"D:\00890396\Desktop\Python\質檢\demo\關鍵字\testkw2.xlsx"
#     with open(uploaded_keywords, "rb") as f:
#         content = f.read()
#     write_and_protect(log_keywords_path, content)
#     append_log(acceptance_id, f"上傳關鍵字：{log_keywords_path}")
#     log_path = os.path.join(init_project_log_folder("2025005"), "操作紀錄.log")
