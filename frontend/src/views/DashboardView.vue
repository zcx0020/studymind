<template>
  <div class="mx-auto max-w-5xl">
    <div class="mb-4">
      <h1 class="text-xl font-semibold tracking-tight text-gray-900">掌握度看板</h1>
      <p class="mt-1 text-[13px] text-gray-500">基于 Elo 模型：1500 为初始值，≥1700 视为已掌握；点击条形图查看错题解析</p>
    </div>

    <StreakBar />

    <div class="mb-4">
      <select
        v-model="docId"
        class="h-9 w-64 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-purple-400 focus:ring-4 focus:ring-purple-500/10"
        @change="load"
      >
        <option v-for="d in docs" :key="d.id" :value="d.id">{{ d.title }}</option>
      </select>
    </div>

    <!-- 渐变统计卡 -->
    <div v-if="stats" class="mb-4 grid grid-cols-3 gap-4">
      <div class="rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 p-5 text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="text-2xl font-bold tabular-nums">{{ stats.avgTheta }}</div>
        <div class="mt-0.5 text-[13px] text-white/80">平均掌握度 θ</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-emerald-400 to-green-500 p-5 text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="text-2xl font-bold tabular-nums">
          {{ stats.mastered }}<span class="ml-1 text-sm font-normal text-white/80">/ {{ stats.total }}</span>
        </div>
        <div class="mt-0.5 text-[13px] text-white/80">已掌握知识点</div>
      </div>
      <div class="rounded-xl bg-gradient-to-br from-blue-400 to-indigo-500 p-5 text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div class="text-2xl font-bold tabular-nums">
          {{ stats.accuracy }}<span class="ml-1 text-sm font-normal text-white/80">%</span>
        </div>
        <div class="mt-0.5 text-[13px] text-white/80">答题正确率</div>
      </div>
    </div>

    <!-- 每日趋势（折线） -->
    <section class="mb-4 rounded-xl border border-gray-200/80 bg-white p-5 shadow-sm">
      <div class="mb-2 flex items-center justify-between">
        <h3 class="text-[15px] font-semibold text-gray-900">📈 每日趋势（近 7 天）</h3>
        <span class="text-xs text-gray-400">模拟历史数据 · 接入真实答题记录后替换</span>
      </div>
      <div ref="trendEl" class="h-[220px] w-full"></div>
      <div ref="countEl" class="h-[150px] w-full"></div>
    </section>

    <!-- 条形图 -->
    <section class="rounded-xl border border-gray-200/80 bg-white p-5 shadow-sm">
      <div class="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
        <span class="inline-flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-sm" style="background: #fb923c"></span>薄弱（θ &lt; 1500）
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-sm" style="background: #6366f1"></span>学习中（1500 ~ 1700）
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-sm" style="background: #10b981"></span>已掌握（θ &gt; 1700）
        </span>
        <span class="ml-auto text-gray-400">虚线：1500 初始值 / 1700 已掌握线 · 点击条形查看错题解析</span>
      </div>
      <div ref="chartEl" class="h-[460px] w-full"></div>
    </section>

    <!-- AI 建议栏（图表下方） -->
    <div
      v-if="weakKps.length"
      class="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-sm"
    >
      <div class="flex items-center gap-2 text-[15px] font-semibold text-amber-900">💡 AI 建议</div>
      <p class="mt-1.5 text-[13px] leading-6 text-amber-800">
        建议优先复习：<span class="font-semibold">{{ weakKps[0].name }}</span>
        （{{ mockWrongCount(weakKps[0].name, weakKps[0].theta) }} 道错题未解决），
        其余薄弱点共 {{ weakKps.length - 1 }} 个。
        <button
          class="ml-1 font-medium text-amber-900 underline underline-offset-2 transition hover:text-amber-700"
          @click="openKp(weakKps[0])"
        >
          查看诊断
        </button>
      </p>
    </div>

    <!-- 错题解析 Drawer -->
    <KpDrawer :kp="selectedKp" @close="selectedKp = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { api, Doc } from '../api'
import { INK } from '../colors'
import { mockTheta, mockWrongCount } from '../mock'
import KpDrawer from '../components/KpDrawer.vue'
import StreakBar from '../components/StreakBar.vue'

const route = useRoute()
const chartEl = ref<HTMLElement>()
const trendEl = ref<HTMLElement>()
const countEl = ref<HTMLElement>()
const docs = ref<Doc[]>([])
const docId = ref<number | null>(route.params.docId ? Number(route.params.docId) : null)
const stats = ref<any>(null)
const items = ref<any[]>([])
const selectedKp = ref<any>(null)

let chart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null
let countChart: echarts.ECharts | null = null

const weakKps = computed(() =>
  [...items.value].filter(i => i.theta < 1500).sort((a, b) => a.theta - b.theta),
)

// 条形图渐变色（按状态动态）
const gradOrange = new echarts.graphic.LinearGradient(0, 0, 1, 0, [
  { offset: 0, color: '#fb923c' }, { offset: 1, color: '#ef4444' },
])
const gradBlue = new echarts.graphic.LinearGradient(0, 0, 1, 0, [
  { offset: 0, color: '#60a5fa' }, { offset: 1, color: '#6366f1' },
])
const gradGreen = new echarts.graphic.LinearGradient(0, 0, 1, 0, [
  { offset: 0, color: '#4ade80' }, { offset: 1, color: '#10b981' },
])
function barColor(v: number) {
  if (v < 1500) return gradOrange
  if (v > 1700) return gradGreen
  return gradBlue
}

onMounted(async () => {
  docs.value = await api.listDocuments()
  if (!docId.value && docs.value.length) docId.value = docs.value[0].id
  if (docId.value) await load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  chart?.dispose()
  trendChart?.dispose()
  countChart?.dispose()
  window.removeEventListener('resize', onResize)
})

function onResize() {
  chart?.resize()
  trendChart?.resize()
  countChart?.resize()
}

/** 模拟 7 天趋势数据（从 ~1420 爬到当前均值，带小幅波动） */
function buildTrend(avgNow: number, masteredNow: number, weakNow: number) {
  const days = ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7']
  const theta = days.map((_, i) => {
    const t = i / 6
    return Math.round(1420 + (avgNow - 1420) * (0.3 + 0.7 * t) + Math.sin(i * 1.6) * 18)
  })
  const mastered = days.map((_, i) => Math.max(0, Math.round(masteredNow * (i / 6) - (i % 3 === 1 ? 1 : 0))))
  const weak = days.map((_, i) => Math.max(0, Math.round(weakNow * (1 - i / 6) + (i === 2 ? 1 : 0))))
  return { days, theta, mastered, weak }
}

async function openKp(kp: any) {
  selectedKp.value = kp
  if (!kp.definition && docId.value) {
    try {
      const g = await api.getGraph(docId.value)
      const node = g.nodes.find((n: any) => n.name === kp.name)
      if (node) selectedKp.value = { ...kp, type: kp.kp_type, definition: node.definition }
    } catch { /* 忽略，Drawer 无定义也可用 */ }
  }
}

async function load() {
  if (!docId.value) return
  const m = await api.getMastery(docId.value)

  // Mock 层：未作答的知识点按序分配 θ（1200/1600/1800），让图表有行动指引效果
  m.items.forEach((it: any, i: number) => {
    if (it.correct_count + it.wrong_count === 0) {
      it.theta = mockTheta(i)
      it.mastered = it.theta > 1700
      it.mock = true
    }
  })
  items.value = m.items

  const sorted = [...m.items].sort((a: any, b: any) => a.theta - b.theta)
  const mastered = m.items.filter((i: any) => i.mastered).length
  const answered = m.items.filter((i: any) => i.correct_count + i.wrong_count > 0)
  stats.value = {
    total: m.items.length,
    mastered,
    avgTheta: Math.round(m.items.reduce((s: number, i: any) => s + i.theta, 0) / m.items.length),
    accuracy: answered.length
      ? Math.round(answered.reduce((s: number, i: any) => s + i.correct_count, 0) /
          answered.reduce((s: number, i: any) => s + i.correct_count + i.wrong_count, 0) * 100)
      : 0,
  }

  // ── 每日趋势折线图（平均掌握度：紫色渐变主线 + 数据点标注） ──
  const trend = buildTrend(
    stats.value.avgTheta,
    stats.value.mastered,
    items.value.filter(i => i.theta < 1500).length,
  )
  trendChart?.dispose()
  trendChart = echarts.init(trendEl.value!)
  trendChart.setOption({
    grid: { left: 8, right: 20, top: 24, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: (p: any) => `${p[0].axisValue}: 平均掌握度 ${p[0].value} 分`,
    },
    xAxis: {
      type: 'category', data: trend.days, boundaryGap: false,
      axisLabel: { color: INK.muted },
      axisLine: { lineStyle: { color: INK.baseline } },
    },
    yAxis: {
      type: 'value', min: 1000, max: 2000,
      axisLabel: { color: INK.muted },
      splitLine: { lineStyle: { color: INK.grid } },
    },
    series: [
      {
        name: '平均掌握度',
        type: 'line', smooth: true, data: trend.theta,
        lineStyle: { width: 3, color: '#7c3aed' },
        itemStyle: { color: '#7c3aed' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(124,58,237,0.25)' },
            { offset: 1, color: 'rgba(124,58,237,0)' },
          ]),
        },
        label: { show: true, fontSize: 10, color: INK.secondary, formatter: '{c}' },
      },
    ],
  })

  // ── 数量趋势（已掌握/薄弱各自独立的量纲与图，遵守"单轴"原则） ──
  countChart?.dispose()
  countChart = echarts.init(countEl.value!)
  countChart.setOption({
    grid: { left: 8, right: 20, top: 30, bottom: 24, containLabel: true },
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['已掌握', '薄弱'], top: 0,
      textStyle: { color: INK.secondary, fontSize: 11 },
    },
    xAxis: {
      type: 'category', data: trend.days, boundaryGap: false,
      axisLabel: { color: INK.muted },
      axisLine: { lineStyle: { color: INK.baseline } },
    },
    yAxis: {
      type: 'value', minInterval: 1,
      axisLabel: { color: INK.muted },
      splitLine: { lineStyle: { color: INK.grid } },
    },
    series: [
      {
        name: '已掌握', type: 'line', smooth: true, data: trend.mastered,
        lineStyle: { width: 2, type: 'dashed', color: '#10b981' },
        itemStyle: { color: '#10b981' },
      },
      {
        name: '薄弱', type: 'line', smooth: true, data: trend.weak,
        lineStyle: { width: 2, type: 'dashed', color: '#ef4444' },
        itemStyle: { color: '#ef4444' },
      },
    ],
  })

  chart?.dispose()
  chart = echarts.init(chartEl.value!)
  chart.setOption({
    grid: { left: 8, right: 40, top: 8, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (p: any) => `${p[0].name}<br/>θ = ${p[0].value}`,
    },
    xAxis: {
      type: 'value',
      min: 1000,
      max: 2000,
      axisLabel: { color: INK.muted },
      axisLine: { lineStyle: { color: INK.baseline } },
      splitLine: { lineStyle: { color: INK.grid } },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((i: any) => i.name),
      axisLabel: { color: INK.secondary },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: sorted.map((i: any) => i.theta),
        barMaxWidth: 18,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: (p: any) => barColor(p.value),
        },
        markLine: {
          symbol: 'none',
          lineStyle: { color: INK.baseline, type: 'dashed' },
          label: { color: INK.muted },
          data: [
            { xAxis: 1500, label: { formatter: '初始值' } },
            { xAxis: 1700, label: { formatter: '已掌握线', position: 'insideEndTop' } },
          ],
        },
      },
    ],
  })

  chart.on('click', (p: any) => {
    if (p.componentType === 'series') {
      const kp = m.items.find((i: any) => i.name === p.name)
      if (kp) openKp(kp)
    }
  })
}
</script>
