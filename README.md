# 销售复盘助手（Electron + Python）

单兵销售复盘助手：本地实时转写，区分「我 / 客户」，会后一键生成销售复盘（客户异议、我的承诺、成交信号、话术建议），并支持复盘问答。**音频处理完即丢弃，不存录音、不上传。**

```
┌──────────────┐   WebSocket   ┌─────────────────────────────┐
│ Electron 前端  │ ◀──────────▶ │ Python 后端                   │
│ 实时对话流 +    │  ws://8765    │ 采音 → FunASR 转写 → 我/客户    │
│ 复盘面板 + 问答 │               │ 标记 → 缓存(仅文字) → LLM 分析  │
└──────────────┘               └─────────────────────────────┘
```

## 两种运行模式

- **Mock 模式（默认）**：不需要任何音频/AI 依赖，模拟一段「我/客户」销售对话。**任何系统都能立刻跑**，用于先看 UI 和链路。
- **Real 模式（Windows）**：`pyaudiowpatch` 双路采集（麦克风=我，系统声=客户）+ FunASR 中文流式转写。

---

## 快速开始（Mock 模式，5 分钟看到界面）

前置：装 [Node.js](https://nodejs.org/)（含 npm）和 Python 3.10+。

```bash
# 1) 装前端依赖
npm install

# 2) 装后端最小依赖
pip install websockets

# 3) 启动（Electron 会自动拉起 Python 后端）
npm start
```

打开后点 **● 开始记录** —— 会看到模拟的「我/客户」对话逐字滚出来；点 **⚡ 生成复盘** 看分析面板（未配大模型时为占位示例）。

> 若 Electron 没能自动启动后端（终端报 backend 启动失败），就分两个终端：
> 终端 A `npm run backend`，终端 B `npm start`。
> 如果你的 python 命令不是 `python`，设置环境变量：Windows PowerShell `$env:SR_PYTHON="py"`。

---

## 切到 Real 模式（Windows 真实采音转写）

> 仅 Windows。建议有 NVIDIA GPU，CPU 也能跑但较慢。

```powershell
# 1) 装真实依赖（首次会下载 FunASR 中文模型，约数百 MB）
pip install pyaudiowpatch funasr modelscope torch torchaudio numpy soundfile

# 2) 切换模式
$env:SR_MODE="real"

# 3) 启动
npm start
```

机制：麦克风路标记为「我」，系统输出 loopback 路标记为「客户」。开会前先把会议软件（腾讯会议/电话）的声音走默认扬声器即可。

热词（提升产品名/客户名识别）：编辑 `backend/config.py` 的 `HOTWORDS`。

---

## 开启大模型复盘分析（可选）

不配也能跑，只是「生成复盘/问答」返回占位。配置后即生效，支持 OpenAI 兼容接口（DeepSeek / 通义）、Anthropic、以及本地 Ollama。

```powershell
# 例：DeepSeek（OpenAI 兼容）
$env:SR_LLM_PROVIDER="openai"
$env:SR_LLM_API_KEY="你的key"
$env:SR_LLM_BASE_URL="https://api.deepseek.com"
$env:SR_LLM_MODEL="deepseek-chat"

# 例：本地 Ollama（数据不出本机，最符合隐私定位）
$env:SR_LLM_PROVIDER="openai"
$env:SR_LLM_BASE_URL="http://localhost:11434/v1"
$env:SR_LLM_MODEL="qwen2.5"
$env:SR_LLM_API_KEY="ollama"
```

也可直接改 `backend/config.py`，避免每次设环境变量。

---

## 目录结构

```
sales-replay/
├── package.json        Electron 配置
├── main.js             主进程：建窗口 + 自动拉起后端
├── preload.js          安全桥接（暴露 ws 地址）
├── renderer/           前端 UI
│   ├── index.html
│   ├── styles.css
│   └── renderer.js     连 ws、渲染对话流/分析/问答
└── backend/
    ├── server.py       WebSocket 服务（模式调度、缓存、转发）
    ├── config.py       所有配置集中在此
    ├── mock_engine.py  模拟对话（Mock 模式）
    ├── real_engine.py  双路采集 + FunASR 流式转写（Real 模式）
    ├── analysis.py     大模型复盘 + 问答
    └── requirements.txt
```

## 开发路线（对应技术架构文档）

- ✅ Phase 1 MVP：采集 → 转写 → 我/客户标记 → 实时展示（本仓库已搭好骨架）
- ⏳ Phase 2：声纹注册校正、复盘卡片打磨、问答（analysis 已接好）
- ⏳ Phase 3：设备选择 UI、多客户区分、打包 + 代码签名
- ⏳ Phase 4：会中实时话术提示、历史趋势统计

## 隐私说明

音频帧在内存中处理完即丢弃，磁盘不留录音文件；客户声纹即用即弃，仅本机保存「我」的声纹与文字稿。正式商用前请就「录音/转写他人对话」的合规问题咨询律师。
