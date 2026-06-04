<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronDown, X, Mail, Hash, PenLine, AlertCircle, ArrowUp, Minus, Clock, Circle, LoaderCircle, PauseCircle, CheckCircle2 } from 'lucide-vue-next'
import type { AdvancedFilters } from '../types'

const props = defineProps<{ modelValue: AdvancedFilters }>()
const emit = defineEmits<{ 'update:modelValue': [v: AdvancedFilters] }>()

type PopoverName = 'source' | 'priority' | 'completion' | 'replyBy'
const openPopover = ref<PopoverName | null>(null)

function toggle(name: PopoverName) {
  openPopover.value = openPopover.value === name ? null : name
}
function close() { openPopover.value = null }

// ── Source ────────────────────────────────────────────────────────────────
const sourceOptions = [
  { label: 'Email',  value: 'mail',   icon: Mail },
  { label: 'Slack',  value: 'slack',  icon: Hash },
  { label: 'Manual', value: 'manual', icon: PenLine },
]

function toggleSource(v: string) {
  const next = props.modelValue.source.includes(v)
    ? props.modelValue.source.filter(s => s !== v)
    : [...props.modelValue.source, v]
  emit('update:modelValue', { ...props.modelValue, source: next })
}

// ── Priority ──────────────────────────────────────────────────────────────
const priorityOptions = [
  { label: 'High',   value: 'high',   icon: AlertCircle, color: 'text-red-500' },
  { label: 'Normal', value: 'normal', icon: ArrowUp,     color: 'text-amber-500' },
  { label: 'Low',    value: 'low',    icon: Minus,       color: 'text-grey-400' },
]

function togglePriority(v: string) {
  const next = props.modelValue.priority.includes(v)
    ? props.modelValue.priority.filter(p => p !== v)
    : [...props.modelValue.priority, v]
  emit('update:modelValue', { ...props.modelValue, priority: next })
}

// ── Completion ────────────────────────────────────────────────────────
const completionOptions = [
  { label: 'Not started', value: 'not_started', icon: Circle,       color: 'text-grey-400' },
  { label: 'In progress', value: 'in_progress', icon: LoaderCircle, color: 'text-blue-500' },
  { label: 'On hold',     value: 'on_hold',     icon: PauseCircle,  color: 'text-amber-500' },
  { label: 'Completed',   value: 'completed',   icon: CheckCircle2, color: 'text-green-500' },
]

function toggleCompletion(v: string) {
  const next = props.modelValue.completion.includes(v)
    ? props.modelValue.completion.filter(c => c !== v)
    : [...props.modelValue.completion, v]
  emit('update:modelValue', { ...props.modelValue, completion: next })
}

// ── Reply by ──────────────────────────────────────────────────────────────
const replyByOptions = [
  { label: 'Overdue',      value: 'overdue' },
  { label: 'Today',        value: 'today' },
  { label: 'This week',    value: 'week' },
  { label: 'Next 30 days', value: 'month' },
  { label: 'No date set',  value: 'none' },
]

function setReplyBy(v: string) {
  const next = props.modelValue.replyBy === v ? null : v
  emit('update:modelValue', { ...props.modelValue, replyBy: next })
  close()
}

// ── Clear all ─────────────────────────────────────────────────────────────
const hasFilters = computed(() =>
  props.modelValue.source.length > 0 ||
  props.modelValue.priority.length > 0 ||
  props.modelValue.completion.length > 0 ||
  props.modelValue.replyBy !== null,
)

function clearAll() {
  emit('update:modelValue', { source: [], priority: [], completion: [], replyBy: null })
}

// ── Labels ────────────────────────────────────────────────────────────────
const sourceLabel = computed(() => {
  const sel = props.modelValue.source
  if (!sel.length) return 'Source'
  return sel.map(s => sourceOptions.find(o => o.value === s)?.label ?? s).join(', ')
})

const priorityLabel = computed(() => {
  const sel = props.modelValue.priority
  if (!sel.length) return 'Priority'
  return sel.map(p => priorityOptions.find(o => o.value === p)?.label ?? p).join(', ')
})

const completionLabel = computed(() => {
  const sel = props.modelValue.completion
  if (!sel.length) return 'Status'
  return sel.map(c => completionOptions.find(o => o.value === c)?.label ?? c).join(', ')
})

const replyByLabel = computed(() =>
  replyByOptions.find(o => o.value === props.modelValue.replyBy)?.label ?? 'Reply by'
)
</script>

<template>
  <!-- backdrop to close popovers on outside click -->
  <div v-if="openPopover" class="fixed inset-0 z-10" @click="close" />

  <div class="flex items-center gap-1.5 flex-wrap">

    <!-- Source pill -->
    <div class="relative">
      <button
        @click="toggle('source')"
        :class="[
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold border transition-all',
          modelValue.source.length
            ? 'bg-brand-50 border-brand-light text-brand-primary'
            : 'bg-surface-card border-grey-200 text-grey-600 hover:border-brand-light hover:text-brand-primary',
        ]"
      >
        <Mail class="w-3.5 h-3.5" />
        {{ sourceLabel }}
        <X
          v-if="modelValue.source.length"
          class="w-3 h-3 ml-0.5 hover:text-brand-dark"
          @click.stop="emit('update:modelValue', { ...modelValue, source: [] })"
        />
        <ChevronDown v-else class="w-3 h-3 ml-0.5 opacity-50" />
      </button>

      <Transition
        enter-active-class="transition-all duration-100 ease-out"
        enter-from-class="opacity-0 scale-95 -translate-y-1"
        leave-active-class="transition-all duration-75 ease-in"
        leave-to-class="opacity-0 scale-95 -translate-y-1"
      >
        <div
          v-if="openPopover === 'source'"
          class="absolute top-full left-0 mt-1.5 z-20 bg-surface-card rounded-xl shadow-dropdown border border-grey-100 overflow-hidden min-w-[160px]"
        >
          <div class="px-3 py-2 border-b border-grey-100">
            <span class="text-micro font-bold text-grey-400 uppercase tracking-wide">Source</span>
          </div>
          <div class="py-1">
            <label
              v-for="opt in sourceOptions"
              :key="opt.value"
              class="flex items-center gap-2.5 px-3 py-2 hover:bg-brand-50 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                :checked="modelValue.source.includes(opt.value)"
                @change="toggleSource(opt.value)"
                class="w-3.5 h-3.5 rounded accent-brand-primary"
              />
              <component :is="opt.icon" class="w-3.5 h-3.5 text-grey-500" />
              <span class="text-caption text-grey-800">{{ opt.label }}</span>
            </label>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Priority pill -->
    <div class="relative">
      <button
        @click="toggle('priority')"
        :class="[
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold border transition-all',
          modelValue.priority.length
            ? 'bg-brand-50 border-brand-light text-brand-primary'
            : 'bg-surface-card border-grey-200 text-grey-600 hover:border-brand-light hover:text-brand-primary',
        ]"
      >
        <AlertCircle class="w-3.5 h-3.5" />
        {{ priorityLabel }}
        <X
          v-if="modelValue.priority.length"
          class="w-3 h-3 ml-0.5 hover:text-brand-dark"
          @click.stop="emit('update:modelValue', { ...modelValue, priority: [] })"
        />
        <ChevronDown v-else class="w-3 h-3 ml-0.5 opacity-50" />
      </button>

      <Transition
        enter-active-class="transition-all duration-100 ease-out"
        enter-from-class="opacity-0 scale-95 -translate-y-1"
        leave-active-class="transition-all duration-75 ease-in"
        leave-to-class="opacity-0 scale-95 -translate-y-1"
      >
        <div
          v-if="openPopover === 'priority'"
          class="absolute top-full left-0 mt-1.5 z-20 bg-surface-card rounded-xl shadow-dropdown border border-grey-100 overflow-hidden min-w-[160px]"
        >
          <div class="px-3 py-2 border-b border-grey-100">
            <span class="text-micro font-bold text-grey-400 uppercase tracking-wide">Priority</span>
          </div>
          <div class="py-1">
            <label
              v-for="opt in priorityOptions"
              :key="opt.value"
              class="flex items-center gap-2.5 px-3 py-2 hover:bg-brand-50 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                :checked="modelValue.priority.includes(opt.value)"
                @change="togglePriority(opt.value)"
                class="w-3.5 h-3.5 rounded accent-brand-primary"
              />
              <component :is="opt.icon" :class="['w-3.5 h-3.5', opt.color]" />
              <span class="text-caption text-grey-800">{{ opt.label }}</span>
            </label>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Completion pill -->
    <div class="relative">
      <button
        @click="toggle('completion')"
        :class="[
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold border transition-all',
          modelValue.completion.length
            ? 'bg-brand-50 border-brand-light text-brand-primary'
            : 'bg-surface-card border-grey-200 text-grey-600 hover:border-brand-light hover:text-brand-primary',
        ]"
      >
        <Circle class="w-3.5 h-3.5" />
        {{ completionLabel }}
        <X
          v-if="modelValue.completion.length"
          class="w-3 h-3 ml-0.5 hover:text-brand-dark"
          @click.stop="emit('update:modelValue', { ...modelValue, completion: [] })"
        />
        <ChevronDown v-else class="w-3 h-3 ml-0.5 opacity-50" />
      </button>

      <Transition
        enter-active-class="transition-all duration-100 ease-out"
        enter-from-class="opacity-0 scale-95 -translate-y-1"
        leave-active-class="transition-all duration-75 ease-in"
        leave-to-class="opacity-0 scale-95 -translate-y-1"
      >
        <div
          v-if="openPopover === 'completion'"
          class="absolute top-full left-0 mt-1.5 z-20 bg-surface-card rounded-xl shadow-dropdown border border-grey-100 overflow-hidden min-w-[160px]"
        >
          <div class="px-3 py-2 border-b border-grey-100">
            <span class="text-micro font-bold text-grey-400 uppercase tracking-wide">Status</span>
          </div>
          <div class="py-1">
            <label
              v-for="opt in completionOptions"
              :key="opt.value"
              class="flex items-center gap-2.5 px-3 py-2 hover:bg-brand-50 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                :checked="modelValue.completion.includes(opt.value)"
                @change="toggleCompletion(opt.value)"
                class="w-3.5 h-3.5 rounded accent-brand-primary"
              />
              <component :is="opt.icon" :class="['w-3.5 h-3.5', opt.color]" />
              <span class="text-caption text-grey-800">{{ opt.label }}</span>
            </label>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Reply by pill -->
    <div class="relative">
      <button
        @click="toggle('replyBy')"
        :class="[
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-caption font-semibold border transition-all',
          modelValue.replyBy
            ? 'bg-brand-50 border-brand-light text-brand-primary'
            : 'bg-surface-card border-grey-200 text-grey-600 hover:border-brand-light hover:text-brand-primary',
        ]"
      >
        <Clock class="w-3.5 h-3.5" />
        {{ replyByLabel }}
        <X
          v-if="modelValue.replyBy"
          class="w-3 h-3 ml-0.5 hover:text-brand-dark"
          @click.stop="emit('update:modelValue', { ...modelValue, replyBy: null })"
        />
        <ChevronDown v-else class="w-3 h-3 ml-0.5 opacity-50" />
      </button>

      <Transition
        enter-active-class="transition-all duration-100 ease-out"
        enter-from-class="opacity-0 scale-95 -translate-y-1"
        leave-active-class="transition-all duration-75 ease-in"
        leave-to-class="opacity-0 scale-95 -translate-y-1"
      >
        <div
          v-if="openPopover === 'replyBy'"
          class="absolute top-full left-0 mt-1.5 z-20 bg-surface-card rounded-xl shadow-dropdown border border-grey-100 overflow-hidden min-w-[160px]"
        >
          <div class="px-3 py-2 border-b border-grey-100">
            <span class="text-micro font-bold text-grey-400 uppercase tracking-wide">Reply by</span>
          </div>
          <div class="py-1">
            <button
              v-for="opt in replyByOptions"
              :key="opt.value"
              @click="setReplyBy(opt.value)"
              :class="[
                'w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors text-caption',
                modelValue.replyBy === opt.value
                  ? 'bg-brand-50 text-brand-primary font-semibold'
                  : 'text-grey-800 hover:bg-brand-50',
              ]"
            >
              <span
                :class="[
                  'w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0',
                  modelValue.replyBy === opt.value
                    ? 'border-brand-primary bg-brand-primary'
                    : 'border-grey-300',
                ]"
              >
                <span v-if="modelValue.replyBy === opt.value" class="w-1.5 h-1.5 rounded-full bg-white" />
              </span>
              {{ opt.label }}
            </button>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Clear all -->
    <Transition
      enter-active-class="transition-all duration-100"
      enter-from-class="opacity-0 scale-90"
      leave-active-class="transition-all duration-75"
      leave-to-class="opacity-0 scale-90"
    >
      <button
        v-if="hasFilters"
        @click="clearAll"
        class="flex items-center gap-1 px-2.5 py-1.5 text-caption text-grey-500 hover:text-red-500 transition-colors"
      >
        <X class="w-3 h-3" />
        Clear
      </button>
    </Transition>
  </div>
</template>
