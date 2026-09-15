import { describe, expect, it } from 'vitest'
import {
  FRONT_HOLES, FRONT_LEDS, FRONT_PARTS, HOLE_COMBOS, REAR_JACKS, STRENGTHS,
  inputFor, ledPatternClashes, ledSentence, ledsFor,
} from './layout'

/** The lit LEDs as "n colour" pairs, so a failing test reads like the firmware table. */
function lit(n: number) {
  return ledsFor(n).flatMap((c, i) => (c === 'off' ? [] : [`${i + 1} ${c}`]))
}

describe('ledsFor', () => {
  // The firmware's update_active_config_leds, and render.leds() in core/qsprofile,
  // for modes 1..16. The card and the screen must show the same lights, in the
  // same colours, or the card cannot be trusted.
  it('matches the firmware and the printed card exactly', () => {
    expect(lit(1)).toEqual(['1 purple'])
    expect(lit(2)).toEqual(['2 purple'])
    expect(lit(5)).toEqual(['5 purple'])
    expect(lit(6)).toEqual(['1 purple', '5 purple'])
    expect(lit(7)).toEqual(['2 purple', '5 purple'])
    expect(lit(9)).toEqual(['4 purple', '5 purple'])
    expect(lit(10)).toEqual(['5 blue']) // the colour is what separates it from mode 5
    expect(lit(11)).toEqual(['1 purple', '5 blue'])
    expect(lit(14)).toEqual(['4 purple', '5 blue'])
    expect(lit(15)).toEqual(['5 red'])
    expect(lit(16)).toEqual(['1 purple', '5 red'])
  })

  it('always returns five lamps', () => {
    for (let n = 1; n <= 16; n++) expect(ledsFor(n)).toHaveLength(5)
  })

  it('reports every LED off past the sixteen modes the QuadStick reads', () => {
    expect(ledsFor(17)).toEqual(['off', 'off', 'off', 'off', 'off'])
    expect(ledsFor(0)).toEqual(['off', 'off', 'off', 'off', 'off'])
  })

  it('never lights the same LED twice or drops a colour', () => {
    for (let n = 1; n <= 16; n++) {
      const on = ledsFor(n).filter((c) => c !== 'off')
      expect(on.length).toBeGreaterThan(0)
      expect(on.length).toBeLessThanOrEqual(2)
      for (const c of on) expect(['purple', 'blue', 'red']).toContain(c)
    }
  })
})

describe('ledSentence', () => {
  it('says the lights in words, colour included', () => {
    expect(ledSentence(ledsFor(1))).toBe('LED 1 purple')
    expect(ledSentence(ledsFor(10))).toBe('LED 5 blue')
    expect(ledSentence(ledsFor(12))).toBe('LED 2 purple and LED 5 blue')
    expect(ledSentence(ledsFor(16))).toBe('LED 1 purple and LED 5 red')
    expect(ledSentence(ledsFor(0))).toBe('no LED')
  })
})

describe('ledPatternClashes', () => {
  it('finds no two of the sixteen modes that look identical, once colour counts', () => {
    // 5 and 10 used to collide as "LED 5 only"; blue against purple tells them apart
    for (let n = 1; n <= 16; n++) expect(ledPatternClashes(n, 16)).toEqual([])
    expect(ledPatternClashes(5, 10)).toEqual([])
    expect(ledPatternClashes(10, 10)).toEqual([])
  })

  it('gives every mode 1 to 16 a distinct pattern', () => {
    const patterns = new Set(Array.from({ length: 16 }, (_, i) => ledsFor(i + 1).join()))
    expect(patterns.size).toBe(16)
  })

  it('never reports a mode as clashing with itself', () => {
    expect(ledPatternClashes(3, 16)).not.toContain(3)
  })
})

describe('the front-panel layout', () => {
  it('staggers the lift so no two hole labels can sit on the same line', () => {
    const lifted = FRONT_HOLES.filter((h) => h.side === 'above')
    const lifts = lifted.map((h) => h.lift)
    expect(new Set(lifts).size).toBe(lifts.length) // all different

    // What actually matters is that no two labels share a line *and* overlap
    // horizontally. A label is centred on its hole and is about one short word
    // wide — call it 9% of the photo, so it reaches ~4.5% each side. Two labels
    // can only touch if their gap is under that and their lifts are equal.
    //
    // The holes are 10.5% apart, so neighbours clear each other horizontally and
    // need only differ in lift. That is why Centre can sit one step below Right
    // rather than three steps above it, up in the status LED row where it covered
    // LED 3. Checked in a browser at 560px: no label overlaps another or an LED.
    const HALF_LABEL = 4.5
    for (const a of lifted) {
      for (const b of lifted) {
        if (a === b) continue
        const overlapsSideways = Math.abs(a.x - b.x) < HALF_LABEL * 2
        if (overlapsSideways) expect(a.lift).not.toBe(b.lift)
      }
    }
  })

  it('keeps the photo label short but the grid heading full', () => {
    for (const h of FRONT_HOLES) {
      expect(h.label.length).toBeLessThanOrEqual(10) // narrow, so callouts cannot collide
      expect(h.full.length).toBeGreaterThanOrEqual(h.label.length)
    }
    expect(FRONT_HOLES.map((h) => h.full)).toEqual([
      'Left hole', 'Centre hole', 'Right hole', 'Side tube',
    ])
  })

  it('has the four holes left to right, with the side tube last', () => {
    expect(FRONT_HOLES.map((h) => h.prefix)).toEqual(['mp_left', 'mp_center', 'mp_right', 'right'])
    expect(FRONT_HOLES.filter((h) => h.sideTube)).toHaveLength(1)
    expect(FRONT_HOLES.at(-1)!.sideTube).toBe(true)
    const xs = FRONT_HOLES.map((h) => h.x)
    expect([...xs].sort((a, b) => a - b)).toEqual(xs) // already in visual order
  })

  it('keeps every callout inside the photo', () => {
    for (const c of [...FRONT_HOLES, ...REAR_JACKS]) {
      expect(c.x).toBeGreaterThan(0)
      expect(c.x).toBeLessThan(100)
      expect(c.y).toBeGreaterThan(0)
      expect(c.y).toBeLessThan(100)
    }
  })

  it('builds the input keywords the catalog actually uses', () => {
    expect(inputFor('mp_left', '_sip')).toBe('mp_left_sip')
    expect(inputFor('mp_center', '_puff_soft')).toBe('mp_center_puff_soft')
    expect(inputFor('right', '_sip')).toBe('right_sip') // the side tube has no mp_ prefix
  })

  it('orders the pressure rows the way the card prints them', () => {
    expect(STRENGTHS.map((s) => s.title)).toEqual(['Soft puff', 'Puff', 'Sip', 'Soft sip'])
  })
})

describe('the rear-panel layout', () => {
  it('numbers the jacks as the case is printed: the top one is 7-8, not 3-4', () => {
    const top = REAR_JACKS.find((j) => j.printed === 'In 7-8')!
    const bottom = REAR_JACKS.find((j) => j.printed === 'In 1-2')!
    expect(top.inputs).toEqual([7, 8])
    expect(top.y).toBeLessThan(bottom.y) // the 7-8 jack is physically above 1-2
    expect(REAR_JACKS.find((j) => j.printed === 'In 3-4')!.inputs).toEqual([3, 4])
    expect(REAR_JACKS.find((j) => j.printed === 'Lip 5-6')!.inputs).toEqual([5, 6])
  })

  it('covers digital_in_1 through 8 exactly once', () => {
    const all = REAR_JACKS.flatMap((j) => j.inputs).sort((a, b) => a - b)
    expect(all).toEqual([1, 2, 3, 4, 5, 6, 7, 8])
  })
})

describe('hole combos', () => {
  it('lists the combinations the firmware actually accepts', () => {
    expect(HOLE_COMBOS.map((c) => c.prefix)).toEqual([
      'mp_left_center', 'mp_right_center', 'mp_left_right', 'mp_triple',
    ])
  })
})

describe('status LED spots', () => {
  it('has one spot per LED, left to right', () => {
    expect(FRONT_LEDS).toHaveLength(5)
    const xs = FRONT_LEDS.map((l) => l.x)
    expect([...xs].sort((a, b) => a - b)).toEqual(xs)
  })

  it('keeps them on one row, evenly spaced', () => {
    expect(new Set(FRONT_LEDS.map((l) => l.y)).size).toBe(1)
    const gaps = FRONT_LEDS.slice(1).map((l, i) => l.x - FRONT_LEDS[i]!.x)
    for (const g of gaps) expect(Math.abs(g - gaps[0]!)).toBeLessThan(0.5)
  })

  // Centre is the tallest-lifted hole label and sits directly under the LED row.
  // At lift 5 it covered LED 3, which the mode overlay needs readable.
  it('keeps the lifted hole labels below the status LED row', () => {
    const centre = FRONT_HOLES.find((h) => h.prefix === 'mp_center')!
    expect(centre.lift).toBeLessThanOrEqual(4)
    // and it still clears its neighbours, which is what lift is for
    const others = FRONT_HOLES.filter((h) => h.lift > 0 && h.prefix !== 'mp_center')
    for (const o of others) expect(o.lift).not.toBe(centre.lift)
  })

  it('keeps the Status LEDs label clear of the lights it points at', () => {
    const label = FRONT_PARTS.find((p) => p.marker === 'led')!
    // 'below' puts the label under its anchor, so it cannot cover the LED row —
    // it used to sit beside them and hid the lights the overlay now needs.
    expect(label.side).toBe('below')
  })
})
