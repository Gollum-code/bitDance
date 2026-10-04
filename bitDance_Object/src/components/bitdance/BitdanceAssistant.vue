<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Sparkles } from 'lucide-vue-next'
import { marked } from 'marked'
import { clearChat, getChatStatus, sendChatMessage, startNewChat } from '../../services/chat'
import { getToken } from '../../services/auth'
import { useAuth } from '../../state/auth'
import { authSessionEpoch } from '../../state/authSession'
import { getLastBacktestResult } from '../../state/bitdanceBacktestContext'
import { appendBacktestReport } from '../../state/backtestReportHistory'

const router = useRouter()
const route = useRoute()
const auth = useAuth()

/** 「我的策略」页才展示生成回测报告入口 */
const showGenerateReport = computed(() => route.name === 'strategies')

marked.setOptions({ gfm: true, breaks: true })

function renderAssistantMarkdown(src: string): string {
  try {
    const out = marked.parse(src, { async: false })
    return typeof out === 'string' ? out : String(out)
  } catch {
    return `<p>${src.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>`
  }
}

const open = ref(false)
const bars = ref<number[]>(Array.from({ length: 20 }, () => 0.2 + Math.random() * 0.8))
let barTimer: ReturnType<typeof setInterval> | undefined

type ChatRole = 'user' | 'assistant'
type ChatMessage = { id: string; role: ChatRole; text: string }

const BOOT_MESSAGE =
  '我是 bitDance 智能助理。你可以直接提问策略、风险或在「我的策略」页面点击「生成回测报告」。'

function createInitialMessages(): ChatMessage[] {
  return [{ id: 'boot', role: 'assistant', text: BOOT_MESSAGE }]
}

const messages = ref<ChatMessage[]>(createInitialMessages())
const inputText = ref('')
const sending = ref(false)
const conversationId = ref('')
const errorText = ref('')
const thinkingSeconds = ref(0)
const thinking = ref(false)
let thinkingTimer: ReturnType<typeof setInterval> | undefined
let thinkingMessageId: string | null = null
const canUseAi = computed(() => {
  authSessionEpoch.value
  return Boolean(getToken() && auth.user.value?.memberActive)
})

const aiGateHint = computed(() => {
  authSessionEpoch.value
  if (!getToken()) return '请登录后使用 AI 问答（会员专享）。'
  if (!auth.user.value?.memberActive) return 'AI 问答仅对会员开放，请在会员中心开通。'
  return ''
})

const hasToken = computed(() => {
  authSessionEpoch.value
  return Boolean(getToken())
})

onMounted(() => {
  barTimer = setInterval(() => {
    bars.value = bars.value.map(() => 0.12 + Math.random() * 0.88)
  }, 480)

  void auth.init().then(() => {
    if (!getToken() || !auth.user.value?.memberActive) return
    void getChatStatus()
      .then((status) => {
        conversationId.value = status.conversationId ?? ''
      })
      .catch(() => {
        /* 后端不可用或非会员时不恢复会话 */
      })
  })
})

watch(open, (v) => {
  if (v) void auth.refresh().catch(() => {})
})

onBeforeUnmount(() => {
  if (barTimer) clearInterval(barTimer)
  if (thinkingTimer) clearInterval(thinkingTimer)
})

function appendMessage(role: ChatRole, text: string) {
  messages.value.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    role,
    text,
  })
}

function updateMessageText(messageId: string, newText: string) {
  const idx = messages.value.findIndex((m) => m.id === messageId)
  if (idx >= 0) messages.value[idx].text = newText
}

async function send(message: string, options?: { showThinking?: boolean; reportUserText?: string; reportPrompt?: string }) {
  const finalMessage = message.trim()
  if (!finalMessage || sending.value) return

  await auth.init()
  if (!getToken()) {
    errorText.value = '请先登录后再使用 AI 问答'
    return
  }
  if (!auth.user.value?.memberActive) {
    appendMessage(
      'assistant',
      'AI 问答为会员专享功能。请前往「会员中心」开通会员后使用。',
    )
    return
  }

  const showThinking = options?.showThinking ?? false
  const userText = options?.reportUserText ?? finalMessage
  const aiPrompt = options?.reportPrompt ?? finalMessage

  if (showThinking) {
    thinking.value = true
    thinkingSeconds.value = 0
    thinkingMessageId = null
    errorText.value = ''

    // 先插入一条占位消息，后续不断替换它的文本
    appendMessage('assistant', 'AI 正在思考中... 已用 0 秒')
    thinkingMessageId = messages.value[messages.value.length - 1]?.id ?? null
    if (thinkingMessageId) {
      thinkingTimer = setInterval(() => {
        thinkingSeconds.value += 1
        updateMessageText(thinkingMessageId as string, `AI 正在思考中... 已用 ${thinkingSeconds.value} 秒`)
      }, 1000)
    }
  }

  appendMessage('user', userText)
  inputText.value = ''
  sending.value = true
  errorText.value = ''

  try {
    const response = conversationId.value
      ? await sendChatMessage(aiPrompt)
      : await startNewChat(aiPrompt)
    conversationId.value = response.conversationId ?? ''

    const replyText = response.reply || '模型没有返回内容，请重试。'
    if (thinkingMessageId) {
      updateMessageText(thinkingMessageId, replyText)
    } else {
      appendMessage('assistant', replyText)
    }

    if (
      userText === '生成回测报告' &&
      replyText &&
      auth.user.value?.id != null &&
      !replyText.includes('模型没有返回内容')
    ) {
      const lastResult = getLastBacktestResult()
      const meta =
        lastResult && lastResult.success && lastResult.stats
          ? {
              stats: lastResult.stats as Record<string, number | string | null>,
              params: (lastResult.params ?? {}) as Record<string, unknown>,
            }
          : undefined
      appendBacktestReport(auth.user.value.id, replyText, meta)
    }
  } catch (error) {
    const text = error instanceof Error ? error.message : '调用服务失败'
    errorText.value = text

    if (thinkingMessageId) {
      updateMessageText(thinkingMessageId, `请求失败：${text}`)
    } else {
      appendMessage('assistant', `请求失败：${text}`)
    }
  } finally {
    sending.value = false
    if (thinkingTimer) clearInterval(thinkingTimer)
    thinkingTimer = undefined
    thinking.value = false
    thinkingMessageId = null
  }
}

async function handleSubmit() {
  await send(inputText.value)
}

async function generateReport() {
  await auth.init()
  if (!getToken() || !auth.user.value?.memberActive) {
    appendMessage('assistant', '生成报告需要会员权限。请先登录并开通会员，或在会员中心升级。')
    return
  }
  const last = getLastBacktestResult()
  if (!last) {
    appendMessage(
      'assistant',
      '尚未在本会话中完成回测。请先在「我的策略」页面点击运行回测，成功后再生成报告。',
    )
    return
  }
  if (!last.success) {
    appendMessage(
      'assistant',
      '最近一次回测未成功完成，没有可用的回测结果。请修正参数或排查错误后重新运行回测。',
    )
    return
  }
  if (!last.stats || typeof last.stats !== 'object') {
    appendMessage('assistant', '回测未返回统计数据，无法生成报告。请重新运行回测后再试。')
    return
  }
  const tradeCount = Number(last.stats.total_trade_count ?? 0)
  if (!Number.isFinite(tradeCount) || tradeCount <= 0) {
    appendMessage(
      'assistant',
      '当前回测成交笔数为 0，无法生成有意义的报告。请先调整参数使策略产生交易后再试。',
    )
    return
  }

  const maxPoints = 60
  const payload = {
    params: last.params,
    stats: last.stats,
    series: {
      dates: last.series.dates.slice(-maxPoints),
      balance: last.series.balance.slice(-maxPoints),
      drawdown: last.series.drawdown.slice(-maxPoints),
      benchmark: (last.series.benchmark ?? []).slice(-maxPoints),
    },
  }

  const prompt =
    '请基于下方「仅允引用、禁止编造」的回测数据 JSON，输出一份 **Markdown（GFM）** 报告：使用 `##`/`###` 标题、列表与表格（适合对比的指标用表格），含执行摘要、收益与风险指标、持仓/敞口（若数据支持）、交易统计、信号与逐期表现解读（不足则声明）、局限性与风险提示。\\n' +
    `回测数据JSON：${JSON.stringify(payload)}`

  await send('生成回测报告', {
    showThinking: true,
    reportUserText: '生成回测报告',
    reportPrompt: prompt,
  })
}

async function resetConversation() {
  if (sending.value) return
  await auth.init()
  if (!getToken()) {
    errorText.value = '请先登录'
    return
  }
  if (!auth.user.value?.memberActive) {
    errorText.value = '新会话仅适用于已登录会员'
    return
  }

  errorText.value = ''
  inputText.value = ''
  if (thinkingTimer) clearInterval(thinkingTimer)
  thinkingTimer = undefined
  thinking.value = false
  thinkingMessageId = null

  messages.value = createInitialMessages()
  conversationId.value = ''
  open.value = true

  try {
    await clearChat()
  } catch (error) {
    const text = error instanceof Error ? error.message : '清空会话失败'
    errorText.value = `${text}（界面已重置为新会话）`
  }
}

function toggle() {
  open.value = !open.value
}
</script>

<template>
  <div class="assistant-root">
    <Transition name="panel">
      <aside v-if="open" class="panel" aria-label="bitDance Assistant 对话面板">
        <div class="panel-glow" aria-hidden="true" />
        <div class="panel-head">
          <Sparkles class="spark" aria-hidden="true" />
          <span>bitDance 智能体</span>
        </div>
        <p class="panel-desc">已接入后端会话能力；AI 问答仅会员可用，可连续追问策略、回测与风险问题。</p>
        <p v-if="aiGateHint" class="gate-banner">{{ aiGateHint }}</p>
        <div v-if="!canUseAi && aiGateHint" class="gate-actions">
          <button v-if="!hasToken" type="button" class="gen" @click="router.push('/login')">
            去登录
          </button>
          <button v-else type="button" class="gen" @click="router.push('/member')">开通会员</button>
        </div>
        <div class="actions" :class="{ 'actions--single': !showGenerateReport }">
          <button
            v-if="showGenerateReport"
            type="button"
            class="gen"
            :disabled="sending || !canUseAi"
            @click="generateReport"
          >
            生成回测报告
          </button>
          <button
            type="button"
            class="ghost"
            :class="{ 'ghost--full': !showGenerateReport }"
            :disabled="sending || !canUseAi"
            @click="resetConversation"
          >
            新会话
          </button>
        </div>
        <div class="report chat-list">
          <div
            v-for="line in messages"
            :key="line.id"
            class="cluster-line"
            :class="line.role"
          >
            <span class="role">{{ line.role === 'user' ? '你' : 'AI' }}</span>
            <span v-if="line.role === 'user'" class="bubble-plain">{{ line.text }}</span>
            <div
              v-else
              class="md-content"
              v-html="renderAssistantMarkdown(line.text)"
            />
          </div>
          <div v-if="sending && !thinking" class="cluster-line assistant">
            <span class="role">AI</span>
            <span class="bubble-plain">AI 正在思考中...</span>
          </div>
          <p v-if="errorText" class="error-tip">{{ errorText }}</p>
        </div>
        <form class="composer" @submit.prevent="handleSubmit">
          <input
            v-model="inputText"
            type="text"
            maxlength="1000"
            placeholder="会员可提问：回撤原因、参数敏感性等"
            :disabled="!canUseAi"
          />
          <button type="submit" class="send" :disabled="sending || !inputText.trim() || !canUseAi">
            发送
          </button>
        </form>
        <div class="session">会话ID：{{ conversationId || '未建立' }}</div>
      </aside>
    </Transition>

    <button
      type="button"
      class="fab"
      :class="{ 'fab--open': open }"
      aria-label="bitDance Assistant"
      :aria-expanded="open"
      @click="toggle"
    >
      <div class="glow" aria-hidden="true" />
      <div class="bars" role="presentation">
        <span v-for="(h, i) in bars" :key="i" class="bar" :style="{ transform: `scaleY(${h})` }" />
      </div>
      <p class="caption">bitDance AI</p>
    </button>
  </div>
</template>

<style scoped>
.assistant-root {
  position: fixed;
  right: 1.25rem;
  bottom: 1.25rem;
  z-index: 35;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.75rem;
}

.panel {
  position: relative;
  width: min(26rem, calc(100vw - 2.5rem));
  padding: 1.15rem 1.2rem 1.25rem;
  border-radius: 1.1rem;
  background: rgba(6, 6, 6, 0.72);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow:
    0 0 0 1px rgba(191, 147, 83, 0.14),
    0 22px 56px rgba(0, 0, 0, 0.55),
    0 0 48px rgba(191, 147, 83, 0.06);
  text-align: left;
}

.panel-glow {
  position: absolute;
  inset: -25%;
  background: radial-gradient(circle at 30% 20%, rgba(191, 147, 83, 0.15) 0%, transparent 55%);
  filter: blur(32px);
  pointer-events: none;
  opacity: 0.7;
}

.panel-head {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(191, 147, 83, 0.65);
}

.spark {
  width: 1rem;
  height: 1rem;
  opacity: 0.85;
}

.panel-desc {
  position: relative;
  margin: 0.35rem 0 0.85rem;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: rgba(168, 162, 158, 0.75);
}

.gate-banner {
  margin: 0 0 0.55rem;
  padding: 0.45rem 0.55rem;
  border-radius: 0.5rem;
  font-size: 0.78rem;
  line-height: 1.45;
  color: rgba(240, 225, 200, 0.9);
  background: rgba(191, 147, 83, 0.12);
  border: 1px solid rgba(191, 147, 83, 0.22);
}

.gate-actions {
  display: flex;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
}

.gate-actions .gen {
  width: auto;
  flex: 1;
}

.gen {
  position: relative;
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: none;
  border-radius: 0.65rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #0a0a0a;
  cursor: pointer;
  background: linear-gradient(180deg, rgba(191, 147, 83, 0.95) 0%, #7f5731 100%);
  box-shadow:
    0 0 0 1px rgba(191, 147, 83, 0.35),
    0 8px 24px rgba(0, 0, 0, 0.35);
  transition: opacity 0.2s ease;
}

.gen:disabled,
.ghost:disabled,
.send:disabled {
  opacity: 0.65;
  cursor: wait;
}

.actions {
  display: grid;
  grid-template-columns: 1fr 0.7fr;
  gap: 0.55rem;
}

.actions--single {
  grid-template-columns: 1fr;
}

.ghost--full {
  width: 100%;
}

.ghost {
  border: 1px solid rgba(191, 147, 83, 0.3);
  border-radius: 0.65rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: rgba(245, 245, 244, 0.88);
  background: rgba(255, 255, 255, 0.05);
}

.report {
  position: relative;
  margin-top: 1rem;
  min-height: 8rem;
}

.chat-list {
  max-height: 16rem;
  overflow-y: auto;
  padding-right: 0.35rem;
}

.cluster-line {
  margin: 0;
  font-size: 0.8125rem;
  line-height: 1.55;
  color: rgba(245, 245, 244, 0.9);
  padding: 0.45rem 0.55rem;
  border-radius: 0.6rem;
  background: rgba(255, 255, 255, 0.04);
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.35rem 0.5rem;
  align-items: start;
}

.bubble-plain {
  grid-column: 2;
  word-break: break-word;
  white-space: pre-wrap;
}

.md-content {
  grid-column: 2;
  min-width: 0;
}

.md-content :deep(h1),
.md-content :deep(h2),
.md-content :deep(h3) {
  color: rgba(245, 245, 244, 0.96);
  line-height: 1.3;
  margin: 0.65rem 0 0.4rem;
  font-weight: 650;
}

.md-content :deep(h1) {
  font-size: 1.05rem;
}

.md-content :deep(h2) {
  font-size: 0.95rem;
}

.md-content :deep(h3) {
  font-size: 0.85rem;
}

.md-content :deep(h1:first-child),
.md-content :deep(h2:first-child),
.md-content :deep(h3:first-child) {
  margin-top: 0;
}

.md-content :deep(p) {
  margin: 0.35rem 0;
  color: rgba(245, 245, 244, 0.9);
}

.md-content :deep(ul),
.md-content :deep(ol) {
  margin: 0.35rem 0;
  padding-left: 1.15rem;
  color: rgba(245, 245, 244, 0.88);
}

.md-content :deep(li) {
  margin: 0.2rem 0;
}

.md-content :deep(blockquote) {
  margin: 0.45rem 0;
  padding: 0.35rem 0.55rem;
  border-left: 3px solid rgba(191, 147, 83, 0.45);
  background: rgba(0, 0, 0, 0.2);
  color: rgba(220, 215, 208, 0.92);
}

.md-content :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.82em;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 0.12rem 0.35rem;
  color: rgba(240, 228, 210, 0.95);
}

.md-content :deep(pre) {
  margin: 0.45rem 0;
  padding: 0.55rem 0.65rem;
  border-radius: 0.45rem;
  background: rgba(0, 0, 0, 0.45);
  overflow-x: auto;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset;
}

.md-content :deep(pre code) {
  background: transparent;
  padding: 0;
  font-size: 0.78rem;
}

.md-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.45rem 0;
  font-size: 0.78rem;
}

.md-content :deep(th),
.md-content :deep(td) {
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.35rem 0.45rem;
  text-align: left;
}

.md-content :deep(th) {
  background: rgba(191, 147, 83, 0.12);
  color: rgba(245, 240, 230, 0.95);
}

.md-content :deep(hr) {
  margin: 0.65rem 0;
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.md-content :deep(strong) {
  color: rgba(253, 246, 236, 0.98);
  font-weight: 650;
}

.md-content :deep(a) {
  color: rgba(147, 197, 253, 0.95);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.cluster-line.user {
  border: 1px solid rgba(191, 147, 83, 0.28);
}

.cluster-line.assistant {
  border: 1px solid rgba(123, 168, 207, 0.22);
}

.role {
  grid-column: 1;
  display: inline-block;
  margin-right: 0;
  color: rgba(191, 147, 83, 0.9);
  font-size: 0.72rem;
  line-height: 1.5;
  padding-top: 0.08rem;
}

.composer {
  margin-top: 0.7rem;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.45rem;
}

.composer input {
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 0.6rem;
  background: rgba(0, 0, 0, 0.25);
  color: rgba(245, 245, 244, 0.92);
  padding: 0.52rem 0.58rem;
  font-size: 0.8rem;
}

.send {
  border: 0;
  border-radius: 0.6rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #0a0a0a;
  padding: 0.48rem 0.7rem;
  background: linear-gradient(180deg, rgba(191, 147, 83, 0.95) 0%, #7f5731 100%);
}

.session {
  margin-top: 0.5rem;
  font-size: 0.72rem;
  color: rgba(168, 162, 158, 0.75);
}

.error-tip {
  margin: 0.35rem 0 0;
  color: #fca5a5;
  font-size: 0.75rem;
}

.fab {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.45rem;
  padding: 0.75rem 0.9rem 0.6rem;
  border: none;
  border-radius: 1rem;
  cursor: pointer;
  background: rgba(6, 6, 6, 0.55);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow:
    0 0 0 1px rgba(191, 147, 83, 0.12),
    0 18px 48px rgba(0, 0, 0, 0.55),
    0 0 36px rgba(191, 147, 83, 0.08);
  transition:
    box-shadow 0.35s ease,
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.fab:hover {
  transform: translateY(-2px);
  box-shadow:
    0 0 0 1px rgba(191, 147, 83, 0.2),
    0 22px 56px rgba(0, 0, 0, 0.55),
    0 0 44px rgba(191, 147, 83, 0.12);
}

.fab--open {
  box-shadow:
    0 0 0 1px rgba(191, 147, 83, 0.28),
    0 0 40px rgba(191, 147, 83, 0.15);
}

.glow {
  position: absolute;
  inset: -30%;
  background: radial-gradient(circle at 50% 80%, rgba(191, 147, 83, 0.2) 0%, transparent 55%);
  filter: blur(26px);
  opacity: 0.65;
  pointer-events: none;
}

.bars {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 44px;
}

.bar {
  width: 3px;
  border-radius: 999px;
  height: 100%;
  transform-origin: bottom center;
  background: linear-gradient(180deg, rgba(250, 250, 249, 0.95) 0%, rgba(191, 147, 83, 0.55) 100%);
  box-shadow: 0 0 12px rgba(191, 147, 83, 0.35);
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
  opacity: 0.85;
}

.caption {
  margin: 0;
  font-size: 0.625rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(191, 147, 83, 0.55);
}

.panel-enter-active,
.panel-leave-active {
  transition:
    opacity 0.4s ease,
    transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}
</style>

