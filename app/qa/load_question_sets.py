"""
動態題組載入模組
從 Excel 檔案載入固定題目和彈性題目
"""

import pandas as pd
from pathlib import Path


def load_fixed_questions(question_set_path):
    """
    載入固定題目（從 fixed sheet）

    參數:
        question_set_path: question_set_toaudit0122.xlsx 的路徑

    回傳:
        list: 包含 question_category 和 question_text 的字典列表
    """
    df = pd.read_excel(question_set_path, sheet_name='fixed')
    questions = []

    for _, row in df.iterrows():
        questions.append({
            'question_category': row['question_category'],
            'question_text': row['question_text']
        })

    return questions


def load_flexible_questions(question_set_path, audio_item_path, audio_id):
    """
    載入彈性題目（從 flexible sheet，根據 audio_id 過濾）

    參數:
        question_set_path: question_set_toaudit0122.xlsx 的路徑
        audio_item_path: audio_item_toaudit0122.xlsx 的路徑
        audio_id: 逐字稿的 id（用於查找對應的 item）

    回傳:
        list: 包含 question_category 和 question_text 的字典列表
    """
    # 1. 從 audio_item_toaudit0122.xlsx 找到對應的 item
    df_audio_item = pd.read_excel(audio_item_path)

    # ✅ 正規化傳入的 audio_id：去副檔名 + 截斷 _transcript 後綴
    normalized_id = str(audio_id).strip().lower()
    for ext in [".wav", ".mp3", ".m4a", ".flac", ".json"]:
        if normalized_id.endswith(ext):
            normalized_id = normalized_id[:-len(ext)]
            break
    if "_transcript" in normalized_id:
        normalized_id = normalized_id.split("_transcript")[0]

    # ✅ 同步正規化 Excel 的 audio_id 欄，建立比對用的暫存欄位
    def _normalize_aid(v):
        s = str(v).strip().lower()
        for ext in [".wav", ".mp3", ".m4a", ".flac"]:
            if s.endswith(ext):
                s = s[:-len(ext)]
                break
        if "_transcript" in s:
            s = s.split("_transcript")[0]
        return s

    df_audio_item["_aid_norm"] = df_audio_item["audio_id"].apply(_normalize_aid)
    matched_rows = df_audio_item[df_audio_item["_aid_norm"] == normalized_id]

    if matched_rows.empty:
        print(f"警告：找不到 audio_id={audio_id}（正規化後={normalized_id}）對應的 item，彈性題目為空")
        return []

    item = matched_rows.iloc[0]['item']
    print(f"audio_id={audio_id} 對應的 item={item}")

    # 2. 從 question_set_toaudit0122.xlsx 的 flexible sheet 載入題目
    df_flexible = pd.read_excel(question_set_path, sheet_name='flexible')

    # 3. 過濾出符合 item 的題目
    matched_questions = df_flexible[df_flexible['item'] == item]

    questions = []
    for _, row in matched_questions.iterrows():
        questions.append({
            'question_category': row['question_category'],
            'question_text': row['question_text']
        })

    return questions


def generate_answer_key(question_text, index):
    """
    從題目索引生成統一的 answer_key

    參數:
        question_text: 題目文字 (保留參數以維持介面相容性)
        index: 題目索引

    回傳:
        str: answer_key (格式: answer_{index})
    """
    index += 1
    return f'answer_{index}'


def detect_yesno_question(question_text):
    """
    檢測題目是否為是非題

    參數:
        question_text: 題目文字

    回傳:
        bool: True 表示是是非題
    """
    yesno_patterns = ['是否', '有沒有', '是不是']
    return any(pattern in question_text for pattern in yesno_patterns)


def build_dynamic_qset(question_set_path, audio_item_path, audio_id):
    """
    建立完整的動態題組（fixed + flexible）

    參數:
        question_set_path: question_set_toaudit0122.xlsx 的路徑
        audio_item_path: audio_item_toaudit0122.xlsx 的路徑
        audio_id: 逐字稿的 id

    回傳:
        list: 完整的題組，格式與原本的 qset 相同
    """
    # 1. 載入固定題目
    fixed_questions = load_fixed_questions(question_set_path)
    print(f"載入 {len(fixed_questions)} 個固定題目")

    # 2. 載入彈性題目
    flexible_questions = load_flexible_questions(question_set_path, audio_item_path, audio_id)
    print(f"載入 {len(flexible_questions)} 個彈性題目")

    # 3. 合併題目
    all_questions = fixed_questions + flexible_questions

    # 4. 轉換成完整格式（加上 question_number, answer_key 和 yesno）
    qset = []
    for idx, q in enumerate(all_questions):
        question_dict = {
            'question_number': idx + 1,  # 題號從 1 開始
            'question_category': q['question_category'],
            'question': q['question_text'],
            'answer_key': generate_answer_key(q['question_text'], idx),
            'yesno': detect_yesno_question(q['question_text'])
        }
        qset.append(question_dict)

    print(f"總共建立 {len(qset)} 個題目")
    return qset


# 測試用主程式
if __name__ == '__main__':
    # 測試載入
    qset = build_dynamic_qset(
        'question_set_toaudit0122.xlsx',
        'audio_item_toaudit0122.xlsx',
        '01.ABA00048357950-437030547--00937815833_2025-03-10_12-49'
    )

    print("\n題組內容：")
    for q in qset:
        print(f"Q{q['question_number']}. [{q['question_category']}] {q['question']} (key={q['answer_key']}, yesno={q['yesno']})")
