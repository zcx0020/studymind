/**
 * 可视化色板 —— 来自 dataviz 参考调色板（已通过 CVD/对比度校验脚本）
 * 规则:
 *  - 类型色为分类编码，固定顺序、永不轮换；颜色必须搭配形状/文字标签（次级编码）
 *  - 状态色仅表达"掌握状态"，必须搭配文字标签
 */

// 分类色（6 个知识点类型，固定槽位顺序）
export const CATEGORICAL = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300']

// 状态色（固定，勿挪作系列色）
export const STATUS = {
  good: '#0ca30c',      // 已掌握
  warning: '#fab219',   // 学习中
  serious: '#ec835a',   // 薄弱
  critical: '#d03b3b',  // 严重薄弱
}

// 文字与底面色（图表墨水）
export const INK = {
  primary: '#0b0b0b',
  secondary: '#52514e',
  muted: '#898781',
  grid: '#e1e0d9',
  baseline: '#c3c2b7',
  surface: '#fcfcfb',
}

// 顺序色（数值大小）：蓝，单一色相
export const SEQ_BLUE = '#2a78d6'

// 实体类型 → 颜色槽位 / 形状（颜色 + 形状双编码）
export const TYPE_COLOR: Record<string, string> = {
  Concept: CATEGORICAL[0],
  Theorem: CATEGORICAL[1],
  Formula: CATEGORICAL[2],
  Algorithm: CATEGORICAL[3],
  Example: CATEGORICAL[4],
  ExamPoint: CATEGORICAL[5],
}

export const TYPE_SHAPE: Record<string, string> = {
  Concept: 'circle',
  Theorem: 'rect',
  Formula: 'diamond',
  Algorithm: 'star',
  Example: 'triangle',
  ExamPoint: 'ellipse',
}

// 关系类型 → 中文短标签（边上展示）
export const REL_LABEL: Record<string, string> = {
  PREREQUISITE_OF: '前置',
  PART_OF: '包含',
  DERIVES_FROM: '推导',
  APPLIES_TO: '应用',
  CONTRASTS_WITH: '对比',
}
