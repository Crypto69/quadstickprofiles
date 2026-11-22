/**
 * Reading the QuadStick in the browser, through WebHID (Chrome and Edge).
 *
 * The app runs on a NAS or as a desktop app, but the QuadStick is plugged into
 * the computer in front of the user, so the browser is the one place that can
 * see it. Read-only: nothing is ever sent to the device.
 *
 * The QuadStick is a composite device (gamepad + keyboard + mouse + drive).
 * Only its gamepad collection is asked for: the keyboard and mouse collections
 * are blocked by the browser anyway, and the gamepad needs no permission beyond
 * the user picking it once. The browser remembers that choice, so the next
 * visit reconnects without asking.
 */
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import type { Report } from './decode'

/** Measured on the owner's unit. Other identities (16D0:092D after a profile
 *  switch) still match the gamepad filters below. */
export const QUADSTICK = { vendorId: 0x0f0d, productId: 0x0066 }

/** Usage page 1 (Generic Desktop): Joystick 4, GamePad 5, Multi-axis 8. */
export const GAMEPAD_FILTERS = [4, 5, 8].map((usage) => ({ usagePage: 1, usage }))

/** The ten bytes the decoder reads. */
export const REPORT_BYTES = 10

// ---- the slice of WebHID used here (not in TypeScript's DOM lib yet) -----------
interface HIDCollection {
  usagePage?: number
  usage?: number
}
export interface HIDDeviceLike {
  opened: boolean
  vendorId: number
  productId: number
  productName: string
  collections: HIDCollection[]
  open(): Promise<void>
  close(): Promise<void>
  addEventListener(type: 'inputreport', fn: (e: HIDReportEvent) => void): void
  removeEventListener(type: 'inputreport', fn: (e: HIDReportEvent) => void): void
}
interface HIDReportEvent {
  device: HIDDeviceLike
  reportId: number
  data: DataView
}
interface HIDConnectionEvent {
  device: HIDDeviceLike
}
export interface HIDLike {
  getDevices(): Promise<HIDDeviceLike[]>
  requestDevice(opts: { filters: object[] }): Promise<HIDDeviceLike[]>
  addEventListener(type: 'connect' | 'disconnect', fn: (e: HIDConnectionEvent) => void): void
  removeEventListener(type: 'connect' | 'disconnect', fn: (e: HIDConnectionEvent) => void): void
}

export function webHid(): HIDLike | null {
  if (typeof navigator === 'undefined') return null
  return (navigator as Navigator & { hid?: HIDLike }).hid ?? null
}

/**
 * Why USB cannot be read here, or null when it can. A browser only offers WebHID
 * on a secure page: https, or this computer's own localhost.
 */
export function unsupportedReason(): 'insecure' | 'browser' | null {
  if (webHid()) return null
  if (typeof window !== 'undefined' && !window.isSecureContext) return 'insecure'
  return 'browser'
}

/**
 * The first bytes of a 64-byte PS4-layout frame, with the report id as byte 0,
 * or null for anything else (the 27/28-byte PS3 frames carry no buttons).
 * A device that numbers its reports has the id stripped into `reportId`; one
 * that does not leaves it as the first data byte.
 */
export function frameFrom(reportId: number, data: DataView): Report | null {
  const bytes = new Uint8Array(data.buffer, data.byteOffset, data.byteLength)
  let frame: number[]
  if (reportId === 1 && bytes.length === 63) frame = [1, ...bytes.subarray(0, REPORT_BYTES - 1)]
  else if (reportId === 0 && bytes.length === 64 && bytes[0] === 1)
    frame = [...bytes.subarray(0, REPORT_BYTES)]
  else return null
  return frame
}

export function isGamepad(d: HIDDeviceLike): boolean {
  return d.collections.some((c) => c.usagePage === 1 && [4, 5, 8].includes(c.usage ?? -1))
}

export function isQuadStick(d: HIDDeviceLike): boolean {
  return d.vendorId === QUADSTICK.vendorId && d.productId === QUADSTICK.productId
}

/**
 * The connection and the latest report, as refs. `onReport` is called for every
 * frame, which is where the guided test listens. `inject` feeds a frame by hand:
 * the page's tests use it, and in a dev build it is on `window.__qsTester` so
 * the page can be driven in a browser without a device.
 */
export function useQuadStickHid(onReport: (r: Report) => void) {
  const hid = webHid()
  const device = shallowRef<HIDDeviceLike | null>(null)
  const connected = ref(false)
  const report = shallowRef<Report | null>(null)
  const error = ref('')

  function feed(r: Report) {
    report.value = r
    onReport(r)
  }

  function onInput(e: HIDReportEvent) {
    const frame = frameFrom(e.reportId, e.data)
    if (frame) feed(frame)
  }

  async function use(d: HIDDeviceLike) {
    error.value = ''
    if (device.value && device.value !== d) await drop()
    try {
      if (!d.opened) await d.open()
    } catch (e) {
      error.value =
        'The QuadStick was found but could not be opened. Close any other app or tab that is ' +
        `reading it, then try again. (${e instanceof Error ? e.message : String(e)})`
      return
    }
    d.addEventListener('inputreport', onInput)
    device.value = d
    connected.value = true
  }

  async function drop() {
    const d = device.value
    device.value = null
    connected.value = false
    report.value = null
    if (!d) return
    d.removeEventListener('inputreport', onInput)
    if (d.opened) await d.close().catch(() => {})
  }

  /** Prefer the QuadStick itself among the gamepads the browser offers. */
  const pick = (list: HIDDeviceLike[]) =>
    list.find((d) => isQuadStick(d) && isGamepad(d)) ?? list.find(isGamepad) ?? null

  /** The browser's chooser. Must run from a click. */
  async function connect() {
    if (!hid) return
    try {
      const chosen = pick(await hid.requestDevice({ filters: GAMEPAD_FILTERS }))
      if (chosen) await use(chosen)
    } catch (e) {
      error.value = `The browser refused: ${e instanceof Error ? e.message : String(e)}`
    }
  }

  function onConnect(e: HIDConnectionEvent) {
    if (!device.value && isGamepad(e.device)) void use(e.device)
  }
  function onDisconnect(e: HIDConnectionEvent) {
    if (e.device === device.value) void drop()
  }

  function inject(r: Report, up = true) {
    connected.value = up
    if (up) feed(r)
    else report.value = null
  }

  onMounted(async () => {
    if (import.meta.env.DEV) (window as unknown as { __qsTester?: unknown }).__qsTester = { inject }
    if (!hid) return
    hid.addEventListener('connect', onConnect)
    hid.addEventListener('disconnect', onDisconnect)
    // Picked on an earlier visit: the browser remembers, so no chooser this time.
    const known = pick(await hid.getDevices().catch(() => []))
    if (known && !device.value) await use(known)
  })

  onBeforeUnmount(() => {
    if (hid) {
      hid.removeEventListener('connect', onConnect)
      hid.removeEventListener('disconnect', onDisconnect)
    }
    void drop()
  })

  return { supported: hid !== null, device, connected, report, error, connect, disconnect: drop, inject }
}
