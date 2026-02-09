"use client"

import { useState } from "react"
import {
  GitBranch,
  RefreshCw,
  Search,
} from "lucide-react"
import { CenteredSpinner } from "@/components/loading/spinner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  useBaseCampEntities,
  useBaseCampGraph,
  useBaseCampGraphStats,
  type BaseCampEntity,
  type BaseCampGraphRelationship,
} from "@/hooks/use-basecamp"

function RelationshipCard({ rel }: { rel: BaseCampGraphRelationship }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/50 bg-muted/20 p-3 text-sm">
      <div className="flex flex-col items-center gap-1">
        <Badge variant="secondary" className="text-xs capitalize">
          {rel.source_type?.replace("_", " ") ?? "entity"}
        </Badge>
        <span className="font-mono text-xs truncate max-w-[120px]">{rel.source_id?.slice(0, 8)}...</span>
      </div>
      <div className="flex flex-col items-center">
        <span className="text-xs text-muted-foreground">{rel.relationship_type}</span>
        <GitBranch className="size-4 text-muted-foreground" />
      </div>
      <div className="flex flex-col items-center gap-1">
        <Badge variant="secondary" className="text-xs capitalize">
          {rel.target_type?.replace("_", " ") ?? "entity"}
        </Badge>
        <span className="font-mono text-xs truncate max-w-[120px]">{rel.target_id?.slice(0, 8)}...</span>
      </div>
    </div>
  )
}

export default function GraphPage() {
  const [selectedEntityId, setSelectedEntityId] = useState<string>("")
  const [search, setSearch] = useState("")

  const { entities, entitiesLoading } = useBaseCampEntities({ limit: 200 })
  const { relationships, relationshipsLoading, refetchRelationships } = useBaseCampGraph(
    selectedEntityId || undefined
  )
  const { graphStats, graphStatsLoading, refetchGraphStats } = useBaseCampGraphStats()

  const filteredEntities = (entities ?? []).filter((e) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      e.value.toLowerCase().includes(q) ||
      e.entity_type.toLowerCase().includes(q)
    )
  })

  const selectedEntity = entities?.find((e) => e.id === selectedEntityId)

  return (
    <div className="size-full overflow-auto">
      <div className="container flex h-full flex-col space-y-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Entity Graph</h1>
            <p className="text-muted-foreground">Explore entity relationships and connections</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => { refetchGraphStats(); if (selectedEntityId) refetchRelationships(); }}
            className="gap-2"
          >
            <RefreshCw className="size-4" /> Refresh
          </Button>
        </div>

        {/* Stats */}
        {graphStats && (
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border-border/50">
              <CardContent className="flex items-center gap-3 p-4">
                <GitBranch className="size-5 text-muted-foreground" />
                <div>
                  <div className="text-xl font-bold">{graphStats.node_count ?? 0}</div>
                  <div className="text-xs text-muted-foreground">Nodes</div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/50">
              <CardContent className="flex items-center gap-3 p-4">
                <GitBranch className="size-5 text-muted-foreground" />
                <div>
                  <div className="text-xl font-bold">{graphStats.relationship_count ?? 0}</div>
                  <div className="text-xs text-muted-foreground">Relationships</div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/50">
              <CardContent className="flex items-center gap-3 p-4">
                <GitBranch className="size-5 text-muted-foreground" />
                <div>
                  <div className="text-xl font-bold">
                    {Array.isArray(graphStats.labels) ? graphStats.labels.length : 0}
                  </div>
                  <div className="text-xs text-muted-foreground">Entity Types</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Entity list / search */}
          <Card className="border-border/50 lg:col-span-1">
            <CardHeader>
              <CardTitle className="text-base">Select Entity</CardTitle>
              <CardDescription>Choose an entity to view its relationships</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  placeholder="Search entities..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="max-h-[400px] space-y-1 overflow-auto">
                {entitiesLoading ? (
                  <div className="flex h-20 items-center justify-center text-sm text-muted-foreground">Loading...</div>
                ) : filteredEntities.length === 0 ? (
                  <div className="flex h-20 items-center justify-center text-sm text-muted-foreground">
                    No entities found
                  </div>
                ) : (
                  filteredEntities.map((entity) => (
                    <button
                      key={entity.id}
                      onClick={() => setSelectedEntityId(entity.id)}
                      className={`w-full text-left rounded-md px-3 py-2 text-sm transition-colors ${
                        selectedEntityId === entity.id
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="truncate font-mono">{entity.value}</span>
                        <Badge variant="outline" className="ml-2 text-xs capitalize shrink-0">
                          {entity.entity_type.replace("_", " ")}
                        </Badge>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* Relationships */}
          <Card className="border-border/50 lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Relationships</CardTitle>
              <CardDescription>
                {selectedEntity
                  ? `Connections for ${selectedEntity.value}`
                  : "Select an entity to view its relationships"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!selectedEntityId ? (
                <div className="flex h-40 items-center justify-center text-muted-foreground">
                  Select an entity from the list
                </div>
              ) : relationshipsLoading ? (
                <div className="flex h-40 items-center justify-center text-muted-foreground">
                  Loading relationships...
                </div>
              ) : !relationships || relationships.length === 0 ? (
                <div className="flex h-40 items-center justify-center text-muted-foreground">
                  No relationships found for this entity
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="text-sm text-muted-foreground">
                    {relationships.length} relationship{relationships.length !== 1 ? "s" : ""}
                  </div>
                  {relationships.map((rel, i) => (
                    <RelationshipCard key={i} rel={rel} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
