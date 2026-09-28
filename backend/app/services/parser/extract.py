"""parser/extract.py —— LLM 从教材 chunk 抽取知识点实体与关系（PDF 路径）
复用 knowledge/schemas 的受控本体 —— 与无教材模式同构，图谱按 name 自动融合
"""
from typing import List

from langchain_core.prompts import ChatPromptTemplate

from app.services.knowledge.schemas import KnowledgeSkeleton
from app.services.llm import get_structured_llm

EXTRACT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是教育知识工程专家。从教材片段中抽取知识点实体及其关系。

## 实体类型（只能使用）
Concept / Theorem / Formula / Algorithm / Example / ExamPoint
## 关系类型（只能使用）
PREREQUISITE_OF / PART_OF / DERIVES_FROM / APPLIES_TO / CONTRASTS_WITH

## 规则
1. 实体名称使用教材原文术语，2~12字，不得改写
2. 只抽取原文明确支持的事实，禁止臆造
3. definition 逐字引用原文（≤80字）
4. importance / difficulty 按课程重要性与学习难度评估 1~5
5. 关系两端实体名必须出现在 entities 中"""),
    ("human", "## 教材片段（章节：{section}）\n{text}"),
])


def extract_from_chunks(chunks: List[dict], max_calls: int = 8) -> KnowledgeSkeleton:
    """按 chunk 批量抽取（长的优先，4 段/次），跨批次合并去重"""
    llm = get_structured_llm(KnowledgeSkeleton, temperature=0.1)
    picked = sorted(chunks, key=lambda c: -len(c["content"]))[: max_calls * 4]

    entities, relations = {}, []
    seen_rel = set()
    for i in range(0, len(picked), 4):
        batch = picked[i:i + 4]
        text = "\n\n".join(f"[{c['section_path']}] {c['content']}" for c in batch)
        sk: KnowledgeSkeleton = llm.invoke(EXTRACT_PROMPT.format(
            section=" / ".join(dict.fromkeys(c["section_path"] for c in batch)),
            text=text))
        for e in sk.entities:
            entities.setdefault(e.name, e)
        for r in sk.relations:
            key = (r.source, r.type, r.target)
            if key not in seen_rel and r.source in entities and r.target in entities:
                seen_rel.add(key)
                relations.append(r)
    return KnowledgeSkeleton(entities=list(entities.values()), relations=relations)
