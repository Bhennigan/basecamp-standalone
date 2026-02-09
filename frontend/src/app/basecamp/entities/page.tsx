"use client"

import { useState } from "react"
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
} from "lucide-react"
import { CenteredSpinner } from "@/components/loading/spinner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useBaseCampEntities, type BaseCampEntity } from "@/hooks/use-basecamp"

const ENTITY_TYPES = [
  "person", "organization", "email", "phone", "domain",
  "ip_address", "social_handle", "username", "address",
  "credential", "document", "image", "url",
]

const THREAT_LEVELS = ["critical", "high", "medium", "low", "info"]

function threatBadge(level: string | null) {
  if (!level) return <Badge variant="outline">Unknown</Badge>
  const map: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }> = {
    critical: { variant: "destructive", icon: <ShieldAlert className="mr-1 size-3" /> },
    high: { variant: "destructive", icon: <AlertTriangle className="mr-1 size-3" /> },
    medium: { variant: "secondary", icon: <Shield className="mr-1 size-3" /> },
    low: { variant: "outline", icon: <ShieldCheck className="mr-1 size-3" /> },
    info: { variant: "outline", icon: <ShieldQuestion className="mr-1 size-3" /> },
  }
  const cfg = map[level] || { variant: "outline" as const, icon: null }
  return (
    <Badge variant={cfg.variant} className="capitalize">
      {cfg.icon}{level}
    </Badge>
  )
}

function EntityRow({
  entity,
  expanded,
  onToggle,
}: {
  entity: BaseCampEntity
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr
        className="cursor-pointer border-b border-border/50 hover:bg-muted/30 transition-colors"
        onClick={onToggle}
      >
        <td className="px-4 py-3">
          {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </td>
        <td className="px-4 py-3">
          <Badge variant="secondary" className="capitalize">{entity.entity_type.replace("_", " ")}</Badge>
        </td>
        <td className="px-4 py-3 font-mono text-sm max-w-[300px] truncate">{entity.value}</td>
        <td className="px-4 py-3">{threatBadge(entity.threat_level)}</td>
        <td className="px-4 py-3 text-sm text-muted-foreground">
          {(entity.confidence * 100).toFixed(0)}%
        </td>
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {entity.tags?.slice(0, 3).map((t) => (
              <Badge key={t} variant="outline" className="text-xs">{t}</Badge>
            ))}
            {entity.tags?.length > 3 && (
              <Badge variant="outline" className="text-xs">+{entity.tags.length - 3}</Badge>
            )}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border/50 bg-muted/10">
          <td colSpan={6} className="px-8 py-4">
            <div className="grid gap-3 md:grid-cols-2 text-sm">
              <div>
                <span className="text-muted-foreground">Normalized: </span>
                <span className="font-mono">{entity.normalized_value}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Source: </span>
                <span>{entity.source}</span>
              </div>
              <div>
                <span className="text-muted-foreground">First seen: </span>
                <span>{new Date(entity.first_seen).toLocaleString()}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Last seen: </span>
                <span>{new Date(entity.last_seen).toLocaleString()}</span>
              </div>
              {entity.entity_metadata && Object.keys(entity.entity_metadata).length > 0 && (
                <div className="col-span-2">
                  <span className="text-muted-foreground">Metadata: </span>
                  <pre className="mt-1 rounded bg-muted/50 p-2 text-xs overflow-auto max-h-32">
                    {JSON.stringify(entity.entity_metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function EntitiesPage() {
  const [typeFilter, setTypeFilter] = useState<string>("")
  const [threatFilter, setThreatFilter] = useState<string>("")
  const [search, setSearch] = useState("")
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { entities, entitiesLoading, refetchEntities } = useBaseCampEntities({
    entity_type: typeFilter || undefined,
    threat_level: threatFilter || undefined,
    limit: 200,
  })

  const filtered = (entities ?? []).filter((e) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      e.value.toLowerCase().includes(q) ||
      e.normalized_value.toLowerCase().includes(q) ||
      e.entity_type.toLowerCase().includes(q) ||
      e.tags?.some((t) => t.toLowerCase().includes(q))
    )
  })

  if (entitiesLoading) return <CenteredSpinner />

  return (
    <div className="size-full overflow-auto">
      <div className="container flex h-full flex-col space-y-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Entities</h1>
            <p className="text-muted-foreground">Extracted and enriched entities from ingested data</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetchEntities()} className="gap-2">
            <RefreshCw className="size-4" /> Refresh
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search entities..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Entity Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {ENTITY_TYPES.map((t) => (
                <SelectItem key={t} value={t} className="capitalize">{t.replace("_", " ")}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={threatFilter} onValueChange={(v) => setThreatFilter(v === "all" ? "" : v)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Threat Level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Levels</SelectItem>
              {THREAT_LEVELS.map((l) => (
                <SelectItem key={l} value={l} className="capitalize">{l}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Summary */}
        <div className="text-sm text-muted-foreground">
          {filtered.length} entities {search && `matching "${search}"`}
        </div>

        {/* Table */}
        <Card className="border-border/50">
          <CardContent className="p-0">
            {filtered.length === 0 ? (
              <div className="flex h-40 items-center justify-center text-muted-foreground">
                {entities?.length === 0
                  ? "No entities extracted yet. Upload a file to get started."
                  : "No entities match the current filters."}
              </div>
            ) : (
              <div className="overflow-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-muted/50 text-left text-sm text-muted-foreground">
                      <th className="w-10 px-4 py-3" />
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Value</th>
                      <th className="px-4 py-3">Threat</th>
                      <th className="px-4 py-3">Confidence</th>
                      <th className="px-4 py-3">Tags</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((entity) => (
                      <EntityRow
                        key={entity.id}
                        entity={entity}
                        expanded={expandedId === entity.id}
                        onToggle={() => setExpandedId(expandedId === entity.id ? null : entity.id)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
