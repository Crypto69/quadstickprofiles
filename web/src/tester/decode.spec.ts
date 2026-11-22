import { describe as group, expect, it } from 'vitest'
import { frame, testerSpec as spec } from '@/test/reports'
import {
  activeInputs, describe, hat, litTubes, modeOf, rawButtons, sideTubeFor, stickOf,
} from './decode'

group('decode', () => {
  it('reads the mode off the d-pad marker', () => {
    expect([0, 2, 4, 6, 1].map((h) => modeOf(spec, frame({ hat: h }))?.n)).toEqual([1, 2, 3, 4, 5])
    expect(modeOf(spec, frame())).toBeNull() // released: 15
    expect(modeOf(spec, frame({ hat: 3 }))).toBeNull() // SE is no qstest mode
    expect(hat(frame({ hat: 6, b5: 0x30 }))).toBe(6) // buttons in the high nibble do not leak
  })

  it('turns a button bit back into the input that drove it, per mode', () => {
    const hard = modeOf(spec, frame({ hat: 2 }))
    const gentle = modeOf(spec, frame({ hat: 4 }))
    // L1 is the left tube in both, hard in mode 2 and gentle in mode 3
    expect(activeInputs(hard, frame({ hat: 2, b6: 0x01 }))).toEqual(['mp_left_sip'])
    expect(activeInputs(gentle, frame({ hat: 4, b6: 0x01 }))).toEqual(['mp_left_sip_soft'])
    expect(activeInputs(hard, frame({ hat: 2, b7: 0x02 }))).toEqual(['lip'])
    expect(activeInputs(null, frame({ b6: 0xff }))).toEqual([])
  })

  it('names every button for a profile that is not qstest', () => {
    expect(rawButtons(frame({ b5: 0x10, b6: 0x21, b7: 0x02 }))).toEqual(['square', 'L1', 'options', 'touchpad'])
  })

  it('reads the stick with up as positive', () => {
    expect(stickOf(frame({ x: 255, y: 0 }))).toMatchObject({ x: 1, y: 1, rx: 255, ry: 0 })
    expect(stickOf(frame({ x: 1, y: 255 }))).toMatchObject({ x: -1, y: -1 })
    expect(stickOf(null)).toMatchObject({ x: 0, y: 0 })
  })

  it('says which tube in words', () => {
    expect(describe(spec, 'mp_left_sip')).toBe('hard sip, left tube')
    expect(describe(spec, 'mp_right_center_puff_soft')).toBe('gentle puff, right + centre tubes')
    expect(describe(spec, 'right_sip_soft')).toBe('gentle sip, side tube')
    expect(describe(spec, 'lip')).toBe('lip button')
  })

  it('shows hard when a tube reports hard and gentle together', () => {
    const on = litTubes(spec, ['mp_left_sip_soft', 'mp_left_sip', 'mp_center_puff_soft'])
    expect(on.left?.level).toBe('hard')
    expect(on.center).toMatchObject({ action: 'puff', level: 'gentle' })
    expect(litTubes(spec, ['mp_left_center_sip'])).toHaveProperty('center')
  })

  it('reads a mode change as a side-tube sip or puff, wrapping round', () => {
    expect(sideTubeFor(2, 3, 5)).toBe('sip')
    expect(sideTubeFor(5, 1, 5)).toBe('sip')
    expect(sideTubeFor(3, 2, 5)).toBe('puff')
    expect(sideTubeFor(1, 5, 5)).toBe('puff')
    expect(sideTubeFor(1, 3, 5)).toBeNull()
  })
})
