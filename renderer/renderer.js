// 渲染进程：连后端 WebSocket，渲染实时对话流、复盘分析与问答。
const wsUrl = (window.SR && window.SR.wsUrl) || "ws://127.0.0.1:8765";

const el = (id) => document.getElementById(id);
const chat = el("chat");
const analysisBody = el("analysis");
let ws = null;
let recording = false;
// 记录每个说话人最后一条 partial 气泡，便于原地更新
const lastBubble = {}; // speaker -> element

function connect() {
  ws = new WebSocket(wsUrl);
  ws.onopen = () => setConn(true, "已连接");
  ws.onclose = () => { setConn(false, "已断开，重连中…"); setTimeout(connect, 1500); };
  ws.onerror = () => setConn(false, "连接错误");
  ws.onmessage = (e) => handle(JSON.parse(e.data));
}

function setConn(on, text) {
  el("dot").className = "dot " + (on ? "on" : "off");
  el("connText").textContent = text;
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function handle(msg) {
  switch (msg.type) {
    case "status":
      if (msg.mode) el("modeBadge").textContent = msg.mode.toUpperCase() + " 模式";
      break;
    case "transcript":
      renderTranscript(msg);
      break;
    case "analysis":
      renderAnalysis(msg.data);
      break;
    case "answer":
      el("qaAnswer").textContent = msg.text || "";
      break;
    case "enroll":
      renderEnroll(msg);
      break;
    case "suggestion":
      showSuggestion(msg.text);
      break;
  }
}

function showSuggestion(text) {
  if (!text) return;
  el("suggestText").textContent = text;
  el("suggestBar").classList.remove("hidden");
}

function renderEnroll(s) {
  const st = el("vpStatus");
  const btn = el("btnEnroll");
  if (s.running) {
    st.className = "vp-status rec";
    st.textContent = `声纹：${s.msg || "录音中"} ${Math.round((s.progress || 0) * 100)}%`;
    btn.disabled = true;
  } else if (s.enrolled) {
    st.className = "vp-status ok";
    st.textContent = "声纹：已注册 ✓" + (s.real ? "" : "（mock）");
    btn.disabled = false;
    btn.textContent = "重新注册";
  } else {
    st.className = "vp-status";
    st.textContent = "声纹：未注册";
    btn.disabled = false;
    btn.textContent = "注册我的声纹";
  }
}

function renderTranscript({ speaker, text, t, final }) {
  if (chat.querySelector(".empty")) chat.innerHTML = "";
  const isMe = speaker === "我";
  let bubble = lastBubble[speaker];
  if (!bubble) {
    const row = document.createElement("div");
    row.className = "row " + (isMe ? "me" : "cust");
    row.innerHTML =
      `<div><div class="meta">${speaker} · ${t}</div>` +
      `<div class="bubble ${final ? "" : "partial"}"></div></div>`;
    chat.appendChild(row);
    bubble = row.querySelector(".bubble");
    lastBubble[speaker] = bubble;
  }
  bubble.textContent = text;
  bubble.classList.toggle("partial", !final);
  if (final) delete lastBubble[speaker]; // 下一句新建气泡
  chat.scrollTop = chat.scrollHeight;
}

function renderAnalysis(data) {
  if (!data) return;
  analysisBody.innerHTML = "";
  if (data._placeholder || data._error) {
    analysisBody.appendChild(card("提示", `<p>${data.summary || "无结果"}</p>`));
    if (!data._error) return;
  }
  if (data.summary && !data._placeholder)
    analysisBody.appendChild(card("整体复盘", `<p>${esc(data.summary)}</p>`, "summary"));
  if (data.objections?.length)
    analysisBody.appendChild(card("客户异议", list(data.objections.map(o =>
      `${esc(o.point)} <span class="tag">${esc(o.type || "")}</span>` +
      (o.quote ? `<div class="quote">“${esc(o.quote)}”</div>` : "")))));
  if (data.commitments?.length)
    analysisBody.appendChild(card("我的承诺", list(data.commitments.map(esc))));
  if (data.signals?.length)
    analysisBody.appendChild(card("成交信号", list(data.signals.map(esc))));
  if (data.coaching?.length)
    analysisBody.appendChild(card("话术复盘", list(data.coaching.map(c =>
      `${esc(c.moment)}<div class="quote">→ ${esc(c.better)}</div>`))));
  if (data.next_actions?.length)
    analysisBody.appendChild(card("下一步行动", list(data.next_actions.map(esc))));
}

function card(title, inner, extra = "") {
  const d = document.createElement("div");
  d.className = "card " + extra;
  d.innerHTML = `<h4>${title}</h4>${inner}`;
  return d;
}
function list(items) { return "<ul>" + items.map(i => `<li>${i}</li>`).join("") + "</ul>"; }
function esc(s) {
  return String(s ?? "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

// ── 按钮 ───────────────────────────────────────────
el("btnStart").onclick = () => {
  send({ type: "start" });
  recording = true;
  chat.innerHTML = ""; Object.keys(lastBubble).forEach(k => delete lastBubble[k]);
  el("btnStart").disabled = true; el("btnStop").disabled = false;
};
el("btnStop").onclick = () => {
  send({ type: "stop" });
  recording = false;
  el("btnStart").disabled = false; el("btnStop").disabled = true;
};
el("btnClear").onclick = () => {
  send({ type: "clear" });
  chat.innerHTML = `<div class="empty">已清空。</div>`;
  analysisBody.innerHTML = `<div class="empty">记录结束后点「生成复盘」。</div>`;
  el("qaAnswer").textContent = "";
  Object.keys(lastBubble).forEach(k => delete lastBubble[k]);
};
el("btnAnalyze").onclick = () => {
  analysisBody.innerHTML = `<div class="empty">正在生成复盘…</div>`;
  send({ type: "analyze" });
};
let suggestOn = false;
el("btnSuggest").onclick = () => {
  suggestOn = !suggestOn;
  el("btnSuggest").textContent = "💡 实时应答：" + (suggestOn ? "开" : "关");
  el("btnSuggest").classList.toggle("accent", suggestOn);
  el("btnSuggest").classList.toggle("ghost", !suggestOn);
  if (!suggestOn) el("suggestBar").classList.add("hidden");
  send({ type: "auto_suggest", on: suggestOn });
};
el("btnEnroll").onclick = () => {
  const enrolled = el("vpStatus").classList.contains("ok");
  const tip = "注册：请在接下来约 20 秒内自然说话（只说你自己），用于建立你的声纹。开始？";
  if (enrolled && !confirm("已有声纹，重新注册将覆盖。继续？")) return;
  if (!confirm(tip)) return;
  send({ type: "enroll_start" });
};
el("btnAsk").onclick = ask;
el("qaInput").addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });
function ask() {
  const q = el("qaInput").value.trim();
  if (!q) return;
  el("qaAnswer").textContent = "思考中…";
  send({ type: "ask", question: q });
}

connect();
