import { ref, computed } from 'vue'
import type { Task, FilterValue } from '../types'
import { api } from '../api'

export function useTasks() {
  const tasks = ref<Task[]>([])
  const activeFilter = ref<FilterValue>('open')
  const loading = ref(false)
  const polling = ref(false)
  const lastPolled = ref<Date | null>(null)
  const error = ref<string | null>(null)

  async function fetchTasks() {
    loading.value = true
    error.value = null
    try {
      tasks.value = await api.listTasks(activeFilter.value)
    } catch {
      error.value = 'Failed to load tasks. Is the backend running?'
    } finally {
      loading.value = false
    }
  }

  async function setFilter(f: FilterValue) {
    activeFilter.value = f
    await fetchTasks()
  }

  async function triggerPoll() {
    polling.value = true
    error.value = null
    try {
      await api.poll()
      lastPolled.value = new Date()
      await fetchTasks()
    } catch {
      error.value = 'Poll failed.'
    } finally {
      polling.value = false
    }
  }

  async function updateReplyBy(id: number, date: Date) {
    await api.updateReplyBy(id, date)
    await fetchTasks()
  }

  async function markReplied(id: number) {
    await api.updateStatus(id, 'replied')
    await fetchTasks()
  }

  async function dismiss(id: number) {
    await api.updateStatus(id, 'dismissed')
    await fetchTasks()
  }

  async function markNotATask(id: number) {
    await api.addFeedback(id, 'not_a_task')
    await api.updateStatus(id, 'dismissed')
    await fetchTasks()
  }

  async function wrongDeadline(id: number) {
    await api.addFeedback(id, 'wrong_deadline')
  }

  const overdueCount = computed(
    () => tasks.value.filter(t => t.status === 'open' && new Date(t.reply_by) < new Date()).length,
  )

  return {
    tasks,
    activeFilter,
    loading,
    polling,
    lastPolled,
    error,
    overdueCount,
    fetchTasks,
    setFilter,
    triggerPoll,
    updateReplyBy,
    markReplied,
    dismiss,
    markNotATask,
    wrongDeadline,
  }
}
