<template>
  <div class="mb-5 flex flex-wrap items-center gap-2.5">
    <!-- 连续打卡（橙红渐变）：全局统计，答题后自动刷新 -->
    <div class="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-orange-400 to-red-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm">
      🔥 连续打卡 {{ stats.streakDays }} 天
    </div>
    <!-- 今日学习（蓝色渐变） -->
    <div class="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-blue-400 to-indigo-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm">
      ⏱️ 今日学习 {{ stats.todayMinutes }} 分钟
    </div>
    <!-- 今日目标（紫色渐变） -->
    <div class="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm">
      🎯 今日目标 {{ stats.goalDone }}/{{ stats.goalTotal }}
    </div>
    <!-- 页面自定义激励 -->
    <slot />
  </div>
</template>

<script setup lang="ts">
// 全局激励栏：数据来自 Pinia stats store，任何页面答题后立即联动刷新
import { useStatsStore } from '../stores/stats'

const stats = useStatsStore()
</script>
