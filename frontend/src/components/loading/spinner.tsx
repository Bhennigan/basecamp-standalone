"use client"

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={`inline-block size-6 animate-spin rounded-full border-2 border-current border-t-transparent ${className || ""}`}
      role="status"
    >
      <span className="sr-only">Loading...</span>
    </div>
  )
}

export function CenteredSpinner() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <Spinner className="size-8" />
    </div>
  )
}
