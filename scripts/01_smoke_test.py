"""01_smoke_test.py —— 零依赖冒烟测试（不需要 pip 安装任何库）
验证: ① DeepSeek API key 有效  ② JSON 结构化输出可用（骨架生成的真实业务路径）
用法: cd studymind && python3 scripts/01_smoke_test.py
"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> dict:
    """极简 .env 解析，避免冒烟测试引入任何第三方依赖"""
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


env = load_env()
KEY = env["DEEPSEEK_API_KEY"]
BASE = env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = env.get("DEEPSEEK_MODEL", "deepseek-chat")


def chat(messages, max_tokens=512, json_mode=False) -> str:
    body = {"model": MODEL, "messages": messages,
            "max_tokens": max_tokens, "temperature": 0.3}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        BASE.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    # 测试① 连通性
    ping = chat([{"role": "user", "content": "只回复两个字：正常"}], max_tokens=10)
    print(f"① API 连通性: {ping}  (模型 {MODEL})")

    # 测试② 骨架生成（与 knowledge/skeleton.py 同款结构化输出路径）
    out = chat([{"role": "user", "content": """你是课程教研专家。为"数据结构"主题生成3个知识点骨架。
输出严格JSON，格式: {"entities":[{"name":"...","type":"Concept","definition":"...","importance":5,"difficulty":2}]}
实体类型只能取 Concept/Theorem/Formula/Algorithm/Example/ExamPoint。"""}],
        max_tokens=800, json_mode=True)
    sk = json.loads(out)
    print(f"② 骨架生成: 收到 {len(sk['entities'])} 个知识点")
    for e in sk["entities"]:
        print(f"   - [{e['type']}] {e['name']} (重要度{e['importance']}/难度{e['difficulty']})")

    print("\n✅ 冒烟测试通过：key 有效，结构化 JSON 输出可用")
