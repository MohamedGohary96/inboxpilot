<script setup lang="ts">
import type { FunctionalComponent, SVGAttributes } from 'vue'

defineProps<{
  icon?: FunctionalComponent<SVGAttributes>
  title?: string
  message?: string
  hint?: string
  actionLabel?: string
}>()

const emit = defineEmits<{ action: [] }>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-14 text-center px-4 animate-fade-in-up">
    <div v-if="icon" class="w-12 h-12 bg-brand-50 rounded-full flex items-center justify-center mb-4">
      <component :is="icon" class="w-6 h-6 text-brand-primary" />
    </div>
    <p v-if="title" class="text-subheading font-bold text-grey-700 mb-1">{{ title }}</p>
    <p class="text-body text-grey-500">{{ message }}</p>
    <p v-if="hint" class="text-caption text-grey-400 mt-1">{{ hint }}</p>
    <button
      v-if="actionLabel"
      @click="emit('action')"
      class="mt-4 px-4 py-1.5 rounded-lg text-caption font-semibold bg-brand-50 text-brand-primary border border-brand-light hover:bg-brand-lightest transition-colors card-interactive"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
