<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { X as XMarkIcon, Check as CheckIcon } from 'lucide-vue-next'
import { api } from '../api'
import PrioritySendersSection from './PrioritySendersSection.vue'
import { THEMES, applyTheme, getActiveThemeId } from '../themes'

const props = defineProps<{ open: boolean; slackConnected?: boolean }>()
const emit = defineEmits<{ close: []; slackStatusChanged: []; pollNow: []; reauth: [] }>()

interface Field {
  key: string
  label: string
  hint: string
  type: 'number' | 'text'
  min?: number
  max?: number
}

const GENERAL_FIELDS: Field[] = [
  { key: 'user_name', label: 'Display name', hint: 'Your name as it appears in AI-drafted reply sign-offs. Leave blank to derive from your email.', type: 'text' },
]

const TIMING_FIELDS: Field[] = [
  { key: 'reply_by_days',          label: 'Default reply window (days)',         hint: 'Days added to received date when no deadline is found.',            type: 'number', min: 1,  max: 30 },
  { key: 'reply_by_hour',          label: 'Default reply hour (0–23)',            hint: 'Hour of day for the default reply-by deadline.',                   type: 'number', min: 0,  max: 23 },
  { key: 'poll_interval_minutes',  label: 'Poll interval (minutes)',              hint: 'How often to automatically check Gmail for new messages.',          type: 'number', min: 1,  max: 60 },
  { key: 'reminder_offsets_hours', label: 'Reminder offsets (hours, comma-sep)', hint: 'Hours before deadline to fire desktop notifications. E.g. 24,1,0.', type: 'text' },
]

// ── Tabs ─────────────────────────────────────────────────────────────
type TabId = 'general' | 'ai' | 'gmail' | 'integrations'

const TABS: { id: TabId; label: string }[] = [
  { id: 'general',      label: 'General'      },
  { id: 'ai',           label: 'AI'           },
  { id: 'gmail',        label: 'Gmail'        },
  { id: 'integrations', label: 'Integrations' },
]

const activeTab = ref<TabId>('general')

const values = ref<Record<string, string>>({})
const loadError = ref<string | null>(null)

// ── General save ─────────────────────────────────────────────────────
const generalSaving = ref(false)
const generalSaved  = ref(false)

async function saveGeneral() {
  generalSaving.value = true
  try {
    await Promise.all(GENERAL_FIELDS.map(f => api.updateSetting(f.key, values.value[f.key] ?? '')))
    generalSaved.value = true
    setTimeout(() => { generalSaved.value = false }, 1500)
  } catch { /* ignore */ }
  finally { generalSaving.value = false }
}

// ── Timing save ──────────────────────────────────────────────────────
const timingSaving = ref(false)
const timingSaved  = ref(false)

async function saveAllTiming() {
  timingSaving.value = true
  try {
    await Promise.all(TIMING_FIELDS.map(f => api.updateSetting(f.key, values.value[f.key] ?? '')))
    timingSaved.value = true
    setTimeout(() => { timingSaved.value = false }, 1500)
  } catch { /* ignore */ }
  finally { timingSaving.value = false }
}

// ── Gmail filter builder ─────────────────────────────────────────────
const CATEGORIES = [
  { key: 'promotions', label: 'Promotions' },
  { key: 'social',     label: 'Social'     },
  { key: 'updates',    label: 'Updates'    },
  { key: 'forums',     label: 'Forums'     },
]

const DEFAULT_QUERY = 'in:inbox is:unread -category:promotions -category:social newer_than:7d'

const filterDays       = ref(7)
const filterUnreadOnly = ref(true)
const filterExcluded   = ref<Set<string>>(new Set(['promotions', 'social']))
const filterSaving     = ref(false)
const filterSaved      = ref(false)

// The textarea-editable query string. Always the source of truth on save.
const gmailQuery = ref(DEFAULT_QUERY)

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

// Build a query string from the builder controls (used when the user clicks them).
function buildQueryFromControls(): string {
  const parts: string[] = ['in:inbox']
  if (filterUnreadOnly.value) parts.push('is:unread')
  for (const cat of CATEGORIES) {
    if (filterExcluded.value.has(cat.key)) parts.push(`-category:${cat.key}`)
  }
  parts.push(`newer_than:${filterDays.value}d`)
  return parts.join(' ')
}

// Builder controls write into the textarea. The textarea is always the saved value.
function applyBuilder() {
  gmailQuery.value = buildQueryFromControls()
}

function toggleCategory(key: string) {
  const next = new Set(filterExcluded.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  filterExcluded.value = next
  applyBuilder()
}

function resetQueryToDefault() {
  gmailQuery.value = DEFAULT_QUERY
  parseQuery(DEFAULT_QUERY)
}

async function saveFilter() {
  filterSaving.value = true
  try {
    await api.updateSetting('gmail_query', gmailQuery.value.trim())
    filterSaved.value = true
    setTimeout(() => { filterSaved.value = false }, 1500)
  } finally {
    filterSaving.value = false
  }
}

// Keep the textarea in sync when builder sliders/toggles change
watch([filterDays, filterUnreadOnly], applyBuilder)
// ── /Gmail filter builder ────────────────────────────────────────────

async function load() {
  try {
    values.value = await api.getSettings()
    const stored = values.value['gmail_query'] ?? DEFAULT_QUERY
    parseQuery(stored)
    gmailQuery.value = stored
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
    emit('close')
    emit('pollNow')
  } finally {
    slackLookbackSaving.value = false
  }
}

watch(() => props.open, async (v) => {
  if (v) {
    await load()
    syncModelChoiceFromValue()
    loadLlmKeyStatus()
  }
})

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

// ── AI provider ──────────────────────────────────────────────────────
interface ProviderMeta {
  label: string
  placeholder: string
  hint: string
  defaultModel: string
  models: string[]   // curated suggestions; user can still type a custom one
}

const PROVIDER_META: Record<string, ProviderMeta> = {
  groq: {
    label: 'Groq',
    placeholder: 'gsk_…',
    hint: 'Get a free key at console.groq.com/keys. Stored locally in your OS keychain.',
    defaultModel: 'llama-3.3-70b-versatile',
    models: [
      'llama-3.3-70b-versatile',
      'llama-3.1-8b-instant',
      'llama-3.1-70b-versatile',
      'mixtral-8x7b-32768',
      'gemma2-9b-it',
    ],
  },
  openai: {
    label: 'OpenAI',
    placeholder: 'sk-…',
    hint: 'Get a key at platform.openai.com/api-keys. Stored locally in your OS keychain.',
    defaultModel: 'gpt-4o',
    models: [
      'gpt-4o',
      'gpt-4o-mini',
      'gpt-4-turbo',
      'o3-mini',
      'gpt-3.5-turbo',
    ],
  },
  anthropic: {
    label: 'Anthropic (Claude)',
    placeholder: 'sk-ant-…',
    hint: 'Get a key at console.anthropic.com. Stored locally in your OS keychain.',
    defaultModel: 'claude-sonnet-4-6',
    models: [
      'claude-opus-4-7',
      'claude-sonnet-4-6',
      'claude-haiku-4-5',
      'claude-3-5-sonnet-latest',
      'claude-3-5-haiku-latest',
    ],
  },
  local: {
    label: 'Local (Ollama / compatible)',
    placeholder: '',
    hint: 'Connects to a local OpenAI-compatible endpoint. No API key required.',
    defaultModel: 'llama3',
    models: [
      'llama3',
      'llama3.1',
      'llama3.2',
      'mistral',
      'phi3',
      'qwen2',
      'gemma2',
    ],
  },
}

const llmHasKey    = ref(false)
const llmKeyInput  = ref('')
const llmKeySaving = ref(false)
const llmKeySaved  = ref(false)
const llmKeyError  = ref<string | null>(null)
const showLlmKeyInput = ref(false)

const providerSaving = ref(false)
const providerSaved  = ref(false)

const currentProvider = computed(() => (values.value['llm_provider'] || 'groq') as string)
const providerMeta    = computed(() => PROVIDER_META[currentProvider.value] ?? PROVIDER_META['groq'])
const modelPlaceholder = computed(() => providerMeta.value.defaultModel)

// Model picker state: a dropdown (modelChoice) plus a free-form input that
// only appears when the user selects "Other". We keep llm_model in sync with
// whichever is active so the save endpoint sees a single value.
//   modelChoice = ''         → use the provider default (llm_model is blank)
//   modelChoice = '<known>'  → llm_model = <known>
//   modelChoice = '__other__'→ llm_model = customModel
const MODEL_OTHER = '__other__'
const modelChoice = ref<string>('')
const customModel = ref<string>('')

function syncModelChoiceFromValue() {
  const m = (values.value['llm_model'] || '').trim()
  if (!m) {
    modelChoice.value = ''
    customModel.value = ''
  } else if (providerMeta.value.models.includes(m)) {
    modelChoice.value = m
    customModel.value = ''
  } else {
    modelChoice.value = MODEL_OTHER
    customModel.value = m
  }
}

function onModelChoiceChange() {
  if (modelChoice.value === MODEL_OTHER) {
    values.value['llm_model'] = customModel.value.trim()
  } else {
    values.value['llm_model'] = modelChoice.value
  }
}

watch(customModel, (v) => {
  if (modelChoice.value === MODEL_OTHER) {
    values.value['llm_model'] = v.trim()
  }
})

async function loadLlmKeyStatus() {
  if (currentProvider.value === 'local') { llmHasKey.value = true; return }
  try {
    const r = await api.getLlmKeyStatus(currentProvider.value)
    llmHasKey.value = r.has_key
  } catch { /* ignore */ }
}

async function saveLlmKey() {
  const key = llmKeyInput.value.trim()
  if (!key) return
  llmKeySaving.value = true
  llmKeyError.value = null
  try {
    await api.setLlmKey(currentProvider.value, key)
    llmHasKey.value = true
    llmKeyInput.value = ''
    showLlmKeyInput.value = false
    llmKeySaved.value = true
    setTimeout(() => { llmKeySaved.value = false }, 1800)
  } catch (e: unknown) {
    llmKeyError.value = e instanceof Error ? e.message : 'Could not save key'
  } finally {
    llmKeySaving.value = false
  }
}

async function saveProviderSettings() {
  providerSaving.value = true
  try {
    await Promise.all([
      api.updateSetting('llm_provider', values.value['llm_provider'] ?? 'groq'),
      api.updateSetting('llm_model',    values.value['llm_model']    ?? ''),
      api.updateSetting('llm_base_url', values.value['llm_base_url'] ?? ''),
    ])
    providerSaved.value = true
    setTimeout(() => { providerSaved.value = false }, 1500)
    await loadLlmKeyStatus()
  } finally {
    providerSaving.value = false
  }
}

watch(currentProvider, () => {
  // Provider changed — old model probably doesn't exist for the new one.
  // Reset to the default to avoid surprising the user.
  modelChoice.value = ''
  customModel.value = ''
  values.value['llm_model'] = ''
  loadLlmKeyStatus()
})

// ── Appearance ───────────────────────────────────────────────────────
const activeThemeId = ref(getActiveThemeId())

function selectTheme(id: string) {
  activeThemeId.value = id
  applyTheme(id)
  localStorage.setItem('app_theme', id)
  api.updateSetting('app_theme', id).catch(() => { /* ignore */ })
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
        class="absolute inset-0 backdrop-blur-sm"
        style="background-color: var(--brand-backdrop)"
        @click="emit('close')"
        aria-hidden="true"
      />

      <!-- Panel -->
      <aside
        role="dialog"
        aria-label="Settings"
        aria-modal="true"
        class="relative z-10 h-full w-full max-w-md bg-surface-card shadow-dropdown flex flex-col animate-fade-in-up"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-grey-100 shrink-0">
          <h2 class="text-heading text-grey-900">Settings</h2>
          <button
            @click="emit('close')"
            aria-label="Close settings"
            class="p-1.5 rounded-lg hover:bg-grey-100 text-grey-400 hover:text-grey-700 transition-colors"
          >
            <XMarkIcon class="w-4 h-4" />
          </button>
        </div>

        <!-- Tab bar -->
        <div class="flex shrink-0 border-b border-grey-100" role="tablist" aria-label="Settings sections">
          <button
            v-for="tab in TABS"
            :key="tab.id"
            role="tab"
            :aria-selected="activeTab === tab.id"
            :aria-controls="`tab-panel-${tab.id}`"
            @click="activeTab = tab.id"
            class="relative flex-1 py-2.5 text-caption font-semibold transition-colors"
            :class="activeTab === tab.id ? 'text-brand-primary' : 'text-grey-500 hover:text-grey-700'"
          >
            <!-- Active indicator dot for AI tab when key not configured -->
            <span v-if="tab.id === 'ai' && !llmHasKey && currentProvider !== 'local'" class="absolute top-2 right-3 w-1.5 h-1.5 rounded-full bg-amber-400" />
            {{ tab.label }}
            <span
              v-if="activeTab === tab.id"
              class="absolute bottom-0 inset-x-0 h-0.5 bg-brand-primary rounded-t-sm"
            />
          </button>
        </div>

        <!-- Tab content -->
        <div
          :id="`tab-panel-${activeTab}`"
          role="tabpanel"
          class="flex-1 overflow-y-auto px-5 py-5 space-y-6"
        >
          <p v-if="loadError" class="text-caption text-red-600">{{ loadError }}</p>

          <!-- ── General tab ─────────────────────────────────────── -->
          <template v-if="activeTab === 'general'">

            <!-- Profile -->
            <div class="space-y-4">
              <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Profile</p>
              <div v-for="field in GENERAL_FIELDS" :key="field.key" class="space-y-1.5">
                <label :for="field.key" class="block text-body text-grey-800">{{ field.label }}</label>
                <input
                  :id="field.key"
                  v-model="values[field.key]"
                  :type="field.type"
                  class="w-full text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary focus:shadow-focus-brand transition-shadow"
                  @keydown.enter="saveGeneral"
                />
                <p class="text-caption text-grey-400">{{ field.hint }}</p>
              </div>
              <button
                @click="saveGeneral"
                :disabled="generalSaving"
                :class="[
                  'w-full py-2 rounded-lg text-caption font-semibold transition-colors',
                  generalSaved
                    ? 'bg-status-replied text-white'
                    : 'bg-brand-primary hover:bg-brand-dark text-white disabled:opacity-50',
                ]"
              >{{ generalSaved ? 'Saved ✓' : generalSaving ? 'Saving…' : 'Save' }}</button>
            </div>

            <div class="border-t border-grey-100" />

            <!-- Timing & reminders -->
            <div class="space-y-4">
              <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Timing &amp; reminders</p>
              <div v-for="field in TIMING_FIELDS" :key="field.key" class="space-y-1.5">
                <label :for="field.key" class="block text-body text-grey-800">{{ field.label }}</label>
                <input
                  :id="field.key"
                  v-model="values[field.key]"
                  :type="field.type"
                  :min="field.min"
                  :max="field.max"
                  class="w-full text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary focus:shadow-focus-brand transition-shadow"
                  @keydown.enter="saveAllTiming"
                />
                <p class="text-caption text-grey-400">{{ field.hint }}</p>
              </div>
              <button
                @click="saveAllTiming"
                :disabled="timingSaving"
                :class="[
                  'w-full py-2 rounded-lg text-caption font-semibold transition-colors',
                  timingSaved
                    ? 'bg-status-replied text-white'
                    : 'bg-brand-primary hover:bg-brand-dark text-white disabled:opacity-50',
                ]"
              >{{ timingSaved ? 'Saved ✓' : timingSaving ? 'Saving…' : 'Save' }}</button>
            </div>

            <div class="border-t border-grey-100" />

            <!-- Appearance -->
            <div class="space-y-3">
              <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Appearance</p>
              <div class="grid grid-cols-5 gap-2">
                <button
                  v-for="theme in THEMES"
                  :key="theme.id"
                  @click="selectTheme(theme.id)"
                  :title="theme.name"
                  :aria-pressed="activeThemeId === theme.id"
                  :aria-label="`${theme.name} theme`"
                  class="flex flex-col items-center gap-1.5 p-2 rounded-lg border-2 transition-all"
                  :class="activeThemeId === theme.id ? 'border-brand-primary bg-brand-50' : 'border-grey-200 hover:border-grey-300'"
                >
                  <span
                    class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                    :style="{ backgroundColor: theme.swatch }"
                  >
                    <CheckIcon v-if="activeThemeId === theme.id" class="w-4 h-4 text-white" />
                  </span>
                  <span class="text-micro font-semibold text-grey-700 leading-tight text-center">{{ theme.name }}</span>
                </button>
              </div>
            </div>

            <div class="border-t border-grey-100" />

            <!-- Account -->
            <div class="space-y-3 pb-2">
              <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Account</p>
              <p class="text-caption text-grey-400">
                Re-authenticate if your Gmail session has expired or you want to switch accounts.
              </p>
              <button
                @click="emit('reauth')"
                class="w-full py-2 rounded-lg text-caption font-semibold bg-grey-100 hover:bg-grey-200 text-grey-700 transition-colors"
              >
                Re-authenticate Gmail
              </button>
            </div>

          </template>

          <!-- ── AI tab ──────────────────────────────────────────── -->
          <template v-else-if="activeTab === 'ai'">

            <div class="space-y-4">
              <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">AI provider</p>

              <!-- Provider selector -->
              <div class="space-y-1.5">
                <label class="block text-body text-grey-800">Provider</label>
                <select
                  v-model="values['llm_provider']"
                  class="w-full text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary bg-white transition-shadow"
                >
                  <option v-for="(meta, key) in PROVIDER_META" :key="key" :value="key">{{ meta.label }}</option>
                </select>
              </div>

              <!-- Model -->
              <div class="space-y-1.5">
                <label class="block text-body text-grey-800">Model</label>
                <select
                  v-model="modelChoice"
                  @change="onModelChoiceChange"
                  class="w-full text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary bg-white transition-shadow"
                >
                  <option value="">Default ({{ providerMeta.defaultModel }})</option>
                  <option v-for="m in providerMeta.models" :key="m" :value="m">{{ m }}</option>
                  <option :value="MODEL_OTHER">Other (custom)…</option>
                </select>

                <input
                  v-if="modelChoice === MODEL_OTHER"
                  v-model="customModel"
                  type="text"
                  placeholder="Enter custom model ID"
                  autocomplete="off"
                  class="w-full text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary transition-shadow font-mono text-caption"
                  @keydown.enter="saveProviderSettings"
                />

                <p class="text-caption text-grey-400">
                  Pick from {{ providerMeta.models.length }} known models, or choose
                  <em>Other</em> to type any model ID the provider supports.
                </p>
              </div>

              <!-- Base URL (local only) -->
              <div v-if="values['llm_provider'] === 'local'" class="space-y-1.5">
                <label class="block text-body text-grey-800">Base URL</label>
                <input
                  v-model="values['llm_base_url']"
                  type="text"
                  placeholder="http://localhost:11434/v1"
                  class="w-full text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary transition-shadow font-mono text-caption"
                  @keydown.enter="saveProviderSettings"
                />
                <p class="text-caption text-grey-400">OpenAI-compatible endpoint URL (e.g. Ollama).</p>
              </div>

              <button
                @click="saveProviderSettings"
                :disabled="providerSaving"
                :class="[
                  'w-full py-2 rounded-lg text-caption font-semibold transition-colors',
                  providerSaved
                    ? 'bg-status-replied text-white'
                    : 'bg-brand-primary hover:bg-brand-dark text-white disabled:opacity-50',
                ]"
              >{{ providerSaved ? 'Saved ✓' : providerSaving ? 'Saving…' : 'Save provider settings' }}</button>

              <!-- API key (not needed for local) -->
              <template v-if="values['llm_provider'] !== 'local'">
                <div class="border-t border-grey-100 pt-3 space-y-3">
                  <div class="flex items-center justify-between">
                    <p class="text-body text-grey-800 font-medium">API key</p>
                    <span
                      :class="[
                        'text-micro font-semibold px-2 py-0.5 rounded-pill',
                        llmHasKey
                          ? 'bg-green-50 text-green-700 ring-1 ring-inset ring-green-200'
                          : 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200',
                      ]"
                    >{{ llmHasKey ? 'Configured' : 'Not set' }}</span>
                  </div>

                  <p v-if="llmKeySaved" class="text-caption text-green-700 bg-green-50 rounded-lg px-3 py-2">API key saved.</p>
                  <p v-if="llmKeyError" class="text-caption text-red-600 bg-red-50 rounded-lg px-3 py-2">{{ llmKeyError }}</p>

                  <div v-if="!showLlmKeyInput">
                    <p class="text-caption text-grey-400 mb-2">{{ providerMeta.hint }}</p>
                    <button
                      @click="showLlmKeyInput = true; llmKeyError = null"
                      class="w-full py-2 rounded-lg text-caption font-semibold bg-brand-primary hover:bg-brand-dark text-white transition-colors"
                    >{{ llmHasKey ? 'Update key' : 'Set API key' }}</button>
                  </div>
                  <div v-else class="space-y-2">
                    <p class="text-caption text-grey-400">{{ providerMeta.hint }}</p>
                    <input
                      v-model="llmKeyInput"
                      type="password"
                      :placeholder="providerMeta.placeholder"
                      class="w-full text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-primary transition-shadow font-mono text-caption"
                      @keydown.enter="saveLlmKey"
                      autocomplete="off"
                    />
                    <div class="flex gap-2">
                      <button
                        @click="saveLlmKey"
                        :disabled="llmKeySaving || !llmKeyInput.trim()"
                        class="flex-1 py-1.5 rounded-lg text-caption font-semibold bg-brand-primary hover:bg-brand-dark text-white disabled:opacity-50 transition-colors"
                      >{{ llmKeySaving ? 'Saving…' : 'Save' }}</button>
                      <button
                        @click="showLlmKeyInput = false; llmKeyInput = ''; llmKeyError = null"
                        class="flex-1 py-1.5 rounded-lg text-caption font-semibold bg-grey-100 hover:bg-grey-200 text-grey-700 transition-colors"
                      >Cancel</button>
                    </div>
                  </div>
                </div>
              </template>
            </div>

          </template>

          <!-- ── Gmail tab ───────────────────────────────────────── -->
          <template v-else-if="activeTab === 'gmail'">

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
                <p class="text-body text-grey-800">Exclude categories</p>
                <div class="grid grid-cols-2 gap-2">
                  <button
                    v-for="cat in CATEGORIES"
                    :key="cat.key"
                    @click="toggleCategory(cat.key)"
                    :class="[
                      'flex items-center gap-2.5 px-3 py-2.5 rounded-lg border text-left transition-all',
                      filterExcluded.has(cat.key)
                        ? 'bg-red-50 border-red-200 text-red-700'
                        : 'border-grey-200 text-grey-500 hover:border-grey-300',
                    ]"
                    :aria-pressed="filterExcluded.has(cat.key)"
                  >
                    <span
                      :class="[
                        'w-4 h-4 rounded flex items-center justify-center shrink-0 transition-colors',
                        filterExcluded.has(cat.key) ? 'bg-red-400' : 'border border-grey-300',
                      ]"
                    >
                      <XMarkIcon v-if="filterExcluded.has(cat.key)" class="w-3 h-3 text-white" />
                    </span>
                    <span class="text-caption font-semibold">{{ cat.label }}</span>
                  </button>
                </div>
                <p class="text-caption text-grey-400">Marked categories are excluded from scanning.</p>
              </div>

              <!-- Query preview collapsed -->
              <details class="group">
                <summary class="cursor-pointer text-caption text-grey-400 hover:text-grey-600 transition-colors select-none list-none flex items-center gap-1.5">
                  <span class="transition-transform duration-150 group-open:rotate-90 inline-block text-micro">▶</span>
                  Advanced: edit Gmail query
                </summary>
                <div class="mt-2 space-y-2">
                  <div class="flex items-center justify-between">
                    <p class="text-micro font-bold text-grey-400 uppercase tracking-wide">Raw query</p>
                    <button
                      type="button"
                      @click="resetQueryToDefault"
                      class="text-micro text-grey-400 hover:text-brand-primary transition-colors"
                    >Reset to default</button>
                  </div>
                  <textarea
                    v-model="gmailQuery"
                    rows="3"
                    spellcheck="false"
                    class="w-full text-caption text-grey-700 font-mono bg-surface-sunk border border-grey-200 rounded-lg px-3 py-2 focus:outline-none focus:border-brand-primary transition-shadow resize-y"
                    placeholder="in:inbox is:unread newer_than:7d"
                  />
                  <p class="text-micro text-grey-400">
                    Any valid Gmail search operator works here — e.g. <code class="font-mono text-grey-500">from:boss@…</code>,
                    <code class="font-mono text-grey-500">label:urgent</code>,
                    <code class="font-mono text-grey-500">has:attachment</code>.
                    Editing this overrides the toggles above; clicking a toggle rewrites this field.
                  </p>
                </div>
              </details>

              <button
                @click="saveFilter"
                :disabled="filterSaving"
                :class="[
                  'w-full py-2 rounded-lg text-caption font-semibold transition-colors',
                  filterSaved
                    ? 'bg-status-replied text-white'
                    : 'bg-brand-primary hover:bg-brand-dark text-white disabled:opacity-50',
                ]"
              >{{ filterSaved ? 'Saved ✓' : filterSaving ? 'Saving…' : 'Save filter' }}</button>
            </div>

            <div class="border-t border-grey-100" />

            <!-- Priority senders (VIPs) -->
            <PrioritySendersSection />

          </template>

          <!-- ── Integrations tab ────────────────────────────────── -->
          <template v-else-if="activeTab === 'integrations'">

            <!-- Slack integration -->
            <div class="space-y-3">
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
                <details class="group">
                  <summary class="cursor-pointer text-caption text-grey-500 hover:text-grey-700 transition-colors select-none list-none flex items-center gap-1.5">
                    <span class="transition-transform duration-150 group-open:rotate-90 inline-block text-micro">▶</span>
                    How to get a Slack token
                  </summary>
                  <div class="mt-2 text-caption text-grey-400 space-y-1.5 bg-surface-sunk rounded-lg px-3 py-3">
                    <p>Connect a Slack <strong class="text-grey-600">User OAuth Token</strong> (xoxp-…) to pull DMs into your task list.</p>
                    <ol class="list-decimal list-inside space-y-1 text-grey-500">
                      <li><a href="https://api.slack.com/apps" target="_blank" rel="noopener" class="text-brand-primary hover:underline">Open your Slack app</a> → OAuth &amp; Permissions</li>
                      <li>Under <strong class="text-grey-600">User Token Scopes</strong> (not Bot Scopes), add:<br>
                        <code class="bg-grey-100 px-1 rounded font-mono text-micro">im:history  im:read  mpim:history  mpim:read  users:read  search:read</code>
                      </li>
                      <li>Scroll to the top → click <strong class="text-grey-600">Install to Workspace</strong> → Allow</li>
                      <li>Copy the <strong class="text-grey-600">User OAuth Token</strong> that appears</li>
                    </ol>
                  </div>
                </details>
                <div v-if="!showSlackInput">
                  <button
                    @click="showSlackInput = true"
                    class="w-full py-2 rounded-lg text-caption font-semibold bg-[#4a154b] hover:bg-[#611f69] text-white transition-colors"
                  >Connect Slack</button>
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

          </template>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
