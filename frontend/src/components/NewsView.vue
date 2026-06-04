<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Github as GithubIcon,
  Tag as TagIcon,
  ShieldAlert as ShieldAlertIcon,
  MessageSquare as MessageSquareIcon,
  Newspaper as NewspaperIcon,
  GitPullRequest as GitPullRequestIcon,
  CircleAlert as CircleAlertIcon,
  Sparkles as SparklesIcon,
  CheckCircle2 as CheckCircle2Icon,
  X as XMarkIcon,
  ExternalLink as ArrowTopRightOnSquareIcon,
  RefreshCw as ArrowPathIcon,
  ChevronDown as ChevronDownIcon,
} from 'lucide-vue-next'
import { api } from '../api'
import type { NewsItem, NewsCategory } from '../types'

const items = ref<NewsItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const activeCategory = ref<NewsCategory | 'all'>('all')
const collapsedRepos = ref<Set<string>>(new Set())
const summarizingIds = ref<Set<number>>(new Set())

const CATEGORIES: { id: NewsCategory | 'all'; label: string; icon: typeof TagIcon }[] = [
  { id: 'all',          label: 'All',           icon: NewspaperIcon },
  { id: 'pull_request', label: 'Pull Requests', icon: GitPullRequestIcon },
  { id: 'issue',        label: 'Issues',        icon: CircleAlertIcon },
  { id: 'release',      label: 'Releases',      icon: TagIcon },
  { id: 'security',     label: 'Security',      icon: ShieldAlertIcon },
  { id: 'discussion',   label: 'Discussions',   icon: MessageSquareIcon },
  { id: 'newsletter',   label: 'Newsletter',    icon: NewspaperIcon },
]

const CATEGORY_ICON: Record<NewsCategory, typeof TagIcon> = {
  release:      TagIcon,
  security:     ShieldAlertIcon,
  discussion:   MessageSquareIcon,
  newsletter:   NewspaperIcon,
  pull_request: GitPullRequestIcon,
  issue:        CircleAlertIcon,
}

const CATEGORY_LABEL: Record<NewsCategory, string> = {
  release:      'release',
  security:     'security',
  discussion:   'discussion',
  newsletter:   'newsletter',
  pull_request: 'pull request',
  issue:        'issue',
}

const CATEGORY_STYLE: Record<NewsCategory, { dot: string; text: string; bg: string }> = {
  release:      { dot: 'bg-green-500',  text: 'text-green-700',  bg: 'bg-green-50' },
  security:     { dot: 'bg-red-500',    text: 'text-red-700',    bg: 'bg-red-50'   },
  discussion:   { dot: 'bg-blue-500',   text: 'text-blue-700',   bg: 'bg-blue-50'  },
  newsletter:   { dot: 'bg-grey-400',   text: 'text-grey-700',   bg: 'bg-grey-100' },
  pull_request: { dot: 'bg-purple-500', text: 'text-purple-700', bg: 'bg-purple-50'},
  issue:        { dot: 'bg-amber-500',  text: 'text-amber-700',  bg: 'bg-amber-50' },
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const cat = activeCategory.value === 'all' ? undefined : activeCategory.value
    const res = await api.listNews(cat)
    items.value = res.items
  } catch (e: any) {
    error.value = e?.message || 'Could not load news'
  } finally {
    loading.value = false
  }
}

function selectCategory(c: NewsCategory | 'all') {
  activeCategory.value = c
  load()
}

const grouped = computed(() => {
  const groups = new Map<string, NewsItem[]>()
  for (const it of items.value) {
    const key = it.news_repo || 'General'
    const list = groups.get(key) || []
    list.push(it)
    groups.set(key, list)
  }
  return Array.from(groups.entries()).sort((a, b) => {
    if (a[0] === 'General') return 1
    if (b[0] === 'General') return -1
    return a[0].localeCompare(b[0])
  })
})

function toggleRepo(repo: string) {
  const next = new Set(collapsedRepos.value)
  if (next.has(repo)) next.delete(repo)
  else next.add(repo)
  collapsedRepos.value = next
}

async function generateSummary(item: NewsItem) {
  if (item.news_summary || summarizingIds.value.has(item.id)) return
  summarizingIds.value = new Set([...summarizingIds.value, item.id])
  try {
    const res = await api.summarizeNews(item.id)
    item.news_summary = res.summary
  } catch { /* leave summary empty, user can retry */ }
  finally {
    const next = new Set(summarizingIds.value)
    next.delete(item.id)
    summarizingIds.value = next
  }
}

async function dismiss(item: NewsItem) {
  items.value = items.value.filter(x => x.id !== item.id)
  try {
    await api.dismissNews(item.id)
  } catch {
    items.value.unshift(item)  // rollback on error
  }
}

function eventSubtitle(item: NewsItem): string | null {
  const s = item.snippet || ''
  if (!s) return null
  const cut = s.split(/—|Reply to this email|View it on GitHub|You are receiving/i)[0].trim()
  return cut.length > 3 ? cut : null
}

function gmailUrl(item: NewsItem): string {
  const id = item.thread_id || item.gmail_message_id
  return `https://mail.google.com/mail/u/0/#inbox/${id}`
}

function githubUrl(item: NewsItem): string | null {
  if (!item.news_repo) return null
  const pr = item.subject.match(/\(PR\s*#(\d+)\)/i)
  if (pr) return `https://github.com/${item.news_repo}/pull/${pr[1]}`
  const iss = item.subject.match(/\(Issue\s*#(\d+)\)/i)
  if (iss) return `https://github.com/${item.news_repo}/issues/${iss[1]}`
  const disc = item.subject.match(/discussion\s*#(\d+)/i)
  if (disc) return `https://github.com/${item.news_repo}/discussions/${disc[1]}`
  switch (item.news_category) {
    case 'release':      return `https://github.com/${item.news_repo}/releases`
    case 'discussion':   return `https://github.com/${item.news_repo}/discussions`
    case 'security':     return `https://github.com/${item.news_repo}/security`
    case 'pull_request': return `https://github.com/${item.news_repo}/pulls`
    case 'issue':        return `https://github.com/${item.news_repo}/issues`
    default:             return `https://github.com/${item.news_repo}`
  }
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1)  return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24)   return `${diffH}h ago`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7)    return `${diffD}d ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

onMounted(load)

defineExpose({ refresh: load })
</script>

<template>
  <section class="max-w-workbench mx-auto px-6 py-6 space-y-4">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <GithubIcon class="w-5 h-5 text-grey-700" />
        <h1 class="text-heading text-grey-900">GitHub News</h1>
        <span class="text-caption text-grey-500 tabular-nums">{{ items.length }}</span>
      </div>
      <button
        @click="load"
        :disabled="loading"
        class="flex items-center gap-1.5 px-3 py-1.5 text-caption text-grey-700 hover:bg-grey-100 rounded-lg transition-colors disabled:opacity-50"
        title="Refresh"
      >
        <ArrowPathIcon class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" />
        Refresh
      </button>
    </div>

    <!-- Category chips -->
    <div class="flex flex-wrap gap-2">
      <button
        v-for="c in CATEGORIES"
        :key="c.id"
        @click="selectCategory(c.id)"
        :class="[
          'flex items-center gap-1.5 px-3 py-1.5 rounded-pill text-caption font-semibold transition-all',
          activeCategory === c.id
            ? 'bg-brand-primary text-white'
            : 'bg-surface-card text-grey-700 border border-grey-300 hover:bg-grey-50'
        ]"
      >
        <component :is="c.icon" class="w-3.5 h-3.5" />
        {{ c.label }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="px-4 py-3 bg-red-50 border-l-[3px] border-red-500 text-red-700 rounded-lg text-body">
      {{ error }}
    </div>

    <!-- Empty -->
    <div v-if="!loading && items.length === 0" class="bg-surface-card rounded-xl shadow-card px-8 py-12 text-center">
      <GithubIcon class="w-10 h-10 text-grey-300 mx-auto mb-3" />
      <p class="text-body text-grey-500">No GitHub news to show.</p>
      <p class="text-caption text-grey-400 mt-1">Releases, security advisories, and discussions will appear here.</p>
    </div>

    <!-- Grouped list -->
    <div v-for="[repo, list] in grouped" :key="repo" class="bg-surface-card rounded-xl shadow-card overflow-hidden">
      <button
        @click="toggleRepo(repo)"
        class="w-full flex items-center justify-between px-4 py-3 hover:bg-grey-50 transition-colors text-left"
      >
        <div class="flex items-center gap-2 min-w-0">
          <GithubIcon class="w-4 h-4 text-grey-500 shrink-0" />
          <span class="text-body font-semibold text-grey-900 truncate">{{ repo }}</span>
          <span class="text-caption text-grey-500 tabular-nums shrink-0">{{ list.length }}</span>
        </div>
        <ChevronDownIcon class="w-4 h-4 text-grey-400 transition-transform shrink-0" :class="{ '-rotate-90': collapsedRepos.has(repo) }" />
      </button>

      <ul v-if="!collapsedRepos.has(repo)" class="divide-y divide-grey-100">
        <li
          v-for="item in list"
          :key="item.id"
          class="px-4 py-3 hover:bg-grey-50 transition-colors group"
        >
          <div class="flex items-start gap-3">
            <!-- Category icon -->
            <div
              :class="[
                'w-7 h-7 rounded-lg flex items-center justify-center shrink-0',
                CATEGORY_STYLE[item.news_category].bg,
              ]"
              :title="item.news_category"
            >
              <component
                :is="CATEGORY_ICON[item.news_category]"
                :class="['w-3.5 h-3.5', CATEGORY_STYLE[item.news_category].text]"
              />
            </div>

            <!-- Content -->
            <div class="min-w-0 flex-1">
              <p class="text-body text-grey-900 leading-snug">{{ item.subject }}</p>

              <p v-if="eventSubtitle(item)" class="text-caption text-grey-700 mt-0.5">
                {{ eventSubtitle(item) }}
              </p>

              <p v-if="item.news_summary" class="text-caption text-grey-600 mt-1 italic">
                {{ item.news_summary }}
              </p>
              <p v-else-if="summarizingIds.has(item.id)" class="text-caption text-grey-400 mt-1 flex items-center gap-1">
                <ArrowPathIcon class="w-3 h-3 animate-spin" />
                Summarizing…
              </p>

              <div class="flex items-center gap-3 mt-1.5 text-caption text-grey-500">
                <span :class="['inline-flex items-center gap-1 capitalize', CATEGORY_STYLE[item.news_category].text]">
                  <span :class="['w-1.5 h-1.5 rounded-full', CATEGORY_STYLE[item.news_category].dot]"></span>
                  {{ CATEGORY_LABEL[item.news_category] }}
                </span>
                <span
                  v-if="item.is_task"
                  class="inline-flex items-center gap-1 text-brand-primary"
                  title="This message is also tracked as a task"
                >
                  <CheckCircle2Icon class="w-3 h-3" />
                  task
                </span>
                <span>{{ formatTime(item.received_at) }}</span>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
              <button
                v-if="!item.news_summary && !summarizingIds.has(item.id)"
                @click="generateSummary(item)"
                title="AI summary"
                class="p-1.5 rounded-lg text-grey-500 hover:text-brand-primary hover:bg-brand-50 transition-colors"
              >
                <SparklesIcon class="w-3.5 h-3.5" />
              </button>
              <a
                v-if="githubUrl(item)"
                :href="githubUrl(item)!"
                target="_blank"
                rel="noopener"
                title="Open in GitHub"
                class="p-1.5 rounded-lg text-grey-500 hover:text-grey-900 hover:bg-grey-100 transition-colors"
              >
                <GithubIcon class="w-3.5 h-3.5" />
              </a>
              <a
                :href="gmailUrl(item)"
                target="_blank"
                rel="noopener"
                title="Open in Gmail"
                class="p-1.5 rounded-lg text-grey-500 hover:text-brand-primary hover:bg-brand-50 transition-colors"
              >
                <ArrowTopRightOnSquareIcon class="w-3.5 h-3.5" />
              </a>
              <button
                @click="dismiss(item)"
                title="Dismiss"
                class="p-1.5 rounded-lg text-grey-500 hover:text-red-600 hover:bg-red-50 transition-colors"
              >
                <XMarkIcon class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </section>
</template>
