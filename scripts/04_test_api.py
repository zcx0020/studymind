"""04_test_api.py —— API 端到端测试（零依赖，仅用标准库）
前置: API 已启动  cd backend && uvicorn app.main:app --port 8000
验证: 生成知识库 → 学习计划 → 异步出题 → 提交答案(触发诊断) →
      最后一题触发异步总结 → 掌握度
用法: python3 scripts/04_test_api.py
"""
import json
import time
import urllib.request

BASE = "http://localhost:8000"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=300) as resp:
        return json.loads(resp.read())


def wait_task(task_id, timeout=300):
    """轮询任务状态（答题模块统一入口 /api/task_status/{id}）"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = req("GET", f"/api/task_status/{task_id}")
        if t["status"] in ("done", "failed"):
            return t
        print(f"   [{t['status']}] {t['stage']} ({t['progress']}%)")
        time.sleep(5)
    raise TimeoutError("任务超时")


if __name__ == "__main__":
    print("① 生成知识库（数据结构 · 二叉树）...")
    t = wait_task(req("POST", "/api/knowledge/generate",
                      {"subject": "数据结构", "topic": "二叉树"})["task_id"])
    if t["status"] == "failed":
        raise RuntimeError(t["error"])
    doc_id = t["result"]["doc_id"]
    print(f"   ✅ doc_id={doc_id}, {t['result']['entities']} 知识点, "
          f"{t['result']['relations']} 条关系")

    print("② 生成学习计划...")
    t = wait_task(req("POST", "/api/plans/generate",
                      {"document_id": doc_id, "total_days": 7})["task_id"])
    if t["status"] == "failed":
        raise RuntimeError(t["error"])
    plan_id = t["result"]["plan_id"]
    print(f"   ✅ plan_id={plan_id}")

    print("③ 今日任务（异步出题任务 + 轮询，前端不阻塞）...")
    task_id = req("POST", "/api/quiz/task",
                  {"mode": "today", "plan_id": plan_id})["task_id"]
    t = wait_task(task_id)
    if t["status"] == "failed":
        raise RuntimeError(t["error"])
    quiz = t["result"]["payload"]
    n_q = sum(len(it["questions"]) for it in quiz["items"])
    all_qids = [q["id"] for it in quiz["items"] for q in it["questions"]]
    print(f"   ✅ Day{quiz['day_index']}, {len(quiz['items'])} 个知识点, {n_q} 题")
    for it in quiz["items"][:2]:
        print(f"      - {it['name']}: {it['questions'][0]['stem'][:36]}...")

    print("④ 提交错误答案（触发异步诊断 + 异步总结）...")
    qid = quiz["items"][0]["questions"][0]["id"]
    t0 = time.time()
    r = req("POST", "/api/submit_answer",
            {"question_id": qid, "user_answer": "完全错误的答案",
             "is_last": True, "question_ids": all_qids, "duration_sec": 30})
    elapsed = time.time() - t0
    print(f"   判分: {'✓' if r['is_correct'] else '✗'}, "
          f"θ={r['mastery']['theta']}（Δ{r['mastery']['delta']}）, "
          f"接口耗时 {elapsed:.2f}s")
    assert elapsed < 2, "提交接口超过 2 秒，违反亚秒契约"

    if r.get("diagnosis_task_id"):
        d = wait_task(r["diagnosis_task_id"])
        if d["status"] == "done":
            print(f"   [诊断] 根因: {d['result']['root_cause']}")
            print(f"   [诊断] 补学路径: {' → '.join(d['result']['remedy_path'][:3])}...")
            print(f"   [计划] 调整 {len(d['result']['changes'])} 条: "
                  f"{[c['action'] for c in d['result']['changes']]}")

    if r.get("summary_task_id"):
        s = wait_task(r["summary_task_id"])
        if s["status"] == "done":
            print(f"   [总结] 正确率 {s['result']['accuracy']}%, "
                  f"薄弱点 {s['result']['weak_names']}, "
                  f"Elo 变化 {[(k['name'], k['theta_before'], k['theta_after']) for k in s['result']['kps']]}")

    print("⑤ 掌握度接口...")
    m = req("GET", f"/api/mastery/{doc_id}")
    sample = m["items"][0]
    print(f"   ✅ {len(m['items'])} 条, 示例: {sample['name']} θ={sample['theta']}")

    print("\n✅ API 端到端测试通过")
