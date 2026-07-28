import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { creditsApi } from '@/api/endpoints/credits'
import { requestsApi } from '@/api/endpoints/requests'
import { setupApi } from '@/api/endpoints/setup'
import { spacesApi } from '@/api/endpoints/spaces'
import type {
  EarningsResponse,
  MemberEarningsResponse,
  OutstandingBalanceResponse,
  RequestResponse,
  SpaceResponse,
  SpaceRuntimeStatus,
  WalletStatusResponse,
} from '@/api/types'
import type {
  ApprovalConfig,
  Payout,
  SharedWallet,
  Space,
  SpaceHealth,
  SpaceRequest,
  TopUp,
  WalletProvider,
} from '@/lib/types'
import { SPACE_INCLUDES, slugify } from '@/lib/types'
import { useSessionStore } from '@/stores/session'

/** How often a PROVISIONING request is polled for progress (ms). */
const PROVISION_POLL_INTERVAL = 3000

/**
 * Station state — fully server-backed: requests/spaces via their endpoints,
 * wallet/earnings/balances via /credits.
 */
export const useStationStore = defineStore('station', () => {
  const requests = ref<SpaceRequest[]>([])
  const spaces = ref<Space[]>([])
  const wallet = ref<SharedWallet | null>(null)
  /** Raw admin earnings payload — getters below derive every view from it. */
  const earnings = ref<EarningsResponse | null>(null)
  const balances = ref<OutstandingBalanceResponse[]>([])
  /** The member's own money view (payable is the headline number). */
  const memberEarnings = ref<MemberEarningsResponse | null>(null)
  /** Syft-space version (image tag) the station deploys — set at onboarding, editable in Settings. */
  const supportedVersion = ref('')
  /** Public domain spaces get subdomains on — empty until the admin sets it. */
  const domain = ref('')
  /** The station's own public host, surfaced at onboarding so the admin
   *  confirms it and hangs spaces off it. Empty in host-run dev. */
  const stationHost = ref('')
  /** Setup done ⇔ the domain is set. The admin dashboard shows the setup dialog until then. */
  const onboarded = computed(() => domain.value !== '')
  /** True once the backend's setup has been fetched (gates the setup dialog). */
  const setupLoaded = ref(false)

  // ---- Setup (server-backed) ----

  async function loadSetup(): Promise<void> {
    const setup = await setupApi.get()
    domain.value = setup.domain
    stationHost.value = setup.station_host
    supportedVersion.value = setup.supported_version
    setupLoaded.value = true
  }

  /** First-run setup: domain + version. Setting the domain is what marks setup done. */
  async function completeOnboarding(input: { domain: string; version: string }): Promise<void> {
    const setup = await setupApi.update({
      domain: input.domain,
      supported_version: input.version,
    })
    domain.value = setup.domain
    supportedVersion.value = setup.supported_version
  }

  /** Settings: bump the version the station deploys ("update all" applies it). */
  async function setSupportedVersion(version: string): Promise<void> {
    const setup = await setupApi.update({ supported_version: version })
    supportedVersion.value = setup.supported_version
  }

  // ---- Requests & spaces (server-backed) ----

  function mapRequest(r: RequestResponse): SpaceRequest {
    return {
      id: r.id,
      spaceName: r.space_name,
      subdomain: r.subdomain,
      requesterEmail: r.owner_email,
      purpose: r.reason,
      createdAt: r.created_at,
      status: r.status,
      // The backend keeps one note per request: a rejection note when
      // rejected, the provisioning error when failed.
      rejectReason: r.status === 'rejected' ? (r.reject_reason ?? undefined) : undefined,
      failureError: r.status === 'failed' ? (r.reject_reason ?? undefined) : undefined,
      spaceId: r.space_id ?? undefined,
      origin: r.origin === 'admin' ? 'admin' : undefined,
    }
  }

  function mapSpace(s: SpaceResponse): Space {
    // Health and API-key state come from separate endpoints; keep whatever
    // was already known while a refresh is in flight.
    const existing = spaceById(s.id)
    return {
      id: s.id,
      name: s.name,
      subdomain: s.subdomain,
      url: s.url,
      ownerEmail: s.owner_email,
      health: existing?.health ?? 'healthy',
      createdAt: s.created_at,
      adminUrl: existing?.adminUrl,
      version: s.version,
    }
  }

  /** Upsert one server request into the local list (newest first). */
  function applyRequest(r: RequestResponse): SpaceRequest {
    const mapped = mapRequest(r)
    const index = requests.value.findIndex((existing) => existing.id === mapped.id)
    if (index >= 0) requests.value[index] = mapped
    else requests.value.unshift(mapped)
    return mapped
  }

  async function loadRequests(): Promise<void> {
    const list = await requestsApi.list() // scoped by role on the backend
    requests.value = list.map(mapRequest)
    // Resume progress tracking for anything still being provisioned
    for (const request of requests.value) {
      if (request.status === 'provisioning') trackProvisioning(request.id)
    }
  }

  const statusToHealth: Record<SpaceRuntimeStatus, SpaceHealth> = {
    running: 'healthy',
    paused: 'paused',
    unavailable: 'unhealthy',
    not_found: 'unhealthy',
  }

  /** Refresh one space's live runtime status + signed-in admin URL. */
  async function refreshSpaceState(spaceId: string): Promise<void> {
    const space = spaceById(spaceId)
    if (!space) return
    const [status, adminUrl] = await Promise.all([
      spacesApi.status(spaceId).catch(() => null),
      spacesApi.adminUrl(spaceId).catch(() => null),
    ])
    if (status) space.health = statusToHealth[status.status]
    if (adminUrl) space.adminUrl = adminUrl.url
  }

  async function loadSpaces(): Promise<void> {
    const session = useSessionStore()
    const list = session.isAdmin ? await spacesApi.list() : await spacesApi.mine()
    spaces.value = list.map(mapSpace)
    await Promise.all(spaces.value.map((s) => refreshSpaceState(s.id)))
  }

  /** Poll a PROVISIONING request until it settles, then refresh spaces. */
  const polling = new Set<string>()
  function trackProvisioning(requestId: string): void {
    if (polling.has(requestId)) return
    polling.add(requestId)
    const timer = setInterval(async () => {
      try {
        const updated = await requestsApi.get(requestId)
        applyRequest(updated)
        if (updated.status !== 'provisioning') {
          clearInterval(timer)
          polling.delete(requestId)
          if (updated.status === 'active') await loadSpaces()
        }
      } catch {
        clearInterval(timer)
        polling.delete(requestId)
      }
    }, PROVISION_POLL_INTERVAL)
  }

  const pendingCount = computed(() => requests.value.filter((r) => r.status === 'pending').length)

  /**
   * "Every space includes" list shown to members and admin. The shared
   * wallet is optional — its line only appears when one is configured.
   */
  const spaceIncludes = computed(() =>
    wallet.value
      ? [
          ...SPACE_INCLUDES,
          `Payments set up for you — get paid through the station (${wallet.value.currency})`,
        ]
      : [...SPACE_INCLUDES],
  )

  // ---- Earnings (credits model: derived from the station's ledger API) ----

  function mapWallet(w: WalletStatusResponse): SharedWallet | null {
    if (!w.configured || !w.provider || !w.currency) return null
    return {
      provider: w.provider as WalletProvider,
      currency: w.currency,
      hubConnected: w.wallet_owner !== null,
    }
  }

  /** Cash collected at the gateway = credits users bought at the station. */
  const totalCollected = computed(() => earnings.value?.totals.credits_sold ?? 0)

  /** What spaces earned, net of refunds — from the station's spend ledger. */
  const totalEarned = computed(() => earnings.value?.totals.earned ?? 0)

  /** Unspent user credit — a liability the station holds, never paid to members. */
  const totalUserCredit = computed(() => earnings.value?.totals.outstanding_balance ?? 0)

  /** Recent settled top-ups (the admin feed). */
  const topUps = computed<TopUp[]>(() =>
    (earnings.value?.recent_top_ups ?? []).map((t) => ({
      id: t.invoice_id,
      userEmail: t.user_email,
      bundleName: t.bundle_name,
      amount: t.amount,
      currency: t.currency,
      paidAt: t.paid_at ?? t.created_at,
    })),
  )

  /** Recorded payouts, newest first. */
  const payouts = computed<Payout[]>(() =>
    (earnings.value?.payouts ?? []).map((p) => ({
      id: p.id,
      spaceId: p.space_id,
      amount: p.amount,
      paidAt: p.created_at,
      note: p.note || undefined,
    })),
  )

  /**
   * Per-space rollup for the payout table, sorted by payable desc. Earnings
   * rows carry space_id; names/owners are joined from the spaces registry
   * (a deleted space keeps earning history but loses its name).
   */
  const earnedBySpace = computed(() => {
    if (!earnings.value) return []
    // Last day each space earned anything, from the daily series.
    const lastDay = new Map<string, string>()
    for (const d of earnings.value.daily) {
      const prev = lastDay.get(d.space_id)
      if (!prev || d.day > prev) lastDay.set(d.space_id, d.day)
    }
    return earnings.value.spaces
      .map((row) => {
        const space = spaces.value.find((s) => s.id === row.space_id)
        return {
          spaceId: row.space_id,
          slug: space?.subdomain ?? row.space_id.slice(0, 8),
          spaceName: space?.name ?? 'Deleted space',
          ownerEmail: space?.ownerEmail ?? '—',
          earned: row.earned,
          queries: row.query_count,
          lastActiveAt: lastDay.get(row.space_id) ?? '',
          paidOut: row.paid_out,
          payable: row.payable,
        }
      })
      .sort((a, b) => b.payable - a.payable)
  })

  const totalPayable = computed(() =>
    earnedBySpace.value.reduce((sum, row) => sum + row.payable, 0),
  )

  /** Per-user credit balances (topped up / spent / remaining). */
  const userBalances = computed(() =>
    balances.value.map((b) => ({
      email: b.user_email,
      toppedUp: b.topped_up,
      spent: b.spent,
      balance: b.balance,
    })),
  )

  /**
   * A subdomain is reserved by a running space or an in-flight provisioning
   * request (pending requests are not reserved — the admin can still edit).
   */
  function subdomainInUse(slug: string, excludeRequestId?: string): boolean {
    return (
      spaces.value.some((s) => s.url.includes(`//${slug}.`)) ||
      requests.value.some(
        (r) => r.subdomain === slug && r.status === 'provisioning' && r.id !== excludeRequestId,
      )
    )
  }

  /** Daily earned totals for the last `days` days (oldest first) for the chart. */
  function earnedByDay(days: number): { date: string; total: number }[] {
    const buckets: { date: string; total: number }[] = []
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(Date.now() - i * 24 * 60 * 60 * 1000)
      buckets.push({ date: d.toISOString().slice(0, 10), total: 0 })
    }
    const byDate = new Map(buckets.map((b) => [b.date, b]))
    for (const row of earnings.value?.daily ?? []) {
      const bucket = byDate.get(row.day)
      if (bucket) bucket.total += row.earned
    }
    return buckets
  }

  function requestsFor(email: string): SpaceRequest[] {
    return requests.value
      .filter((r) => r.requesterEmail === email && r.status !== 'withdrawn')
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  }

  function spaceById(id: string): Space | undefined {
    return spaces.value.find((s) => s.id === id)
  }

  // ---- Credits loads (server-backed) ----

  /** Wallet presence + bundle catalog (any signed-in user). */
  async function loadWallet(): Promise<void> {
    wallet.value = mapWallet(await creditsApi.wallet())
  }

  /** Admin: the full money dashboard (earnings + outstanding balances). */
  async function loadEarnings(): Promise<void> {
    const [earned, outstanding] = await Promise.all([creditsApi.earnings(), creditsApi.balances()])
    earnings.value = earned
    balances.value = outstanding.balances
  }

  /** Member: what their spaces earned and are still owed. */
  async function loadMemberEarnings(): Promise<void> {
    memberEarnings.value = await creditsApi.myEarnings()
  }

  async function submitRequest(input: {
    spaceName: string
    purpose: string
  }): Promise<SpaceRequest> {
    const created = await requestsApi.submit({
      space_name: input.spaceName,
      subdomain: slugify(input.spaceName),
      reason: input.purpose,
    })
    return applyRequest(created)
  }

  /** Approve (admin): the backend starts provisioning; we poll for progress. */
  async function approveRequest(requestId: string, config: ApprovalConfig): Promise<void> {
    const approved = await requestsApi.approve(requestId, {
      space_name: config.spaceName,
      subdomain: config.subdomain,
      attach_wallet: config.attachWallet ?? true,
    })
    applyRequest(approved)
    trackProvisioning(requestId)
  }

  /** Retry a FAILED request (admin) — same review-and-confirm as approve. */
  async function retryProvision(requestId: string, _config: ApprovalConfig): Promise<void> {
    const retried = await requestsApi.retry(requestId)
    applyRequest(retried)
    trackProvisioning(requestId)
  }

  /**
   * Admin creates a space directly — a request record is still created so
   * provisioning progress, failures/retry, and the owner's member-dashboard
   * view all reuse the same machinery as approved requests.
   */
  async function createSpace(input: {
    spaceName: string
    subdomain: string
    ownerEmail: string
  }): Promise<SpaceRequest> {
    const created = await requestsApi.submit({
      space_name: input.spaceName,
      subdomain: input.subdomain,
      owner_email: input.ownerEmail,
    })
    const approved = await requestsApi.approve(created.id, {})
    const request = applyRequest(approved)
    trackProvisioning(request.id)
    return request
  }

  /** Reject a pending request with a reason (admin). */
  async function rejectRequest(requestId: string, reason: string): Promise<void> {
    applyRequest(await requestsApi.reject(requestId, { reason }))
  }

  /** Member withdraws their own pending request. */
  async function withdrawRequest(requestId: string): Promise<void> {
    applyRequest(await requestsApi.withdraw(requestId))
  }

  /** Restart is not wired to the backend yet. */
  function restartSpace(_spaceId: string) {}

  /** Pause = scale the space's deployment to 0; data (volume + vector db) stays. */
  async function pauseSpace(spaceId: string): Promise<void> {
    const status = await spacesApi.pause(spaceId)
    const space = spaceById(spaceId)
    if (space) space.health = statusToHealth[status.status]
  }

  /** Start = scale back to 1; the pod takes a moment to become ready. */
  async function startSpace(spaceId: string): Promise<void> {
    const space = spaceById(spaceId)
    if (!space || space.health !== 'paused') return
    await spacesApi.resume(spaceId)
    space.health = 'starting'
    // Poll until the pod reports ready (or give up and show live state)
    for (let attempt = 0; attempt < 20; attempt++) {
      await new Promise((r) => setTimeout(r, PROVISION_POLL_INTERVAL))
      const status = await spacesApi.status(spaceId).catch(() => null)
      if (status?.status === 'running') {
        space.health = 'healthy'
        return
      }
    }
    await refreshSpaceState(spaceId)
  }

  /** Per-space update is not wired to the backend yet. */
  function updateSpace(_spaceId: string) {}

  /** Update-all is not wired to the backend yet. */
  function updateAllSpaces() {}

  /** Issue a fresh API key; the space applies it on its next restart. */
  async function regenerateApiKey(spaceId: string): Promise<void> {
    const rotated = await spacesApi.regenerateToken(spaceId)
    const space = spaceById(spaceId)
    if (space) space.adminUrl = rotated.url
  }

  /** Record a manual payout (server-capped at the space's payable). */
  async function recordPayout(input: {
    spaceId: string
    amount: number
    note?: string
  }): Promise<void> {
    await creditsApi.recordPayout({
      space_id: input.spaceId,
      amount: input.amount,
      note: input.note?.trim() || undefined,
    })
    await loadEarnings() // payable/paid-out columns come from the server
  }

  /**
   * Configure (or replace) the station's shared gateway wallet. Spaces
   * approved before the wallet existed are attached in the same call; their
   * Secrets apply on the next pod restart.
   */
  async function setupWallet(input: {
    provider: WalletProvider
    currency: string
    credentials: Record<string, string>
    /** Paste an existing SyftHub API token — or set syfthubPassword to mint one. */
    syfthubApiToken?: string
    syfthubPassword?: string
  }): Promise<{ spacesAttached: number; spacesFailed: number }> {
    const result = await creditsApi.setupWallet({
      provider: input.provider,
      currency: input.currency,
      credentials: input.credentials,
      ...(input.syfthubApiToken ? { syfthub_api_token: input.syfthubApiToken } : {}),
      ...(input.syfthubPassword ? { syfthub_password: input.syfthubPassword } : {}),
    })
    wallet.value = mapWallet(result)
    return { spacesAttached: result.spaces_attached, spacesFailed: result.spaces_failed }
  }

  /**
   * Delete tears the space down completely — deployment, volume and vector
   * database included (a freed subdomain must never surface another owner's
   * data). Keyed by the space's request, which is marked DELETED.
   */
  async function deleteSpace(spaceId: string): Promise<void> {
    const request = requests.value.find((r) => r.spaceId === spaceId)
    if (!request) return
    applyRequest(await requestsApi.deleteSpace(request.id))
    spaces.value = spaces.value.filter((s) => s.id !== spaceId)
  }

  return {
    requests,
    spaces,
    wallet,
    memberEarnings,
    topUps,
    payouts,
    supportedVersion,
    domain,
    stationHost,
    onboarded,
    setupLoaded,
    loadSetup,
    completeOnboarding,
    pendingCount,
    totalCollected,
    totalEarned,
    totalUserCredit,
    earnedBySpace,
    totalPayable,
    userBalances,
    earnedByDay,
    subdomainInUse,
    spaceIncludes,
    setupWallet,
    requestsFor,
    spaceById,
    loadRequests,
    loadSpaces,
    loadWallet,
    loadEarnings,
    loadMemberEarnings,
    refreshSpaceState,
    submitRequest,
    approveRequest,
    createSpace,
    retryProvision,
    rejectRequest,
    withdrawRequest,
    regenerateApiKey,
    recordPayout,
    restartSpace,
    pauseSpace,
    startSpace,
    updateSpace,
    updateAllSpaces,
    setSupportedVersion,
    deleteSpace,
  }
})
