"""quiz/schemas.py —— 主观题判分的结构化输出契约
（出题的 QuizQuestion 契约定义在 rag/adaptive_quiz.py，避免两处定义漂移）
"""
from typing import List

from pydantic import BaseModel, Field


class GradingPoint(BaseModel):
    point: str = Field(description="评分要点")
    student_covered: bool = Field(description="学生是否答到该要点")
    comment: str = Field(description="一句话点评")


class GradingResult(BaseModel):
    """主观题判分结果"""
    score: int = Field(ge=0, le=100)
    is_correct: bool = Field(description="score>=60 视为正确")
    feedback: str = Field(description="评语，指出亮点与不足")
    points: List[GradingPoint] = Field(default_factory=list)
