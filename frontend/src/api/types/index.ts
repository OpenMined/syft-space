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
    collectionName?: string
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
  system_prompt?: string | null
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

// Provider model fetching types
export interface FetchProviderModelsRequest {
  base_url: string
  api_key: string
}

export interface ProviderModelItem {
  id: string
  name: string | null
  owned_by: string | null
}

export interface FetchProviderModelsResponse {
  models: ProviderModelItem[]
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
  system_prompt?: string | null
}

export interface AttachedPolicy {
  id: string
  name: string
  policy_type: string
  configuration: Record<string, unknown>
  wallet_id?: string | null
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
  system_prompt?: string | null
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
  wallet_id?: string
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
}

export interface ConnectMarketplaceRequest {
  username: string
  password: string
  url?: string
}

export interface VerifyMarketplaceOTPRequest {
  url?: string
  email: string
  password: string
  code: string
}

export interface ResendMarketplaceOTPRequest {
  url?: string
  email: string
}

export const MarketplaceErrorCode = {
  EmailVerificationRequired: 'EMAIL_VERIFICATION_REQUIRED',
  EmailNotVerified: 'EMAIL_NOT_VERIFIED',
} as const

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

export interface TransactionResponse {
  id: string
  sender_email: string
  recipient_email: string
  amount: number
  status: string
  created_at: string
  app_name?: string
  app_ep_path?: string
}

// Slug Availability API types
export interface SlugAvailabilityRequest {
  slug: string
  marketplace_ids?: string[] | null
  check_all_marketplaces?: boolean
}

export interface SlugAvailabilityResponse {
  slug: string
  local_available: boolean
  marketplaces?: Array<{
    marketplace_id: string
    marketplace_name: string
    available: boolean | null
    error?: string
  }> | null
}

// Publish Endpoint API types
export interface PublishEndpointRequest {
  marketplace_ids?: string[] | null
  publish_to_all_marketplaces?: boolean
}

export interface PublishResult {
  marketplace_id: string
  marketplace_name: string
  success: boolean
  message?: string | null
  error?: string | null
}

export interface PublishEndpointResponse {
  endpoint_slug: string
  results: PublishResult[]
}

export interface UnpublishResult {
  marketplace_id: string
  marketplace_name: string
  success: boolean
  message?: string | null
  error?: string | null
}

export interface UpdateEndpointRequest {
  name?: string
  summary?: string
  description?: string
  system_prompt?: string | null
}

// Feedback API types
export interface FeedbackResponse {
  success: boolean
  message: string
  ticket_id: string | null
}

// Settings API types
export interface PublicUrlResponse {
  public_url: string | null
}

export interface UpdatePublicUrlRequest {
  public_url: string
}

export interface ProxyStatusResponse {
  connected: boolean
  public_url: string | null
  has_token: boolean
}

export interface DiagnosticsResponse {
  enabled: boolean
}

export interface UpdateDiagnosticsRequest {
  enabled: boolean
}

// Endpoint query API types
export interface EndpointQueryMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface EndpointQueryRequest {
  messages: EndpointQueryMessage[]
  max_tokens?: number
  temperature?: number
  similarity_threshold?: number
  limit?: number
  stop_sequences?: string[]
}

export interface ChatDocumentResponse {
  document_id: string
  content: string
  metadata: Record<string, unknown>
  similarity_score: number
  source_endpoint_slug?: string
  source_endpoint_name?: string
}

export interface ChatReferencesResponse {
  documents: ChatDocumentResponse[]
  search_engine: string | null
}

export interface ChatMessageResponse {
  role: string
  content: string
  tokens: number
}

export interface ChatTokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface ChatSummaryResponse {
  id: string
  model: string
  message: ChatMessageResponse
  finish_reason: string
  usage: ChatTokenUsage
}

export interface EndpointQueryResponse {
  summary: ChatSummaryResponse | null
  references: ChatReferencesResponse | null
}

// Wallet API types
export interface WalletResponse {
  id: string
  wallet_type: string
  name: string
  currency: string
  country: string | null
  is_active: boolean
  display: Record<string, string>
  created_at: string
  updated_at: string
}

export interface WalletListItem {
  id: string
  wallet_type: string
  name: string
  currency: string
  country: string | null
  is_active: boolean
  display: Record<string, string>
  created_at: string
}

export interface MppBalanceResponse {
  balance: number
  currency: string
  recent_transactions: TransactionResponse[]
  wallet_configured: boolean
}

// Wallet-scoped payment API types

export interface UserBalanceResponse {
  wallet_id: string
  user_email: string
  balance: number
  currency: string
}

export interface LedgerEntryResponse {
  id: string
  transaction_id: string
  type: string
  amount: number
  currency: string
  charge_unit: string
  charge_quantity: number
  user_email: string
  wallet_id: string | null
  endpoint_id: string | null
  created_at: string
}

export interface LedgerEntryPage {
  items: LedgerEntryResponse[]
  next_cursor: string | null
}
