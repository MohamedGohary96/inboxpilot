<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { CheckCircle2 as CheckCircleIcon, XCircle as XCircleIcon, RefreshCw as ArrowPathIcon } from 'lucide-vue-next'
import type { ReauthState } from '../types'
import { api } from '../api'

const props = defineProps<{
  state: ReauthState
}>()

const emit = defineEmits<{
  done: []
  error: []
  close: []
}>()

// Poll status while pending
let pollTimer: ReturnType<typeof setInterval> | null = null

async function pollStatus() {
  try {
    const s = await api.getStatus()
    if (s.reauth_state === 'done') {
      stopPolling()
      emit('done')
    } else if (s.reauth_state === 'error') {
      stopPolling()
      emit('error')
    }
  } catch {
    // backend unreachable — keep polling
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(pollStatus, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(() => props.state, (s) => {
  if (s === 'pending') startPolling()
  else stopPolling()
}, { immediate: true })

onUnmounted(stopPolling)

async function onRetry() {
  await api.triggerReauth()
}

async function onClose() {
  await api.resetReauth()
  emit('close')
}
</script>

<template>
  <Transition
    enter-active-class="transition-opacity duration-150"
    enter-from-class="opacity-0"
    leave-active-class="transition-opacity duration-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="state !== 'idle'"
      class="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click.self="state === 'done' || state === 'error' ? onClose() : undefined"
    >
      <div class="bg-surface-card rounded-2xl shadow-dropdown w-full max-w-sm mx-4 overflow-hidden">

        <!-- Pending -->
        <div v-if="state === 'pending'" class="px-8 py-10 flex flex-col items-center text-center gap-5">
          <div class="w-14 h-14 rounded-full bg-brand-50 flex items-center justify-center">
            <ArrowPathIcon class="w-7 h-7 text-brand-primary animate-spin" />
          </div>
          <div>
            <h2 class="text-heading text-grey-900 mb-1.5">Sign in with Google</h2>
            <p class="text-body text-grey-500">
              A browser window has been opened.<br>Complete the sign-in there.
            </p>
          </div>
          <p class="text-caption text-grey-400">Waiting for authentication…</p>
        </div>

        <!-- Done -->
        <div v-else-if="state === 'done'" class="px-8 py-10 flex flex-col items-center text-center gap-5">
          <div class="w-14 h-14 rounded-full bg-green-50 flex items-center justify-center">
            <CheckCircleIcon class="w-7 h-7 text-green-500" />
          </div>
          <div>
            <h2 class="text-heading text-grey-900 mb-1.5">Signed in successfully</h2>
            <p class="text-body text-grey-500">Your account is now connected.</p>
          </div>
          <button
            @click="onClose"
            class="px-6 py-2 bg-brand-primary hover:bg-brand-dark text-white text-body font-semibold rounded-lg transition-colors"
          >
            Done
          </button>
        </div>

        <!-- Error -->
        <div v-else-if="state === 'error'" class="px-8 py-10 flex flex-col items-center text-center gap-5">
          <div class="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center">
            <XCircleIcon class="w-7 h-7 text-red-500" />
          </div>
          <div>
            <h2 class="text-heading text-grey-900 mb-1.5">Authentication failed</h2>
            <p class="text-body text-grey-500">Something went wrong. Check the backend logs and try again.</p>
          </div>
          <div class="flex gap-3">
            <button
              @click="onRetry"
              class="px-5 py-2 bg-brand-primary hover:bg-brand-dark text-white text-body font-semibold rounded-lg transition-colors"
            >
              Retry
            </button>
            <button
              @click="onClose"
              class="px-5 py-2 bg-grey-100 hover:bg-grey-200 text-grey-700 text-body font-semibold rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>

      </div>
    </div>
  </Transition>
</template>
