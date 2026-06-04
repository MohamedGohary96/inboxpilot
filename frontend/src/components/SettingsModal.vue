<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { X as XMarkIcon, Check as CheckIcon } from 'lucide-vue-next'
import { api } from '../api'
import PrioritySendersSection from './PrioritySendersSection.vue'

const props = defineProps<{ open: boolean; slackConnected?: boolean }>()
const emit = defineEmits<{ close: []; slackStatusChanged: []; pollNow: [] }>()

interface Field {
  key: string
  label: string
  hint: string
  type: 'number' | 'text'
  min?: number
  max?: number
}

const FIELDS: Field[] = [
  { key: 'reply_by_days',          label: 'Default reply window (days)',         hint: 'Days added to received date when no deadline is found.',            type: 'number', min: 1,  max: 30 },
  { key: 'reply_by_hour',          label: 'Default reply hour (0–23)',            hint: 'Hour of day for the default reply-by deadline.',                   type: 'number', min: 0,  max: 23 },
  { key: 'poll_interval_minutes',  label: 'Poll interval (minutes)',              hint: 'How often to automatically check Gmail for new messages.',          type: 'number', min: 1,  max: 60 },
  { key: 'reminder_offsets_hours', label: 'Reminder offsets (hours, comma-sep)', hint: 'Hours before deadline to fire desktop notifications. E.g. 24,1,0.', type: 'text' },
]

const values = ref<Record<string, string>>({})
const saving = ref<Record<string, boolean>>({})
const saved  = ref<Record<string, boolean>>({})
const loadError = ref<string | null>(null)

// ── Gmail filter builder ─────────────────────────────────────────────
const CATEGORIES = [
  { key: 'promotions', label: 'Promotions' },
  { key: 'social',     label: 'Social'     },
  { key: 'updates',    label: 'Updates'    },
  { key: 'forums',     label: 'Forums'     },
]

const filterDays       = ref(7)
const filterUnreadOnly = ref(true)
const filterExcluded   = ref<Set<string>>(new Set(['promotions', 'social']))
const filterSaving     = ref(false)
const filterSaved      = ref(false)

function parseQuery(q: string) {
  const days = q.match(/newer_than:(\d+)d/)
  filterDays.value       = days ? parseInt(days[1]) : 7
  filterUnreadOnly.value = q.includes('is:unread')
  const exc = new Set<string>()
  for (const cat of CATEGORIES) {
    if (q.includes(`-category:${cat.key}`)) exc.add(cat.key)
  }
  filterExcluded.value = exc
}

const builtQuery = computed(() => {
  const parts: string[] = ['in:inbox']
  if (filterUnreadOnly.value) parts.push('is:unread')
  for (const cat of CATEGORIES) {
    if (filterExcluded.value.has(cat.key)) parts.push(`-category:${cat.key}`)
  }
  parts.push(`newer_than:${filterDays.value}d`)
  return parts.join(' ')
})

function toggleCategory(key: string) {
  const next = new Set(filterExcluded.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  filterExcluded.value = next
}

async function saveFilter() {
  filterSaving.value = true
  try {
    await api.updateSetting('gmail_query', builtQuery.value)
    filterSaved.value = true
    setTimeout(() => { filterSaved.value = false }, 1500)
  } finally {
    filterSaving.value = false
  }
}
// ── /Gmail filter builder ────────────────────────────────────────────

async function load() {
  try {
    values.value = await api.getSettings()
    parseQuery(values.value['gmail_query'] ?? 'in:inbox is:unread -category:promotions -category:social newer_than:7d')
    slackLookbackDays.value = parseInt(values.value['slack_lookback_days'] ?? '7')
  } catch {
    loadError.value = 'Could not load settings.'
  }
}

async function saveSlackLookback() {
  slackLookbackSaving.value = true
  try {
    await api.updateSetting('slack_lookback_days', String(slackLookbackDays.value))
    await api.slackReset()
    slackLookbackSaved.value = true
    setTimeout(() => { slackLookbackSaved.value = false }, 1500)
    // Close modal and immediately trigger a poll so data re-fetches from the new window
    emit('close')
    emit('pollNow')
  } finally {
    slackLookbackSaving.value = false
  }
}

watch(() => props.open, (v) => { if (v) load() })

async function save(key: string) {
  saving.value[key] = true
  try {
    await api.updateSetting(key, values.value[key] ?? '')
    saved.value[key] = true
    setTimeout(() => { saved.value[key] = false }, 1500)
  } catch {
    // ignore — user can retry
  } finally {
    saving.value[key] = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

// ── Slack connect ────────────────────────────────────────────────────
const slackToken = ref('')
const slackConnecting = ref(false)
const slackError = ref<string | null>(null)
const slackInfo = ref<string | null>(null)
const showSlackInput = ref(false)

const slackLookbackDays = ref(7)
const slackLookbackSaving = ref(false)
const slackLookbackSaved = ref(false)

async function connectSlack() {
  if (!slackToken.value.trim()) return
  slackConnecting.value = true
  slackError.value = null
  try {
    const r = await api.connectSlack(slackToken.value.trim())
    slackInfo.value = `Connected to ${r.team} as ${r.user}`
    slackToken.value = ''
    showSlackInput.value = false
    emit('slackStatusChanged')
  } catch (e: unknown) {
    slackError.value = e instanceof Error ? e.message : 'Connection failed'
  } finally {
    slackConnecting.value = false
  }
}

async function disconnectSlack() {
  slackConnecting.value = true
  slackError.value = null
  try {
    await api.slackLogout()
    slackInfo.value = null
    emit('slackStatusChanged')
  } catch {
    slackError.value = 'Disconnect failed'
  } finally {
    slackConnecting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-start justify-end"
      @keydown="onKeydown"
    >
      <!-- Backdrop -->
      <div
        class="absolute inset-0 bg-brand-darkest/30 backdrop-blur-sm"
        @click="emit('close')"
        aria-hidden="true"
      />

      <!-- Panel -->
      <aside
        role="dialog"
        aria-label="Settings"
        aria-modal="true"
        class="relative z-10 h-full w-full max-w-sm bg-surface-card shadow-dropdown flex flex-col animate-fade-in-up"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-grey-100">
          <h2 class="text-heading text-grey-900">Settings</h2>
          <button
            @click="emit('close')"
            aria-label="Close settings"
            class="p-1.5 rounded-lg hover:bg-grey-100 text-grey-400 hover:text-grey-700 transition-colors"
          >
            <XMarkIcon class="w-4 h-4" />
          </button>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto px-5 py-5 space-y-6">
          <p v-if="loadError" class="text-caption text-red-600">{{ loadError }}</p>

          <!-- Gmail filter builder -->
          <div class="space-y-4">
            <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Gmail filter</p>

            <!-- Look-back window -->
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <label class="text-body text-grey-800">Look back</label>
                <span class="text-body font-semibold text-brand-primary tabular-nums">{{ filterDays }} days</span>
              </div>
              <input
                type="range"
                v-model.number="filterDays"
                min="1" max="30"
                class="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                style="accent-color: var(--brand-primary)"
                aria-label="Days to look back"
              />
              <div class="flex justify-between text-micro text-grey-400">
                <span>1 day</span><span>30 days</span>
              </div>
            </div>

            <!-- Read status -->
            <div class="space-y-1.5">
              <p class="text-body text-grey-800">Read status</p>
              <div class="flex gap-2">
                <button
                  @click="filterUnreadOnly = true"
                  :class="[
                    'flex-1 py-2 rounded-lg text-caption font-semibold border transition-all',
                    filterUnreadOnly
                      ? 'bg-brand-primary border-brand-primary text-white'
                      : 'border-grey-200 text-grey-500 hover:border-brand-light hover:text-brand-primary',
                  ]"
                >Unread only</button>
                <button
                  @click="filterUnreadOnly = false"
                  :class="[
                    'flex-1 py-2 rounded-lg text-caption font-semibold border transition-all',
                    !filterUnreadOnly
                      ? 'bg-brand-primary border-brand-primary text-white'
                      : 'border-grey-200 text-grey-500 hover:border-brand-light hover:text-brand-primary',
                  ]"
                >All mail</button>
              </div>
            </div>

            <!-- Category exclusions -->
            <div class="space-y-1.5">
              <p class="text-body text-grey-800">Skip categories</p>
              <div class="grid grid-cols-2 gap-2">
                <button
                  v-for="cat in CATEGORIES"
                  :key="cat.key"
                  @click="toggleCategory(cat.key)"
                  :class="[
                    'flex items-center gap-2.5 px-3 py-2.5 rounded-lg border text-left transition-all',
                    filterExcluded.has(cat.key)
                      ? 'bg-brand-50 border-brand-light text-brand-darkest'
                      : 'border-grey-200 text-grey-500 hover:border-grey-300',
                  ]"
                  :aria-pressed="filterExcluded.has(cat.key)"
                >
                  <span
                    :class="[
                      'w-4 h-4 rounded flex items-center justify-center shrink-0 transition-colors',
                      filterExcluded.has(cat.key) ? 'bg-brand-primary' : 'border border-grey-300',
                    ]"
                  >
                    <CheckIcon v-if="filterExcluded.has(cat.key)" class="w-3 h-3 text-white" />
                  </span>
                  <span class="text-caption font-semibold">{{ cat.label }}</span>
                </button>
              </div>
              <p class="text-caption text-grey-400">Checked categories are excluded from scanning.</p>
            </div>

            <!-- Query preview -->
            <div class="bg-surface-sunk rounded-lg px-3 py-2.5 space-y-1">
              <p class="text-micro font-bold text-grey-400 uppercase tracking-wide">Query preview</p>
              <code class="text-caption text-grey-700 font-mono break-all">{{ builtQuery }}</code>
            </div>

            <!-- Save -->
            <button
              @click="saveFilter"
              :disabled="filterSaving"
              :class="[
                'w-full py-2 rounded-lg text-caption font-semibold transition-colors',
                filterSaved
                  ? 'bg-status-replied text-white'
                  : 'bg-brand-primary hover:bg-brand-dark text-white disabled:opacity-50',
              ]"
            >
              {{ filterSaved ? 'Saved ✓' : filterSaving ? 'Saving…' : 'Save filter' }}
            </button>
          </div>

          <!-- Divider -->
          <div class="border-t border-grey-100" />

          <!-- Other settings -->
          <div class="space-y-5">
            <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Timing &amp; reminders</p>
            <div v-for="field in FIELDS" :key="field.key" class="space-y-1.5">
              <label :for="field.key" class="block text-body text-grey-800">
                {{ field.label }}
              </label>
              <div class="flex gap-2">
                <input
                  :id="field.key"
                  v-model="values[field.key]"
                  :type="field.type"
                  :min="field.min"
                  :max="field.max"
                  class="flex-1 text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary focus:shadow-focus-brand transition-shadow"
                  @keydown.enter="save(field.key)"
                />
                <button
                  @click="save(field.key)"
                  :disabled="saving[field.key]"
                  :class="[
                    'px-3 py-1.5 text-caption font-semibold rounded-lg transition-colors',
                    saved[field.key]
                      ? 'bg-status-replied text-white'
                      : 'bg-brand-primary text-white hover:bg-brand-dark disabled:opacity-50',
                  ]"
                  :aria-label="`Save ${field.label}`"
                >
                  {{ saved[field.key] ? '✓' : saving[field.key] ? '…' : 'Save' }}
                </button>
              </div>
              <p class="text-caption text-grey-400">{{ field.hint }}</p>
            </div>
          </div>

          <!-- Divider -->
          <div class="border-t border-grey-100" />

          <!-- Priority senders (VIPs) -->
          <PrioritySendersSection />

          <!-- Slack integration -->
          <div class="border-t border-grey-100 pt-2 space-y-3">
            <div class="flex items-center justify-between">
              <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Slack</p>
              <span
                :class="[
                  'text-micro font-semibold px-2 py-0.5 rounded-pill',
                  slackConnected ? 'bg-green-50 text-green-700 ring-1 ring-inset ring-green-200' : 'bg-grey-100 text-grey-500',
                ]"
              >{{ slackConnected ? 'Connected' : 'Not connected' }}</span>
            </div>

            <p v-if="slackInfo" class="text-caption text-green-700 bg-green-50 rounded-lg px-3 py-2">{{ slackInfo }}</p>
            <p v-if="slackError" class="text-caption text-red-600 bg-red-50 rounded-lg px-3 py-2">{{ slackError }}</p>

            <template v-if="!slackConnected">
              <div class="text-caption text-grey-400 space-y-1.5">
                <p>Connect a Slack <strong class="text-grey-600">User OAuth Token</strong> (xoxp-…) to pull DMs into your task list.</p>
                <ol class="list-decimal list-inside space-y-1 text-grey-500">
                  <li><a href="https://api.slack.com/apps" target="_blank" rel="noopener" class="text-brand-primary hover:underline">Open your Slack app</a> → OAuth &amp; Permissions</li>
                  <li>Under <strong class="text-grey-600">User Token Scopes</strong> (not Bot Scopes, not App-Level Tokens), add:<br>
                    <code class="bg-grey-100 px-1 rounded font-mono text-micro">im:history  im:read  mpim:history  mpim:read  users:read  search:read</code>
                  </li>
                  <li>Scroll to the top of that same page → click <strong class="text-grey-600">Install to Workspace</strong> (or Reinstall if already installed) → Allow</li>
                  <li>Copy the <strong class="text-grey-600">User OAuth Token</strong> that appears on that page</li>
                </ol>
              </div>
              <div v-if="!showSlackInput">
                <button
                  @click="showSlackInput = true"
                  class="w-full py-2 rounded-lg text-caption font-semibold bg-[#4a154b] hover:bg-[#611f69] text-white transition-colors"
                >
                  Connect Slack
                </button>
              </div>
              <div v-else class="space-y-2">
                <input
                  v-model="slackToken"
                  type="password"
                  placeholder="User OAuth Token — xoxp-…"
                  class="w-full text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary transition-shadow font-mono text-caption"
                  @keydown.enter="connectSlack"
                />
                <div class="flex gap-2">
                  <button
                    @click="connectSlack"
                    :disabled="slackConnecting || !slackToken.trim()"
                    class="flex-1 py-1.5 rounded-lg text-caption font-semibold bg-[#4a154b] hover:bg-[#611f69] text-white disabled:opacity-50 transition-colors"
                  >{{ slackConnecting ? 'Connecting…' : 'Connect' }}</button>
                  <button
                    @click="showSlackInput = false; slackToken = ''; slackError = null"
                    class="flex-1 py-1.5 rounded-lg text-caption font-semibold bg-grey-100 hover:bg-grey-200 text-grey-700 transition-colors"
                  >Cancel</button>
                </div>
              </div>
            </template>

            <template v-else>
              <!-- Lookback window -->
              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <label class="text-body text-grey-800">Look back</label>
                  <span class="text-body font-semibold text-brand-primary tabular-nums">{{ slackLookbackDays }} days</span>
                </div>
                <input
                  type="range"
                  v-model.number="slackLookbackDays"
                  min="1" max="30"
                  class="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                  style="accent-color: var(--brand-primary)"
                  aria-label="Slack look-back days"
                />
                <div class="flex justify-between text-micro text-grey-400">
                  <span>1 day</span><span>30 days</span>
                </div>
                <p class="text-caption text-grey-400">How far back to search on the first poll (DMs and mentions).</p>
                <button
                  @click="saveSlackLookback"
                  :disabled="slackLookbackSaving"
                  :class="[
                    'w-full py-2 rounded-lg text-caption font-semibold transition-colors',
                    slackLookbackSaved
                      ? 'bg-status-replied text-white'
                      : 'bg-brand-primary hover:bg-brand-dark text-white disabled:opacity-50',
                  ]"
                >{{ slackLookbackSaved ? 'Saved ✓' : slackLookbackSaving ? 'Saving…' : 'Save' }}</button>
              </div>

              <div class="border-t border-grey-100" />

              <button
                @click="disconnectSlack"
                :disabled="slackConnecting"
                class="w-full py-2 rounded-lg text-caption font-semibold bg-grey-100 hover:bg-red-50 text-red-600 disabled:opacity-50 transition-colors"
              >{{ slackConnecting ? 'Disconnecting…' : 'Disconnect Slack' }}</button>
            </template>
          </div>

          <!-- Re-auth -->
          <div class="border-t border-grey-100 pt-2 space-y-1.5">
            <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Re-authenticate Gmail</p>
            <p class="text-caption text-grey-400">
              Run <code class="bg-grey-100 px-1.5 py-0.5 rounded font-mono text-micro">todo-mail reauth</code>
              in your terminal to reset your Google OAuth credentials.
            </p>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
