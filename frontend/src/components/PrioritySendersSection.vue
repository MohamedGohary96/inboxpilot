<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Star, Plus, Trash2, Pencil, Check, X } from 'lucide-vue-next'
import { api } from '../api'
import type { PrioritySender } from '../types'

const senders = ref<PrioritySender[]>([])
const loading = ref(false)
const loadError = ref<string | null>(null)

const adding = ref(false)
const draftEmail = ref('')
const draftNote = ref('')
const draftHours = ref<number>(4)
const addError = ref<string | null>(null)
const addSaving = ref(false)

const editingId = ref<number | null>(null)
const editNote = ref('')
const editHours = ref<number>(4)

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const sortedSenders = computed(() => [...senders.value].sort((a, b) => a.email.localeCompare(b.email)))

async function load() {
  loading.value = true
  loadError.value = null
  try {
    const res = await api.listPrioritySenders()
    senders.value = res.senders
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Could not load priority senders.'
  } finally {
    loading.value = false
  }
}

function startAdd() {
  adding.value = true
  draftEmail.value = ''
  draftNote.value = ''
  draftHours.value = 4
  addError.value = null
}

function cancelAdd() {
  adding.value = false
  addError.value = null
}

async function submitAdd() {
  const email = draftEmail.value.trim()
  if (!EMAIL_RE.test(email)) {
    addError.value = 'Enter a valid email address (e.g. alice@acme.com).'
    return
  }
  if (draftHours.value < 1 || draftHours.value > 168) {
    addError.value = 'Reply window must be between 1 and 168 hours.'
    return
  }
  addSaving.value = true
  addError.value = null
  try {
    const created = await api.addPrioritySender(email, draftHours.value, draftNote.value.trim() || undefined)
    senders.value = [...senders.value, created]
    adding.value = false
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    addError.value = msg.includes('409') ? 'That email is already a priority sender.' : msg
  } finally {
    addSaving.value = false
  }
}

function startEdit(s: PrioritySender) {
  editingId.value = s.id
  editNote.value = s.note ?? ''
  editHours.value = s.reply_window_hours
}

function cancelEdit() {
  editingId.value = null
}

async function submitEdit(id: number) {
  if (editHours.value < 1 || editHours.value > 168) return
  try {
    await api.updatePrioritySender(id, { note: editNote.value.trim(), reply_window_hours: editHours.value })
    const i = senders.value.findIndex(s => s.id === id)
    if (i !== -1) {
      senders.value[i] = { ...senders.value[i], note: editNote.value.trim() || null, reply_window_hours: editHours.value }
    }
    editingId.value = null
  } catch (e) {
    console.error('update sender failed', e)
  }
}

async function remove(id: number) {
  const prev = senders.value
  senders.value = senders.value.filter(s => s.id !== id)
  try {
    await api.deletePrioritySender(id)
  } catch (e) {
    senders.value = prev
    console.error('delete sender failed', e)
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2">
      <Star class="w-3.5 h-3.5 text-brand-primary fill-brand-primary" />
      <p class="text-caption font-bold text-grey-700 uppercase tracking-wide">Priority senders</p>
    </div>
    <p class="text-caption text-grey-500 -mt-1">
      Tasks from these people are forced to high priority and use a tighter reply window. Matches both Gmail and Slack by email.
    </p>

    <p v-if="loadError" class="text-caption text-red-500">{{ loadError }}</p>

    <ul v-if="sortedSenders.length" class="space-y-1.5">
      <li
        v-for="s in sortedSenders"
        :key="s.id"
        class="px-3 py-2 rounded-lg border border-grey-100 bg-surface-card"
      >
        <template v-if="editingId === s.id">
          <div class="space-y-1.5">
            <p class="text-body font-semibold text-grey-800 truncate">{{ s.email }}</p>
            <input
              v-model="editNote"
              type="text"
              placeholder="Note (optional)"
              class="w-full px-2 py-1 text-caption text-grey-800 bg-white rounded border border-grey-200 focus:border-brand-light focus:ring-2 focus:ring-brand-lightest outline-none"
            />
            <div class="flex items-center gap-2">
              <input
                v-model.number="editHours"
                type="number"
                min="1" max="168"
                class="w-20 px-2 py-1 text-caption text-grey-800 bg-white rounded border border-grey-200 focus:border-brand-light focus:ring-2 focus:ring-brand-lightest outline-none tabular-nums"
              />
              <span class="text-caption text-grey-500">hours reply window</span>
              <div class="ml-auto flex items-center gap-1">
                <button
                  @click="submitEdit(s.id)"
                  class="p-1 rounded hover:bg-green-100 text-green-600 transition-colors"
                  aria-label="Save changes"
                ><Check class="w-3.5 h-3.5" /></button>
                <button
                  @click="cancelEdit"
                  class="p-1 rounded hover:bg-grey-100 text-grey-500 transition-colors"
                  aria-label="Cancel edit"
                ><X class="w-3.5 h-3.5" /></button>
              </div>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="flex items-center gap-2">
            <div class="flex-1 min-w-0">
              <p class="text-body font-semibold text-grey-800 truncate" :title="s.email">{{ s.email }}</p>
              <div class="flex items-center gap-2 text-caption text-grey-500">
                <span class="tabular-nums">{{ s.reply_window_hours }}h window</span>
                <span v-if="s.note">·</span>
                <span v-if="s.note" class="truncate">{{ s.note }}</span>
              </div>
            </div>
            <button
              @click="startEdit(s)"
              class="p-1 rounded text-grey-400 hover:bg-grey-100 hover:text-grey-700 transition-colors"
              aria-label="Edit sender"
              title="Edit"
            ><Pencil class="w-3.5 h-3.5" /></button>
            <button
              @click="remove(s.id)"
              class="p-1 rounded text-grey-400 hover:bg-red-50 hover:text-red-500 transition-colors"
              aria-label="Remove sender"
              title="Remove"
            ><Trash2 class="w-3.5 h-3.5" /></button>
          </div>
        </template>
      </li>
    </ul>

    <p v-else-if="!loading && !adding" class="text-caption text-grey-400 italic">No priority senders yet.</p>

    <button
      v-if="!adding"
      @click="startAdd"
      class="flex items-center gap-1.5 px-2.5 py-1.5 text-caption font-semibold rounded-lg text-brand-primary hover:bg-brand-lightest transition-colors"
    >
      <Plus class="w-3.5 h-3.5" />
      Add priority sender
    </button>

    <form
      v-if="adding"
      @submit.prevent="submitAdd"
      class="flex flex-col gap-1.5 p-3 bg-brand-50 border border-brand-light rounded-lg"
    >
      <input
        v-model="draftEmail"
        type="email"
        placeholder="alice@acme.com"
        autofocus
        class="px-2 py-1.5 text-body text-grey-800 bg-white rounded border border-grey-200 focus:border-brand-light focus:ring-2 focus:ring-brand-lightest outline-none"
      />
      <input
        v-model="draftNote"
        type="text"
        placeholder="Note (optional, e.g. 'manager')"
        class="px-2 py-1.5 text-body text-grey-800 bg-white rounded border border-grey-200 focus:border-brand-light focus:ring-2 focus:ring-brand-lightest outline-none"
      />
      <div class="flex items-center gap-2">
        <input
          v-model.number="draftHours"
          type="number"
          min="1" max="168"
          class="w-20 px-2 py-1.5 text-body text-grey-800 bg-white rounded border border-grey-200 focus:border-brand-light focus:ring-2 focus:ring-brand-lightest outline-none tabular-nums"
        />
        <span class="text-caption text-grey-600">hours reply window</span>
      </div>
      <p v-if="addError" class="text-caption text-red-500">{{ addError }}</p>
      <div class="flex items-center gap-2 mt-1">
        <button
          type="submit"
          :disabled="addSaving || !draftEmail.trim()"
          class="px-3 py-1.5 text-caption font-semibold bg-brand-primary text-white rounded-lg hover:bg-brand-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >Add</button>
        <button
          type="button"
          @click="cancelAdd"
          class="px-3 py-1.5 text-caption font-semibold text-grey-600 hover:bg-grey-100 rounded-lg transition-colors"
        >Cancel</button>
      </div>
    </form>
  </div>
</template>
