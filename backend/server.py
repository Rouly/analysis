"""WebSocket 后端：连接前端，跑采音→转写引擎，转发结果，处理复盘分析与问答。

协议（JSON）：
  前端→后端: {"type":"start"} {"type":"stop"} {"type":"analyze"} {"type":"ask","question":"..."} {"type":"clear"}
  后端→前端: {"type":"status",...} {"type":"transcript",...} {"type":"analysis",...} {"type":"answer",...}
"""
import asyncio
import json

import websockets

import config
import analysis
import speaker
import store

# 当前对话缓存（仅文字，不含音频）
dialogue = []          # [{t, speaker, text}]
_partial = {}          # speaker -> 最近一条未 final 的索引
engine = None
main_loop = None
clients = set()
auto_suggest = False        # 实时应答开关
_suggest_busy = False       # 防止并发调用 LLM


def make_engine():
    if config.MODE == "real":
        from real_engine import RealEngine
        return RealEngine()
    from mock_engine import MockEngine
    return MockEngine()


async def broadcast(msg):
    if clients:
        data = json.dumps(msg, ensure_ascii=False)
        await asyncio.gather(*[c.send(data) for c in clients], return_exceptions=True)


def emit_transcript(speaker, text, t, final):
    """引擎线程回调（非 asyncio 线程），转交事件循环广播 + 更新缓存。"""
    def _apply():
        idx = _partial.get(speaker)
        if idx is not None and not _is_final_done(idx):
            dialogue[idx] = {"t": t, "speaker": speaker, "text": text, "final": final}
        else:
            dialogue.append({"t": t, "speaker": speaker, "text": text, "final": final})
            _partial[speaker] = len(dialogue) - 1
        if final:
            _partial.pop(speaker, None)
        asyncio.ensure_future(broadcast(
            {"type": "transcript", "speaker": speaker, "text": text, "t": t, "final": final}))
        # 客户说完一轮 → 自动生成应答建议
        if final and speaker == "客户" and auto_suggest:
            asyncio.ensure_future(run_suggestion())
    main_loop.call_soon_threadsafe(_apply)


async def run_suggestion():
    global _suggest_busy
    if _suggest_busy:
        return
    _suggest_busy = True
    try:
        text = await asyncio.to_thread(analysis.suggest_reply, clean_dialogue())
        if text:
            await broadcast({"type": "suggestion", "text": text})
    finally:
        _suggest_busy = False


def _is_final_done(idx):
    return 0 <= idx < len(dialogue) and dialogue[idx].get("final")


async def poll_enroll():
    """注册期间每 300ms 广播一次进度，直到结束。"""
    while True:
        st = speaker.enroll_state()
        await broadcast({"type": "enroll", **st})
        if not st.get("running"):
            break
        await asyncio.sleep(0.3)


def clean_dialogue():
    """交给大模型的版本：只保留已 final 的句子。"""
    return [{"t": d["t"], "speaker": d["speaker"], "text": d["text"]}
            for d in dialogue if d.get("final")]


async def handle(ws):
    global engine
    clients.add(ws)
    await ws.send(json.dumps({"type": "status", "mode": config.MODE,
                              "msg": f"已连接（{config.MODE} 模式）"}, ensure_ascii=False))
    await ws.send(json.dumps({"type": "enroll", **speaker.enroll_state()}, ensure_ascii=False))
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            t = msg.get("type")
            if t == "start":
                dialogue.clear()
                _partial.clear()
                engine = make_engine()
                engine.start(emit_transcript)
                await broadcast({"type": "status", "mode": config.MODE, "msg": "开始记录…"})
            elif t == "stop":
                if engine:
                    engine.stop()
                    engine = None
                # 会话存档（仅文字）
                saved = clean_dialogue()
                if saved:
                    sid = store.save_session(saved)
                    await broadcast({"type": "status", "mode": config.MODE,
                                     "msg": f"已停止，已存档会话 #{sid}"})
                else:
                    await broadcast({"type": "status", "mode": config.MODE, "msg": "已停止"})
            elif t == "auto_suggest":
                global auto_suggest
                auto_suggest = bool(msg.get("on"))
                await broadcast({"type": "status", "mode": config.MODE,
                                 "msg": ("已开启实时应答" if auto_suggest else "已关闭实时应答")})
            elif t == "enroll_start":
                speaker.start_enroll()
                asyncio.ensure_future(poll_enroll())
            elif t == "enroll_state":
                await ws.send(json.dumps({"type": "enroll", **speaker.enroll_state()},
                                         ensure_ascii=False))
            elif t == "enroll_delete":
                store.delete_voiceprint("我")
                speaker._my_vec = None
                await ws.send(json.dumps({"type": "enroll", **speaker.enroll_state()},
                                         ensure_ascii=False))
            elif t == "clear":
                dialogue.clear()
                _partial.clear()
                await broadcast({"type": "status", "mode": config.MODE, "msg": "已清空对话"})
            elif t == "analyze":
                await broadcast({"type": "status", "mode": config.MODE, "msg": "正在生成复盘…"})
                result = await asyncio.to_thread(analysis.analyze, clean_dialogue())
                await ws.send(json.dumps({"type": "analysis", "data": result}, ensure_ascii=False))
            elif t == "ask":
                q = msg.get("question", "")
                ans = await asyncio.to_thread(analysis.ask, clean_dialogue(), q)
                await ws.send(json.dumps({"type": "answer", "question": q, "text": ans},
                                         ensure_ascii=False))
    finally:
        clients.discard(ws)


async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    print(f"[sales-replay] WebSocket 启动 ws://{config.HOST}:{config.PORT}  模式={config.MODE}")
    async with websockets.serve(handle, config.HOST, config.PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[sales-replay] 已退出")
