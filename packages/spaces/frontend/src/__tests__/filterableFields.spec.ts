import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { FilterSchema } from '@/api/types'
import FilterableFieldsPicker from '@/components/FilterableFieldsPicker.vue'
import {
  allowlistChanged,
  allowlistFor,
  describeAllowlist,
  filterRows,
  filteringDisabled,
  summarizeAllowlist,
} from '@/lib/filterableFields'

const schema: FilterSchema = {
  fields: {
    title: { type: 'string', ops: ['eq', 'ne', 'in', 'nin'] },
    published: { type: 'datetime', ops: ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'] },
    tags: { type: 'string[]', ops: ['contains_any', 'contains_all'] },
  },
  logic: ['and', 'or'],
  max_depth: 5,
  max_conditions: 50,
  max_list_values: 100,
}

describe('filterRows', () => {
  it('ticks every declared field when the allowlist is null', () => {
    const rows = filterRows(schema, null)
    expect(rows.map((r) => [r.name, r.checked])).toEqual([
      ['title', true],
      ['published', true],
      ['tags', true],
    ])
  })

  it('ticks only the listed fields and appends stale names unticked', () => {
    const rows = filterRows(schema, ['published', 'gone'])
    expect(rows.map((r) => [r.name, r.checked, r.spec === null])).toEqual([
      ['title', false, false],
      ['published', true, false],
      ['tags', false, false],
      ['gone', false, true],
    ])
  })
})

describe('allowlistFor', () => {
  it('stores null once every declared field is ticked', () => {
    expect(allowlistFor(schema, ['title', 'published', 'tags'])).toBeNull()
    expect(allowlistFor(schema, ['tags', 'title', 'published', 'gone'])).toBeNull()
  })

  it('stores the explicit list for a partial tick, in declaration order', () => {
    expect(allowlistFor(schema, ['tags', 'title'])).toEqual(['title', 'tags'])
    expect(allowlistFor(schema, [])).toEqual([])
  })
})

describe('allowlist helpers', () => {
  it('describes the three states', () => {
    expect(describeAllowlist(null)).toBe('All declared fields')
    expect(describeAllowlist([])).toBe('Filtering disabled')
    expect(describeAllowlist(['a'])).toBe('1 field')
    expect(describeAllowlist(['a', 'b'])).toBe('2 fields')
  })

  it('summarises the selection against the schema', () => {
    expect(summarizeAllowlist(schema, null)).toBe('All 3 fields')
    expect(summarizeAllowlist(schema, [])).toBe('Off')
    expect(summarizeAllowlist(schema, ['title', 'gone'])).toBe('1 of 3 fields')
  })

  it('tells disabled from everything-else and compares by value', () => {
    expect(filteringDisabled([])).toBe(true)
    expect(filteringDisabled(null)).toBe(false)
    expect(filteringDisabled(['a'])).toBe(false)
    expect(allowlistChanged(null, null)).toBe(false)
    expect(allowlistChanged(['a'], ['a'])).toBe(false)
    expect(allowlistChanged(null, [])).toBe(true)
  })
})

describe('FilterableFieldsPicker', () => {
  it('renders a row per field with its type and strikes a stale name', () => {
    const wrapper = mount(FilterableFieldsPicker, {
      props: { schema, modelValue: ['published', 'gone'] },
    })
    const rows = wrapper.findAll('[data-field]')
    expect(rows.map((r) => r.attributes('data-field'))).toEqual([
      'title',
      'published',
      'tags',
      'gone',
    ])
    expect(rows[1]!.text()).toContain('datetime')
    expect(rows[3]!.find('label').classes()).toContain('line-through')
    expect(rows[3]!.text()).toContain('no longer declared')
  })

  it('emits null when the last unticked field is ticked and [] when filtering is turned off', async () => {
    const wrapper = mount(FilterableFieldsPicker, {
      props: { schema, modelValue: ['published', 'tags'] },
    })
    const last = () => {
      const emitted = wrapper.emitted('update:modelValue') ?? []
      return emitted[emitted.length - 1]
    }
    await wrapper.find('[data-field="title"] button[role="checkbox"]').trigger('click')
    expect(last()).toEqual([null])

    await wrapper.find('button[role="switch"]').trigger('click')
    expect(last()).toEqual([[]])
  })
})
