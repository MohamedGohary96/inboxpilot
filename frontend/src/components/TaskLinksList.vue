<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, Trash2, ExternalLink, Link as LinkIcon } from 'lucide-vue-next'
import type { TaskLink } from '../types'

const props = defineProps<{ taskId: number; links: TaskLink[] }>()
const emit = defineEmits<{ add: [data: { url: string; label?: string }]; remove: [linkId: number] }>()

const adding = ref(false)
const draftUrl = ref('')
const draftLabel = ref('')
const error = ref<string | null>(null)
const saving = ref(false)

function startAdd() {
  adding.value = true
  draftUrl.value = ''
  draftLabel.value = ''
  error.value = null
}

function cancelAdd() {
  adding.value = false
  error.value = null
}

function isValidUrl(s: string): boolean {
  return /^https?:\/\/\S+/.test(s.trim())
}

async function submit() {
  const url = draftUrl.value.trim()
  if (!isValidUrl(url)) {
    error.value = 'URL must start with http:// or https://'
    return
  }
  saving.value = true
  error.value = null
  try {
    emit('add', { url, label: draftLabel.value.trim() || undefined })
    adding.value = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Could not add link'
  } finally {
    saving.value = false
  }
}

function hostnameOf(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}

function displayLabel(link: TaskLink): string {
  return link.label?.trim() || hostnameOf(link.url)
}

const empty = computed(() => props.links.length === 0 && !adding.value)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-1.5">
      <span class="text-micro font-extrabold uppercase tracking-widest text-grey-500">
        Links<span v-if="links.length"> · {{ links.length }}</span>
      </span>
      <button
        v-if="!adding"
        type="button"
        @click="startAdd"
        class="flex items-center gap-1 px-2 py-0.5 text-micro font-semibold rounded text-brand-primary hover:bg-brand-lightest transition-colors"
      >
        <Plus class="w-3 h-3" />
        Add link
      </button>
    </div>

    <ul v-if="links.length" class="space-y-1 mb-2">
      <li
        v-for="link in links"
        :key="link.id"
        class="group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-grey-50 transition-colors"
      >
        <LinkIcon class="w-3.5 h-3.5 text-grey-400 shrink-0" />
        <a
          :href="link.url"
          target="_blank"
          rel="noopener noreferrer"
          @click.stop
          class="flex-1 text-body text-grey-800 truncate hover:text-brand-primary hover:underline"
          :title="link.url"
        >
          {{ displayLabel(link) }}
        </a>
        <a
          :href="link.url"
          target="_blank"
          rel="noopener noreferrer"
          @click.stop
          class="text-grey-400 hover:text-brand-primary transition-colors"
          aria-label="Open link"
        >
          <ExternalLink class="w-3.5 h-3.5" />
        </a>
        <button
          type="button"
          @click.stop="emit('remove', link.id)"
          class="text-grey-400 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
          aria-label="Remove link"
          title="Remove link"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>
      </li>
    </ul>

    <div v-else-if="empty" class="text-caption text-grey-400 italic mb-2">No links attached.</div>

    <form
      v-if="adding"
      @submit.prevent="submit"
      class="flex flex-col gap-1.5 p-2 bg-surface-card border border-grey-200 rounded-lg"
      @click.stop
    >
      <input
        v-model="draftUrl"
        type="url"
        placeholder="https://…"
        autofocus
        class="px-2 py-1 text-body text-grey-800 bg-white rounded border border-grey-200 focus:border-brand-light focus:ring-2 focus:ring-brand-lightest outline-none"
        style="font-size:13px"
      />
      <input
        v-model="draftLabel"
        type="text"
        placeholder="Label (optional)"
        class="px-2 py-1 text-body text-grey-800 bg-white rounded border border-grey-200 focus:border-brand-light focus:ring-2 focus:ring-brand-lightest outline-none"
        style="font-size:13px"
      />
      <p v-if="error" class="text-caption text-red-500">{{ error }}</p>
      <div class="flex items-center gap-2 mt-1">
        <button
          type="submit"
          :disabled="saving || !draftUrl.trim()"
          class="px-3 py-1 text-caption font-semibold bg-brand-primary text-white rounded-lg hover:bg-brand-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Add
        </button>
        <button
          type="button"
          @click="cancelAdd"
          class="px-3 py-1 text-caption font-semibold text-grey-600 hover:bg-grey-100 rounded-lg transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  </div>
</template>
