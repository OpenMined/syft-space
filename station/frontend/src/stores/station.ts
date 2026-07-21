import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { requestsApi } from '@/api/endpoints/requests'
import { setupApi } from '@/api/endpoints/setup'
import { spacesApi } from '@/api/endpoints/spaces'
import type { RequestResponse, SpaceResponse, SpaceRuntimeStatus } from '@/api/types'
import type {
  ApprovalConfig,
  CreditDebit,
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

let idCounter = 0
function nextId(prefix: string): string {
  idCounter += 1
  return `${prefix}_${idCounter.toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

function daysAgo(n: number): string {
  return new Date(Date.now() - n * 24 * 60 * 60 * 1000).toISOString()
}

/**
 * Station state: space requests + provisioned spaces are server-backed;
 * the wallet/earnings data is still mocked in-memory until the credits
 * service lands.
 */
export const useStationStore = defineStore('station', () => {
  const requests = ref<SpaceRequest[]>([])
  const spaces = ref<Space[]>([])
  const wallet = ref<SharedWallet | null>(null)
  const topUps = ref<TopUp[]>([])
  const debits = ref<CreditDebit[]>([])
  const payouts = ref<Payout[]>([])
  /** Syft-space version (image tag) the station deploys — set at onboarding, editable in Settings. */
  const supportedVersion = ref('')
  /** Public domain spaces get subdomains on — empty until the admin sets it. */
  const domain = ref('')
  /** Setup done ⇔ the domain is set. The admin dashboard shows the setup dialog until then. */
  const onboarded = computed(() => domain.value !== '')
  /** True once the backend's setup has been fetched (gates the setup dialog). */
  const setupLoaded = ref(false)
  const seededFor = ref<string | null>(null)

  // ---- Setup (server-backed) ----

  async function loadSetup(): Promise<void> {
    const setup = await setupApi.get()
    domain.value = setup.domain
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
      url: s.url,
      ownerEmail: s.owner_email,
      health: existing?.health ?? 'healthy',
      createdAt: s.created_at,
      apiKeyClaimed: existing?.apiKeyClaimed ?? true,
      version: s.version,
      walletSeeded: existing?.walletSeeded ?? true,
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

  /** Refresh one space's live runtime status + API-key claim state. */
  async function refreshSpaceState(spaceId: string): Promise<void> {
    const space = spaceById(spaceId)
    if (!space) return
    const [status, token] = await Promise.all([
      spacesApi.status(spaceId).catch(() => null),
      spacesApi.tokenStatus(spaceId).catch(() => null),
    ])
    if (status) space.health = statusToHealth[status.status]
    if (token) space.apiKeyClaimed = token.revealed
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

  // ---- Earnings (credits model: the station's own ledger) ----

  /** Cash collected at the gateway = credits users bought at the station. */
  const totalCollected = computed(() => topUps.value.reduce((sum, t) => sum + t.amount, 0))

  /** What spaces earned = per-query price × queries, from the debit ledger. */
  const totalEarned = computed(() => debits.value.reduce((sum, d) => sum + d.amount, 0))

  /** Unspent user credit — a liability the station holds, never paid to members. */
  const totalUserCredit = computed(() => totalCollected.value - totalEarned.value)

  /** Per-space rollup for the payout table, sorted by payable desc. */
  const earnedBySpace = computed(() => {
    const rollup = new Map<
      string,
      {
        spaceName: string
        ownerEmail: string
        earned: number
        queries: number
        lastActiveAt: string
      }
    >()
    for (const d of debits.value) {
      const row = rollup.get(d.spaceSlug)
      if (row) {
        row.earned += d.amount
        row.queries += d.queries
        if (d.day > row.lastActiveAt) row.lastActiveAt = d.day
      } else {
        rollup.set(d.spaceSlug, {
          spaceName: d.spaceName,
          ownerEmail: d.ownerEmail,
          earned: d.amount,
          queries: d.queries,
          lastActiveAt: d.day,
        })
      }
    }
    return [...rollup.entries()]
      .map(([slug, row]) => {
        const paidOut = payouts.value
          .filter((p) => p.spaceSlug === slug)
          .reduce((sum, p) => sum + p.amount, 0)
        return { slug, ...row, paidOut, payable: row.earned - paidOut }
      })
      .sort((a, b) => b.payable - a.payable)
  })

  const totalPayable = computed(() =>
    earnedBySpace.value.reduce((sum, row) => sum + row.payable, 0),
  )

  /** Per-user credit balances (topped up − spent), sorted by balance desc. */
  const userBalances = computed(() => {
    const map = new Map<string, { toppedUp: number; spent: number }>()
    for (const t of topUps.value) {
      const row = map.get(t.userEmail) ?? { toppedUp: 0, spent: 0 }
      row.toppedUp += t.amount
      map.set(t.userEmail, row)
    }
    for (const d of debits.value) {
      const row = map.get(d.userEmail) ?? { toppedUp: 0, spent: 0 }
      row.spent += d.amount
      map.set(d.userEmail, row)
    }
    return [...map.entries()]
      .map(([email, row]) => ({ email, ...row, balance: row.toppedUp - row.spent }))
      .sort((a, b) => b.balance - a.balance)
  })

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
    for (const d of debits.value) {
      const bucket = byDate.get(d.day.slice(0, 10))
      if (bucket) bucket.total += d.amount
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

  /**
   * Seed the wallet/earnings demo data once per signed-in user. Payments
   * stay mocked until the credits service lands; requests and spaces are
   * server-backed and never seeded.
   */
  function seedForDemo(memberEmail: string, _memberName: string) {
    if (seededFor.value === memberEmail) return
    seededFor.value = memberEmail

    const firstRun = !onboarded.value

    // Shared wallet pre-seeded so the Earnings tab has data — unless the
    // admin already completed setup (respect an explicit skip there).
    if (!wallet.value && firstRun) {
      wallet.value = {
        provider: 'xendit',
        currency: 'USD',
        maskedKey: 'xnd_prod_••••3kf9',
        createdAt: daysAgo(20),
      }
    }
    if (!wallet.value) return

    // Credits model: users top up once at the station checkout…
    // (the member has their own balance too — they query other spaces)
    const seedTopUps: Array<[user: string, amount: number, ago: number]> = [
      [memberEmail, 30, 4.4],
      ['kim@labmate.org', 20, 3.2],
      ['kim@labmate.org', 50, 9.1],
      ['ravi@labmate.org', 10, 6.4],
      ['pat@student.edu', 25, 8.3],
      ['jo@student.edu', 40, 7.6],
      ['counsel@client.com', 60, 10.2],
      ['paralegal@lawfirm.com', 5, 9.8],
    ]
    topUps.value = seedTopUps.map(([user, amount, ago]) => ({
      id: nextId('top'),
      userEmail: user,
      amount,
      currency: 'USD',
      paidAt: daysAgo(ago),
    }))

    // …and spend per query at any space (daily aggregates: price × queries,
    // attributed to the space whose token authorized them). kim and pat also
    // spend at spaces run by other members — credits work station-wide.
    const seedDebits: Array<
      [slug: string, owner: string, user: string, amount: number, queries: number, ago: number]
    > = [
      ['research-lab', memberEmail, 'kim@labmate.org', 12, 120, 2.1],
      ['research-lab', memberEmail, 'kim@labmate.org', 8, 80, 5.3],
      ['research-lab', memberEmail, 'ravi@labmate.org', 4, 40, 4.2],
      ['econ-archive', 'lee@university.edu', memberEmail, 6, 120, 1.8],
      ['legal-docs', 'ana@lawfirm.com', memberEmail, 4, 16, 0.5],
      ['econ-archive', 'lee@university.edu', 'pat@student.edu', 10, 200, 1.2],
      ['econ-archive', 'lee@university.edu', 'jo@student.edu', 15, 300, 6.1],
      ['econ-archive', 'lee@university.edu', 'jo@student.edu', 7, 140, 3.4],
      ['legal-docs', 'ana@lawfirm.com', 'counsel@client.com', 25, 100, 2.6],
      ['legal-docs', 'ana@lawfirm.com', 'paralegal@lawfirm.com', 3, 12, 8.1],
      ['legal-docs', 'ana@lawfirm.com', 'kim@labmate.org', 5, 20, 0.9],
      ['summer-workshop', 'lee@university.edu', 'pat@student.edu', 2, 40, 12.4],
    ]
    debits.value = seedDebits.map(([slug, owner, user, amount, queries, ago]) => ({
      id: nextId('deb'),
      spaceSlug: slug,
      spaceName: slug,
      ownerEmail: owner,
      userEmail: user,
      amount,
      queries,
      day: daysAgo(ago),
    }))

    // One payout already recorded so the payable column has variety
    payouts.value = [
      {
        id: nextId('out'),
        spaceSlug: 'econ-archive',
        amount: 20,
        currency: 'USD',
        paidAt: daysAgo(6),
        note: 'June payout — bank transfer',
      },
    ]
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

  /** Issue a fresh API key; the owner claims it from their dashboard again. */
  async function regenerateApiKey(spaceId: string): Promise<void> {
    const status = await spacesApi.regenerateToken(spaceId)
    const space = spaceById(spaceId)
    if (space) space.apiKeyClaimed = status.revealed
  }

  /** Record a manual payout to a member against their space's collected total. */
  function recordPayout(input: { spaceSlug: string; amount: number; note?: string }) {
    payouts.value.unshift({
      id: nextId('out'),
      spaceSlug: input.spaceSlug,
      amount: input.amount,
      currency: wallet.value?.currency ?? 'USD',
      paidAt: new Date().toISOString(),
      note: input.note?.trim() || undefined,
    })
  }

  /**
   * Configure (or replace) the station's shared gateway wallet. New
   * credentials reach each space's Secret on its next pod restart, so every
   * existing space flips to "wallet pending restart".
   */
  function configureWallet(input: { provider: WalletProvider; apiKey: string; currency: string }) {
    const prefix = input.provider === 'xendit' ? 'xnd_prod_' : 'sk_live_'
    wallet.value = {
      provider: input.provider,
      currency: input.currency,
      maskedKey: `${prefix}••••${input.apiKey.slice(-4)}`,
      createdAt: new Date().toISOString(),
    }
    for (const space of spaces.value) space.walletSeeded = false
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
    topUps,
    debits,
    payouts,
    supportedVersion,
    domain,
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
    configureWallet,
    requestsFor,
    spaceById,
    seedForDemo,
    loadRequests,
    loadSpaces,
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
