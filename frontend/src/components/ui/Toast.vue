<script setup lang="ts">
import { CheckCircle2 as CheckCircleIcon, XCircle as XCircleIcon, Info as InformationCircleIcon, X as XMarkIcon } from 'lucide-vue-next'
import { useToast, type Toast } from '../../composables/useToast'

const { toasts, dismiss, undo } = useToast()

const iconFor = (type: Toast['type']) => ({
  success: CheckCircleIcon,
  error:   XCircleIcon,
  info:    InformationCircleIcon,
}[type])

const colorFor = (type: Toast['type']) => ({
  success: 'border-l-status-replied text-status-replied',
  error:   'border-l-red-500 text-red-600',
  info:    'border-l-brand-primary text-brand-primary',
}[type])
</script>

<template>
  <Teleport to="body">
    <div class="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none">
      <TransitionGroup
        enter-active-class="animate-slide-in-right"
        leave-active-class="transition-all duration-200 ease-in"
        leave-to-class="opacity-0 translate-x-4"
      >
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto flex items-center gap-3 bg-surface-card rounded-lg shadow-toast border-l-[3px] px-4 py-3 min-w-[260px] max-w-sm"
          :class="colorFor(toast.type)"
          role="status"
          aria-live="polite"
        >
          <component :is="iconFor(toast.type)" class="w-4 h-4 shrink-0" />
          <span class="text-body text-grey-800 flex-1">{{ toast.message }}</span>
          <button
            v-if="toast.undoFn"
            @click="undo(toast)"
            class="text-caption font-bold text-brand-primary hover:text-brand-dark transition-colors shrink-0"
          >
            Undo
          </button>
          <button
            @click="dismiss(toast.id)"
            class="p-0.5 rounded text-grey-400 hover:text-grey-700 transition-colors shrink-0"
            :aria-label="`Dismiss notification: ${toast.message}`"
          >
            <XMarkIcon class="w-3.5 h-3.5" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
