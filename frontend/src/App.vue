<template>
  <div class="min-h-screen bg-gray-50">
    <!-- 左侧固定侧边栏 -->
    <aside class="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-gray-200/80 bg-white">
      <!-- Logo -->
      <div class="flex items-center gap-2.5 px-5 pb-5 pt-6">
        <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-sm shadow-indigo-200">
          <Brain class="h-5 w-5 text-white" />
        </div>
        <div>
          <div class="text-[15px] font-semibold tracking-tight text-gray-900">StudyMind</div>
          <div class="text-[11px] text-gray-400">AI 学习助手</div>
        </div>
      </div>

      <!-- 导航 -->
      <nav class="flex-1 space-y-1 px-3">
        <router-link
          v-for="item in nav"
          :key="item.path"
          :to="item.path"
          class="group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors"
          :class="active === item.path
            ? 'bg-indigo-50 text-indigo-700'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'"
        >
          <!-- 选中指示器（左侧竖条） -->
          <span
            v-if="active === item.path"
            class="absolute -left-3 h-4 w-1 rounded-r-full bg-indigo-600"
          ></span>
          <component
            :is="item.icon"
            class="h-[18px] w-[18px] transition-colors"
            :class="active === item.path ? 'text-indigo-600' : 'text-gray-400 group-hover:text-gray-500'"
          />
          {{ item.label }}
        </router-link>
      </nav>

      <!-- 底部用户 -->
      <div class="border-t border-gray-100 p-4">
        <div class="flex items-center gap-3 rounded-lg px-2 py-1.5">
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-[11px] font-semibold text-gray-600">
            D
          </div>
          <div class="min-w-0">
            <div class="truncate text-[13px] font-medium text-gray-800">demo 用户</div>
            <div class="text-[11px] text-gray-400">课程演示账号</div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧内容区 -->
    <main class="ml-60 flex-1 p-8">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { BarChart3, Brain, CalendarDays, Library, Network, PencilLine } from 'lucide-vue-next'

const route = useRoute()

// 当前一级路由（/graph/1 → /graph）
const active = computed(() => {
  const seg = route.path.split('/')[1]
  return seg ? `/${seg}` : '/'
})

const nav = [
  { path: '/', label: '我的知识库', icon: Library },
  { path: '/graph', label: '知识图谱', icon: Network },
  { path: '/plan', label: '学习计划', icon: CalendarDays },
  { path: '/quiz', label: '答题练习', icon: PencilLine },
  { path: '/dashboard', label: '掌握度看板', icon: BarChart3 },
]
</script>
