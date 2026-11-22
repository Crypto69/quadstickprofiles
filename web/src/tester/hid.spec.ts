import { describe, expect, it } from 'vitest'
import { frameFrom, isGamepad, isQuadStick, type HIDDeviceLike } from './hid'

const view = (bytes: number[]) => new DataView(Uint8Array.from(bytes).buffer)

describe('frameFrom', () => {
  it('puts a numbered report id back in front of a 64-byte frame', () => {
    const data = Array.from({ length: 63 }, (_, i) => i + 10)
    expect(frameFrom(1, view(data))).toEqual([1, 10, 11, 12, 13, 14, 15, 16, 17, 18])
  })

  it('takes an unnumbered 64-byte frame that starts with 0x01 as it is', () => {
    const data = [1, ...Array.from({ length: 63 }, (_, i) => i)]
    expect(frameFrom(0, view(data))).toEqual([1, 0, 1, 2, 3, 4, 5, 6, 7, 8])
  })

  it('ignores the short PS3 frames and anything else', () => {
    expect(frameFrom(1, view(new Array(26).fill(0)))).toBeNull()
    expect(frameFrom(0, view(new Array(28).fill(0)))).toBeNull()
    expect(frameFrom(2, view(new Array(63).fill(0)))).toBeNull()
  })
})

describe('device matching', () => {
  const dev = (vendorId: number, productId: number, usage: number) =>
    ({ vendorId, productId, collections: [{ usagePage: 1, usage }] }) as HIDDeviceLike
  it('knows the QuadStick and any gamepad collection', () => {
    expect(isQuadStick(dev(0x0f0d, 0x0066, 5))).toBe(true)
    expect(isQuadStick(dev(0x16d0, 0x092d, 5))).toBe(false)
    expect(isGamepad(dev(0x16d0, 0x092d, 5))).toBe(true)
    expect(isGamepad(dev(0x0f0d, 0x0066, 6))).toBe(false) // a keyboard collection
  })
})
