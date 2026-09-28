"""plan/topo.py —— 拓扑分层与任务装箱（纯算法，无 I/O，可单元测试）
保障：任何知识点的前置，所在天一定 ≤ 该知识点所在天（拓扑序天然满足）
"""
from typing import Dict, List, Tuple


def topological_layers(names: List[str],
                       prereq_pairs: List[Tuple[str, str]],
                       priority: Dict[str, int]) -> Tuple[List[List[str]], List[str]]:
    """Kahn 分层拓扑排序。
    prereq_pairs: [(前置名, 后继名)]，即 PREREQUISITE_OF 的 (a, b)
    priority: 排序键（importance 越高越靠前），保证同层输出稳定
    返回 (layers, leftovers)；leftovers 非空说明图中有环 → 降级为同层并告警
    """
    succ: Dict[str, List[str]] = {n: [] for n in names}
    indeg: Dict[str, int] = {n: 0 for n in names}
    for a, b in prereq_pairs:
        if a not in names or b not in names or a == b:
            continue
        succ[a].append(b)
        indeg[b] += 1

    layers, done = [], set()
    while True:
        layer = sorted((n for n in names if n not in done and indeg[n] == 0),
                       key=lambda n: -priority.get(n, 3))
        if not layer:
            break
        layers.append(layer)
        for n in layer:
            done.add(n)
            for m in succ[n]:
                indeg[m] -= 1

    leftovers = [n for n in names if n not in done]
    if leftovers:                      # 环内节点降级为同层，计划仍可生成
        layers.append(sorted(leftovers, key=lambda n: -priority.get(n, 3)))
    return layers, leftovers


def pack_days(layers: List[List[str]],
              prereq_map: Dict[str, List[str]],
              kp_info: Dict[str, Tuple[int, int]],
              total_days: int, minutes_per_day: int,
              max_per_day: int = 5) -> Dict[str, int]:
    """把分层知识点贪心装箱到 total_days 天。
    kp_info: {name: (importance, difficulty)}；估算时长 est = min(8 + difficulty*3, 12) 分钟
    硬约束: 每天最多 max_per_day 个知识点 + 分钟容量；两者都满则顺延下一天
    （调用方必须先按容量计算好 total_days，兜底分支只在极端情况下触发）
    返回 {name: day_index(1-based)}
    """
    est = {n: min(8 + kp_info[n][1] * 3, 12) for n in kp_info}
    cap = [minutes_per_day] * total_days
    cnt = [0] * total_days
    kp_day: Dict[str, int] = {}

    for layer in layers:                     # 层内已按 importance 降序
        for n in layer:
            need = est[n]
            prereq_days = [kp_day[p] for p in prereq_map.get(n, []) if p in kp_day]
            start_day = max(prereq_days, default=1)
            for d in range(start_day - 1, total_days):
                if cnt[d] >= max_per_day:    # 每日数量上限
                    continue
                if cap[d] >= need:
                    kp_day[n] = d + 1
                    cap[d] -= need
                    cnt[d] += 1
                    break
            else:
                # 兜底：正常情况不会走到（调用方已按容量延期）；放最后一天并计数
                kp_day[n] = total_days
                cnt[total_days - 1] += 1
    return kp_day


# ── 单元测试示例（pytest，体现"算法层可验证"） ──
def test_topo_layers():
    layers, left = topological_layers(
        ["A", "B", "C"], [("A", "B"), ("B", "C")], {"A": 5, "B": 3, "C": 4})
    assert layers == [["A"], ["B"], ["C"]] and left == []


def test_cycle_fallback():
    layers, left = topological_layers(
        ["A", "B"], [("A", "B"), ("B", "A")], {"A": 5, "B": 3})
    assert left == ["A", "B"]               # 环被降级为同层，不崩溃
