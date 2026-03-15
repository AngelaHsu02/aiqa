import pandas as pd
import numpy as np
import os
import re
import unicodedata
from datetime import datetime

def exceltodict(keyword_path):
    sheets_dict = {}
    xls = pd.ExcelFile(keyword_path)

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df.columns = [col.strip() for col in df.columns]  # 修正欄位名稱，防止空格

            # 檢查是否有必要的欄位
            if 'TOPIC' not in df.columns or 'KEYWORD' not in df.columns:
                print(f"[SKIP] Sheet '{sheet_name}': Missing TOPIC or KEYWORD columns")
                continue

            # 檢查是否有資料
            if df.empty:
                print(f"[SKIP] Sheet '{sheet_name}': No data")
                continue

            keywords_dict = {}

            for _, row in df.iterrows():
                topic = str(row["TOPIC"]).strip()
                keyword = str(row["KEYWORD"]).strip()

                # 跳過空值
                if topic == 'nan' or keyword == 'nan' or not topic or not keyword:
                    continue

                if topic not in keywords_dict:
                    keywords_dict[topic] = []
                keywords_dict[topic].append(keyword)

            # 只有當有有效關鍵字時才加入
            if keywords_dict:
                sheets_dict[sheet_name] = keywords_dict
                print(f"[OK] Loaded sheet '{sheet_name}': {len(keywords_dict)} topics")

        except Exception as e:
            print(f"[ERROR] Skipping sheet '{sheet_name}': {e}")
            continue

    return sheets_dict


def run_callcompliance(transcript_paths, keyword_path, debug=False):
    sheets_dict = exceltodict(keyword_path)
    results_list = []  # 儲存所有匹配結果

    # for root, _, files in os.walk(transcript_path):  # 遞迴掃描所有目錄
    #     for filename in files:
    #         if filename.endswith(".txt"):
    #             file_path = os.path.join(root, filename)  # 獲取完整路徑
    #             relative_path = os.path.relpath(file_path, transcript_path)  # 取得相對於根目錄的路徑
    for file_path in transcript_paths:
        print(f"file_path:{file_path}")
        if not os.path.isfile(file_path) or not file_path.endswith(".txt"):
            continue  # 跳過不存在或非 txt 檔
        filename = os.path.basename(file_path)
        original_lines = []  # 存儲原始內容

        # 初始化關鍵字匹配標記 (針對每個關鍵字的匹配情況)
        keyword_found = {}
        for sheet_name, keywords_dict in sheets_dict.items():
            for topic, keywords in keywords_dict.items():
                for keyword in keywords:
                    keyword_found[(sheet_name, topic, keyword)] = False  # 預設關鍵字未匹配

        # 讀取 txt 文件
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, start=1):
                original_lines.append(line)  # 存儲原始行
                modified_line = line.strip()#sanitize_text(line)

                for sheet_name, keywords_dict in sheets_dict.items():
                    for topic, keywords in keywords_dict.items():
                        for keyword in keywords:
                            if keyword in modified_line:
                                results_list.append({
                                    "來源": sheet_name,
                                    "角色":topic,
                                    "關鍵字": keyword,
                                    "逐字稿名稱": filename,
                                    "比對行數": line_num,
                                    "逐字稿時間": modified_line,
                                    "檔案": file_path})
                                keyword_found[(sheet_name, topic, keyword)] = True# 標記關鍵字已匹配

        for (sheet_name, topic, keyword), found in keyword_found.items():
            if not found:  # 若該關鍵字未匹配
                results_list.append({
                    "來源": sheet_name,
                    "角色":topic,
                    "關鍵字": keyword,
                    "逐字稿名稱": filename,
                    "比對行數": "空值",
                    "逐字稿時間": "空值",
                    "檔案": file_path
                        })
    # 轉換結果為 DataFrame
    if not results_list:
        # 如果沒有任何結果，創建一個空的 DataFrame 但包含所有必要的欄位
        print("[WARNING] No matching results found. Creating empty DataFrame.")
        df_results = pd.DataFrame(columns=["來源", "角色", "關鍵字", "逐字稿名稱", "比對行數", "逐字稿時間", "檔案", "是否比對到"])
    else:
        df_results = pd.DataFrame(results_list)
        # 新增'是否比對到'欄位
        df_results["是否比對到"] = np.where((df_results["比對行數"] == "空值") & (df_results["逐字稿時間"] == "空值"),"否","是")

    return df_results



# if __name__ == "__main__":
#     keyword_path = r'D:\00890396\Desktop\Python\Audit\demo\keywords_服中.xlsx'
#     transcript_path = r'D:\00890396\Desktop\Python\Audit\code\STT_try1\直效'
#     df_results = run_callcompliance(transcript_path, keyword_path)
#     print(df_results)
