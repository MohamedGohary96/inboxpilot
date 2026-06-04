import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { Task, FilterValue, Priority, Completion, AdvancedFilters, TaskLink } from '../types'
import { api } from '../api'

export const useTaskStore = defineStore('tasks', () => {
  const tasks           = ref<Task[]>([])
  const activeFilter    = ref<FilterValue>('open')
  const advancedFilters = ref<AdvancedFilters>({ source: [], priority: [], completion: [], replyBy: null })
  const loading         = ref(false)
  const polling         = ref(false)
  const lastPolled      = ref<Date | null>(null)
  const error           = ref<string | null>(null)
  const selectedIds     = ref<Set<number>>(new Set())
  const linksByTask     = ref<Record<number, TaskLink[]>>({})

  const overdueCount = computed(
    () => tasks.value.filter(t => t.status === 'open' && new Date(t.reply_by) < new Date()).length,
  )

  const hasSelection = computed(() => selectedIds.value.size > 0)

  const allSelected = computed(
    () => tasks.value.length > 0 && tasks.value.every(t => selectedIds.value.has(t.id)),
  )

  // ── data ─────────────────────────────────────────────────────────────────

  async function fetchTasks() {
    loading.value = true
    error.value = null
    try {
      tasks.value = await api.listTasks(activeFilter.value, advancedFilters.value)
      selectedIds.value = new Set()
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

  async function setAdvancedFilters(f: AdvancedFilters) {
    advancedFilters.value = f
    await fetchTasks()
  }

  function clearAdvancedFilters() {
    advancedFilters.value = { source: [], priority: [], completion: [], replyBy: null }
  }

  async function triggerPoll() {
    polling.value = true
    error.value = null
    try {
      try {
        await api.poll()
      } catch (e: unknown) {
        // 409 = another poll already running — join it instead of failing
        const msg = e instanceof Error ? e.message : String(e)
        if (!msg.includes('409')) throw e
      }
      // Poll is fire-and-forget. Watch progress until done.
      await new Promise<void>((resolve, reject) => {
        const MAX_WAIT_MS = 12 * 60 * 1000
        const deadline = Date.now() + MAX_WAIT_MS
        const timer = setInterval(async () => {
          try {
            const p = await api.getPollProgress()
            if (p.done) {
              clearInterval(timer)
              resolve()
            } else if (Date.now() > deadline) {
              clearInterval(timer)
              reject(new Error('timeout'))
            }
          } catch {
            clearInterval(timer)
            reject(new Error('progress check failed'))
          }
        }, 800)
      })
      lastPolled.value = new Date()
      await fetchTasks()
    } catch {
      error.value = 'Poll failed.'
    } finally {
      polling.value = false
    }
  }

  // ── single-task actions ───────────────────────────────────────────────────

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

  async function updateTask(id: number, data: { title?: string; priority?: Priority; completion?: Completion; notes?: string }) {
    // Optimistic local update
    const task = tasks.value.find(t => t.id === id)
    if (task) {
      if (data.title !== undefined) task.title = data.title
      if (data.priority !== undefined) task.priority = data.priority
      if (data.completion !== undefined) task.completion = data.completion
      if (data.notes !== undefined) task.notes = data.notes || null
    }
    await api.updateTask(id, data)
  }

  // ── Links ─────────────────────────────────────────────────────────────────

  async function loadLinks(taskId: number): Promise<TaskLink[]> {
    const { links } = await api.listLinks(taskId)
    linksByTask.value = { ...linksByTask.value, [taskId]: links }
    return links
  }

  async function addLink(taskId: number, url: string, label?: string): Promise<TaskLink> {
    const link = await api.addLink(taskId, url, label)
    const existing = linksByTask.value[taskId] ?? []
    linksByTask.value = { ...linksByTask.value, [taskId]: [...existing, link] }
    const task = tasks.value.find(t => t.id === taskId)
    if (task) task.link_count = (task.link_count ?? 0) + 1
    return link
  }

  async function removeLink(taskId: number, linkId: number) {
    const existing = linksByTask.value[taskId] ?? []
    // Optimistic removal
    linksByTask.value = { ...linksByTask.value, [taskId]: existing.filter(l => l.id !== linkId) }
    const task = tasks.value.find(t => t.id === taskId)
    if (task) task.link_count = Math.max(0, (task.link_count ?? 1) - 1)
    try {
      await api.deleteLink(taskId, linkId)
    } catch (e) {
      // Revert on failure
      linksByTask.value = { ...linksByTask.value, [taskId]: existing }
      if (task) task.link_count = (task.link_count ?? 0) + 1
      throw e
    }
  }

  async function createTask(title: string, replyBy?: Date, priority?: Priority, notes?: string) {
    await api.createTask({
      title,
      reply_by: replyBy?.toISOString(),
      priority,
      notes,
    })
    await fetchTasks()
  }

  // ── bulk selection ────────────────────────────────────────────────────────

  function toggleSelect(id: number) {
    const next = new Set(selectedIds.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    selectedIds.value = next
  }

  function toggleSelectAll() {
    if (allSelected.value) {
      selectedIds.value = new Set()
    } else {
      selectedIds.value = new Set(tasks.value.map(t => t.id))
    }
  }

  function clearSelection() {
    selectedIds.value = new Set()
  }

  // ── bulk actions ──────────────────────────────────────────────────────────

  async function bulkMarkReplied() {
    const ids = [...selectedIds.value]
    await Promise.all(ids.map(id => api.updateStatus(id, 'replied')))
    await fetchTasks()
  }

  async function bulkDismiss() {
    const ids = [...selectedIds.value]
    await Promise.all(ids.map(id => api.updateStatus(id, 'dismissed')))
    await fetchTasks()
  }

  async function bulkSetCompletion(completion: Completion) {
    const ids = [...selectedIds.value]
    await Promise.all(ids.map(id => api.updateTask(id, { completion })))
    await fetchTasks()
  }

  return {
    tasks, activeFilter, advancedFilters, loading, polling, lastPolled, error,
    selectedIds, linksByTask, overdueCount, hasSelection, allSelected,
    fetchTasks, setFilter, setAdvancedFilters, clearAdvancedFilters,
    triggerPoll, updateReplyBy, updateTask,
    markReplied, dismiss, markNotATask, wrongDeadline, createTask,
    toggleSelect, toggleSelectAll, clearSelection,
    bulkMarkReplied, bulkDismiss, bulkSetCompletion,
    loadLinks, addLink, removeLink,
  }
})
