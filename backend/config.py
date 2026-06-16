"""集中配置。改这里即可，不必动其它文件。"""
import os

# 运行模式：
#   "mock" = 不需要任何音频/AI 依赖，模拟一段"我/客户"对话，用于先看 UI 跑通。
#   "real" = 真实采音 + FunASR 中文转写（需 Windows + pyaudiowpatch + funasr）。
MODE = os.environ.get("SR_MODE", "mock")

# WebSocket 服务地址（前端会连这个）
HOST = "127.0.0.1"
PORT = int(os.environ.get("SR_PORT", "8765"))

# ── 音频参数（real 模式）──────────────────────────────
SAMPLE_RATE = 16000          # FunASR 标准输入
CHANNELS = 1
CHUNK_MS = 300               # 每帧时长(ms)，影响延迟与算力

# ── FunASR 模型（real 模式，首次会自动下载并离线缓存）─────
ASR_MODEL = "paraformer-zh-streaming"   # 中文流式转写
VAD_MODEL = "fsmn-vad"                    # 端点检测
HOTWORDS = ""               # 销售热词，空格分隔，如："明道云 私有化 试用期"

# ── 声纹（real 模式）──────────────────────────────────
SPK_MODEL = "cam++"          # FunASR 声纹模型
ENROLL_SECONDS = 20          # 注册录音时长(秒)
SPK_THRESHOLD = 0.35         # 余弦相似度阈值：高于此判定为"我"（CAM++ 经验值 0.3~0.4）

# ── 大模型复盘分析（可选）──────────────────────────────
# 留空则"生成复盘"返回占位结果。支持 OpenAI 兼容接口（DeepSeek/通义/Ollama）。
LLM_PROVIDER = os.environ.get("SR_LLM_PROVIDER", "")   # "openai" | "anthropic" | ""
LLM_API_KEY = os.environ.get("SR_LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("SR_LLM_BASE_URL", "")   # 自定义/Ollama: http://localhost:11434/v1
LLM_MODEL = os.environ.get("SR_LLM_MODEL", "gpt-4o-mini")
