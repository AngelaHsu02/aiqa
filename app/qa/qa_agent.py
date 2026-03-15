"""
AI 質檢代理模組
從逐字稿 JSON 檔案執行 AI 質檢，產生質檢結果

主要功能：
1. 支援 Gemini、Gemma 和 Ollama (OSS) 三種 LLM 模型
2. 將逐字稿標註為四大類（核身、申辦細節、權利義務、親簽）
3. 動態載入題組並自動作答
4. 支援單檔和批次處理
"""

import json
import os
import pathlib
import requests
import httpx
import urllib3
import google.generativeai as genai
from openai import AzureOpenAI
from dotenv import load_dotenv
from app.qa.load_question_sets import build_dynamic_qset

load_dotenv()

# ── 關閉 SSL 驗證 + 繞過公司 Proxy（與 transcribe.py 相同設定）──
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_gpt_http = httpx.Client(
    verify=False,
    mounts={"https://": None, "http://": None},  # 直連，不走 Proxy
    timeout=httpx.Timeout(connect=30.0, read=120.0, write=60.0, pool=10.0),
)


# ==================== 模型類別 ====================

class AzureGPTModel:
    """Azure OpenAI GPT 模型封裝（金鑰從 .env 讀取）"""

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_API_KEY"),
            api_version=os.getenv("AZURE_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_ENDPOINT"),
            http_client=_gpt_http,   # ✅ 繞過公司 Proxy
        )
        self.deployment = os.getenv("AZURE_DEPLOYMENT")

    def generate_content(self, prompt: str):
        """把 prompt 送出並回傳含 .text 的物件"""
        prompt_length = len(prompt)
        estimated_tokens = prompt_length // 1.5
        print(f"[DEBUG] Prompt 長度: {prompt_length} 字元, 約 {estimated_tokens:.0f} tokens")

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "你是一位嚴謹的電訪作業品質檢核專家，僅使用繁體中文工作與溝通。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_completion_tokens=4096,   # ✅ 新版 API 用 max_completion_tokens
            )
            content = response.choices[0].message.content or ""
            print(f"[DEBUG] ✅ AzureGPT API 調用成功")
            return AzureGPTResponse(content)
        except Exception as e:
            print(f"AzureGPT API 調用錯誤: {e}")
            return AzureGPTResponse("")


class AzureGPTResponse:
    """統一介面的 response 物件"""
    def __init__(self, text: str):
        self.text = text

class GemmaModel:
    """部門 VLLM 模型封裝"""

    def __init__(self, api_url: str, model_name: str, temperature: float = 0):
        self.api_url = api_url
        self.model_name = model_name
        self.temperature = temperature

    def generate_content(self, prompt: str):
        """把 prompt 包裝成 messages 格式"""
        # 檢查 prompt 長度
        prompt_length = len(prompt)
        estimated_tokens = prompt_length // 1.5  # 中文約 1.5 字元 = 1 token
        print(f"[DEBUG] Prompt 長度: {prompt_length} 字元, 約 {estimated_tokens:.0f} tokens")

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "你是一位嚴謹的電訪作業品質檢核專家，僅使用繁體中文工作與溝通。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "stream": False
        }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=300)
            response.raise_for_status()

            if response.status_code != 200:
                print(f"[ERROR] HTTP 狀態碼: {response.status_code}")
                print(f"[ERROR] 回應內容: {response.text[:500]}")

            data = response.json()
            print(f"[DEBUG] ✅ API 調用成功")

            choices = data.get("choices", [])
            if not choices:
                return GemmaResponse("")

            content = choices[0].get("message", {}).get("content", "")
            return GemmaResponse(content)

        except Exception as e:
            print(f"API 調用錯誤: {e}")
            return GemmaResponse("")


class GemmaResponse:
    """模擬 Gemini Response 物件"""
    def __init__(self, text: str):
        self.text = text


class OllamaModel:
    """地端 Ollama 模型（使用 /api/generate 端點）"""

    def __init__(self, api_url: str, model_name: str):
        self.api_url = api_url
        self.model_name = model_name

    def generate_content(self, prompt: str):
        """把 prompt 送出並回傳統一格式的 Response 物件"""
        prompt_length = len(prompt)
        estimated_tokens = prompt_length // 1.5
        print(f"[DEBUG] Prompt 長度: {prompt_length} 字元, 約 {estimated_tokens:.0f} tokens")

        payload = {
            "model": self.model_name,
            "system": "你是一位嚴謹的電訪作業品質檢核專家，僅使用繁體中文工作與溝通。",
            "prompt": prompt,
            "stream": False
        }
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=300)
            response.raise_for_status()

            if response.status_code != 200:
                print(f"[ERROR] HTTP 狀態碼: {response.status_code}")
                print(f"[ERROR] 回應內容: {response.text[:500]}")

            data = response.json()
            print(f"[DEBUG] ✅ API 調用成功")
            # Ollama /api/generate 回傳欄位為 'response'（非 choices）
            content = data.get("response", "")
            return OllamaResponse(content)

        except Exception as e:
            print(f"API 調用錯誤: {e}")
            return OllamaResponse("")


class OllamaResponse:
    """模擬 Gemini Response 物件（供 Ollama 使用）"""
    def __init__(self, text: str):
        self.text = text


# ==================== 輔助函數 ====================

def extract_json(text):
    """從文字中提取 JSON"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except Exception:
        return {}


def enrich_evidence(result_obj, seg_index):
    """補充 evidence 的 raw_timestamp 和 text"""
    for item in result_obj.get("acquired_answer", []):
        new_ev = []
        for ev in item.get("evidence", []):
            # 處理不同格式的 evidence
            if isinstance(ev, dict):
                sid_str = str(ev.get("sentence_id", "")).strip()
            elif isinstance(ev, (int, str)):
                sid_str = str(ev).strip()
            else:
                continue

            if not sid_str:
                continue
            try:
                sid_int = int(sid_str)
            except Exception:
                continue
            seg = seg_index.get(sid_int)
            if not seg:
                continue
            new_ev.append({
                "sentence_id": str(sid_int),
                "raw_timestamp": seg.get("raw_timestamp"),
                "text": seg.get("text")
            })
        item["evidence"] = new_ev
    return result_obj


def build_context_for_model(segments):
    """建立模型用的上下文（只含 sentence_id 與 text）"""
    lines = []
    for seg in segments:
        sid = seg.get("sentence_id")
        text = seg.get("text", "")
        lines.append(f"{sid}\t{text}")
    return "\n".join(lines)


# ==================== 核心函數 ====================

def label_segments_by_category(tid: str, context: str, model):
    """Gemini/Gemma 標註四大類"""
    instruction = f"""
    角色：你是一位嚴謹的電訪作業品質檢核助理。

    任務：請將逐字稿內容整理成四大類段落：核身、申辦細節、權利義務、親簽。
    - 同一類可以出現多段，請全部收集。
    - 類別不必依固定順序。
    - 盡可能擴大範圍，只要合理相關就納入。
    - text 必須原樣取自逐字稿內容，不可自行改寫。

    只回傳 JSON 物件（無其他文字），格式如下：
    {{
    "id": "{tid}",
    "sections": {{
        "核身": [
        {{"sentence_id": "數字", "text": "逐字稿原句"}}
        ],
        "申辦細節": [
        {{"sentence_id": "數字", "text": "逐字稿原句"}}
        ],
        "權利義務": [],
        "親簽": []
    }}
    }}
    """.strip()

    prompt = f"""
    任務說明：{instruction}

    逐字稿（僅 sentence_id 與 text，每行一筆，以 TAB 分隔）：{context}
    """

    response = model.generate_content(prompt)
    raw_text = (getattr(response, "text", None) or "").strip()
    return extract_json(raw_text)


def build_test_paper(tid, qset):
    """產生空白考卷"""
    return {
        "id": tid,
        "acquired_answer": [
            {
                "question_category": q["question_category"],
                "question": q["question"],
                "yesno": q.get("yesno", False),
                q["answer_key"]: "",
                "reason": "",
                "evidence": [{"sentence_id": ""}]
            }
            for q in qset
        ]
    }

def ask_one_question(transcript_json: str, answer_key: str, question_category: str,
                     question_text: str, label_json: str = "", yesno: bool = False, model=None):
  # 共用規則
  common_rules = """
    <rule id="source_only">判斷依據必須來自逐字稿。認定「有提到」的標準為「語意實質等同」：
    1. 不要求逐字相同、不要求句型相同。
    2. 若題目包含多個概念（如「提到Ａ，請評估Ｂ」），只要客服用語意表達出這幾個核心概念（例如「會有利息，請留意自身財務狀況」），即視為完全符合。
    3. 嚴禁以「未明確逐字說出ＯＯＯ」為由判定為未提到。</rule>
    <rule id="evidence">evidence 必須填入 reason 中提及的所有句子的 sentence_id（即使答案為「無法確認」或「否」）。若無句子才填空陣列。</rule>"""
  # 依題型決定答案規則
  if yesno:
      answer_rule = '<rule id="answer_format">VALUE 只能為「是」或「否」。若客服的話語「實質涵蓋」了題目要求的所有核心精神，VALUE 必須填「是」；完全沒提到或缺少核心精神才填「否」。</rule>'
  else:
      answer_rule = '<rule id="answer_format">VALUE 為簡短文字，摘錄逐字稿中的相關內容。完全找不到相關內容才填「無法確認」。</rule>'

  instruction = f"""
  <task>
    <role>電訪作業品質檢核專家</role>
    <question>{question_text}</question>
    <category>{question_category}</category>
    {answer_rule}{common_rules}
    <output>只回傳 JSON，不得有多餘文字：
    {{"VALUE": "答案", "reason": "依哪些句子得出結論", "evidence": [{{"sentence_id": 數字}}]}}
    </output>
  </task>
  """.strip()

  prompt = f"""
  任務說明：
  {instruction}

  原逐字稿 JSON：
  {transcript_json}

  逐句標註 JSON：
  {label_json}
  """

  response = model.generate_content(prompt)
  raw_text = (getattr(response, "text", None) or "").strip()
  obj = extract_json(raw_text)

  if "evidence" not in obj or not isinstance(obj.get("evidence"), list):
      obj["evidence"] = []
  value = obj.get("VALUE", None)
  obj.pop("VALUE", None)
  obj[answer_key] = value
  return obj

# def ask_one_question(transcript_json: str, answer_key: str, question_category: str,
#                      question_text: str, label_json: str = "", yesno: bool = False, model=None):
#     """單題呼叫"""
#     extra = ""
#     if yesno:
#         extra = '－此題 "VALUE" 只能為 "是"、"否"、"無法確認"\n'

#     instruction = f"""
#     角色：你是一位嚴謹的電訪作業品質檢核專家。

#     任務：根據下方逐字稿，回答單一問題：{question_text}

#     問題分類：{question_category}

#     原則：
#     －僅使用逐字稿可支持的內容；若資訊不足，請回傳 VALUE = 無法確認。
#     －evidence是字典型態，僅填出現關鍵資訊的 sentence_id（數字），可包含多筆。
#     －只回傳 JSON，不得包含多餘文字、說明、反引號或程式碼區塊。
#     {extra}
#     輸出 JSON 物件（無其他文字）：
#     {{
#     "VALUE": 值,
#     "reason": "簡要說明依哪些句子得出結論",
#     "evidence": [{{"sentence_id": 數字}}, ...]
#     }}
#     """.strip()

#     prompt = f"""
#     任務說明：
#     {instruction}

#     原逐字稿 JSON：
#     {transcript_json}

#     逐句標註 JSON：
#     {label_json}
#     """

#     response = model.generate_content(prompt)
#     raw_text = (getattr(response, "text", None) or "").strip()
#     obj = extract_json(raw_text)

#     if "evidence" not in obj or not isinstance(obj.get("evidence"), list):
#         obj["evidence"] = []
#     value = obj.get("VALUE", None)
#     obj.pop("VALUE", None)
#     obj[answer_key] = value
#     return obj


# ==================== 主程式函數 ====================

def run_qa_on_transcript_json(
    INPUT_JSON,
    model,
    question_set_path="questionset_0206.xlsx",
    audio_item_path="audioitem_0206.xlsx",
    output_dir=None
):
    """
    主程式：處理單一逐字稿 JSON 檔案

    參數:
        INPUT_JSON: 逐字稿 JSON 檔案路徑
        model: LLM 模型實例（支援 Gemini、Gemma 等）
        question_set_path: 題組 Excel 檔案路徑
        audio_item_path: audio_id 對應表 Excel 檔案路徑
        output_dir: 輸出目錄路徑（若為 None 則輸出到原檔案所在目錄）
    """
    print(f"\n{'='*60}")
    print(f"處理逐字稿：{INPUT_JSON}")
    print(f"{'='*60}")

    p = pathlib.Path(INPUT_JSON)
    # 使用 utf-8-sig 來處理可能的 BOM
    with open(p, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    tid = data.get("id") or p.stem
    segments = data.get("segments", [])

    print(f"逐字稿 ID：{tid}")
    print(f"句子數量：{len(segments)}")

    # 決定輸出目錄
    if output_dir:
        out_dir = pathlib.Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"輸出目錄：{out_dir}")
    else:
        out_dir = p.parent

    # 建立 sentence_id 索引
    seg_index = {}
    for seg in segments:
        try:
            sid = int(seg.get("sentence_id"))
        except Exception:
            try:
                sid = int(str(seg.get("sentence_id")).strip())
            except Exception:
                continue
        seg_index[sid] = {
            "raw_timestamp": seg.get("raw_timestamp"),
            "text": seg.get("text")
        }

    # 建立模型用的上下文
    context = build_context_for_model(segments)

    # === 步驟 1：產生標註 ===
    print("\n[步驟 1] 呼叫 label_segments_by_category 產生四大類標註...")
    label_data = label_segments_by_category(tid, context, model)

    # === 步驟 2：儲存標註結果 ===
    label_path = out_dir / (p.stem + "_label.json")
    with open(label_path, "w", encoding="utf-8") as fo:
        json.dump(label_data, fo, ensure_ascii=False, indent=2)
    print(f"[步驟 2] 標註結果已儲存：{label_path}")

    # === 步驟 3：動態載入題組 ===
    print(f"\n[步驟 3] 動態載入題組...")
    print(f"  - 題組檔案：{question_set_path}")
    print(f"  - 對應表檔案：{audio_item_path}")
    print(f"  - audio_id：{tid}")

    qset = build_dynamic_qset(question_set_path, audio_item_path, tid)

    # === 步驟 4：建立空白考卷 ===
    print(f"\n[步驟 4] 建立空白考卷（共 {len(qset)} 題）...")
    test_paper = build_test_paper(tid, qset)
    test_path = out_dir / (p.stem + "_test.json")
    with open(test_path, "w", encoding="utf-8") as fo:
        json.dump(test_paper, fo, ensure_ascii=False, indent=2)
    print(f"空白考卷已儲存：{test_path.name}")

    # === 步驟 5：逐題作答 ===
    print(f"\n[步驟 5] 開始逐題作答...")
    transcript_json = json.dumps(data, ensure_ascii=False)
    label_json = json.dumps(label_data, ensure_ascii=False)

    # print("context")
    # print(context)
    for idx, q in enumerate(qset, 1):
        print(f"  [{idx}/{len(qset)}] {q['question_category']}: {q['question']}")

        ans = ask_one_question(
            transcript_json=context,
            answer_key=q["answer_key"],
            question_category=q["question_category"],
            question_text=q["question"],
            label_json=label_json,
            yesno=q.get("yesno", False),
            model=model
        )

        # 回填答案
        test_paper["acquired_answer"][idx-1][q["answer_key"]] = ans.get(q["answer_key"])
        test_paper["acquired_answer"][idx-1]["reason"] = ans.get("reason")
        test_paper["acquired_answer"][idx-1]["evidence"] = ans.get("evidence", [])

    # === 步驟 6：補充 evidence 資訊 ===
    print(f"\n[步驟 6] 補充 evidence 的時間戳記和文字...")
    result_obj = {
        "id": tid,
        "acquired_answer": test_paper["acquired_answer"]
    }
    result_obj = enrich_evidence(result_obj, seg_index)

    # === 步驟 7：輸出最終結果 ===
    out_path = out_dir / (p.stem + "_test_done.json")
    with open(out_path, "w", encoding="utf-8") as fo:
        json.dump(result_obj, fo, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ 處理完成！")
    print(f"  - 標註檔案：{label_path}")
    print(f"  - 考卷檔案：{test_path}")
    print(f"  - 答案檔案：{out_path}")
    print(f"{'='*60}\n")

    return result_obj


def run_qa_from_folder(
    ROOT_DIR,
    model,
    question_set_path,
    audio_item_path,
    pattern="*_transcript_*.json",
    recursive=True,
    output_dir=None
):
    """
    批次處理：遞迴處理整個資料夾的逐字稿 JSON

    參數:
        ROOT_DIR: 根目錄
        model: LLM 模型實例（支援 Gemini、Gemma 等）
        pattern: 檔案名稱模式
        recursive: 是否遞迴搜尋子目錄
        question_set_path: 題組 Excel 檔案路徑
        audio_item_path: audio_id 對應表 Excel 檔案路徑
        output_dir: 輸出目錄路徑（若為 None 則輸出到transcript.json所在目錄）
    """
    root = pathlib.Path(ROOT_DIR)
    files = list(root.rglob(pattern)) if recursive else list(root.glob(pattern))
    print(f"找到 {len(files)} 個檔案（pattern={pattern}，recursive={recursive}）")

    results = []
    for i, p in enumerate(sorted(files), 1):
        try:
            print(f"\n[{i}/{len(files)}] 處理：{p.name}")
            res = run_qa_on_transcript_json(
                str(p),
                model=model,
                question_set_path=question_set_path,
                audio_item_path=audio_item_path,
                output_dir=output_dir
            )
            results.append(res)
        except Exception as e:
            print(f"[{i}/{len(files)}] 發生錯誤：{p} -> {e}")

    print(f"\n完成。成功 {len(results)} 件，失敗 {len(files) - len(results)} 件。")
    return results

# ── 套用格式化邏輯 ──
def fmt_evidence(evs):
    """將 evidence list 轉成可讀的多行文字"""
    if not evs or not isinstance(evs, list):
        return ''
    return '\n'.join(
        f"[{ev.get('sentence_id', '')}] {ev.get('raw_timestamp', '')}  {ev.get('text', '')}"
        for ev in evs if isinstance(ev, dict)
    )

def get_checkpoints(row):
    """檢核點：特殊題直接標記；是非題異常答案是「否」；其他題是「無法確認」"""
    q = str(row['質檢問題'])
    if '是否為投資型保單' in q:
        return '不用分正常異常'
    return '否' if row['是非題'] else '無法確認'

def get_qa_result(row, invest_gate_map):
    """AI質檢結果：考慮投資型保單閘門邏輯"""
    q      = str(row['質檢問題'])
    answer = str(row['AI回答']).strip()

    if '是否為投資型保單' in q:
        return '不用分正常異常'

    if '如為投資型解約' in q:
        if invest_gate_map.get(row['音檔名稱'], '') == '否': #非投資型保單
            # 非投資型保單：如果 AI 判斷有權利義務，代表講了不該講的，算異常；如果沒有，算正常
            return '異常' if answer == '是' else '正常'

    if row['是非題']:
        return '異常' if answer == '否' else '正常'
    else:
        return '異常' if answer == '無法確認' else '正常'
