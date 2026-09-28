<template>
  <div class="mx-auto max-w-6xl">
    <div class="mb-4">
      <h1 class="text-xl font-semibold tracking-tight text-gray-900">知识图谱</h1>
      <p class="mt-1 text-[13px] text-gray-500">节点颜色代表掌握状态，名称前红色角标为错题数；点击节点查看错题解析</p>
    </div>

    <!-- 激励栏 + 图谱统计 -->
    <StreakBar>
      <div class="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-emerald-400 to-green-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm">
        ✅ 已掌握 {{ stats.mastered }} 个节点
      </div>
      <div class="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-orange-400 to-red-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm">
        ⚠️ 薄弱 {{ stats.weak }} 个节点
      </div>
    </StreakBar>

    <div class="mb-4 flex flex-wrap items-center gap-3">
      <select
        v-model="docId"
        class="h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-purple-400 focus:ring-4 focus:ring-purple-500/10"
        @change="load"
      >
        <option v-for="d in docs" :key="d.id" :value="d.id">{{ d.title }}</option>
      </select>

      <button
        type="button"
        class="flex h-9 items-center gap-1.5 rounded-lg border px-3.5 text-sm font-medium transition active:scale-95"
        :class="pathMode
          ? 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
          : 'border-gray-200 bg-white text-gray-600 hover:border-purple-400 hover:text-purple-600'"
        @click="togglePath"
      >
        <Map class="h-4 w-4" />
        {{ pathMode ? '清除路径' : '推荐学习路径' }}
      </button>

      <!-- 状态图例（仅 4 种状态） -->
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
        <span class="inline-flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full border-2 border-gray-300 bg-white"></span>未学
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500"></span>学习中
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full bg-gradient-to-br from-emerald-400 to-green-500"></span>已掌握
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full bg-gradient-to-br from-orange-400 to-red-500"></span>薄弱
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-flex h-3 items-center rounded-full bg-red-500 px-1.5 text-[9px] font-bold text-white">2</span>错题数
        </span>
      </div>
    </div>

    <!-- 画布：内联样式高度兜底 -->
    <div
      ref="container"
      class="w-full overflow-hidden rounded-xl border border-gray-200/80 bg-white shadow-sm"
      :style="{ height: canvasHeight + 'px' }"
    ></div>

    <KpDrawer :kp="selectedKp" @close="selectedKp = null" />
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { Map } from 'lucide-vue-next'
import { api, Doc } from '../api'
import { REL_LABEL } from '../colors'
import { mockTheta, mockWrongCount } from '../mock'
import KpDrawer from '../components/KpDrawer.vue'
import StreakBar from '../components/StreakBar.vue'

const route = useRoute()
const container = ref<HTMLElement>()
const docs = ref<Doc[]>([])
const docId = ref<number | null>(route.params.docId ? Number(route.params.docId) : null)
const selectedKp = ref<any>(null)
const pathMode = ref(false)
const canvasHeight = ref(600)
const stats = reactive({ mastered: 0, weak: 0 })

let chart: echarts.ECharts | null = null
let graphData: { nodes: any[]; links: any[] } = { nodes: [], links: [] }

// 节点状态渐变（温暖配色）
const gradMastered = new echarts.graphic.LinearGradient(0, 0, 1, 1, [
  { offset: 0, color: '#4ade80' }, { offset: 1, color: '#059669' },
])
const gradLearning = new echarts.graphic.LinearGradient(0, 0, 1, 1, [
  { offset: 0, color: '#60a5fa' }, { offset: 1, color: '#4f46e5' },
])
const gradWeak = new echarts.graphic.LinearGradient(0, 0, 1, 1, [
  { offset: 0, color: '#fb923c' }, { offset: 1, color: '#ef4444' },
])

function nodeStyle(n: any) {
  if (n._meta.mastered) return { grad: gradMastered, border: '#059669', label: '#059669' }
  if (n._meta.theta < 1500) return { grad: gradWeak, border: '#ea580c', label: '#ea580c' }
  if (n._meta.theta === 1500) return { grad: null, border: '#d1d5db', label: '#6b7280' }
  return { grad: gradLearning, border: '#4f46e5', label: '#4f46e5' }
}

function buildOption(nodes: any[], links: any[], pathChain: string[] | null) {
  const chainSet = pathChain ? new Set(pathChain) : null
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p: any) =>
        p.dataType === 'node'
          ? `${p.data.name}<br/>θ = ${p.data._meta?.theta}（${p.data._meta?.mastered ? '已掌握' : p.data._meta?.theta < 1500 ? '薄弱' : '学习中'}）<br/>错题 ${p.data._meta?.wrongCount ?? 0} 道`
          : `${p.data.value || ''}：${p.data.source} → ${p.data.target}`,
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        force: { repulsion: 600, edgeLength: [130, 200], gravity: 0.08, friction: 0.6 },
        data: nodes.map((n) => {
          const st = chainSet?.has(n.id) ? { grad: gradMastered, border: '#059669', label: '#059669' } : nodeStyle(n)
          return {
            id: n.id,
            name: n.name,
            symbolSize: 34 + (n.importance || 3) * 6,
            itemStyle: {
              color: st.grad ?? '#ffffff',
              borderColor: st.border,
              borderWidth: chainSet?.has(n.id) ? 5 : 2.5,
            },
            label: {
              show: true,
              position: 'bottom',
              distance: 8,
              color: st.label,
              fontSize: 12,
              fontWeight: 600,
              formatter: (p: any) => {
                const badge = p.data._meta?.wrongCount || 0
                return badge > 0 ? `{badge|${badge}} ${p.name}` : p.name
              },
              rich: {
                badge: {
                  color: '#ffffff', backgroundColor: '#ef4444', borderRadius: 9,
                  padding: [1, 6], fontSize: 10, fontWeight: 'bold',
                },
              },
            },
            _meta: n._meta,
          }
        }),
        links: links.map((l) => ({
          source: l.source,
          target: l.target,
          value: REL_LABEL[l._type] || '',
          lineStyle: chainSet?.has(l._chainKey)
            ? { color: '#10b981', width: 4.5, curveness: 0.1 }
            : {
                color: '#9ca3af', width: 2, curveness: 0.1,
                type: l._type === 'CONTRASTS_WITH' ? 'dashed' : 'solid',
              },
        })),
        // 连线：加粗浅灰 + 箭头（关系文字用紫色点缀）
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 10],
        edgeLabel: {
          show: true,
          formatter: (p: any) => p.data.value || '',
          color: '#7c3aed',
          fontSize: 13,
          backgroundColor: '#ffffff',
          padding: [2, 4],
        },
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
      },
    ],
  }
}

onMounted(async () => {
  canvasHeight.value = Math.max(520, window.innerHeight - 260)
  docs.value = await api.listDocuments()
  if (!docId.value && docs.value.length) docId.value = docs.value[0].id
  if (docId.value) await load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  chart?.dispose()
  window.removeEventListener('resize', onResize)
})

function onResize() {
  canvasHeight.value = Math.max(520, window.innerHeight - 260)
  chart?.resize()
}

async function load() {
  if (!docId.value) return
  const [g, m] = await Promise.all([api.getGraph(docId.value), api.getMastery(docId.value)])
  const thetaMap: Record<string, any> = {}
  m.items.forEach((it: any) => (thetaMap[it.name] = it))

  console.log('[GraphView] 图谱数据:', { nodes: g.nodes.length, edges: g.edges.length, sampleNode: g.nodes[0] })
  if (!g.nodes?.length) {
    ElMessage.warning('该教材暂无知识点数据')
    return
  }

  const nodes = g.nodes.map((n: any, i: number) => {
    const st = thetaMap[n.name]
    let theta = st ? st.theta : 1500
    let mastered = !!st?.mastered
    if (!st || st.correct_count + st.wrong_count === 0) {
      theta = mockTheta(i)
      mastered = theta > 1700
    }
    const wrongCount = st && st.wrong_count > 0 ? st.wrong_count : mockWrongCount(n.name, theta)
    return {
      id: n.name,
      name: n.name,
      importance: n.importance || 3,
      _meta: { ...n, theta, mastered, wrongCount },
    }
  })

  const links = g.edges.map((e: any) => ({
    source: e.source,
    target: e.target,
    _type: e.type,
    _chainKey: `${e.source}->${e.target}`,
  }))

  graphData = { nodes, links }
  pathMode.value = false
  stats.mastered = nodes.filter(n => n._meta.mastered).length
  stats.weak = nodes.filter(n => n._meta.theta < 1500).length

  await nextTick()
  const w = container.value?.clientWidth || 900
  const h = container.value?.clientHeight || 600
  console.log('[GraphView] 画布尺寸:', { width: w, height: h })

  chart?.dispose()
  chart = echarts.init(container.value!, undefined, { width: w, height: h })
  chart.setOption(buildOption(nodes, links, null), true)
  chart.on('click', (p: any) => {
    if (p.dataType === 'node') selectedKp.value = p.data._meta
  })
}

// ── 推荐学习路径：沿 PREREQUISITE_OF 从最薄弱知识点回溯到根，再延伸至叶子 ──
function togglePath() {
  if (!chart) return
  if (pathMode.value) {
    chart.setOption(buildOption(graphData.nodes, graphData.links, null), true)
    pathMode.value = false
    return
  }

  const succ: Record<string, string[]> = {}
  const pred: Record<string, string[]> = {}
  graphData.links.forEach((l: any) => {
    if (l._type !== 'PREREQUISITE_OF') return
    ;(succ[l.source] ||= []).push(l.target)
    ;(pred[l.target] ||= []).push(l.source)
  })
  if (!Object.keys(succ).length && !Object.keys(pred).length) {
    ElMessage.info('该知识库暂未抽取到前置关系，无法推荐路径')
    return
  }

  const thetaOf: Record<string, number> = {}
  graphData.nodes.forEach((n: any) => (thetaOf[n.id] = n._meta.theta))
  const sorted = [...graphData.nodes].sort((a, b) => thetaOf[a.id] - thetaOf[b.id])
  const weak = sorted.find((n) => pred[n.id]?.length) || sorted[0]

  const chain: string[] = [weak.id]
  let cur = weak.id
  while (pred[cur]?.length) {
    cur = pred[cur][0]
    chain.unshift(cur)
  }
  cur = weak.id
  while (succ[cur]?.length) {
    cur = succ[cur][0]
    chain.push(cur)
  }

  chart.setOption(buildOption(graphData.nodes, graphData.links, chain), true)
  pathMode.value = true
  ElMessage.success(`推荐路径：${chain.join(' → ')}`)
}
</script>
