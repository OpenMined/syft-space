import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UtcStampHint from '@/components/UtcStampHint.vue'
import {
  describeUtcStamp,
  findUtcStampInPath,
  parseUtcStamp,
  utcStampHint,
  utcStampHintForPath,
} from '@/lib/utcStamp'

const LA = { locale: 'en-US', timeZone: 'America/Los_Angeles' }

// ICU may put a narrow no-break space before AM/PM; compare on plain spaces.
const plain = (s: string | undefined) => s?.replace(/[  ]/g, ' ')

describe('parseUtcStamp', () => {
  it('parses a stamped folder name as a UTC moment', () => {
    expect(parseUtcStamp('2026-10-07_1900_UTC')?.toISOString()).toBe('2026-10-07T19:00:00.000Z')
  })

  it('accepts a collision suffix', () => {
    expect(parseUtcStamp('2026-10-07_1900_UTC_2')?.toISOString()).toBe('2026-10-07T19:00:00.000Z')
    expect(parseUtcStamp('2026-10-07_0005_UTC_13')?.toISOString()).toBe('2026-10-07T00:05:00.000Z')
  })

  it('rejects names that do not match the pattern exactly', () => {
    for (const name of [
      'news',
      '2026-10-07',
      '2026-10-07_1900',
      '2026-10-07_1900_utc',
      '2026-10-07_1900_UTC_',
      '2026-10-07_1900_UTC_0',
      '2026-10-07_1900_UTC.md',
      'x2026-10-07_1900_UTC',
      '2026-10-07_19:00_UTC',
    ]) {
      expect(parseUtcStamp(name), name).toBeNull()
    }
  })

  it('rejects impossible dates and times', () => {
    expect(parseUtcStamp('2026-13-40_2599_UTC')).toBeNull()
    expect(parseUtcStamp('2026-02-30_1200_UTC')).toBeNull()
    expect(parseUtcStamp('2026-10-07_2400_UTC')).toBeNull()
    expect(parseUtcStamp('2026-10-07_1960_UTC')).toBeNull()
  })
})

describe('findUtcStampInPath', () => {
  it('finds the deepest stamped segment', () => {
    expect(findUtcStampInPath('/data/news/2026-10-07_1900_UTC')?.toISOString()).toBe(
      '2026-10-07T19:00:00.000Z',
    )
    expect(
      findUtcStampInPath('/data/2026-10-06_0800_UTC/2026-10-07_1900_UTC_2/a.md')?.toISOString(),
    ).toBe('2026-10-07T19:00:00.000Z')
  })

  it('returns null for paths without a stamp', () => {
    expect(findUtcStampInPath('/data/news/article.md')).toBeNull()
    expect(findUtcStampInPath('post:123')).toBeNull()
  })
})

describe('describeUtcStamp', () => {
  it('formats the moment in the given time zone with a UTC explanation', () => {
    const hint = describeUtcStamp(new Date('2026-10-07T19:00:00Z'), LA)
    expect(plain(hint.label)).toBe('Oct 7, 12:00 PM PDT')
    expect(plain(hint.title)).toBe(
      'Collected at Oct 7, 2026, 12:00 PM PDT in your time zone (Oct 7, 2026, 7:00 PM UTC)',
    )
  })

  it('crosses the date line when the zone does', () => {
    const hint = describeUtcStamp(new Date('2026-10-07T19:00:00Z'), {
      locale: 'en-US',
      timeZone: 'Asia/Tokyo',
    })
    expect(plain(hint.label)).toBe('Oct 8, 4:00 AM GMT+9')
  })

  it('wraps parsing for names and paths', () => {
    expect(plain(utcStampHint('2026-10-07_1900_UTC_2', LA)?.label)).toBe('Oct 7, 12:00 PM PDT')
    expect(utcStampHint('reports', LA)).toBeNull()
    expect(plain(utcStampHintForPath('/news/2026-10-07_1900_UTC', LA)?.label)).toBe(
      'Oct 7, 12:00 PM PDT',
    )
    expect(utcStampHintForPath('/news/reports', LA)).toBeNull()
  })
})

describe('UtcStampHint', () => {
  it('renders the local time for a stamped path', () => {
    const wrapper = mount(UtcStampHint, {
      props: { path: '/news/2026-10-07_1900_UTC', ...LA },
    })
    expect(plain(wrapper.get('[data-testid="utc-stamp-hint"]').text())).toBe('Oct 7, 12:00 PM PDT')
  })

  it('renders nothing for other paths', () => {
    const wrapper = mount(UtcStampHint, { props: { path: '/news/reports', ...LA } })
    expect(wrapper.find('[data-testid="utc-stamp-hint"]').exists()).toBe(false)
  })
})
