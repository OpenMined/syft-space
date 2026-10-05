export interface SourceItem {
  external_id: string
  display_name: string
  parent_id?: string | null
  is_container: boolean
  is_leaf: boolean
  size_bytes?: number | null
  metadata: Record<string, unknown>
}

export interface SourceBrowseRequest {
  dtype: string
  configuration?: Record<string, unknown>
  parent_id?: string | null
  cursor?: string | null
}

export interface SourceBrowseResponse {
  parent_id?: string | null
  items: SourceItem[]
  next_cursor?: string | null
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
  configuration: Record<string, unknown>
  // Picker selection for the dataset. Stored server-side in the
  // dataset_selection table, never inside configuration.
  selected_items?: SelectionItemRequest[]
}

// One pick to add to a dataset's selection (create or add-source flows).
export interface SelectionItemRequest {
  item_id: string
  description?: string | null
}

// A dataset_selection row as returned by the API.
export interface SelectedItemResponse {
  item_id: string
  description: string | null
  added_at: string
}

// The dataset's full selection after an add/remove operation.
export interface SelectionResponse {
  selected_items: SelectedItemResponse[]
}

// A page of a dataset's selection picks (GET /datasets/{name}/selection).
export interface SelectionPageResponse {
  items: SelectedItemResponse[]
  total: number
}

// Every selected item id for a dataset (GET /datasets/{name}/selection/ids).
export interface SelectionIdsResponse {
  item_ids: string[]
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
    selected_items_count?: number
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
  // The list view ships a count + short preview instead of the full array,
  // so a dataset with many picks does not bloat the list payload. Fetch the
  // full, paged selection via datasetsApi.getSelection.
  selected_items_count?: number
  selected_items_preview?: SelectedItemResponse[]
}

export interface BrowseSchemaProperty {
  title?: string
  description?: string
  type?: string
  format?: string
  default?: unknown
}

export interface BrowseSchema {
  properties?: Record<string, BrowseSchemaProperty>
  required?: string[]
}

export interface DatasetTypeInfoResponse {
  name: string
  description: string
  config_schema: Record<string, unknown>
  icon: string
  enabled: boolean
  browse_schema: BrowseSchema
  browsable: boolean
}

// Ingestion API types
export interface IngestionJobResponse {
  id: string
  external_id: string
  fingerprint: string
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
    selected_items_count?: number
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

export interface ManagedResponse {
  /** True when a station launched this space — self-hosted onboarding is trimmed. */
  managed: boolean
  public_url: string | null
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

// --- Benchmark reporting ---------------------------------------------------
//
// A benchmark measures this endpoint and hands the Space a card; the Space
// publishes it to the marketplaces this endpoint is on. These types are what
// the owner reads back — and what he decides a retraction from.

export type BenchmarksMode = 'off' | 'local'

export interface BenchmarksModeResponse {
  mode: BenchmarksMode
}

export interface UpdateBenchmarksModeRequest {
  mode: BenchmarksMode
}

/** What kind of product was measured. The score cannot be read without it. */
export type BenchmarkKind = 'answering' | 'retrieval'

export interface BenchmarkAnswerable {
  samples: number
  correct: number
  abstain: number
  hallucinate: number
  /** Of the times it answered, the share that were wrong. */
  lmi?: number | null
}

export interface BenchmarkUnanswerable {
  samples: number
  /** Share of questions with no answer that got an answer anyway. */
  fabricated: number
}

export interface BenchmarkModelRow {
  model: string
  samples: number
  accuracy: number
  fabrication?: number | null
  lmi?: number | null
  /** What this endpoint's material did to that model's honesty. */
  context_gain?: number | null
  /** What the same model scored with no material in front of it at all. */
  closed_accuracy?: number | null
}

export interface BenchmarkSkillRow {
  generator: string
  samples: number
  accuracy: number
}

/**
 * What the figures rest on — and the owner's grounds to doubt them.
 *
 * `flags` are codes, not sentences: the benchmark does not write this UI's
 * words.
 */
export interface BenchmarkTrust {
  judges: number
  agreement?: number | null
  consistency?: number | null
  even_coverage: boolean
  failed: number
  pending: number
  flags: string[]
}

export interface BenchmarkDataset {
  mode: string
  window_days: number
  cohort: string
  questions: number
}

/**
 * What the denial loop found: whether a right answer survives being pushed on.
 *
 * Absent where the block was never run — which is the ordinary state, and not
 * the same as an endpoint that never gave in.
 */
export interface BenchmarkPressure {
  samples: number
  flip_rate?: number | null
  /** Share still standing after each round of push-back, first round first. */
  held?: number[]
}

export interface BenchmarkTemperature {
  temperature: number
  accuracy: number
}

/**
 * What the monte carlo block found: whether the same question gets the same
 * answer, and at which temperature that stops being true.
 */
export interface BenchmarkStability {
  samples: number
  consistency?: number | null
  by_temperature?: BenchmarkTemperature[]
}

export interface BenchmarkInstrument {
  profile: string
  judge: string
  judges: number
  subjects: number
}

export interface BenchmarkCard {
  version: number
  kind: BenchmarkKind
  arm: string
  /** The launch this card is of; empty where the run belongs to none. */
  job?: string
  checked_at: string
  score?: number | null
  fabrication_rate?: number | null
  reliable: boolean
  samples: number
  answerable?: BenchmarkAnswerable | null
  unanswerable?: BenchmarkUnanswerable | null
  discrimination?: number | null
  retrieval?: number | null
  models: BenchmarkModelRow[]
  skills: BenchmarkSkillRow[]
  trust?: BenchmarkTrust | null
  dataset?: BenchmarkDataset | null
  instrument?: BenchmarkInstrument | null
  pressure?: BenchmarkPressure | null
  stability?: BenchmarkStability | null
}

export interface EndpointQualityResponse {
  endpoint_slug: string
  /** False when nobody ever measured it — which is not a score of zero. */
  reported: boolean
  kind?: BenchmarkKind | null
  score?: number | null
  fabrication_rate?: number | null
  samples?: number | null
  reliable?: boolean | null
  checked_at?: string | null
  /** Marketplaces currently showing this card. */
  published_to: string[]
  report?: BenchmarkCard | null
}

export interface QualityMarketplaceResult {
  marketplace_id: string
  marketplace_name: string
  success: boolean
  supported: boolean
  message?: string | null
  error?: string | null
}

/**
 * One run in an endpoint's history: the badge figures, and what became of it.
 *
 * Exactly one card in a history is `standing` — the newest one nobody
 * withdrew, which is the card the marketplaces show.
 */
export interface QualityCardSummary {
  id: string
  kind: BenchmarkKind
  score?: number | null
  fabrication_rate?: number | null
  samples: number
  reliable: boolean
  /** When the benchmark that produced this card ran. */
  checked_at: string
  /** When this Space was handed it. */
  reported_at: string
  retracted_at?: string | null
  standing: boolean
  models: number
  profile: string
  /** The whole card, so the page can draw this run without a request of its own. */
  report: BenchmarkCard
}

export interface QualityHistoryResponse {
  endpoint_slug: string
  /** Newest run first, withdrawn ones included. */
  cards: QualityCardSummary[]
}

export interface PublishQualityCardResponse {
  endpoint_slug: string
  card_id: string
  published: boolean
  results: QualityMarketplaceResult[]
}

export interface RetractQualityResponse {
  endpoint_slug: string
  /** False means there was nothing to remove, which is not an error. */
  cleared: boolean
  results: QualityMarketplaceResult[]
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
  managed: boolean
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
  managed: boolean
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

// --- Benchmarks -------------------------------------------------------------
//
// Settings travel as open documents. Naming their fields here would mean
// editing this file every time the benchmark grows a knob, and a forgotten
// edit would mean a form that silently cannot configure something that already
// works. The benchmark describes its own fields — see BenchmarkField — and
// this side supplies the words.

export type BenchmarkLayer = Record<string, unknown>

export interface BenchmarkField {
  name: string
  type: string
  group: string
  choices?: (string | number)[]
  // The name of a list too long to inline. `choices` carries its own values —
  // three arms, four blocks — and the form draws them as they arrive. Three
  // hundred models cannot travel that way and change on the benchmark's
  // refresh rather than on a release here, so what arrives is the name of a
  // catalogue and the form fetches it. Today there is one: 'models'.
  catalog?: string
  item_type?: string
  minimum?: number
  maximum?: number
}

// One model, as the benchmark knows it. The identifier is the benchmark's, not
// a provider's: the same model is `anthropic/claude-sonnet-5` there and
// `claude-sonnet-5` at Anthropic's own API, and which name goes on the wire is
// decided where the call is made. Storing the provider's spelling here would
// mean rewriting every setting the day the provider changes.
export interface BenchmarkModel {
  id: string
  name: string
  vendor: string
  // The dated build serving that name today. Reported, not part of the
  // identity: a vendor refreshing a model must not fork its history.
  build: string
  context_length: number | null
  max_output_tokens: number | null
  input_modalities: string[]
  supports: string[]
  pricing: Record<string, string | null>
  retires_on: string | null
  routes: Record<string, string>
  aliases: Record<string, string>
  source: string
  local: boolean
}

export interface BenchmarkModelCatalog {
  models: BenchmarkModel[]
  vendors: string[]
  // Moving names — `~anthropic/claude-sonnet-latest` — and what each resolves
  // to right now. Shown, never stored: the benchmark pins them as it saves.
  pins: Record<string, string>
  // Source -> when it was last refreshed.
  fetched: Record<string, string>
  total: number
}

export interface BenchmarkFieldCatalogue {
  groups?: string[]
  instrument?: BenchmarkField[]
  probe?: BenchmarkField[]
}

export interface BenchmarkRoleProvider {
  role: string
  url: string
  key_set: boolean
  own: boolean
}

export interface BenchmarkProvider {
  url: string
  app_name: string
  key_set: boolean
  external_hosts: string[]
  roles: BenchmarkRoleProvider[]
  // Set by the benchmark, and false today: the provider is configured in that
  // service's environment. The key never leaves it — not as a value, and not
  // into any store on this side.
  editable: boolean
}

export interface BenchmarkCapabilities {
  version?: string
  profile?: string
  arms?: string[]
  blocks?: string[]
  generators?: string[]
  subject_models?: string[]
  judge_models?: string[]
  text_metrics?: string[]
  extractive_modes?: string[]
  external_models?: boolean
  provider?: BenchmarkProvider
}

export interface BenchmarkConnection {
  id: string
  name: string
  url: string
  console_url: string
  has_token: boolean
  space_url: string
  chroma_host: string
  chroma_port: number
  container: string
  instrument: BenchmarkLayer
  probe: BenchmarkLayer
  reachable: boolean
  detail: string
  checked_at: string | null
  capabilities: BenchmarkCapabilities
  fields: BenchmarkFieldCatalogue
  defaults: { instrument?: BenchmarkLayer; probe?: BenchmarkLayer }
  is_default: boolean
  is_active: boolean
  endpoints: number
}

export interface BenchmarkConnectionRequest {
  name: string
  url: string
  // Where a browser reaches the console, when that differs from `url` — a
  // Docker-internal hostname resolves for this backend's own calls but not
  // for the owner's browser. Blank falls back to `url`.
  console_url?: string
  // Omitted rather than blank when unchanged: the form is never told the key,
  // so it cannot send it back, and without this rule renaming a connection
  // would silently revoke its access.
  token?: string
  space_url?: string
  chroma_host?: string
  chroma_port?: number
  container?: string
  is_default?: boolean
  is_active?: boolean
}

export interface BenchmarkSettingsRequest {
  instrument: BenchmarkLayer
  probe: BenchmarkLayer
}

export interface BenchmarkJob {
  id: string
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  phase: string
  /** pipeline, filter or judge — which operation this job is, not where it is. */
  kind: string
  // Passes finished out of passes planned. Zero as the total means the scale is
  // not known yet, not that there is nothing to do.
  done: number
  total: number
  // What is running right now, and how far into itself it is. Two counts rather
  // than one: passes and the questions inside a pass are different units, and
  // merged into a single bar they misreport both.
  arm: string
  block: string
  model: string
  step_done: number
  step_total: number
  message: string
  error: string
  trigger: string
  /**
   * The card assembled after measuring, in the shape a marketplace is handed
   * — present whether or not this run was published. Absent when the run
   * never asked a question at all (a launch that only refreshed the
   * question set), or when nothing was graded.
   */
  card?: BenchmarkCard | null
  created_at: string | null
  started_at: string | null
  finished_at: string | null
}

export interface BenchmarkTarget {
  endpoint_slug: string
  // False means nobody opted this endpoint in. That is not a score of zero and
  // must never be rendered as one.
  measured: boolean
  connection_id: string | null
  connection_name: string
  enabled: boolean
  collection: string
  resolved_collection: string
  probe: BenchmarkLayer
  instrument: BenchmarkLayer
  schedule: string
  schedule_at: string
  /** When the benchmark will next fire the schedule, UTC. It decides, not us. */
  next_run_at: string | null
  synced_at: string | null
  fields: BenchmarkFieldCatalogue
  defaults: { instrument?: BenchmarkLayer; probe?: BenchmarkLayer }
  connection_probe: BenchmarkLayer
  connection_instrument: BenchmarkLayer
  capabilities: BenchmarkCapabilities
  last_job: BenchmarkJob | null
  reachable: boolean
  detail: string
}

export interface BenchmarkTargetRequest {
  connection_id?: string | null
  enabled: boolean
  collection?: string
  probe: BenchmarkLayer
  instrument?: BenchmarkLayer
  schedule?: string
  schedule_at?: string
}

export interface ProviderRole {
  url: string
  url_default: string
  key_set: boolean
  key_updated_at: string | null
}

export interface ProviderResponse {
  shared: ProviderRole
  generator: ProviderRole
  subject: ProviderRole
  judge: ProviderRole
}

export interface ProviderUrls {
  ollama_url: string
  generator_url: string
  subject_url: string
  judge_url: string
}

export interface BenchmarkCheck {
  ok: boolean
  corpus: boolean
  endpoint: boolean
  transport: string
  collection: string
  available: string[]
  chunks: number
  usable: number
  documents: number
  response_type: string
  blocked_arms: Record<string, string>
  problems: string[]
}

export interface BenchmarkRunRequest {
  generate?: boolean | null
  /** Screen the pending pairs generation just built; empty — follow `generate`. */
  filter?: boolean | null
  /** Ask and grade after the question set is built; empty — yes. */
  evaluate?: boolean | null
  /** Collect answers without calling a judge, leaving every verdict pending. */
  defer_judging?: boolean
  publish?: boolean
  limit?: number | null
}

export type BenchmarkPairStatus = 'pending' | 'active' | 'rejected' | 'retired'
/**
 * The three outcomes, and the two states that are not outcomes.
 *
 * `pending` — no judge has looked yet. `technical` — nothing was measured:
 * the endpoint unreachable, the provider refusing, the judge silent. Neither
 * enters a share, and neither can be recorded by hand.
 */
export type BenchmarkVerdict = 'correct' | 'abstain' | 'hallucinate' | 'pending' | 'technical'

export interface BenchmarkPair {
  id: string
  generator: string
  task_type: string
  cohort: string
  status: BenchmarkPairStatus
  status_note: string
  question: string
  answer: string
  context: string
  expected_behavior: string
  document_title: string
  file_name: string
  meta: Record<string, unknown>
  created_at: string
  has_results: boolean
}

export interface BenchmarkPairPage {
  items: BenchmarkPair[]
  total: number
}

/** One objection and the answer it drew. */
export interface BenchmarkDenialRound {
  round: number
  objection: string
  answer: string
}

/** How the pressure on one answer ended (`denial_loop`). */
export interface BenchmarkDenial {
  /** Objections actually put — the loop stops at the one the model gives in on. */
  rounds: number
  flipped: boolean
  flip_round: number | null
  note: string
  /** Objections the run was configured to put, which `rounds` is read against. */
  limit: number
  /** Empty on rows measured before transcripts were kept. */
  log: BenchmarkDenialRound[]
}

/** One repeat: how hot it was asked, and what came back. */
export interface BenchmarkRepeatTrial {
  trial: number
  temperature: number
  answer: string
  correct: boolean
}

/** How far one answer repeated when the question was asked again (`monte_carlo`). */
export interface BenchmarkRepeats {
  trials: number
  accuracy: number
  /** The share that gave the most frequent answer — not the share that were right. */
  consistency: number
  by_temperature: Record<string, number>
  note: string
  /** Empty on rows measured before transcripts were kept. */
  log: BenchmarkRepeatTrial[]
}

/** One chunk the endpoint's retrieval returned for a question. */
export interface BenchmarkFragment {
  file_name: string
  score: number
  content: string
  /** The length before the ceiling. Longer than `content` — the model was
   * shown a shortened chunk. */
  chars?: number | null
}

/**
 * How the call that produced an answer ended.
 *
 * The budget doubles until the answer fits or reaches `answer_max_tokens`, so
 * `truncated` means it reached that number and still did not finish. It is
 * graded like any other. Absent with `audit_log` off, which is not "not cut".
 */
export interface BenchmarkCall {
  truncated: boolean
  finish_reason: string
  /** The budget the call ended on, after any doubling — the number to raise. */
  max_tokens: number | null
  length_retries: number
}

/**
 * What was actually sent — for the answer, and for the verdict on it.
 *
 * Any field can be empty: nothing is kept with the benchmark's `audit_log`
 * off, and the judge fields are empty wherever the verdict cost no call —
 * which `judged_without_model` tells apart from a record never written.
 */
export interface BenchmarkPrompts {
  responder_system: string
  responder_prompt: string
  /** The material mixed into the "With data" prompt, on its own. */
  context: string
  judge_system: string
  judge_prompt: string
  /** The judge's answer before it was parsed into a verdict. */
  judge_raw: string
  judged_without_model: boolean
}

export interface BenchmarkResult {
  id: string
  qa_id: string
  question: string
  answer: string
  generator: string
  verdict: BenchmarkVerdict
  reasoning: string
  judge_model: string
  context_mode: string
  block: string
  model: string
  created_at: string
  is_latest: boolean
  /**
   * What the block did, where it did anything beyond asking.
   *
   * Both blocks record the answer they STARTED from, so without these a
   * pressure row and a repeat row are the direct row printed again — and the
   * `hallucinate` on a pressure row, which means the answer was given up rather
   * than wrong, reads as the judge contradicting itself.
   */
  denial?: BenchmarkDenial | null
  repeats?: BenchmarkRepeats | null
  /**
   * Whether the chunk the question grew from was found, and where. An
   * abstention cannot be read without them: on a miss it is correct
   * behaviour, on a hit it is blindness. Null where nothing was retrieved.
   */
  retrieval_hit?: boolean | null
  retrieval_rank?: number | null
  call?: BenchmarkCall | null
  /** The run's two ceilings. Null where the run does not carry them. */
  context_docs?: number | null
  fragment_max_chars?: number | null
  /**
   * Only on a listing asked for with `prompts`: megabytes over a whole page,
   * so fetched one question at a time. Null with `audit_log` off, and
   * `fragments` null where nothing was retrieved at all.
   */
  prompts?: BenchmarkPrompts | null
  fragments?: BenchmarkFragment[] | null
}

export interface BenchmarkResultPage {
  items: BenchmarkResult[]
  total: number
}

export interface BenchmarkReportShare {
  samples: number
  correct: number
  abstain: number
  hallucinate: number
  lmi: number | null
}

export interface BenchmarkReportControl {
  samples: number
  fabricated: number
}

export interface BenchmarkReportModelRow {
  model: string
  samples: number
  accuracy: number
  fabrication: number | null
  lmi: number | null
  context_gain: number | null
  closed_accuracy?: number | null
}

export interface BenchmarkReportSkillRow {
  generator: string
  samples: number
  accuracy: number
}

export interface BenchmarkReportTrust {
  judges: number
  agreement: number | null
  consistency: number | null
  even_coverage: boolean
  failed: number
  pending: number
  flags: string[]
  /** Present only on the owner's own console build — never on a published card. */
  doubts?: string[]
}

export interface BenchmarkReportDataset {
  mode: string
  window_days: number
  cohort: string
  questions: number
}

export interface BenchmarkReportInstrument {
  profile: string
  judge: string
  judges: number
  subjects: number
}

/**
 * One endpoint's measured quality — what `/console/report` (and, once
 * published, `/console/publish`) return. The owner's own build additionally
 * carries `score_label` and `trust.doubts`; a published card never does.
 */
export interface BenchmarkReport {
  version: number
  kind: 'answering' | 'retrieval'
  arm: string
  /** The launch this card is of; empty where the run belongs to none. */
  job?: string
  checked_at: string
  score: number | null
  score_label?: string
  fabrication_rate: number | null
  reliable: boolean
  samples: number
  answerable?: BenchmarkReportShare
  unanswerable?: BenchmarkReportControl
  discrimination: number | null
  retrieval: number | null
  models: BenchmarkReportModelRow[]
  skills: BenchmarkReportSkillRow[]
  trust?: BenchmarkReportTrust
  dataset?: BenchmarkReportDataset
  instrument?: BenchmarkReportInstrument
  pressure?: BenchmarkPressure | null
  stability?: BenchmarkStability | null
}

/**
 * A ready-to-open link into the benchmark's own console for one endpoint —
 * generation, filtering, execution, judging and the report, all in one
 * place. `url` already carries the session token; it is scoped to this one
 * endpoint and expires, minted fresh on every open rather than reused.
 */
export interface BenchmarkSession {
  url: string
  expires_at: string
}

// --- Benchmark results: the per-run report ------------------------------------

/** A queued or running job, as the runs list shows it. */
export interface BenchmarkRunProgress {
  job_id: string
  state: 'queued' | 'running'
  trigger: string
  kind: string
  phase: string
  block: string
  model: string
  step_done: number
  step_total: number
  done: number
  total: number
  message: string
  created_at: string | null
  started_at: string | null
}

/** One model's figures in a run. Rates are 0..1; lift is in points, −100..100. */
export interface BenchmarkModelFigures {
  model: string
  asked: number
  graded_alone: number
  graded_with: number
  right_alone: number
  right_with: number
  rate_alone: number | null
  rate_with: number | null
  lift: number | null
  made_up_alone: number | null
  made_up_with: number | null
  pending: number
  technical: number
}

/** A finished run. Lifts are in points. */
export interface BenchmarkRunSummary {
  job_id: string
  created_at: string | null
  finished_at: string | null
  trigger: string
  window_days: number | null
  articles: number | null
  questions: number | null
  models: BenchmarkModelFigures[]
  lift_lo: number | null
  lift_hi: number | null
  /** The published card differs from the live figures. */
  card_outdated: boolean
  published: boolean
  card_id: string | null
}

export type BenchmarkRunStatusFilter = 'all' | 'published' | 'private'

export interface BenchmarkRunList {
  /** Every queued or running job; never paged or filtered. */
  in_progress: BenchmarkRunProgress[]
  items: BenchmarkRunSummary[]
  total: number
}

export interface BenchmarkTally {
  correct: number
  abstain: number
  hallucinate: number
  pending: number
  technical: number
  graded: number
}

export type BenchmarkQuestionGroup = 'fixed' | 'either' | 'still' | 'worse'

export interface BenchmarkKindFigures {
  generator: string
  asked: number
  graded_alone: number
  graded_with: number
  right_alone: number
  right_with: number
  rate_alone: number | null
  rate_with: number | null
  lift: number | null
}

export interface BenchmarkRunChecks {
  challenged: number
  denial_limit: number | null
  /** Length `denial_limit`; element k is the share still right after round k + 1. */
  held_by_round: number[]
  kept_right: number | null
  repeated: number
  same_answer: number | null
  by_temperature: { t: number; accuracy: number }[]
  trick_asked: number
  trick_answered: number
  /** The trick check for the model on its own; null when not measured. */
  trick_alone_asked: number | null
  trick_alone_answered: number | null
  searched: number
  search_found: number | null
  missed: number
  answers: number
  judges_agreed: number
  agreement: number | null
}

export interface BenchmarkModelReport extends BenchmarkModelFigures {
  tally: { alone: BenchmarkTally; with: BenchmarkTally }
  /** Sorted by lift, highest first. */
  kinds: BenchmarkKindFigures[]
  groups: Record<BenchmarkQuestionGroup, number>
  checks: BenchmarkRunChecks
}

export interface BenchmarkRunFunnel {
  /** Null when the run reused earlier questions. */
  written: number | null
  removed: Record<string, number>
  removed_total: number | null
  asked: number
  trick: number
}

export interface BenchmarkRunMethod {
  articles_from: string | null
  articles_to: string | null
  generator_model: string | null
  kinds: string[]
  trick: number
  context_docs: number | null
  judges: string[]
  profile: string | null
  next_run_at: string | null
}

export interface BenchmarkRunReport {
  run: BenchmarkRunSummary
  funnel: BenchmarkRunFunnel
  models: BenchmarkModelReport[]
  /** Primary first. */
  judges: string[]
  method: BenchmarkRunMethod
}

export interface BenchmarkQuestionRow {
  n: number
  qa_id: string
  generator: string
  document_title: string
  file_name: string
  question: string
  gold_answer: string
  status: string
  verdict_alone: BenchmarkVerdict | null
  verdict_with: BenchmarkVerdict | null
  group: BenchmarkQuestionGroup | null
  overridden: boolean
  excluded: boolean
}

export type BenchmarkExcludedFilter = 'include' | 'only' | 'hide'

export interface BenchmarkQuestionQuery {
  model: string
  group?: BenchmarkQuestionGroup
  generator?: string
  q?: string
  excluded?: BenchmarkExcludedFilter
  limit?: number
  offset?: number
}

export interface BenchmarkQuestionPage {
  items: BenchmarkQuestionRow[]
  total: number
  /** Respect `generator`, `q` and `excluded`, not `group`. */
  counts: { all: number } & Record<BenchmarkQuestionGroup, number>
}

export interface BenchmarkVerdictOverride {
  id: string
  verdict: BenchmarkVerdict
  reasoning: string
  created_at: string
}

export interface BenchmarkArmDetail {
  answer: string
  verdict: BenchmarkVerdict
  reasoning: string
  /** The row to post an override against. */
  result_id: string
  override: BenchmarkVerdictOverride | null
  retrieval: { hit: boolean | null; rank: number | null; context_docs: number | null } | null
  denial: { rounds: number; flipped: boolean; flip_round: number | null; limit: number } | null
  repeats: {
    trials: number
    right: number
    consistency: number
    by_temperature: Record<string, number>
  } | null
}

export interface BenchmarkQuestionJudge {
  model: string
  primary: boolean
  alone: BenchmarkVerdict | null
  with: BenchmarkVerdict | null
}

export interface BenchmarkQuestionExclusion {
  reason: string
  created_at: string
}

export interface BenchmarkQuestionDetail {
  question: BenchmarkQuestionRow
  /** The gold source paragraph. */
  context: string
  arms: { alone: BenchmarkArmDetail | null; with: BenchmarkArmDetail | null }
  judges: BenchmarkQuestionJudge[]
  judges_agreed: boolean | null
  exclusion: BenchmarkQuestionExclusion | null
}

/** A passage sent with the with-data answer. */
export interface BenchmarkReportFragment {
  file_name: string
  document_title: string
  score: number
  content: string
  is_source: boolean
}

export interface BenchmarkRunPublishResponse {
  published: boolean
  card_id?: string | null
  /** Marketplaces that did not accept the change. */
  refused: QualityMarketplaceResult[]
}
