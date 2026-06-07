<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { CircleUser as UserCircleIcon, ChevronDown as ChevronDownIcon, RefreshCw as ArrowPathIcon, LogOut as ArrowRightStartOnRectangleIcon } from 'lucide-vue-next'

const props = defineProps<{
  accountEmail: string | null
  needsReauth?: boolean
}>()

const photoFailed = ref(false)
watch(() => props.accountEmail, () => { photoFailed.value = false })

const emit = defineEmits<{
  reauth: []
  logout: []
}>()

const open = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const showLogoutConfirm = ref(false)

function toggle() {
  open.value = !open.value
  if (!open.value) showLogoutConfirm.value = false
}

function close() {
  open.value = false
  showLogoutConfirm.value = false
}

function onReauth() {
  close()
  emit('reauth')
}

function onLogoutRequest() {
  showLogoutConfirm.value = true
}

function onLogoutConfirm() {
  close()
  emit('logout')
}

function onClickOutside(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    close()
  }
}

onMounted(() => document.addEventListener('mousedown', onClickOutside))
onUnmounted(() => document.removeEventListener('mousedown', onClickOutside))

function initials(email: string | null) {
  if (!email) return '?'
  return email.charAt(0).toUpperCase()
}
</script>

<template>
  <div ref="menuRef" class="relative">
    <button
      @click="toggle"
      class="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
      :aria-expanded="open"
      aria-haspopup="true"
      :title="needsReauth ? 'Gmail session expired — click to reconnect' : 'Gmail connected'"
    >
      <div class="relative">
        <div class="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center text-micro font-bold text-white overflow-hidden">
          <img
            v-if="accountEmail && !photoFailed"
            :src="'/api/me/photo'"
            alt=""
            class="w-full h-full object-cover"
            @error="photoFailed = true"
          />
          <span v-else>{{ initials(accountEmail) }}</span>
        </div>
        <span
          class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-grey-900"
          :class="needsReauth ? 'bg-amber-400 animate-pulse' : 'bg-green-400'"
          aria-hidden="true"
        ></span>
      </div>
      <span v-if="accountEmail" class="text-caption max-w-[120px] truncate hidden sm:block">{{ accountEmail }}</span>
      <ChevronDownIcon class="w-3 h-3 shrink-0 transition-transform" :class="open ? 'rotate-180' : ''" />
    </button>

    <Transition
      enter-active-class="transition-all duration-100 ease-out"
      enter-from-class="opacity-0 scale-95 -translate-y-1"
      leave-active-class="transition-all duration-75 ease-in"
      leave-to-class="opacity-0 scale-95 -translate-y-1"
    >
      <div
        v-if="open"
        class="absolute right-0 top-full mt-1.5 w-64 bg-grey-900 border border-grey-700 rounded-xl shadow-dropdown overflow-hidden z-50"
        role="menu"
      >
        <!-- Account info -->
        <div class="px-4 py-3 border-b border-grey-800">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-full bg-brand-primary/30 flex items-center justify-center text-caption font-bold text-white shrink-0 overflow-hidden">
              <img
                v-if="accountEmail && !photoFailed"
                :src="'/api/me/photo'"
                alt=""
                class="w-full h-full object-cover"
                @error="photoFailed = true"
              />
              <span v-else>{{ initials(accountEmail) }}</span>
            </div>
            <div class="min-w-0">
              <p class="text-caption font-semibold text-white truncate">{{ accountEmail ?? 'Not signed in' }}</p>
              <p class="text-micro flex items-center gap-1" :class="needsReauth ? 'text-amber-400' : 'text-green-400'">
                <span class="w-1.5 h-1.5 rounded-full" :class="needsReauth ? 'bg-amber-400 animate-pulse' : 'bg-green-400'"></span>
                {{ needsReauth ? 'Session expired' : 'Connected' }}
              </p>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="py-1">
          <button
            @click="onReauth"
            class="w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-caption transition-colors"
            :class="needsReauth ? 'text-amber-300 hover:bg-amber-950/40 hover:text-amber-200' : 'text-grey-200 hover:bg-grey-800 hover:text-white'"
            role="menuitem"
          >
            <ArrowPathIcon class="w-4 h-4 shrink-0" :class="needsReauth ? 'text-amber-400' : 'text-grey-400'" />
            <div>
              <p class="font-medium">{{ needsReauth ? 'Reconnect Gmail' : 'Re-authenticate' }}</p>
              <p class="text-micro" :class="needsReauth ? 'text-amber-400/70' : 'text-grey-500'">
                {{ needsReauth ? 'Token expired — sign in again to resume syncing' : 'Refresh token or update scopes' }}
              </p>
            </div>
          </button>

          <div class="h-px bg-grey-800 mx-4 my-1" />

          <template v-if="!showLogoutConfirm">
            <button
              @click="onLogoutRequest"
              class="w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-caption text-red-400 hover:bg-red-950/50 hover:text-red-300 transition-colors"
              role="menuitem"
            >
              <ArrowRightStartOnRectangleIcon class="w-4 h-4 shrink-0" />
              Sign out
            </button>
          </template>
          <template v-else>
            <div class="px-4 py-2.5 space-y-2">
              <p class="text-caption text-grey-300">Sign out and clear credentials?</p>
              <div class="flex gap-2">
                <button
                  @click="onLogoutConfirm"
                  class="flex-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-caption font-semibold rounded-lg transition-colors"
                >
                  Sign out
                </button>
                <button
                  @click="showLogoutConfirm = false"
                  class="flex-1 px-3 py-1.5 bg-grey-700 hover:bg-grey-600 text-grey-200 text-caption font-semibold rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </div>
</template>
