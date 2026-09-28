"""quiz/grading.py —— 判分策略
客观题：规则判分（快、零成本、可解释）
主观题：LLM 按评分细则判分（rubric），返回分点扣分原因，供诊断引擎使用
"""
import re

from langchain_core.prompts import ChatPromptTemplate

from app.services.llm import get_structured_llm
from .schemas import GradingResult


def _normalize(s: str) -> str:
    return re.sub(r"[\s。.;；;]", "", str(s)).upper()


def grade_objective(qtype: str, correct: str, user: str) -> bool:
    if qtype == "multi_choice":              # 多选题：选项集合相等（顺序无关）
        return _normalize("".join(sorted(user))) == _normalize("".join(sorted(correct)))
    return _normalize(user) == _normalize(correct)   # 单选/判断/填空：归一化后精确匹配


RUBRIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是课程助教，按评分细则批改简答题。

## 批改要求
1. 对照评分要点逐条判断学生是否答到，每条给出针对性点评
2. score 为百分制；is_correct = score>=60
3. feedback 先肯定亮点再指出不足，语气鼓励，不超过80字"""),
    ("human", """## 题目
{stem}
## 参考答案与评分要点
{analysis}
## 学生作答
{user_answer}"""),
])


def grade_subjective(question: dict, user_answer: str) -> GradingResult:
    """主观题 LLM 判分"""
    llm = get_structured_llm(GradingResult, temperature=0.1)
    return llm.invoke(RUBRIC_PROMPT.format(
        stem=question["stem"], analysis=question["analysis"],
        user_answer=user_answer))
