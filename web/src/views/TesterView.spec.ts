import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import TesterView from './TesterView.vue'
import { fileResponse, stubFetch } from '@/test/factories'
import { frame, testerSpec } from '@/test/reports'

async function settle(times = 6) {
  for (let i = 0; i < times; i++) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
}

/** A QuadStick the browser already knows (picked on an earlier visit). */
function fakeQuadStick() {
  const listeners: ((e: unknown) => void)[] = []
  const device = {
    opened: false,
    vendorId: 0x0f0d,
    productId: 0x0066,
    productName: 'QuadStick',
    collections: [{ usagePage: 1, usage: 5 }],
    open: vi.fn(async () => {
      device.opened = true
    }),
    close: vi.fn(async () => {
      device.opened = false
    }),
    addEventListener: (_: string, fn: (e: unknown) => void) => listeners.push(fn),
    removeEventListener: vi.fn(),
  }
  /** Send a report the way WebHID does: id stripped, 63 data bytes. */
  const send = (bytes: number[]) => {
    const data = new Uint8Array(63)
    data.set(bytes.slice(1))
    for (const fn of listeners) fn({ device, reportId: 1, data: new DataView(data.buffer) })
  }
  const hid = {
    getDevices: vi.fn(async () => [device]),
    requestDevice: vi.fn(async () => [device]),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }
  return { device, hid, send }
}

async function page(withHid = true) {
  vi.stubGlobal(
    'fetch',
    stubFetch({
      '/api/tester/spec': testerSpec,
      '/api/tester/qstest.csv': fileResponse('QuadStick Configuration,Version 1.4,,qstest\r\n', { filename: 'qstest.csv', contentType: 'text/csv' }),
    }),
  )
  const qs = fakeQuadStick()
  if (withHid) Object.defineProperty(navigator, 'hid', { value: qs.hid, configurable: true })
  const w = mount(TesterView, { attachTo: document.body })
  await settle()
  return { w, ...qs }
}

describe('TesterView', () => {
  beforeEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })
  afterEach(() => {
    Reflect.deleteProperty(navigator, 'hid')
    document.body.innerHTML = ''
  })

  it('reconnects a QuadStick the browser already knows, without asking', async () => {
    const { w, device, hid } = await page()
    expect(device.open).toHaveBeenCalled()
    expect(hid.requestDevice).not.toHaveBeenCalled()
    expect(w.text()).toContain('Connected: QuadStick')
  })

  it('shows the mode, the LEDs and what each tube reports, live', async () => {
    const { w, send } = await page()
    send(frame({ hat: 2, b6: 0x01 })) // mode 2, L1: hard sip on the left tube
    await settle()
    expect(w.find('.big').text()).toContain('Hard sips & puffs')
    expect(w.text()).toContain('LED 2 purple')
    expect(w.find('.live').text()).toContain('hard sip, left tube')
    expect(w.findAll('circle.tube.sip')).toHaveLength(1)
    expect(w.findAll('circle.led.purple')).toHaveLength(1)
  })

  it('says so when the device is not in the test profile, and names the raw buttons', async () => {
    const { w, send } = await page()
    send(frame({ hat: 15, b5: 0x20 }))
    await settle()
    expect(w.find('.big').text()).toContain('Not the test profile')
    expect(w.find('.live').text()).toBe('Buttons: cross')
  })

  it('runs a section: the mode step, then a wrong input flagged, then the right one', async () => {
    const { w, send } = await page()
    const hard = w.findAll('button').find((b) => b.text() === '2 · Hard')
    await hard!.trigger('click')
    expect(w.find('.ask').text()).toContain('Go to mode 2')
    send(frame({ hat: 2 }))
    await settle()
    expect(w.find('.verdict').text()).toContain('✓')
    await new Promise((r) => setTimeout(r, 1400)) // a pass moves on by itself
    await settle()
    expect(w.find('.ask').text()).toMatch(/Hard sip\s+on the left tube/i)
    send(frame({ hat: 2, b5: 0x10 })) // square: hard puff, left
    send(frame({ hat: 2 }))
    await new Promise((r) => setTimeout(r, 350))
    await settle()
    expect(w.find('.verdict').text()).toContain('hard puff, left tube')
    expect(w.find('.results').text()).toContain('✗')
  })

  it('offers the test profile with the copy-it-on checklist', async () => {
    const { w } = await page()
    const btn = w.findAll('button').find((b) => b.text() === 'Download qstest.csv')
    await btn!.trigger('click')
    await settle()
    expect(document.body.textContent).toContain('Copy qstest.csv onto the QuadStick')
  })

  it('explains why USB cannot be read when the browser has no WebHID', async () => {
    const { w } = await page(false)
    expect(w.find('.warn').text()).toMatch(/secure page|Chrome or Edge/)
    expect(w.findAll('button').some((b) => b.text() === 'Connect the QuadStick')).toBe(false)
  })
})
