<template>
  <div class="mx-auto max-w-5xl">
    <!-- 页头 -->
    <div class="mb-6">
      <h1 class="text-xl font-semibold tracking-tight text-gray-900">我的知识库</h1>
      <p class="mt-1 text-[13px] text-gray-500">今天也来学一点吧，坚持就会有收获 🌱</p>
    </div>

    <!-- ① 学习激励卡片（4 个渐变数据卡） -->
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <!-- 连续打卡：橙红渐变 + 火焰动效 -->
      <div class="group rounded-xl bg-gradient-to-br from-orange-400 to-red-500 p-4 text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="flex items-center justify-between">
          <span class="flame-icon text-xl">🔥</span>
          <span class="text-[11px] font-medium text-white/80">连续打卡</span>
        </div>
        <div class="mt-2 text-2xl font-bold tabular-nums">{{ stats.streakDays }} <span class="text-sm font-normal text-white/80">天</span></div>
        <div class="mt-0.5 text-[11px] text-white/70">再坚持 3 天解锁新成就 ✨</div>
      </div>

      <!-- 今日学习：蓝色渐变 -->
      <div class="rounded-xl bg-gradient-to-br from-blue-400 to-indigo-500 p-4 text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="flex items-center justify-between">
          <span class="text-xl">⏱️</span>
          <span class="text-[11px] font-medium text-white/80">今日学习</span>
        </div>
        <div class="mt-2 text-2xl font-bold tabular-nums">{{ stats.todayMinutes }} <span class="text-sm font-normal text-white/80">分钟</span></div>
        <div class="mt-0.5 text-[11px] text-white/70">比昨天多学了 8 分钟</div>
      </div>

      <!-- 已掌握：绿色渐变 -->
      <div class="rounded-xl bg-gradient-to-br from-emerald-400 to-green-500 p-4 text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="flex items-center justify-between">
          <span class="text-xl">✅</span>
          <span class="text-[11px] font-medium text-white/80">已掌握</span>
        </div>
        <div class="mt-2 text-2xl font-bold tabular-nums">{{ masteredCount }} <span class="text-sm font-normal text-white/80">个知识点</span></div>
        <div class="mt-0.5 text-[11px] text-white/70">继续保持节奏</div>
      </div>

      <!-- 今日目标：紫色渐变 + 进度条 -->
      <div class="rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 p-4 text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="flex items-center justify-between">
          <span class="text-xl">🎯</span>
          <span class="text-[11px] font-medium text-white/80">今日目标</span>
        </div>
        <div class="mt-2 text-2xl font-bold tabular-nums">
          {{ stats.goalDone }}<span class="text-sm font-normal text-white/80">/{{ stats.goalTotal }} 完成</span>
        </div>
        <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-white/25">
          <div class="h-full rounded-full bg-white transition-all duration-500" :style="{ width: (stats.goalDone / stats.goalTotal) * 100 + '%' }"></div>
        </div>
      </div>
    </div>

    <!-- ② 新建知识库 + 上传教材（并排卡片） -->
    <div class="mt-4 grid gap-4 md:grid-cols-2">
      <!-- 新建知识库 -->
      <section class="rounded-xl border border-gray-200/80 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="flex items-start gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm">
            <Library class="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 class="text-[15px] font-semibold text-gray-900">新建知识库</h2>
            <p class="mt-0.5 text-xs text-gray-400">无需教材，输入主题即可生成</p>
          </div>
        </div>

        <form class="mt-4 space-y-3" @submit.prevent="createKb">
          <input
            v-model="subject"
            type="text"
            placeholder="科目 · 如 机器学习"
            class="h-10 w-full rounded-lg border border-gray-200 bg-gray-50/60 px-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-purple-400 focus:bg-white focus:ring-4 focus:ring-purple-500/10"
          />
          <input
            v-model="topic"
            type="text"
            placeholder="主题 · 如 线性回归"
            class="h-10 w-full rounded-lg border border-gray-200 bg-gray-50/60 px-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-purple-400 focus:bg-white focus:ring-4 focus:ring-purple-500/10"
          />
          <button
            type="submit"
            :disabled="generating"
            class="flex h-10 w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Loader2 v-if="generating" class="h-4 w-4 animate-spin" />
            <Sparkles v-else class="h-4 w-4" />
            {{ generating ? '生成中…' : '生成知识库' }}
          </button>
        </form>

        <div v-if="generating" class="mt-3">
          <div class="mb-1 flex items-center justify-between text-xs">
            <span class="font-medium text-purple-600">{{ stage || '准备中…' }}</span>
            <span class="tabular-nums text-gray-400">
              {{ progress }}%<template v-if="genEta.eta.value !== null"> · {{ fmtEta(genEta.eta.value) }}</template>
            </span>
          </div>
          <div class="h-1.5 overflow-hidden rounded-full bg-purple-50">
            <div class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-500" :style="{ width: progress + '%' }"></div>
          </div>
        </div>
      </section>

      <!-- 上传教材 -->
      <section class="rounded-xl border border-gray-200/80 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="flex items-start gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-orange-400 to-pink-500 shadow-sm">
            <Upload class="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 class="text-[15px] font-semibold text-gray-900">上传教材 PDF</h2>
            <p class="mt-0.5 text-xs text-gray-400">可选增强：扫描版自动 OCR，约 2 秒/页</p>
          </div>
        </div>

        <div class="mt-4 space-y-3">
          <label
            class="flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-dashed border-gray-300 px-3 text-sm text-gray-500 transition hover:border-purple-400 hover:text-purple-600"
          >
            <FileText class="h-4 w-4 shrink-0" />
            <span class="truncate">{{ pdfFile ? pdfFile.name : '点击选择 PDF 文件' }}</span>
            <input type="file" accept=".pdf" class="hidden" @change="onFileChange" />
          </label>
          <button
            type="button"
            :disabled="!pdfFile || uploading"
            class="flex h-10 w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
            @click="uploadPdf"
          >
            <Loader2 v-if="uploading" class="h-4 w-4 animate-spin" />
            <Upload v-else class="h-4 w-4" />
            {{ uploading ? '解析中…' : '上传并解析' }}
          </button>
        </div>

        <div v-if="uploading" class="mt-3">
          <div class="mb-1 flex items-center justify-between text-xs">
            <span class="font-medium text-purple-600">{{ upStage || '上传中…' }}</span>
            <span class="tabular-nums text-gray-400">
              {{ upProgress }}%<template v-if="upEta.eta.value !== null"> · {{ fmtEta(upEta.eta.value) }}</template>
            </span>
          </div>
          <div class="h-1.5 overflow-hidden rounded-full bg-purple-50">
            <div class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-500" :style="{ width: upProgress + '%' }"></div>
          </div>
        </div>
      </section>
    </div>

    <!-- 生成计划弹窗：每日任务量自定义 -->
    <el-dialog v-model="planDialogOpen" title="生成学习计划" width="440px">
      <div class="space-y-4">
        <p class="text-sm text-gray-600">
          为《{{ planTarget?.title }}》（{{ planTarget?.kp_count }} 个知识点）生成计划
        </p>
        <div>
          <label class="text-xs font-medium text-gray-500">🎯 每日学习量（知识点数量）</label>
          <div class="mt-1.5 flex items-center gap-3">
            <input
              v-model.number="planDailyLimit"
              type="range"
              min="1"
              max="20"
              class="flex-1 accent-purple-600"
            />
            <span class="w-14 rounded-lg bg-purple-50 px-2 py-1 text-center text-sm font-semibold tabular-nums text-purple-700">
              {{ planDailyLimit }} 个
            </span>
          </div>
          <p v-if="planDailyLimit > 10" class="mt-1.5 flex items-center gap-1 text-xs text-amber-600">
            <TriangleAlert class="h-3.5 w-3.5 shrink-0" />
            ⚠️ 每天学习超过 10 个知识点可能会非常疲劳，建议量力而行哦！
          </p>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500">每天学习时长（分钟）</label>
          <input
            v-model.number="planMinutes"
            type="number"
            min="15"
            max="300"
            class="mt-1.5 h-9 w-32 rounded-lg border border-gray-200 bg-gray-50/60 px-3 text-sm outline-none transition focus:border-purple-400 focus:bg-white focus:ring-4 focus:ring-purple-500/10"
          />
        </div>
        <p class="rounded-lg bg-indigo-50 px-3 py-2 text-xs leading-5 text-indigo-700">
          预计 <b class="tabular-nums">{{ Math.max(1, Math.ceil((planTarget?.kp_count || 0) / planDailyLimit)) }}</b> 天完成
          （基于每天 {{ planDailyLimit }} 个知识点）
        </p>
      </div>
      <template #footer>
        <el-button @click="planDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="planningId !== null" @click="confirmPlan">生成计划</el-button>
      </template>
    </el-dialog>

    <!-- ③ 数据表格 -->
    <section class="mt-6 overflow-hidden rounded-xl border border-gray-200/80 bg-white shadow-sm">
      <table v-if="docs.length" class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
            <th class="px-5 py-3">ID</th>
            <th class="px-4 py-3">教材</th>
            <th class="px-4 py-3">来源</th>
            <th class="px-4 py-3 text-right">知识点</th>
            <th class="px-4 py-3">状态</th>
            <th class="px-4 py-3 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="d in docs"
            :key="d.id"
            class="border-b border-gray-50 transition-colors last:border-0 hover:bg-purple-50/60"
          >
            <!-- ID 徽章 -->
            <td class="px-5 py-3.5">
              <span class="rounded-md bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-500">#{{ d.id }}</span>
            </td>

            <!-- 教材：图标 + 加粗名称 -->
            <td class="px-4 py-3.5">
              <div class="flex items-center gap-2.5">
                <FileText v-if="d.source_type === 'pdf'" class="h-4 w-4 shrink-0 text-gray-400" />
                <BookOpen v-else class="h-4 w-4 shrink-0 text-purple-500" />
                <span class="font-semibold text-gray-900">{{ d.title }}</span>
              </div>
            </td>

            <!-- 来源：AI 生成 = 紫渐变标签；pdf = 灰色标签 -->
            <td class="px-4 py-3.5">
              <span
                v-if="d.source_type === 'llm_generated'"
                class="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-violet-500 to-purple-600 px-2.5 py-0.5 text-xs font-medium text-white shadow-sm"
              >
                <Sparkles class="h-3 w-3" />AI 生成
              </span>
              <span
                v-else
                class="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600"
              >
                {{ d.source_type }}
              </span>
            </td>

            <!-- 知识点：加粗数字 + 小箭头 -->
            <td class="px-4 py-3.5 text-right">
              <span class="inline-flex items-center gap-0.5">
                <span class="font-bold tabular-nums text-gray-800">{{ d.kp_count }}</span>
                <ArrowUpRight class="h-3.5 w-3.5 text-gray-400" />
              </span>
            </td>

            <!-- 状态：彩色圆点 + 文字（失败行悬停显示具体原因） -->
            <td class="px-4 py-3.5">
              <span class="inline-flex items-center gap-1.5 text-xs" :title="d.parse_status === 'failed' ? (d.error_message || '') : ''">
                <span class="h-1.5 w-1.5 rounded-full" :class="statusInfo(d.parse_status).dot"></span>
                <span :class="statusInfo(d.parse_status).cls">{{ statusInfo(d.parse_status).text }}</span>
              </span>
            </td>

            <!-- 操作：失败行只显示 重试+删除；正常行显示 图谱/看板/生成计划 + 删除 -->
            <td class="px-4 py-3.5">
              <div class="flex items-center justify-end gap-1">
                <template v-if="d.parse_status === 'failed'">
                  <button
                    type="button"
                    title="重新解析"
                    :disabled="retryingId === d.id"
                    class="flex items-center gap-1 rounded-lg p-2 text-gray-500 transition hover:bg-gray-100 hover:text-purple-600 active:scale-95 disabled:opacity-50"
                    @click="retryDoc(d)"
                  >
                    <Loader2 v-if="retryingId === d.id" class="h-4 w-4 animate-spin" />
                    <RotateCcw v-else class="h-4 w-4" />
                  </button>
                </template>
                <template v-else>
                  <button
                    type="button"
                    title="知识图谱"
                    class="rounded-lg p-2 text-gray-500 transition hover:bg-gray-100 hover:text-purple-600 active:scale-95"
                    @click="go('graph', d.id)"
                  >
                    <Network class="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    title="掌握度看板"
                    class="rounded-lg p-2 text-gray-500 transition hover:bg-gray-100 hover:text-purple-600 active:scale-95"
                    @click="go('dashboard', d.id)"
                  >
                    <BarChart3 class="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    :disabled="planningId === d.id"
                    class="ml-1 inline-flex items-center gap-1 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
                    @click="createPlan(d)"
                  >
                    <Loader2 v-if="planningId === d.id" class="h-3 w-3 animate-spin" />
                    <CalendarDays v-else class="h-3 w-3" />
                    生成计划
                  </button>
                </template>
                <button
                  type="button"
                  title="删除教材"
                  class="rounded-lg p-2 text-gray-500 transition hover:bg-red-50 hover:text-red-500 active:scale-95"
                  @click="removeDoc(d)"
                >
                  <Trash2 class="h-4 w-4" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 空状态 -->
      <div v-else class="flex flex-col items-center justify-center py-16 text-center">
        <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-purple-50">
          <Library class="h-6 w-6 text-purple-400" />
        </div>
        <p class="mt-3 text-sm font-medium text-gray-700">还没有知识库</p>
        <p class="mt-1 text-xs text-gray-400">在上方输入主题，或上传一份 PDF 教材开始</p>
      </div>
    </section>

    <!-- ④ 今日推荐（基于薄弱知识点） -->
    <section
      v-if="recommend.length"
      class="mt-6 rounded-xl border-l-4 border-orange-400 bg-amber-50 p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-sm"
    >
      <div class="flex items-center gap-2 text-[15px] font-semibold text-amber-900">🎯 今日推荐</div>
      <p class="mt-1.5 text-[13px] leading-6 text-amber-800">
        检测到 {{ recommend.length }} 个薄弱知识点：
        <span class="font-semibold">{{ recommend.map(r => r.name).join('、') }}</span>
        （θ = {{ recommend.map(r => r.theta).join(' / ') }}）
        <br />建议先用 10 分钟复习，再回到今天的计划。
      </p>
      <div class="mt-3 flex gap-2">
        <button
          class="rounded-lg bg-orange-500 px-3.5 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-orange-600 active:scale-95"
          @click="router.push('/quiz')"
        >
          去练习
        </button>
        <button
          class="rounded-lg border border-orange-300 bg-white px-3.5 py-1.5 text-xs font-medium text-orange-600 transition hover:bg-orange-50 active:scale-95"
          @click="router.push('/dashboard')"
        >
          查看掌握度
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowUpRight, BarChart3, BookOpen, CalendarDays, FileText, Library,
  Loader2, Network, RotateCcw, Sparkles, Trash2, TriangleAlert, Upload,
} from 'lucide-vue-next'
import { api, waitTask, Doc } from '../api'
import { mockTheta } from '../mock'
import { useStatsStore } from '../stores/stats'

const router = useRouter()
const docs = ref<Doc[]>([])
const subject = ref('机器学习')
const topic = ref('')
const generating = ref(false)
const progress = ref(0)
const stage = ref('')
const planningId = ref<number | null>(null)
const pdfFile = ref<File | null>(null)
const uploading = ref(false)
const upProgress = ref(0)
const upStage = ref('')
const recommend = ref<any[]>([])
const retryingId = ref<number | null>(null)

// ── 激励数据（全局 stats store：答题提交后自动联动；掌握数来自 mastery） ──
const stats = useStatsStore()
const masteredCount = ref(5)

// ── 任务 ETA 推算：滑动窗口采样进度变化率，外推剩余时间 ──
function createEtaTracker() {
  const samples = ref<{ t: number; p: number }[]>([])
  const push = (p: number) => {
    samples.value = [
      ...samples.value.filter(s => s.t > Date.now() - 30000),
      { t: Date.now(), p },
    ]
  }
  const eta = computed(() => {
    const s = samples.value
    if (s.length < 2) return null
    const dt = (s[s.length - 1].t - s[0].t) / 1000
    const dp = s[s.length - 1].p - s[0].p
    if (dt <= 0 || dp <= 0) return null
    return (100 - s[s.length - 1].p) / (dp / dt)   // 秒
  })
  return { push, eta, reset: () => (samples.value = []) }
}
const genEta = createEtaTracker()
const upEta = createEtaTracker()

function fmtEta(sec: number): string {
  if (sec < 20) return '即将完成'
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return m > 0 ? `预计还需 ${m} 分 ${s} 秒` : `预计还需 ${s} 秒`
}

onMounted(async () => {
  await load()
  await loadRecommend()
})

async function load() {
  docs.value = await api.listDocuments()
}

/** 今日推荐：取最新教材的薄弱知识点（未作答的用 Mock θ，与看板/图谱一致） */
async function loadRecommend() {
  const doc = docs.value[0]
  if (!doc) {
    recommend.value = []
    return
  }
  try {
    const m = await api.getMastery(doc.id)
    m.items.forEach((it: any, i: number) => {
      if (it.correct_count + it.wrong_count === 0) {
        it.theta = mockTheta(i)
        it.mastered = it.theta > 1700
      }
    })
    recommend.value = m.items
      .filter((i: any) => i.theta < 1500)
      .sort((a: any, b: any) => a.theta - b.theta)
      .slice(0, 2)
  } catch {
    recommend.value = []
  }
}

async function createKb() {
  if (!topic.value.trim()) {
    ElMessage.warning('请输入主题')
    return
  }
  generating.value = true
  progress.value = 0
  genEta.reset()
  try {
    const taskId = await api.generateKnowledge(subject.value, topic.value.trim())
    const t = await waitTask(taskId, s => {
      progress.value = s.progress
      stage.value = s.stage
      genEta.push(s.progress)
    })
    if (t.status === 'failed') ElMessage.error(t.error)
    else ElMessage.success(`知识库生成完成：${t.result.entities} 个知识点`)
    topic.value = ''
    await load()
    await loadRecommend()
  } finally {
    generating.value = false
  }
}

// ── 生成计划弹窗（每日任务量自定义） ──
const planDialogOpen = ref(false)
const planTarget = ref<Doc | null>(null)
const planDailyLimit = ref(5)
const planMinutes = ref(45)

function createPlan(doc: Doc) {
  // 必须传入整行对象（Doc）：弹窗需要 title / kp_count 展示与天数计算
  planTarget.value = doc
  planDailyLimit.value = 5
  planMinutes.value = 45
  planDialogOpen.value = true
}

async function confirmPlan() {
  const d = planTarget.value
  if (!d || typeof d !== 'object') {
    ElMessage.error('数据异常：请关闭弹窗后重试')
    return
  }
  planningId.value = d.id
  try {
    // 关键：按用户选的每日学习量计算总天数（23 个知识点 / 6 个每天 = 4 天），
    // 与弹窗里的"预计 X 天完成"完全一致；后端仍有自动延期兜底
    const estDays = Math.max(1, Math.ceil(d.kp_count / planDailyLimit.value))
    const taskId = await api.generatePlan(d.id, estDays, planMinutes.value, planDailyLimit.value)
    const t = await waitTask(taskId)
    if (t.status === 'failed') ElMessage.error(t.error)
    else {
      ElMessage.success(
        t.result.extended
          ? `知识点较多，计划已自动延长为 ${t.result.total_days} 天`
          : `学习计划已生成（${t.result.total_days} 天，每天最多 ${t.result.daily_limit} 个）`,
      )
      planDialogOpen.value = false
      router.push(`/plan/${t.result.plan_id}`)
    }
  } finally {
    planningId.value = null
  }
}

async function removeDoc(d: Doc) {
  try {
    await ElMessageBox.confirm(
      `确定要删除《${d.title}》吗？相关学习计划、题目和答题记录也将被删除。`,
      '删除教材',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return   // 用户取消
  }
  try {
    await api.deleteDocument(d.id)
    docs.value = docs.value.filter(x => x.id !== d.id)
    ElMessage.success('教材已删除')
    await loadRecommend()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function retryDoc(d: Doc) {
  retryingId.value = d.id
  uploading.value = true          // 复用上传卡的进度条 + ETA 展示
  upProgress.value = 0
  upEta.reset()
  try {
    const { task_id } = await api.retryDocument(d.id)
    const t = await waitTask(task_id, s => {
      upProgress.value = s.progress
      upStage.value = s.stage
      upEta.push(s.progress)
    })
    if (t.status === 'failed') ElMessage.error(t.error)
    else ElMessage.success(`重新解析完成：${t.result.entities} 个知识点`)
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重试失败')
  } finally {
    retryingId.value = null
    uploading.value = false
  }
}

function onFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  pdfFile.value = f || null
}

async function uploadPdf() {
  if (!pdfFile.value) return
  uploading.value = true
  upProgress.value = 0
  upEta.reset()
  try {
    const { task_id } = await api.uploadPdf(pdfFile.value)
    const t = await waitTask(task_id, s => {
      upProgress.value = s.progress
      upStage.value = s.stage
      upEta.push(s.progress)
    })
    if (t.status === 'failed') ElMessage.error(t.error)
    else ElMessage.success(`PDF 解析完成：${t.result.entities} 个知识点`)
    pdfFile.value = null
    await load()
  } finally {
    uploading.value = false
  }
}

function go(name: string, id: number) {
  router.push(`/${name}/${id}`)
}

// ── 状态显示 ──
function statusInfo(s: string) {
  return {
    done: { text: '已就绪', cls: 'text-emerald-600', dot: 'bg-emerald-500' },
    parsing: { text: '学习中', cls: 'text-blue-600', dot: 'bg-blue-500' },
    pending: { text: '排队中', cls: 'text-gray-500', dot: 'bg-gray-400' },
    failed: { text: '解析失败', cls: 'text-orange-500', dot: 'bg-orange-400' },
  }[s] || { text: s, cls: 'text-gray-500', dot: 'bg-gray-400' }
}
</script>

<style scoped>
/* 火焰图标呼吸动效 */
@keyframes flame-glow {
  0%, 100% { transform: scale(1); filter: drop-shadow(0 0 0 rgba(255, 180, 80, 0)); }
  50% { transform: scale(1.18); filter: drop-shadow(0 0 8px rgba(255, 220, 120, 0.9)); }
}
.flame-icon {
  display: inline-block;
  animation: flame-glow 1.6s ease-in-out infinite;
}
</style>
