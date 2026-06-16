"""Real 引擎（Windows）：pyaudiowpatch 双路采集 → FunASR 中文流式转写。

设计要点：
- 麦克风路 = "我"；系统输出 loopback 路 = "客户"。这是最稳的"我/客户"信号，
  避免实时说话人分离的高难度（声纹校正可作为 Phase 2 增强）。
- 每路一个独立 FunASR 流式实例，互不干扰。
- 音频帧处理完即丢弃，不写磁盘（隐私设计）。

依赖：pyaudiowpatch, funasr, numpy, torch/torchaudio。仅在 MODE=real 时导入。
"""
import threading
import time
import queue
import numpy as np

import config

# FunASR 流式参数：chunk_size=[0,10,5] 约对应 600ms 主块
_CHUNK_SIZE = [0, 10, 5]
_ENC_LOOKBACK = 4
_DEC_LOOKBACK = 1
_CHUNK_SAMPLES = _CHUNK_SIZE[1] * 960   # 16k 下每块样本数 ≈ 9600 (600ms)


def _resample(audio_f32, src_rate):
    """简易线性重采样到 16k（够用；要更高质量可换 torchaudio.functional.resample）。"""
    if src_rate == config.SAMPLE_RATE:
        return audio_f32
    n_out = int(len(audio_f32) * config.SAMPLE_RATE / src_rate)
    if n_out <= 0:
        return np.zeros(0, dtype=np.float32)
    x_old = np.linspace(0, 1, len(audio_f32), endpoint=False)
    x_new = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_new, x_old, audio_f32).astype(np.float32)


class _SourceStream:
    """单路（麦克风或 loopback）的采集 + 转写线程。"""

    def __init__(self, speaker, device_info, p, emit, t0):
        self.default_speaker = speaker     # "我" 或 "客户"（来自音轨来源）
        self.speaker = speaker             # 当前段实际标签（可被声纹校正）
        self.device_info = device_info
        self.p = p
        self.emit = emit
        self.t0 = t0
        self._stop = threading.Event()
        self._q = queue.Queue()
        self._buf = np.zeros(0, dtype=np.float32)
        self._cache = {}
        self._text_final = ""
        self._seg_audio = []               # 当前段累积音频，用于声纹校正
        self._classified = False
        from funasr import AutoModel
        self._model = AutoModel(model=config.ASR_MODEL, disable_update=True)

    def start(self):
        self._cap_t = threading.Thread(target=self._capture, daemon=True)
        self._asr_t = threading.Thread(target=self._transcribe, daemon=True)
        self._cap_t.start()
        self._asr_t.start()

    def _capture(self):
        import pyaudiowpatch as pyaudio
        rate = int(self.device_info["defaultSampleRate"])
        ch = int(self.device_info["maxInputChannels"]) or 1
        frames = int(rate * config.CHUNK_MS / 1000)
        stream = self.p.open(
            format=pyaudio.paInt16, channels=ch, rate=rate, input=True,
            input_device_index=self.device_info["index"], frames_per_buffer=frames,
        )
        try:
            while not self._stop.is_set():
                data = stream.read(frames, exception_on_overflow=False)
                a = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                if ch > 1:                       # 多声道取均值转单声道
                    a = a.reshape(-1, ch).mean(axis=1)
                self._q.put(_resample(a, rate))  # 帧用完即弃，仅留重采样后的临时数组
        finally:
            stream.stop_stream()
            stream.close()

    def _transcribe(self):
        while not self._stop.is_set():
            try:
                a = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            self._buf = np.concatenate([self._buf, a])
            while len(self._buf) >= _CHUNK_SAMPLES:
                chunk = self._buf[:_CHUNK_SAMPLES]
                self._buf = self._buf[_CHUNK_SAMPLES:]
                self._feed(chunk, is_final=False)

    def _maybe_correct(self):
        """累积约 1.5s 音频后，用声纹判断本段是否真的是"我"，校正标签一次。"""
        if self._classified:
            return
        seg = np.concatenate(self._seg_audio) if self._seg_audio else np.zeros(0, np.float32)
        if len(seg) < int(1.5 * config.SAMPLE_RATE):
            return
        import speaker as spk
        matched, sim = spk.is_me(seg[-int(2 * config.SAMPLE_RATE):])
        if matched is None:
            return  # 未注册/无法判定 → 保持音轨默认标签
        if matched and self.default_speaker != "我":
            self.speaker = "我"          # 外放：我的声音从扬声器回灌，纠正为"我"
        elif (not matched) and self.default_speaker == "我":
            self.speaker = "客户"        # 客户声音被麦克风拾取，纠正为"客户"
        self._classified = True

    def _feed(self, chunk, is_final):
        self._seg_audio.append(chunk)
        self._maybe_correct()
        res = self._model.generate(
            input=chunk, cache=self._cache, is_final=is_final,
            chunk_size=_CHUNK_SIZE, encoder_chunk_look_back=_ENC_LOOKBACK,
            decoder_chunk_look_back=_DEC_LOOKBACK,
        )
        piece = res[0]["text"] if res and res[0].get("text") else ""
        if piece:
            self._text_final += piece
            self.emit(self.speaker, self._text_final, _ts(self.t0), False)

    def stop(self):
        self._stop.set()
        # flush 末块
        try:
            if len(self._buf) > 0:
                self._feed(self._buf, is_final=True)
            if self._text_final:
                self.emit(self.speaker, self._text_final, _ts(self.t0), True)
        except Exception:
            pass


class RealEngine:
    def __init__(self):
        self._sources = []
        self._p = None

    def start(self, emit):
        import pyaudiowpatch as pyaudio
        self._p = pyaudio.PyAudio()
        t0 = time.time()
        mic = self._default_mic()
        loop = self._default_loopback()
        if mic:
            s = _SourceStream("我", mic, self._p, emit, t0)
            s.start()
            self._sources.append(s)
        if loop:
            s = _SourceStream("客户", loop, self._p, emit, t0)
            s.start()
            self._sources.append(s)
        if not self._sources:
            emit("系统", "未找到可用音频设备，请检查麦克风/扬声器。", "00:00", True)

    def _default_mic(self):
        try:
            return self._p.get_default_input_device_info()
        except Exception:
            return None

    def _default_loopback(self):
        """找到与默认扬声器对应的 WASAPI loopback 设备。"""
        import pyaudiowpatch as pyaudio
        try:
            wasapi = self._p.get_host_api_info_by_type(pyaudio.paWASAPI)
            spk = self._p.get_device_info_by_index(wasapi["defaultOutputDevice"])
            for lb in self._p.get_loopback_device_info_generator():
                if spk["name"] in lb["name"]:
                    return lb
        except Exception:
            return None
        return None

    def stop(self):
        for s in self._sources:
            s.stop()
        self._sources = []
        if self._p:
            self._p.terminate()
            self._p = None


def _ts(t0):
    s = int(time.time() - t0)
    return f"{s // 60:02d}:{s % 60:02d}"
