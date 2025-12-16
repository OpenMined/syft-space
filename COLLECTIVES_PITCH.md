# Data Collectives - Partner Feedback Deck

**5-minute pitch**

---

## Slide 1: The Problem

**Small data owners are invisible in AI**

- Can't afford infrastructure (vector DBs, hosting, APIs)
- No discoverability - lost in the noise
- Can't negotiate fair terms with AI companies
- Lack technical capacity to participate

**Result:** Only big tech wins in the AI economy.

---

## Slide 2: The Solution - Collectives

**Organize small data owners into powerful groups**

What collectives provide:
- 🏢 **Shared infrastructure** - No need to run your own servers
- 🔍 **Unified discovery** - One endpoint routes to all members
- 💪 **Collective bargaining** - Better terms, better prices
- ✅ **Trust & legitimacy** - Collective reputation rubs off on members

**Think**: Faculty union, but for data owners.

---

## Slide 3: How It Works

**Member Flow:**
1. Join a collective (e.g., "Harvard Research")
2. Create dataset/model in SyftAI Space
3. Choose: "Host on Harvard infrastructure" ✅
4. Publish endpoint → Auto-attached to collective

**Result:** Your endpoint is now:
- Hosted at `you.harvard.syftbox.net`
- Discoverable through `harvard.syftbox.net/query`
- Using collective's pricing/access terms (optional)

**No servers, no DevOps, no BS.**

---

## Slide 4: Collective Admin View

**What collective admins manage:**

1. **Members** - Approve/reject, assign pricing tiers
2. **Hosting** - See subdomain usage (`alice.harvard.syftbox.net`)
3. **Terms** - Define pricing tiers members can use
4. **Analytics** - See queries, revenue, member contributions

**Member retains control:**
- Choose collective pricing OR own pricing
- Choose collective access OR own access
- Leave anytime

---

## Slide 5: The Money Part

**Revenue flows directly to endpoints** (no pooling)

Example query to `harvard.syftbox.net/query`:
- Broadcasts to 3 member endpoints
- Alice's endpoint: $0.001/token (collective tier)
- Bob's endpoint: $0.002/token (own pricing)
- Carol's endpoint: $0.001/token (collective tier)

**Total cost:** Sum of all three = $0.004/token

**Each member gets paid** for their endpoint's contribution.

Collective just routes - doesn't take a cut (yet).

---

## Slide 6: What We Built

**Two apps running now:**

1. **SyftAI Space** (existing) - Members manage data/models/endpoints
   - Added: "Host on collective" option
   - Added: Collective terms in policies

2. **Collectives UI** (NEW) - Admins manage collectives
   - Create collectives with capabilities
   - Manage members and requests
   - Configure pricing tiers
   - View analytics

---


