"use client"

import { createContext, useContext } from "react"

const DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000000"

const WorkspaceIdContext = createContext<string>(DEFAULT_WORKSPACE_ID)

export function WorkspaceIdProvider({ children }: { children: React.ReactNode }) {
  return (
    <WorkspaceIdContext.Provider value={DEFAULT_WORKSPACE_ID}>
      {children}
    </WorkspaceIdContext.Provider>
  )
}

export function useWorkspaceId() {
  return useContext(WorkspaceIdContext)
}
