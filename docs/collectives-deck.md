# Syft Space Collectives — Pitch Deck

> Audience: small news organizations and trade associations who would *run* the
> collective infrastructure on behalf of their members.
> Each slide has **on-screen content** and a **say-this** script — the words you
> speak while it's up.

---

## 1 — The problem

**On screen:**
- Your members own valuable data.
- They can't safely sell it alone.

**Say this:**
> Every one of your members is sitting on something AI companies want to pay
> for. A newsroom has twenty years of archives. A trade association has decades
> of reports, standards, and member submissions. The demand is real and the
> money is real. But no single small member can build the infrastructure, set up
> the billing, enforce who's allowed to use the data, and feel legally safe
> doing it. So the data just sits there. The content exists — what's missing is
> shared infrastructure and someone trusted to run it.

---

## 2 — The idea: a data collective

**On screen:**
- One organization runs the infrastructure.
- Many members plug in their data.
- Buyers query it all through one door.

**Say this:**
> The idea is simple. One organization — you — runs a single system. Each member
> connects their own data to it, and their data stays theirs. Together, those
> members add up to something a buyer can actually use: one place to query
> everyone's content at once. Think of it like a co-op. You own the building and
> the storefront. Each member keeps the keys to their own unit. The buyer walks
> into one shop instead of negotiating with twenty separate sellers.

---

## 3 — Two roles, one system

**On screen:**
- **Host** — runs the infra, manages members, sees everything.
- **Member** — connects data, sets pricing, keeps their revenue.

**Say this:**
> There are exactly two roles. The host — that's you, the association or the
> news network — runs the infrastructure and oversees the whole collective. The
> members are your tenants: each one gets a normal, private workspace that just
> happens to live on your system. It's the same application either way. When you
> log in as the host, you see across the entire collective. When a member logs
> in, they only see their own space. No member ever sees another member's data.

---

## 4 — What the host sees

**On screen:**
- **Members** — who's in, who's active, who's earning
- **Collective APIs** — the shared endpoints buyers hit
- **Stats** — total revenue, this month, active and earning members

**Say this:**
> As the host, you get one dashboard for the whole collective. You see your
> members — who's joined, who's active this month, who's actually earning. You
> see the collective APIs, which are the shared endpoints buyers query, each with
> its own revenue and traffic. And you see the money: total revenue, revenue this
> month, how many members are active, how many are earning. In our demo that's
> three hundred members, forty-seven active, ten earning. One toggle flips you
> between this collective-wide view and your own private workspace.

---

## 5 — What a member sees

**On screen:**
- Sign in once — no registration, you manage membership.
- Connect data: **WordPress · RSS · files & folders**
- Set pricing. Keep the revenue.

**Say this:**
> A member's experience is deliberately boring — in a good way. They sign in once
> with a key; there's nothing to register, because you control who's a member.
> Then they connect their data the way they already work. A newsroom points it at
> their WordPress site and the posts sync in. They add an RSS feed and new
> articles flow in as they publish. Or they just upload archives and PDFs.
> They set a price per query, and they keep what they earn. Onboarding a member
> is "paste a URL and a key" — not "migrate your whole archive."

---

## 6 — How the data becomes one product

**On screen:**
- Each member's data → their own API
- Member APIs → **collective APIs**
- Buyers query the collective, not the members

**Say this:**
> Here's the part that makes it valuable. Each member's data becomes their own
> small API. The system rolls those individual APIs up into collective APIs — for
> example, "search every member's archive" or "retrieve documents across the
> whole network." The buyer never talks to twenty members. They query one
> endpoint and get answers drawn from everyone who opted in. The collective is
> worth far more than any single member's data, and that combined value is
> exactly what you're able to offer because you're the one running it.

---

## 7 — How money flows

**On screen:**
- Buyers pay **per request** or in **prepaid bundles**
- Members collect to **their own wallet** — or your **shared collective wallet**
- Host sees the whole picture; each member sees their slice

**Say this:**
> Money is per use. A buyer either pays a tiny amount per request, or buys a
> bundle up front. Every member decides where their share lands. A member who
> has their own payment setup uses their own wallet. A member who doesn't want
> to deal with that can route their earnings straight to a shared collective
> wallet you provide. That's the thing that unblocks small members — they don't
> need their own payment rails to participate. You see the full revenue picture
> across the collective; each member sees their own slice.

---

## 8 — Why a collective beats going it alone

**On screen:**
- Aggregation is worth more than any one archive
- Shared infrastructure, shared cost
- You're already the trusted broker
- Twenty members negotiating together beat twenty alone

**Say this:**
> Why do this together instead of everyone for themselves? Four reasons. First,
> aggregation: buyers want everyone's content, not one archive, so the whole is
> worth more than the parts. Second, cost: one system, one gateway, one billing
> setup, run by the organization that already serves the members. Third, trust:
> you're already the neutral party your members rely on — holding the keys and
> splitting revenue fairly is a natural extension of that. And fourth, leverage:
> twenty members negotiating as one have real bargaining power. For an
> association, this is just what you already do — pool resources and represent
> members collectively — applied to data.

---

## 9 — Who runs one well

**On screen:**
- **News:** regional paper groups, newsroom networks, journalism consortia
- **Associations:** industry bodies, professional groups, sector coalitions
- The pattern: a trusted center + members who each hold a slice

**Say this:**
> Who is this for? On the news side: regional newspaper groups pooling archives,
> independent newsroom networks sharing investigative work, public-interest
> journalism consortia. On the association side: industry bodies with decades of
> reports, professional groups with member-contributed knowledge, sector
> coalitions where each member holds one piece of a valuable whole. The pattern
> is always the same — a trusted organization at the center, and members who
> individually can't build this, but together own something buyers want. If that
> describes you, you're exactly who this was built for.

---

## 10 — How it fits together (the one technical slide)

**On screen:**
- Host runs one system at a public URL they control
- Members join as isolated tenants on that system
- Member APIs compose into collective APIs
- Access, limits, and pricing enforced as policies; revenue routed per wallet

**Say this:**
> One slide on the plumbing, then we're done. You run a single system at a web
> address you control. Members join as isolated tenants — separate data, shared
> front door. Their APIs compose into the collective APIs buyers hit. Who's
> allowed in, how often they can query, and what they pay are all enforced
> automatically as policies, and revenue routes to the right wallet on every
> request. Members never run a server. Buyers never see the seams. You operate
> one system and manage everything else from the dashboard.
