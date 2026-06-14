/**
 * Mock relationships store.
 *
 * A Person is a counterparty on the far side of an API — someone you talk to on a
 * platform. Each person resolves to an API (their override, else the platform
 * default) and an effective auto/manual mode driven by that API's HIL policy,
 * unless the person pins a mode explicitly.
 */
import { reactive } from 'vue'
import {
  getApiById,
  getPlatformDefaultApiId,
  type ApiResource,
  type Platform,
} from './mockApis'

export type ReplyMode = 'auto' | 'manual'

export interface ConversationMessage {
  id: string
  direction: 'in' | 'out'
  text: string
  timestamp: Date
  wasDraft?: boolean
}

export interface PersonReplyConfig {
  apiOverrideId: string | null
  customPrompt: string | null
  modeOverride: ReplyMode | null
}

export interface Person {
  id: string
  name: string
  handle: string
  platform: Platform
  avatarInitials: string
  metadata: string
  conversation: ConversationMessage[]
  reply: PersonReplyConfig
  lastMessageAt: Date
}

const noOverride = (): PersonReplyConfig => ({
  apiOverrideId: null,
  customPrompt: null,
  modeOverride: null,
})

export const people = reactive<Person[]>([
  {
    id: 'ada-lovelace',
    name: 'Ada Lovelace',
    handle: '@ada',
    platform: 'slack',
    avatarInitials: 'AL',
    metadata: 'Engineering lead. Prefers terse, technical answers. Timezone: GMT.',
    reply: noOverride(),
    lastMessageAt: new Date('2026-06-14T09:12:00'),
    conversation: [
      {
        id: 'm1',
        direction: 'in',
        text: 'Can you send over the latest deploy notes?',
        timestamp: new Date('2026-06-14T09:12:00'),
      },
    ],
  },
  {
    id: 'grace-hopper',
    name: 'Grace Hopper',
    handle: '@grace',
    platform: 'slack',
    avatarInitials: 'GH',
    metadata: 'Mentor. Likes a friendly tone. Often asks for status updates.',
    reply: { apiOverrideId: null, customPrompt: null, modeOverride: 'auto' },
    lastMessageAt: new Date('2026-06-13T17:40:00'),
    conversation: [
      {
        id: 'm1',
        direction: 'in',
        text: 'How did the demo go?',
        timestamp: new Date('2026-06-13T17:40:00'),
      },
      {
        id: 'm2',
        direction: 'out',
        text: 'It went really well — they approved the next phase!',
        timestamp: new Date('2026-06-13T17:42:00'),
        wasDraft: true,
      },
    ],
  },
  {
    id: 'alan-turing',
    name: 'Alan Turing',
    handle: '+44 7700 900123',
    platform: 'whatsapp',
    avatarInitials: 'AT',
    metadata: 'Old friend. Casual tone, emoji welcome.',
    reply: noOverride(),
    lastMessageAt: new Date('2026-06-14T08:01:00'),
    conversation: [
      {
        id: 'm1',
        direction: 'in',
        text: 'Lunch this weekend?',
        timestamp: new Date('2026-06-14T08:01:00'),
      },
    ],
  },
  {
    id: 'katherine-johnson',
    name: 'Katherine Johnson',
    handle: '+1 202 555 0142',
    platform: 'whatsapp',
    avatarInitials: 'KJ',
    metadata: 'Collaborator on the orbital dataset. Precise, detail-oriented.',
    reply: { apiOverrideId: 'research-api', customPrompt: null, modeOverride: null },
    lastMessageAt: new Date('2026-06-12T14:20:00'),
    conversation: [
      {
        id: 'm1',
        direction: 'in',
        text: 'Do you have a citation for the re-entry figures?',
        timestamp: new Date('2026-06-12T14:20:00'),
      },
    ],
  },
  {
    id: 'edsger-dijkstra',
    name: 'Edsger Dijkstra',
    handle: '@edsger',
    platform: 'syfthub',
    avatarInitials: 'ED',
    metadata: 'Reviewer. Expects rigor. No fluff.',
    reply: noOverride(),
    lastMessageAt: new Date('2026-06-11T11:05:00'),
    conversation: [
      {
        id: 'm1',
        direction: 'in',
        text: 'Which animals in the dataset are listed as endangered?',
        timestamp: new Date('2026-06-11T11:05:00'),
      },
    ],
  },
  {
    id: 'margaret-hamilton',
    name: 'Margaret Hamilton',
    handle: '@margaret',
    platform: 'syfthub',
    avatarInitials: 'MH',
    metadata: 'Systems engineer. Likes structured, numbered answers.',
    reply: noOverride(),
    lastMessageAt: new Date('2026-06-10T16:30:00'),
    conversation: [
      {
        id: 'm1',
        direction: 'in',
        text: 'Can your assistant summarize the conservation status report?',
        timestamp: new Date('2026-06-10T16:30:00'),
      },
    ],
  },
  {
    id: 'barbara-liskov',
    name: 'Barbara Liskov',
    handle: '@barbara',
    platform: 'slack',
    avatarInitials: 'BL',
    metadata: 'Principal. Substitutable answers only. 😉',
    reply: noOverride(),
    lastMessageAt: new Date('2026-06-09T13:00:00'),
    conversation: [
      {
        id: 'm1',
        direction: 'in',
        text: 'Got a minute to look at the API contract?',
        timestamp: new Date('2026-06-09T13:00:00'),
      },
    ],
  },
  {
    id: 'john-mccarthy',
    name: 'John McCarthy',
    handle: '+1 650 555 0199',
    platform: 'whatsapp',
    avatarInitials: 'JM',
    metadata: 'Acquaintance. Keep it brief.',
    reply: { apiOverrideId: null, customPrompt: null, modeOverride: 'auto' },
    lastMessageAt: new Date('2026-06-08T19:45:00'),
    conversation: [
      {
        id: 'm1',
        direction: 'in',
        text: 'Are we still on for Tuesday?',
        timestamp: new Date('2026-06-08T19:45:00'),
      },
    ],
  },
])

export const getPersonById = (personId: string): Person | undefined =>
  people.find((person) => person.id === personId)

export const getPeopleByPlatform = (platform: Platform): Person[] =>
  people.filter((person) => person.platform === platform)

/** The API that will answer for this person: their override, else the platform default. */
export const resolveApiForPerson = (person: Person): ApiResource | undefined => {
  const apiId = person.reply.apiOverrideId ?? getPlatformDefaultApiId(person.platform)
  return getApiById(apiId)
}

/** Explicit pin wins; otherwise the resolved API's HIL policy decides. */
export const effectiveMode = (person: Person): ReplyMode => {
  if (person.reply.modeOverride) return person.reply.modeOverride
  return resolveApiForPerson(person)?.hasHilPolicy ? 'manual' : 'auto'
}
