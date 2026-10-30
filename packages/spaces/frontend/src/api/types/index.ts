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
// These types list the fields the client reads, not the full wire format.

export type BenchmarkLayer = Record<string, unknown>

/** The instrument keys the Benchmark setup tab writes by name. */
export type BenchmarkInstrumentLayer = BenchmarkLayer & {
  /** Web check model (step 3). Unset means no web check. */
  filter_model?: string | null
  /** Who settles a question returned by hand: the web check, or the user. */
  manual_status_priority?: 'filter' | 'manual'
  /** Model calls in flight at once, 1..64. */
  concurrency?: number
  /** 0..2, or "default" for the model's own; null inherits. */
  judge_temperature?: number | 'default' | null
  judge_reasoning_effort?: 'none' | 'minimal' | 'low' | 'medium' | 'high' | 'default'
}

// One model, identified by the benchmark's id (e.g. `anthropic/claude-sonnet-5`).
export interface BenchmarkModel {
  id: string
  name: string
  vendor: string
  context_length: number | null
  supports: string[]
  /** Built-in search ("native"), the OpenRouter web plugin, or none; optional. */
  web_search?: BenchmarkWebSearch
  pricing: Record<string, string | null>
  retires_on: string | null
  local: boolean
}

export type BenchmarkWebSearch = 'native' | 'plugin' | 'none'

/** A page the model cited for an answer it searched the web for. */
export interface BenchmarkCitation {
  url: string
  title?: string | null
}

export interface BenchmarkModelCatalog {
  models: BenchmarkModel[]
  vendors: string[]
  // Moving names (`~anthropic/claude-sonnet-latest`) and what each resolves to.
  pins: Record<string, string>
  // Source -> when it was last refreshed.
  fetched: Record<string, string>
}

export interface BenchmarkCapabilities {
  profile?: string
  generators?: string[]
  subject_models?: string[]
  judge_models?: string[]
  external_models?: boolean
}

export interface BenchmarkConnection {
  id: string
  name: string
  url: string
  has_token: boolean
  space_url: string
  chroma_host: string
  chroma_port: number
  container: string
  reachable: boolean
  detail: string
  capabilities: BenchmarkCapabilities
  endpoints: number
}

export interface BenchmarkConnectionRequest {
  name: string
  url: string
  // Omitted to keep the stored key.
  token?: string
  space_url?: string
  chroma_host?: string
  chroma_port?: number
  container?: string
}

export interface BenchmarkJob {
  id: string
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  phase: string
  /** pipeline, filter or judge — which operation this job is, not where it is. */
  kind: string
  // The current pass and its progress (questions within the pass).
  block: string
  model: string
  step_done: number
  step_total: number
  message: string
  created_at: string | null
  started_at: string | null
  finished_at: string | null
  /** Null until the evaluate phase starts. */
  progress_plan?: BenchmarkProgressPlan | null
}

/** What the evaluate phase will ask, fixed when it starts. */
export interface BenchmarkProgressPlan {
  /** Per pass. */
  questions: number
  models: string[]
  /** Arms in plan order. */
  conditions: string[]
  /** Blocks in plan order. */
  checks: string[]
  skipped_monte_carlo: string[]
}

export interface BenchmarkTarget {
  endpoint_slug: string
  // False: this endpoint is not measured (not a score of zero).
  measured: boolean
  connection_id: string | null
  enabled: boolean
  collection: string
  resolved_collection: string
  probe: BenchmarkLayer
  instrument: BenchmarkLayer
  schedule: string
  schedule_at: string
  /** When the benchmark next runs the schedule, UTC. */
  next_run_at: string | null
  /** The benchmark's own values, under the endpoint's layers. */
  defaults: { instrument?: BenchmarkLayer; probe?: BenchmarkLayer }
  capabilities: BenchmarkCapabilities
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
  /** Null when the benchmark's keys could not be read. */
  key_set: boolean | null
  key_updated_at: string | null
  /** Whether the address the role calls stays inside the perimeter, as the benchmark judges it; null when it did not say. */
  local: boolean | null
}

/** Where an address points, as the Space backend judges it (`GET /benchmarks/locality`). */
export interface AddressLocality {
  /** Empty when the address cannot be read. */
  host: string
  local: boolean
}

export interface ProviderResponse {
  shared: ProviderRole
  generator: ProviderRole
  subject: ProviderRole
  judge: ProviderRole
  /** The web check; blank fields take the models under test's. */
  filter: ProviderRole
}

/** One provider key after it was stored or cleared (the credential routes' reply). */
export interface ProviderKeyState {
  key_set: boolean
  key_updated_at: string | null
}

/** Every role's address at once; a blank one removes that override. */
export interface ProviderUrls {
  ollama_url: string
  generator_url: string
  subject_url: string
  judge_url: string
  filter_url: string
}

/** Articles in the time window, counted by the benchmark's generation rule. */
export interface BenchmarkWindow {
  /** Articles in the window, undated ones included (generation keeps them). */
  count: number
}

export interface BenchmarkRunRequest {
  generate?: boolean | null
  /** Ask and grade after the question set is built; empty — yes. */
  evaluate?: boolean | null
}

export type BenchmarkPairStatus = 'pending' | 'active' | 'rejected' | 'retired'
/** Fine outcome of a control answer; null on other kinds and under an override. */
export type BenchmarkBehavior = 'declined' | 'corrected' | 'web_sourced' | 'made_up'

/**
 * Verdicts. `web_sourced`: facts its web search supports. `pending` (not graded yet) and
 * `technical` (nothing measured) are not outcomes: they enter no share and cannot be set by hand.
 */
export type BenchmarkVerdict =
  | 'correct'
  | 'abstain'
  | 'hallucinate'
  | 'web_sourced'
  | 'incomplete'
  | 'pending'
  | 'technical'

export interface BenchmarkPair {
  id: string
  generator: string
  status: BenchmarkPairStatus
  status_note: string
  /** Why the pair is not active, as a code; null while it is. */
  status_reason?: string | null
  question: string
  answer: string
  context: string
  document_title: string
  file_name: string
  meta: Record<string, unknown>
  created_at: string
}

/** A model call behind a generated pair, as it was made. */
export interface BenchmarkRecordedCall {
  call: string
  model: string
  system: string
  /** The prompt as sent, the passage in place. */
  user: string
  reply: string
  /** The passage a writer prompt was built from; empty on a check call. */
  passage: string
  cost_usd: number | null
  latency_s: number | null
}

/** A pair read from a run's report, with the calls that wrote and checked it. */
export interface BenchmarkRunPair extends BenchmarkPair {
  /** Empty texts when none are kept; null when the pair records no call. */
  writer_call: BenchmarkRecordedCall | null
  entity_call: BenchmarkRecordedCall | null
}

/** One objection and the answer it drew. */
export interface BenchmarkDenialRound {
  round: number
  objection: string
  answer: string
}

/** How the pressure on one answer ended (`denial_loop`). */
export interface BenchmarkDenial {
  /** Objections put; the loop stops when the model gives in. */
  rounds: number
  flipped: boolean
  flip_round: number | null
  note: string
  /** Objections the run was configured to put, which `rounds` is read against. */
  limit: number
  /** Empty when no transcript is stored. */
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
  /** Empty when no transcript is stored. */
  log: BenchmarkRepeatTrial[]
}

/** One chunk the endpoint's retrieval returned for a question. */
export interface BenchmarkFragment {
  file_name: string
  score: number
  content: string
  /** Length before the ceiling; longer than `content` when the chunk was shortened. */
  chars?: number | null
}

/**
 * How the answering call ended. `truncated`: still unfinished at `answer_max_tokens`
 * (graded as usual). Absent with `audit_log` off.
 */
export interface BenchmarkCall {
  truncated: boolean
  finish_reason: string
  /** The token budget the call ended on, after any doubling. */
  max_tokens: number | null
  length_retries: number
}

/**
 * What was sent for the answer and its verdict. Empty with `audit_log` off; judge fields
 * are empty when the verdict cost no call (`judged_without_model`).
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
  /** Whether the job's figures count this row for its answer; null without the `job` filter. */
  counted?: boolean | null
  /** What the denial loop or Monte Carlo block did beyond the starting answer. */
  denial?: BenchmarkDenial | null
  repeats?: BenchmarkRepeats | null
  /** Whether the question's source chunk was retrieved, and where; null when nothing was. */
  retrieval_hit?: boolean | null
  retrieval_rank?: number | null
  call?: BenchmarkCall | null
  /** The run's two ceilings. Null where the run does not carry them. */
  context_docs?: number | null
  fragment_max_chars?: number | null
  /** Only with `prompts`; null with `audit_log` off. */
  prompts?: BenchmarkPrompts | null
  fragments?: BenchmarkFragment[] | null
  /** Pages cited by an answer given with web search. */
  citations?: BenchmarkCitation[] | null
  /** Asked to search the web and cited nothing. */
  web_search_unused?: boolean | null
  behavior?: BenchmarkBehavior | null
}

export interface BenchmarkResultPage {
  items: BenchmarkResult[]
  total: number
}

// --- Benchmark results: the per-run report ------------------------------------

/** A queued or running job, as the runs list shows it. */
export interface BenchmarkRunProgress {
  job_id: string
  state: 'queued' | 'running'
  kind: string
  phase: string
  block: string
  model: string
  step_done: number
  step_total: number
  message: string
  created_at: string | null
  started_at: string | null
  progress_plan?: BenchmarkProgressPlan | null
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
  /** Why some answers failed; optional. */
  failure?: BenchmarkModelFailure | null
}

/** A model's failed calls: a short label and a one-sentence tooltip. */
export interface BenchmarkModelFailure {
  label: string
  detail: string
}

/** A finished run. Lifts are in points. */
export interface BenchmarkRunSummary {
  job_id: string
  created_at: string | null
  /** Job start; run duration = finished_at − started_at. */
  started_at?: string | null
  finished_at: string | null
  window_days: number | null
  /** Distinct articles of the asked questions. */
  articles: number | null
  /** `YYYY-MM-DD`: earliest and latest article date (published, else added) among them. */
  articles_first?: string | null
  articles_last?: string | null
  /** How many of `articles` have a date; the range covers only these. */
  articles_dated?: number | null
  /** Distinct articles this job wrote questions from. */
  articles_new?: number | null
  questions: number | null
  models: BenchmarkModelFigures[]
  lift_lo: number | null
  lift_hi: number | null
  /** True: the job wrote or filtered questions but asked no model. */
  build_only?: boolean
  state?: 'succeeded' | 'failed' | 'cancelled'
  /** Who stopped the job; null — it was not stopped. */
  stopped?: 'owner' | 'spending_cap' | null
  build?: BenchmarkBuildCounts | null
}

/** What one job wrote, and its filter decisions by outcome. */
export interface BenchmarkBuildCounts {
  written: number
  checked: number
  kept: number
  removed: number
  failed: number
}

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
  /** Included in `graded`. */
  web_sourced?: number
  /** Included in `graded`; neither right nor hallucinated. */
  incomplete?: number
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
  /** Trick questions answered from the web; not in `trick_answered`. */
  trick_web?: number
  /** The same for the model on its own; null when not measured. */
  trick_alone_web?: number | null
  searched: number
  search_found: number | null
  missed: number
  answers: number
  judges_agreed: number
  agreement: number | null
}

export interface BenchmarkModelReport extends BenchmarkModelFigures {
  tally: { alone: BenchmarkTally; with: BenchmarkTally }
  /** In generator registry order. */
  kinds: BenchmarkKindFigures[]
  groups: Record<BenchmarkQuestionGroup, number>
  checks: BenchmarkRunChecks
}

export interface BenchmarkRunFunnel {
  /** Null when the run reused earlier questions. */
  written: number | null
  /** By reason; a reason that removed nothing is absent. */
  removed: Record<string, number>
  /** Kept but not asked: the web check had not passed them. */
  unchecked?: number | null
  asked: number
  trick: number
}

export interface BenchmarkRunMethod {
  generator_model: string | null
  kinds: string[]
  trick: number
  profile: string | null
  /** The challenge limit per right answer; null when the block did not run. */
  denial_rounds: number | null
  /** Repeats per temperature and the temperatures, ascending; null when the block did not run. */
  repeats: { trials: number; temperatures: number[] } | null
  web_check_model?: string | null
  /** The filter judge, else Judge 1. */
  web_check_judge?: string | null
  cost?: BenchmarkRunCost | null
}

/** OpenRouter spend of one job, in USD. */
export interface BenchmarkRunCost {
  /** The key's spend after the job minus before it; null if either read failed. */
  usd: number | null
  /** Sum of per-call usage.cost. */
  usd_calls: number
  /** Sum of `by_role`; optional. */
  total_usd?: number | null
  by_role?: BenchmarkCostByRole | null
}

/** Per-call cost of one job by role, in USD. */
export interface BenchmarkCostByRole {
  writer: number
  web_check: number
  subjects: number
  judges: number
}

/** How one kind's generation went in one job. */
export interface BenchmarkKindBuild {
  kind: string
  unit: 'passage' | 'article'
  budget: number
  written: number
  units_available: number
  /** Failed ones included. */
  units_read: number
  failed_units: number
  /** Written by the top-up rounds, beyond the budget; included in `written`. */
  topped_up?: number
  dropped: Record<string, number>
  stopped: string
}

export interface BenchmarkGeneratedPage {
  kinds: BenchmarkKindBuild[]
  items: BenchmarkRunPair[]
  total: number
}

/** Questions of the target read by id, whichever job wrote them. */
export interface BenchmarkRunPairs {
  items: BenchmarkRunPair[]
  total: number
}

export type BenchmarkFilterStage = 'writing' | 'grounding' | 'control' | 'web_check'
export type BenchmarkFilterOutcome = 'kept' | 'removed' | 'failed'

export interface BenchmarkWebCheck {
  model: string
  judge: string
  answer: string
  verdict: string
  reasoning: string
  citations: BenchmarkCitation[]
  searches: number | null
  error: string | null
}

/** One filter decision a job made, on a question it wrote or an earlier one. */
export interface BenchmarkFilterDecision {
  qa_id: string
  question: string
  answer: string
  generator: string
  stage: BenchmarkFilterStage
  outcome: BenchmarkFilterOutcome
  reason: string
  reason_code: string | null
  at: string | null
  written_at: string
  /** Written by another job. */
  earlier: boolean
  status: string
  status_note: string
  web_check: BenchmarkWebCheck | null
}

/** A draft the writer threw away before it was stored. */
export interface BenchmarkDroppedDraft {
  question: string
  answer: string
  reason: string
}

/** One writer call of a job, with the drafts it dropped. */
export interface BenchmarkWriterCall {
  call: string
  generator: string
  model: string
  at: string | null
  document_title: string
  file_name: string
  passage: string
  system: string
  user: string
  reply: string
  cost_usd: number | null
  latency_s: number | null
  error: string | null
  dropped: BenchmarkDroppedDraft[]
}

export interface BenchmarkWritingPage {
  items: BenchmarkWriterCall[]
  total: number
}

export interface BenchmarkFilterPage {
  items: BenchmarkFilterDecision[]
  total: number
  counts: Record<BenchmarkFilterOutcome, number>
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
  verdict_alone: BenchmarkVerdict | null
  verdict_with: BenchmarkVerdict | null
  group: BenchmarkQuestionGroup | null
}

export interface BenchmarkQuestionQuery {
  model: string
  group?: BenchmarkQuestionGroup
  generator?: string
  q?: string
  limit?: number
  offset?: number
}

export interface BenchmarkQuestionPage {
  items: BenchmarkQuestionRow[]
  total: number
  /** Respect `generator` and `q`, not `group`. */
  counts: { all: number } & Record<BenchmarkQuestionGroup, number>
}

export interface BenchmarkArmDetail {
  answer: string
  verdict: BenchmarkVerdict
  denial: { rounds: number; flipped: boolean; flip_round: number | null; limit: number } | null
  repeats: { trials: number; right: number } | null
  /** Pages cited by an answer given with web search. */
  citations?: BenchmarkCitation[] | null
  /** Asked to search the web and cited nothing. */
  web_search_unused?: boolean | null
  /** One sentence on why it shows no search; null where it searched. */
  web_search_unused_reason?: string | null
  /** The counted fine outcome; null under an override. */
  behavior?: BenchmarkBehavior | null
}

export interface BenchmarkQuestionJudge {
  model: string
  primary: boolean
  alone: BenchmarkVerdict | null
  with: BenchmarkVerdict | null
  /** Optional, as are the behaviors. */
  alone_reasoning?: string | null
  with_reasoning?: string | null
  alone_behavior?: BenchmarkBehavior | null
  with_behavior?: BenchmarkBehavior | null
}

export interface BenchmarkQuestionDetail {
  arms: { alone: BenchmarkArmDetail | null; with: BenchmarkArmDetail | null }
  judges: BenchmarkQuestionJudge[]
}

/** A passage sent with the with-data answer. */
export interface BenchmarkReportFragment {
  file_name: string
  document_title: string
  score: number
  content: string
}
