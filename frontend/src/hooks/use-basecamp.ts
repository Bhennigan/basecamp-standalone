"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosProgressEvent } from "axios"
import { client } from "@/lib/api"
import { useWorkspaceId } from "@/providers/workspace-id"

/* ── TYPES ─────────────────────────────────────────────────────────────────── */

// Data Source types
export interface BaseCampDataSource {
  id: string
  name: string
  type: string
  config: Record<string, unknown>
  status: "active" | "inactive" | "error"
  created_at: string
  updated_at: string
}

export interface BaseCampDataSourceCreate {
  name: string
  type: string
  config: Record<string, unknown>
}

export interface BaseCampDataSourceUpdate {
  name?: string
  config?: Record<string, unknown>
  status?: "active" | "inactive"
}

// Ingestion Job types
export interface BaseCampIngestionJob {
  id: string
  source_id: string
  status: "pending" | "running" | "completed" | "failed"
  progress: number
  records_processed: number
  records_failed: number
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
  updated_at: string
}

// Schema types
export interface BaseCampSchemaField {
  name: string
  type: string
  required: boolean
  description?: string
  default?: unknown
}

export interface BaseCampSchema {
  id: string
  name: string
  description?: string
  fields: BaseCampSchemaField[]
  created_at: string
  updated_at: string
}

export interface BaseCampSchemaCreate {
  name: string
  description?: string
  fields: BaseCampSchemaField[]
}

export interface BaseCampSchemaUpdate {
  name?: string
  description?: string
  fields?: BaseCampSchemaField[]
}

export interface BaseCampSchemaInferRequest {
  data: Record<string, unknown>[]
  sample_size?: number
}

// Record types
export interface BaseCampRecord {
  id: string
  schema_id: string
  data: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface BaseCampRecordCreate {
  schema_id: string
  data: Record<string, unknown>
}

export interface BaseCampRecordQuery {
  schema_id?: string
  filters?: Record<string, unknown>
  limit?: number
  offset?: number
  order_by?: string
  order_direction?: "asc" | "desc"
}

export interface BaseCampExportRequest {
  schema_id?: string
  filters?: Record<string, unknown>
  format?: "csv" | "json" | "parquet"
}

export interface BaseCampUploadResponse {
  job_id: string
  filename: string
  records_count: number
}

/* ── DATA SOURCES ─────────────────────────────────────────────────────────── */

export function useBaseCampSources() {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: sources,
    isLoading: sourcesLoading,
    error: sourcesError,
    refetch: refetchSources,
  } = useQuery<BaseCampDataSource[]>({
    queryKey: ["basecamp", "sources", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/basecamp/ingest/sources", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const { mutateAsync: createSource, isPending: createSourcePending } =
    useMutation<BaseCampDataSource, Error, BaseCampDataSourceCreate>({
      mutationFn: async (data) => {
        const response = await client.post("/api/basecamp/ingest/sources", data, {
          params: { workspace_id: workspaceId },
        })
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "sources", workspaceId],
        })
      },
    })

  const { mutateAsync: updateSource, isPending: updateSourcePending } =
    useMutation<
      BaseCampDataSource,
      Error,
      { id: string; data: BaseCampDataSourceUpdate }
    >({
      mutationFn: async ({ id, data }) => {
        const response = await client.patch(
          `/api/basecamp/ingest/sources/${id}`,
          data,
          { params: { workspace_id: workspaceId } }
        )
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "sources", workspaceId],
        })
      },
    })

  const { mutateAsync: deleteSource, isPending: deleteSourcePending } =
    useMutation<void, Error, string>({
      mutationFn: async (id) => {
        await client.delete(`/api/basecamp/ingest/sources/${id}`, {
          params: { workspace_id: workspaceId },
        })
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "sources", workspaceId],
        })
      },
    })

  return {
    sources,
    sourcesLoading,
    sourcesError,
    refetchSources,
    createSource,
    createSourcePending,
    updateSource,
    updateSourcePending,
    deleteSource,
    deleteSourcePending,
  }
}

export function useBaseCampSource(sourceId: string) {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: source,
    isLoading: sourceLoading,
    error: sourceError,
  } = useQuery<BaseCampDataSource>({
    queryKey: ["basecamp", "sources", workspaceId, sourceId],
    queryFn: async () => {
      const response = await client.get(
        `/api/basecamp/ingest/sources/${sourceId}`,
        { params: { workspace_id: workspaceId } }
      )
      return response.data
    },
    enabled: !!workspaceId && !!sourceId,
  })

  const { mutateAsync: updateSource, isPending: updateSourcePending } =
    useMutation<BaseCampDataSource, Error, BaseCampDataSourceUpdate>({
      mutationFn: async (data) => {
        const response = await client.patch(
          `/api/basecamp/ingest/sources/${sourceId}`,
          data,
          { params: { workspace_id: workspaceId } }
        )
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "sources", workspaceId, sourceId],
        })
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "sources", workspaceId],
        })
      },
    })

  return {
    source,
    sourceLoading,
    sourceError,
    updateSource,
    updateSourcePending,
  }
}

/* ── INGESTION JOBS ─────────────────────────────────────────────────────────── */

export function useBaseCampJobs() {
  const workspaceId = useWorkspaceId()

  const {
    data: jobs,
    isLoading: jobsLoading,
    error: jobsError,
    refetch: refetchJobs,
  } = useQuery<BaseCampIngestionJob[]>({
    queryKey: ["basecamp", "jobs", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/basecamp/ingest/jobs", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
    refetchInterval: (query) => {
      // Poll every 3 seconds if there are running jobs
      const data = query.state.data
      if (!data) return false
      const hasRunningJobs = data.some(
        (job) => job.status === "pending" || job.status === "running"
      )
      return hasRunningJobs ? 3000 : false
    },
  })

  return {
    jobs,
    jobsLoading,
    jobsError,
    refetchJobs,
  }
}

export function useBaseCampJob(jobId: string) {
  const workspaceId = useWorkspaceId()

  const {
    data: job,
    isLoading: jobLoading,
    error: jobError,
    refetch: refetchJob,
  } = useQuery<BaseCampIngestionJob>({
    queryKey: ["basecamp", "jobs", workspaceId, jobId],
    queryFn: async () => {
      const response = await client.get(`/api/basecamp/ingest/jobs/${jobId}`, {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId && !!jobId,
    refetchInterval: (query) => {
      // Poll every 2 seconds if job is still running
      const data = query.state.data
      if (!data) return false
      return data.status === "pending" || data.status === "running" ? 2000 : false
    },
  })

  return {
    job,
    jobLoading,
    jobError,
    refetchJob,
  }
}

/* ── FILE UPLOAD ────────────────────────────────────────────────────────────── */

export interface UploadOptions {
  onProgress?: (progress: number) => void
}

export function useBaseCampUpload() {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    mutateAsync: uploadFile,
    isPending: uploadPending,
    error: uploadError,
  } = useMutation<
    BaseCampUploadResponse,
    Error,
    { file: File; schemaId?: string; options?: UploadOptions }
  >({
    mutationFn: async ({ file, schemaId, options }) => {
      const formData = new FormData()
      formData.append("file", file)
      if (schemaId) {
        formData.append("schema_id", schemaId)
      }

      const response = await client.post("/api/basecamp/ingest/upload", formData, {
        params: { workspace_id: workspaceId },
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress: (progressEvent: AxiosProgressEvent) => {
          if (options?.onProgress && progressEvent.total) {
            const progress = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            )
            options.onProgress(progress)
          }
        },
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["basecamp", "jobs", workspaceId],
      })
      queryClient.invalidateQueries({
        queryKey: ["basecamp", "records", workspaceId],
      })
    },
  })

  return {
    uploadFile,
    uploadPending,
    uploadError,
  }
}

/* ── SCHEMAS ────────────────────────────────────────────────────────────────── */

export function useBaseCampSchemas() {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: schemas,
    isLoading: schemasLoading,
    error: schemasError,
    refetch: refetchSchemas,
  } = useQuery<BaseCampSchema[]>({
    queryKey: ["basecamp", "schemas", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/basecamp/schemas/", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const { mutateAsync: createSchema, isPending: createSchemaPending } =
    useMutation<BaseCampSchema, Error, BaseCampSchemaCreate>({
      mutationFn: async (data) => {
        const response = await client.post("/api/basecamp/schemas/", data, {
          params: { workspace_id: workspaceId },
        })
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "schemas", workspaceId],
        })
      },
    })

  const { mutateAsync: updateSchema, isPending: updateSchemaPending } =
    useMutation<BaseCampSchema, Error, { id: string; data: BaseCampSchemaUpdate }>(
      {
        mutationFn: async ({ id, data }) => {
          const response = await client.patch(
            `/api/basecamp/schemas/${id}`,
            data,
            { params: { workspace_id: workspaceId } }
          )
          return response.data
        },
        onSuccess: () => {
          queryClient.invalidateQueries({
            queryKey: ["basecamp", "schemas", workspaceId],
          })
        },
      }
    )

  const { mutateAsync: deleteSchema, isPending: deleteSchemaPending } =
    useMutation<void, Error, string>({
      mutationFn: async (id) => {
        await client.delete(`/api/basecamp/schemas/${id}`, {
          params: { workspace_id: workspaceId },
        })
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "schemas", workspaceId],
        })
      },
    })

  const { mutateAsync: inferSchema, isPending: inferSchemaPending } = useMutation<
    BaseCampSchema,
    Error,
    BaseCampSchemaInferRequest
  >({
    mutationFn: async (data) => {
      const response = await client.post("/api/basecamp/schemas/infer", data, {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
  })

  return {
    schemas,
    schemasLoading,
    schemasError,
    refetchSchemas,
    createSchema,
    createSchemaPending,
    updateSchema,
    updateSchemaPending,
    deleteSchema,
    deleteSchemaPending,
    inferSchema,
    inferSchemaPending,
  }
}

export function useBaseCampSchema(schemaId: string) {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: schema,
    isLoading: schemaLoading,
    error: schemaError,
  } = useQuery<BaseCampSchema>({
    queryKey: ["basecamp", "schemas", workspaceId, schemaId],
    queryFn: async () => {
      const response = await client.get(`/api/basecamp/schemas/${schemaId}`, {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId && !!schemaId,
  })

  const { mutateAsync: updateSchema, isPending: updateSchemaPending } =
    useMutation<BaseCampSchema, Error, BaseCampSchemaUpdate>({
      mutationFn: async (data) => {
        const response = await client.patch(
          `/api/basecamp/schemas/${schemaId}`,
          data,
          { params: { workspace_id: workspaceId } }
        )
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "schemas", workspaceId, schemaId],
        })
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "schemas", workspaceId],
        })
      },
    })

  return {
    schema,
    schemaLoading,
    schemaError,
    updateSchema,
    updateSchemaPending,
  }
}

/* ── RECORDS ────────────────────────────────────────────────────────────────── */

export function useBaseCampRecords(queryParams?: BaseCampRecordQuery) {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: records,
    isLoading: recordsLoading,
    error: recordsError,
    refetch: refetchRecords,
  } = useQuery<BaseCampRecord[]>({
    queryKey: ["basecamp", "records", workspaceId, queryParams],
    queryFn: async () => {
      const response = await client.get("/api/basecamp/data/records", {
        params: {
          workspace_id: workspaceId,
          ...queryParams,
        },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const { mutateAsync: createRecord, isPending: createRecordPending } =
    useMutation<BaseCampRecord, Error, BaseCampRecordCreate>({
      mutationFn: async (data) => {
        const response = await client.post("/api/basecamp/data/records", data, {
          params: { workspace_id: workspaceId },
        })
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "records", workspaceId],
        })
      },
    })

  const { mutateAsync: queryRecords, isPending: queryRecordsPending } =
    useMutation<BaseCampRecord[], Error, BaseCampRecordQuery>({
      mutationFn: async (query) => {
        const response = await client.post("/api/basecamp/data/query", query, {
          params: { workspace_id: workspaceId },
        })
        return response.data
      },
    })

  return {
    records,
    recordsLoading,
    recordsError,
    refetchRecords,
    createRecord,
    createRecordPending,
    queryRecords,
    queryRecordsPending,
  }
}

/* ── DATA EXPORT ────────────────────────────────────────────────────────────── */

export function useBaseCampExport() {
  const workspaceId = useWorkspaceId()

  const { mutateAsync: exportData, isPending: exportPending } = useMutation<
    Blob,
    Error,
    BaseCampExportRequest
  >({
    mutationFn: async (request) => {
      const response = await client.post("/api/basecamp/data/export", request, {
        params: { workspace_id: workspaceId },
        responseType: "blob",
      })
      return response.data
    },
  })

  const downloadExport = async (
    request: BaseCampExportRequest,
    filename?: string
  ) => {
    const blob = await exportData(request)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    try {
      a.href = url
      a.download =
        filename || `basecamp-export.${request.format || "json"}`
      document.body.appendChild(a)
      a.click()
    } finally {
      a.remove()
      window.URL.revokeObjectURL(url)
    }
  }

  return {
    exportData,
    exportPending,
    downloadExport,
  }
}

/* ── ENTITIES (Enrichment) ─────────────────────────────────────────────────── */

export interface BaseCampEntity {
  id: string
  entity_type: string
  value: string
  normalized_value: string
  confidence: number
  threat_level: string | null
  source: string
  source_record_id: string | null
  tags: string[]
  entity_metadata: Record<string, unknown>
  first_seen: string
  last_seen: string
}

export interface BaseCampEntitySearchResult {
  id: string | number
  score: number
  payload: Record<string, unknown>
}

export function useBaseCampEntities(params?: {
  entity_type?: string
  threat_level?: string
  limit?: number
  offset?: number
}) {
  const workspaceId = useWorkspaceId()

  const {
    data: entities,
    isLoading: entitiesLoading,
    error: entitiesError,
    refetch: refetchEntities,
  } = useQuery<BaseCampEntity[]>({
    queryKey: ["basecamp", "entities", workspaceId, params],
    queryFn: async () => {
      const response = await client.get("/api/enrichment/entities", {
        params: { workspace_id: workspaceId, ...params },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  return { entities, entitiesLoading, entitiesError, refetchEntities }
}

/* ── ENTITY SEARCH (Vectors) ───────────────────────────────────────────────── */

export function useBaseCampEntitySearch() {
  const workspaceId = useWorkspaceId()

  const {
    mutateAsync: searchEntities,
    data: searchResults,
    isPending: searchPending,
    error: searchError,
  } = useMutation<
    BaseCampEntitySearchResult[],
    Error,
    { query: string; entity_type?: string; limit?: number }
  >({
    mutationFn: async (params) => {
      const response = await client.post("/api/vectors/search", params, {
        params: { workspace_id: workspaceId },
      })
      return response.data?.results ?? response.data
    },
  })

  return { searchEntities, searchResults, searchPending, searchError }
}

/* ── GRAPH ─────────────────────────────────────────────────────────────────── */

export interface BaseCampGraphRelationship {
  source_id: string
  source_type: string
  relationship_type: string
  target_id: string
  target_type: string
}

export interface BaseCampGraphNeighbor {
  id: string
  labels: string[]
  properties: Record<string, unknown>
}

export function useBaseCampGraph(entityId?: string) {
  const workspaceId = useWorkspaceId()

  const {
    data: relationships,
    isLoading: relationshipsLoading,
    error: relationshipsError,
    refetch: refetchRelationships,
  } = useQuery<BaseCampGraphRelationship[]>({
    queryKey: ["basecamp", "graph", "relationships", workspaceId, entityId],
    queryFn: async () => {
      const response = await client.get(`/api/graph/entity/${entityId}`, {
        params: { workspace_id: workspaceId },
      })
      return response.data?.relationships ?? response.data
    },
    enabled: !!workspaceId && !!entityId,
  })

  const {
    data: neighbors,
    isLoading: neighborsLoading,
    refetch: refetchNeighbors,
  } = useQuery<BaseCampGraphNeighbor[]>({
    queryKey: ["basecamp", "graph", "neighbors", workspaceId, entityId],
    queryFn: async () => {
      const response = await client.get(`/api/graph/neighbors/${entityId}`, {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId && !!entityId,
  })

  return {
    relationships,
    relationshipsLoading,
    relationshipsError,
    neighbors,
    neighborsLoading,
    refetchRelationships,
    refetchNeighbors,
  }
}

export function useBaseCampGraphStats() {
  const workspaceId = useWorkspaceId()

  const {
    data: graphStats,
    isLoading: graphStatsLoading,
    refetch: refetchGraphStats,
  } = useQuery<Record<string, unknown>>({
    queryKey: ["basecamp", "graph", "stats", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/graph/stats", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  return { graphStats, graphStatsLoading, refetchGraphStats }
}

/* ── CONNECTORS ────────────────────────────────────────────────────────────── */

export interface BaseCampConnector {
  name: string
  type: string
  description?: string
  status: string
  health?: string
  config?: Record<string, unknown>
  last_fetch?: string
}

export function useBaseCampConnectors() {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: connectors,
    isLoading: connectorsLoading,
    error: connectorsError,
    refetch: refetchConnectors,
  } = useQuery<BaseCampConnector[]>({
    queryKey: ["basecamp", "connectors", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/connectors/", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const { mutateAsync: createConnector, isPending: createConnectorPending } =
    useMutation<
      BaseCampConnector,
      Error,
      { name: string; type: string; config?: Record<string, unknown> }
    >({
      mutationFn: async (data) => {
        const response = await client.post("/api/connectors/", data, {
          params: { workspace_id: workspaceId },
        })
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "connectors", workspaceId],
        })
      },
    })

  const { mutateAsync: deleteConnector, isPending: deleteConnectorPending } =
    useMutation<void, Error, string>({
      mutationFn: async (name) => {
        await client.delete(`/api/connectors/${name}`, {
          params: { workspace_id: workspaceId },
        })
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "connectors", workspaceId],
        })
      },
    })

  const { mutateAsync: testConnector, isPending: testConnectorPending } =
    useMutation<Record<string, unknown>, Error, { name: string; query?: string }>({
      mutationFn: async ({ name, query }) => {
        const response = await client.post(
          `/api/connectors/${name}/test`,
          { query: query || "test" },
          { params: { workspace_id: workspaceId } }
        )
        return response.data
      },
    })

  const { mutateAsync: fetchFromConnector, isPending: fetchPending } =
    useMutation<Record<string, unknown>, Error, { name: string; query: string }>({
      mutationFn: async ({ name, query }) => {
        const response = await client.post(
          `/api/connectors/${name}/fetch`,
          { query },
          { params: { workspace_id: workspaceId } }
        )
        return response.data
      },
    })

  return {
    connectors,
    connectorsLoading,
    connectorsError,
    refetchConnectors,
    createConnector,
    createConnectorPending,
    deleteConnector,
    deleteConnectorPending,
    testConnector,
    testConnectorPending,
    fetchFromConnector,
    fetchPending,
  }
}

/* ── REVIEW QUEUE ──────────────────────────────────────────────────────────── */

export interface BaseCampReviewItem {
  id: string
  workspace_id: string
  entity_id: string | null
  record_id: string | null
  item_type: string
  status: "pending" | "in_review" | "approved" | "rejected" | "reclassified"
  priority: "critical" | "high" | "medium" | "low"
  confidence_score: number
  confidence_threshold: number
  reason: string | null
  data: Record<string, unknown>
  assigned_to: string | null
  reviewed_by: string | null
  review_notes: string | null
  created_at: string
  updated_at: string
  reviewed_at: string | null
}

export interface BaseCampReviewStats {
  pending: number
  in_review: number
  approved: number
  rejected: number
  reclassified: number
  total: number
}

export function useBaseCampReviewQueue(params?: {
  status?: string
  priority?: string
  limit?: number
  offset?: number
}) {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: reviewData,
    isLoading: reviewLoading,
    error: reviewError,
    refetch: refetchReview,
  } = useQuery<{ items: BaseCampReviewItem[]; count: number }>({
    queryKey: ["basecamp", "review", "queue", workspaceId, params],
    queryFn: async () => {
      const response = await client.get("/api/review/queue", {
        params: { workspace_id: workspaceId, ...params },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const {
    data: reviewStats,
    isLoading: statsLoading,
    refetch: refetchStats,
  } = useQuery<BaseCampReviewStats>({
    queryKey: ["basecamp", "review", "stats", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/review/stats", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const { mutateAsync: assignItem, isPending: assignPending } = useMutation<
    BaseCampReviewItem,
    Error,
    { itemId: string; assignee: string }
  >({
    mutationFn: async ({ itemId, assignee }) => {
      const response = await client.post(
        `/api/review/item/${itemId}/assign`,
        { assignee },
        { params: { workspace_id: workspaceId } }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["basecamp", "review", workspaceId],
      })
    },
  })

  const { mutateAsync: submitDecision, isPending: decisionPending } =
    useMutation<
      unknown,
      Error,
      {
        itemId: string
        decision: string
        reviewer_id: string
        notes?: string
      }
    >({
      mutationFn: async ({ itemId, decision, reviewer_id, notes }) => {
        const response = await client.post(
          `/api/review/item/${itemId}/decision`,
          { decision, reviewer_id, notes },
          { params: { workspace_id: workspaceId } }
        )
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "review", workspaceId],
        })
      },
    })

  return {
    reviewItems: reviewData?.items ?? [],
    reviewCount: reviewData?.count ?? 0,
    reviewLoading,
    reviewError,
    refetchReview,
    reviewStats,
    statsLoading,
    refetchStats,
    assignItem,
    assignPending,
    submitDecision,
    decisionPending,
  }
}

/* ── EVENTS ────────────────────────────────────────────────────────────────── */

export interface BaseCampEventSubject {
  pattern: string
  description: string
  example_event: string
}

export function useBaseCampEvents() {
  const workspaceId = useWorkspaceId()

  const {
    data: subjects,
    isLoading: subjectsLoading,
    error: subjectsError,
  } = useQuery<BaseCampEventSubject[]>({
    queryKey: ["basecamp", "events", "subjects", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/events/subjects", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const {
    data: eventHealth,
    isLoading: healthLoading,
  } = useQuery<Record<string, unknown>>({
    queryKey: ["basecamp", "events", "health", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/events/health", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
    refetchInterval: 30000,
  })

  return { subjects, subjectsLoading, subjectsError, eventHealth, healthLoading }
}
