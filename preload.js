// 预加载脚本：当前仅暴露后端 WebSocket 地址，保持渲染进程沙箱。
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("SR", {
  wsUrl: process.env.SR_WS || "ws://127.0.0.1:8765",
});
