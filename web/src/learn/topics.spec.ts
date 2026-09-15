import { describe, expect, it } from 'vitest'
import { FUNCTION_DEMOS, PATTERNS, TOPICS, topicBySlug } from './topics'

describe('Learn topics', () => {
  it('covers the nine subjects the spec lists', () => {
    expect(TOPICS).toHaveLength(9)
    expect(TOPICS.map((t) => t.slug)).toEqual([
      'three-parts', 'files-and-modes', 'changing-mode', 'lights', 'soft-and-hard',
      'functions', 'patterns', 'settings', 'safety',
    ])
  })

  it('has a unique slug and a blurb for each', () => {
    const slugs = TOPICS.map((t) => t.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
    for (const t of TOPICS) {
      expect(t.title.length).toBeGreaterThan(5)
      expect(t.blurb.length).toBeGreaterThan(10)
    }
  })

  it('looks a topic up by slug, and says no to an unknown one', () => {
    expect(topicBySlug('lights')?.title).toContain('lights')
    expect(topicBySlug('nope')).toBeNull()
  })

  it('describes the lights the way the firmware drives them: LED 5 changes colour past five', () => {
    const blurb = topicBySlug('lights')!.blurb
    expect(blurb).toMatch(/purple/)
    expect(blurb).toMatch(/blue/)
    expect(blurb).toMatch(/red/)
    // the old rule was "past five, LED 5 plus one more" — true only up to 9
    expect(blurb).not.toMatch(/LED 5 plus one more/)
  })
})

describe('function demos', () => {
  it('has the same number of ticks on both tracks', () => {
    for (const d of FUNCTION_DEMOS) {
      expect(d.output).toHaveLength(d.input.length)
      expect(d.input.length).toBeGreaterThan(4)
    }
  })

  it('only shows functions the firmware actually has', () => {
    // these are the names in core/qsprofile/catalog.FUNCTIONS
    const real = new Set([
      'normal', 'toggle', 'repeat', 'pulse', 'duty', 'greater_than', 'less_than',
      'force_off', 'delayed_latch', 'delay_off', 'delay_on', 'tap',
      'increment_value', 'decrement_value',
    ])
    for (const d of FUNCTION_DEMOS) expect(real.has(d.name)).toBe(true)
  })

  it('explains each one without leaning on the keyword', () => {
    // "tap" is ordinary English, so it is allowed in its own description; the
    // underscored names are jargon and must not appear in the plain wording.
    for (const d of FUNCTION_DEMOS) {
      expect(d.plain.length).toBeGreaterThan(15)
      if (d.name.includes('_')) {
        expect(d.plain.toLowerCase()).not.toContain(d.name)
        expect(d.plain).not.toContain('_')
      }
    }
  })

  it('shows behaviour that actually differs between functions', () => {
    const shapes = FUNCTION_DEMOS.map((d) => `${d.input.join()}|${d.output.join()}`)
    expect(new Set(shapes).size).toBe(shapes.length)
  })

  it('gets the headline behaviours right', () => {
    const by = (n: string) => FUNCTION_DEMOS.find((d) => d.name === n)!

    // normal: output mirrors input exactly
    expect(by('normal').output).toEqual(by('normal').input)

    // toggle: the output stays on after the input stops
    const tog = by('toggle')
    const firstPress = tog.input.indexOf(true)
    expect(tog.output[firstPress + 1]).toBe(true)
    expect(tog.input[firstPress + 1]).toBe(false)

    // repeat: more than one separate press from one hold
    const rep = by('repeat')
    const presses = rep.output.filter((on, i) => on && !rep.output[i - 1]).length
    expect(presses).toBeGreaterThan(1)

    // pulse: exactly one press however long the hold
    const pul = by('pulse')
    expect(pul.output.filter(Boolean)).toHaveLength(1)
    expect(pul.input.filter(Boolean).length).toBeGreaterThan(1)

    // delay_on: the output starts after the input does
    const don = by('delay_on')
    expect(don.output.indexOf(true)).toBeGreaterThan(don.input.indexOf(true))

    // delay_off: the output ends after the input does
    const doff = by('delay_off')
    expect(doff.output.lastIndexOf(true)).toBeGreaterThan(doff.input.lastIndexOf(true))
  })
})

describe('worked patterns', () => {
  it('names the file and mode each one came from', () => {
    for (const p of PATTERNS) {
      expect(p.source).toMatch(/\.csv/)
      expect(p.what.length).toBeGreaterThan(30)
    }
  })

  it('uses real keywords in every row it shows', () => {
    const outputs = new Set(['left_2', 'left_3', 'right_3'])
    const fns = new Set(['normal', 'toggle', 'delay_on'])
    for (const p of PATTERNS) {
      for (const r of p.rows) {
        expect(outputs.has(r.output)).toBe(true)
        expect(fns.has(r.fn)).toBe(true)
        expect(r.input).toMatch(/^(mp_|right_|up$|down$|left$|lip)/)
      }
    }
  })

  it('includes the patterns the spec asks for', () => {
    const all = PATTERNS.map((p) => `${p.title} ${p.what}`).join(' ').toLowerCase()
    expect(all).toContain('sprint')
    expect(all).toContain('aim')
    expect(all).toContain('stick click')
  })
})
