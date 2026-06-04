<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ChevronLeft as ChevronLeftIcon, ChevronRight as ChevronRightIcon, MapPin as MapPinIcon } from 'lucide-vue-next'
import { api } from '../api'
import type { CalendarEvent } from '../types'

// ── Constants ────────────────────────────────────────────────────────────────
const HOUR_START = 6   // 6 AM
const HOUR_END   = 22  // 10 PM (exclusive — grid shows up to this line)
const PX_PER_HOUR = 64
const TOTAL_HEIGHT = (HOUR_END - HOUR_START) * PX_PER_HOUR

const HOURS = Array.from({ length: HOUR_END - HOUR_START + 1 }, (_, i) => HOUR_START + i)

// Google Calendar color IDs → CSS color
const GCal_COLORS: Record<string, string> = {
  '1':  '#7986cb', // Lavender
  '2':  '#33b679', // Sage
  '3':  '#8e24aa', // Grape
  '4':  '#e67c73', // Flamingo
  '5':  '#f6bf26', // Banana
  '6':  '#f4511e', // Tangerine
  '7':  '#039be5', // Peacock
  '8':  '#3f51b5', // Blueberry
  '9':  '#0b8043', // Basil
  '10': '#d50000', // Tomato
  '11': '#616161', // Graphite
}
const DEFAULT_COLOR = '#a3007c'

const DAY_NAMES = ['Sat', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']

// ── Week navigation ───────────────────────────────────────────────────────────
// Week runs Sat → Fri. Days off: Friday (getDay=5) and Saturday (getDay=6).
function getSaturday(d: Date): Date {
  const result = new Date(d)
  const dow = result.getDay()
  result.setDate(result.getDate() - (dow - 6 + 7) % 7)
  result.setHours(0, 0, 0, 0)
  return result
}

function isDayOff(d: Date) { return d.getDay() === 5 || d.getDay() === 6 }

const weekStart = ref(getSaturday(new Date()))

const days = computed(() =>
  Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart.value)
    d.setDate(weekStart.value.getDate() + i)
    return d
  })
)

function prevWeek() { weekStart.value = new Date(weekStart.value.getTime() - 7 * 86400_000) }
function nextWeek() { weekStart.value = new Date(weekStart.value.getTime() + 7 * 86400_000) }
function goToToday() { weekStart.value = getSaturday(new Date()) }

const weekRangeLabel = computed(() => {
  const s = days.value[0]
  const e = days.value[6]
  const fmtDate = (d: Date) => d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  const year = e.getFullYear()
  if (s.getMonth() === e.getMonth()) {
    return `${s.toLocaleDateString([], { month: 'long' })} ${s.getDate()}–${e.getDate()}, ${year}`
  }
  return `${fmtDate(s)} – ${fmtDate(e)}, ${year}`
})

// ── Today detection ────────────────────────────────────────────────────────
const todayStr = ref(new Date().toDateString())

function isToday(d: Date) { return d.toDateString() === todayStr.value }

// Refresh "today" marker at midnight
let todayTimer: ReturnType<typeof setTimeout> | null = null
function scheduleTodayRefresh() {
  const now = new Date()
  const msUntilMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).getTime() - now.getTime()
  todayTimer = setTimeout(() => {
    todayStr.value = new Date().toDateString()
    scheduleTodayRefresh()
  }, msUntilMidnight)
}
onMounted(scheduleTodayRefresh)
onUnmounted(() => { if (todayTimer) clearTimeout(todayTimer) })

// ── Current time indicator ─────────────────────────────────────────────────
const now = ref(new Date())
let clockTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => { clockTimer = setInterval(() => { now.value = new Date() }, 60_000) })
onUnmounted(() => { if (clockTimer) clearInterval(clockTimer) })

const currentTimeOffset = computed(() => {
  const h = now.value.getHours() + now.value.getMinutes() / 60
  return (h - HOUR_START) * PX_PER_HOUR
})

// ── Data fetching ──────────────────────────────────────────────────────────
const events = ref<CalendarEvent[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

async function fetchEvents() {
  loading.value = true
  error.value = null
  try {
    const from = new Date(weekStart.value)
    const to = new Date(weekStart.value)
    to.setDate(to.getDate() + 7)
    const res = await api.getCalendarEvents(from, to)
    events.value = res.events
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    console.error('[CalendarView] fetchEvents failed:', e)
    if (msg.includes('503')) {
      error.value = 'Calendar not connected — run todo-mail start to authenticate.'
    } else {
      error.value = `Could not load calendar events: ${msg}`
    }
  } finally {
    loading.value = false
  }
}

watch(weekStart, fetchEvents)
onMounted(fetchEvents)

// ── Event helpers ─────────────────────────────────────────────────────────
const allDayEvents = computed(() =>
  events.value.filter(e => e.all_day)
)

// Return "YYYY-MM-DD" in the user's local timezone.
function localDateStr(d: Date): string {
  return (
    `${d.getFullYear()}-` +
    `${String(d.getMonth() + 1).padStart(2, '0')}-` +
    `${String(d.getDate()).padStart(2, '0')}`
  )
}

function eventsForDay(day: Date): CalendarEvent[] {
  const dateStr = localDateStr(day)
  return events.value.filter(e => {
    if (e.all_day) return false
    // Parse the event start (may carry its own UTC offset); compare in local time.
    return localDateStr(new Date(e.start)) === dateStr
  })
}

function allDayEventsForDay(day: Date): CalendarEvent[] {
  const dateStr = localDateStr(day)
  return allDayEvents.value.filter(e => {
    // all-day event start/end are plain date strings like "2026-04-25"
    return e.start <= dateStr && dateStr < e.end
  })
}

function hasAllDayEvents(day: Date): boolean {
  return allDayEventsForDay(day).length > 0
}

const showAllDayRow = computed(() => days.value.some(hasAllDayEvents))

function eventColor(event: CalendarEvent): string {
  return event.color_id ? (GCal_COLORS[event.color_id] ?? DEFAULT_COLOR) : DEFAULT_COLOR
}

function eventTop(event: CalendarEvent): number {
  const d = new Date(event.start)
  const hours = d.getHours() + d.getMinutes() / 60
  return Math.max(0, (hours - HOUR_START) * PX_PER_HOUR)
}

function eventHeight(event: CalendarEvent): number {
  const start = new Date(event.start)
  const end = new Date(event.end)
  const durationHours = (end.getTime() - start.getTime()) / 3_600_000
  return Math.max(20, durationHours * PX_PER_HOUR)
}

function formatHour(h: number): string {
  if (h === 0)  return '12 AM'
  if (h < 12)  return `${h} AM`
  if (h === 12) return '12 PM'
  return `${h - 12} PM`
}

function formatEventTime(event: CalendarEvent): string {
  const d = new Date(event.start)
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function openEvent(event: CalendarEvent) {
  if (!event.html_link) return
  const w = 960, h = 700
  const left = Math.round((screen.width  - w) / 2)
  const top  = Math.round((screen.height - h) / 2)
  window.open(
    event.html_link,
    'gcal-event',
    `width=${w},height=${h},left=${left},top=${top},resizable=yes,scrollbars=yes`
  )
}

const responseLabel: Record<string, string> = {
  accepted:      'Accepted',
  declined:      'Declined',
  tentative:     'Maybe',
  needsAction:   'Invited',
}

// ── Overlap columns ────────────────────────────────────────────────────────
// For each day, assign events to non-overlapping columns so they're legible.
interface PlacedEvent { event: CalendarEvent; col: number; cols: number }

function placeEvents(dayEvents: CalendarEvent[]): PlacedEvent[] {
  // Sort by start time
  const sorted = [...dayEvents].sort((a, b) => a.start.localeCompare(b.start))
  const placed: PlacedEvent[] = []
  const columns: Date[] = [] // tracks end-time of last event in each column

  for (const ev of sorted) {
    const start = new Date(ev.start)
    const end   = new Date(ev.end)
    let col = columns.findIndex(endTime => endTime <= start)
    if (col === -1) { col = columns.length; columns.push(end) }
    else            { columns[col] = end }
    placed.push({ event: ev, col, cols: 0 })
  }

  // Second pass: set cols = total concurrent columns at that time
  for (const p of placed) {
    const start = new Date(p.event.start)
    const end   = new Date(p.event.end)
    let maxCol = p.col
    for (const q of placed) {
      const qs = new Date(q.event.start)
      const qe = new Date(q.event.end)
      if (qs < end && qe > start) maxCol = Math.max(maxCol, q.col)
    }
    p.cols = maxCol + 1
  }

  return placed
}
</script>

<template>
  <div class="flex flex-col" style="height: calc(100vh - 3.5rem);">

    <!-- Navigation bar -->
    <div class="bg-surface-card border-b border-grey-100 px-6 py-3 flex items-center gap-4 shrink-0">
      <div class="flex items-center gap-1">
        <button
          @click="prevWeek"
          class="p-1.5 rounded-lg text-grey-500 hover:bg-grey-100 hover:text-grey-800 transition-colors"
          aria-label="Previous week"
        >
          <ChevronLeftIcon class="w-4 h-4" />
        </button>
        <button
          @click="nextWeek"
          class="p-1.5 rounded-lg text-grey-500 hover:bg-grey-100 hover:text-grey-800 transition-colors"
          aria-label="Next week"
        >
          <ChevronRightIcon class="w-4 h-4" />
        </button>
      </div>
      <h2 class="text-heading text-grey-900 font-semibold">{{ weekRangeLabel }}</h2>
      <button
        @click="goToToday"
        class="ml-auto px-3 py-1.5 text-caption font-semibold rounded-lg border border-grey-200 text-grey-600 hover:bg-grey-100 hover:text-grey-900 transition-colors"
      >
        Today
      </button>
    </div>

    <!-- Error banner -->
    <div
      v-if="error"
      class="mx-6 mt-3 px-4 py-3 bg-red-50 border-l-[3px] border-red-400 text-red-700 text-body rounded-lg shrink-0 flex items-center gap-3"
    >
      <span class="flex-1">{{ error }}</span>
      <button
        @click="fetchEvents"
        class="px-3 py-1 text-caption font-semibold bg-red-100 hover:bg-red-200 rounded-lg transition-colors shrink-0"
      >Retry</button>
    </div>

    <!-- Scrollable calendar grid -->
    <div class="flex-1 overflow-hidden flex flex-col min-h-0">
      <!-- Sticky header: day names -->
      <div class="flex shrink-0 border-b border-grey-200 bg-surface-card">
        <!-- gutter column -->
        <div class="w-14 shrink-0" />
        <!-- Day columns header -->
        <div class="flex-1 grid grid-cols-7">
          <div
            v-for="(day, i) in days"
            :key="i"
            class="border-l border-grey-100 text-center py-2"
            :class="isToday(day) ? 'bg-brand-50' : isDayOff(day) ? 'bg-grey-50' : ''"
          >
            <p class="text-micro text-grey-500 font-semibold uppercase tracking-wide">{{ DAY_NAMES[i] }}</p>
            <p
              class="text-body font-bold tabular-nums leading-snug"
              :class="isToday(day) ? 'text-brand-primary' : 'text-grey-700'"
            >
              {{ day.getDate() }}
            </p>
          </div>
        </div>
      </div>

      <!-- All-day events row -->
      <div
        v-if="showAllDayRow"
        class="flex shrink-0 border-b border-grey-100 bg-surface-card"
      >
        <div class="w-14 shrink-0 flex items-center justify-end pr-2">
          <span class="text-micro text-grey-400">all-day</span>
        </div>
        <div class="flex-1 grid grid-cols-7">
          <div
            v-for="(day, i) in days"
            :key="i"
            class="border-l border-grey-100 px-1 py-1 space-y-0.5 min-h-[28px]"
            :class="isToday(day) ? 'bg-brand-50' : isDayOff(day) ? 'bg-grey-50' : ''"
          >
            <div
              v-for="ev in allDayEventsForDay(day)"
              :key="ev.id"
              @click="openEvent(ev)"
              class="rounded px-1.5 py-0.5 text-micro font-semibold text-white truncate cursor-pointer hover:opacity-80 transition-opacity"
              :style="{ backgroundColor: eventColor(ev) }"
              :title="ev.title"
            >
              {{ ev.title }}
            </div>
          </div>
        </div>
      </div>

      <!-- Time grid (scrollable) -->
      <div class="flex-1 overflow-y-auto" style="overscroll-behavior: contain;">
        <!-- Loading skeleton -->
        <div v-if="loading" class="flex">
          <div class="w-14 shrink-0" />
          <div class="flex-1 grid grid-cols-7">
            <div
              v-for="n in 7"
              :key="n"
              class="border-l border-grey-100 p-2 space-y-2"
              :style="{ height: `${TOTAL_HEIGHT}px` }"
            >
              <div
                v-for="sk in 3"
                :key="sk"
                class="h-12 rounded-lg skeleton-shimmer"
                :style="{ marginTop: `${sk * 96}px` }"
              />
            </div>
          </div>
        </div>

        <!-- Actual grid -->
        <div v-else class="flex relative">
          <!-- Time labels column -->
          <div class="w-14 shrink-0 relative" :style="{ height: `${TOTAL_HEIGHT}px` }">
            <div
              v-for="h in HOURS"
              :key="h"
              class="absolute right-0 pr-2 text-right text-micro text-grey-400 leading-none"
              :style="{ top: `${(h - HOUR_START) * PX_PER_HOUR - 6}px`, width: '100%' }"
            >
              {{ h > HOUR_START && h < HOUR_END ? formatHour(h) : '' }}
            </div>
          </div>

          <!-- Day columns -->
          <div class="flex-1 grid grid-cols-7">
            <div
              v-for="(day, di) in days"
              :key="di"
              class="relative border-l border-grey-100"
              :class="isToday(day) ? 'bg-brand-50/40' : isDayOff(day) ? 'bg-grey-50/60' : ''"
              :style="{ height: `${TOTAL_HEIGHT}px` }"
            >
              <!-- Hour lines -->
              <div
                v-for="h in HOURS"
                :key="h"
                class="absolute inset-x-0 border-b"
                :class="h % 2 === 0 ? 'border-grey-200' : 'border-grey-100'"
                :style="{ top: `${(h - HOUR_START) * PX_PER_HOUR}px` }"
              />

              <!-- Current time indicator -->
              <div
                v-if="isToday(day)"
                class="absolute inset-x-0 z-20 flex items-center pointer-events-none"
                :style="{ top: `${currentTimeOffset}px` }"
              >
                <div class="w-2 h-2 rounded-full bg-brand-primary shrink-0 -ml-1" />
                <div class="flex-1 border-t border-brand-primary" />
              </div>

              <!-- Events -->
              <template v-for="p in placeEvents(eventsForDay(day))" :key="p.event.id">
                <div
                  @click="openEvent(p.event)"
                  class="absolute rounded-lg overflow-hidden cursor-pointer hover:brightness-110 transition-all shadow-sm group"
                  :style="{
                    top:    `${eventTop(p.event) + 1}px`,
                    height: `${eventHeight(p.event) - 2}px`,
                    left:   `${(p.col / p.cols) * 100}%`,
                    width:  `${(1 / p.cols) * 100 - 1}%`,
                    backgroundColor: eventColor(p.event),
                    zIndex: 10 + p.col,
                  }"
                  :title="p.event.title"
                >
                  <div class="px-1.5 py-1 h-full flex flex-col overflow-hidden">
                    <p class="text-micro font-bold text-white leading-tight truncate">
                      {{ p.event.title }}
                    </p>
                    <p v-if="eventHeight(p.event) >= 32" class="text-micro text-white/80 leading-tight">
                      {{ formatEventTime(p.event) }}
                    </p>
                    <div
                      v-if="p.event.location && eventHeight(p.event) >= 48"
                      class="flex items-center gap-0.5 mt-auto"
                    >
                      <MapPinIcon class="w-2.5 h-2.5 text-white/70 shrink-0" />
                      <p class="text-micro text-white/70 truncate">{{ p.event.location }}</p>
                    </div>
                  </div>

                  <!-- Response badge -->
                  <div
                    v-if="p.event.self_response && p.event.self_response !== 'accepted'"
                    class="absolute top-0 right-0 m-0.5 px-1 rounded text-micro font-bold text-white/90"
                    :class="p.event.self_response === 'declined' ? 'bg-red-800/40' : 'bg-black/20'"
                  >
                    {{ responseLabel[p.event.self_response] }}
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- Empty state (no events, not loading) -->
        <div
          v-if="!loading && !error && events.filter(e => !e.all_day).length === 0"
          class="absolute inset-0 flex items-center justify-center pointer-events-none"
        >
          <div class="text-center space-y-1.5">
            <p class="text-heading text-grey-500">No events this week</p>
            <p class="text-body text-grey-400">Enjoy the open calendar.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
