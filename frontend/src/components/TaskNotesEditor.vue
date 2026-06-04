<script setup lang="ts">
import { ref, watch, computed, onBeforeUnmount } from 'vue'
import { Eye, Pencil } from 'lucide-vue-next'
import { marked } from 'marked'

// Render markdown links with safe target/rel attributes.
const _renderer = new marked.Renderer()
const _renderLink = _renderer.link.bind(_renderer)
_renderer.link = (...args: Parameters<typeof _renderer.link>) => {
  const html = _renderLink(...args)
  return html.replace(/^<a /, '<a target="_blank" rel="noopener noreferrer" ')
}
marked.use({ renderer: _renderer })

const props = defineProps<{ taskId: number; modelValue: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [v: string]; save: [v: string] }>()

const NOTES_MAX_CHARS = 50_000
const SAVE_DEBOUNCE_MS = 1000

const draft = ref(props.modelValue ?? '')
const showPreview = ref(false)
const saveState = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

let saveTimer: ReturnType<typeof setTimeout> | null = null
let savedFlashTimer: ReturnType<typeof setTimeout> | null = null

// Sync from props when the task changes externally (e.g. after fetchTasks)
watch(() => props.taskId, () => {
  draft.value = props.modelValue ?? ''
  saveState.value = 'idle'
})

watch(() => props.modelValue, v => {
  if (saveState.value === 'idle') draft.value = v ?? ''
})

function flushSave() {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
  emit('save', draft.value)
}

function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveState.value = 'saving'
  saveTimer = setTimeout(() => {
    saveTimer = null
    emit('save', draft.value)
  }, SAVE_DEBOUNCE_MS)
}

function onInput(e: Event) {
  const v = (e.target as HTMLTextAreaElement).value
  if (v.length > NOTES_MAX_CHARS) {
    draft.value = v.slice(0, NOTES_MAX_CHARS)
  } else {
    draft.value = v
  }
  emit('update:modelValue', draft.value)
  scheduleSave()
}

function onBlur() {
  if (saveTimer) flushSave()
}

// Parent can call markSaved()/markError() via expose
defineExpose({
  markSaved() {
    saveState.value = 'saved'
    if (savedFlashTimer) clearTimeout(savedFlashTimer)
    savedFlashTimer = setTimeout(() => { saveState.value = 'idle' }, 1500)
  },
  markError() {
    saveState.value = 'error'
  },
})

const charCount = computed(() => draft.value.length)
const charCountVisible = computed(() => charCount.value > NOTES_MAX_CHARS * 0.8)

const renderedHtml = computed(() => {
  if (!draft.value.trim()) return ''
  try {
    return marked.parse(draft.value, { breaks: true, gfm: true }) as string
  } catch {
    return ''
  }
})

const stateLabel = computed(() => ({
  idle:   '',
  saving: 'Saving…',
  saved:  'Saved',
  error:  'Save failed',
}[saveState.value]))

const stateClass = computed(() => ({
  idle:   '',
  saving: 'text-grey-400',
  saved:  'text-status-replied',
  error:  'text-red-500',
}[saveState.value]))

onBeforeUnmount(() => {
  if (saveTimer) flushSave()
  if (savedFlashTimer) clearTimeout(savedFlashTimer)
})
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-1.5">
      <span class="text-micro font-extrabold uppercase tracking-widest text-grey-500">Your notes</span>
      <div class="flex items-center gap-2">
        <span :class="['text-micro tabular-nums', stateClass]">{{ stateLabel }}</span>
        <span
          v-if="charCountVisible"
          :class="['text-micro tabular-nums', charCount >= NOTES_MAX_CHARS ? 'text-red-500 font-semibold' : 'text-grey-400']"
        >
          {{ charCount.toLocaleString() }} / {{ NOTES_MAX_CHARS.toLocaleString() }}
        </span>
        <button
          type="button"
          @click="showPreview = !showPreview"
          :title="showPreview ? 'Edit' : 'Preview'"
          class="p-1 rounded text-grey-400 hover:bg-grey-100 hover:text-grey-700 transition-colors"
        >
          <Pencil v-if="showPreview" class="w-3.5 h-3.5" />
          <Eye v-else class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <div
      v-if="showPreview"
      class="md-preview px-3 py-2 bg-surface-card rounded-lg border border-grey-200 min-h-[100px] text-body text-grey-800"
    >
      <div v-if="renderedHtml" v-html="renderedHtml" />
      <p v-else class="text-grey-400 italic">Nothing to preview.</p>
    </div>

    <textarea
      v-else
      :value="draft"
      @input="onInput"
      @blur="onBlur"
      @click.stop
      placeholder="Add notes — markdown supported (lists, **bold**, [links](url))"
      rows="4"
      class="w-full px-3 py-2 text-body text-grey-800 bg-surface-card rounded-lg border border-grey-200 focus:border-brand-light focus:ring-2 focus:ring-brand-lightest outline-none resize-y font-mono"
      style="font-size:13px; line-height:1.5;"
    />
  </div>
</template>

<style scoped>
.md-preview :deep(p)        { margin: 0 0 0.6em; }
.md-preview :deep(p:last-child) { margin-bottom: 0; }
.md-preview :deep(h1),
.md-preview :deep(h2),
.md-preview :deep(h3)       { font-weight: 700; margin: 0.6em 0 0.4em; line-height: 1.25; }
.md-preview :deep(h1)       { font-size: 1.15em; }
.md-preview :deep(h2)       { font-size: 1.05em; }
.md-preview :deep(h3)       { font-size: 1em; }
.md-preview :deep(ul),
.md-preview :deep(ol)       { padding-left: 1.4em; margin: 0 0 0.6em; }
.md-preview :deep(li)       { margin: 0.15em 0; }
.md-preview :deep(a)        { color: var(--brand-primary); text-decoration: underline; }
.md-preview :deep(code)     { background: var(--grey-100); padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.9em; }
.md-preview :deep(pre)      { background: var(--grey-100); padding: 0.6em; border-radius: 6px; overflow-x: auto; margin: 0 0 0.6em; }
.md-preview :deep(pre code) { background: transparent; padding: 0; }
.md-preview :deep(blockquote) { border-left: 3px solid var(--grey-200); padding-left: 0.8em; color: var(--grey-600); margin: 0 0 0.6em; }
.md-preview :deep(strong)   { font-weight: 700; }
</style>
