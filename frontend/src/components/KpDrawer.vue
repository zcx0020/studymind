<template>
  <transition name="slide">
    <div v-if="kp" class="fixed inset-0 z-40 bg-gray-900/20" @click.self="$emit('close')">
      <div class="absolute inset-y-0 right-0 flex w-[380px] flex-col border-l border-gray-200 bg-white shadow-2xl">
        <!-- 头部：渐变大图标 + 名称 + 状态 -->
        <header class="flex items-start justify-between border-b border-gray-100 px-6 py-5">
          <div class="flex items-start gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm">
              <BookOpen class="h-5 w-5 text-white" />
            </div>
            <div>
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="text-lg font-semibold tracking-tight text-gray-900">{{ kp.name }}</h3>
                <span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="statusBadge">
                  {{ statusText }}
                </span>
              </div>
              <p class="mt-1 text-xs text-gray-400">
                {{ kp.type || kp.kp_type }} · 掌握度 θ = {{ kp.theta }}
              </p>
            </div>
          </div>
          <button
            class="rounded-md p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
            @click="$emit('close')"
          >
            <X class="h-4 w-4" />
          </button>
        </header>

        <!-- 内容 -->
        <div class="flex-1 space-y-5 overflow-y-auto px-6 py-5">
          <p v-if="kp.definition" class="text-[13px] leading-5 text-gray-500">{{ kp.definition }}</p>

          <!-- AI 诊断（温暖鼓励语气） -->
          <div class="rounded-xl bg-indigo-50/70 p-4">
            <div class="flex items-center gap-1.5 text-xs font-semibold text-indigo-700">
              <Sparkles class="h-3.5 w-3.5" />AI 诊断
            </div>
            <p class="mt-2 text-[13px] leading-5 text-indigo-900/80">{{ diagnosis }}</p>
          </div>

          <!-- 错题列表 -->
          <div v-if="wrongQs.length">
            <div class="mb-2 flex items-center gap-1.5 text-xs font-semibold text-gray-700">
              <TriangleAlert class="h-3.5 w-3.5 text-orange-500" />
              历史错题（{{ wrongQs.length }}）
            </div>
            <div
              v-for="(w, i) in wrongQs"
              :key="i"
              class="mb-3 rounded-lg border border-gray-100 bg-gray-50/60 p-3.5"
            >
              <p class="text-[13px] font-medium leading-5 text-gray-800">{{ i + 1 }}. {{ w.stem }}</p>
              <div class="mt-2 space-y-1 text-[13px]">
                <p class="flex items-start gap-1.5 text-red-600">
                  <X class="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>你的答案：{{ w.wrong }}</span>
                </p>
                <p class="flex items-start gap-1.5 text-emerald-600">
                  <Check class="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>正确答案：{{ w.correct }}</span>
                </p>
              </div>
            </div>
          </div>
          <div v-else class="rounded-lg bg-emerald-50 px-4 py-3 text-[13px] text-emerald-700">
            🎉 该知识点暂无错题记录，保持得很好！
          </div>
        </div>

        <!-- 行动按钮（渐变） -->
        <footer class="border-t border-gray-100 p-4">
          <button
            class="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 py-2.5 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95"
            @click="goPractice"
          >
            🎯 针对薄弱点专项练习
          </button>
        </footer>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpen, Check, Sparkles, TriangleAlert, X } from 'lucide-vue-next'
import { mockDiagnosis, mockWrongQuestions } from '../mock'

const props = defineProps<{ kp: any }>()
const emit = defineEmits(['close'])
const router = useRouter()

const diagnosis = computed(() =>
  props.kp ? mockDiagnosis(props.kp.name, props.kp.theta) : '',
)
const wrongQs = computed(() =>
  props.kp ? mockWrongQuestions(props.kp.name, props.kp.theta) : [],
)

const statusText = computed(() => {
  if (!props.kp) return ''
  if (props.kp.mastered || props.kp.theta > 1700) return '已掌握'
  if (props.kp.theta < 1500) return '薄弱'
  return '学习中'
})
const statusBadge = computed(() =>
  ({
    已掌握: 'bg-emerald-50 text-emerald-600',
    薄弱: 'bg-orange-50 text-orange-600',
    学习中: 'bg-blue-50 text-blue-600',
  })[statusText.value],
)

function goPractice() {
  router.push('/quiz')
  emit('close')
}
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: opacity 0.2s ease;
}
.slide-enter-active > div,
.slide-leave-active > div {
  transition: transform 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
}
.slide-enter-from > div,
.slide-leave-to > div {
  transform: translateX(40px);
}
</style>
