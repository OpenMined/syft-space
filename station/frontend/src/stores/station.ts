import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { setupApi } from '@/api/endpoints/setup'
import type {
  ApprovalConfig,
  CreditDebit,
  Payout,
  SharedWallet,
  Space,
  SpaceRequest,
  TopUp,
  WalletProvider,
} from '@/lib/types'
import { STATION_DOMAIN, SPACE_INCLUDES, SUPPORTED_VERSION, slugify } from '@/lib/types'

/** Simulated provisioning delay (ms) so the PROVISIONING state is visible. */
const PROVISION_DELAY = 6000
const RESTART_DELAY = 3000

let idCounter = 0
function nextId(prefix: string): string {
  idCounter += 1
  return `${prefix}_${idCounter.toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

function makeApiKey(): string {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let key = 'sk-space-'
  for (let i = 0; i < 40; i++) key += chars[Math.floor(Math.random() * chars.length)]
  return key
}

function daysAgo(n: number): string {
  return new Date(Date.now() - n * 24 * 60 * 60 * 1000).toISOString()
}

/**
 * Mock station state: space requests + provisioned spaces.
 *
 * All transitions are simulated in-memory (reset on refresh). Approving a
 * request "provisions" after a delay; a subdomain containing "fail"
 * demonstrates the FAILED + retry path.
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
      .filter((r) => r.requesterEmail === email)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  }

  function spaceById(id: string): Space | undefined {
    return spaces.value.find((s) => s.id === id)
  }

  /** Seed demo data once per signed-in member so every state is visible. */
  function seedForDemo(memberEmail: string, memberName: string) {
    if (seededFor.value === memberEmail) return
    seededFor.value = memberEmail
    requests.value = []
    spaces.value = []

    // Member-first demo: if the admin hasn't set a domain yet, fall back to
    // the demo default so seeded URLs work (setup state itself is
    // server-backed now and never touched here).
    const firstRun = !onboarded.value
    const seedDomain = domain.value || STATION_DOMAIN

    // A space of the member's that is already active, API key not yet claimed
    const activeSpace: Space = {
      id: nextId('spc'),
      name: 'research-lab',
      url: `https://research-lab.${seedDomain}`,
      ownerEmail: memberEmail,
      health: 'healthy',
      createdAt: daysAgo(2),
      apiKey: makeApiKey(),
      apiKeyClaimed: false,
      version: SUPPORTED_VERSION,
      walletSeeded: true,
    }
    spaces.value.push(activeSpace)
    requests.value.push({
      id: nextId('req'),
      spaceName: 'research-lab',
      subdomain: 'research-lab',
      requesterEmail: memberEmail,
      requesterName: memberName,
      purpose: 'RAG over our public health research corpus.',
      createdAt: daysAgo(2),
      status: 'active',
      spaceId: activeSpace.id,
    })

    // A pending request of the member's
    requests.value.push({
      id: nextId('req'),
      spaceName: 'genomics-pilot',
      subdomain: 'genomics-pilot',
      requesterEmail: memberEmail,
      requesterName: memberName,
      purpose: 'Pilot for the genomics team, mostly PDF ingestion.',
      createdAt: daysAgo(0.2),
      status: 'pending',
    })

    // A rejected request of the member's
    requests.value.push({
      id: nextId('req'),
      spaceName: 'test-space',
      subdomain: 'test-space',
      requesterEmail: memberEmail,
      requesterName: memberName,
      purpose: 'Just trying things out.',
      createdAt: daysAgo(5),
      status: 'rejected',
      rejectReason: 'Please use a descriptive space name tied to a project.',
    })

    // Other members' pending requests (admin queue)
    requests.value.push({
      id: nextId('req'),
      spaceName: 'clinical-notes',
      subdomain: 'clinical-notes',
      requesterEmail: 'dana@hospital.org',
      requesterName: 'Dana Reyes',
      purpose: 'Private QA over anonymized clinical notes.',
      createdAt: daysAgo(0.5),
      status: 'pending',
    })
    requests.value.push({
      id: nextId('req'),
      spaceName: 'policy-briefs',
      subdomain: 'policy-briefs',
      requesterEmail: 'sam@thinktank.net',
      requesterName: 'Sam Okafor',
      purpose: 'Searchable archive of policy briefs for our analysts.',
      createdAt: daysAgo(1.1),
      status: 'pending',
    })

    // Other members' running spaces (admin Spaces tab)
    spaces.value.push({
      id: nextId('spc'),
      name: 'econ-archive',
      url: `https://econ-archive.${seedDomain}`,
      ownerEmail: 'lee@university.edu',
      health: 'healthy',
      createdAt: daysAgo(12),
      apiKey: makeApiKey(),
      apiKeyClaimed: true,
      version: '0.9.2',
      walletSeeded: true,
    })
    spaces.value.push({
      id: nextId('spc'),
      name: 'legal-docs',
      url: `https://legal-docs.${seedDomain}`,
      ownerEmail: 'ana@lawfirm.com',
      health: 'unhealthy',
      createdAt: daysAgo(30),
      apiKey: makeApiKey(),
      apiKeyClaimed: true,
      version: SUPPORTED_VERSION,
      walletSeeded: true,
    })
    spaces.value.push({
      id: nextId('spc'),
      name: 'summer-workshop',
      url: `https://summer-workshop.${seedDomain}`,
      ownerEmail: 'lee@university.edu',
      health: 'paused',
      createdAt: daysAgo(45),
      apiKey: makeApiKey(),
      apiKeyClaimed: true,
      version: '0.9.1',
      walletSeeded: false,
    })

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

  function submitRequest(input: {
    spaceName: string
    requesterEmail: string
    requesterName: string
    purpose: string
  }): SpaceRequest {
    const request: SpaceRequest = {
      id: nextId('req'),
      spaceName: input.spaceName,
      subdomain: slugify(input.spaceName),
      requesterEmail: input.requesterEmail,
      requesterName: input.requesterName,
      purpose: input.purpose,
      createdAt: new Date().toISOString(),
      status: 'pending',
    }
    requests.value.unshift(request)
    return request
  }

  /** Kick off provisioning for a request: PROVISIONING → (delay) → ACTIVE, or FAILED if subdomain contains "fail". */
  function startProvisioning(request: SpaceRequest, config: ApprovalConfig) {
    request.spaceName = config.spaceName
    request.subdomain = config.subdomain
    request.status = 'provisioning'
    request.failureError = undefined

    setTimeout(() => {
      if (request.subdomain.includes('fail')) {
        request.status = 'failed'
        request.failureError =
          'Pod failed readiness probe: ImagePullBackOff for syft-space:latest (simulated)'
        return
      }
      const space: Space = {
        id: nextId('spc'),
        name: config.spaceName,
        url: `https://${config.subdomain}.${domain.value}`,
        ownerEmail: request.requesterEmail,
        health: 'healthy',
        createdAt: new Date().toISOString(),
        apiKey: makeApiKey(),
        apiKeyClaimed: false,
        version: supportedVersion.value,
        walletSeeded: wallet.value !== null,
      }
      spaces.value.unshift(space)
      request.status = 'active'
      request.spaceId = space.id
    }, PROVISION_DELAY)
  }

  function approveRequest(requestId: string, config: ApprovalConfig) {
    const request = requests.value.find((r) => r.id === requestId)
    if (!request || (request.status !== 'pending' && request.status !== 'failed')) return
    startProvisioning(request, config)
  }

  function retryProvision(requestId: string, config: ApprovalConfig) {
    approveRequest(requestId, config)
  }

  /**
   * Admin creates a space directly — no member request to approve. A request
   * record is still created (origin: 'admin') so provisioning progress,
   * failures/retry, and the owner's member-dashboard view all reuse the same
   * machinery as approved requests.
   */
  function createSpace(input: {
    spaceName: string
    subdomain: string
    ownerEmail: string
  }): SpaceRequest {
    const request: SpaceRequest = {
      id: nextId('req'),
      spaceName: input.spaceName,
      subdomain: input.subdomain,
      requesterEmail: input.ownerEmail,
      requesterName: input.ownerEmail.split('@')[0] ?? input.ownerEmail,
      purpose: '',
      createdAt: new Date().toISOString(),
      status: 'pending',
      origin: 'admin',
    }
    requests.value.unshift(request)
    startProvisioning(request, { spaceName: input.spaceName, subdomain: input.subdomain })
    return request
  }

  /** Reject a pending request, or abandon a failed provisioning attempt. */
  function rejectRequest(requestId: string, reason: string) {
    const request = requests.value.find((r) => r.id === requestId)
    if (!request || (request.status !== 'pending' && request.status !== 'failed')) return
    request.status = 'rejected'
    request.rejectReason = reason
  }

  /** Member withdraws their own pending request. */
  function withdrawRequest(requestId: string) {
    const request = requests.value.find((r) => r.id === requestId)
    if (!request || request.status !== 'pending') return
    requests.value = requests.value.filter((r) => r.id !== requestId)
  }

  /** One-time API key reveal: returns the key and marks it claimed. */
  function claimApiKey(spaceId: string): string | null {
    const space = spaceById(spaceId)
    if (!space || space.apiKeyClaimed) return null
    space.apiKeyClaimed = true
    return space.apiKey
  }

  function restartSpace(spaceId: string) {
    const space = spaceById(spaceId)
    if (!space || space.health === 'paused') return
    space.health = 'restarting'
    setTimeout(() => {
      space.health = 'healthy'
      if (wallet.value) space.walletSeeded = true
    }, RESTART_DELAY)
  }

  /** Pause = scale the space's deployment to 0; data (volume + vector db) stays. */
  function pauseSpace(spaceId: string) {
    const space = spaceById(spaceId)
    if (!space) return
    space.health = 'paused'
  }

  /** Start = scale back to 1; pod takes a moment to become ready. */
  function startSpace(spaceId: string) {
    const space = spaceById(spaceId)
    if (!space || space.health !== 'paused') return
    space.health = 'starting'
    setTimeout(() => {
      space.health = 'healthy'
      if (wallet.value) space.walletSeeded = true
    }, RESTART_DELAY)
  }

  /**
   * Update = patch the deployment's image tag to the supported version.
   * Running space: pod is recreated (brief downtime). Paused space: spec
   * updates instantly and the new version applies at the next start.
   */
  function updateSpace(spaceId: string) {
    const space = spaceById(spaceId)
    if (!space || space.version === supportedVersion.value) return
    if (space.health === 'paused') {
      space.version = supportedVersion.value
      return
    }
    space.health = 'restarting'
    setTimeout(() => {
      space.version = supportedVersion.value
      space.health = 'healthy'
      if (wallet.value) space.walletSeeded = true
    }, RESTART_DELAY)
  }

  function updateAllSpaces() {
    for (const space of spaces.value) {
      if (space.version !== supportedVersion.value) updateSpace(space.id)
    }
  }

  /** Issue a fresh API key; the owner claims it from their dashboard again. */
  function regenerateApiKey(spaceId: string) {
    const space = spaceById(spaceId)
    if (!space) return
    space.apiKey = makeApiKey()
    space.apiKeyClaimed = false
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

  /** Delete removes the running space; data (PVC + Chroma database) is retained unless purged. */
  function deleteSpace(spaceId: string, purge = false) {
    const space = spaceById(spaceId)
    if (!space) return
    spaces.value = spaces.value.filter((s) => s.id !== spaceId)
    const request = requests.value.find((r) => r.spaceId === spaceId)
    if (request) {
      request.status = 'deleted'
      request.rejectReason = purge
        ? 'Space and all of its data were removed by the station admin.'
        : 'Space was removed by the station admin. Its data (volume and vector database) is retained and can be reattached.'
      request.spaceId = undefined
    }
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
    submitRequest,
    approveRequest,
    createSpace,
    retryProvision,
    rejectRequest,
    withdrawRequest,
    claimApiKey,
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
