<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Sparkles as SparklesIcon,
  Clipboard as ClipboardDocumentIcon,
  ClipboardCheck as ClipboardDocumentCheckIcon,
  ExternalLink as ArrowTopRightOnSquareIcon,
  RefreshCw as ArrowPathIcon,
  CalendarPlus,
  CheckCircle2 as CheckCircleIcon,
} from 'lucide-vue-next'
import type { Task } from '../types'
import { api } from '../api'

const props = defineProps<{ task: Task }>()

// ── Draft Reply ───────────────────────────────────────────────────────
const instructions = ref('')
const draft = ref<string | null>(null)
const loadingDraft = ref(false)
const copied = ref(false)
const draftError = ref<string | null>(null)
const draftMeeting = ref<{ start: string; end: string; html_link: string | null; title: string; error?: string } | null>(null)

const MAX_GMAIL_BODY = 1400

const gmailComposeUrl = computed(() => {
  if (!draft.value || !props.task.sender_email) return null
  if (draft.value.length > MAX_GMAIL_BODY) return null
  const to  = encodeURIComponent(props.task.sender_email)
  const sub = encodeURIComponent(`Re: ${props.task.subject ?? ''}`)
  const bod = encodeURIComponent(draft.value)
  return `https://mail.google.com/mail/u/0/?view=cm&fs=1&to=${to}&su=${sub}&body=${bod}`
})

const draftTooLong = computed(() => !!draft.value && draft.value.length > MAX_GMAIL_BODY)

async function generate() {
  loadingDraft.value = true
  draft.value = null
  copied.value = false
  draftError.value = null
  draftMeeting.value = null
  const text = instructions.value.trim()
  try {
    if (text) {
      // Smart path: detect meeting intent + draft reply in one shot
      const res = await api.smartReply(props.task.id, text)
      draft.value = res.draft
      if (res.meeting) draftMeeting.value = res.meeting
    } else {
      const res = await api.draftReply(props.task.id)
      draft.value = res.draft
    }
  } catch {
    draftError.value = 'Could not generate draft. Please try again.'
  } finally {
    loadingDraft.value = false
  }
}

async function copyDraft() {
  if (!draft.value) return
  await navigator.clipboard.writeText(draft.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 1800)
}

// ── Schedule Meeting ──────────────────────────────────────────────────
function nextSaturday(): string {
  const d = new Date()
  const daysUntilSat = (6 - d.getDay() + 7) % 7 || 7
  d.setDate(d.getDate() + daysUntilSat)
  return d.toISOString().slice(0, 10)
}

const meetingDate        = ref(nextSaturday())
const meetingWindowStart = ref('09:00')
const meetingWindowEnd   = ref('12:00')
const meetingDuration    = ref(30)
const meetingTitle       = ref('')
const loadingMeeting     = ref(false)
const meetingError       = ref<string | null>(null)
const meetingResult      = ref<{ start: string; end: string; html_link: string | null; title: string } | null>(null)

const meetingTitlePlaceholder = computed(() =>
  `Meeting with ${props.task.sender || props.task.sender_email || 'sender'}`
)

function formatSlot(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function bookMeeting() {
  loadingMeeting.value = true
  meetingError.value = null
  meetingResult.value = null
  try {
    const res = await api.scheduleMeeting(props.task.id, {
      date: meetingDate.value,
      window_start: meetingWindowStart.value,
      window_end: meetingWindowEnd.value,
      duration_minutes: meetingDuration.value,
      title: meetingTitle.value.trim() || undefined,
    })
    meetingResult.value = res
  } catch (e: any) {
    const msg = e?.message || ''
    if (msg.includes('409')) {
      meetingError.value = 'No free slot found in that window — try a wider range or different date.'
    } else if (msg.includes('400')) {
      meetingError.value = 'No email address found for this sender — cannot send a calendar invite.'
    } else {
      meetingError.value = 'Could not book the meeting. Please try again.'
    }
  } finally {
    loadingMeeting.value = false
  }
}
</script>

<template>
  <div class="animate-fade-in-down bg-brand-50 border-b border-brand-lightest divide-y divide-brand-lightest">

    <!-- ── Draft Reply section ── -->
    <div class="px-5 py-4">
      <div class="flex items-center gap-1.5 text-micro font-extrabold uppercase tracking-widest text-brand-primary mb-3">
        <SparklesIcon class="w-3.5 h-3.5" />
        Draft Reply
      </div>

      <div class="mb-3">
        <label class="block text-caption text-grey-500 mb-1">
          Instructions <span class="text-grey-400">(optional)</span>
        </label>
        <div class="relative">
          <textarea
            v-model="instructions"
            :disabled="loadingDraft"
            maxlength="500"
            rows="2"
            placeholder='e.g. "decline politely", "ask for more time", "say yes and CC Ahmed"'
            class="w-full max-w-xl resize-none rounded-lg border border-grey-300 bg-surface-card px-3 py-2 text-body text-grey-800 placeholder-grey-400 focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent disabled:opacity-50 transition"
          />
          <span class="absolute bottom-2 right-2 text-micro text-grey-400">{{ instructions.length }}/500</span>
        </div>
      </div>

      <button
        @click="generate"
        :disabled="loadingDraft"
        class="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-caption font-semibold transition-all disabled:opacity-50"
        :class="draft ? 'bg-surface-card text-brand-primary border border-brand-light hover:bg-brand-lightest' : 'bg-brand-primary text-white hover:bg-brand-dark'"
      >
        <ArrowPathIcon v-if="loadingDraft" class="w-3.5 h-3.5 animate-spin" />
        <SparklesIcon v-else class="w-3.5 h-3.5" />
        {{ loadingDraft ? 'Generating…' : draft ? 'Regenerate' : 'Generate' }}
      </button>

      <p v-if="draftError" class="mt-2 text-caption text-red-500">{{ draftError }}</p>

      <template v-if="draft">
        <div class="mt-4 pt-3 border-t border-brand-lightest">

          <!-- Meeting booked confirmation -->
          <div v-if="draftMeeting && !draftMeeting.error" class="flex items-start gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2.5 mb-3">
            <CheckCircleIcon class="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
            <div class="min-w-0">
              <p class="text-caption font-semibold text-grey-800">Meeting booked: {{ draftMeeting.title }}</p>
              <p class="text-caption text-grey-500">
                {{ formatSlot(draftMeeting.start) }} – {{ new Date(draftMeeting.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
              </p>
              <a v-if="draftMeeting.html_link" :href="draftMeeting.html_link" target="_blank" rel="noopener"
                class="text-caption text-brand-primary hover:underline inline-flex items-center gap-1 mt-0.5">
                View in Calendar <ArrowTopRightOnSquareIcon class="w-3 h-3" />
              </a>
            </div>
          </div>
          <p v-if="draftMeeting?.error" class="text-caption text-amber-600 mb-3">
            Could not book meeting: {{ draftMeeting.error }}
          </p>

          <pre class="text-body text-grey-800 whitespace-pre-wrap font-sans leading-relaxed max-w-xl">{{ draft }}</pre>
          <p v-if="draftTooLong" class="mt-2 text-caption text-amber-600">
            Draft is too long to pre-fill Gmail — use Copy instead.
          </p>
          <div class="flex items-center gap-2 mt-3">
            <button
              @click="copyDraft"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold transition-all"
              :class="copied
                ? 'bg-status-replied text-white border border-status-replied'
                : 'bg-surface-card text-brand-primary border border-brand-light hover:bg-brand-lightest'"
            >
              <ClipboardDocumentCheckIcon v-if="copied" class="w-3.5 h-3.5" />
              <ClipboardDocumentIcon v-else class="w-3.5 h-3.5" />
              {{ copied ? 'Copied!' : 'Copy' }}
            </button>
            <a
              v-if="gmailComposeUrl"
              :href="gmailComposeUrl"
              target="_blank"
              rel="noopener"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold bg-surface-card text-brand-primary border border-brand-light hover:bg-brand-lightest transition-all"
            >
              <ArrowTopRightOnSquareIcon class="w-3.5 h-3.5" />
              Open in Gmail
            </a>
          </div>
        </div>
      </template>
    </div>

    <!-- ── Schedule Meeting section ── -->
    <div class="px-5 py-4">
      <div class="flex items-center gap-1.5 text-micro font-extrabold uppercase tracking-widest text-brand-primary mb-3">
        <CalendarPlus class="w-3.5 h-3.5" />
        Schedule Meeting
      </div>

      <!-- Booked result -->
      <div v-if="meetingResult" class="flex items-start gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2.5 mb-3">
        <CheckCircleIcon class="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
        <div class="min-w-0">
          <p class="text-caption font-semibold text-grey-800">{{ meetingResult.title }}</p>
          <p class="text-caption text-grey-500">
            {{ formatSlot(meetingResult.start) }} – {{ new Date(meetingResult.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
          </p>
          <a
            v-if="meetingResult.html_link"
            :href="meetingResult.html_link"
            target="_blank"
            rel="noopener"
            class="text-caption text-brand-primary hover:underline inline-flex items-center gap-1 mt-0.5"
          >
            View in Calendar <ArrowTopRightOnSquareIcon class="w-3 h-3" />
          </a>
        </div>
      </div>

      <div v-if="!meetingResult" class="flex flex-wrap gap-3 items-end">
        <!-- Date -->
        <div>
          <label class="block text-caption text-grey-500 mb-1">Date</label>
          <input
            v-model="meetingDate"
            type="date"
            :disabled="loadingMeeting"
            class="rounded-lg border border-grey-300 bg-surface-card px-2.5 py-1.5 text-body text-grey-800 focus:outline-none focus:ring-2 focus:ring-brand-primary disabled:opacity-50"
          />
        </div>

        <!-- Window -->
        <div>
          <label class="block text-caption text-grey-500 mb-1">Free window</label>
          <div class="flex items-center gap-1.5">
            <input
              v-model="meetingWindowStart"
              type="time"
              :disabled="loadingMeeting"
              class="rounded-lg border border-grey-300 bg-surface-card px-2.5 py-1.5 text-body text-grey-800 focus:outline-none focus:ring-2 focus:ring-brand-primary disabled:opacity-50"
            />
            <span class="text-caption text-grey-400">to</span>
            <input
              v-model="meetingWindowEnd"
              type="time"
              :disabled="loadingMeeting"
              class="rounded-lg border border-grey-300 bg-surface-card px-2.5 py-1.5 text-body text-grey-800 focus:outline-none focus:ring-2 focus:ring-brand-primary disabled:opacity-50"
            />
          </div>
        </div>

        <!-- Duration -->
        <div>
          <label class="block text-caption text-grey-500 mb-1">Duration</label>
          <select
            v-model="meetingDuration"
            :disabled="loadingMeeting"
            class="rounded-lg border border-grey-300 bg-surface-card px-2.5 py-1.5 text-body text-grey-800 focus:outline-none focus:ring-2 focus:ring-brand-primary disabled:opacity-50"
          >
            <option :value="15">15 min</option>
            <option :value="30">30 min</option>
            <option :value="45">45 min</option>
            <option :value="60">60 min</option>
          </select>
        </div>
      </div>

      <!-- Optional title -->
      <div v-if="!meetingResult" class="mt-2.5">
        <input
          v-model="meetingTitle"
          type="text"
          :placeholder="meetingTitlePlaceholder"
          :disabled="loadingMeeting"
          maxlength="100"
          class="w-full max-w-sm rounded-lg border border-grey-300 bg-surface-card px-3 py-1.5 text-body text-grey-800 placeholder-grey-400 focus:outline-none focus:ring-2 focus:ring-brand-primary disabled:opacity-50 transition"
        />
      </div>

      <p v-if="meetingError" class="mt-2 text-caption text-red-500">{{ meetingError }}</p>

      <div class="flex gap-2 mt-3">
        <button
          v-if="!meetingResult"
          @click="bookMeeting"
          :disabled="loadingMeeting"
          class="flex items-center gap-1.5 px-4 py-1.5 bg-brand-primary hover:bg-brand-dark text-white rounded-lg text-caption font-semibold transition-all disabled:opacity-50"
        >
          <ArrowPathIcon v-if="loadingMeeting" class="w-3.5 h-3.5 animate-spin" />
          <CalendarPlus v-else class="w-3.5 h-3.5" />
          {{ loadingMeeting ? 'Booking…' : 'Book Meeting' }}
        </button>

        <button
          v-if="meetingResult"
          @click="meetingResult = null; meetingError = null"
          class="flex items-center gap-1.5 px-4 py-1.5 bg-surface-card text-brand-primary border border-brand-light hover:bg-brand-lightest rounded-lg text-caption font-semibold transition-all"
        >
          Schedule another
        </button>
      </div>
    </div>

  </div>
</template>
