"""knowledge/skeleton.py —— 把 (科目, 主题) 变成结构化知识骨架（无教材模式入口）
LLM 的通用领域知识在这里被"结构化"成可检索、可规划、可出题的知识库
"""
from langchain_core.prompts import ChatPromptTemplate

from app.services.llm import get_structured_llm
from .schemas import KnowledgeSkeleton

SKELETON_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是大学课程教研专家，负责为学习系统构建主题知识骨架。

## 任务
基于你的领域知识，为给定主题生成一套知识点体系，包含实体与关系。

## 实体类型（只能使用）
Concept(核心概念) / Theorem(定理) / Formula(公式) / Algorithm(方法) / Example(经典案例) / ExamPoint(高频考点)

## 关系类型（只能使用）
PREREQUISITE_OF(前置依赖) / PART_OF(组成部分) / DERIVES_FROM(推导关系) / APPLIES_TO(应用于) / CONTRASTS_WITH(易混淆对比)

## 生成规则
1. 数量：{min_entities}~{max_entities} 个知识点，覆盖该主题从入门到进阶的完整脉络
2. 结构：主干知识点之间用 PREREQUISITE_OF 串联成清晰的学习顺序，整体必须是有向无环图（禁止循环依赖，如 A→B→A）
3. 层次：难度分布合理（约40%为1-2级基础、40%为3级、20%为4-5级进阶），importance≥4 的应是该主题公认核心
4. 每个 definition 必须具体可检索，能独立支撑出题（不写"XX是重要概念"这类空话）
5. 关系两端实体名必须与 entities 中的 name 完全一致
6. 知识范围以大学本科课程为准，不超出该主题公认内容"""),
    ("human", "科目：{subject}\n主题：{topic}"),
])


def generate_skeleton(subject: str, topic: str,
                      min_entities: int = 12, max_entities: int = 25) -> KnowledgeSkeleton:
    """生成骨架。返回前自检：关系中引用了不存在的实体则自愈重试"""
    llm = get_structured_llm(KnowledgeSkeleton, temperature=0.3)
    broken = []
    for _ in range(3):
        sk: KnowledgeSkeleton = llm.invoke(SKELETON_PROMPT.format(
            subject=subject, topic=topic,
            min_entities=min_entities, max_entities=max_entities))
        names = {e.name for e in sk.entities}
        broken = [r for r in sk.relations
                  if r.source not in names or r.target not in names]
        if not broken:
            return sk
    raise RuntimeError(f"骨架生成连续失败：{len(broken)} 条悬空关系")
