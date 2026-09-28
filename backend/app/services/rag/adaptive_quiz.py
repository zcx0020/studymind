"""rag/adaptive_quiz.py —— 动态RAG与自适应出题
- HybridRetriever: 向量+BM25 融合 → RRF → 重排（有教材路径）
- ChromaRetriever: 无教材路径的最小检索器（知识库 = 生成的知识点定义）
- AdaptiveQuizService: Elo 难度匹配 + 个性化出题 + 质量门禁
- run_diagnosis: GraphRAG 根因诊断（M6 动态调整引擎用）
"""
import json
from typing import List

import jieba
from FlagEmbedding import FlagReranker
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from app.services.llm import get_embedder, get_structured_llm


# ══════════════ 1. 掌握度模型（Elo 数学部分，全项目唯一实现） ══════════════

def difficulty_to_elo(difficulty: int) -> float:
    """题目难度(1~5)映射到 Elo 量表：难度3=1500，与初始掌握度对齐"""
    return 1200.0 + difficulty * 100.0


def elo_update(theta: float, beta: float, correct: bool, K: float = 32.0) -> float:
    """知识点掌握度 θ 与题目难度 β 双参数更新（θ、β 必须同处 Elo 量表）"""
    p = 1.0 / (1.0 + 10 ** ((beta - theta) / 400))
    return theta + K * (int(correct) - p)


def pick_difficulty(theta: float, target_p: float = 0.7) -> int:
    """按"心流区"匹配难度：选 P(答对)≈0.7 的题目难度（1~5）"""
    best, best_gap = 3, 9.9
    for d in range(1, 6):
        beta = difficulty_to_elo(d)
        p = 1.0 / (1.0 + 10 ** ((beta - theta) / 400))
        if abs(p - target_p) < best_gap:
            best, best_gap = d, abs(p - target_p)
    return best


# ══════════════ 2. 输出契约 ══════════════

class QuizQuestion(BaseModel):
    """LLM 出题结果（与 questions 表字段对应）"""
    stem: str
    options: List[str] = Field(default_factory=list)
    answer: str
    analysis: str = Field(description="解析必须引用教材原文并说明解题思路")
    difficulty: int = Field(ge=1, le=5)
    bloom: str = Field(description="记忆/理解/应用/分析")


class DiagnosisResult(BaseModel):
    """GraphRAG 根因诊断结果"""
    root_cause: str = Field(description="前置基础缺失/概念混淆/练习不足/难度跳跃过大")
    evidence: List[str] = Field(default_factory=list)
    remedy_path: List[str] = Field(default_factory=list,
                                   description="按前置依赖从基础到当前的补学顺序")
    confused_concepts: List[str] = Field(default_factory=list,
                                         description="易混淆概念，供出题设计干扰项")
    next_strategy: dict = Field(description="出题策略，如 {'difficulty':2,'bloom':'理解'}")


# ══════════════ 3. 混合检索器（有教材路径：向量+BM25 → RRF → 重排） ══════════════

class HybridRetriever:
    """向量检索（语义）+ BM25（术语/公式关键词）融合检索。
    图检索用于诊断路径（run_diagnosis 直接 Cypher 查询），正文检索不做图融合。
    """

    def __init__(self, doc_id: int, pg_conn, milvus_client, neo4j_driver):
        self.doc_id = doc_id
        self.pg_conn = pg_conn
        self.milvus = milvus_client
        self.driver = neo4j_driver
        self.embedder = get_embedder()
        self.reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)

        with pg_conn.cursor() as cur:
            cur.execute("""SELECT id, section_path, content FROM chunks
                           WHERE document_id=%s AND chunk_type='text'""", (doc_id,))
            rows = cur.fetchall()
        self.corpus = [(r[0], r[1], r[2]) for r in rows]
        self._text_by_id = {r[0]: r[2] for r in rows}
        self.bm25 = BM25Okapi([list(jieba.cut(t)) for _, _, t in self.corpus])

        with pg_conn.cursor() as cur:
            cur.execute("SELECT id, parent_id FROM chunks WHERE document_id=%s", (doc_id,))
            self._parent = dict(cur.fetchall())

    def _vector_search(self, q: str, topk: int = 20) -> List[tuple]:
        qv = self.embedder.encode(q, normalize_embeddings=True).tolist()
        hits = self.milvus.search("chunks", data=[qv], limit=topk,
                                  filter=f"document_id == {self.doc_id}",
                                  output_fields=["chunk_id"])
        return [(h["entity"]["chunk_id"], h["distance"]) for h in hits[0]]

    def _bm25_search(self, q: str, topk: int = 20) -> List[tuple]:
        scores = self.bm25.get_scores(list(jieba.cut(q)))
        ranked = sorted(enumerate(scores), key=lambda x: -x[1])[:topk]
        return [(self.corpus[i][0], s) for i, s in ranked]

    @staticmethod
    def rrf(ranked_lists: List[List[tuple]], k: int = 60) -> List[tuple]:
        """倒数排名融合（Reciprocal Rank Fusion）"""
        scores = {}
        for lst in ranked_lists:
            for rank, (cid, _) in enumerate(lst):
                scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        return sorted(scores.items(), key=lambda x: -x[1])

    def corpus_by_id(self, cid: int) -> str:
        return self._text_by_id.get(cid, "")

    def parent_of(self, cid: int) -> dict:
        """小chunk命中 → 返回父chunk（完整小节）作为生成上下文"""
        pid = self._parent.get(cid)
        if pid:
            with self.pg_conn.cursor() as cur:
                cur.execute("SELECT content FROM chunks WHERE id=%s", (pid,))
                row = cur.fetchone()
            if row:
                return {"content": row[0]}
        return {"content": self.corpus_by_id(cid)}

    def retrieve(self, q: str, top_n: int = 5) -> List[dict]:
        fused = self.rrf([self._vector_search(q), self._bm25_search(q)])
        pairs = [(q, self.corpus_by_id(cid)) for cid, _ in fused[:20]]
        scores = self.reranker.compute_score(pairs, normalize=True)
        top_ids = [fused[i][0] for i in sorted(range(len(scores)),
                                                key=lambda i: -scores[i])[:top_n]]
        return [self.parent_of(cid) for cid in top_ids]


# ══════════════ 4. Chroma 检索器（无教材模式） ══════════════

class ChromaRetriever:
    """知识库 = 知识点定义/教材原文（Chroma collection），与有教材路径同构。
    集合不存在时优雅降级为空上下文（出题仍可用，仅检索上下文为空）"""

    def __init__(self, chroma_client, collection_name: str, embedder):
        self.col = None
        try:
            self.col = chroma_client.get_collection(collection_name)
        except Exception:
            self.col = None
        self.embedder = embedder

    def retrieve(self, q: str, top_n: int = 5) -> List[dict]:
        if self.col is None:
            return []
        hits = self.col.query(
            query_embeddings=[self.embedder.encode(q).tolist()],
            n_results=top_n)
        return [{"content": d} for d in hits["documents"][0]]


# ══════════════ 5. 个性化出题 Prompt 与服务 ══════════════

QUIZ_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是《{course}》课程出题专家。基于给定教材内容生成一道练习题。

## 出题要求
- 题型: {qtype}，难度: {difficulty}/5，认知层次: {bloom}
- 题干必须基于教材内容，可变换情境，不得杜撰教材未涉及的知识
- 解析必须引用教材原文，并说明解题思路
- 干扰项优先取材于学生曾出错的易混淆概念: {confused_concepts}（增强个性化）
- 若题型为选择题，答案必须来自选项之一
- 若"已出过的题目"非空，必须更换考查角度（换情境/换考法/换提问切入点），严禁雷同"""),
    ("human", """## 目标知识点: {knowledge_point}
## 教材内容
{context}
## 该知识点已出过的题目
{existing_questions}
## 出题角度要求
{angle_hint}"""),
])


def _coerce_choice_answer(q: QuizQuestion) -> bool:
    """把 LLM 返回的答案归一化为选项字母，兼容常见写法:
    "B" / "b." / "(B)" / "B. 过拟合" / "选项B" / 完整选项文本
    """
    letters = "ABCDEFGH"
    if not q.options or len(q.options) > len(letters):
        return False
    ans = (q.answer or "").strip().strip("。.；; ")
    n = len(q.options)
    # ① 纯字母
    if ans.upper() in letters[:n]:
        q.answer = ans.upper()
        return True
    # ② "A. xxx" / "B) xxx" / "C、xxx"
    if len(ans) >= 2 and ans[0].upper() in letters[:n] and ans[1] in ".。、)）:：":
        q.answer = ans[0].upper()
        return True
    # ③ 短文本中唯一的选项字母（如"选项B"）
    if len(ans) <= 6:
        found = [c for c in ans.upper() if c in letters[:n]]
        if len(found) == 1:
            q.answer = found[0]
            return True
    # ④ 答案即选项完整文本（或其开头）
    for i, opt in enumerate(q.options):
        if opt and (opt.strip() == ans or ans.startswith(opt.strip()[:10])):
            q.answer = letters[i]
            return True
    return False


class AdaptiveQuizService:
    """自适应出题：Elo 心流匹配难度 + 个性化 Prompt + 质量门禁"""

    def __init__(self, retriever):
        self.retriever = retriever
        self.embedder = get_embedder()
        self.llm = get_structured_llm(QuizQuestion, temperature=0.5)  # 适度温度促多样性

    def _max_similarity(self, stems: list, stem: str) -> float:
        """与已有题干的最大向量相似度（0~1）；无题库返回 0"""
        if not stems:
            return 0.0
        import numpy as np
        sim = self.embedder.encode([stem], normalize_embeddings=True) @ \
            self.embedder.encode(stems, normalize_embeddings=True).T
        return float(sim[0].max())

    def generate(self, user_id: int, kp: dict, theta: float,
                 diagnosis: dict | None = None, qtype: str = "single_choice",
                 pg_conn=None, existing_stems: list | None = None) -> QuizQuestion:
        # ① 难度：Elo 心流匹配，再叠加诊断策略（根因"基础缺失"则再降1级）
        difficulty = pick_difficulty(theta)
        bloom = diagnosis["next_strategy"].get("bloom", "理解") if diagnosis else "理解"
        if diagnosis and diagnosis.get("root_cause") == "前置基础缺失":
            difficulty = max(1, difficulty - 1)

        # ② 检索上下文（自适应RAG）：名称+定义联合查询，对教材原文与生成定义两种知识库都有效
        query = kp["name"] if not kp.get("definition") else f"{kp['name']}：{kp['definition']}"
        context = self.retriever.retrieve(query, top_n=5)
        confused = diagnosis.get("confused_concepts", []) if diagnosis else []

        # ②b 已有题干：既作为去重依据，也注入 Prompt 促使模型换角度出题
        stems = list(existing_stems or [])
        if not stems and pg_conn is not None:
            with pg_conn.cursor() as cur:
                cur.execute("""SELECT stem FROM questions
                               WHERE knowledge_point_id=%s LIMIT 50""",
                            (kp["kp_id"],))
                stems = [r[0] for r in cur.fetchall()]

        # ③ 生成 + 质量门禁 + 自愈重试
        #    每次重试注入"换角度"指令提升多样性；去重连续失败时退化为
        #    "接受最不相似的一题"——绝不让门禁把出题接口打挂（窄知识点角度有限）
        #    性能关键：题干向量只算一次（此前每次重试都全量重算 → 单题 30s+ 的"卡死"主因）
        import numpy as np
        stem_vecs = (self.embedder.encode(stems, normalize_embeddings=True)
                     if stems else None)

        def max_sim(new_stem: str) -> float:
            nonlocal stem_vecs
            if stem_vecs is None or len(stem_vecs) == 0:
                return 0.0
            v = self.embedder.encode([new_stem], normalize_embeddings=True)
            return float((v @ stem_vecs.T).max())

        angles = ["", "请换一个完全不同的情境（如生活化场景）出题",
                  "请改为综合应用/计算题形式", "请从易错辨析的角度出题"]
        reasons = []
        best_q, best_sim = None, 2.0
        for attempt in range(5):
            q: QuizQuestion = self.llm.invoke(QUIZ_PROMPT.format(
                course=kp.get("course") or kp.get("name", ""), qtype=qtype,
                difficulty=difficulty, bloom=bloom,
                confused_concepts="、".join(confused) or "无",
                knowledge_point=kp["name"],
                context="\n\n".join(c["content"] for c in context),
                existing_questions="\n".join(f"- {s}" for s in stems[-10:]) or "（无）",
                angle_hint=angles[attempt % len(angles)]))
            # 数据清洗：LLM 可能返回 options=null 或含空项，统一为干净列表
            q.options = [o for o in (q.options or []) if o and str(o).strip()]
            if qtype == "single_choice" and not _coerce_choice_answer(q):
                reasons.append(f"答案无法映射到选项: {q.answer!r}")
                continue
            sim = max_sim(q.stem)
            if sim < best_sim:
                best_q, best_sim = q, sim
            if sim <= 0.95:
                v = self.embedder.encode([q.stem], normalize_embeddings=True)
                stem_vecs = v if stem_vecs is None else np.vstack([stem_vecs, v])
                stems.append(q.stem)      # 本次会话内同样参与去重
                return q
            reasons.append(f"题干重复(sim={sim:.2f}): {q.stem[:26]}...")
        if best_q is not None and best_sim <= 0.98:
            # 退化兜底：接受最不相似的一题，保证接口可用
            stems.append(best_q.stem)
            return best_q
        raise RuntimeError(f"出题质量门禁连续失败: {'; '.join(reasons)}")


# ══════════════ 6. GraphRAG 根因诊断 ══════════════

DIAGNOSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是学习诊断专家。根据答题数据与知识图谱邻域信息，诊断学习障碍根因。

## 分析要求
1. 根因类型判定: 前置基础缺失 / 概念混淆(CONTRASTS_WITH) / 练习不足 / 难度跳跃过大
2. 按 PREREQUISITE_OF 依赖关系给出从最基础前置开始的补学路径；remedy_path 每项必须是图谱邻域中出现的知识点名称，只写名称本身（如"假设函数"），禁止附带解释文字
3. 给出下一阶段出题策略（难度/认知层次）
4. 列出学生可能混淆的概念对，供出题时设计干扰项"""),
    ("human", """## 近期答题记录
{recent_answers}
## 薄弱点 "{weak_kp}" 的知识图谱邻域(含掌握度0-1)
{graph_subgraph}"""),
])


def run_diagnosis(user_id: int, weak_kp_name: str, theta_map: dict,
                  driver, pg_conn) -> DiagnosisResult:
    """拉取薄弱点2跳子图 → LLM诊断 → 返回结构化结果（调用方负责落库 diagnosis_reports）"""
    records, _, _ = driver.execute_query("""
        MATCH (n {name: $kp})-[r*1..2]-(m)
        RETURN n, r, m LIMIT 40""", kp=weak_kp_name)
    subgraph = [{"node": rec["m"]["name"],
                 "mastery": theta_map.get(rec["m"]["name"], 0.0)}
                for rec in records]

    with pg_conn.cursor() as cur:
        cur.execute("""SELECT q.stem, r.is_correct, r.user_answer, r.created_at
                       FROM quiz_records r JOIN questions q ON q.id = r.question_id
                       WHERE r.user_id=%s ORDER BY r.created_at DESC LIMIT 10""",
                    (user_id,))
        cols = [d[0] for d in cur.description]
        recent = [dict(zip(cols, r)) for r in cur.fetchall()]

    llm = get_structured_llm(DiagnosisResult, temperature=0.1)
    return llm.invoke(DIAGNOSIS_PROMPT.format(
        recent_answers=json.dumps(recent, ensure_ascii=False, default=str),
        weak_kp=weak_kp_name,
        graph_subgraph=json.dumps(subgraph, ensure_ascii=False)))
