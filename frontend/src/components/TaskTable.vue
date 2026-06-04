<script setup lang="ts">
import { ref } from 'vue'
import { Inbox as InboxIcon } from 'lucide-vue-next'
import type { Task, FilterValue } from '../types'
import TaskRow from './TaskRow.vue'
import EmptyState from './ui/EmptyState.vue'

const props = defineProps<{
  tasks: Task[]
  loading: boolean
  activeFilter?: FilterValue
  focusedIndex?: number
  selectedIds?: Set<number>
  allSelected?: boolean
}>()

const emit = defineEmits<{
  'update-reply-by':   [id: number, date: Date]
  'update-task':       [id: number, data: { title?: string; priority?: import('../types').Priority }]
  'mark-replied':      [id: number]
  dismiss:             [id: number]
  'not-a-task':        [id: number]
  'toggle-select':     [id: number]
  'toggle-select-all': []
}>()

const rowRefs = ref<InstanceType<typeof TaskRow>[]>([])

defineExpose({
  openDatePickerAt(index: number) {
    rowRefs.value[index]?.openDatePicker()
  },
})

const emptyMessages: Record<string, { title: string; message: string }> = {
  open:      { title: 'Inbox zero.',            message: 'Go touch grass.' },
  replied:   { title: 'Nothing replied yet.',   message: 'Tasks you mark as replied will appear here.' },
  dismissed: { title: 'Clean slate.',           message: 'Dismissed tasks will show up here.' },
  all:       { title: 'No tasks found.',        message: 'Poll your inbox to detect emails that need a reply.' },
}
</script>

<template>
  <div>
    <div v-if="loading" class="py-20 text-center text-caption text-grey-400">Loading…</div>

    <EmptyState
      v-else-if="tasks.length === 0"
      :icon="InboxIcon"
      :title="emptyMessages[activeFilter ?? 'all']?.title"
      :message="emptyMessages[activeFilter ?? 'all']?.message"
    />

    <!-- Table — fixed layout, colgroup widths matching design file -->
    <table v-else class="w-full" style="border-collapse:collapse; table-layout:fixed;">
      <colgroup>
        <col style="width:40px" />    <!-- select -->
        <col style="width:192px" />   <!-- from (avatar + name) -->
        <col />                       <!-- task — flex -->
        <col style="width:90px" />    <!-- priority -->
        <col style="width:120px" />   <!-- completion -->
        <col style="width:130px" />   <!-- reply-by -->
        <col style="width:196px" />   <!-- actions -->
      </colgroup>
      <thead>
        <tr style="background:var(--surface-sunk); border-bottom:1px solid var(--grey-100)">
          <!-- Select all -->
          <th class="px-3 py-2.5 w-8">
            <input
              type="checkbox"
              :checked="allSelected"
              @change="emit('toggle-select-all')"
              aria-label="Select all tasks"
              class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary cursor-pointer"
            />
          </th>
          <th class="px-3 py-2.5 text-left text-micro font-bold text-grey-500 uppercase tracking-widest">From</th>
          <th class="px-3 py-2.5 text-left text-micro font-bold text-grey-500 uppercase tracking-widest">Task</th>
          <th class="px-3 py-2.5 text-left text-micro font-bold text-grey-500 uppercase tracking-widest">Priority</th>
          <th class="px-3 py-2.5 text-left text-micro font-bold text-grey-500 uppercase tracking-widest">Status</th>
          <th class="px-3 py-2.5 text-left text-micro font-bold text-grey-500 uppercase tracking-widest">Reply by</th>
          <th class="px-3 py-2.5 text-right text-micro font-bold text-grey-500 uppercase tracking-widest"></th>
        </tr>
      </thead>
      <TransitionGroup
        tag="tbody"
        enter-active-class="transition-all duration-300 ease-out"
        enter-from-class="opacity-0 translate-y-1"
        leave-active-class="transition-none"
        leave-to-class="opacity-0"
      >
        <TaskRow
          v-for="(task, i) in tasks"
          :key="task.id"
          :ref="(el) => { if (el) rowRefs[i] = el as InstanceType<typeof TaskRow> }"
          :task="task"
          :focused="focusedIndex === i"
          :selected="selectedIds?.has(task.id) ?? false"
          :class="`stagger-${Math.min(i, 5)}`"
          :style="{ transitionDelay: `${Math.min(i, 5) * 40}ms` }"
          @update-reply-by="d => emit('update-reply-by', task.id, d)"
          @update-task="data => emit('update-task', task.id, data)"
          @mark-replied="emit('mark-replied', task.id)"
          @dismiss="emit('dismiss', task.id)"
          @not-a-task="emit('not-a-task', task.id)"
          @toggle-select="emit('toggle-select', task.id)"
        />
      </TransitionGroup>
    </table>
  </div>
</template>
