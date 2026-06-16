# 打包成 Windows .exe

> ⚠️ 必须在 **Windows 电脑**上执行。`.exe` 无法在 Linux/Mac 上交叉编译（尤其 Python 后端）。

## 方案 A：先打「Mock 版」验证流程（推荐，最快）

Mock 版不含 AI 依赖，能跑通界面与全部交互，用来验证打包链路。

```powershell
# 0) 前置：装 Node.js、Python 3.10+
# 1) 装依赖
npm install
pip install websockets pyinstaller

# 2) 把 Python 后端打成 server.exe
npm run build:backend
#   产物在 build/backend/server.exe

# 3) 用 electron-builder 打成安装包
npm run dist
#   产物在 dist/  →  销售复盘助手-0.1.0-setup.exe
```

双击 `dist/` 里的 setup.exe 安装，开始菜单/桌面会出现「销售复盘助手」，**无需用户另装 Python**（后端已打进安装包）。

## 方案 B：打「Real 版」（含中文转写/声纹，体积大）

Real 模式依赖 `torch / funasr / pyaudiowpatch`，体积大（数 GB）、还需收集模型数据文件，打包较复杂。建议先方案 A 跑通，再升级：

1. 安装 real 依赖：
   ```powershell
   pip install pyaudiowpatch funasr modelscope torch torchaudio numpy soundfile pyinstaller
   ```
2. 编辑 `backend/server.spec`，取消 `hiddenimports` 里 real 相关行的注释；
   可能还需用 `--collect-all funasr --collect-all torch` 收集数据文件（首次会很大）。
3. 重新 `npm run build:backend && npm run dist`。
4. FunASR 模型建议首次运行时联网下载并缓存，而非打进安装包（否则包过大）。

## 代码签名（正式商用再做）

不签名时 Windows SmartScreen 会弹"未知发布者"警告。正式分发前：

- 买代码签名证书（个人 EV 证书亦可，见技术架构文档第 9 节）。
- 在 `package.json` 的 `build.win` 增加签名配置，或用 `signtool` 对产物签名。

## 常见问题

- **构建时 electron 下载慢/失败**：设国内镜像
  `setx ELECTRON_MIRROR https://npmmirror.com/mirrors/electron/`
- **server.exe 闪退**：先在终端单独运行 `build/backend/server.exe` 看报错。
- **想要绿色免安装版**：把 `build.win.target` 从 `nsis` 改为 `portable`。
