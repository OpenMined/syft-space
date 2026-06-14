---
marp: true
title: Syft Space Collectives
author: Syft Space
paginate: true
size: 16:9
theme: collective
style: |
  /* @theme collective */
  :root {
    --bg: #ffffff;
    --fg: #1a1a1a;
    --muted: #6b6b6b;
    --accent: #f59e0b;
    --accent-2: #fb923c;
    --line: #ececec;
    --card: #fafafa;
  }
  section {
    background: var(--bg);
    color: var(--fg);
    font-family: -apple-system, "Inter", "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 26px;
    line-height: 1.5;
    padding: 70px 90px;
    letter-spacing: -0.01em;
  }
  section::after {
    color: var(--muted);
    font-size: 14px;
  }
  h1 {
    font-size: 52px;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin: 0 0 28px 0;
  }
  h1 .grad {
    background: linear-gradient(90deg, var(--accent), var(--accent-2));
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  h2 {
    font-size: 22px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent);
    margin: 0 0 24px 0;
  }
  ul { margin-top: 8px; }
  li {
    margin: 0 0 16px 0;
    padding-left: 4px;
  }
  li::marker { color: var(--accent); }
  strong { color: var(--fg); font-weight: 700; }
  em { color: var(--muted); font-style: normal; }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 24px;
    margin-top: 12px;
  }
  th {
    text-align: left;
    color: var(--accent);
    text-transform: uppercase;
    font-size: 16px;
    letter-spacing: 0.06em;
    border-bottom: 2px solid var(--line);
    padding: 12px 16px;
  }
  td {
    border-bottom: 1px solid var(--line);
    padding: 16px;
    vertical-align: top;
  }
  td:first-child { font-weight: 700; white-space: nowrap; }
  .lead-num {
    color: var(--accent);
    font-weight: 700;
    font-size: 18px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 12px;
  }
  section.title {
    justify-content: center;
  }
  section.title h1 { font-size: 64px; }
  section.title p { font-size: 28px; color: var(--muted); max-width: 80%; }
  .pill {
    display: inline-block;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 6px 18px;
    font-size: 18px;
    color: var(--muted);
    margin-bottom: 28px;
  }
  .kpi { display: flex; gap: 28px; margin-top: 24px; }
  .kpi > div {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 24px 28px;
    flex: 1;
  }
  .kpi .n { font-size: 40px; font-weight: 700; }
  .kpi .l { font-size: 16px; color: var(--muted); }
---

<!-- _class: title -->

<span class="pill">Syft Space</span>

# Data collectives <span class="grad">for members who can't go it alone</span>

How a news network or trade association turns its members' data into one product — and pays them for it.

---

<!--
THE PROBLEM. Say this:
Every one of your members is sitting on something AI companies want to pay for.
A newsroom has twenty years of archives. A trade association has decades of
reports, standards, and member submissions. The demand is real and the money is
real. But no single small member can build the infrastructure, set up billing,
enforce who's allowed to use the data, and feel legally safe doing it. So the
data just sits there. The content exists — what's missing is shared
infrastructure and someone trusted to run it.
-->

<div class="lead-num">01 · The problem</div>

# Your members own valuable data. <span class="grad">They can't safely sell it alone.</span>

- AI companies will pay for archives, reports, and member knowledge
- No single small member can build the infra, billing, or access controls
- So the data just sits there

*The content already exists. What's missing is shared infrastructure — and someone trusted to run it.*

---

<!--
THE IDEA. Say this:
The idea is simple. One organization — you — runs a single system. Each member
connects their own data to it, and their data stays theirs. Together those
members add up to something a buyer can actually use: one place to query
everyone's content at once. Think of it like a co-op. You own the building and
the storefront. Each member keeps the keys to their own unit. The buyer walks
into one shop instead of negotiating with twenty separate sellers.
-->

<div class="lead-num">02 · The idea</div>

# A data <span class="grad">collective</span>

- **One organization** runs the infrastructure
- **Many members** plug in their own data — it stays theirs
- **Buyers** query all of it through one door

*Like a co-op: you own the storefront, each member keeps the keys to their unit, and the buyer walks into one shop — not twenty.*

---

<!--
TWO ROLES. Say this:
There are exactly two roles. The host — that's you, the association or the news
network — runs the infrastructure and oversees the whole collective. The members
are your tenants: each one gets a normal, private workspace that just happens to
live on your system. It's the same application either way. When you log in as
the host, you see across the entire collective. When a member logs in, they only
see their own space. No member ever sees another member's data.
-->

<div class="lead-num">03 · Roles</div>

# Two roles, one system

| Role | Who | What they do |
|------|-----|--------------|
| Host | The association or news network | Runs the infra, manages members, sees everything |
| Member | Each newsroom or member firm | Connects data, sets pricing, keeps their revenue |

*Same app, two modes. The host sees the whole collective; each member sees only their own private space.*

---

<!--
WHAT THE HOST SEES. Say this:
As the host, you get one dashboard for the whole collective. You see your
members — who's joined, who's active this month, who's actually earning. You see
the collective APIs, the shared endpoints buyers query, each with its own revenue
and traffic. And you see the money: total revenue, revenue this month, how many
members are active, how many are earning. In our demo that's three hundred
members, forty-seven active, ten earning. One toggle flips you between this
collective-wide view and your own private workspace.
-->

<div class="lead-num">04 · The host's view</div>

# One dashboard, the whole collective

- **Members** — who's in, who's active, who's earning
- **Collective APIs** — the shared endpoints buyers hit, with revenue each
- **Stats** — total revenue, this month, active and earning members

<div class="kpi">
  <div><div class="n">300</div><div class="l">members</div></div>
  <div><div class="n">47</div><div class="l">active this month</div></div>
  <div><div class="n">10</div><div class="l">earning</div></div>
</div>

---

<!--
WHAT A MEMBER SEES. Say this:
A member's experience is deliberately boring — in a good way. They sign in once
with a key; there's nothing to register, because you control who's a member.
Then they connect their data the way they already work. A newsroom points it at
their WordPress site and the posts sync in. They add an RSS feed and new articles
flow in as they publish. Or they just upload archives and PDFs. They set a price
per query, and they keep what they earn. Onboarding a member is "paste a URL and
a key" — not "migrate your whole archive."
-->

<div class="lead-num">05 · The member's view</div>

# A normal workspace, with the rails built in

- **Sign in once** — no registration; you manage membership
- **Connect data the way they already work:** WordPress · RSS · files & folders
- **Set a price per query** — and keep what they earn

*Onboarding a member is "paste a URL and a key" — not "migrate your whole archive."*

---

<!--
ONE PRODUCT. Say this:
Here's the part that makes it valuable. Each member's data becomes their own
small API. The system rolls those individual APIs up into collective APIs — for
example, "search every member's archive" or "retrieve documents across the whole
network." The buyer never talks to twenty members. They query one endpoint and
get answers drawn from everyone who opted in. The collective is worth far more
than any single member's data, and that combined value is exactly what you can
offer because you're the one running it.
-->

<div class="lead-num">06 · The value</div>

# Many archives become <span class="grad">one product</span>

- Each member's data becomes **their own API**
- Those APIs roll up into **collective APIs** — e.g. *search every member's archive*
- Buyers query **one endpoint**, drawn from everyone who opted in

*The collective is worth far more than any single archive. That combined value is what only you — the host — can offer.*

---

<!--
MONEY. Say this:
Money is per use. A buyer either pays a tiny amount per request, or buys a bundle
up front. Every member decides where their share lands. A member who has their
own payment setup uses their own wallet. A member who doesn't want to deal with
that can route their earnings straight to a shared collective wallet you provide.
That's the thing that unblocks small members — they don't need their own payment
rails to participate. You see the full revenue picture; each member sees their
own slice.
-->

<div class="lead-num">07 · The money</div>

# Members get paid per query

- Buyers pay **per request** or in **prepaid bundles**
- Members collect to **their own wallet** — or your **shared collective wallet**
- Host sees the whole picture; each member sees their slice

*The shared wallet is the unlock: small members don't need their own payment rails to participate.*

---

<!--
WHY TOGETHER. Say this:
Why do this together instead of everyone for themselves? Four reasons. First,
aggregation: buyers want everyone's content, not one archive, so the whole is
worth more than the parts. Second, cost: one system, one gateway, one billing
setup, run by the organization that already serves the members. Third, trust:
you're already the neutral party your members rely on — holding the keys and
splitting revenue fairly is a natural extension of that. Fourth, leverage: twenty
members negotiating as one have real bargaining power. For an association, this
is just what you already do — pool resources and represent members collectively —
applied to data.
-->

<div class="lead-num">08 · Why a collective</div>

# Better together than alone

- **Aggregation** — buyers want everyone's content; the whole beats the parts
- **Shared cost** — one system, run by the org that already serves members
- **Trust** — you're already the neutral broker holding the keys
- **Leverage** — twenty members negotiating as one

*For an association, this is what you already do — pool resources, represent members — applied to data.*

---

<!--
WHO. Say this:
Who is this for? On the news side: regional newspaper groups pooling archives,
independent newsroom networks sharing investigative work, public-interest
journalism consortia. On the association side: industry bodies with decades of
reports, professional groups with member-contributed knowledge, sector coalitions
where each member holds one piece of a valuable whole. The pattern is always the
same — a trusted organization at the center, and members who individually can't
build this, but together own something buyers want. If that describes you, you're
exactly who this was built for.
-->

<div class="lead-num">09 · Who runs one well</div>

# Built for trusted networks

- **News** — regional paper groups, newsroom networks, journalism consortia
- **Associations** — industry bodies, professional groups, sector coalitions

*The pattern: a trusted organization at the center, and members who individually can't build this — but together own something buyers want.*

---

<!--
PLUMBING. Say this:
One slide on the plumbing, then we're done. You run a single system at a web
address you control. Members join as isolated tenants — separate data, shared
front door. Their APIs compose into the collective APIs buyers hit. Who's allowed
in, how often they can query, and what they pay are all enforced automatically as
policies, and revenue routes to the right wallet on every request. Members never
run a server. Buyers never see the seams. You operate one system and manage
everything else from the dashboard.
-->

<div class="lead-num">10 · How it fits together</div>

# Under the hood

- Host runs **one system** at a public URL they control
- Members join as **isolated tenants** — separate data, shared front door
- Member APIs compose into **collective APIs**
- Access, limits, and pricing enforced as **policies**; revenue routed per wallet

*Members never run a server. Buyers never see the seams. You operate one system and manage the rest from the dashboard.*
