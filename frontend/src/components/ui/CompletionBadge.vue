<script setup lang="ts">
import { computed } from 'vue'
import { Circle, LoaderCircle, PauseCircle, CheckCircle2 } from 'lucide-vue-next'
import type { Completion } from '../../types'

const props = defineProps<{ completion: Completion; clickable?: boolean }>()
const emit = defineEmits<{ click: [e: MouseEvent] }>()

const CONFIG: Record<Completion, { label: string; icon: object; cls: string; hover: string }> = {
  not_started: { label: 'Not started', icon: Circle,       cls: 'bg-grey-50 text-grey-500 ring-1 ring-inset ring-grey-200',      hover: 'hover:bg-grey-100' },
  in_progress: { label: 'In progress', icon: LoaderCircle, cls: 'bg-blue-50 text-blue-600 ring-1 ring-inset ring-blue-200',       hover: 'hover:bg-blue-100' },
  on_hold:     { label: 'On hold',     icon: PauseCircle,  cls: 'bg-amber-50 text-amber-600 ring-1 ring-inset ring-amber-200',    hover: 'hover:bg-amber-100' },
  completed:   { label: 'Completed',   icon: CheckCircle2, cls: 'bg-green-50 text-green-600 ring-1 ring-inset ring-green-200',    hover: 'hover:bg-green-100' },
}

const cfg = computed(() => CONFIG[props.completion] ?? CONFIG.not_started)
</script>

<template>
  <component
    :is="clickable ? 'button' : 'span'"
    type="button"
    :class="[
      'inline-flex items-center gap-1 text-micro font-semibold px-2 py-0.5 rounded-pill transition-colors select-none whitespace-nowrap',
      cfg.cls,
      clickable ? [cfg.hover, 'cursor-pointer'] : '',
    ]"
    v-bind="clickable ? { title: 'Click to change status' } : {}"
    @click="clickable ? emit('click', $event) : undefined"
  >
    <component :is="cfg.icon" class="w-3 h-3 shrink-0" />
    {{ cfg.label }}
  </component>
</template>
