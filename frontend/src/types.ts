export type Priority = 'low' | 'normal' | 'high'
export type Status = 'open' | 'replied' | 'dismissed'
export type FilterValue = Status | 'all'
export type Completion = 'not_started' | 'in_progress' | 'on_hold' | 'completed'

export interface AdvancedFilters {
  source: string[]
  priority: string[]
  completion: string[]
  replyBy: string | null
}
export type FeedbackKind = 'not_a_task' | 'wrong_summary' | 'wrong_deadline' | 'missed_task'
export type DeadlineConfidence = 'explicit' | 'implied' | 'none'

export interface ClassificationInfo {
  reasoning: string | null
  priority_signals: string[]
  deadline_confidence: DeadlineConfidence | null
  model: string
  prompt_version: string
  classified_at: string
}

export type ReauthState = 'idle' | 'pending' | 'done' | 'error'

export interface AppStatus {
  authenticated: boolean
  account_email: string | null
  reauth_state: ReauthState
  needs_reauth: boolean
  slack_connected: boolean
  total_messages: number
  total_tasks: number
  open_tasks: number
  last_poll: string | null
}

export type NewsCategory = 'release' | 'security' | 'discussion' | 'newsletter' | 'pull_request' | 'issue'

export interface NewsItem {
  id: number
  sender: string | null
  sender_email: string
  subject: string
  received_at: string
  news_category: NewsCategory
  news_repo: string | null
  news_summary: string | null
  snippet: string | null
  thread_id: string | null
  gmail_message_id: string
  is_task: number  // 0 or 1 from SQLite
  task_id: number | null
}

export type TaskSource = 'mail' | 'manual' | 'slack'

export interface TaskLink {
  id: number
  url: string
  label: string | null
  created_at: string
}

export interface PrioritySender {
  id: number
  email: string
  note: string | null
  reply_window_hours: number
  created_at: string
}

export interface CalendarEvent {
  id: string
  title: string
  start: string        // ISO-8601 datetime (timed) or date (all-day)
  end: string
  all_day: boolean
  color_id: string | null
  description: string | null
  location: string | null
  organizer: string | null
  html_link: string | null
  self_response: 'accepted' | 'declined' | 'tentative' | 'needsAction' | null
}

export interface Task {
  id: number
  source: TaskSource
  title: string | null
  notes: string | null
  summary: string | null
  asker: string | null
  extracted_deadline: string | null
  priority: Priority
  completion: Completion
  reply_by: string
  status: Status
  calendar_event_id: string | null
  created_at: string
  updated_at: string
  // null for manual tasks
  sender: string | null
  sender_email: string | null
  subject: string | null
  thread_id: string | null
  received_at: string | null
  // null for non-Slack tasks
  slack_channel_id: string | null
  slack_ts: string | null
  slack_team_id: string | null
  sender_avatar: string | null
  // count of attached links — used for row indicator
  link_count: number
  // true when this task's sender is on the priority_senders list
  is_vip_sender: boolean
}
