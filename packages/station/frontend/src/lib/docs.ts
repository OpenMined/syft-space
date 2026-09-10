/**
 * Canonical links into the public Syft Station docs. Product copy stays terse
 * and points here for the full explanation, so the UI never duplicates the
 * docs. Change a path once here and every surface follows.
 *
 * https://syft.docs.openmined.org/station
 */
const BASE = 'https://syft.docs.openmined.org/station'

export const DOCS = {
  station: BASE,
  dnsAndTls: `${BASE}/operators/dns-and-tls`,
  creditsAndPayouts: `${BASE}/operators/credits-and-payouts`,
  versions: `${BASE}/operators/versions`,
  membersQuickstart: `${BASE}/members/quickstart`,
} as const
