"use client"

import { createContext, useContext } from "react"

const WorkspaceIdContext = createContext<string>("default")

export function WorkspaceIdProvider({ children }: { children: React.ReactNode }) {
  return (
    <WorkspaceIdContext.Provider value="default">
      {children}
    </WorkspaceIdContext.Provider>
  )
}

export function useWorkspaceId() {
  return useContext(WorkspaceIdContext)
}
