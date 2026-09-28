/**
 * 演示用假数据层（Mock）
 * 目的：让看板/图谱有"行动指引"效果——未作答的知识点按序分配 θ
 * （1200 薄弱 / 1600 学习中 / 1800 已掌握），并提供错题列表与 AI 诊断文案。
 * 接入真实数据时，把调用点替换为对应 API 返回即可（答题记录在 quiz_records 表）。
 */

function hash(s: string): number {
  let h = 0
  for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return h
}

/** 未作答知识点按序分配 θ（高低起伏更真实：简单 1800+ / 中等 1500+ / 困难 1100-1300，
 *  带确定性抖动，条形有长有短、颜色红蓝绿交错） */
export function mockTheta(index: number): number {
  const base = [1850, 1520, 1180, 1680, 1240, 1580, 1900, 1450, 1150, 1620][index % 10]
  return base + ((index * 37) % 50) - 25
}

const WRONG_POOL = [
  {
    stem: '在求解特征值时，若特征方程存在重根，正确的做法是？',
    wrong: '重根只算一个特征值，无需特殊处理',
    correct: '重根按重数计入，并分别验证对应的特征向量空间',
  },
  {
    stem: '关于矩阵可对角化的判定，下列说法正确的是？',
    wrong: '任意方阵都可以对角化',
    correct: '仅当每个特征值的几何重数等于代数重数时才可对角化',
  },
  {
    stem: '计算属于 λ 的特征向量时，下列步骤错误的是？',
    wrong: '直接取齐次方程组 (λI−A)x=0 的任意一个解作为特征向量',
    correct: '取基础解系中非零向量的线性组合（排除零向量）',
  },
  {
    stem: '关于奇异值分解 A=UΣVᵀ，下列说法错误的是？',
    wrong: 'U 与 V 可以是任意正交矩阵',
    correct: 'U 的列是 AAᵀ 的特征向量，V 的列是 AᵀA 的特征向量',
  },
]

/** 该知识点的历史错题（确定性生成 0~3 道：薄弱2-3道/学习中1道/已掌握0道） */
export function mockWrongQuestions(kpName: string, theta: number) {
  const n = theta > 1700 ? 0 : theta < 1500 ? 2 + (hash(kpName) % 2) : 1
  const start = hash(kpName) % WRONG_POOL.length
  return Array.from({ length: n }, (_, i) => WRONG_POOL[(start + i) % WRONG_POOL.length])
}

/** 错题数量（图谱节点右上角角标） */
export function mockWrongCount(kpName: string, theta: number): number {
  return mockWrongQuestions(kpName, theta).length
}

/** AI 诊断文案（温暖鼓励语气，接入真实 LLM 诊断时替换为 diagnosis_reports 数据） */
export function mockDiagnosis(kpName: string, theta: number): string {
  if (theta < 1500) {
    return `别灰心，「${kpName}」只是暂时没掌握～从答题记录看，主要问题集中在基础概念与典型求解步骤。回到教材复习一遍定义和例题，再练 ${2 + (hash(kpName) % 3)} 道题就能有明显进步，加油！💪`
  }
  if (theta <= 1700) {
    return `不错！「${kpName}」已经入门了，只是熟练度还不够稳定。针对易混淆点再练 2~3 道题就能稳定掌握啦，冲！🚀`
  }
  return `太棒了！「${kpName}」已经完全掌握，继续保持这个状态，可以挑战更高难度的题目了～🏆`
}
