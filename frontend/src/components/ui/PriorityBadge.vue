<script setup lang="ts">
import { computed } from 'vue'
import { Flame, Minus, ChevronDown } from 'lucide-vue-next'
import type { Priority } from '../../types'

const props = defineProps<{ priority: Priority; clickable?: boolean }>()
const emit = defineEmits<{ click: [e: MouseEvent] }>()

const CONFIG = {
  high:   { label: 'High',   icon: Flame,       cls: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-200',      hover: 'hover:bg-red-100' },
  normal: { label: 'Normal', icon: Minus,        cls: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200', hover: 'hover:bg-amber-100' },
  low:    { label: 'Low',    icon: ChevronDown,  cls: 'bg-sky-50 text-sky-600 ring-1 ring-inset ring-sky-100',      hover: 'hover:bg-sky-100' },
}

const cfg = computed(() => CONFIG[props.priority] ?? CONFIG.normal)
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
    v-bind="clickable ? { title: 'Click to change priority' } : {}"
    @click="clickable ? emit('click', $event) : undefined"
  >
    <component :is="cfg.icon" class="w-3 h-3 shrink-0" />
    {{ cfg.label }}
  </component>
</template>
