<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import {
  RefreshCw as ArrowPathIcon,
  HelpCircle as QuestionMarkCircleIcon,
  Mail as EnvelopeIcon,
  Calendar as CalendarDaysIcon,
  Settings as Cog6ToothIcon,
  Check as CheckIcon,
  X as XMarkIcon,
  Clipboard as ClipboardDocumentIcon,
  Github as GithubIcon,
} from 'lucide-vue-next'
import { useTaskStore } from './stores/tasks'
import FilterChips from './components/FilterChips.vue'
import FilterBar from './components/FilterBar.vue'
import TaskTable from './components/TaskTable.vue'
import QuickAddBar from './components/QuickAddBar.vue'
import CalendarView from './components/CalendarView.vue'
import NewsView from './components/NewsView.vue'
import AccountMenu from './components/AccountMenu.vue'
import ReauthModal from './components/ReauthModal.vue'
import SettingsModal from './components/SettingsModal.vue'
import ToastContainer from './components/ui/Toast.vue'
import { useToast } from './composables/useToast'
import { api } from './api'
import type { AppStatus, ReauthState } from './types'

const activeTab = ref<'tasks' | 'calendar' | 'news'>('tasks')
const newsUnreadCount = ref(0)

async function refreshNewsCount() {
  try {
    const res = await api.newsUnreadCount()
    newsUnreadCount.value = res.count
  } catch { /* ignore */ }
}

const store = useTaskStore()

// ── Poll progress ──────────────────────────────────────────────────────
const pollPhase  = ref('')
const pollCurrent = ref(0)
const pollTotal   = ref(0)
const pollDone    = ref(true)

let progressTimer: ReturnType<typeof setInterval> | null = null

async function tickProgress() {
  try {
    const p = await api.getPollProgress()
    pollPhase.value   = p.phase
    pollCurrent.value = p.current
    pollTotal.value   = p.total
    pollDone.value    = p.done
    if (p.done && progressTimer) {
      clearInterval(progressTimer)
      progressTimer = null
    }
  } catch { /* backend busy — ignore */ }
}

function startProgressPolling() {
  pollDone.value = false
  pollPhase.value = 'Starting…'
  pollCurrent.value = 0
  pollTotal.value = 0
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = setInterval(tickProgress, 600)
}

onUnmounted(() => { if (progressTimer) clearInterval(progressTimer) })

// --- app status (auth + first-run detection) ---
const appStatus = ref<AppStatus | null>(null)

async function fetchStatus() {
  try {
    appStatus.value = await api.getStatus()
  } catch { /* backend unreachable — error already shown by fetchTasks */ }
}

onMounted(async () => {
  await fetchStatus()
  await store.fetchTasks()
  refreshNewsCount()
  const taskParam = new URLSearchParams(window.location.search).get('task')
  if (taskParam) {
    const id = parseInt(taskParam, 10)
    const idx = store.tasks.findIndex(t => t.id === id)
    if (idx >= 0) {
      focusedIndex.value = idx
      window.history.replaceState({}, '', window.location.pathname)
    }
  }
})

function formatPollTime(iso: string | null | undefined) {
  if (!iso) return 'never'
  // Append Z so JS treats the string as UTC and converts to local time
  const utc = iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z'
  return new Date(utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

async function onPollNow() {
  startProgressPolling()
  await store.triggerPoll()
  await fetchStatus()
  await tickProgress()
}

// --- auth ---
const reauthState = ref<ReauthState>('idle')

async function onReauth() {
  try {
    const r = await api.triggerReauth()
    reauthState.value = r.state as ReauthState
  } catch {
    reauthState.value = 'error'
  }
}

async function onLogout() {
  await api.logout()
  appStatus.value = null
  await fetchStatus()
}

async function onReauthDone() {
  reauthState.value = 'idle'
  await fetchStatus()
  await store.fetchTasks()
}

async function onReauthError() {
  reauthState.value = 'error'
}

async function onReauthClose() {
  reauthState.value = 'idle'
  await fetchStatus()
}

// sync reauth_state from backend on each status fetch
watch(appStatus, (s) => {
  if (s && s.reauth_state !== 'idle' && reauthState.value === 'idle') {
    reauthState.value = s.reauth_state
  }
})

// --- settings & cheatsheet ---
const showSettings   = ref(false)
const showCheatsheet = ref(false)

// --- overdue badge pulse ---
const overdueKey = ref(0)
watch(() => store.overdueCount, () => { overdueKey.value++ })

watch(activeTab, (tab) => {
  if (tab === 'news') refreshNewsCount()
})

// --- toast + undo wrappers ---
const toast = useToast()

async function onMarkReplied(id: number) {
  const task = store.tasks.find(t => t.id === id)
  const label = task?.summary ?? task?.subject ?? 'Task'
  await store.markReplied(id)
  toast.show(`"${label}" marked as replied`, 'success', async () => {
    await api.updateStatus(id, 'open')
    await store.fetchTasks()
  })
}

async function onDismiss(id: number) {
  const task = store.tasks.find(t => t.id === id)
  const label = task?.summary ?? task?.subject ?? 'Task'
  await store.dismiss(id)
  toast.show(`"${label}" dismissed`, 'info', async () => {
    await api.updateStatus(id, 'open')
    await store.fetchTasks()
  })
}

// --- quick add ---
const quickAddRef = ref<InstanceType<typeof QuickAddBar> | null>(null)

async function onAddTask(title: string, replyBy: Date, priority: import('./types').Priority) {
  await store.createTask(title, replyBy, priority)
  toast.show(`"${title}" added`, 'success')
}

// --- keyboard navigation ---
const focusedIndex = ref<number | undefined>(undefined)
const tableRef = ref<InstanceType<typeof TaskTable> | null>(null)

// SR live region
const srAnnounce = ref('')
function announce(msg: string) {
  srAnnounce.value = ''
  setTimeout(() => { srAnnounce.value = msg }, 10)
}

function clamp(n: number) {
  return Math.max(0, Math.min(n, store.tasks.length - 1))
}

function onKeyDown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement).tagName
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return
  if ((e.target as HTMLElement).isContentEditable) return

  switch (e.key) {
    case 'n':
      e.preventDefault()
      quickAddRef.value?.focus()
      break
    case 'j':
    case 'ArrowDown':
      e.preventDefault()
      focusedIndex.value = focusedIndex.value === undefined ? 0 : clamp(focusedIndex.value + 1)
      break
    case 'k':
    case 'ArrowUp':
      e.preventDefault()
      focusedIndex.value = focusedIndex.value === undefined ? 0 : clamp(focusedIndex.value - 1)
      break
    case 'e':
      if (focusedIndex.value !== undefined) {
        e.preventDefault()
        tableRef.value?.openDatePickerAt(focusedIndex.value)
      }
      break
    case 'r':
      if (focusedIndex.value !== undefined) {
        e.preventDefault()
        const rt = store.tasks[focusedIndex.value]
        onMarkReplied(rt.id)
        announce(`Marked "${rt.summary ?? rt.subject}" as replied`)
      }
      break
    case 'd':
      if (focusedIndex.value !== undefined) {
        e.preventDefault()
        const dt = store.tasks[focusedIndex.value]
        onDismiss(dt.id)
        announce(`Dismissed "${dt.summary ?? dt.subject}"`)
      }
      break
    case 'x':
      if (focusedIndex.value !== undefined) {
        e.preventDefault()
        store.toggleSelect(store.tasks[focusedIndex.value].id)
      }
      break
    case 'Escape':
      focusedIndex.value = undefined
      showCheatsheet.value = false
      store.clearSelection()
      break
    case '?':
      showCheatsheet.value = !showCheatsheet.value
      break
  }
}

onMounted(() => window.addEventListener('keydown', onKeyDown))
onUnmounted(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <!-- Screen-reader live region -->
  <div aria-live="polite" aria-atomic="true" class="sr-only">{{ srAnnounce }}</div>

  <!-- Poll progress bar — fixed top -->
  <Transition
    enter-active-class="transition-opacity duration-150"
    leave-active-class="transition-opacity duration-300"
    enter-from-class="opacity-0"
    leave-to-class="opacity-0"
  >
    <div v-if="!pollDone" class="fixed top-0 left-0 right-0 z-[9999] h-[3px] bg-brand-lightest overflow-hidden">
      <div
        class="h-full bg-brand-primary transition-all duration-500 ease-out"
        :style="{
          width: pollTotal > 0
            ? `${Math.round((pollCurrent / pollTotal) * 100)}%`
            : '100%',
          animation: pollTotal === 0 ? 'progress-indeterminate 1.4s ease-in-out infinite' : 'none',
        }"
      />
    </div>
  </Transition>

  <SettingsModal
    :open="showSettings"
    :slack-connected="appStatus?.slack_connected ?? false"
    @close="showSettings = false"
    @slack-status-changed="fetchStatus"
    @poll-now="onPollNow"
  />
  <ReauthModal
    :state="reauthState"
    @done="onReauthDone"
    @error="onReauthError"
    @close="onReauthClose"
  />
  <ToastContainer />

  <div class="min-h-screen bg-surface-page">
    <!-- Skip to content -->
    <a href="#main-content" class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[9999] focus:px-4 focus:py-2 focus:bg-brand-primary focus:text-white focus:rounded-lg focus:text-body focus:font-semibold">Skip to content</a>

    <!-- Header -->
    <header class="bg-brand-darkest h-14 flex items-center px-6 gap-6 sticky top-0 z-50">
      <div class="flex items-center gap-2.5 text-white font-bold text-heading tracking-tight shrink-0">
        <EnvelopeIcon class="w-5 h-5 shrink-0" />
        todo·mail
      </div>

      <!-- Tab nav -->
      <nav class="flex items-center gap-1 shrink-0" aria-label="Main navigation">
        <button
          @click="activeTab = 'tasks'"
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold transition-colors',
            activeTab === 'tasks' ? 'bg-white/15 text-white' : 'text-white/55 hover:text-white hover:bg-white/10',
          ]"
          :aria-current="activeTab === 'tasks' ? 'page' : undefined"
        >
          <EnvelopeIcon class="w-3.5 h-3.5" />
          Tasks
          <span
            v-if="store.overdueCount > 0 && activeTab !== 'tasks'"
            :key="overdueKey"
            class="bg-brand-primary text-white text-micro font-bold px-1.5 py-0.5 rounded-pill tabular-nums"
          >{{ store.overdueCount }}</span>
        </button>
        <button
          @click="activeTab = 'calendar'"
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold transition-colors',
            activeTab === 'calendar' ? 'bg-white/15 text-white' : 'text-white/55 hover:text-white hover:bg-white/10',
          ]"
          :aria-current="activeTab === 'calendar' ? 'page' : undefined"
        >
          <CalendarDaysIcon class="w-3.5 h-3.5" />
          Calendar
        </button>
        <button
          @click="activeTab = 'news'"
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold transition-colors',
            activeTab === 'news' ? 'bg-white/15 text-white' : 'text-white/55 hover:text-white hover:bg-white/10',
          ]"
          :aria-current="activeTab === 'news' ? 'page' : undefined"
        >
          <GithubIcon class="w-3.5 h-3.5" />
          News
          <span
            v-if="newsUnreadCount > 0"
            class="bg-brand-primary text-white text-micro font-bold px-1.5 py-0.5 rounded-pill tabular-nums"
          >{{ newsUnreadCount }}</span>
        </button>
      </nav>

      <span
        v-if="store.overdueCount > 0 && activeTab === 'tasks'"
        :key="overdueKey"
        class="bg-brand-primary text-white text-micro font-bold px-2 py-0.5 rounded-pill tabular-nums animate-count-pulse shrink-0"
      >
        {{ store.overdueCount }} overdue
      </span>
      <div class="ml-auto flex items-center gap-3">
        <div class="text-micro text-white/60 flex items-center gap-1.5 shrink-0">
          <span class="w-1.5 h-1.5 rounded-full shrink-0" :class="!pollDone ? 'bg-brand-light animate-pulse' : 'bg-green-400'"></span>
          <template v-if="!pollDone">
            {{ pollPhase }}
            <span v-if="pollTotal > 0" class="tabular-nums text-white/40">({{ pollCurrent }}/{{ pollTotal }})</span>
          </template>
          <template v-else>
            {{ appStatus?.last_poll ? `Synced ${formatPollTime(appStatus.last_poll)}` : 'Not synced' }}
          </template>
        </div>
        <button
          @click="onPollNow"
          :disabled="store.polling || appStatus?.authenticated === false"
          class="flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-body font-semibold rounded-lg disabled:opacity-40 transition-colors shrink-0"
        >
          <ArrowPathIcon class="w-3.5 h-3.5" :class="{ 'animate-spin': store.polling }" />
          Poll now
        </button>
        <button
          @click="showSettings = true"
          title="Settings"
          aria-label="Open settings"
          class="p-1.5 rounded text-white/50 hover:text-white hover:bg-white/10 transition-colors"
        >
          <Cog6ToothIcon class="w-4 h-4" />
        </button>
        <button
          @click="showCheatsheet = !showCheatsheet"
          title="Keyboard shortcuts"
          aria-label="Show keyboard shortcuts"
          class="p-1.5 rounded transition-colors"
          :class="showCheatsheet ? 'text-white bg-white/15' : 'text-white/50 hover:text-white hover:bg-white/10'"
        >
          <QuestionMarkCircleIcon class="w-4 h-4" />
        </button>
        <AccountMenu
          v-if="appStatus?.authenticated"
          :account-email="appStatus?.account_email ?? null"
          :needs-reauth="appStatus?.needs_reauth ?? false"
          @reauth="onReauth"
          @logout="onLogout"
        />
      </div>
    </header>

    <!-- Calendar tab (full-bleed, no padding wrapper) -->
    <div v-if="activeTab === 'calendar'" class="bg-surface-page">
      <CalendarView />
    </div>

    <!-- News tab -->
    <div v-if="activeTab === 'news'" class="bg-surface-page">
      <NewsView />
    </div>

    <main v-if="activeTab === 'tasks'" id="main-content" class="max-w-workbench mx-auto px-6 py-6 space-y-4">
      <!-- Error banner -->
      <div
        v-if="store.error"
        role="alert"
        class="flex items-start gap-3 px-4 py-3 bg-red-50 border-l-[3px] border-red-500 text-red-700 rounded-lg text-body"
      >
        <XMarkIcon class="w-4 h-4 mt-0.5 shrink-0" />
        {{ store.error }}
      </div>

      <!-- Gmail reauth banner -->
      <div
        v-if="appStatus?.needs_reauth && appStatus?.authenticated"
        role="alert"
        class="flex items-start gap-3 px-4 py-3 bg-amber-50 border-l-[3px] border-amber-500 text-amber-800 rounded-lg text-body"
      >
        <EnvelopeIcon class="w-4 h-4 mt-0.5 shrink-0" />
        <div class="flex-1">
          <p class="font-semibold">Gmail session expired</p>
          <p class="text-caption text-amber-700">
            New mail polling has stopped. Reconnect Gmail to resume syncing.
          </p>
        </div>
        <button
          @click="onReauth"
          class="shrink-0 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-caption font-semibold rounded-lg transition-colors"
        >
          Reconnect Gmail
        </button>
      </div>

      <!-- Keyboard cheatsheet -->
      <Transition enter-active-class="animate-scale-in" leave-active-class="transition-opacity duration-100" leave-to-class="opacity-0">
        <div
          v-if="showCheatsheet"
          class="rounded-lg overflow-hidden shadow-dropdown animate-scale-in"
        >
          <div class="bg-brand-primary px-4 py-2 flex items-center justify-between">
            <span class="text-caption font-bold text-white uppercase tracking-wide">Keyboard shortcuts</span>
            <button @click="showCheatsheet = false" class="text-white/60 hover:text-white transition-colors" aria-label="Close shortcuts">
              <XMarkIcon class="w-3.5 h-3.5" />
            </button>
          </div>
          <div class="bg-grey-900 px-4 py-3 text-grey-100 font-mono grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2">
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">n</kbd> new task</span>
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">j / ↓</kbd> next</span>
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">k / ↑</kbd> prev</span>
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">e</kbd> edit reply-by</span>
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">r</kbd> mark replied</span>
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">d</kbd> dismiss</span>
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">x</kbd> toggle select</span>
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">Esc</kbd> deselect all</span>
            <span class="text-caption"><kbd class="bg-grey-700 border border-grey-500 px-1.5 py-0.5 rounded text-micro shadow-sm">?</kbd> this panel</span>
          </div>
        </div>
      </Transition>

      <!-- Not authenticated — setup card -->
      <div
        v-if="appStatus && !appStatus.authenticated"
        class="bg-surface-card rounded-xl shadow-card px-8 py-12 flex flex-col items-center text-center gap-5 animate-fade-in-up card-interactive"
      >
        <div class="w-14 h-14 bg-brand-50 rounded-full flex items-center justify-center">
          <EnvelopeIcon class="w-7 h-7 text-brand-primary" />
        </div>
        <div>
          <h2 class="text-heading text-grey-900 mb-2">Connect Gmail to get started</h2>
          <p class="text-body text-grey-500 max-w-sm">
            Click below to sign in with Google and connect your inbox.
          </p>
        </div>
        <button
          @click="onReauth"
          class="flex items-center gap-2 px-4 py-2 bg-brand-primary hover:bg-brand-dark text-white text-body font-semibold rounded-lg transition-colors"
        >
          <EnvelopeIcon class="w-4 h-4" />
          Connect Gmail
        </button>
        <details class="w-full max-w-sm text-left">
          <summary class="text-caption text-grey-500 cursor-pointer hover:text-grey-700 transition-colors select-none">View permissions requested</summary>
          <div class="mt-3 bg-surface-sunk rounded-lg px-4 py-3 text-caption text-grey-500 space-y-1.5 animate-fade-in-down">
            <p><strong class="text-grey-700">gmail.readonly</strong> — read your inbox only, no modifications</p>
            <p><strong class="text-grey-700">calendar.events</strong> — create events on a dedicated "Replies" calendar</p>
            <p class="pt-1 text-grey-400">All email data stays on your Mac. Only subject + body are sent to the LLM for classification.</p>
          </div>
        </details>
        <!-- Design-file addition: preview link -->
        <button
          @click="appStatus = { ...(appStatus ?? { total_messages: 0, total_tasks: 0, open_tasks: 0, last_poll: null, account_email: null, reauth_state: 'idle' as const, needs_reauth: false, slack_connected: false }), authenticated: true }"
          class="flex items-center gap-1.5 text-caption text-grey-400 hover:text-grey-600 transition-colors mt-1"
        >
          Preview the app without Gmail →
        </button>
      </div>

      <!-- Authenticated: normal task view -->
      <template v-else>
        <!-- First-run: authenticated but no messages yet -->
        <div
          v-if="appStatus && appStatus.total_messages === 0 && !store.polling"
          class="bg-surface-card rounded-xl shadow-card px-8 py-12 flex flex-col items-center text-center gap-4 animate-fade-in-up"
        >
          <div class="w-14 h-14 bg-brand-50 rounded-full flex items-center justify-center">
            <ArrowPathIcon class="w-7 h-7 text-brand-primary" />
          </div>
          <div>
            <h2 class="text-heading text-grey-900 mb-2">Ready to scan</h2>
            <p class="text-body text-grey-500 max-w-sm">
              Hit <strong class="text-grey-700">Poll now</strong> to scan your last 7 days of inbox and detect emails that need a reply.
            </p>
          </div>
        </div>

        <!-- Scanning skeleton -->
        <div v-else-if="store.polling" class="bg-surface-card rounded-xl shadow-card overflow-hidden">
          <div class="px-4 py-3 border-b border-grey-100">
            <div class="h-3 w-40 rounded skeleton-shimmer" />
          </div>
          <div class="divide-y divide-grey-100">
            <div v-for="n in 5" :key="n" class="px-4 py-4 flex items-center gap-4">
              <div class="w-8 h-8 rounded-full skeleton-shimmer shrink-0" />
              <div class="flex flex-col gap-1.5 w-28">
                <div class="h-2.5 rounded skeleton-shimmer" />
                <div class="h-2 w-20 rounded skeleton-shimmer" />
              </div>
              <div class="h-2.5 flex-1 rounded skeleton-shimmer" />
              <div class="h-6 w-16 rounded-pill skeleton-shimmer" />
              <div class="h-2.5 w-20 rounded skeleton-shimmer" />
            </div>
          </div>
          <p class="px-4 py-3 text-caption text-grey-400 text-center border-t border-grey-100">
            Scanning your inbox and classifying emails…
          </p>
        </div>

        <template v-else>
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div class="flex items-center gap-3 flex-wrap">
              <FilterChips :active="store.activeFilter" @change="store.setFilter" />
              <div class="h-4 w-px bg-grey-200 hidden sm:block" />
              <FilterBar
                :model-value="store.advancedFilters"
                @update:model-value="store.setAdvancedFilters"
              />
            </div>
            <div v-if="appStatus" class="text-caption text-grey-500 tabular-nums">
              Showing <strong class="text-grey-800">{{ store.tasks.length }}</strong> of {{ appStatus.total_tasks }} tasks
            </div>
          </div>

          <!-- Bulk action toolbar — slides in when rows are selected -->
          <Transition
            enter-active-class="transition-all duration-150 ease-out"
            enter-from-class="opacity-0 -translate-y-1"
            leave-active-class="transition-all duration-100 ease-in"
            leave-to-class="opacity-0 -translate-y-1"
          >
            <div
              v-if="store.hasSelection"
              class="flex items-center gap-3 px-4 py-2.5 bg-brand-50 border border-brand-light rounded-lg"
              role="toolbar"
              aria-label="Bulk actions"
            >
              <span class="text-caption font-bold text-brand-darkest tabular-nums">
                {{ store.selectedIds.size }} selected
              </span>
              <div class="h-4 w-px bg-brand-light" />
              <button
                @click="store.bulkMarkReplied"
                class="flex items-center gap-1.5 px-3 py-1.5 bg-brand-primary hover:bg-brand-dark text-white text-caption font-semibold rounded-lg transition-colors"
                aria-label="Mark selected tasks as replied"
              >
                <CheckIcon class="w-3.5 h-3.5" />
                Mark replied
              </button>
              <button
                @click="store.bulkDismiss"
                class="flex items-center gap-1.5 px-3 py-1.5 bg-brand-50 hover:bg-brand-lightest text-brand-primary border border-brand-light text-caption font-semibold rounded-lg transition-colors"
                aria-label="Dismiss selected tasks"
              >
                <XMarkIcon class="w-3.5 h-3.5" />
                Dismiss
              </button>
              <button
                @click="store.clearSelection"
                class="ml-auto p-1.5 rounded text-brand-light hover:text-brand-primary transition-colors"
                aria-label="Clear selection"
              >
                <XMarkIcon class="w-3.5 h-3.5" />
              </button>
            </div>
          </Transition>

          <!-- Quick add bar -->
          <QuickAddBar ref="quickAddRef" @add="onAddTask" />

          <div class="bg-surface-card rounded-xl shadow-card overflow-hidden">
            <!-- All-caught-up delight state -->
            <div
              v-if="!store.loading && store.tasks.length === 0 && appStatus && appStatus.total_messages > 0"
              class="py-14 flex flex-col items-center gap-3 animate-fade-in-up"
            >
              <div class="w-16 h-16 bg-brand-50 rounded-full flex items-center justify-center">
                <CheckIcon class="w-8 h-8 text-brand-primary" />
              </div>
              <div class="text-center space-y-1.5">
                <p class="text-heading text-grey-900">
                  {{ store.activeFilter === 'open' ? 'Inbox zero.' : 'Nothing here.' }}
                </p>
                <p class="text-body text-grey-500">
                  {{ store.activeFilter === 'open' ? 'Go touch grass.' : `No ${store.activeFilter} tasks right now.` }}
                </p>
              </div>
              <div class="flex items-center gap-3 text-caption text-grey-400 tabular-nums mt-1">
                <span>{{ appStatus.total_tasks }} tasks total</span>
                <span>·</span>
                <span>Synced {{ formatPollTime(appStatus.last_poll) }}</span>
              </div>
              <button
                @click="onPollNow"
                :disabled="store.polling"
                class="mt-1 flex items-center gap-1.5 px-3 py-1.5 bg-brand-50 hover:bg-brand-lightest text-brand-primary border border-brand-light text-caption font-semibold rounded-lg disabled:opacity-50 transition-colors"
              >
                <ArrowPathIcon class="w-3.5 h-3.5" />
                Poll now
              </button>
            </div>

            <TaskTable
              v-else
              ref="tableRef"
              :tasks="store.tasks"
              :loading="store.loading"
              :active-filter="store.activeFilter"
              :focused-index="focusedIndex"
              :selected-ids="store.selectedIds"
              :all-selected="store.allSelected"
              @update-reply-by="store.updateReplyBy"
              @update-task="(id, data) => store.updateTask(id, data)"
              @mark-replied="onMarkReplied"
              @dismiss="onDismiss"
              @not-a-task="store.markNotATask"
              @toggle-select="store.toggleSelect"
              @toggle-select-all="store.toggleSelectAll"
            />
          </div>
        </template>
      </template>
    </main>
  </div>
</template>
