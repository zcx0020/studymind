import axios from 'axios'

// 本地开发：'/api' 走 vite 代理到 localhost:8000；
// Vercel 部署：构建时设置 VITE_API_BASE=https://<render域名>/api
const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 300000,
})

export interface Doc {
  id: number
  title: string
  source_type: string
  parse_status: string
  kp_count: number
  error_message?: string | null
}

export interface TaskStatus {
  id: string
  status: 'pending' | 'running' | 'done' | 'failed'
  stage: string
  progress: number
  result: any
  error: string | null
}

export interface PlanSummary {
  id: number
  document_id: number
  title: string
  total_days: number
  status: string
  goal: string
  daily_limit?: number
}

/** 提交答案的返回（客观题 graded / 主观题 grading 待批改） */
export interface SubmitResult {
  status: 'graded' | 'grading'
  is_correct?: boolean | null
  correct_answer?: string
  analysis?: string
  feedback?: string
  mastery?: {
    theta: number
    theta_before?: number
    delta?: number
    streak?: number
    mastered?: boolean
  }
  diagnosis_task_id?: string | null
  grading_task_id?: string | null
  summary_task_id?: string | null
}

/** 会话总结（/api/task_status/{summary_task_id} 轮询得到） */
export interface SummaryPayload {
  total: number
  correct: number
  wrong: number
  accuracy: number
  duration_sec: number
  kps: { kp_id: number; name: string; correct: number; wrong: number
         theta_before: number | null; theta_after: number | null }[]
  weak_names: string[]
  wrong_questions: {
    stem: string
    kp_name: string
    user_answer: string
    correct_answer: string
    analysis: string
  }[]
}

export const api = {
  listDocuments: () => http.get('/documents').then(r => r.data.items as Doc[]),
  generateKnowledge: (subject: string, topic: string) =>
    http.post('/knowledge/generate', { subject, topic }).then(r => r.data.task_id as string),
  getTask: (id: string) => http.get(`/tasks/${id}`).then(r => r.data as TaskStatus),
  /** 答题模块统一轮询入口（后端 /api/task_status/{id}，与 /api/tasks/{id} 等价） */
  getTaskStatus: (id: string) => http.get(`/task_status/${id}`).then(r => r.data as TaskStatus),
  getGraph: (docId: number) => http.get(`/knowledge/graph/${docId}`).then(r => r.data),
  listPlans: () => http.get('/plans').then(r => r.data.items as PlanSummary[]),
  generatePlan: (docId: number, totalDays = 7, minutesPerDay = 45, dailyLimit = 5) =>
    http.post('/plans/generate', {
      document_id: docId, total_days: totalDays,
      minutes_per_day: minutesPerDay, daily_limit: dailyLimit,
    }).then(r => r.data.task_id as string),
  getPlan: (planId: number) => http.get(`/plans/${planId}`).then(r => r.data),
  rebalancePlan: (planId: number) =>
    http.post(`/plans/${planId}/rebalance`).then(r => r.data as { moved: number; total_days: number }),
  /** 异步出题任务：立即返回 task_id，配合 getTaskStatus 轮询，前端永不阻塞 */
  startQuizTask: (params: object) =>
    http.post('/quiz/task', params).then(r => r.data.task_id as string),
  /**
   * 提交答案（后端契约 <1s 返回）：客观题直接带 is_correct；
   * 主观题返回 grading_task_id（AI 批改，轮询）；
   * 最后一题 is_last=true 时返回 summary_task_id（异步总结，轮询）
   */
  submitAnswer: (questionId: number, userAnswer: string, extra?: {
    is_last?: boolean
    question_ids?: number[]
    duration_sec?: number
  }) =>
    http.post('/submit_answer', {
      question_id: questionId,
      user_answer: userAnswer,
      is_last: extra?.is_last ?? false,
      question_ids: extra?.question_ids ?? [],
      duration_sec: extra?.duration_sec,
    }, { timeout: 10000 }).then(r => r.data as SubmitResult),
  getMastery: (docId: number) => http.get(`/mastery/${docId}`).then(r => r.data),
  uploadPdf: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post('/documents/upload', fd).then(r => r.data as { task_id: string; doc_id: number })
  },
  deleteDocument: (docId: number) => http.delete(`/documents/${docId}`).then(r => r.data),
  retryDocument: (docId: number) =>
    http.post(`/documents/${docId}/retry`).then(r => r.data as { task_id: string; doc_id: number }),
}

/** 轮询异步任务直到完成 */
export async function waitTask(taskId: string, onProgress?: (t: TaskStatus) => void): Promise<TaskStatus> {
  for (;;) {
    const t = await api.getTask(taskId)
    onProgress?.(t)
    if (t.status === 'done' || t.status === 'failed') return t
    await new Promise(r => setTimeout(r, 3000))
  }
}
