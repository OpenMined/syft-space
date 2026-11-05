import { describe, expect, it } from 'vitest'
import type { ConfigSchema } from '@/api/types'
import { SOURCE_PRESENTATION } from '@/config/sources'
import {
  configurationPatch,
  displayedConfiguration,
  draftErrors,
  draftFromStored,
  editableFields,
  fieldsByAxis,
  isPublicProperty,
  type FieldDraft,
} from '@/lib/datasetConfig'

const copy = (dtype: string) => SOURCE_PRESENTATION[dtype]?.fields ?? {}

// Mirrors what GET /datasets/types/{name} returns for the built-in bindings.
const wordpress: ConfigSchema = {
  required: ['siteUrl', 'username', 'applicationPassword', 'collectionName'],
  properties: {
    siteUrl: { type: 'string', axis: 'source', editable: true },
    username: { type: 'string', axis: 'source', editable: true },
    applicationPassword: {
      type: 'string',
      format: 'password',
      axis: 'source',
      editable: true,
      visibility: 'secret',
    },
    userAgent: { type: 'string', axis: 'source', default: 'Mozilla/5.0' },
    pollIntervalSeconds: { type: 'integer', axis: 'source', editable: true, default: 300 },
    collectionName: { type: 'string', axis: 'vector_store' },
    httpPort: { type: 'integer', axis: 'vector_store', visibility: 'internal' },
  },
}

const weaviate: ConfigSchema = {
  required: ['http_url', 'grpc_url', 'api_key', 'collection_name'],
  properties: {
    http_url: { type: 'string', format: 'uri', axis: 'vector_store', editable: true },
    api_key: { type: 'string', axis: 'vector_store', editable: true, visibility: 'secret' },
    collection_name: { type: 'string', axis: 'vector_store' },
    headers: {
      anyOf: [{ type: 'object' }, { type: 'null' }],
      axis: 'vector_store',
      editable: true,
      visibility: 'secret',
    },
    metadata_properties: {
      anyOf: [{ type: 'array', items: { type: 'string' } }, { type: 'null' }],
      axis: 'vector_store',
      editable: true,
    },
    filters: { anyOf: [{ type: 'object' }, { type: 'null' }], axis: 'vector_store' },
  },
}

const rss: ConfigSchema = {
  required: ['feedUrls', 'collectionName'],
  properties: {
    feedUrls: { type: 'string', axis: 'source', editable: true },
    pollIntervalSeconds: {
      type: 'integer',
      axis: 'source',
      editable: true,
      enum: [900, 3600],
      default: 3600,
    },
    collectionName: { type: 'string', axis: 'vector_store' },
  },
}

describe('editableFields', () => {
  it('keeps only editable, non-internal properties in schema order', () => {
    expect(editableFields(wordpress, copy('wordpress')).map((f) => f.name)).toEqual([
      'siteUrl',
      'username',
      'applicationPassword',
      'pollIntervalSeconds',
    ])
  })

  it('classifies each field by its schema flags', () => {
    const kinds = Object.fromEntries(
      editableFields(weaviate, copy('remote_weaviate')).map((f) => [f.name, f.kind]),
    )
    expect(kinds).toEqual({
      http_url: 'text',
      api_key: 'secret',
      headers: 'secretMap',
      metadata_properties: 'list',
    })
    const wp = Object.fromEntries(
      editableFields(wordpress, copy('wordpress')).map((f) => [f.name, f.kind]),
    )
    expect(wp.applicationPassword).toBe('secret')
    expect(wp.pollIntervalSeconds).toBe('number')
  })

  it('uses the source copy for labels, list separators and select labels', () => {
    const fields = editableFields(rss, copy('rss'))
    const feeds = fields.find((f) => f.name === 'feedUrls')!
    expect(feeds).toMatchObject({
      kind: 'list',
      separator: ',',
      label: 'Feed URLs',
      required: true,
    })
    const poll = fields.find((f) => f.name === 'pollIntervalSeconds')!
    expect(poll.kind).toBe('select')
    expect(poll.options).toEqual([
      { value: '900', label: 'Every 15 minutes' },
      { value: '3600', label: 'Every hour' },
    ])
  })

  it('groups by axis and drops empty axes', () => {
    const groups = fieldsByAxis(editableFields(weaviate, copy('remote_weaviate')))
    expect(groups.map((g) => g.label)).toEqual(['Vector store'])
    const wp = fieldsByAxis(editableFields(wordpress, copy('wordpress')))
    expect(wp.map((g) => g.axis)).toEqual(['source'])
  })
})

describe('isPublicProperty', () => {
  it('hides secret and internal values, shows everything else', () => {
    expect(isPublicProperty(wordpress, 'siteUrl')).toBe(true)
    expect(isPublicProperty(wordpress, 'applicationPassword')).toBe(false)
    expect(isPublicProperty(wordpress, 'httpPort')).toBe(false)
    expect(isPublicProperty(wordpress, 'unknownKey')).toBe(true)
    expect(isPublicProperty(null, 'anything')).toBe(true)
  })
})

describe('displayedConfiguration', () => {
  it('keeps every public value that is set, whatever its shape', () => {
    // A stored FilterCondition has five keys once defaults are serialized.
    const filters = {
      type: 'condition',
      property: 'status',
      op: 'eq',
      value_dtype: 'string',
      value: 'published',
    }
    const shown = displayedConfiguration(weaviate, {
      http_url: 'http://w:8080',
      api_key: 'secret',
      headers: { 'X-OpenAI-Api-Key': null },
      metadata_properties: ['title', 'author'],
      filters,
      content_property: null,
    })
    expect(Object.keys(shown)).toEqual(['http_url', 'metadata_properties', 'filters'])
    expect(shown.filters).toBe(filters)
  })

  it('shows every set value when the schema is unknown', () => {
    expect(displayedConfiguration(null, { a: 1, b: undefined, c: { d: [1, 2] } })).toEqual({
      a: 1,
      c: { d: [1, 2] },
    })
  })
})

describe('draftFromStored', () => {
  const fields = editableFields(weaviate, copy('remote_weaviate'))
  const byName = Object.fromEntries(fields.map((f) => [f.name, f]))

  it('starts a secret empty and a secret map with its stored keys kept', () => {
    expect(draftFromStored(byName.api_key!, undefined)).toEqual({ kind: 'secret', replacement: '' })
    expect(draftFromStored(byName.headers!, { 'X-Org': null })).toEqual({
      kind: 'secretMap',
      entries: [{ key: 'X-Org', value: null, stored: true }],
    })
  })

  it('splits joined lists and keeps arrays as rows', () => {
    const feeds = editableFields(rss, copy('rss'))[0]!
    expect(draftFromStored(feeds, 'https://a/feed,https://b/feed')).toEqual({
      kind: 'rows',
      rows: ['https://a/feed', 'https://b/feed'],
    })
    // Spacing around the separator in a stored string is not content.
    expect(draftFromStored(feeds, 'https://a/feed, https://b/feed ,')).toEqual({
      kind: 'rows',
      rows: ['https://a/feed', 'https://b/feed'],
    })
    expect(draftFromStored(byName.metadata_properties!, ['title', 'url'])).toEqual({
      kind: 'rows',
      rows: ['title', 'url'],
    })
    expect(draftFromStored(byName.metadata_properties!, null)).toEqual({ kind: 'rows', rows: [] })
  })
})

describe('configurationPatch', () => {
  const wpFields = editableFields(wordpress, copy('wordpress'))
  const stored = { siteUrl: 'https://old.example', username: 'bob', pollIntervalSeconds: 300 }
  const drafts = (): Record<string, FieldDraft> =>
    Object.fromEntries(
      wpFields.map((f) => [f.name, draftFromStored(f, stored[f.name as keyof typeof stored])]),
    )

  it('sends nothing when nothing changed', () => {
    expect(configurationPatch(wpFields, stored, drafts())).toEqual({})
  })

  it('sends only changed keys, numbers as numbers, secrets only when replaced', () => {
    const d = drafts()
    d.siteUrl = { kind: 'value', value: ' https://new.example ' }
    d.pollIntervalSeconds = { kind: 'value', value: '900' }
    d.applicationPassword = { kind: 'secret', replacement: 'new-pass' }
    expect(configurationPatch(wpFields, stored, d)).toEqual({
      siteUrl: 'https://new.example',
      pollIntervalSeconds: 900,
      applicationPassword: 'new-pass',
    })
  })

  it('removes an optional value with null and never nulls a required one', () => {
    const wvFields = editableFields(weaviate, copy('remote_weaviate'))
    const wvStored = { http_url: 'https://w', metadata_properties: ['a'] }
    const d: Record<string, FieldDraft> = {
      http_url: { kind: 'value', value: '' },
      metadata_properties: { kind: 'rows', rows: [] },
    }
    expect(configurationPatch(wvFields, wvStored, d)).toEqual({ metadata_properties: null })
    expect(draftErrors(wvFields, d)).toEqual({ http_url: 'HTTP URL is required' })
  })

  it('sends a numeric enum choice as a number', () => {
    const rssFields = editableFields(rss, copy('rss'))
    const d: Record<string, FieldDraft> = {
      pollIntervalSeconds: { kind: 'value', value: '900' },
    }
    expect(configurationPatch(rssFields, { pollIntervalSeconds: 3600 }, d)).toEqual({
      pollIntervalSeconds: 900,
    })
  })

  it('does not treat an untouched list as changed because of spacing in the stored string', () => {
    const rssFields = editableFields(rss, copy('rss'))
    const stored = { feedUrls: 'https://a/feed, https://b/feed' }
    const untouched: Record<string, FieldDraft> = {
      feedUrls: draftFromStored(rssFields[0]!, stored.feedUrls),
    }
    expect(configurationPatch(rssFields, stored, untouched)).toEqual({})

    const reordered: Record<string, FieldDraft> = {
      feedUrls: { kind: 'rows', rows: ['https://b/feed', 'https://a/feed'] },
    }
    expect(configurationPatch(rssFields, stored, reordered)).toEqual({
      feedUrls: 'https://b/feed,https://a/feed',
    })
  })

  it('joins list rows with the copy separator and dedupes blanks', () => {
    const rssFields = editableFields(rss, copy('rss'))
    const d: Record<string, FieldDraft> = {
      feedUrls: { kind: 'rows', rows: ['https://a/feed', ' ', 'https://b/feed', 'https://a/feed'] },
    }
    expect(configurationPatch(rssFields, { feedUrls: 'https://a/feed' }, d)).toEqual({
      feedUrls: 'https://a/feed,https://b/feed',
    })
  })

  it('sends a secret map with null for kept keys, strings for replaced, absent for removed', () => {
    const wvFields = editableFields(weaviate, copy('remote_weaviate'))
    const headers = wvFields.find((f) => f.name === 'headers')!
    const wvStored = { headers: { 'X-Keep': null, 'X-Rotate': null, 'X-Drop': null } }
    const d: Record<string, FieldDraft> = {
      headers: {
        kind: 'secretMap',
        entries: [
          { key: 'X-Keep', value: null, stored: true },
          { key: 'X-Rotate', value: 'fresh', stored: true },
          { key: 'X-New', value: 'v', stored: false },
        ],
      },
    }
    expect(configurationPatch([headers], wvStored, d)).toEqual({
      headers: { 'X-Keep': null, 'X-Rotate': 'fresh', 'X-New': 'v' },
    })
    const untouched: Record<string, FieldDraft> = {
      headers: draftFromStored(headers, wvStored.headers),
    }
    expect(configurationPatch([headers], wvStored, untouched)).toEqual({})
    const cleared: Record<string, FieldDraft> = { headers: { kind: 'secretMap', entries: [] } }
    expect(configurationPatch([headers], wvStored, cleared)).toEqual({ headers: null })
  })

  it('flags unnamed, duplicate and valueless new headers', () => {
    const headers = editableFields(weaviate, copy('remote_weaviate')).find(
      (f) => f.name === 'headers',
    )!
    const check = (entries: FieldDraft & { kind: 'secretMap' }) =>
      draftErrors([headers], { headers: entries }).headers
    expect(check({ kind: 'secretMap', entries: [{ key: '', value: 'v', stored: false }] })).toMatch(
      /name/,
    )
    expect(
      check({
        kind: 'secretMap',
        entries: [
          { key: 'A', value: null, stored: true },
          { key: 'A', value: 'v', stored: false },
        ],
      }),
    ).toMatch(/unique/)
    expect(check({ kind: 'secretMap', entries: [{ key: 'A', value: '', stored: false }] })).toMatch(
      /value/,
    )
  })
})

describe('bounded numbers', () => {
  // Mirrors the remote Weaviate schema's hybrid fields.
  const weaviateSearch: ConfigSchema = {
    properties: {
      search_mode: {
        type: 'string',
        enum: ['vector', 'hybrid'],
        default: 'vector',
        axis: 'vector_store',
        editable: true,
      },
      alpha: {
        type: 'number',
        minimum: 0,
        maximum: 1,
        default: 0.7,
        axis: 'vector_store',
        editable: true,
      },
    },
  }
  const fields = editableFields(weaviateSearch, copy('remote_weaviate'))

  it('renders a string enum as a select and a bounded number as a number field', () => {
    const mode = fields.find((f) => f.name === 'search_mode')
    const alpha = fields.find((f) => f.name === 'alpha')
    expect(mode?.kind).toBe('select')
    expect(mode?.numeric).toBe(false)
    expect(mode?.options.map((o) => o.value)).toEqual(['vector', 'hybrid'])
    expect(alpha?.kind).toBe('number')
    expect([alpha?.min, alpha?.max]).toEqual([0, 1])
  })

  it('refuses a number outside the schema bounds', () => {
    const errorsFor = (value: string) => draftErrors(fields, { alpha: { kind: 'value', value } })
    expect(errorsFor('0.4')).toEqual({})
    expect(errorsFor('1.5').alpha).toBe('Vector weight (alpha) must be at most 1')
    expect(errorsFor('-0.1').alpha).toBe('Vector weight (alpha) must be at least 0')
  })
})
