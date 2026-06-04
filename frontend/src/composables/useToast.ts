import { ref } from 'vue'

export type ToastType = 'info' | 'success' | 'error'

export interface Toast {
  id: number
  message: string
  type: ToastType
  undoFn?: () => void
}

const toasts = ref<Toast[]>([])
let nextId = 1

const DURATION = 5000

export function useToast() {
  function show(message: string, type: ToastType = 'info', undoFn?: () => void) {
    const id = nextId++
    toasts.value.push({ id, message, type, undoFn })
    setTimeout(() => dismiss(id), DURATION)
  }

  function dismiss(id: number) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  function undo(toast: Toast) {
    toast.undoFn?.()
    dismiss(toast.id)
  }

  return { toasts, show, dismiss, undo }
}
