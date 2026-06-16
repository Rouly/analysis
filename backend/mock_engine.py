"""Mock 引擎：不依赖任何音频/AI 库，按时间轴吐出一段模拟"我/客户"对话。
用于在任意电脑上先把 UI + WebSocket 链路跑通。"""
import threading
import time

SCRIPT = [
    ("客户", "你们这个产品我们看了，整体还行，但价格确实有点超预算。"),
    ("我",   "理解，预算这块我们可以聊。方便问下今年大概的预算范围吗？"),
    ("客户", "今年这块预算大概二十万左右，是我和我们总监一起定的。"),
    ("我",   "好的，二十万的话我们标准版完全覆盖。我可以给您申请一个老客户折扣。"),
    ("客户", "折扣能到多少？另外你们和明道云比有什么优势？"),
    ("我",   "折扣我尽量帮您争取到八五折。对比的话我们私有化部署更彻底，数据完全在您本地。"),
    ("客户", "私有化这点不错，我们比较在意数据安全。那能先试用一段时间吗？"),
    ("我",   "可以的，我给您开一个月的试用，包安装、包培训，这个我现在就能答应您。"),
    ("客户", "行，那你把报价和试用方案发我邮箱，我下周和总监过一下。"),
    ("我",   "没问题，今天下班前发您。下周三我再跟您对一下进展可以吗？"),
]


class MockEngine:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self, emit):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(emit,), daemon=True)
        self._thread.start()

    def _run(self, emit):
        t0 = time.time()
        for speaker, text in SCRIPT:
            if self._stop.is_set():
                return
            # 模拟流式：先逐字推 partial，再推 final
            buf = ""
            for ch in text:
                if self._stop.is_set():
                    return
                buf += ch
                emit(speaker, buf, _ts(t0), False)
                time.sleep(0.04)
            emit(speaker, text, _ts(t0), True)
            time.sleep(0.8)

    def stop(self):
        self._stop.set()


def _ts(t0):
    s = int(time.time() - t0)
    return f"{s // 60:02d}:{s % 60:02d}"
