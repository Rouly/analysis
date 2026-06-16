"""声纹注册与匹配。

- 注册：录一段"我"的语音 → CAM++ 提取声纹向量 → 存 SQLite。
- 匹配：实时片段提声纹，与"我"的向量算余弦相似度，>阈值 判定为"我"。
  用于校正双路采集的标签（防外放/串音把客户误判成我、或反之）。

无 FunASR/pyaudiowpatch（如 Mock 模式或未装依赖）时自动降级：
  注册走"模拟成功"，匹配返回"不校正"，保证 UI 链路可跑。
"""
import threading
import numpy as np

import config
import store

# 依赖可用性探测
try:
    import pyaudiowpatch  # noqa
    _HAS_AUDIO = True
except Exception:
    _HAS_AUDIO = False

try:
    from funasr import AutoModel  # noqa
    _HAS_FUNASR = True
except Exception:
    _HAS_FUNASR = False

REAL = _HAS_AUDIO and _HAS_FUNASR

_extractor = None
_my_vec = None          # 缓存"我"的声纹向量
_enroll_thread = None
_enroll_state = {"running": False, "progress": 0.0, "msg": ""}


def _get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = AutoModel(model=config.SPK_MODEL, disable_update=True)
    return _extractor


def _embed(audio_16k_f32):
    """提取声纹向量。失败/降级返回 None。"""
    if not _HAS_FUNASR:
        return None
    try:
        res = _get_extractor().generate(input=audio_16k_f32)
        emb = res[0].get("spk_embedding") if res else None
        if emb is None:
            return None
        v = np.asarray(emb, dtype=np.float32).flatten()
        n = np.linalg.norm(v)
        return (v / n) if n > 0 else v
    except Exception:
        return None


def cosine(a, b):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ── 注册 ───────────────────────────────────────────
def enroll_state():
    s = dict(_enroll_state)
    s["enrolled"] = store.has_voiceprint("我")
    s["real"] = REAL
    return s


def start_enroll(on_done=None):
    """后台线程录音+提声纹+存库。进度可通过 enroll_state() 轮询。"""
    global _enroll_thread
    if _enroll_state["running"]:
        return
    _enroll_thread = threading.Thread(target=_run_enroll, args=(on_done,), daemon=True)
    _enroll_thread.start()


def _run_enroll(on_done):
    _enroll_state.update(running=True, progress=0.0, msg="开始录音…")
    try:
        if REAL:
            audio = _record_mic(config.ENROLL_SECONDS)
            _enroll_state.update(progress=0.9, msg="提取声纹…")
            vec = _embed(audio)
            if vec is None:
                _enroll_state.update(running=False, progress=0.0, msg="提取声纹失败")
                if on_done:
                    on_done(False, "提取声纹失败，请重试")
                return
            store.save_voiceprint(vec, "我")
            _load_my_vec(force=True)
            _enroll_state.update(running=False, progress=1.0, msg="注册完成")
            if on_done:
                on_done(True, "声纹注册完成")
        else:
            # 降级：模拟注册（Mock 模式下让 UI 流程可走通）
            import time
            for i in range(config.ENROLL_SECONDS):
                _enroll_state.update(progress=(i + 1) / config.ENROLL_SECONDS,
                                     msg=f"模拟录音 {i + 1}/{config.ENROLL_SECONDS}s…")
                time.sleep(0.1)  # mock 下加速
            store.save_voiceprint(np.zeros(192, dtype=np.float32), "我")
            _enroll_state.update(running=False, progress=1.0, msg="注册完成（mock）")
            if on_done:
                on_done(True, "声纹注册完成（mock 模拟）")
    except Exception as e:
        _enroll_state.update(running=False, progress=0.0, msg=f"注册失败：{e}")
        if on_done:
            on_done(False, str(e))


def _record_mic(seconds):
    """从默认麦克风录 seconds 秒，返回 16k 单声道 float32。仅 real。"""
    import pyaudiowpatch as pyaudio
    from real_engine import _resample
    p = pyaudio.PyAudio()
    info = p.get_default_input_device_info()
    rate = int(info["defaultSampleRate"])
    ch = int(info["maxInputChannels"]) or 1
    frames = int(rate * 0.2)
    stream = p.open(format=pyaudio.paInt16, channels=ch, rate=rate, input=True,
                    input_device_index=info["index"], frames_per_buffer=frames)
    buf = []
    total = int(seconds / 0.2)
    try:
        for i in range(total):
            data = stream.read(frames, exception_on_overflow=False)
            a = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            if ch > 1:
                a = a.reshape(-1, ch).mean(axis=1)
            buf.append(_resample(a, rate))
            _enroll_state.update(progress=0.05 + 0.8 * (i + 1) / total,
                                 msg=f"录音中 {int((i + 1) * 0.2)}/{seconds}s…")
    finally:
        stream.stop_stream(); stream.close(); p.terminate()
    return np.concatenate(buf) if buf else np.zeros(0, dtype=np.float32)


# ── 匹配（实时校正）────────────────────────────────────
def _load_my_vec(force=False):
    global _my_vec
    if _my_vec is None or force:
        v = store.load_voiceprint("我")
        _my_vec = np.asarray(v, np.float32) if v else None
    return _my_vec


def is_me(audio_16k_f32):
    """该片段是否为"我"。返回 (matched, similarity)。
    未注册/降级/提取失败时返回 (None, 0.0) 表示"无法判定，保持原标签"。"""
    my = _load_my_vec()
    if my is None or not REAL:
        return None, 0.0
    vec = _embed(audio_16k_f32)
    if vec is None:
        return None, 0.0
    sim = cosine(my, vec)
    return (sim >= config.SPK_THRESHOLD), sim
