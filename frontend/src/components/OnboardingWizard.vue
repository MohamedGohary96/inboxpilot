<script setup lang="ts">
import { ref } from 'vue'
import { Upload as UploadIcon, Check as CheckIcon, ExternalLink as ExternalLinkIcon } from 'lucide-vue-next'
import { api } from '../api'

const emit = defineEmits<{ done: [] }>()

const step = ref<1 | 2 | 3>(1)

// ── Step 2: credentials upload ────────────────────────────────────────
const dragging      = ref(false)
const uploading     = ref(false)
const uploadDone    = ref(false)
const uploadError   = ref<string | null>(null)

function onDragOver(e: DragEvent) {
  e.preventDefault()
  dragging.value = true
}

function onDragLeave() {
  dragging.value = false
}

async function onDrop(e: DragEvent) {
  e.preventDefault()
  dragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) await uploadFile(file)
}

async function onFileInput(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) await uploadFile(file)
}

async function uploadFile(file: File) {
  uploadError.value = null
  uploading.value = true
  try {
    await api.uploadCredentials(file)
    uploadDone.value = true
  } catch (err: unknown) {
    uploadError.value = err instanceof Error ? err.message : 'Upload failed'
  } finally {
    uploading.value = false
  }
}

// ── Step 3: Gmail OAuth ───────────────────────────────────────────────
const connecting    = ref(false)
const connectError  = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

async function connectGmail() {
  connecting.value = true
  connectError.value = null
  try {
    await api.triggerReauth()
    pollTimer = setInterval(async () => {
      try {
        const status = await api.getStatus()
        if (status.authenticated) {
          clearInterval(pollTimer!)
          pollTimer = null
          emit('done')
        } else if (status.reauth_state === 'error') {
          clearInterval(pollTimer!)
          pollTimer = null
          connectError.value = 'Sign-in failed. Please try again.'
          connecting.value = false
        }
      } catch { /* backend busy — keep polling */ }
    }, 1500)
  } catch {
    connectError.value = 'Could not start sign-in flow. Is the server running?'
    connecting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-surface-page flex items-center justify-center px-4 py-12">
    <div class="w-full max-w-lg">

      <!-- Logo + title -->
      <div class="flex flex-col items-center gap-3 mb-8">
        <img src="/icon-192.png" alt="InboxPilot" class="w-16 h-16 rounded-2xl shadow-card" />
        <h1 class="text-2xl font-bold text-grey-900 tracking-tight">InboxPilot</h1>
      </div>

      <!-- Step indicators -->
      <div class="flex items-center justify-center gap-2 mb-8">
        <template v-for="n in 3" :key="n">
          <div
            :class="[
              'w-8 h-8 rounded-full flex items-center justify-center text-caption font-bold transition-all',
              step === n
                ? 'bg-brand-primary text-white shadow-sm'
                : step > n
                  ? 'bg-brand-primary text-white opacity-40'
                  : 'bg-grey-100 text-grey-400',
            ]"
          >
            <CheckIcon v-if="step > n" class="w-4 h-4" />
            <span v-else>{{ n }}</span>
          </div>
          <div v-if="n < 3" class="w-12 h-0.5 rounded-full" :class="step > n ? 'bg-brand-primary opacity-40' : 'bg-grey-200'" />
        </template>
      </div>

      <!-- Card -->
      <div class="bg-surface-card rounded-2xl shadow-card px-8 py-8 space-y-6">

        <!-- ── Step 1: Welcome ─────────────────────────────────────── -->
        <template v-if="step === 1">
          <div class="text-center space-y-3">
            <h2 class="text-xl font-bold text-grey-900">Welcome to InboxPilot</h2>
            <p class="text-body text-grey-500 leading-relaxed">
              Your AI-powered email triage tool. InboxPilot scans your Gmail inbox, finds emails that need a reply, and helps you stay on top of your workload.
            </p>
          </div>

          <div class="space-y-3">
            <p class="text-caption font-bold text-grey-600 uppercase tracking-wide">What you'll need</p>
            <div class="space-y-2.5">
              <div v-for="item in [
                { icon: '📁', text: 'A Google Cloud credentials file (client_secrets.json) — we\'ll walk you through creating it' },
                { icon: '📬', text: 'A Google account with Gmail' },
                { icon: '⚡', text: 'An AI provider API key (you can add this later)' },
              ]" :key="item.text" class="flex items-start gap-3">
                <span class="text-lg shrink-0 mt-0.5">{{ item.icon }}</span>
                <p class="text-body text-grey-600">{{ item.text }}</p>
              </div>
            </div>
          </div>

          <button
            @click="step = 2"
            class="w-full py-3 rounded-xl bg-brand-primary hover:bg-brand-dark text-white font-semibold text-body transition-colors"
          >
            Get started →
          </button>
        </template>

        <!-- ── Step 2: Credentials ─────────────────────────────────── -->
        <template v-else-if="step === 2">
          <div class="space-y-1.5">
            <h2 class="text-xl font-bold text-grey-900">Connect Google</h2>
            <p class="text-body text-grey-500">
              InboxPilot needs a Google Cloud credentials file to access your Gmail. Follow the steps below, then drop the file here.
            </p>
          </div>

          <!-- Instructions -->
          <details class="group">
            <summary class="cursor-pointer select-none list-none flex items-center justify-between py-2.5 px-3 rounded-lg bg-brand-50 hover:bg-brand-lightest transition-colors">
              <span class="text-caption font-semibold text-brand-darkest">How to create the credentials file</span>
              <span class="text-brand-primary transition-transform duration-150 group-open:rotate-180 text-micro">▼</span>
            </summary>
            <ol class="mt-3 space-y-3 text-caption text-grey-600 list-decimal list-inside px-1">
              <li>
                <a href="https://console.cloud.google.com/projectcreate" target="_blank" rel="noopener"
                   class="text-brand-primary hover:underline inline-flex items-center gap-1">
                  Open Google Cloud Console <ExternalLinkIcon class="w-3 h-3" />
                </a>
                — create a new project named <strong class="text-grey-800">InboxPilot</strong>
              </li>
              <li>In the search bar, search for and enable these APIs:
                <div class="mt-1.5 flex flex-wrap gap-1.5 ml-3">
                  <span v-for="api in ['Gmail API', 'Google Calendar API', 'People API']" :key="api"
                        class="bg-grey-100 text-grey-700 text-micro font-mono px-2 py-0.5 rounded">{{ api }}</span>
                </div>
              </li>
              <li>Go to <strong class="text-grey-800">APIs &amp; Services → Credentials</strong></li>
              <li>If prompted, configure the OAuth consent screen:
                <span class="text-grey-500"> User type: External, App name: InboxPilot — save and continue through all steps</span>
              </li>
              <li>Click <strong class="text-grey-800">+ Create Credentials → OAuth client ID</strong></li>
              <li>Application type: <strong class="text-grey-800">Desktop app</strong> → Create</li>
              <li>Click <strong class="text-grey-800">Download JSON</strong> and save the file</li>
            </ol>
          </details>

          <!-- Drop zone -->
          <div
            @dragover="onDragOver"
            @dragleave="onDragLeave"
            @drop="onDrop"
            :class="[
              'relative border-2 border-dashed rounded-xl px-6 py-8 flex flex-col items-center gap-3 transition-all',
              uploadDone
                ? 'border-green-400 bg-green-50'
                : dragging
                  ? 'border-brand-primary bg-brand-50'
                  : 'border-grey-200 hover:border-grey-300 bg-grey-50',
            ]"
          >
            <template v-if="uploadDone">
              <div class="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                <CheckIcon class="w-6 h-6 text-green-600" />
              </div>
              <p class="text-body font-semibold text-green-700">Credentials file loaded</p>
              <button @click="uploadDone = false; uploadError = null" class="text-caption text-grey-400 hover:text-grey-600 transition-colors">
                Use a different file
              </button>
            </template>
            <template v-else>
              <div class="w-12 h-12 rounded-full bg-grey-100 flex items-center justify-center">
                <UploadIcon class="w-6 h-6 text-grey-400" />
              </div>
              <div class="text-center space-y-1">
                <p class="text-body font-semibold text-grey-700">
                  {{ dragging ? 'Drop it here' : 'Drop client_secrets.json here' }}
                </p>
                <p class="text-caption text-grey-400">or</p>
              </div>
              <label class="cursor-pointer px-4 py-2 rounded-lg bg-white border border-grey-200 hover:border-brand-primary text-caption font-semibold text-grey-700 hover:text-brand-primary transition-colors">
                Browse files
                <input type="file" accept=".json,application/json" class="sr-only" @change="onFileInput" :disabled="uploading" />
              </label>
              <p v-if="uploading" class="text-caption text-brand-primary">Validating…</p>
              <p v-if="uploadError" class="text-caption text-red-600 text-center">{{ uploadError }}</p>
            </template>
          </div>

          <div class="flex gap-3">
            <button @click="step = 1" class="flex-1 py-2.5 rounded-xl border border-grey-200 text-caption font-semibold text-grey-600 hover:bg-grey-50 transition-colors">
              ← Back
            </button>
            <button
              @click="step = 3"
              :disabled="!uploadDone"
              class="flex-1 py-2.5 rounded-xl bg-brand-primary hover:bg-brand-dark text-white font-semibold text-caption transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Continue →
            </button>
          </div>
        </template>

        <!-- ── Step 3: Sign in with Google ────────────────────────── -->
        <template v-else-if="step === 3">
          <div class="space-y-1.5">
            <h2 class="text-xl font-bold text-grey-900">Sign in with Google</h2>
            <p class="text-body text-grey-500">
              Almost there! Click below to open the Google sign-in window and authorize InboxPilot to read your inbox.
            </p>
          </div>

          <div class="bg-surface-sunk rounded-xl px-4 py-4 space-y-2 text-caption text-grey-500">
            <p class="font-semibold text-grey-700">InboxPilot will request access to:</p>
            <div v-for="item in [
              { scope: 'gmail.readonly', desc: 'Read your inbox — no modifications' },
              { scope: 'calendar.events', desc: 'Create events on a dedicated Replies calendar' },
              { scope: 'contacts.readonly', desc: 'Show sender names and photos' },
            ]" :key="item.scope" class="flex items-start gap-2">
              <CheckIcon class="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
              <span><strong class="text-grey-700">{{ item.scope }}</strong> — {{ item.desc }}</span>
            </div>
          </div>

          <p v-if="connectError" class="text-caption text-red-600 bg-red-50 rounded-lg px-3 py-2">{{ connectError }}</p>

          <div class="space-y-3">
            <button
              v-if="!connecting"
              @click="connectGmail"
              class="w-full py-3 rounded-xl bg-brand-primary hover:bg-brand-dark text-white font-semibold text-body transition-colors"
            >
              Connect Gmail →
            </button>
            <div v-else class="w-full py-3 rounded-xl bg-brand-50 border border-brand-light flex items-center justify-center gap-2 text-body font-semibold text-brand-primary">
              <span class="w-4 h-4 border-2 border-brand-primary border-t-transparent rounded-full animate-spin shrink-0"></span>
              Waiting for Google sign-in…
            </div>
            <button v-if="!connecting" @click="step = 2" class="w-full py-2 text-caption text-grey-400 hover:text-grey-600 transition-colors">
              ← Back
            </button>
          </div>

          <p class="text-micro text-grey-400 text-center">
            A browser window will open for Google sign-in. Come back here once you've approved access.
          </p>
        </template>

      </div>
    </div>
  </div>
</template>
