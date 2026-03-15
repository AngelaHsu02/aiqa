import os, io, re, base64, json
from html import unescape
import streamlit as st
from app.utils.log import append_log, init_project_log_folder
from typing import Optional

def update_meta(meta_path, col, content):
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    meta[col] = content
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # ------ 內部小工具：把 reuse 的關鍵字轉為 BytesIO 物件清單（支援路徑 & data:URI） ------
def parse_reuse_keywords_to_fileobjs(value, lookup_dirs=None):                                         # 讓 Clone 可以「多檔」
    import re, base64, io, os
    out = []
    lookup_dirs = lookup_dirs or []
    items = value if isinstance(value, list) else ([value] if value else [])
    # 4) 支援href="data:...;base64,..." 在前、download="..." 在後的正則
    #    group(1) = base64 內容（允許空字串）
    #    group(2) = download 的檔名
    pat = re.compile(
        r'href\s*=\s*["\']data:[^;"\']+;base64,([^"\']*)["\']'   # 先抓 href="data:...;base64,XXXX"
        r'.*?'                                                   # 中間可有其它屬性
        r'download\s*=\s*["\']([^"\']+)["\']',                   # 再抓 download="檔名"
        flags=re.I | re.S
    )

    for it in items:
        if not it:
            continue
        # A. 檔案路徑
        if isinstance(it, str) and os.path.exists(it):
            with open(it, "rb") as f:
                bio = io.BytesIO(f.read())
            bio.name = os.path.basename(it)
            out.append(bio)
            print(f"existbio: {bio}")
            continue
        # B. data:URI 的 <a ...> 片段
        if isinstance(it, str):
            s = unescape(it)                      # 還原 HTML escape（&quot; → " 等）
            for m in pat.finditer(s):             # 允許一段字串內出現多個 <a> 片段
                b64  = (m.group(1) or "").strip()         # group(1) 可能為空（clone 的 data URI）
                name = m.group(2) or "keywords.xlsx"
                print(f"b64: {b64[:20]}")
                print(f"data URI 轉檔：{name}")
                try:
                    raw = base64.b64decode(b64)
                    bio = io.BytesIO(raw)
                    bio.name = name
                    out.append(bio)
                except Exception:
                    # 解析失敗就忽略該片段
                    pass
    print(f"out: {out}")
    return out

# --- 單位對照 ---
CODE_TO_UNIT = {"1": "服務中心", "2": "智能客服中心", "3": "直效行銷部"}
UNIT_TO_CODE = {v: k for k, v in CODE_TO_UNIT.items()}

def unit_code_from_acceptance() -> str:
    """只讀受理編號尾碼，不寫 session。"""
    acc = st.session_state.get("acceptance_id")
    if acc and "_" in acc:
        c = acc.rsplit("_", 1)[-1]
        if c in CODE_TO_UNIT:
            return c
    return "1"  # 沒有受理編號時的預設顯示

def ensure_project_folder() -> Optional[str]:
    acc = st.session_state.get("acceptance_id")
    if not acc:
        return None
    path = init_project_log_folder(acc)
    st.session_state.audio_folder = path
    return path

def write_meta_and_header(force_update_log: bool = False):
    """覆寫 meta；每個 acceptance 只寫一次 header；必要時增加「更新基本資訊」紀錄。"""
    folder = ensure_project_folder()
    if not folder:
        return

    # 以 session 的 unit_code 為唯一真值（建立前會先同步）
    code = st.session_state.get("unit_code", unit_code_from_acceptance())

    meta_path = os.path.join(folder, "meta.json")
    meta = {
        "acceptance_id": st.session_state.get("acceptance_id", ""),
        "employee_id": st.session_state.get("employee_id", ""),
        "unit_code": code,
        "unit_name": CODE_TO_UNIT.get(code, "未知"),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    acc = st.session_state.get("acceptance_id", "")
    # 每個 acceptance 的 header 只寫一次
    if st.session_state.get("log_header_written_for") != acc:
        append_log(acc, f"員工編號：{st.session_state.get('employee_id','')}")
        append_log(acc, f"受理編號：{acc}")
        st.session_state["log_header_written_for"] = acc

    if force_update_log:
        append_log(
            acc,
            f"更新基本資訊 → 員編：{st.session_state.get('employee_id','')}，"
            f"單位：{code}{CODE_TO_UNIT.get(code,'未知')}"
        )

# CODE_TO_UNIT = {"1": "服務中心", "2": "智能客服中心", "3": "直效行銷部"}
# UNIT_TO_CODE = {v: k for k, v in CODE_TO_UNIT.items()}

# def infer_unit_code_from_context() -> str:
#     """只讀取，**不**寫入 session。優先從 acceptance_id 反推，否則給預設。"""
#     acc = st.session_state.get("acceptance_id")
#     if acc and "_" in acc:
#         c = acc.rsplit("_", 1)[-1]
#         if c in CODE_TO_UNIT:
#             return c
#     # 你想要的預設代碼
#     return "1"

# def ensure_project_folder() -> str | None:
#     acc = st.session_state.get("acceptance_id")
#     if not acc:
#         return None
#     path = init_project_log_folder(acc)
#     st.session_state.audio_folder = path
#     return path

# def write_meta_and_header(force_update_log: bool = False):
#     """覆寫 meta；每個 acceptance 只寫一次 header；必要時新增一條更新紀錄。"""
#     folder = ensure_project_folder()
#     if not folder:
#         return
#     code = st.session_state.get("unit_code", infer_unit_code_from_context())
#     meta_path = os.path.join(folder, "meta.json")
#     meta = {
#         "acceptance_id": st.session_state.get("acceptance_id", ""),
#         "employee_id": st.session_state.get("employee_id", ""),
#         "unit_code": code,
#         "unit_name": CODE_TO_UNIT.get(code, "未知"),
#     }
#     with open(meta_path, "w", encoding="utf-8") as f:
#         json.dump(meta, f, ensure_ascii=False, indent=2)

#     acc = st.session_state.get("acceptance_id", "")
#     # 每個 acceptance 的 header 只寫一次
#     if st.session_state.get("log_header_written_for") != acc:
#         append_log(acc, f"員工編號：{st.session_state.get('employee_id','')}")
#         append_log(acc, f"受理編號：{acc}")
#         st.session_state["log_header_written_for"] = acc

#     if force_update_log:
#         append_log(
#             acc,
#             f"更新基本資訊 → 員編：{st.session_state.get('employee_id','')}，"
#             f"單位：{CODE_TO_UNIT.get(code,'未知')}({code})"
#         )
