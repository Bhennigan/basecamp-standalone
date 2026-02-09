"use client"

import { useState, useMemo } from "react"
import {
  Download,
  Search,
  RefreshCw,
  Eye,
  FileJson,
  FileSpreadsheet,
  FileText,
  Pencil,
  Trash2,
  Database,
  Copy,
  Check,
} from "lucide-react"
import type { ColumnDef, Row } from "@tanstack/react-table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { DataTable, DataTableColumnHeader } from "@/components/data-table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { CenteredSpinner } from "@/components/loading/spinner"
import { useToast } from "@/components/ui/use-toast"
import {
  useBaseCampSchemas,
  useBaseCampSchema,
  useBaseCampRecords,
  useBaseCampExport,
  type BaseCampRecord,
  type BaseCampSchemaField,
} from "@/hooks/use-basecamp"

// Utility to format field values for display
function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "-"
  }
  if (typeof value === "object") {
    return JSON.stringify(value)
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false"
  }
  return String(value)
}

// Utility to truncate long values
function truncateValue(value: string, maxLength = 50): string {
  if (value.length <= maxLength) return value
  return `${value.slice(0, maxLength)}...`
}

// Field type badge component
function FieldTypeBadge({ type }: { type: string }) {
  const colorMap: Record<string, string> = {
    string: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    number: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    boolean: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    object: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    array: "bg-pink-500/20 text-pink-400 border-pink-500/30",
    date: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  }

  const className = colorMap[type.toLowerCase()] || "bg-muted text-muted-foreground"

  return (
    <Badge variant="outline" className={className}>
      {type}
    </Badge>
  )
}

// Copy button component
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-6"
      onClick={handleCopy}
    >
      {copied ? (
        <Check className="size-3 text-emerald-400" />
      ) : (
        <Copy className="size-3" />
      )}
    </Button>
  )
}

// Record detail sheet component
function RecordDetailSheet({
  record,
  fields,
  open,
  onOpenChange,
  onEdit,
  onDelete,
}: {
  record: BaseCampRecord | null
  fields: BaseCampSchemaField[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onEdit: () => void
  onDelete: () => void
}) {
  const [viewMode, setViewMode] = useState<"fields" | "json">("fields")

  if (!record) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto border-border/50 bg-background sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Eye className="size-5 text-muted-foreground" />
            Record details
          </SheetTitle>
          <SheetDescription>
            ID: {record.id}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={onEdit}
            >
              <Pencil className="size-4" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={onDelete}
            >
              <Trash2 className="size-4" />
              Delete
            </Button>
          </div>

          {/* View toggle */}
          <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as "fields" | "json")}>
            <TabsList className="bg-muted/50">
              <TabsTrigger value="fields">Fields</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
            </TabsList>

            <TabsContent value="fields" className="mt-4">
              <div className="space-y-3">
                {fields.map((field) => {
                  const value = record.data[field.name]
                  const displayValue = formatFieldValue(value)

                  return (
                    <div
                      key={field.name}
                      className="rounded-lg border border-border/50 bg-muted/30 p-3"
                    >
                      <div className="mb-1 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{field.name}</span>
                          <FieldTypeBadge type={field.type} />
                          {field.required && (
                            <span className="text-xs text-amber-400">required</span>
                          )}
                        </div>
                        <CopyButton text={displayValue} />
                      </div>
                      {field.description && (
                        <p className="mb-2 text-xs text-muted-foreground">
                          {field.description}
                        </p>
                      )}
                      <pre className="whitespace-pre-wrap break-all rounded bg-background/50 p-2 font-mono text-xs text-foreground">
                        {displayValue}
                      </pre>
                    </div>
                  )
                })}

                {/* Metadata */}
                <div className="mt-6 space-y-2 border-t border-border/50 pt-4">
                  <h4 className="text-xs font-medium text-muted-foreground">Metadata</h4>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="text-muted-foreground">Created:</span>
                      <span className="ml-2">
                        {new Date(record.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Updated:</span>
                      <span className="ml-2">
                        {new Date(record.updated_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="json" className="mt-4">
              <div className="relative">
                <div className="absolute right-2 top-2">
                  <CopyButton text={JSON.stringify(record.data, null, 2)} />
                </div>
                <pre className="overflow-auto rounded-lg border border-border/50 bg-muted/30 p-4 font-mono text-xs">
                  {JSON.stringify(record.data, null, 2)}
                </pre>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function BaseCampDataPage() {
  const { toast } = useToast()

  // State
  const [selectedSchemaId, setSelectedSchemaId] = useState<string>("")
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedRecord, setSelectedRecord] = useState<BaseCampRecord | null>(null)
  const [isDetailOpen, setIsDetailOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [recordToDelete, setRecordToDelete] = useState<BaseCampRecord | null>(null)

  // Data fetching
  const { schemas, schemasLoading } = useBaseCampSchemas()
  const {
    records,
    recordsLoading,
    recordsError,
    refetchRecords,
  } = useBaseCampRecords(
    selectedSchemaId ? { schema_id: selectedSchemaId } : undefined
  )
  const { downloadExport, exportPending } = useBaseCampExport()

  // Fetch full schema details (with fields) when one is selected
  const { schema: selectedSchema } = useBaseCampSchema(selectedSchemaId)

  // Filter records based on search
  const filteredRecords = useMemo(() => {
    if (!records) return []
    if (!searchQuery.trim()) return records

    const query = searchQuery.toLowerCase()
    return records.filter((record) => {
      // Search in record ID
      if (record.id.toLowerCase().includes(query)) return true

      // Search in data fields
      return Object.values(record.data).some((value) => {
        const strValue = formatFieldValue(value).toLowerCase()
        return strValue.includes(query)
      })
    })
  }, [records, searchQuery])

  // Generate columns dynamically from schema fields
  const columns = useMemo<ColumnDef<BaseCampRecord>[]>(() => {
    if (!selectedSchema) return []

    const fieldColumns: ColumnDef<BaseCampRecord>[] = (selectedSchema.fields || [])
      .slice(0, 5) // Limit to first 5 fields for table display
      .map((field) => ({
        accessorKey: `data.${field.name}`,
        header: ({ column }) => (
          <DataTableColumnHeader
            column={column}
            title={field.name}
          />
        ),
        cell: ({ row }) => {
          const value = row.original.data[field.name]
          const displayValue = truncateValue(formatFieldValue(value), 40)
          return (
            <span className="font-mono text-xs">{displayValue}</span>
          )
        },
      }))

    return [
      {
        accessorKey: "id",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="ID" />
        ),
        cell: ({ row }) => (
          <span className="font-mono text-xs text-muted-foreground">
            {row.original.id.slice(0, 8)}...
          </span>
        ),
      },
      ...fieldColumns,
      {
        accessorKey: "created_at",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Created" />
        ),
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {new Date(row.original.created_at).toLocaleDateString()}
          </span>
        ),
      },
      {
        id: "actions",
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={(e) => {
              e.stopPropagation()
              handleViewRecord(row.original)
            }}
          >
            <Eye className="size-4" />
          </Button>
        ),
      },
    ]
  }, [selectedSchema])

  // Handlers
  const handleViewRecord = (record: BaseCampRecord) => {
    setSelectedRecord(record)
    setIsDetailOpen(true)
  }

  const handleRowClick = (row: Row<BaseCampRecord>) => () => {
    handleViewRecord(row.original)
  }

  const handleEditRecord = () => {
    toast({
      title: "Coming soon",
      description: "Record editing will be available in a future update.",
    })
  }

  const handleDeleteRecord = () => {
    if (selectedRecord) {
      setRecordToDelete(selectedRecord)
      setDeleteDialogOpen(true)
    }
  }

  const confirmDelete = () => {
    if (recordToDelete) {
      toast({
        title: "Coming soon",
        description: "Record deletion will be available in a future update.",
      })
      setDeleteDialogOpen(false)
      setRecordToDelete(null)
      setIsDetailOpen(false)
    }
  }

  const handleExport = async (format: "json" | "csv" | "parquet") => {
    if (!selectedSchemaId) {
      toast({
        title: "No schema selected",
        description: "Please select a schema to export data.",
        variant: "destructive",
      })
      return
    }

    try {
      const timestamp = new Date().toISOString().split("T")[0]
      const filename = `basecamp-export-${selectedSchema?.name || "data"}-${timestamp}.${format === "parquet" ? "parquet" : format}`

      await downloadExport(
        {
          schema_id: selectedSchemaId,
          format,
        },
        filename
      )

      toast({
        title: "Export started",
        description: `Downloading ${filename}`,
      })
    } catch {
      toast({
        title: "Export failed",
        description: "Failed to export data. Please try again.",
        variant: "destructive",
      })
    }
  }

  // Loading state
  if (schemasLoading) {
    return <CenteredSpinner />
  }

  return (
    <div className="size-full overflow-auto">
      <div className="container flex h-full flex-col space-y-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Data browser</h1>
            <p className="text-muted-foreground">
              Browse and query your ingested data records
            </p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                className="gap-2"
                disabled={!selectedSchemaId || exportPending}
              >
                <Download className="size-4" />
                Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem
                onClick={() => handleExport("json")}
                className="gap-2"
              >
                <FileJson className="size-4" />
                Export as JSON
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleExport("csv")}
                className="gap-2"
              >
                <FileText className="size-4" />
                Export as CSV
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleExport("parquet")}
                className="gap-2"
              >
                <FileSpreadsheet className="size-4" />
                Export as Parquet
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Filters bar */}
        <div className="flex items-center gap-4">
          <Select value={selectedSchemaId} onValueChange={setSelectedSchemaId}>
            <SelectTrigger className="w-64 border-border/50 bg-background">
              <SelectValue placeholder="Select a schema" />
            </SelectTrigger>
            <SelectContent>
              {schemas?.map((schema) => (
                <SelectItem key={schema.id} value={schema.id}>
                  <div className="flex items-center gap-2">
                    <Database className="size-4 text-muted-foreground" />
                    {schema.name}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search records..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="border-border/50 bg-background pl-9"
              disabled={!selectedSchemaId}
            />
          </div>

          <Button
            variant="outline"
            size="icon"
            onClick={() => refetchRecords()}
            disabled={!selectedSchemaId || recordsLoading}
            className="border-border/50"
          >
            <RefreshCw className={`size-4 ${recordsLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>

        {/* Content */}
        {!selectedSchemaId ? (
          // No schema selected empty state
          <div className="flex flex-1 flex-col items-center justify-center rounded-lg border-2 border-dashed border-border/50 bg-muted/20">
            <Database className="mb-4 size-12 text-muted-foreground/50" />
            <h3 className="mb-2 text-lg font-medium">Select a schema to browse records</h3>
            <p className="text-sm text-muted-foreground">
              Choose a schema from the dropdown above to view its records
            </p>
          </div>
        ) : (
          // Data table
          <div className="flex-1">
            <DataTable
              columns={columns}
              data={filteredRecords}
              isLoading={recordsLoading}
              error={recordsError as Error | null}
              onClickRow={handleRowClick}
              emptyMessage={
                searchQuery
                  ? "No records match your search"
                  : "No records found for this schema"
              }
              errorMessage="Failed to load records"
              tableId={`basecamp-data-${selectedSchemaId}`}
            />
          </div>
        )}

        {/* Record detail sheet */}
        <RecordDetailSheet
          record={selectedRecord}
          fields={selectedSchema?.fields || []}
          open={isDetailOpen}
          onOpenChange={setIsDetailOpen}
          onEdit={handleEditRecord}
          onDelete={handleDeleteRecord}
        />

        {/* Delete confirmation dialog */}
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete record</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete this record? This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={confirmDelete}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}
