/**
 * Turning the QuadStick's raw USB input report into "hard sip, left tube".
 *
 * The device sends 64-byte PS4-layout reports (byte 0 is the report id, 0x01).
 * A report says neither which mode the device is in nor which tube pressed a
 * button, so the tester leans on the `qstest` profile (core/qsprofile/tester.py):
 * each mode holds one d-pad direction, which names the mode, and each tested
 * input drives its own button. The spec the API serves says which bit is which.
 *
 *   byte 1, 2   left stick X, Y (0–255, 128 centre; stick up = low Y)
 *   byte 5      low nibble: d-pad hat (0 N … 7 NW, 15 released);
 *               0x10 square, 0x20 cross, 0x40 circle, 0x80 triangle
 *   byte 6      L1 R1 L2 R2 share options L3 R3 (bit 0 … 7)
 *   byte 7      0x01 PS, 0x02 touchpad
 */

/** The first ten bytes of a report, byte 0 the report id. */
export type Report = readonly number[]

export type Tube = 'left' | 'center' | 'right' | 'side' | 'lip'

export interface TesterInput {
  tubes: Tube[]
  action: 'sip' | 'puff' | 'press'
  level: 'hard' | 'gentle' | ''
}

export interface TesterMapEntry {
  out: string
  byte: number
  mask: number
  input: string
}

export interface TesterMode {
  n: number
  name: string
  /** The d-pad direction this mode holds, as the hat nibble reads it. */
  hat: number
  help: string
  map: TesterMapEntry[]
}

/** GET /api/tester/spec, generated with the profile from one table. */
export interface TesterSpec {
  profile: string
  filename: string
  inputs: Record<string, TesterInput>
  modes: TesterMode[]
}

/** What the hat reads with no d-pad held (measured: 15, not 8). */
export const HAT_RELEASED = 15

export function hat(b: Report): number {
  return (b[5] ?? HAT_RELEASED) & 15
}

/** The qstest mode the report's d-pad marker names, or null when it names none. */
export function modeOf(spec: TesterSpec, b: Report): TesterMode | null {
  const h = hat(b)
  return spec.modes.find((m) => m.hat === h) ?? null
}

/** The inputs whose button is down in this report, in the mode's map order. */
export function activeInputs(mode: TesterMode | null, b: Report): string[] {
  if (!mode) return []
  return mode.map.filter((e) => ((b[e.byte] ?? 0) & e.mask) !== 0).map((e) => e.input)
}

export interface Stick {
  /** −1 … 1, right positive. */
  x: number
  /** −1 … 1, up positive (the report's Y runs the other way). */
  y: number
  /** The raw bytes, 0–255. */
  rx: number
  ry: number
}

export function axis(v: number): number {
  return Math.max(-1, Math.min(1, (v - 128) / 127))
}

export function stickOf(b: Report | null): Stick {
  if (!b) return { x: 0, y: 0, rx: 128, ry: 128 }
  const rx = b[1] ?? 128
  const ry = b[2] ?? 128
  return { x: axis(rx), y: -axis(ry), rx, ry }
}

/** Every button by its PlayStation name, for a profile that is not qstest. */
const RAW: [number, number, string][] = [
  [5, 0x10, 'square'], [5, 0x20, 'cross'], [5, 0x40, 'circle'], [5, 0x80, 'triangle'],
  [6, 0x01, 'L1'], [6, 0x02, 'R1'], [6, 0x04, 'L2'], [6, 0x08, 'R2'],
  [6, 0x10, 'share'], [6, 0x20, 'options'], [6, 0x40, 'L3'], [6, 0x80, 'R3'],
  [7, 0x01, 'PS'], [7, 0x02, 'touchpad'],
]

export function rawButtons(b: Report): string[] {
  return RAW.filter(([byte, mask]) => ((b[byte] ?? 0) & mask) !== 0).map(([, , name]) => name)
}

export const TUBE_NAME: Record<Tube, string> = {
  left: 'left',
  center: 'centre',
  right: 'right',
  side: 'side tube',
  lip: 'lip button',
}

/** "hard sip, left tube", "gentle puff, left + centre tubes", "lip button". */
export function describe(spec: TesterSpec, id: string): string {
  const i = spec.inputs[id]
  if (!i) return id
  if (i.action === 'press') return 'lip button'
  const where = i.tubes.map((t) => TUBE_NAME[t]).join(' + ')
  const what = `${i.level === 'gentle' ? 'gentle' : 'hard'} ${i.action}`
  if (i.tubes[0] === 'side') return `${what}, side tube`
  return `${what}, ${where} tube${i.tubes.length > 1 ? 's' : ''}`
}

/**
 * Which tubes to light, and as what. When a gentle and a hard input are both
 * down on one tube (mode 5 shows both), the tube shows hard.
 */
export function litTubes(spec: TesterSpec, ids: string[]): Partial<Record<Tube, TesterInput>> {
  const on: Partial<Record<Tube, TesterInput>> = {}
  for (const id of ids) {
    const i = spec.inputs[id]
    if (!i) continue
    for (const t of i.tubes) {
      const prev = on[t]
      if (!prev || (prev.level === 'gentle' && i.level === 'hard')) on[t] = i
    }
  }
  return on
}

/**
 * A mode change is a side-tube sip (next) or puff (previous), wrapping round.
 * The report never says which, so it is read off the step between the two modes.
 */
export function sideTubeFor(from: number, to: number, total: number): 'sip' | 'puff' | null {
  if (from === to) return null
  if (to === from + 1 || (from === total && to === 1)) return 'sip'
  if (to === from - 1 || (from === 1 && to === total)) return 'puff'
  return null
}
