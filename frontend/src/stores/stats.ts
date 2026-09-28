import { defineStore } from 'pinia'

/**
 * 全局学习统计（所有页面顶部激励栏共用，答题后实时联动）
 * - recordAnswer()   每题提交成功后立即调用 → 连续答对/今日答题数立刻刷新
 * - recordSession()  会话结束（查看总结）时调用 → 打卡/时长/目标进度刷新
 * 初始值为演示基线（接入点：登录时从用户统计接口拉取）
 */
export const useStatsStore = defineStore('stats', {
  state: () => ({
    streakDays: 7,        // 连续打卡天数
    todayMinutes: 32,     // 今日学习分钟
    goalDone: 3,          // 今日目标完成数
    goalTotal: 5,
    answeredToday: 0,     // 今日已答题数（会话累计）
    correctToday: 0,
    answerStreak: 0,      // 连续答对题数（跨页面共享，答错清零）
  }),
  actions: {
    /** 每题提交成功后调用：答题数累加、连对/断连即时更新 */
    recordAnswer(isCorrect: boolean) {
      this.answeredToday += 1
      if (isCorrect) {
        this.correctToday += 1
        this.answerStreak += 1
      } else {
        this.answerStreak = 0
      }
    },
    /** 会话结束调用：打卡 +1、时长累加、目标进度刷新 */
    recordSession(minutes: number) {
      this.streakDays += 1
      this.todayMinutes += Math.max(1, minutes)
      // 演示口径：每完成 5 题记 1 个目标单位
      this.goalDone = Math.min(this.goalTotal, Math.max(this.goalDone, Math.ceil(this.answeredToday / 5)))
    },
  },
})
