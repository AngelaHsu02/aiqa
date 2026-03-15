# **分割左右聲道**
import whisper
import csv
import os
import librosa
import soundfile as sf
import noisereduce as nr
import torch
import torchaudio
# from silero_vad import get_speech_timestamps, read_audio
import numpy as np
from pydub import AudioSegment
from datetime import datetime
from functools import lru_cache

# # 初始化 Silero VAD 模型
# model, utils = torch.hub.load(
#     repo_or_dir='snakers4/silero-vad',
#     model='silero_vad',
#     force_reload=True)
# (get_speech_timestamps, _, read_audio, *_) = utils

@lru_cache(maxsize=1)
def init_vad():
    """
    載入並快取 Silero VAD (Voice Activity Detection) 模型與工具；服務啟動時呼叫一次即可。
    回傳: (vad_model, get_speech_timestamps)
    """
    print(f"📦 Silero VAD 載入模型")
    # split.py is at app/audio/split.py
    # go up 3 levels to reach project root: audio -> app -> project root
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    _app_dir  = os.path.dirname(_this_dir)
    _base_dir = os.path.dirname(_app_dir)
    _silero_path = os.path.join(_base_dir, "vendor", "silero-vad")
    vad_model, utils = torch.hub.load(
        repo_or_dir=_silero_path,
        model='silero_vad',
        source="local",
        force_reload=False
    )
    (get_speech_timestamps, _, _read_audio, *_) = utils
    return vad_model, get_speech_timestamps

def apply_vad(audio, sample_rate):# **VAD處理**
    vad_model, get_speech_timestamps = init_vad()
    wav_tensor = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
    speech_timestamps = get_speech_timestamps(wav_tensor, vad_model, sampling_rate=sample_rate)

    if not speech_timestamps:
        return np.zeros_like(audio)  # 沒偵測到語音則整段靜音

    result = np.zeros_like(audio)
    for t in speech_timestamps:
        start, end = t['start'], t['end']
        result[start:end] = audio[start:end]
    return result

def process_audio(file_path, output_path):# **降噪+增強**
    try:
        # 讀取音訊
        y, sr = librosa.load(file_path, sr=None) # 變量 y = 音波、sr = sample rate

        # **降噪**
        reduced_noise = nr.reduce_noise(y=y, sr=sr, prop_decrease=0.9)

        # **VAD 處理**
        vad_audio = apply_vad(reduced_noise, sr)
        if vad_audio is None:
            print(f"⚠️ {file_path} 未偵測到語音，跳過儲存。")
            return

        # **儲存降噪後的音訊**
        temp_wav_path = output_path.replace(".wav", "_denoised.wav")
        sf.write(temp_wav_path, vad_audio, sr)

        audio = AudioSegment.from_file(temp_wav_path, format="wav")# 變成 pydub 形式
        audio = audio + 5  # 提高 5dB 音量
        audio = audio.set_channels(1).set_frame_rate(16000)  # # 轉成單聲道/16kHz

        # **儲存最終處理後的音訊**
        audio.export(output_path, format="wav")

        # 刪除臨時降噪音檔
        os.remove(temp_wav_path)

    except Exception as e:
        print(f"❌ 處理音訊 {file_path} 時發生錯誤：{e}")

def split_folder(input_folder: str):
    """
    對資料夾內 .mp3/.wav 做左右聲道切分並前處理。
    回傳: 產生的 ['..._left.wav', '..._right.wav'] 路徑清單
    """
    produced = []
    # **批量處理所有mp3,wav檔案**
    for filename in os.listdir(input_folder):

        if filename.lower().endswith((".mp3",".wav")):  # 只處理mp3,wav檔案
            input_path = os.path.join(input_folder, filename)
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}開始切{filename}聲道")

            try:
                # 讀取音檔
                file_ext = filename.lower().split(".")[-1]  # 取得副檔名（不含.）
                audio = AudioSegment.from_file(input_path, format=file_ext)
                print(f"{filename}聲道數：{audio.channels}")

                # **確認是否為雙聲道**

                if audio.channels != 2:
                    print(f"⚠️ 跳過{filename}：此檔案不是雙聲道")
                    continue # 非雙聲道則跳過

                # **取得檔案名稱（不含副檔名)、設定輸出檔案名稱**
                base_name = os.path.splitext(filename)[0]
                left_wav_path = os.path.join(input_folder, f"{base_name}_left.wav")
                right_wav_path = os.path.join(input_folder, f"{base_name}_right.wav")

                # **分割左右聲道**
                channels = audio.split_to_mono() # 分割成單聲道
                left_channel = channels[0]  # 左聲道
                right_channel = channels[1]  # 右聲道

                # **儲存左右聲道原始音訊**
                left_channel.export(left_wav_path, format="wav", parameters=["-ac", "1"])
                right_channel.export(right_wav_path, format="wav", parameters=["-ac", "1"])
                print("完成切聲道，開始前處理")

                # **前處理：降噪＆音量增強＆VAD **
                print(f"左聲道前處理：{left_wav_path}")
                process_audio(left_wav_path, left_wav_path)

                print(f"右聲道前處理：{right_wav_path}")
                process_audio(right_wav_path, right_wav_path)

                produced.extend([left_wav_path, right_wav_path])
                print(f"✅ {filename} 左右聲道前處理完成，輸出到資料夾：{input_folder}")
            except Exception as e:
                print(f"❌ 處理 {filename} 時發生錯誤：{e}")
    return produced

# print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}批量處理完成！")
