<template>
  <div class="mx-auto max-w-3xl pb-24">
    <!-- 标题（随 Tab 变化） -->
    <div class="mb-4">
      <h1 class="text-xl font-semibold tracking-tight text-gray-900">{{ tabTitle }}</h1>
      <p class="mt-1 text-[13px] text-gray-500">{{ tabSubtitle }}</p>
    </div>

    <StreakBar>
      <div class="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm">
        ⚡ 连续答对 {{ stats.answerStreak }} 题
      </div>
    </StreakBar>

    <!-- ① 学习状态栏 -->
    <QuizHeader
      :progress-pct="progressPct"
      :answered-count="answeredCount"
      :total-count="total"
      :exam-mode="activeTab === 'exam' && examActive"
      :exam-time-text="examTimeText"
    />

    <!-- ② Tab 切换栏 -->
    <div class="mb-4 flex rounded-xl border border-gray-200/80 bg-white p-1 shadow-sm">
      <button
        v-for="t in TABS"
        :key="t.key"
        type="button"
        class="flex-1 rounded-lg px-3 py-2 text-sm font-medium transition active:scale-95"
        :class="activeTab === t.key
          ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-sm'
          : 'text-gray-600 hover:bg-purple-50'"
        @click="switchTab(t.key)"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- ③ 各 Tab 的控制区 -->
    <div v-if="activeTab === 'daily'" class="mb-4 flex items-center gap-3">
      <select
        v-model="planId"
        class="h-9 flex-1 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-purple-400 focus:ring-4 focus:ring-purple-500/10"
        @change="loadCurrent"
      >
        <option v-for="p in plans" :key="p.id" :value="p.id">#{{ p.id }} {{ p.title }}</option>
      </select>
      <button
        type="button"
        class="flex h-9 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3.5 text-sm font-medium text-gray-600 transition hover:border-purple-400 hover:text-purple-600"
        :disabled="phase === 'loading'"
        @click="loadCurrent"
      >
        <RefreshCw class="h-3.5 w-3.5" :class="phase === 'loading' && 'animate-spin'" />
        刷新题目
      </button>
    </div>

    <div v-else-if="activeTab === 'kp'" class="mb-4 flex flex-wrap items-center gap-3">
      <select
        v-model="selDocId"
        class="h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-purple-400 focus:ring-4 focus:ring-purple-500/10"
        @change="onKpDocChange"
      >
        <option :value="null" disabled>选择教材</option>
        <option v-for="d in docs" :key="d.id" :value="d.id">{{ d.title }}</option>
      </select>
      <select
        v-model="selKpId"
        class="h-9 flex-1 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-purple-400 focus:ring-4 focus:ring-purple-500/10"
        :disabled="!kpList.length"
        @change="loadCurrent"
      >
        <option :value="null" disabled>选择知识点（薄弱点优先）</option>
        <option v-for="k in kpList" :key="k.id" :value="k.id">
          {{ k.is_weak ? '🔴 ' : '' }}{{ k.name }}（θ={{ k.theta }}）
        </option>
      </select>
      <button
        type="button"
        :disabled="!selKpId || phase === 'loading'"
        class="flex h-9 items-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-4 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:opacity-50"
        @click="loadCurrent"
      >
        {{ phase === 'loading' ? '出题中…' : '开始专项练习' }}
      </button>
    </div>

    <div v-else class="mb-4 flex flex-wrap items-center gap-3">
      <select
        v-model="selDocId"
        class="h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-purple-400 focus:ring-4 focus:ring-purple-500/10"
        @change="onKpDocChange"
      >
        <option :value="null" disabled>选择教材</option>
        <option v-for="d in docs" :key="d.id" :value="d.id">{{ d.title }}</option>
      </select>
      <select
        v-model="examCount"
        class="h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-purple-400 focus:ring-4 focus:ring-purple-500/10"
      >
        <option :value="10">10 题</option>
        <option :value="20">20 题</option>
        <option :value="30">30 题</option>
      </select>
      <button
        type="button"
        :disabled="!selDocId || phase === 'loading'"
        class="flex h-9 items-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-4 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:opacity-50"
        @click="loadCurrent"
      >
        {{ phase === 'loading' ? '组卷中…' : '开始考试' }}
      </button>
      <span
        v-if="examActive && activeTab === 'exam'"
        class="rounded-full px-3 py-1 text-xs font-semibold tabular-nums"
        :class="examRemain < 300 ? 'bg-red-50 text-red-600' : 'bg-indigo-50 text-indigo-700'"
      >
        ⏳ {{ examTimeText }}
      </span>
    </div>

    <!-- ④ 状态机视图：idle 错误提示 / loading 出题中 / 答题向导 / 总结 -->
    <div v-if="loadError && phase === 'idle'" class="mb-4 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-5 py-4">
      <span class="flex items-center gap-2 text-sm text-red-700">
        <TriangleAlert class="h-4 w-4 shrink-0" />
        ⚠️ 题目加载失败：{{ loadError }}
      </span>
      <button
        class="shrink-0 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-50 active:scale-95"
        @click="loadCurrent"
      >
        点击重试
      </button>
    </div>

    <!-- 出题中：异步任务 + 轮询，页面全程可操作，绝不阻塞 -->
    <div v-if="phase === 'loading'" class="flex flex-col items-center justify-center rounded-xl border border-gray-200/80 bg-white py-16 shadow-sm">
      <Loader2 class="h-7 w-7 animate-spin text-purple-500" />
      <p class="mt-3 text-sm font-medium text-gray-700">🤖 AI 正在出题…</p>
      <p class="mt-1 text-xs text-gray-400">{{ loadHint || '已预生成的题库秒开；新题约 15~20 秒/道' }}</p>
      <p class="mt-1.5 text-[11px] text-amber-500">
        题目较多时生成更久——页面可正常操作，也可以先切到其他 Tab 逛逛～
      </p>
    </div>

    <!-- 答题向导：answering（作答）→ result（对错+解析） -->
    <template v-if="(phase === 'answering' || phase === 'result') && current">
      <!-- 题目导航点：可回看已答题 / 跳回当前待答题 -->
      <div v-if="total" class="mb-4 flex flex-wrap items-center gap-2">
        <button
          v-for="(f, i) in flatQuestions"
          :key="f.q.id"
          type="button"
          :disabled="!canJump(i)"
          class="h-2.5 w-2.5 rounded-full transition"
          :class="[dotClass(i), canJump(i) ? 'hover:scale-125' : 'cursor-not-allowed opacity-30']"
          :title="`第 ${i + 1} 题`"
          @click="jumpTo(i)"
        />
      </div>

      <!-- 当前题目卡片 -->
      <section class="mb-4 rounded-xl border border-gray-200/80 bg-white p-6 shadow-sm">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <span class="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700">{{ current.kp.name }}</span>
          <span class="text-xs tabular-nums text-gray-400">第 {{ currentIndex + 1 }}/{{ total }} 题 · θ = {{ current.kp.theta }}</span>
          <span
            v-if="current.kp.diagnosis"
            class="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200"
          >
            <TriangleAlert class="h-3 w-3" />{{ current.kp.diagnosis.root_cause }}
          </span>
        </div>

        <p class="text-[16px] font-semibold leading-7 text-gray-900">{{ current.q.stem }}</p>

        <!-- 客观题选项 -->
        <div v-if="hasOptions" class="mt-4 space-y-2.5">
          <button
            v-for="(opt, i) in (current.q.options || [])"
            :key="i"
            type="button"
            :disabled="phase === 'result'"
            class="flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm transition"
            :class="optionClass(i)"
            @click="selectOption('ABCDEFGH'[i])"
          >
            <span
              class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs font-semibold transition"
              :class="letterClass(i)"
            >
              {{ 'ABCDEFGH'[i] }}
            </span>
            <span class="flex-1">{{ opt }}</span>
            <Check v-if="isCorrectOption(i)" class="h-4 w-4 shrink-0 text-emerald-600" />
            <X v-else-if="isChosenWrong(i)" class="h-4 w-4 shrink-0 text-red-500" />
          </button>
        </div>

        <!-- 主观题 / 填空：文本输入 -->
        <textarea
          v-else-if="needsTextInput"
          v-model="textAnswer"
          rows="3"
          :disabled="phase === 'result'"
          placeholder="在此输入你的答案…"
          class="mt-4 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-purple-400 focus:ring-2 focus:ring-purple-500/10 disabled:bg-gray-50"
        />

        <p v-else class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
          ⚠️ 题目数据异常（缺少选项），请点击上方"刷新题目"重新加载
        </p>

        <!-- 提交本题（answering 阶段） -->
        <div v-if="phase === 'answering' && hasDraft" class="mt-4 flex justify-end">
          <button
            type="button"
            :disabled="isSubmitting"
            class="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:opacity-60"
            @click="handleSubmit"
          >
            <Loader2 v-if="isSubmitting" class="h-3.5 w-3.5 animate-spin" />
            提交本题
          </button>
        </div>

        <!-- 本题结果（result 阶段） -->
        <div v-if="phase === 'result' && lastResult" class="mt-4">
          <div class="flex flex-wrap items-center gap-2">
            <template v-if="gradingPending">
              <span class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-600">
                <Loader2 class="h-3 w-3 animate-spin" /> AI 批改中…
              </span>
            </template>
            <template v-else>
              <span
                class="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium"
                :class="lastResult.is_correct ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'"
              >
                {{ lastResult.is_correct ? '✅ 回答正确！' : '❌ 回答错误。' }}
                <span v-if="lastResult.mastery?.delta !== undefined" class="tabular-nums">
                  Elo {{ lastResult.mastery.delta >= 0 ? '+' : '' }}{{ lastResult.mastery.delta.toFixed(1) }}
                </span>
              </span>
              <span class="rounded-full bg-orange-50 px-2.5 py-0.5 text-xs font-medium tabular-nums text-orange-600">
                🔥 连对 {{ lastResult.mastery?.streak ?? 0 }}
              </span>
              <span v-if="lastResult.correct_answer !== undefined" class="text-xs text-gray-400">
                正确答案：{{ lastResult.correct_answer }}
              </span>
            </template>
          </div>

          <!-- 分层解析 -->
          <div v-if="!gradingPending" class="mt-3 rounded-lg border-l-4 border-blue-400 bg-blue-50 px-4 py-3">
            <p class="text-[13px] leading-5 text-blue-900">{{ brief }}</p>
            <button
              v-if="steps.length"
              class="mt-2 flex items-center gap-1 text-xs font-medium text-blue-600 transition hover:text-blue-700"
              @click="toggleSteps"
            >
              {{ stepsOpen[current.q.id] ? '收起详解' : '展开详解' }}
              <ChevronDown class="h-3 w-3 transition-transform" :class="stepsOpen[current.q.id] ? '' : '-rotate-90'" />
            </button>
            <ol v-if="stepsOpen[current.q.id]" class="mt-2 list-decimal space-y-1 pl-4 text-[13px] leading-5 text-blue-900">
              <li v-for="(s, i) in steps" :key="i">{{ s }}</li>
            </ol>
          </div>
          <p v-else class="mt-3 rounded-lg bg-blue-50 px-4 py-3 text-xs leading-5 text-blue-700">
            主观题由 AI 按评分细则批改（约 10~30 秒），批改完成后自动显示结果与评语。
          </p>

          <!-- 诊断（后台任务轮询回填） -->
          <div v-if="diagPending[current.q.id]" class="mt-3 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700">
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
            🧠 AI 正在生成学习诊断（约 10~30 秒），可以先看解析～
          </div>
          <div v-else-if="lastResult.diagnosis" class="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <div class="flex items-center gap-1.5 text-xs font-semibold text-amber-800">
              <TriangleAlert class="h-3.5 w-3.5" />
              学习诊断：{{ lastResult.diagnosis.root_cause }}
            </div>
            <p class="mt-1.5 text-xs leading-5 text-amber-700">
              补学路径：{{ (lastResult.diagnosis.remedy_path || []).join(' → ') }}
              <br />
              学习计划已自动调整 {{ lastResult.diagnosis.changes?.length ?? 0 }} 项
            </p>
          </div>

          <!-- AI 助教（演示） -->
          <div class="mt-3">
            <button
              class="flex items-center gap-1.5 rounded-lg border border-purple-200 bg-white px-3 py-1.5 text-xs font-medium text-purple-600 transition hover:bg-purple-50 active:scale-95"
              @click="toggleChat"
            >
              <Bot class="h-3.5 w-3.5" />
              {{ chats[current.q.id]?.open ? '收起 AI 助教' : '🤖 还是不懂？问 AI' }}
            </button>

            <div v-if="chats[current.q.id]?.open" class="mt-2 overflow-hidden rounded-xl border border-purple-100 bg-purple-50/40">
              <div class="max-h-64 space-y-2 overflow-y-auto p-3">
                <div v-for="(msg, mi) in (chats[current.q.id]?.messages || [])" :key="mi" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                  <div
                    class="max-w-[85%] rounded-xl px-3 py-2 text-[13px] leading-5"
                    :class="msg.role === 'user'
                      ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white'
                      : 'bg-white text-gray-700 shadow-sm'"
                  >
                    {{ msg.text }}
                    <button
                      v-if="msg.jumpGraph"
                      class="mt-1.5 block text-xs font-medium text-purple-600 underline underline-offset-2"
                      @click="router.push(`/graph/${current.kp.doc_id}`)"
                    >
                      查看知识图谱 →
                    </button>
                  </div>
                </div>
                <div v-if="chats[current.q.id]?.typing" class="flex justify-start">
                  <div class="rounded-xl bg-white px-3 py-2 text-xs text-gray-400 shadow-sm">
                    AI 助教正在思考<span class="animate-pulse">…</span>
                  </div>
                </div>
              </div>

              <div class="border-t border-purple-100 p-2.5">
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="p in PRESETS"
                    :key="p"
                    class="rounded-full border border-purple-200 bg-white px-2.5 py-1 text-[11px] text-purple-600 transition hover:bg-purple-50 active:scale-95"
                    @click="ask(p)"
                  >
                    {{ p }}
                  </button>
                </div>
                <div class="mt-2 flex gap-2">
                  <input
                    v-model="chatInput[current.q.id]"
                    type="text"
                    placeholder="向 AI 助教自由提问…"
                    class="h-9 flex-1 rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none transition focus:border-purple-400 focus:ring-2 focus:ring-purple-500/10"
                    @keyup.enter="ask(chatInput[current.q.id] || '')"
                  />
                  <button
                    class="flex h-9 items-center gap-1 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-3.5 text-xs font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95"
                    @click="ask(chatInput[current.q.id] || '')"
                  >
                    <Send class="h-3.5 w-3.5" />发送
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 关键分叉：最后一题 → 查看总结；否则 → 下一题 -->
          <div class="mt-4 flex justify-end gap-2">
            <button
              v-if="!isLastQuestion"
              type="button"
              class="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95"
              @click="handleNext"
            >
              下一题
              <ArrowRight class="h-3.5 w-3.5" />
            </button>
            <button
              v-else
              type="button"
              :disabled="gradingPending"
              class="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:from-emerald-600 hover:to-teal-700 active:scale-95 disabled:opacity-60"
              @click="handleFinish"
            >
              <Loader2 v-if="gradingPending" class="h-3.5 w-3.5 animate-spin" />
              {{ gradingPending ? 'AI 批改中，请稍候…' : '🎉 查看总结' }}
            </button>
          </div>
        </div>
      </section>
    </template>

    <!-- ⑤ finished：总结页（异步总结任务轮询回填，秒开） -->
    <section v-if="phase === 'finished'" class="rounded-xl border border-gray-200/80 bg-white p-8 shadow-sm">
      <div class="text-center">
        <div class="text-5xl">🎉</div>
        <h3 class="mt-3 text-2xl font-bold tracking-tight text-gray-900">练习完成！</h3>
        <div class="mt-4 bg-gradient-to-r from-indigo-500 to-purple-600 bg-clip-text text-6xl font-bold tabular-nums text-transparent">
          {{ summaryAccuracy }}%
        </div>
        <div class="mt-1 text-sm text-gray-500">
          正确率 · 用时 {{ summaryMinutes }} 分钟 · 共 {{ total }} 题
        </div>
      </div>

      <!-- 总结生成中（后台任务，1~2 秒） -->
      <div v-if="summaryLoading" class="mt-6 flex items-center justify-center gap-2 rounded-xl bg-gray-50 py-8 text-sm text-gray-500">
        <Loader2 class="h-4 w-4 animate-spin text-purple-500" />
        正在汇总本次练习（掌握度变化 / 错题回顾）…
      </div>

      <template v-else>
        <!-- 掌握度变化（Elo） -->
        <div class="mt-6 rounded-xl bg-gray-50 p-4 text-left">
          <div class="text-xs font-semibold text-gray-500">掌握度变化（Elo）</div>
          <div v-for="s in eloChanges" :key="s.name" class="mt-2 flex items-center justify-between text-sm">
            <span class="font-medium text-gray-800">{{ s.name }}</span>
            <span class="tabular-nums">
              <span :class="deltaSign(s) === 1 ? 'text-emerald-600' : deltaSign(s) === -1 ? 'text-red-500' : 'text-gray-400'">
                {{ s.before ?? '—' }} → {{ s.after ?? '—' }}
              </span>
              <span
                v-if="s.before != null && s.after != null"
                class="ml-1.5 text-xs"
                :class="deltaSign(s) === 1 ? 'text-emerald-500' : deltaSign(s) === -1 ? 'text-red-400' : 'text-gray-300'"
              >
                ({{ s.after > s.before ? '+' : '' }}{{ (s.after - s.before).toFixed(1) }})
              </span>
            </span>
          </div>
          <div v-if="!eloChanges.length" class="mt-2 text-xs text-gray-400">暂无答题记录</div>
        </div>

        <div v-if="weakNames.length" class="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-left text-[13px] leading-5 text-amber-800">
          ⚠️ 发现 {{ weakNames.length }} 个薄弱点（{{ weakNames.join('、') }}），建议立即复习
        </div>
        <div v-else class="mt-4 rounded-lg bg-emerald-50 px-4 py-3 text-[13px] text-emerald-700">
          🌟 全部答对，太强了！继续保持！
        </div>

        <!-- 错题回顾 -->
        <div v-if="wrongQuestions.length" class="mt-4 max-h-60 overflow-y-auto rounded-xl border border-red-100 bg-red-50/40 p-4 text-left">
          <div class="text-xs font-semibold text-red-600">📝 错题回顾（{{ wrongQuestions.length }} 题）</div>
          <div v-for="(w, i) in wrongQuestions" :key="i" class="mt-2 rounded-lg bg-white p-3 shadow-sm">
            <p class="text-[13px] font-medium leading-5 text-gray-800">{{ i + 1 }}. {{ w.stem }}</p>
            <p class="mt-1.5 flex items-start gap-1.5 text-xs leading-5 text-red-600">
              <X class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>你的答案：{{ w.user_answer }}</span>
            </p>
            <p class="mt-0.5 flex items-start gap-1.5 text-xs leading-5 text-emerald-600">
              <Check class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>正确答案：{{ w.correct_answer }}</span>
            </p>
            <p class="mt-1.5 text-xs leading-4 text-gray-500">💡 {{ w.analysis }}</p>
          </div>
        </div>

        <div class="mt-6 flex justify-center gap-2">
          <button
            class="rounded-lg border border-purple-300 bg-white px-4 py-2 text-sm font-medium text-purple-600 transition hover:bg-purple-50 active:scale-95"
            @click="loadCurrent"
          >
            🔄 再来一轮
          </button>
          <button
            class="rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:from-indigo-600 hover:to-purple-700 active:scale-95"
            @click="router.push('/')"
          >
            🏠 返回知识库
          </button>
          <button
            class="rounded-lg border border-purple-300 bg-white px-4 py-2 text-sm font-medium text-purple-600 transition hover:bg-purple-50 active:scale-95"
            @click="router.push('/dashboard')"
          >
            📊 去掌握度看板
          </button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowRight, Bot, Check, ChevronDown, Loader2, RefreshCw, Send, TriangleAlert, X,
} from 'lucide-vue-next'
import { api, Doc, PlanSummary, SummaryPayload, TaskStatus } from '../api'
import QuizHeader from '../components/QuizHeader.vue'
import StreakBar from '../components/StreakBar.vue'
import { useStatsStore } from '../stores/stats'

/**
 * 答题练习状态机（逐题向导）：
 *   idle ──开始──▶ loading（异步出题+轮询）──▶ answering ──提交本题──▶ result
 *   result ──下一题──▶ answering（下一题）
 *   result（最后一题）──查看总结──▶ finished（异步总结任务轮询回填）
 * 硬性保证：isSubmitting 在 finally 中必重置，按钮永不卡死；
 *           任何 LLM 调用都在后端后台线程，前端只做轮询，主线程永不阻塞。
 */
type TabKey = 'daily' | 'kp' | 'exam'
type Phase = 'idle' | 'loading' | 'answering' | 'result' | 'finished'
const TABS: { key: TabKey; label: string }[] = [
  { key: 'daily', label: '🎯 每日任务' },
  { key: 'kp', label: '📖 知识点专项' },
  { key: 'exam', label: '📚 阶段总考' },
]

const route = useRoute()
const router = useRouter()
const stats = useStatsStore()

const activeTab = ref<TabKey>('daily')
const phase = ref<Phase>('idle')

// ── 配置区 ──
const plans = ref<PlanSummary[]>([])
const planId = ref<number | null>(route.params.planId ? Number(route.params.planId) : null)
const dailyQuiz = ref<any>(null)
const docs = ref<Doc[]>([])
const selDocId = ref<number | null>(null)
const kpList = ref<any[]>([])
const selKpId = ref<number | null>(null)
const examCount = ref(20)
const examTitle = ref('')
const examRemain = ref(45 * 60)
const examActive = ref(false)
let examTimerId: number | undefined

// ── 加载 ──
const loadError = ref('')
const loadHint = ref('')

// ── 会话答题状态 ──
const quizItems = ref<any[]>([])
const currentIndex = ref(0)
const selected = ref('')
const textAnswer = ref('')
const isSubmitting = ref(false)
const sessionResults = reactive<Record<number, any>>({})
const diagPending = reactive<Record<number, boolean>>({})
const summaryTaskId = ref<string | null>(null)
const summary = ref<SummaryPayload | null>(null)
const summaryLoading = ref(false)
const countedStreak = new Set<number>()      // 已计入全局连对的题目（主观题批改完成时补计）
const questionStartedAt = ref(Date.now())

// ── 计时 ──
const seconds = ref(0)
let timerId: number | undefined
let pollEpoch = 0                            // 每次重载/切 Tab 递增，作废所有旧轮询

const stepsOpen = reactive<Record<number, boolean>>({})

// ── 派生状态 ──
const flatQuestions = computed(() =>
  quizItems.value.flatMap((it: any) => it.questions.map((q: any) => ({ kp: it, q }))),
)
const total = computed(() => flatQuestions.value.length)
const current = computed(() => flatQuestions.value[currentIndex.value] ?? null)
const isLastQuestion = computed(() => total.value > 0 && currentIndex.value >= total.value - 1)
const lastResult = computed(() => {
  const qid = current.value?.q.id
  return qid != null ? sessionResults[qid] ?? null : null
})
const gradingPending = computed(() =>
  !!lastResult.value && !!lastResult.value.grading_task_id && lastResult.value.is_correct == null,
)
const hasOptions = computed(() => (current.value?.q.options || []).length > 0)
const needsTextInput = computed(() => {
  const t = current.value?.q.qtype
  return t === 'short_answer' || t === 'fill_blank' || t === 'true_false'
})
const hasDraft = computed(() =>
  hasOptions.value ? !!selected.value : textAnswer.value.trim().length > 0,
)
const answeredCount = computed(() => Object.keys(sessionResults).length)
const correctCount = computed(() =>
  flatQuestions.value.filter(f => sessionResults[f.q.id]?.is_correct === true).length,
)
const accuracy = computed(() =>
  total.value ? Math.round((correctCount.value / total.value) * 100) : 0,
)
const progressPct = computed(() =>
  total.value ? Math.round((answeredCount.value / total.value) * 100) : 0,
)
const elapsedMinutes = computed(() => Math.max(1, Math.round(seconds.value / 60)))
const examTimeText = computed(() => {
  const m = Math.floor(examRemain.value / 60)
  const s = examRemain.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

// ── 总结派生（优先后端汇总，未就绪时用会话内存兜底，总结页绝不空白） ──
const summaryAccuracy = computed(() => summary.value?.accuracy ?? accuracy.value)
const summaryMinutes = computed(() =>
  summary.value?.duration_sec
    ? Math.max(1, Math.round(summary.value.duration_sec / 60))
    : elapsedMinutes.value,
)
const eloChanges = computed(() => {
  const src = summary.value?.kps
  if (src && src.length) {
    return src.map(k => ({ name: k.name, before: k.theta_before, after: k.theta_after }))
  }
  const out: { name: string; before: number | null; after: number | null }[] = []
  for (const f of flatQuestions.value) {
    const r = sessionResults[f.q.id]
    if (!r?.mastery || out.some(o => o.name === f.kp.name)) continue
    const theta = r.mastery.theta ?? 0
    const before = r.mastery.theta_before ?? theta - (r.mastery.delta ?? 0)
    out.push({ name: f.kp.name, before: Math.round(before * 10) / 10, after: theta })
  }
  return out
})
function deltaSign(s: { before: number | null; after: number | null }): number {
  if (s.before == null || s.after == null) return 0
  return s.after > s.before ? 1 : s.after < s.before ? -1 : 0
}
const weakNames = computed(() => {
  if (summary.value) return summary.value.weak_names
  const names: string[] = []
  for (const f of flatQuestions.value) {
    if (sessionResults[f.q.id]?.is_correct === false && !names.includes(f.kp.name)) {
      names.push(f.kp.name)
    }
  }
  return names
})
const wrongQuestions = computed(() => {
  if (summary.value) return summary.value.wrong_questions
  return flatQuestions.value
    .filter(f => sessionResults[f.q.id]?.is_correct === false)
    .map(f => {
      const r = sessionResults[f.q.id]
      return {
        stem: f.q.stem, kp_name: f.kp.name,
        user_answer: r.userAnswer || '（未作答）',
        correct_answer: r.correct_answer ?? '', analysis: r.analysis ?? '',
      }
    })
})

const tabTitle = computed(() => {
  if (activeTab.value === 'kp') {
    return selKpId.value ? `专项练习：${kpList.value.find(k => k.id === selKpId.value)?.name || ''}` : '知识点专项'
  }
  if (activeTab.value === 'exam') {
    return examTitle.value ? `《${examTitle.value}》阶段测试` : '阶段总考'
  }
  const day = dailyQuiz.value?.day_index
  return day ? `Day ${day} 每日练习（${quizItems.value?.length ?? 0} 个知识点）` : '每日任务'
})
const tabSubtitle = computed(() => {
  if (activeTab.value === 'kp') return '针对单一知识点强化，适合薄弱点冲刺'
  if (activeTab.value === 'exam') return '随机覆盖整本教材，45 分钟倒计时，模拟真实考试'
  return '选择选项后点击"提交本题"，答错会自动生成学习诊断并调整计划'
})

// ── 生命周期 ──
onMounted(async () => {
  timerId = window.setInterval(() => seconds.value++, 1000)
  const [ps, ds] = await Promise.all([api.listPlans(), api.listDocuments()])
  plans.value = ps
  docs.value = ds
  if (!selDocId.value && ds.length) selDocId.value = ds[0].id
  if (!planId.value && ps.length) planId.value = ps[0].id
  await loadCurrent()
})

onBeforeUnmount(() => {
  pollEpoch++
  if (timerId) clearInterval(timerId)
  if (examTimerId) clearInterval(examTimerId)
})

// ── 通用任务轮询（epoch 作废机制：切 Tab/重载后旧轮询自动退出，绝不并发写状态） ──
function sleep(ms: number) {
  return new Promise<void>(r => setTimeout(r, ms))
}

async function pollTask(
  taskId: string,
  onDone: (t: TaskStatus) => void,
  intervalMs = 2000,
  maxAttempts = 60,
  onFail?: (t: TaskStatus) => void,
  onTick?: (t: TaskStatus) => void,
) {
  const epoch = pollEpoch
  for (let i = 0; i < maxAttempts; i++) {
    await sleep(intervalMs)
    if (epoch !== pollEpoch) return        // 会话已重置，本次轮询作废
    let t: TaskStatus
    try {
      t = await api.getTaskStatus(taskId)
    } catch {
      continue                             // 单次轮询失败不中断循环
    }
    onTick?.(t)
    if (t.status === 'done') {
      onDone(t)
      return
    }
    if (t.status === 'failed') {
      onFail?.(t)
      return
    }
  }
}

// ── Tab 与加载 ──
function resetSession() {
  for (const k of Object.keys(sessionResults)) delete sessionResults[k]
  for (const k of Object.keys(diagPending)) delete diagPending[k]
  for (const k of Object.keys(stepsOpen)) delete stepsOpen[k]
  for (const k of Object.keys(chats)) delete chats[k]
  for (const k of Object.keys(chatInput)) delete chatInput[k]
  currentIndex.value = 0
  selected.value = ''
  textAnswer.value = ''
  summary.value = null
  summaryTaskId.value = null
  summaryLoading.value = false
  countedStreak.clear()
  seconds.value = 0
  loadError.value = ''
  loadHint.value = ''
}

async function switchTab(key: TabKey) {
  if (activeTab.value === key) return
  activeTab.value = key
  examActive.value = false
  if (examTimerId) clearInterval(examTimerId)
  quizItems.value = []
  phase.value = 'idle'
  if (key === 'kp' && !kpList.value.length) {
    await loadKpList()
  }
  await loadCurrent()
}

async function loadKpList() {
  if (!selDocId.value) return
  try {
    const m = await api.getMastery(selDocId.value)
    kpList.value = [...m.items].sort((a: any, b: any) => a.theta - b.theta)   // 薄弱优先
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '知识点列表加载失败')
  }
}

async function onKpDocChange() {
  kpList.value = []
  selKpId.value = null
  if (activeTab.value === 'kp' && selDocId.value) {
    await loadKpList()
  }
}

/** 出题任务参数（异步任务模式：请求立即返回，轮询拿结果，前端永不阻塞） */
function buildTaskParams(): object | null {
  if (activeTab.value === 'daily') {
    if (!planId.value) {
      ElMessage.warning('请先选择计划')
      return null
    }
    return { mode: 'today', plan_id: planId.value }
  }
  if (activeTab.value === 'kp') {
    if (!selKpId.value) {
      ElMessage.warning('请先选择知识点')
      return null
    }
    return { mode: 'by_kp', kp_id: selKpId.value, count: 5 }
  }
  if (!selDocId.value) {
    ElMessage.warning('请先选择教材')
    return null
  }
  return { mode: 'exam', doc_id: selDocId.value, count: examCount.value }
}

function applyPayload(mode: string, payload: any) {
  if (!payload) {
    loadError.value = '任务返回数据为空'
    quizItems.value = []
    phase.value = 'idle'
    return
  }
  if (mode === 'today') {
    dailyQuiz.value = payload
    quizItems.value = payload.items ?? []
  } else if (mode === 'by_kp') {
    quizItems.value = payload.items ?? []
  } else {
    quizItems.value = payload.items ?? []
    examTitle.value = payload.title || ''
    examRemain.value = 45 * 60
    examActive.value = (payload.total ?? 0) > 0
    if (examTimerId) clearInterval(examTimerId)
    if (examActive.value) {
      examTimerId = window.setInterval(() => {
        examRemain.value = Math.max(0, examRemain.value - 1)
        if (examRemain.value <= 0) {
          clearInterval(examTimerId)
          ElMessage.warning('⏰ 考试时间到，已停止作答')
        }
      }, 1000)
    }
  }
}

async function loadCurrent() {
  loadError.value = ''
  resetSession()
  quizItems.value = []
  phase.value = 'loading'
  pollEpoch++                              // 作废所有旧轮询
  const params = buildTaskParams()
  if (!params) {
    phase.value = 'idle'
    return
  }
  try {
    // ① 发起异步出题任务（立即返回）
    const taskId = await api.startQuizTask(params)
    console.log('[Quiz] 出题任务已启动:', taskId)
    // ② 轮询任务状态：单次异常不中断，最多 5 分钟
    await pollTask(
      taskId,
      t => {
        applyPayload(params.mode as string, t.result?.payload)
        currentIndex.value = 0
        beginQuestion()
      },
      1500, 200,
      t => {
        loadError.value = t.error || '题目生成失败'
        quizItems.value = []
        phase.value = 'idle'
      },
      t => { loadHint.value = t.stage || 'AI 正在出题…' },
    )
    if (phase.value === 'loading') {       // 轮询耗尽仍未完成
      loadError.value = '出题超时（5 分钟），请点击重试'
      phase.value = 'idle'
    }
  } catch (e: any) {
    console.error('[Quiz] 加载异常:', e)
    loadError.value = e?.response?.data?.detail || e?.message || '网络或服务异常'
    quizItems.value = []
    phase.value = 'idle'
  }
}

/** 进入一道新题：清空草稿、重置作答计时、按是否已答决定展示阶段 */
function beginQuestion() {
  selected.value = ''
  textAnswer.value = ''
  questionStartedAt.value = Date.now()
  const qid = current.value?.q.id
  phase.value = qid != null && sessionResults[qid] ? 'result' : 'answering'
  nextTick(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
}

// ── 答题状态机（核心：永不卡死的提交） ──
function selectOption(letter: string) {
  if (phase.value === 'result' || isSubmitting.value) return
  selected.value = letter
}

async function handleSubmit() {
  if (isSubmitting.value) return                        // 防重复提交
  if (phase.value !== 'answering' || !current.value) return
  const answer = hasOptions.value ? selected.value : textAnswer.value.trim()
  if (!answer) return
  isSubmitting.value = true
  const f = current.value
  const qid = f.q.id
  try {
    const durationSec = Math.max(0, Math.round((Date.now() - questionStartedAt.value) / 1000))
    const res = await api.submitAnswer(qid, answer, {
      is_last: isLastQuestion.value,
      question_ids: flatQuestions.value.map(x => x.q.id),
      duration_sec: durationSec,
    })
    sessionResults[qid] = { ...res, userAnswer: answer }

    // 客观题即时计入全局统计；主观题等批改完成时补计（不重复）
    if (res.is_correct != null) {
      stats.recordAnswer(res.is_correct)
      countedStreak.add(qid)
    }
    // 后台任务：诊断 / 批改 / 总结 —— 都只拿 task_id 轮询，绝不等待
    if (res.diagnosis_task_id) startDiagnosisPoll(qid, res.diagnosis_task_id)
    if (res.summary_task_id) summaryTaskId.value = res.summary_task_id
    if (res.grading_task_id) startGradingPoll(qid, res.grading_task_id)

    phase.value = 'result'                              // 显示对错和解析
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败，请重试')
  } finally {
    isSubmitting.value = false                          // 必须重置！按钮永不卡死
  }
}

function handleNext() {
  if (currentIndex.value >= total.value - 1) return
  currentIndex.value += 1
  beginQuestion()
}

/** 第一道未答题的下标：导航点只能回看已答题，或跳回当前待答题（保持逐题闭环） */
const firstUnansweredIndex = computed(() => {
  const i = flatQuestions.value.findIndex(f => !sessionResults[f.q.id])
  return i === -1 ? Math.max(0, total.value - 1) : i
})
function canJump(i: number) {
  const qid = flatQuestions.value[i].q.id
  return !!sessionResults[qid] || i === firstUnansweredIndex.value
}
function jumpTo(i: number) {
  if (i < 0 || i >= total.value || !canJump(i)) return
  currentIndex.value = i
  beginQuestion()
}

function handleFinish() {
  if (phase.value === 'finished') return
  if (gradingPending.value) {
    ElMessage.info('AI 正在批改本题，完成后即可查看总结')
    return
  }
  phase.value = 'finished'
  if (timerId) clearInterval(timerId)
  if (examTimerId) clearInterval(examTimerId)
  examActive.value = false
  // 会话结束 → 更新全局统计，所有页面的顶部激励栏立即联动刷新
  stats.recordSession(elapsedMinutes.value)
  // 异步总结任务：轮询回填，1~2 秒完成；失败/超时则用会话内存数据兜底展示
  if (summaryTaskId.value) {
    summaryLoading.value = true
    pollTask(
      summaryTaskId.value,
      t => {
        summary.value = t.result
        summaryLoading.value = false
      },
      1000, 30,
      () => { summaryLoading.value = false },
    ).then(() => {
      if (summaryLoading.value) summaryLoading.value = false
    })
  }
}

/** 后台轮询诊断任务：回填该题诊断面板（不影响答题与总结） */
function startDiagnosisPoll(qid: number, taskId: string) {
  diagPending[qid] = true
  pollTask(taskId, t => {
    const prev = sessionResults[qid]
    if (prev) sessionResults[qid] = { ...prev, diagnosis: t.result }
    diagPending[qid] = false
  }, 2500, 60).then(() => {
    if (diagPending[qid]) diagPending[qid] = false
  })
}

/** 后台轮询主观题批改：回填对错/评语/Elo，并补计全局连对 */
function startGradingPoll(qid: number, taskId: string) {
  pollTask(taskId, t => {
    const prev = sessionResults[qid]
    if (!prev) return
    sessionResults[qid] = { ...prev, ...t.result, grading_task_id: undefined }
    if (t.result?.is_correct != null && !countedStreak.has(qid)) {
      stats.recordAnswer(t.result.is_correct)
      countedStreak.add(qid)
    }
    if (t.result?.diagnosis_task_id) startDiagnosisPoll(qid, t.result.diagnosis_task_id)
  }, 2000, 60)
}

// ── 分层解析 ──
function splitAnalysis() {
  const a = lastResult.value?.analysis || ''
  const parts = a.split(/[。！？；]/).map((s: string) => s.trim()).filter(Boolean)
  return { brief: parts[0] ? parts[0] + '。' : a, steps: parts.slice(1) }
}
const brief = computed(() => splitAnalysis().brief)
const steps = computed(() => splitAnalysis().steps)
function toggleSteps() {
  const qid = current.value?.q.id
  if (qid != null) stepsOpen[qid] = !stepsOpen[qid]
}

// ── AI 助教（Mock 回复，演示用） ──
const PRESETS = ['用更通俗的话解释一遍', '这道题考的是哪个知识点？', '出一道类似的简单题给我练练']
const chats = reactive<Record<number, { open: boolean; messages: { role: string; text: string; jumpGraph?: boolean }[]; typing: boolean }>>({})
const chatInput = reactive<Record<number, string>>({})

function chatOf(qid: number) {
  if (!chats[qid]) chats[qid] = { open: false, messages: [], typing: false }
  return chats[qid]
}
function toggleChat() {
  const qid = current.value?.q.id
  if (qid != null) {
    const c = chatOf(qid)
    c.open = !c.open
  }
}
function ask(text: string) {
  const qid = current.value?.q.id
  if (qid == null) return
  const t = (text || '').trim()
  if (!t) return
  const c = chatOf(qid)
  c.open = true
  c.messages.push({ role: 'user', text: t })
  chatInput[qid] = ''
  c.typing = true
  const kp = current.value?.kp
  setTimeout(() => {
    c.typing = false
    c.messages.push({ role: 'ai', text: aiReply(kp, t), jumpGraph: t.includes('知识点') })
  }, 700)
}
function aiReply(kp: any, question: string): string {
  const name = kp?.name || '这个知识点'
  if (question.includes('通俗')) {
    return `好嘞，用大白话讲「${name}」：${kp?.definition ? kp.definition.slice(0, 60) + '……' : ''}\n把它想成一个生活场景：就像整理房间要先分类再摆放，解题也要先明确已知条件，再套用对应的规则。这样理解是不是轻松多了？😊`
  }
  if (question.includes('知识点')) {
    return `这道题考查的是「${name}」。${kp?.definition ? '它的定义是：' + kp.definition : ''}\n它在知识结构里可能还有前置与后续关联，点击下面的链接去图谱里看看全貌吧～`
  }
  if (question.includes('类似') || question.includes('简单题')) {
    return `没问题，先降难度练手：\n「${name}」的最基础形式——下面是一道热身题：已知条件更简单、只考查单一概念。\n（此处为演示回复，接入 LLM 后会自动生成一道难度 1 的题目并写入练习队列）`
  }
  return `好问题！关于这道题，核心思路是：先定位它考查「${name}」的哪个侧面，再按教材中的标准步骤推进。\n（演示回复：接入 LLM 后这里会结合题目与教材原文给出针对性讲解）`
}

// ── 选项样式与导航点 ──
function normalize(s: string) {
  return (s || '').trim().replace(/[\s。.;；;]/g, '').toUpperCase()
}
function isCorrectOption(i: number) {
  const r = lastResult.value
  return !!r && r.is_correct != null && normalize(r.correct_answer) === 'ABCDEFGH'[i]
}
function isChosenWrong(i: number) {
  return !!lastResult.value && lastResult.value.is_correct != null
    && !isCorrectOption(i) && selected.value === 'ABCDEFGH'[i]
}
function optionClass(i: number) {
  const letter = 'ABCDEFGH'[i]
  const r = lastResult.value
  if (phase.value === 'result' && r && r.is_correct != null) {
    if (isCorrectOption(i)) return 'border-emerald-400 bg-emerald-50 text-emerald-900'
    if (selected.value === letter) return 'border-red-300 bg-red-50 text-red-800'
    return 'border-gray-100 bg-gray-50/60 text-gray-400'
  }
  if (selected.value === letter) {
    return 'cursor-pointer border-purple-400 bg-purple-50 text-purple-900 ring-2 ring-purple-500/15'
  }
  return 'cursor-pointer border-gray-200 bg-white text-gray-700 hover:border-purple-300 hover:bg-purple-50/40'
}
function letterClass(i: number) {
  const letter = 'ABCDEFGH'[i]
  const r = lastResult.value
  if (phase.value === 'result' && r && r.is_correct != null) {
    if (isCorrectOption(i)) return 'bg-emerald-500 text-white'
    if (selected.value === letter) return 'bg-red-500 text-white'
    return 'bg-gray-100 text-gray-300'
  }
  return selected.value === letter ? 'bg-purple-500 text-white' : 'bg-gray-100 text-gray-500'
}
function dotClass(i: number) {
  const qid = flatQuestions.value[i].q.id
  const r = sessionResults[qid]
  if (i === currentIndex.value) return 'bg-purple-500 ring-4 ring-purple-200'
  if (r?.is_correct === true) return 'bg-emerald-400'
  if (r?.is_correct === false) return 'bg-red-400'
  if (r && r.is_correct == null) return 'bg-blue-400 animate-pulse'
  return 'bg-gray-200'
}
</script>
