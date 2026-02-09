"use client"

import * as React from "react"

interface Toast {
  id: string
  title?: string
  description?: string
  variant?: "default" | "destructive"
}

interface ToastState {
  toasts: Toast[]
}

let toastCount = 0
let listeners: Array<(state: ToastState) => void> = []
let memoryState: ToastState = { toasts: [] }

function dispatch(action: { type: "ADD"; toast: Toast } | { type: "DISMISS"; id: string }) {
  if (action.type === "ADD") {
    memoryState = {
      toasts: [...memoryState.toasts, action.toast],
    }
    // Auto dismiss after 5 seconds
    setTimeout(() => {
      dispatch({ type: "DISMISS", id: action.toast.id })
    }, 5000)
  } else if (action.type === "DISMISS") {
    memoryState = {
      toasts: memoryState.toasts.filter((t) => t.id !== action.id),
    }
  }
  listeners.forEach((listener) => listener(memoryState))
}

function toast({
  title,
  description,
  variant = "default",
}: {
  title?: string
  description?: string
  variant?: "default" | "destructive"
}) {
  const id = String(toastCount++)
  dispatch({
    type: "ADD",
    toast: { id, title, description, variant },
  })
  return { id, dismiss: () => dispatch({ type: "DISMISS", id }) }
}

function useToast() {
  const [state, setState] = React.useState<ToastState>(memoryState)

  React.useEffect(() => {
    listeners.push(setState)
    return () => {
      listeners = listeners.filter((l) => l !== setState)
    }
  }, [])

  return {
    ...state,
    toast,
    dismiss: (id: string) => dispatch({ type: "DISMISS", id }),
  }
}

export { useToast, toast }
