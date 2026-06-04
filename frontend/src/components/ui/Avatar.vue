<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ name: string; email?: string; size?: 'sm' | 'md' }>()

const TINTS = [
  'bg-purple-100 text-purple-700',
  'bg-pink-100   text-pink-700',
  'bg-sky-100    text-sky-700',
  'bg-teal-100   text-teal-700',
  'bg-amber-100  text-amber-700',
  'bg-brand-lightest text-brand-dark',
]

function hash(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return h
}

const tint = computed(() => TINTS[hash(props.email ?? props.name) % TINTS.length])

const initials = computed(() =>
  props.name
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
)

const sizeClass = computed(() =>
  props.size === 'sm' ? 'w-7 h-7 text-micro' : 'w-8 h-8 text-caption'
)
</script>

<template>
  <div
    :class="['rounded-full flex items-center justify-center font-bold shrink-0', tint, sizeClass]"
    :title="name"
    aria-hidden="true"
  >
    {{ initials }}
  </div>
</template>
