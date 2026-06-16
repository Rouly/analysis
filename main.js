// Electron 主进程：创建窗口，并（可选）自动拉起 Python 后端。
const { app, BrowserWindow } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

let backendProc = null;

// 是否由 Electron 自动启动后端。设为 false 时请手动运行 `npm run backend`。
const AUTO_START_BACKEND = true;
// Python 可执行文件：Windows 通常是 "python"，部分环境是 "py" 或 "python3"。
const PYTHON = process.env.SR_PYTHON || (process.platform === "win32" ? "python" : "python3");

function startBackend() {
  if (!AUTO_START_BACKEND) return;

  // 打包后优先用 PyInstaller 生成的后端可执行文件（无需用户装 Python）
  const bundled = path.join(
    process.resourcesPath || "",
    "backend",
    process.platform === "win32" ? "server.exe" : "server"
  );
  if (app.isPackaged && fs.existsSync(bundled)) {
    backendProc = spawn(bundled, [], { env: process.env, stdio: "inherit" });
  } else {
    // 开发模式：用系统 Python 跑源码
    const script = path.join(__dirname, "backend", "server.py");
    backendProc = spawn(PYTHON, [script], {
      cwd: path.join(__dirname, "backend"),
      env: process.env,
      stdio: "inherit",
    });
  }
  backendProc.on("error", (err) => {
    console.error("[backend] 启动失败：", err.message,
      "— 开发模式可手动运行 `npm run backend`，或设置 SR_PYTHON 指向正确的 python。");
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 760,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: "#0f1115",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  startBackend();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (backendProc) backendProc.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProc) backendProc.kill();
});
