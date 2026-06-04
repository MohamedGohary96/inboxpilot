import type { Task, Status, FilterValue, Priority, Completion, ClassificationInfo, AppStatus, CalendarEvent, AdvancedFilters, TaskLink, PrioritySender, NewsItem, NewsCategory } from './types'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    ...options,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  listTasks: (status: FilterValue = 'open', filters?: AdvancedFilters) => {
    const p = new URLSearchParams({ status })
    for (const s of filters?.source ?? []) p.append('source', s)
    for (const pr of filters?.priority ?? []) p.append('priority', pr)
    for (const c of filters?.completion ?? []) p.append('completion', c)
    if (filters?.replyBy) p.set('reply_by', filters.replyBy)
    return request<Task[]>(`/tasks?${p}`)
  },

  createTask: (data: { title: string; reply_by?: string; priority?: Priority; notes?: string }) =>
    request<Task>('/tasks', { method: 'POST', body: JSON.stringify(data) }),

  updateTask: (id: number, data: { title?: string; priority?: Priority; completion?: Completion; notes?: string }) =>
    request<{ ok: boolean }>(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  listLinks: (taskId: number) =>
    request<{ links: TaskLink[] }>(`/tasks/${taskId}/links`),

  addLink: (taskId: number, url: string, label?: string) =>
    request<TaskLink>(`/tasks/${taskId}/links`, {
      method: 'POST',
      body: JSON.stringify({ url, label }),
    }),

  deleteLink: (taskId: number, linkId: number) =>
    request<{ ok: boolean }>(`/tasks/${taskId}/links/${linkId}`, { method: 'DELETE' }),

  updateReplyBy: (id: number, replyBy: Date) =>
    request<{ ok: boolean }>(`/tasks/${id}/reply_by`, {
      method: 'POST',
      body: JSON.stringify({ reply_by: replyBy.toISOString() }),
    }),

  updateStatus: (id: number, status: Status) =>
    request<{ ok: boolean }>(`/tasks/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),

  addFeedback: (id: number, kind: string, note?: string) =>
    request<{ ok: boolean }>(`/tasks/${id}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ kind, note }),
    }),

  getClassification: (id: number) =>
    request<ClassificationInfo>(`/tasks/${id}/classification`),

  suggestReply: (id: number) =>
    request<{ reply: string }>(`/tasks/${id}/suggest-reply`, { method: 'POST' }),

  smartReply: (id: number, instructions: string) =>
    request<{
      draft: string
      meeting: { event_id: string; start: string; end: string; html_link: string | null; title: string; error?: string } | null
      to_email: string | null
      subject: string | null
      thread_id: string | null
    }>(`/tasks/${id}/smart-reply`, { method: 'POST', body: JSON.stringify({ instructions }) }),

  draftReply: (id: number, instructions?: string) =>
    request<{ draft: string; to_email: string | null; subject: string | null; thread_id: string | null }>(
      `/tasks/${id}/draft-reply`,
      { method: 'POST', body: JSON.stringify({ instructions: instructions || null }) },
    ),

  scheduleMeeting: (id: number, data: {
    date: string
    window_start: string
    window_end: string
    duration_minutes: number
    title?: string
  }) =>
    request<{ event_id: string; start: string; end: string; html_link: string | null; title: string }>(
      `/tasks/${id}/schedule-meeting`,
      { method: 'POST', body: JSON.stringify(data) },
    ),

  poll: () =>
    request<{ started: boolean }>('/poll', { method: 'POST' }),

  getPollProgress: () =>
    request<{ phase: string; current: number; total: number; done: boolean }>('/poll/progress'),

  getStatus: () =>
    request<AppStatus>('/status'),

  getSettings: () =>
    request<Record<string, string>>('/settings'),

  updateSetting: (key: string, value: string) =>
    request<{ ok: boolean }>('/settings', {
      method: 'POST',
      body: JSON.stringify({ key, value }),
    }),

  getCalendarEvents: (from: Date, to: Date) =>
    request<{ events: CalendarEvent[] }>(
      `/calendar/events?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`
    ),

  triggerReauth: () =>
    request<{ state: string }>('/auth/reauth', { method: 'POST' }),

  resetReauth: () =>
    request<{ state: string }>('/auth/reauth/reset', { method: 'POST' }),

  logout: () =>
    request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),

  connectSlack: (token: string) =>
    request<{ ok: boolean; team: string; user: string; team_id: string }>(
      '/auth/slack/connect',
      { method: 'POST', body: JSON.stringify({ token }) },
    ),

  slackLogout: () =>
    request<{ ok: boolean }>('/auth/slack/logout', { method: 'POST' }),

  slackReset: () =>
    request<{ ok: boolean }>('/auth/slack/reset', { method: 'POST' }),

  pollSlack: () =>
    request<{ new_messages: number }>('/auth/slack/poll', { method: 'POST' }),

  // ── Priority senders (VIPs) ─────────────────────────────────────────────
  listPrioritySenders: () =>
    request<{ senders: PrioritySender[] }>('/priority-senders'),

  addPrioritySender: (email: string, replyWindowHours: number, note?: string) =>
    request<PrioritySender>('/priority-senders', {
      method: 'POST',
      body: JSON.stringify({ email, note, reply_window_hours: replyWindowHours }),
    }),

  updatePrioritySender: (id: number, data: { note?: string; reply_window_hours?: number }) =>
    request<{ ok: boolean }>(`/priority-senders/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deletePrioritySender: (id: number) =>
    request<{ ok: boolean }>(`/priority-senders/${id}`, { method: 'DELETE' }),

  // ── News (GitHub digest) ────────────────────────────────────────────────
  listNews: (category?: NewsCategory, repo?: string) => {
    const p = new URLSearchParams()
    if (category) p.set('category', category)
    if (repo) p.set('repo', repo)
    const qs = p.toString()
    return request<{ items: NewsItem[] }>(`/news${qs ? '?' + qs : ''}`)
  },

  newsUnreadCount: () =>
    request<{ count: number }>('/news/unread-count'),

  summarizeNews: (id: number) =>
    request<{ summary: string }>(`/news/${id}/summarize`, { method: 'POST' }),

  dismissNews: (id: number) =>
    request<{ ok: boolean }>(`/news/${id}/dismiss`, { method: 'POST' }),

  dismissAllNews: (category?: NewsCategory) => {
    const p = new URLSearchParams()
    if (category) p.set('category', category)
    const qs = p.toString()
    return request<{ ok: boolean; dismissed: number }>(
      `/news/dismiss-all${qs ? '?' + qs : ''}`,
      { method: 'POST' },
    )
  },
}
