<script setup lang="ts">
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import VueDatePicker from '@vuepic/vue-datepicker'
import {
  Check as CheckIcon,
  X as XMarkIcon,
  Flag as FlagIcon,
  ExternalLink as ArrowTopRightOnSquareIcon,
  Sparkles as SparklesIcon,
  Info as InformationCircleIcon,
  MoreHorizontal as EllipsisHorizontalIcon,
  SquarePen as PencilSquareIcon,
  StickyNote as StickyNoteIcon,
  Star as StarIcon,
} from 'lucide-vue-next'
import type { Task, ClassificationInfo, TaskLink } from '../types'
import { api } from '../api'
import { useTaskStore } from '../stores/tasks'
import PriorityBadge from './ui/PriorityBadge.vue'
import CompletionBadge from './ui/CompletionBadge.vue'
import TaskNotesEditor from './TaskNotesEditor.vue'
import TaskLinksList from './TaskLinksList.vue'
import ReplyDraftPanel from './ReplyDraftPanel.vue'

const props = defineProps<{ task: Task; focused?: boolean; selected?: boolean }>()
const emit = defineEmits<{
  'update-reply-by': [date: Date]
  'update-task': [data: { title?: string; priority?: import('../types').Priority; completion?: import('../types').Completion }]
  'mark-replied': []
  dismiss: []
  'not-a-task': []
  'toggle-select': []
}>()

// ── Status ────────────────────────────────────────────────────────────
const isOverdue = computed(
  () => props.task.status === 'open' && new Date(props.task.reply_by) < new Date(),
)
const isNearDue = computed(() => {
  if (isOverdue.value) return false
  const diff = new Date(props.task.reply_by).getTime() - Date.now()
  return props.task.status === 'open' && diff > 0 && diff < 4 * 60 * 60 * 1000
})

// ── Avatar ────────────────────────────────────────────────────────────
const TINTS = [
  { bg: '#fde2e6', fg: '#9f1239' },
  { bg: '#fef3c7', fg: '#92400e' },
  { bg: '#e0f2fe', fg: '#075985' },
  { bg: '#dcfce7', fg: '#166534' },
  { bg: '#ede9fe', fg: '#5b21b6' },
  { bg: '#fce7f3', fg: '#9d174d' },
]
function hashStr(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return h
}
const isManual = computed(() => props.task.source === 'manual')
const isSlack = computed(() => props.task.source === 'slack')
const avatarTint = computed(() =>
  isManual.value
    ? { bg: '#f3f4f6', fg: '#6b7280' }
    : isSlack.value
      ? { bg: '#4a154b', fg: '#ffffff' }
      : TINTS[hashStr(props.task.sender_email ?? '') % TINTS.length]
)
const avatarInitials = computed(() =>
  (props.task.sender ?? '').split(/\s+/).map((w: string) => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() || '?'
)

// ── Date formatting ───────────────────────────────────────────────────
const gmailUrl = computed(
  () => props.task.thread_id && !isSlack.value
    ? `https://mail.google.com/mail/u/0/#inbox/${props.task.thread_id}`
    : null,
)

const slackUrl = computed(() => {
  if (!isSlack.value || !props.task.slack_team_id || !props.task.slack_channel_id || !props.task.slack_ts) return null
  return `slack://channel?team=${props.task.slack_team_id}&id=${props.task.slack_channel_id}&message=${props.task.slack_ts}`
})

function formatReplyBy(iso: string) {
  const d = new Date(iso)
  const now = Date.now()
  const diff = d.getTime() - now
  const absH = Math.abs(diff) / 3600000
  const dateStr = d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  let rel: string
  if (diff < 0) {
    rel = absH < 24 ? `${Math.round(absH)}h overdue` : `${Math.round(absH / 24)}d overdue`
  } else {
    if (absH < 1) rel = `in ${Math.round(absH * 60)}m`
    else if (absH < 24) rel = `in ${Math.round(absH)}h`
    else rel = `in ${Math.round(absH / 24)}d`
  }
  return { dateStr, rel }
}

const replyByFormatted = computed(() => formatReplyBy(props.task.reply_by))

// ── Priority pill ─────────────────────────────────────────────────────
const priorityMeta = computed(() => ({
  high:   { label: 'HIGH',   cls: 'bg-brand-lightest text-brand-darkest font-bold' },
  normal: { label: 'normal', cls: 'bg-grey-100 text-grey-600' },
  low:    { label: 'low',    cls: '' },
})[props.task.priority])

// ── Inline title edit ─────────────────────────────────────────────────
const editingTitle = ref(false)
const draftTitle = ref('')
const titleInputRef = ref<HTMLInputElement | null>(null)

function startEditTitle(e: MouseEvent) {
  e.stopPropagation()
  draftTitle.value = props.task.title ?? props.task.summary ?? props.task.subject ?? ''
  editingTitle.value = true
  nextTick(() => { titleInputRef.value?.select() })
}

function saveTitle() {
  const trimmed = draftTitle.value.trim()
  const original = props.task.title ?? props.task.summary ?? props.task.subject ?? ''
  if (trimmed && trimmed !== original) emit('update-task', { title: trimmed })
  editingTitle.value = false
}

function cancelEditTitle() {
  editingTitle.value = false
}

// ── Priority cycling ──────────────────────────────────────────────────
const PRIORITIES = ['low', 'normal', 'high'] as const

function cyclePriority(e: MouseEvent) {
  e.stopPropagation()
  const idx = PRIORITIES.indexOf(props.task.priority as typeof PRIORITIES[number])
  emit('update-task', { priority: PRIORITIES[(idx + 1) % PRIORITIES.length] })
}

// ── Completion cycling ────────────────────────────────────────────────
const COMPLETIONS = ['not_started', 'in_progress', 'on_hold', 'completed'] as const

function cycleCompletion(e: MouseEvent) {
  e.stopPropagation()
  const idx = COMPLETIONS.indexOf(props.task.completion as typeof COMPLETIONS[number])
  emit('update-task', { completion: COMPLETIONS[(idx + 1) % COMPLETIONS.length] })
}

// ── Suggest reply ─────────────────────────────────────────────────────
const showDraftPanel = ref(false)

function onToggleDraftPanel() {
  showDraftPanel.value = !showDraftPanel.value
  if (showDraftPanel.value) {
    showWhy.value = false
    showNotes.value = false
  }
}

// ── Notes & links panel ──────────────────────────────────────────────
const taskStore = useTaskStore()
const showNotes = ref(false)
const notesEditorRef = ref<InstanceType<typeof TaskNotesEditor> | null>(null)
const linksLoading = ref(false)

const links = computed<TaskLink[]>(() => taskStore.linksByTask[props.task.id] ?? [])

const hasNotes = computed(() => !!props.task.notes && props.task.notes.trim().length > 0)
const linkCount = computed(() => props.task.link_count ?? 0)
const hasAttachments = computed(() => hasNotes.value || linkCount.value > 0)
const notesIndicatorTitle = computed(() => {
  const parts: string[] = []
  if (hasNotes.value) parts.push('Notes')
  if (linkCount.value === 1) parts.push('1 link')
  else if (linkCount.value > 1) parts.push(`${linkCount.value} links`)
  return parts.length ? parts.join(' · ') : 'Notes & links'
})

async function onToggleNotes() {
  if (showNotes.value) { showNotes.value = false; return }
  showNotes.value = true
  if (!(props.task.id in taskStore.linksByTask)) {
    linksLoading.value = true
    try {
      await taskStore.loadLinks(props.task.id)
    } catch {
      // ignore — empty list will render
    } finally {
      linksLoading.value = false
    }
  }
}

async function onSaveNotes(value: string) {
  try {
    await taskStore.updateTask(props.task.id, { notes: value })
    notesEditorRef.value?.markSaved()
  } catch {
    notesEditorRef.value?.markError()
  }
}

async function onAddLink(data: { url: string; label?: string }) {
  try {
    await taskStore.addLink(props.task.id, data.url, data.label)
  } catch (e) {
    console.error('add link failed', e)
  }
}

async function onRemoveLink(linkId: number) {
  try {
    await taskStore.removeLink(props.task.id, linkId)
  } catch (e) {
    console.error('remove link failed', e)
  }
}

// ── Why this? ─────────────────────────────────────────────────────────
const loadingWhy = ref(false)
const classification = ref<ClassificationInfo | null>(null)
const showWhy = ref(false)

async function onToggleWhy() {
  if (showWhy.value) { showWhy.value = false; return }
  showDraftPanel.value = false
  showWhy.value = true
  if (classification.value) return
  loadingWhy.value = true
  try {
    classification.value = await api.getClassification(props.task.id)
  } catch {
    classification.value = null
    showWhy.value = false
  } finally {
    loadingWhy.value = false
  }
}

const confidenceLabel: Record<string, string> = {
  explicit: 'Explicit deadline in email',
  implied:  'Implied deadline',
  none:     'No deadline found — defaulted',
}

// ── Completion animation ──────────────────────────────────────────────
const completing = ref(false)
const completingDismiss = ref(false)
const ANIM_MS = 650

async function onMarkReplied() {
  if (completing.value || completingDismiss.value) return
  completing.value = true
  await new Promise(r => setTimeout(r, ANIM_MS))
  emit('mark-replied')
}

async function onDismiss() {
  if (completing.value || completingDismiss.value) return
  completingDismiss.value = true
  await new Promise(r => setTimeout(r, ANIM_MS))
  emit('dismiss')
}

// ── Secondary overflow dropdown ───────────────────────────────────────
const showMore = ref(false)
const moreRef = ref<HTMLElement | null>(null)
const moreMenuPos = ref({ top: 0, right: 0 })

function toggleMore(e: MouseEvent) {
  e.stopPropagation()
  if (!showMore.value && moreRef.value) {
    const rect = moreRef.value.getBoundingClientRect()
    moreMenuPos.value = { top: rect.bottom + 4, right: window.innerWidth - rect.right }
  }
  showMore.value = !showMore.value
}

function onClickOutside(e: MouseEvent) {
  if (moreRef.value && !moreRef.value.contains(e.target as Node)) showMore.value = false
}
onMounted(() => document.addEventListener('click', onClickOutside, true))
onUnmounted(() => document.removeEventListener('click', onClickOutside, true))

// ── Datepicker (keyboard 'e') ─────────────────────────────────────────
const datepickerRef = ref<InstanceType<typeof VueDatePicker> | null>(null)

defineExpose({
  openDatePicker() { datepickerRef.value?.openMenu() },
})

watch(() => props.focused, (v) => {
  if (!v) {
    showDraftPanel.value = false
    showWhy.value = false
    showMore.value = false
  }
})
</script>

<template>
  <!-- Main row -->
  <tr
    :class="[
      'transition-colors duration-100',
      completing       ? 'row-completing'  : '',
      completingDismiss ? 'row-dismissing' : '',
    ]"
    :style="{
      borderLeft: isOverdue
        ? '3px solid var(--status-overdue)'
        : isNearDue
          ? '3px solid var(--status-due-soon)'
          : '3px solid transparent',
      background: (!completing && !completingDismiss && focused)
        ? 'var(--brand-50)'
        : 'transparent',
      boxShadow: (!completing && !completingDismiss && focused)
        ? 'inset 3px 0 0 0 var(--brand-primary)'
        : 'none',
      cursor: 'pointer',
    }"
    :aria-label="`Task: ${task.title ?? task.summary ?? task.subject}, from ${task.sender ?? 'you'}${isOverdue ? ', overdue' : isNearDue ? ', due soon' : ''}`"
  >
    <!-- Checkbox -->
    <td class="px-3 py-3 w-8">
      <input
        type="checkbox"
        :checked="selected"
        @change="emit('toggle-select')"
        :aria-label="`Select task: ${task.summary ?? task.subject}`"
        class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary cursor-pointer"
        @click.stop
      />
    </td>

    <!-- From — avatar + name stacked (matches design: 192px col) -->
    <td class="px-3 py-3" style="width:192px">
      <div class="flex items-center gap-2.5">
        <!-- Avatar: pencil icon for manual, initials + optional photo for mail -->
        <div
          class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-caption shrink-0 relative overflow-hidden"
          :style="{ background: avatarTint.bg, color: avatarTint.fg }"
          aria-hidden="true"
        >
          <PencilSquareIcon v-if="isManual" class="w-4 h-4" />
          <span v-else-if="isSlack && !task.sender_avatar" class="text-[10px] font-black leading-none">S</span>
          <template v-else-if="!isSlack">{{ avatarInitials }}</template>
          <!-- Slack profile photo -->
          <img
            v-if="isSlack && task.sender_avatar"
            :src="task.sender_avatar"
            :alt="task.sender ?? ''"
            class="absolute inset-0 w-full h-full object-cover"
            @error="($event.target as HTMLImageElement).style.display = 'none'"
          />
          <!-- Gmail profile photo: loads on top of initials; hides itself on error -->
          <img
            v-if="!isManual && !isSlack && task.sender_email"
            :src="`/api/contacts/photo?email=${encodeURIComponent(task.sender_email)}`"
            :alt="task.sender ?? ''"
            class="absolute inset-0 w-full h-full object-cover"
            @error="($event.target as HTMLImageElement).style.display = 'none'"
          />
        </div>
        <!-- Name + email -->
        <div class="min-w-0 flex-1">
          <div class="text-body font-semibold text-grey-900 truncate flex items-center gap-1">
            <StarIcon
              v-if="task.is_vip_sender"
              class="w-3.5 h-3.5 text-brand-primary fill-brand-primary shrink-0"
              title="Priority sender"
            />
            <span class="truncate">{{ isManual ? 'You' : (task.sender || task.sender_email) }}</span>
          </div>
          <div v-if="isSlack" class="text-caption text-[#4a154b] font-semibold truncate">Slack DM</div>
          <div v-else-if="!isManual" class="text-caption text-grey-500 truncate">{{ task.sender_email }}</div>
          <div v-else class="text-caption text-grey-400">manual task</div>
        </div>
      </div>
    </td>

    <!-- Task title/summary + subject caption -->
    <td class="px-3 py-3 min-w-0">
      <div class="task-summary text-subheading text-grey-900 mb-0.5">
        <input
          v-if="editingTitle"
          ref="titleInputRef"
          v-model="draftTitle"
          class="w-full bg-transparent border-b-2 border-brand-primary outline-none text-subheading text-grey-900 pb-0.5"
          @keydown.enter.prevent="saveTitle"
          @keydown.escape.prevent="cancelEditTitle"
          @blur="saveTitle"
          @click.stop
        />
        <span
          v-else
          @click="startEditTitle"
          class="cursor-text hover:text-brand-primary transition-colors"
          title="Click to edit"
        >{{ task.title ?? task.summary ?? task.subject }}</span>
      </div>
      <div v-if="!isManual && task.summary" class="text-caption text-grey-500 truncate max-w-[420px]" :title="task.subject ?? ''">{{ task.subject }}</div>
      <div v-if="task.asker" class="text-caption text-grey-400">from {{ task.asker }}</div>
      <div v-if="isManual && task.notes" class="text-caption text-grey-500 truncate max-w-[420px]">{{ task.notes }}</div>
    </td>

    <!-- Priority — click to cycle low → normal → high -->
    <td class="px-3 py-3" style="width:90px">
      <PriorityBadge :priority="task.priority" clickable @click="cyclePriority" />
    </td>

    <!-- Completion — click to cycle not_started → in_progress → on_hold → completed -->
    <td class="px-3 py-3" style="width:120px">
      <CompletionBadge :completion="task.completion" clickable @click="cycleCompletion" />
    </td>

    <!-- Reply-by — date + relative time -->
    <td class="px-3 py-3 tabular-nums" style="width:130px">
      <VueDatePicker
        ref="datepickerRef"
        :model-value="new Date(task.reply_by)"
        auto-apply
        :enable-time-picker="false"
        :teleport="true"
        :week-start="6"
        @update:model-value="(d: Date | null) => { if (d) emit('update-reply-by', d) }"
      >
        <template #trigger>
          <button
            class="text-left hover:underline"
            :class="isOverdue ? 'text-status-overdue font-semibold' : isNearDue ? 'text-status-due-soon font-semibold' : 'text-grey-800'"
            style="font-size:13px; font-weight:600;"
            aria-label="Edit reply-by date"
            @click.stop
          >{{ replyByFormatted.dateStr }}</button>
          <div
            class="text-caption mt-0.5"
            :class="isOverdue ? 'text-status-overdue font-medium' : isNearDue ? 'text-status-due-soon font-medium' : 'text-grey-500'"
          >{{ replyByFormatted.rel }}</div>
        </template>
      </VueDatePicker>
    </td>

    <!-- Actions — matches design: ✨ ℹ 🕐 | ✕ ✓  + ⋯ for secondary -->
    <td class="px-3 py-3" style="width:196px">
      <div class="flex items-center justify-end gap-0.5">

        <!-- Message actions (hidden for manual tasks only) -->
        <template v-if="!isManual">
          <!-- Draft reply -->
          <button
            @click.stop="onToggleDraftPanel"
            :title="showDraftPanel ? 'Hide draft panel' : 'Draft a reply with AI'"
            :aria-label="showDraftPanel ? 'Hide draft panel' : 'Draft a reply with AI'"
            :class="[
              'w-[30px] h-[30px] rounded-lg inline-flex items-center justify-center transition-colors',
              showDraftPanel ? 'bg-brand-lightest text-brand-primary' : 'hover:bg-brand-lightest text-grey-400 hover:text-brand-primary',
            ]"
          >
            <SparklesIcon class="w-[15px] h-[15px]" />
          </button>

          <!-- Why this? -->
          <button
            @click.stop="onToggleWhy"
            :title="showWhy ? 'Hide reasoning' : 'Why is this a task?'"
            :aria-label="showWhy ? 'Hide reasoning' : 'Show classification reasoning'"
            :class="[
              'w-[30px] h-[30px] rounded-lg inline-flex items-center justify-center transition-colors',
              showWhy ? 'bg-brand-lightest text-brand-primary' : 'hover:bg-brand-lightest text-grey-400 hover:text-brand-primary',
              loadingWhy ? 'animate-pulse' : '',
            ]"
          >
            <InformationCircleIcon class="w-[15px] h-[15px]" />
          </button>

        </template>

        <!-- Notes & links — available for all task types -->
        <button
          @click.stop="onToggleNotes"
          :title="showNotes ? 'Hide notes' : notesIndicatorTitle"
          :aria-label="showNotes ? 'Hide notes and links' : notesIndicatorTitle"
          :class="[
            'relative w-[30px] h-[30px] rounded-lg inline-flex items-center justify-center transition-colors',
            showNotes
              ? 'bg-brand-lightest text-brand-primary'
              : hasAttachments
                ? 'bg-brand-50 text-brand-primary hover:bg-brand-lightest'
                : 'hover:bg-brand-lightest text-grey-400 hover:text-brand-primary',
          ]"
        >
          <StickyNoteIcon class="w-[15px] h-[15px]" />
          <span
            v-if="linkCount > 0"
            class="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-brand-primary text-white text-[10px] leading-[15px] font-bold tabular-nums text-center"
          >{{ linkCount > 9 ? '9+' : linkCount }}</span>
          <span
            v-else-if="hasNotes"
            class="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-brand-primary"
          />
        </button>

        <!-- Separator -->
        <div class="w-px h-4 bg-grey-200 mx-1 shrink-0" aria-hidden="true"></div>

        <!-- Dismiss -->
        <button
          @click.stop="onDismiss"
          :disabled="completing || completingDismiss"
          title="Dismiss (d)"
          aria-label="Dismiss task"
          :class="[
            'w-[30px] h-[30px] rounded-lg inline-flex items-center justify-center transition-colors',
            completingDismiss ? 'bg-grey-200 text-grey-600' : 'hover:bg-grey-100 text-grey-400 hover:text-grey-700',
          ]"
        >
          <XMarkIcon class="w-[15px] h-[15px]" />
        </button>

        <!-- Mark replied / Done — check-btn class triggers checkPop + green bg on completing -->
        <button
          @click.stop="onMarkReplied"
          :disabled="completing || completingDismiss"
          :title="isManual ? 'Mark done (r)' : 'Mark replied (r)'"
          :aria-label="isManual ? 'Mark done' : 'Mark replied'"
          :class="[
            'check-btn w-[30px] h-[30px] rounded-lg inline-flex items-center justify-center transition-colors',
            completing ? 'bg-status-replied text-white' : 'hover:bg-green-100 text-grey-400 hover:text-green-600',
          ]"
        >
          <CheckIcon class="w-[15px] h-[15px]" />
        </button>

        <!-- Secondary overflow — Not a task / Open in Gmail -->
        <div class="relative" ref="moreRef">
          <button
            @click="toggleMore"
            title="More actions"
            aria-label="More actions"
            :class="[
              'w-[30px] h-[30px] rounded-lg inline-flex items-center justify-center transition-colors',
              showMore ? 'bg-brand-lightest text-brand-primary' : 'hover:bg-grey-100 text-grey-400 hover:text-grey-700',
            ]"
          >
            <EllipsisHorizontalIcon class="w-[15px] h-[15px]" />
          </button>

          <Teleport to="body">
            <Transition enter-active-class="animate-scale-in" leave-active-class="transition-opacity duration-100" leave-to-class="opacity-0">
              <div
                v-if="showMore"
                class="fixed z-[9999] bg-surface-card rounded-lg shadow-dropdown border border-grey-200 py-1 min-w-[180px]"
                :style="{ top: moreMenuPos.top + 'px', right: moreMenuPos.right + 'px' }"
              >
                <!-- Gmail task menu -->
                <template v-if="!isManual && !isSlack">
                  <button
                    @click="emit('not-a-task'); showMore = false"
                    class="w-full flex items-center gap-2.5 px-3 py-2 text-body text-grey-700 hover:bg-grey-100 transition-colors text-left"
                  >
                    <FlagIcon class="w-4 h-4 shrink-0" />
                    Not a task
                  </button>
                  <div class="border-t border-grey-100 my-1" />
                  <a
                    v-if="gmailUrl"
                    :href="gmailUrl"
                    target="_blank"
                    rel="noopener"
                    class="w-full flex items-center gap-2.5 px-3 py-2 text-body text-grey-700 hover:bg-grey-100 transition-colors"
                    @click="showMore = false"
                  >
                    <ArrowTopRightOnSquareIcon class="w-4 h-4 shrink-0" />
                    Open in Gmail
                  </a>
                </template>

                <!-- Slack task menu -->
                <template v-if="isSlack">
                  <button
                    @click="emit('not-a-task'); showMore = false"
                    class="w-full flex items-center gap-2.5 px-3 py-2 text-body text-grey-700 hover:bg-grey-100 transition-colors text-left"
                  >
                    <FlagIcon class="w-4 h-4 shrink-0" />
                    Not a task
                  </button>
                  <div class="border-t border-grey-100 my-1" />
                  <a
                    v-if="slackUrl"
                    :href="slackUrl"
                    class="w-full flex items-center gap-2.5 px-3 py-2 text-body text-grey-700 hover:bg-grey-100 transition-colors"
                    @click="showMore = false"
                  >
                    <ArrowTopRightOnSquareIcon class="w-4 h-4 shrink-0" />
                    Open in Slack
                  </a>
                </template>

                <!-- Manual task menu -->
                <button
                  v-if="isManual"
                  @click="emit('dismiss'); showMore = false"
                  class="w-full flex items-center gap-2.5 px-3 py-2 text-body text-red-600 hover:bg-red-50 transition-colors text-left"
                >
                  <XMarkIcon class="w-4 h-4 shrink-0" />
                  Delete task
                </button>
              </div>
            </Transition>
          </Teleport>
        </div>

      </div>
    </td>
  </tr>

  <!-- Why this? expansion panel -->
  <tr v-if="showWhy && (classification || loadingWhy)">
    <td colspan="7" class="p-0" style="border-left: 3px solid var(--brand-primary)">
      <div class="animate-fade-in-down bg-brand-50 px-5 py-3.5 border-b border-brand-lightest">
        <div v-if="loadingWhy" class="text-caption text-brand-primary animate-pulse">Loading reasoning…</div>
        <template v-else-if="classification">
          <div class="flex items-center gap-1.5 text-micro font-extrabold uppercase tracking-widest text-brand-primary mb-2">
            <InformationCircleIcon class="w-3.5 h-3.5" />
            Why this is a task
          </div>
          <p class="text-body text-grey-800 mb-2.5 max-w-xl">{{ classification.reasoning ?? 'No reasoning recorded.' }}</p>
          <div v-if="classification.priority_signals.length" class="flex flex-wrap gap-1.5 mb-2.5">
            <span
              v-for="signal in classification.priority_signals"
              :key="signal"
              class="text-micro font-semibold px-2 py-0.5 rounded-pill bg-brand-lightest text-brand-dark"
            >{{ signal }}</span>
          </div>
          <div class="text-caption text-grey-500">
            Deadline: <strong class="text-grey-700 font-semibold">{{ confidenceLabel[classification.deadline_confidence ?? 'none'] }}</strong>
            &nbsp;·&nbsp;{{ classification.model }} / {{ classification.prompt_version }}
          </div>
        </template>
      </div>
    </td>
  </tr>

  <!-- Notes & links expansion panel -->
  <tr v-if="showNotes">
    <td colspan="7" class="p-0" style="border-left: 3px solid var(--brand-primary)">
      <div class="animate-fade-in-down bg-brand-50 px-5 py-3.5 border-b border-brand-lightest">
        <div class="flex items-center gap-1.5 text-micro font-extrabold uppercase tracking-widest text-brand-primary mb-3">
          <StickyNoteIcon class="w-3.5 h-3.5" />
          Notes &amp; links
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5 max-w-4xl">
          <TaskNotesEditor
            ref="notesEditorRef"
            :task-id="task.id"
            :model-value="task.notes"
            @save="onSaveNotes"
          />
          <div>
            <p v-if="linksLoading" class="text-caption text-grey-400 italic">Loading links…</p>
            <TaskLinksList
              v-else
              :task-id="task.id"
              :links="links"
              @add="onAddLink"
              @remove="onRemoveLink"
            />
          </div>
        </div>
      </div>
    </td>
  </tr>

  <!-- Draft reply expansion panel -->
  <tr v-if="showDraftPanel && !isManual">
    <td colspan="7" class="p-0" style="border-left: 3px solid var(--brand-primary)">
      <ReplyDraftPanel :task="task" />
    </td>
  </tr>
</template>
