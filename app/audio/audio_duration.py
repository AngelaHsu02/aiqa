import io
from io import BytesIO

def _read_bytes_preserve(fp):
    """讀取 file-like 的 bytes 並嘗試還原 pointer（若支援）。回傳 bytes。"""
    try:
        pos = fp.tell()
    except Exception:
        pos = None
    data = fp.read()
    try:
        if pos is not None:
            fp.seek(pos)
    except Exception:
        pass
    return data

def get_audio_duration_seconds(file_like):
    """
    解析音檔長度（秒），接受 UploadedFile / BytesIO / open(file,'rb') 等物件。
    依序嘗試：pydub (需 ffmpeg) -> soundfile -> wave。
    解析失敗回傳 None。
    """
    data = _read_bytes_preserve(file_like)
    buf = BytesIO(data)

    # 1) pydub（支援多格式，但需要系統 ffmpeg）
    try:
        from pydub import AudioSegment
        name = getattr(file_like, "name", None)
        if name and "." in name:
            fmt = name.rsplit(".", 1)[1].lower()
            seg = AudioSegment.from_file(buf, format=fmt)
        else:
            seg = AudioSegment.from_file(buf)
        return len(seg) / 1000.0
    except Exception:
        pass

    # 2) soundfile (優於 wave，但不支援 mp3)
    try:
        import soundfile as sf
        buf.seek(0)
        with sf.SoundFile(buf) as sfobj:
            return sfobj.frames / float(sfobj.samplerate)
    except Exception:
        pass

    # 3) wave (僅 wav)
    try:
        import wave
        buf.seek(0)
        with wave.open(buf, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        pass

    return None

def format_duration(sec):
    """把秒數格式化成人類可讀字串，例如 '2min:37sec'、'1h 02m:05s'。"""
    if sec is None:
        return "未知長度"
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}h {m:02d}m:{s:02d}s"
    elif m > 0:
        return f"{m}min:{s:02d}sec"
    else:
        return f"{s}sec"

def get_size_mb_from_bytes(b: bytes):
    return len(b) / 1024 / 1024
