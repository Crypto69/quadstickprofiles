import { describe, expect, it } from 'vitest'
import { frame, testerSpec as spec } from '@/test/reports'
import { activeInputs, modeOf, stickOf, type Report } from './decode'
import { ADVANCE_MS, GuidedTest, QUIET_MS } from './guided'

function rig() {
  let t = 0
  const test = new GuidedTest(spec, () => t)
  const send = (r: Report) =>
    test.report({ mode: modeOf(spec, r), active: activeInputs(modeOf(spec, r), r), stick: stickOf(r) })
  const wait = (ms: number) => {
    t += ms
    test.tick()
  }
  return { test, send, wait }
}

describe('GuidedTest', () => {
  it('builds one section per mode, each starting with "go to mode N"', () => {
    const { test } = rig()
    expect(test.sections.map((s) => [s.name, s.mode, s.steps.length])).toEqual([
      ['Joystick', 1, 5], ['Hard', 2, 6], ['Gentle', 3, 6], ['Combinations', 4, 10], ['Everything', 5, 4],
    ])
    test.start('Hard')
    expect(test.plan[0]).toMatchObject({ kind: 'mode', mode: 2 })
    expect(test.plan).toHaveLength(7)
  })

  it('passes the mode step on the marker and moves on by itself', () => {
    const { test, send, wait } = rig()
    test.start('Hard')
    send(frame({ hat: 0 }))
    expect(test.result).toBeNull()
    send(frame({ hat: 2 }))
    expect(test.result).toMatchObject({ ok: true, asked: 'go to mode 2' })
    wait(ADVANCE_MS - 1)
    expect(test.idx).toBe(0)
    wait(1)
    expect(test.idx).toBe(1)
  })

  it('judges an input attempt once it has been quiet for 250 ms, naming all it saw', () => {
    const { test, send, wait } = rig()
    test.start('Everything')
    test.go(1) // hard sip, centre tube
    send(frame({ hat: 1, b6: 0x80 })) // R3: the gentle one first, on the way up
    send(frame({ hat: 1, b6: 0x80, b5: 0x80 })) // then triangle: the hard one
    send(frame({ hat: 1 }))
    wait(QUIET_MS - 1)
    expect(test.result).toBeNull()
    wait(1)
    expect(test.result).toEqual({
      asked: 'hard sip, centre tube',
      got: 'gentle sip, centre tube + hard sip, centre tube',
      ok: true,
    })
  })

  it('fails the wrong input, and the next attempt replaces the fail without a click', () => {
    const { test, send, wait } = rig()
    test.start('Hard')
    test.go(1) // hard sip, left
    send(frame({ hat: 2, b5: 0x10 })) // square: hard puff, left
    send(frame({ hat: 2 }))
    wait(QUIET_MS)
    expect(test.result).toMatchObject({ ok: false, got: 'hard puff, left tube' })
    send(frame({ hat: 2, b6: 0x01 }))
    send(frame({ hat: 2 }))
    wait(QUIET_MS)
    expect(test.result?.ok).toBe(true)
  })

  it('ignores input from the wrong mode', () => {
    const { test, send, wait } = rig()
    test.start('Hard')
    test.go(1)
    send(frame({ hat: 4, b6: 0x01 })) // mode 3: the gentle left sip
    send(frame({ hat: 4 }))
    wait(QUIET_MS)
    expect(test.result).toBeNull()
  })

  it('passes a joystick step at 85% travel when it returns to centre', () => {
    const { test, send } = rig()
    test.start('Joystick')
    test.go(1) // up
    send(frame({ hat: 0, y: 30 })) // 77% up
    send(frame({ hat: 0 }))
    expect(test.result).toMatchObject({ ok: false, got: 'reached 77% up (X 128, Y 30)' })
    send(frame({ hat: 0, y: 5 }))
    send(frame({ hat: 0, y: 128 }))
    expect(test.result).toMatchObject({ ok: true, got: 'reached 97% up (X 128, Y 5)' })
  })

  it('skips, goes back to redo, and counts what passed', () => {
    const { test, send, wait } = rig()
    test.start('Hard')
    send(frame({ hat: 2 }))
    wait(ADVANCE_MS)
    test.skip()
    expect(test.results.get(1)).toMatchObject({ ok: null })
    test.back()
    expect(test.idx).toBe(1)
    expect(test.results.has(1)).toBe(false)
    for (let i = 1; i < test.plan.length; i++) test.skip()
    expect(test.finished).toBe(true)
    expect(test.passed).toBe(1)
  })
})
