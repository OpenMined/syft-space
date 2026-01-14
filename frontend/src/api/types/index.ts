export interface FileItem {
  name: string
  path: string
  is_dir: boolean
  size?: number
  modified: string
  extension?: string
}

export interface BrowseResponse {
  path: string
  parent?: string
  items: FileItem[]
}

export interface FilePathItem {
  path: string
  description: string
}

export interface CreateDatasetRequest {
  dtype: string
  name: string
  summary: string
  tags: string
  configuration: {
    collectionName: string
    filePaths: FilePathItem[]
  }
}

export interface ProvisionerStateResponse {
  status: string
  state?: Record<string, unknown>
  started_at?: string
  stopped_at?: string
  error?: string
}

export interface DatasetResponse {
  id: string
  name: string
  dtype: string
  configuration: Record<string, unknown>
  summary: string
  tags: string
  provisioner_state?: ProvisionerStateResponse
  created_at: string
  updated_at: string
  connected_endpoints: EndpointListItem[]
}

export interface HealthcheckResponse {
  dataset_type_status: string
  provisioner_status?: string
  message: string
}

export interface EndpointListItem {
  id: string
  name: string
  slug: string
  summary: string
  response_type: string
  published: boolean
  tags: string
  created_at: string
  model?: {
    id: string
    name: string
    dtype: string
    configuration: Record<string, unknown>
  }
  dataset?: {
    id: string
    name: string
    summary: string
    dtype: string
    configuration: Record<string, unknown>
  }
}

export interface ProvisionerStatusResponse {
  status: string
  error?: string
}

export interface DatasetListItem {
  id: string
  name: string
  dtype: string
  summary: string
  tags: string
  created_at: string
  configuration: Record<string, unknown>
  connected_endpoints: EndpointListItem[]
  provisioner_status?: ProvisionerStatusResponse
}

export interface DatasetTypeInfoResponse {
  name: string
  description: string
  config_schema: Record<string, unknown>
  icon: string
  enabled: boolean
}

// Ingestion API types
export interface IngestionJobResponse {
  id: string
  file_path: string
  file_name: string
  file_size: number
  status: string
  error_message?: string
  retry_count: number
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface IngestionStatusResponse {
  dataset_id: string
  dataset_name: string
  is_watching: boolean
  total_jobs: number
  pending: number
  in_progress: number
  completed: number
  failed: number
  cancelled: number
}

export interface IngestionJobListResponse {
  jobs: IngestionJobResponse[]
  total: number
  limit: number
  offset: number
}

export interface StartIngestionResponse {
  message: string
  jobs_created: number
  is_watching: boolean
}

export interface StopIngestionResponse {
  message: string
  jobs_cancelled: number
}

export interface RetryIngestionResponse {
  message: string
  jobs_reset: number
}

export interface UpdateDatasetRequest {
  name?: string
  summary?: string
  tags?: string
}

// Model API types
export interface CreateModelRequest {
  name: string
  dtype: string
  configuration: Record<string, unknown>
  summary?: string
  tags?: string
}

export interface ModelResponse {
  id: string
  name: string
  dtype: string
  configuration: Record<string, unknown>
  summary: string
  tags: string
  created_at: string
  updated_at: string
  connected_endpoints: EndpointListItem[]
}

export interface ModelListItem {
  id: string
  name: string
  dtype: string
  configuration: Record<string, unknown>
  summary: string
  tags: string
  created_at: string
  connected_endpoints: EndpointListItem[]
}

export interface UpdateModelRequest {
  name?: string
  summary?: string
  tags?: string
}

export interface ModelResponseWithEndpoints {
  id: string
  name: string
  dtype: string
  configuration: Record<string, unknown>
  summary: string
  tags: string
  created_at: string
  updated_at: string
  connected_endpoints: EndpointListItem[]
}

export interface ModelTypeInfoResponse {
  name: string
  description: string
  config_schema: Record<string, unknown>
  icon: string
  enabled: boolean
}

// Endpoint API types
export interface CreateEndpointRequest {
  name: string
  slug: string
  description?: string
  summary?: string
  dataset_id?: string
  model_id?: string
  response_type?: string
  published?: boolean
  tags?: string
}

export interface AttachedPolicy {
  id: string
  name: string
  policy_type: string
  configuration: Record<string, unknown>
}

export interface EndpointResponse {
  id: string
  name: string
  slug: string
  description: string
  summary: string
  dataset_id?: string
  model_id?: string
  response_type: string
  published: boolean
  tags: string
  created_at: string
  updated_at: string
  // Fields included in detail response
  model?: {
    id: string
    name: string
    dtype: string
    configuration: Record<string, unknown>
  }
  dataset?: {
    id: string
    name: string
    summary: string
    dtype: string
    configuration: Record<string, unknown>
  }
  policies?: AttachedPolicy[]
}

// Policy API types
export interface CreatePolicyRequest {
  name: string
  policy_type: string
  configuration: Record<string, unknown>
  endpoint_id: string
}

export interface PolicyResponse {
  id: string
  name: string
  policy_type: string
  configuration: Record<string, unknown>
  endpoint_id: string
  created_at: string
  updated_at: string
}

export interface PolicyListItem {
  id: string
  name: string
  policy_type: string
  endpoint_id: string
  created_at: string
}

// Marketplace API types
export interface RegisterMarketplaceRequest {
  name: string
  username: string
  url?: string
  email: string
  password: string
  accounting_url?: string
  accounting_password?: string
}

export interface ConnectMarketplaceRequest {
  username: string
  password: string
  url?: string
}

export interface MarketplaceResponse {
  id: string
  name: string
  url: string
  email: string
  is_default: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MarketplaceListItem {
  id: string
  name: string
  username: string
  email: string
  url: string
  is_default: boolean
  is_active: boolean
}

export interface BalanceResponse {
  balance: number
  currency: string
}

// Settings API types
export interface PublicUrlResponse {
  public_url: string | null
}

export interface UpdatePublicUrlRequest {
  public_url: string
}
