<script setup lang="ts">
import type { FilterValue } from '../types'

defineProps<{ active: FilterValue }>()
const emit = defineEmits<{ change: [f: FilterValue] }>()

const filters: { label: string; value: FilterValue }[] = [
  { label: 'Open',      value: 'open' },
  { label: 'Replied',   value: 'replied' },
  { label: 'Dismissed', value: 'dismissed' },
  { label: 'All',       value: 'all' },
]
</script>

<template>
  <div class="inline-flex bg-surface-card rounded-lg p-1 shadow-card gap-0.5">
    <button
      v-for="f in filters"
      :key="f.value"
      @click="emit('change', f.value)"
      :class="[
        'px-3 py-1.5 rounded-md text-caption font-semibold transition-all',
        active === f.value
          ? 'bg-brand-primary text-white shadow-card'
          : 'text-grey-500 hover:text-brand-primary hover:bg-brand-50',
      ]"
    >
      {{ f.label }}
    </button>
  </div>
</template>
