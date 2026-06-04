<script setup lang="ts">
import { ref } from 'vue'
import VueDatePicker from '@vuepic/vue-datepicker'
import { Plus as PlusIcon, Calendar as CalendarDaysIcon } from 'lucide-vue-next'
import type { Priority } from '../types'
import PriorityBadge from './ui/PriorityBadge.vue'

const emit = defineEmits<{
  add: [title: string, replyBy: Date, priority: Priority]
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const title      = ref('')
const priority   = ref<Priority>('normal')
const replyBy    = ref<Date>(defaultDate())
const submitting = ref(false)

function defaultDate(): Date {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  d.setHours(17, 0, 0, 0)
  return d
}

function formatDate(d: Date): string {
  const today    = new Date(); today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1)
  const target   = new Date(d); target.setHours(0, 0, 0, 0)
  if (target.getTime() === today.getTime())    return 'Today'
  if (target.getTime() === tomorrow.getTime()) return 'Tomorrow'
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

async function submit() {
  if (!title.value.trim() || submitting.value) return
  submitting.value = true
  try {
    emit('add', title.value.trim(), replyBy.value, priority.value)
    title.value    = ''
    priority.value = 'normal'
    replyBy.value  = defaultDate()
    inputRef.value?.focus()
  } finally {
    submitting.value = false
  }
}

defineExpose({
  focus() { inputRef.value?.focus() },
})

const PRIORITIES: Priority[] = ['low', 'normal', 'high']
</script>

<template>
  <div class="bg-surface-card rounded-xl shadow-card border border-brand-lightest overflow-visible">
    <!-- Input row -->
    <div class="flex items-center gap-3 px-4 py-3">
      <div class="w-6 h-6 rounded-full bg-brand-lightest flex items-center justify-center shrink-0">
        <PlusIcon class="w-3.5 h-3.5 text-brand-primary" />
      </div>
      <input
        ref="inputRef"
        v-model="title"
        placeholder="What needs to get done? (press n to focus)"
        class="flex-1 bg-transparent outline-none text-body text-grey-900 placeholder:text-grey-400 min-w-0"
        @keydown.enter.prevent="submit"
        @keydown.escape="title = ''"
      />
    </div>

    <!-- Controls row -->
    <div class="flex items-center gap-1.5 px-4 py-2.5 border-t border-grey-100 bg-surface-sunk rounded-b-xl">
      <!-- Priority selector -->
      <div class="flex items-center gap-1" role="group" aria-label="Priority">
        <button
          v-for="p in PRIORITIES"
          :key="p"
          type="button"
          @click="priority = p"
          :aria-pressed="priority === p"
          :class="['rounded-pill transition-all', priority === p ? '' : 'opacity-35 hover:opacity-70']"
        >
          <PriorityBadge :priority="p" />
        </button>
      </div>

      <div class="w-px h-4 bg-grey-200 mx-1 shrink-0" aria-hidden="true" />

      <!-- Date picker -->
      <VueDatePicker
        v-model="replyBy"
        auto-apply
        :enable-time-picker="false"
        :teleport="true"
        :week-start="6"
      >
        <template #trigger>
          <button
            type="button"
            class="flex items-center gap-1.5 px-2.5 py-1 rounded-pill text-micro font-semibold text-grey-600 hover:bg-grey-100 transition-colors"
            aria-label="Set due date"
          >
            <CalendarDaysIcon class="w-3.5 h-3.5" />
            {{ formatDate(replyBy) }}
          </button>
        </template>
      </VueDatePicker>

      <div class="ml-auto">
        <button
          type="button"
          @click="submit"
          :disabled="!title.trim() || submitting"
          class="px-4 py-1.5 bg-brand-primary hover:bg-brand-dark disabled:opacity-40 text-white text-caption font-semibold rounded-lg transition-colors"
        >
          Add task
        </button>
      </div>
    </div>
  </div>
</template>
