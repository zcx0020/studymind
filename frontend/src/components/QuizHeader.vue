<template>
  <!-- 学习状态栏（Sticky Header）：计时器独立在本组件内，每秒只重渲染这一小块，
       避免整个答题页每秒全量 diff 导致"页面没有响应" -->
  <div class="sticky top-0 z-30 mb-5 rounded-xl border border-gray-200/80 bg-white/90 px-5 py-3 shadow-sm">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2 text-sm font-semibold tabular-nums text-gray-800">
        <Timer v-if="!examMode" class="h-4 w-4 text-purple-500" />
        <AlarmClock v-else class="h-4 w-4 text-purple-500" />
        {{ examMode ? examTimeText : timeText }}
        <span v-if="examMode" class="text-[11px] font-normal text-gray-400">考试剩余</span>
      </div>
      <div class="flex min-w-40 flex-1 items-center gap-3">
        <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-100">
          <div
            class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-500"
            :style="{ width: progressPct + '%' }"
          ></div>
        </div>
        <span class="whitespace-nowrap text-xs tabular-nums text-gray-500">
          已做 {{ answeredCount }} / 共 {{ totalCount }} 题
        </span>
      </div>
      <div class="flex items-center gap-1 text-[11px] text-gray-400">
        <Save class="h-3 w-3" />答案已自动保存
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { AlarmClock, Save, Timer } from 'lucide-vue-next'

const props = defineProps<{
  progressPct: number
  answeredCount: number
  totalCount: number
  examMode: boolean
  examTimeText: string
}>()

// 计时器只在子组件内更新（隔离渲染范围）
const seconds = ref(0)
let timerId: number | undefined

onMounted(() => {
  timerId = window.setInterval(() => seconds.value++, 1000)
})
onBeforeUnmount(() => {
  if (timerId) clearInterval(timerId)
})

const timeText = computed(() => {
  const h = Math.floor(seconds.value / 3600)
  const m = Math.floor((seconds.value % 3600) / 60)
  const s = seconds.value % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
})
</script>
