import os
import threading
from datetime import datetime, timedelta
from opencc import OpenCC
from openai import AzureOpenAI
from dotenv import load_dotenv
import httpx
import urllib3

load_dotenv()

# ── 關閉 SSL 驗證 + 繞過公司 Proxy（避免大音檔被 Proxy 截斷導致 502）──
# httpx 0.28+ 已移除 proxies 參數，改用 mounts 設定直連（不走任何 Proxy）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_http = httpx.Client(
    verify=False,
    mounts={"https://": None, "http://": None},  # None = 直連，不走 Proxy
    timeout=httpx.Timeout(
        connect=30.0,    # 建立連線最多等 30 秒
        read=300.0,      # 讀回應最多等 5 分鐘（長音檔轉錄需要）
        write=300.0,     # 上傳音檔最多等 5 分鐘
        pool=10.0,
    ),
)

# ── Azure Whisper 用戶端（從 .env 讀取，啟動時建立一次）──
_whisper_client = AzureOpenAI(
    api_key=os.getenv("WHISPER_API_KEY"),
    api_version=os.getenv("WHISPER_API_VERSION"),
    azure_endpoint=os.getenv("WHISPER_ENDPOINT"),
    http_client=_http,
)
_WHISPER_DEPLOYMENT = os.getenv("WHISPER_DEPLOYMENT", "whisper")


# ── 全域排隊鎖：確保同一時間只有一個任務在呼叫 API ──
_whisper_lock = threading.Lock()

# ── 全域佇列清單：追蹤排隊中的所有任務 ──
_queue_lock = threading.Lock()
_queue_list = []


def register_job(job_id: str, file_infos: list):
    """任務加入佇列（開始等待前呼叫）。file_infos: [{"name":..., "duration_sec":...}]"""
    with _queue_lock:
        _queue_list.append({"job_id": job_id, "files": file_infos})


def unregister_job(job_id: str):
    """任務從佇列移除（轉錄全部完成後呼叫）"""
    with _queue_lock:
        for i, item in enumerate(_queue_list):
            if item["job_id"] == job_id:
                _queue_list.pop(i)
                break


def get_queue_snapshot() -> list:
    """回傳目前佇列的快照（淺拷貝），供 UI 讀取，不阻塞"""
    with _queue_lock:
        return list(_queue_list)


def is_lock_busy() -> bool:
    """非阻塞查詢：若已有人佔用則回傳 True，否則 False"""
    acquired = _whisper_lock.acquire(blocking=False)
    if acquired:
        _whisper_lock.release()
        return False
    return True


cc = OpenCC('s2t')  # 簡體轉繁體


def format_custom_time(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((td.total_seconds() - total_seconds) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def transcribe_file(file_path, output_dir, model=None, model_size: str = "azureapi"):
    """
    使用 Azure Whisper API 轉文字，輸出格式與地端 Whisper 相同（TXT + JSON）。
    參數 model / model_size 保留相容舊介面，不實際使用。
    """
    import json

    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    suffix = f"_transcript_openaiwhisper_{model_size}"
    output_txt = os.path.join(output_dir, f"{base_filename}{suffix}.txt")
    output_json = os.path.join(output_dir, f"{base_filename}{suffix}.json")

    print(f"⏳ 排隊等候 API 資源：{os.path.basename(file_path)}")
    with _whisper_lock:
        print(f"▶️  開始呼叫 Azure Whisper API：{os.path.basename(file_path)}")
        with open(file_path, "rb") as audio_file:
            result = _whisper_client.audio.transcriptions.create(
                model=_WHISPER_DEPLOYMENT,
                file=audio_file,
                language="zh",
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        print(f"✅ Azure Whisper 轉文字完成：{os.path.basename(file_path)}")

    # ── 解析回傳結果 ──
    segments = getattr(result, "segments", []) or []

    # ✅ 寫入逐字稿 TXT
    with open(output_txt, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Filename: {os.path.basename(file_path)}\n")
        f.write(f"Detected Language: {getattr(result, 'language', 'zh')}\n")
        f.write(f"Whisper Model: {model_size}\n\n")
        for seg in segments:
            start = format_custom_time(seg.get("start", 0) if isinstance(seg, dict) else seg.start)
            end   = format_custom_time(seg.get("end",   0) if isinstance(seg, dict) else seg.end)
            text  = seg.get("text", "")          if isinstance(seg, dict) else seg.text
            traditional_text = cc.convert(text.strip())
            f.write(f"[{start} -- {end}] {traditional_text}\n")

    # ✅ 寫入逐字稿 JSON（供 AI 質檢使用）
    json_data = {
        "id": base_filename,
        "source": f"{base_filename}{suffix}.txt",
        "segments": [],
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "whisper_model": model_size,
            "original_line_count": len(segments),
        }
    }

    for idx, seg in enumerate(segments, 1):
        if isinstance(seg, dict):
            start_sec = seg.get("start", 0)
            end_sec   = seg.get("end",   0)
            text      = seg.get("text", "")
        else:
            start_sec = seg.start
            end_sec   = seg.end
            text      = seg.text

        start_time = format_custom_time(start_sec)
        end_time   = format_custom_time(end_sec)
        traditional_text = cc.convert(text.strip())

        json_data["segments"].append({
            "sentence_id": idx,
            "raw_timestamp": f"[{start_time} -- {end_time}]",
            "start": start_time,
            "end":   end_time,
            "start_seconds": start_sec,
            "end_seconds":   end_sec,
            "duration_seconds": end_sec - start_sec,
            "speaker": None,
            "text": traditional_text,
        })

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return output_txt, output_json


def transcribe_folder(
    input_folder: str,
    model=None,                           # 保留相容舊介面
    output_dir: str = None,
    model_size: str = "azureapi",
    include_exts=(".mp3", ".wav", ".mp4", ".m4a"),
    job_id: str = None,
):
    """
    批次轉文字，呼叫 Azure Whisper API。
    """
    import uuid
    from app.audio.audio_duration import get_audio_duration_seconds
    from io import BytesIO

    if output_dir is None:
        output_dir = input_folder
    if job_id is None:
        job_id = str(uuid.uuid4())

    targets = []
    for root, _, files in os.walk(input_folder):
        for f in files:
            if any(f.lower().endswith(ext) for ext in include_exts):
                targets.append(os.path.join(root, f))
    targets = sorted(targets)

    # 讀取每個音檔的時長，組成 file_infos 供 UI 顯示
    file_infos = []
    for p in targets:
        try:
            with open(p, "rb") as fh:
                dur = get_audio_duration_seconds(BytesIO(fh.read())) or 0.0
        except Exception:
            dur = 0.0
        file_infos.append({"name": os.path.basename(p), "duration_sec": dur})

    register_job(job_id, file_infos)
    print(f"📋 任務 {job_id} 已加入佇列，共 {len(file_infos)} 個音檔")

    produced = []
    failed = []
    try:
        for p in targets:
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S} 開始轉 {os.path.basename(p)} 成文字")
            try:
                out_txt, out_json = transcribe_file(p, output_dir, model_size=model_size)
                produced.extend([out_txt, out_json])
                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} 完成逐字稿路徑 {out_txt}")
                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} 完成 JSON 路徑 {out_json}")
            except Exception as e:
                fname = os.path.basename(p)
                failed.append(fname)
                print(f"❌ 轉文字失敗：{fname}，錯誤：{e}")
        if failed:
            print(f"⚠️ 以下 {len(failed)} 個音檔轉文字失敗：{', '.join(failed)}")
        print(f"✅ 轉文字結束，成功 {len(produced)//2} 個，失敗 {len(failed)} 個，輸出到資料夾：{output_dir}")
    finally:
        unregister_job(job_id)
        print(f"📋 任務 {job_id} 已從佇列移除")

    return produced
