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
  source_id: string | null
  schema_id: string | null
  state: "received" | "analyzing" | "validating" | "transforming" | "loading" | "complete" | "failed" | "quarantined"
  status?: string // legacy alias
  file_name: string | null
  file_format: string | null
  total_records: number | null
  processed_records: number
  failed_records: number
  error_message?: string | null
  started_at?: string | null
  completed_at?: string | null
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
  message: string
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
      // Poll every 3 seconds if there are active jobs
      const data = query.state.data
      if (!data) return false
      const hasActiveJobs = data.some(
        (job) => {
          const s = (job.state || job.status || "").toLowerCase()
          return s === "received" || s === "analyzing" || s === "validating" || s === "transforming" || s === "loading"
        }
      )
      return hasActiveJobs ? 3000 : false
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
      // Poll every 2 seconds if job is still active
      const data = query.state.data
      if (!data) return false
      const s = (data.state || data.status || "").toLowerCase()
      return s === "received" || s === "analyzing" || s === "validating" || s === "transforming" || s === "loading" ? 2000 : false
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
      const response = await client.get("/api/basecamp/schemas", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const { mutateAsync: createSchema, isPending: createSchemaPending } =
    useMutation<BaseCampSchema, Error, BaseCampSchemaCreate>({
      mutationFn: async (data) => {
        const response = await client.post("/api/basecamp/schemas", data, {
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

/* ── MAPPING PROFILES ──────────────────────────────────────────────────────── */

export interface FieldMapping {
  source_field: string
  target_field: string
  transform: string
  params: Record<string, unknown>
}

export interface MappingProfile {
  id: string
  name: string
  description: string | null
  target_schema_id: string
  mappings: FieldMapping[]
  drop_unmapped: boolean
  created_at: string
  updated_at: string
}

export interface MappingProfileCreate {
  name: string
  description: string | null
  target_schema_id: string
  mappings: FieldMapping[]
  drop_unmapped: boolean
}

export function useBaseCampMappings() {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: mappings,
    isLoading: mappingsLoading,
    error: mappingsError,
    refetch: refetchMappings,
  } = useQuery<MappingProfile[]>({
    queryKey: ["basecamp", "mappings", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/basecamp/transform/profiles", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const { mutateAsync: createMapping, isPending: createMappingPending } =
    useMutation<MappingProfile, Error, MappingProfileCreate>({
      mutationFn: async (data) => {
        const response = await client.post("/api/basecamp/transform/profiles", data, {
          params: { workspace_id: workspaceId },
        })
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "mappings", workspaceId],
        })
      },
    })

  const { mutateAsync: deleteMapping, isPending: deleteMappingPending } =
    useMutation<void, Error, string>({
      mutationFn: async (id) => {
        await client.delete(`/api/basecamp/transform/profiles/${id}`, {
          params: { workspace_id: workspaceId },
        })
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "mappings", workspaceId],
        })
      },
    })

  return {
    mappings,
    mappingsLoading,
    mappingsError,
    refetchMappings,
    createMapping,
    createMappingPending,
    deleteMapping,
    deleteMappingPending,
  }
}

/* ── CONSUMERS ─────────────────────────────────────────────────────────────── */

export interface Consumer {
  id: string
  name: string
  description: string | null
  callback_url: string | null
  schema_ids: string[]
  mapping_profile_id: string | null
  active: boolean
  api_key: string
  last_poll: string | null
  created_at: string
  updated_at: string
}

export interface ConsumerCreate {
  name: string
  description: string | null
  callback_url: string | null
  mapping_profile_id: string | null
}

export function useBaseCampConsumers() {
  const workspaceId = useWorkspaceId()
  const queryClient = useQueryClient()

  const {
    data: consumers,
    isLoading: consumersLoading,
    error: consumersError,
    refetch: refetchConsumers,
  } = useQuery<Consumer[]>({
    queryKey: ["basecamp", "consumers", workspaceId],
    queryFn: async () => {
      const response = await client.get("/api/basecamp/consumers", {
        params: { workspace_id: workspaceId },
      })
      return response.data
    },
    enabled: !!workspaceId,
  })

  const { mutateAsync: createConsumer, isPending: createConsumerPending } =
    useMutation<Consumer, Error, ConsumerCreate>({
      mutationFn: async (data) => {
        const response = await client.post("/api/basecamp/consumers", data, {
          params: { workspace_id: workspaceId },
        })
        return response.data
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "consumers", workspaceId],
        })
      },
    })

  const { mutateAsync: deleteConsumer, isPending: deleteConsumerPending } =
    useMutation<void, Error, string>({
      mutationFn: async (id) => {
        await client.delete(`/api/basecamp/consumers/${id}`, {
          params: { workspace_id: workspaceId },
        })
      },
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["basecamp", "consumers", workspaceId],
        })
      },
    })

  return {
    consumers,
    consumersLoading,
    consumersError,
    refetchConsumers,
    createConsumer,
    createConsumerPending,
    deleteConsumer,
    deleteConsumerPending,
  }
}
