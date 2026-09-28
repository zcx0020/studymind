<template>
  <div class="mx-auto max-w-4xl">
    <div class="mb-4">
      <h1 class="text-xl font-semibold tracking-tight text-gray-900">
        学习计划<template v-if="currentPlanTitle"> · {{ currentPlanTitle }}</template>
      </h1>
      <p class="mt-1 text-[13px] text-gray-500">
        任务按天均匀分配（每天 ≤{{ planDailyLimit }} 个知识点），天数按知识点总量自动计算
        <template v-if="currentPlanDays"> · 当前计划共 {{ currentPlanDays }} 天</template>
        ；答错后引擎会自动插入补学任务（紫色标记）
      </p>
      <div class="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-purple-50 px-3 py-1.5 text-xs text-purple-700">
        📌 完成标准：掌握度 θ 达到 1700 = 100%（答对加分、答错扣分；悬停进度条看当前 θ 和差距）
      </div>
    </div>

    <!-- 激励栏 + 今日任务统计 -->
    <StreakBar>
      <div class="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-emerald-400 to-green-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm">
        ✅ 今日任务 {{ todayDone }}/{{ todayTotal }} 完成
      </div>
      <div class="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-blue-400 to-indigo-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm">
        📚 预计学习 {{ todayMinutes }} 分钟
      </div>
    </StreakBar>

    <div class="mb-5 flex items-center gap-3">
      <select
        v-model="planId"
        class="h-9 flex-1 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-purple-400 focus:ring-4 focus:ring-purple-500/10"
        @change="load"
      >
        <option v-for="p in plans" :key="p.id" :value="p.id">
          #{{ p.id }} {{ p.title }}（{{ p.total_days }}天）
        </option>
      </select>
      <button
        type="button"
        :disabled="!planId"
        class="flex h-9 items-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-4 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
        @click="goQuiz"
      >
        <Play class="h-3.5 w-3.5" />
        开始今天的学习
      </button>
    </div>

    <div v-if="!plans.length" class="flex flex-col items-center justify-center rounded-xl border border-gray-200/80 bg-white py-16 text-center shadow-sm">
      <CalendarDays class="h-8 w-8 text-gray-300" />
      <p class="mt-3 text-sm font-medium text-gray-700">还没有学习计划</p>
      <p class="mt-1 text-xs text-gray-400">到「知识库」页面选择教材生成计划</p>
    </div>

    <!-- Day 折叠面板（首个 Day 默认展开） -->
    <section
      v-for="(items, day) in days"
      :key="day"
      class="mb-4 overflow-hidden rounded-xl border border-gray-200/80 bg-white shadow-sm"
    >
      <div
        role="button"
        class="flex w-full cursor-pointer items-center gap-2.5 border-b border-gray-100 px-5 py-3 text-left transition"
        :class="items.length > planDailyLimit ? 'bg-red-50/70 hover:bg-red-50' : 'bg-gray-50/60 hover:bg-gray-50'"
        @click="toggleDay(String(day))"
      >
        <ChevronDown
          class="h-4 w-4 shrink-0 text-gray-400 transition-transform duration-200"
          :class="openDays.has(String(day)) ? '' : '-rotate-90'"
        />
        <span class="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700">Day {{ day }}</span>
        <span class="text-sm font-medium text-gray-800">{{ items.length }} 个知识点</span>
        <span class="text-xs text-gray-400">约 {{ sumMinutes(items) }} 分钟</span>
        <span
          v-if="items.length > planDailyLimit"
          class="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-medium text-red-600"
        >
          <TriangleAlert class="h-3 w-3" />任务过重
        </span>
        <button
          v-if="items.length > planDailyLimit"
          type="button"
          :disabled="rebalancing"
          class="inline-flex items-center gap-1 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-2.5 py-1 text-[11px] font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:opacity-60"
          @click.stop="splitDay"
        >
          <Loader2 v-if="rebalancing" class="h-3 w-3 animate-spin" />
          <Shuffle v-else class="h-3 w-3" />
          自动拆分
        </button>
        <span class="ml-auto text-xs text-gray-400">
          {{ items.filter((i: any) => i.status === 'done').length }}/{{ items.length }} 已完成
        </span>
      </div>

      <div v-show="openDays.has(String(day))">
        <!-- 任务卡片行：左侧色边区分完成状态 -->
        <div
          v-for="row in items"
          :key="row.kp_id"
          class="group cursor-pointer border-b border-gray-50 border-l-4 px-5 py-3.5 pl-4 transition-colors last:border-b-0"
          :class="row.status === 'done'
            ? 'border-l-emerald-400 hover:bg-emerald-50/40'
            : row.status === 'doing'
              ? 'border-l-blue-300 hover:bg-purple-50/50'
              : 'border-l-gray-200 hover:bg-gray-50/60'"
          @click="toggle(`${day}:${row.kp_id}`)"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="flex min-w-0 flex-wrap items-center gap-2">
              <BookOpen class="h-4 w-4 shrink-0 text-purple-500" />
              <span class="truncate text-sm font-semibold text-gray-900">{{ row.name }}</span>
              <span
                v-for="t in row.task_types"
                :key="t"
                class="rounded-full px-2 py-0.5 text-[11px] font-medium"
                :class="taskClass(t)"
              >
                {{ taskLabel(t) }}
              </span>
              <span
                v-if="row.adaptive"
                class="rounded-full bg-purple-100 px-2 py-0.5 text-[11px] font-medium text-purple-700"
              >
                ⚡自适应
              </span>
            </div>
            <div class="flex shrink-0 items-center gap-3">
              <!-- 三段式进度条（阅读 / 笔记 / 练习）+ 悬停子任务清单 -->
              <div class="group relative hidden w-36 items-center gap-2 sm:flex">
                <div class="flex h-1.5 flex-1 gap-0.5">
                  <div
                    class="flex-1 rounded-l-full transition-colors duration-500"
                    :class="row.progress >= 33 ? 'bg-gradient-to-r from-blue-400 to-indigo-500' : 'bg-gray-100'"
                  ></div>
                  <div
                    class="flex-1 transition-colors duration-500"
                    :class="row.progress >= 66 ? 'bg-gradient-to-r from-indigo-500 to-purple-600' : 'bg-gray-100'"
                  ></div>
                  <div class="flex-1 overflow-hidden rounded-r-full bg-gray-100">
                    <div
                      class="h-full rounded-r-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-500"
                      :style="{ width: practicePct(row.progress) + '%' }"
                    ></div>
                  </div>
                </div>
                <span class="w-9 text-right text-[11px] tabular-nums text-gray-400">{{ row.progress }}%</span>

                <!-- 悬停详情：子任务完成清单 -->
                <div class="pointer-events-none absolute -top-28 right-0 z-20 hidden w-64 rounded-lg bg-gray-900 px-3.5 py-3 text-[11px] leading-5 text-white shadow-xl group-hover:block">
                  <div class="text-xs font-semibold">{{ row.name }} · {{ row.progress }}% {{ statusTextOf(row) }}</div>
                  <div class="mt-1.5 space-y-1 text-gray-300">
                    <div :class="row.progress >= 33 ? 'text-emerald-300' : ''">
                      {{ row.progress >= 33 ? '✓' : '○' }} 阅读教材内容{{ row.progress >= 33 ? '（已完成）' : '' }}
                    </div>
                    <div :class="row.progress >= 66 ? 'text-emerald-300' : ''">
                      {{ row.progress >= 66 ? '✓' : '○' }} 观看视频/整理笔记{{ row.progress >= 66 ? '（已完成）' : '' }}
                    </div>
                    <div>
                      <span :class="done3(row.progress) === 3 ? 'text-emerald-300' : ''">
                        {{ done3(row.progress) === 3 ? '✓' : '○' }} 完成练习题（{{ done3(row.progress) }}/3 题）
                      </span>
                      <span v-if="done3(row.progress) < 3" class="ml-1 font-medium text-amber-300">
                        ← 还差 {{ 3 - done3(row.progress) }} 题
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              <span
                class="inline-flex items-center gap-1 text-xs"
                :class="row.status === 'done' ? 'text-emerald-600' : row.status === 'doing' ? 'text-blue-600' : 'text-gray-400'"
              >
                <CheckCircle2 v-if="row.status === 'done'" class="h-3.5 w-3.5" />
                <Play v-else-if="row.status === 'doing'" class="h-3.5 w-3.5" />
                <Lock v-else class="h-3.5 w-3.5" />
                {{ row.status === 'done' ? '已完成' : row.status === 'doing' ? '进行中' : '未开始' }}
              </span>
              <button
                type="button"
                class="flex items-center gap-1 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95"
                @click.stop="goQuiz"
              >
                <Play class="h-3 w-3" />开始学习
              </button>
            </div>
          </div>
          <p v-if="expanded.has(`${day}:${row.kp_id}`)" class="mt-2 pl-6 text-[13px] leading-5 text-gray-500">
            {{ row.definition || '（无定义）' }}
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { BookOpen, CalendarDays, CheckCircle2, ChevronDown, Loader2, Lock, Play, Shuffle, TriangleAlert } from 'lucide-vue-next'
import { api, PlanSummary } from '../api'
import { mockTheta } from '../mock'
import StreakBar from '../components/StreakBar.vue'

const route = useRoute()
const router = useRouter()
const plans = ref<PlanSummary[]>([])
const planId = ref<number | null>(route.params.planId ? Number(route.params.planId) : null)
const days = ref<Record<number, any[]>>({})
const expanded = reactive(new Set<string>())
const openDays = reactive(new Set<string>())

// 今日（第一个 Day）统计
const currentPlanDays = computed(
  () => plans.value.find(p => p.id === planId.value)?.total_days,
)
const currentPlanTitle = computed(
  () => plans.value.find(p => p.id === planId.value)?.title,
)
const planDailyLimit = computed(
  () => plans.value.find(p => p.id === planId.value)?.daily_limit || 5,
)

const firstDayItems = computed(() => {
  const keys = Object.keys(days.value).map(Number).sort((a, b) => a - b)
  return keys.length ? days.value[keys[0]] : []
})
const todayDone = computed(() => firstDayItems.value.filter((i: any) => i.status === 'done').length)
const todayTotal = computed(() => firstDayItems.value.length)
const todayMinutes = computed(() => sumMinutes(firstDayItems.value))

onMounted(async () => {
  plans.value = await api.listPlans()
  if (!planId.value && plans.value.length) planId.value = plans.value[0].id
  if (planId.value) await load()
})

function sumMinutes(items: any[]) {
  return items.reduce((s: number, i: any) => s + (i.est_minutes || 0), 0)
}

/** 真实进度：θ 1400→0%、1700→100% 线性映射。
 *  未作答的知识点用 mock θ（演示起伏），答过题后是真实 Elo——答对进度涨，答错进度掉 */
function thetaProgress(theta: number): number {
  return Math.min(100, Math.max(0, Math.round(((theta - 1400) / 300) * 100)))
}

async function load() {
  if (!planId.value) return
  // 真实掌握度 → 每行进度与状态（未作答的用 mock θ 展示演示起伏）
  const meta = plans.value.find(p => p.id === planId.value)
  const kpMeta: Record<number, any> = {}
  if (meta) {
    try {
      const m = await api.getMastery(meta.document_id)
      m.items.forEach((it: any, i: number) => {
        if (it.correct_count + it.wrong_count === 0) {
          it.theta = mockTheta(i)
          it.mastered = it.theta > 1700
        }
        kpMeta[it.id] = it
      })
    } catch { /* 忽略，进度退化为初始值 */ }
  }

  const data = await api.getPlan(planId.value)
  // 同一知识点的多条任务合并为一行（学习 & 复习 & 练习）
  const grouped: Record<number, any[]> = {}
  for (const [day, rows] of Object.entries<any[]>(data.days)) {
    const map = new Map<number, any>()
    for (const r of rows) {
      const m = map.get(r.kp_id)
      if (m) {
        if (!m.task_types.includes(r.task_type)) m.task_types.push(r.task_type)
        m.est_minutes += r.est_minutes
        if (r.created_by === 'adaptive') m.adaptive = true
        if (m.status === 'done' && r.status !== 'done') m.status = r.status
      } else {
        map.set(r.kp_id, { ...r, task_types: [r.task_type], adaptive: r.created_by === 'adaptive' })
      }
    }
    const list = [...map.values()].map((r) => {
      const km = kpMeta[r.kp_id]
      const theta: number = km ? km.theta : 1500
      const realDone = r.status === 'done' || (km?.mastered ?? false)
      const status = realDone ? 'done' : theta >= 1400 ? 'doing' : 'todo'
      return { ...r, theta, status, progress: thetaProgress(theta) }
    })
    grouped[Number(day)] = list
  }
  days.value = grouped

  // 首个 Day 默认展开，其余折叠
  const keys = Object.keys(grouped).map(Number).sort((a, b) => a - b)
  openDays.clear()
  if (keys.length) openDays.add(String(keys[0]))
}

const rebalancing = ref(false)

async function splitDay() {
  if (!planId.value) return
  rebalancing.value = true
  try {
    const r = await api.rebalancePlan(planId.value)
    if (r.moved > 0) {
      ElMessage.success(`✅ 已将 ${r.moved} 个知识点拆分到后续天数，每天不超过 ${r.max_per_day} 个`)
    } else {
      ElMessage.info(`该计划每天任务数已符合上限（${r.max_per_day} 个/天），无需拆分`)
    }
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '调整失败')
  } finally {
    rebalancing.value = false
  }
}

// ── 三段进度条与子任务清单 ──
function practicePct(p: number) {
  if (p <= 66) return 0
  return Math.min(100, Math.round(((p - 66) / 34) * 100))
}
function done3(p: number) {
  if (p <= 66) return 0
  if (p >= 100) return 3
  return Math.min(3, Math.max(1, Math.round(((p - 66) / 34) * 3)))
}
function statusTextOf(row: any) {
  return row.status === 'done' ? '已完成' : row.status === 'doing' ? '进行中' : '未开始'
}
function progressTip(row: any) {
  const gap = Math.max(0, 1700 - Math.round(row.theta))
  if (row.status === 'done') {
    return `已完成：掌握度 θ=${row.theta}（≥1700 达标），继续挑战新知识点吧`
  }
  if (row.status === 'doing') {
    return `进行中：θ=${row.theta}，还差 ${gap} 分达标——去答题，答对加分、答错扣分`
  }
  return `未开始：θ=${row.theta}（<1400 计入未开始），完成练习后进度才会增长`
}

function toggleDay(key: string) {
  openDays.has(key) ? openDays.delete(key) : openDays.add(key)
}

function toggle(key: string) {
  expanded.has(key) ? expanded.delete(key) : expanded.add(key)
}

function goQuiz() {
  router.push(`/quiz/${planId.value}`)
}

function taskLabel(t: string) {
  return { learn: '学习', review: '复习', practice: '练习' }[t] || t
}
function taskClass(t: string) {
  return {
    learn: 'bg-blue-100 text-blue-700',
    review: 'bg-orange-100 text-orange-700',
    practice: 'bg-emerald-100 text-emerald-700',
  }[t] || 'bg-gray-100 text-gray-600'
}
</script>
