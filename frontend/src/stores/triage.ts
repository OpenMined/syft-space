import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Platform } from './mockApis'
import { effectiveMode, getPersonById } from './mockRelationships'

export interface TriageItem {
  id: string
  personId: string
  platform: Platform
  incomingMessage: string
  draftReply: string
  rationale: string
  suggestedAction: string
  timestamp: Date
  status: 'pending' | 'sent' | 'dismissed'
}

export const useTriageStore = defineStore('triage', () => {
  const items = ref<TriageItem[]>([
    {
      id: 't1',
      personId: 'ada-lovelace',
      platform: 'slack',
      incomingMessage: 'Can you send over the latest deploy notes?',
      draftReply:
        'Hi Ada — deploy notes for v2.3 are attached. Summary: migrations ran clean, latency down 12%. Let me know if you need the full changelog.',
      rationale: 'Ada prefers terse, technical answers; pulled deploy summary from recent context.',
      suggestedAction: 'Send notes',
      timestamp: new Date('2026-06-14T09:13:00'),
      status: 'pending',
    },
    {
      id: 't2',
      personId: 'alan-turing',
      platform: 'whatsapp',
      incomingMessage: 'Lunch this weekend?',
      draftReply: 'Would love to! Saturday 1pm at the usual spot? 🙂',
      rationale: 'Casual friend; matched friendly tone and proposed a concrete time.',
      suggestedAction: 'Propose time',
      timestamp: new Date('2026-06-14T08:02:00'),
      status: 'pending',
    },
    {
      id: 't3',
      personId: 'edsger-dijkstra',
      platform: 'syfthub',
      incomingMessage: 'Which animals in the dataset are listed as endangered?',
      draftReply:
        '12 species in the dataset carry an IUCN "Endangered" status, including the African wild dog and the riverine rabbit. Full list with citations attached.',
      rationale: 'Reviewer expects rigor; answer cites the dataset and offers the full list.',
      suggestedAction: 'Answer with data',
      timestamp: new Date('2026-06-11T11:06:00'),
      status: 'pending',
    },
    {
      id: 't4',
      personId: 'barbara-liskov',
      platform: 'slack',
      incomingMessage: 'Got a minute to look at the API contract?',
      draftReply:
        'Sure — sending feedback now. One note: the response schema should stay substitutable across versions so existing clients keep working.',
      rationale: 'Principal engineer; kept it substitutable per her preference.',
      suggestedAction: 'Share feedback',
      timestamp: new Date('2026-06-09T13:01:00'),
      status: 'pending',
    },
  ])

  // Only manual-mode people ever surface in triage, so flipping a person to auto
  // reactively removes them from the queue.
  const pendingTriage = computed(() =>
    items.value.filter((item) => {
      if (item.status !== 'pending') return false
      const person = getPersonById(item.personId)
      return person ? effectiveMode(person) === 'manual' : false
    }),
  )

  const editDraft = (id: string, text: string): void => {
    const item = items.value.find((i) => i.id === id)
    if (item) item.draftReply = text
  }

  const dismissTriage = (id: string): void => {
    const item = items.value.find((i) => i.id === id)
    if (item) item.status = 'dismissed'
  }

  const sendTriage = (id: string): void => {
    const item = items.value.find((i) => i.id === id)
    if (!item) return
    const person = getPersonById(item.personId)
    if (person) {
      person.conversation.push({
        id: `m${person.conversation.length + 1}`,
        direction: 'out',
        text: item.draftReply,
        timestamp: new Date(),
        wasDraft: true,
      })
      person.lastMessageAt = new Date()
    }
    item.status = 'sent'
  }

  return { items, pendingTriage, editDraft, dismissTriage, sendTriage }
})
