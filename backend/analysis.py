"""销售复盘分析：把对话文字喂给大模型，产出结构化结果。
留空 API key 时返回占位示例，保证 UI 链路可跑。"""
import json
import config

SYSTEM_PROMPT = """你是资深销售教练。下面是一段销售与客户的对话（已区分"我"=销售本人，"客户"=对方）。
请从销售视角分析，只输出 JSON，字段如下：
{
  "objections":   [{"point": "客户的异议/顾虑", "quote": "对应原话", "type": "价格|竞品|信任|决策权|需求|其它"}],
  "commitments":  ["我方做出的每一条承诺（折扣/交期/功能/赠送等）"],
  "signals":      ["成交信号：预算/决策人/采购时间/试用意向等关键信息"],
  "coaching":     [{"moment": "我可能说得不好的地方", "better": "更好的话术建议"}],
  "next_actions": ["下一步具体跟进事项"],
  "summary":      "三句话以内的整体复盘"
}
只输出 JSON，不要多余文字。"""

QA_SYSTEM = """你是销售复盘助手。基于下面这段已转写的对话（"我"=销售本人，"客户"=对方）回答用户的问题，简洁直接，必要时引用原话。"""


def _dialogue_to_text(dialogue):
    return "\n".join(f'[{d.get("t","")}] {d["speaker"]}: {d["text"]}' for d in dialogue)


def _placeholder(dialogue):
    return {
        "objections": [{"point": "（示例）配置大模型后这里显示真实异议分析", "quote": "", "type": "其它"}],
        "commitments": ["（示例）我答应的事项会逐条列在这里"],
        "signals": ["（示例）客户预算/决策人/时间等信号"],
        "coaching": [{"moment": "（示例）说得不好的地方", "better": "更好的话术"}],
        "next_actions": ["（示例）下一步跟进事项"],
        "summary": "未配置大模型，当前为占位结果。在 config.py 或环境变量中设置 LLM_API_KEY 后即生效。",
        "_placeholder": True,
    }


def _call_llm(system, user):
    """统一调用入口，兼容 OpenAI 接口与 Anthropic。"""
    if config.LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=config.LLM_API_KEY,
                                     base_url=config.LLM_BASE_URL or None)
        resp = client.messages.create(
            model=config.LLM_MODEL, max_tokens=2000,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text
    # 默认走 OpenAI 兼容（DeepSeek / 通义 / Ollama 均可）
    from openai import OpenAI
    client = OpenAI(api_key=config.LLM_API_KEY or "sk-none",
                    base_url=config.LLM_BASE_URL or None)
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content


def analyze(dialogue):
    """生成销售复盘报告。dialogue: [{t, speaker, text}, ...]"""
    if not dialogue:
        return {"summary": "还没有对话内容。", "_placeholder": True}
    if not (config.LLM_PROVIDER and config.LLM_API_KEY) and config.LLM_PROVIDER != "openai":
        # 没配置 key 时返回占位（Ollama 本地可不需要真实 key，故 provider=openai 放行）
        if not config.LLM_BASE_URL:
            return _placeholder(dialogue)
    try:
        raw = _call_llm(SYSTEM_PROMPT, _dialogue_to_text(dialogue))
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)
    except Exception as e:
        return {"summary": f"分析调用失败：{e}", "_error": True}


SUGGEST_SYSTEM = """你是销售实时助手。下面是销售("我")与客户的对话，客户刚说完最新一轮。
请针对客户最新的话/提问，给"我"一句可以直接说出口的应答建议：自然、专业、推进成交。
只输出建议的话术本身，一两句话，不要解释、不要前缀。"""


def suggest_reply(dialogue):
    """针对客户最新一轮，生成一条可直接说的建议话术。"""
    if not dialogue:
        return ""
    # 没配大模型时给一条通用兜底建议，保证实时应答可演示
    if not (config.LLM_API_KEY or config.LLM_BASE_URL):
        last = next((d for d in reversed(dialogue) if d["speaker"] == "客户"), None)
        if not last:
            return ""
        return f"（示例建议·配置大模型后变真实）针对「{last['text'][:20]}…」可先共情认同，再用具体方案回应并反问需求。"
    try:
        return _call_llm(SUGGEST_SYSTEM, _dialogue_to_text(dialogue)).strip()
    except Exception as e:
        return f"（应答建议失败：{e}）"


def ask(dialogue, question):
    """基于对话回答用户提问。"""
    if not (config.LLM_API_KEY or config.LLM_BASE_URL):
        return "未配置大模型，无法问答。请在 config.py 设置 LLM_API_KEY。"
    try:
        user = f"对话记录：\n{_dialogue_to_text(dialogue)}\n\n问题：{question}"
        return _call_llm(QA_SYSTEM, user)
    except Exception as e:
        return f"问答调用失败：{e}"
