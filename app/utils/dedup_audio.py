import os

def dedup_by_name(file_objs):
    """
    依 'name' 去重，保持原順序；支援 Streamlit UploadedFile / BytesIO。
    若物件沒有 name，會用 'unnamed_i' 補上（極少見）。
    """
    seen = set()
    unique = []
    for i, f in enumerate(file_objs or []):
        name = getattr(f, "name", None) or f"unnamed_{i}"
        if name in seen:
            continue
        seen.add(name)
        unique.append(f)
        # 確保後面流程都能取到 name
        if not hasattr(f, "name"):
            try:
                f.name = name  # BytesIO 也可動態掛上屬性
            except Exception:
                pass
    return unique

def _norm_path(p):
    return os.path.normpath(p) if isinstance(p, (str, os.PathLike)) else p

def _norm_paths(paths):
    if paths is None:
        return []
    if isinstance(paths, (str, os.PathLike)):
        return [os.path.normpath(paths)]
    # list/tuple 逐一處理
    return [os.path.normpath(p) for p in paths if isinstance(p, (str, os.PathLike))]
