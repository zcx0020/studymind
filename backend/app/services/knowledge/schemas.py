"""knowledge/schemas.py —— 知识骨架的结构化输出契约"""
from typing import List, Literal

from pydantic import BaseModel, Field

EntityType = Literal["Concept", "Theorem", "Formula", "Algorithm", "Example", "ExamPoint"]
RelationType = Literal["PREREQUISITE_OF", "PART_OF", "DERIVES_FROM", "APPLIES_TO", "CONTRASTS_WITH"]


class Entity(BaseModel):
    """知识点实体（入库 Neo4j 节点 + PG knowledge_points + Chroma chunk）"""
    name: str = Field(description="知识点名称，2~12字的标准术语")
    type: EntityType
    definition: str = Field(description="具体定义或说明，30~100字，可独立阅读")
    importance: int = Field(ge=1, le=5, description="重要程度 1-5")
    difficulty: int = Field(ge=1, le=5, description="学习难度 1-5")


class Relation(BaseModel):
    """知识点关系（入库 Neo4j 边）"""
    source: str = Field(description="起点知识点名称，必须出现在 entities 中")
    target: str = Field(description="终点知识点名称，必须出现在 entities 中")
    type: RelationType
    reason: str = Field(description="为什么存在这条关系，一句话说明")


class KnowledgeSkeleton(BaseModel):
    """一个主题的完整知识骨架"""
    entities: List[Entity] = Field(min_length=1)
    relations: List[Relation] = Field(default_factory=list)
