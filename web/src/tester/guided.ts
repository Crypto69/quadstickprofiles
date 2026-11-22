/**
 * The guided test: one instruction at a time ("hard sip, left tube"), then what
 * the QuadStick actually reported. Pure logic with an injected clock, so the
 * rules below are unit-tested without a device or a timer.
 *
 * - A section starts with "go to mode N", which passes as soon as the d-pad
 *   marker shows mode N.
 * - An input step gathers every input seen during an attempt. The attempt ends
 *   250 ms after the last input lets go, and passes if the asked input was among
 *   them. The result names everything that registered, so "asked hard, got
 *   gentle + hard" is visible.
 * - A joystick step tracks the furthest travel in the asked direction while the
 *   stick is off centre (more than 15 %). Back at centre it passes at 85 % or more.
 * - Reports from the wrong mode are ignored; the page says "go back to mode N".
 * - A pass moves on by itself after 1.3 s. A fail stays on screen, and the next
 *   attempt simply replaces it: no button to press first (the pointer is driven
 *   by mouth or head, so every click saved counts). Skip moves on without one.
 */
import { describe, type Stick, type TesterMode, type TesterSpec } from './decode'

export type Direction = 'up' | 'down' | 'left' | 'right'

export type Step =
  | { kind: 'mode'; mode: number; section: string }
  | { kind: 'joy'; mode: number; dir: Direction; section: string }
  | { kind: 'input'; mode: number; input: string; section: string }

export interface Section {
  name: string
  mode: number
  steps: Step[]
}

export interface Result {
  asked: string
  got: string
  /** true passed, false failed, null skipped. */
  ok: boolean | null
}

/** What one report tells the test. */
export interface Sample {
  mode: TesterMode | null
  active: string[]
  stick: Stick
}

export const QUIET_MS = 250
export const ADVANCE_MS = 1300
export const JOY_DEADZONE = 0.15
export const JOY_PASS = 0.85

const DIRECTIONS: Direction[] = ['up', 'down', 'left', 'right']

/** The sections, from the spec: only inputs the mode really maps become steps. */
export function buildSections(spec: TesterSpec): Section[] {
  const has = (n: number, id: string) =>
    spec.modes.find((m) => m.n === n)?.map.some((e) => e.input === id) ?? false
  const inputs = (name: string, n: number, ids: string[]): Step[] =>
    ids.filter((id) => has(n, id)).map((input) => ({ kind: 'input', mode: n, input, section: name }))
  const singles = (suffix: string) =>
    ['left', 'center', 'right'].flatMap((t) => [`mp_${t}_sip${suffix}`, `mp_${t}_puff${suffix}`])
  const sections: Section[] = [
    {
      name: 'Joystick',
      mode: 1,
      steps: [
        ...DIRECTIONS.map((dir): Step => ({ kind: 'joy', mode: 1, dir, section: 'Joystick' })),
        ...inputs('Joystick', 1, ['lip']),
      ],
    },
    { name: 'Hard', mode: 2, steps: inputs('Hard', 2, singles('')) },
    { name: 'Gentle', mode: 3, steps: inputs('Gentle', 3, singles('_soft')) },
    {
      name: 'Combinations',
      mode: 4,
      steps: inputs('Combinations', 4, [
        'mp_left_center_sip', 'mp_left_center_puff', 'mp_right_center_sip', 'mp_right_center_puff',
        'mp_left_center_sip_soft', 'mp_left_center_puff_soft', 'mp_right_center_sip_soft',
        'mp_right_center_puff_soft', 'right_sip_soft', 'right_puff_soft',
      ]),
    },
    {
      name: 'Everything',
      mode: 5,
      steps: inputs('Everything', 5, [
        'mp_center_sip', 'mp_center_sip_soft', 'mp_left_puff', 'mp_left_puff_soft',
      ]),
    },
  ]
  return sections.filter((s) => spec.modes.some((m) => m.n === s.mode) && s.steps.length)
}

export class GuidedTest {
  readonly sections: Section[]
  plan: Step[] = []
  /** −1 before the first start; plan.length once finished. */
  idx = -1
  results = new Map<number, Result>()
  /** What was asked for: the whole test, or one section's name. */
  scope = ''

  private capture: Set<string> | null = null
  private quietSince: number | null = null
  private joyPeak: { along: number; rx: number; ry: number } | null = null
  private passedAt: number | null = null

  constructor(
    private readonly spec: TesterSpec,
    private readonly now: () => number = () => performance.now(),
  ) {
    this.sections = buildSections(spec)
  }

  get running(): boolean {
    return this.idx >= 0 && this.idx < this.plan.length
  }

  get finished(): boolean {
    return this.plan.length > 0 && this.idx >= this.plan.length
  }

  get step(): Step | null {
    return this.running ? (this.plan[this.idx] ?? null) : null
  }

  /** The current step's result, if it has one yet. */
  get result(): Result | null {
    return this.results.get(this.idx) ?? null
  }

  get passed(): number {
    return [...this.results.values()].filter((r) => r.ok === true).length
  }

  asked(st: Step): string {
    if (st.kind === 'mode') return `go to mode ${st.mode}`
    if (st.kind === 'joy') return `joystick all the way ${st.dir}`
    return describe(this.spec, st.input)
  }

  /** Start the whole test, or one section by name. */
  start(section?: string) {
    this.plan = []
    for (const s of this.sections) {
      if (section !== undefined && s.name !== section) continue
      this.plan.push({ kind: 'mode', mode: s.mode, section: s.name }, ...s.steps)
    }
    this.scope = section ?? 'the whole test'
    this.results = new Map()
    this.go(0)
  }

  go(i: number) {
    this.idx = Math.max(0, Math.min(i, this.plan.length))
    this.capture = null
    this.quietSince = null
    this.joyPeak = null
    this.passedAt = null
  }

  retry() {
    this.results.delete(this.idx)
    this.go(this.idx)
  }

  skip() {
    if (!this.running) return
    this.record(null, 'skipped')
    this.go(this.idx + 1)
  }

  /** Go to the previous step and do it again. */
  back() {
    this.results.delete(this.idx - 1)
    this.go(this.idx - 1)
  }

  /** Feed every report here. */
  report(s: Sample) {
    const st = this.step
    if (!st || this.result?.ok === true) return
    if (st.kind === 'mode') {
      if (s.mode?.n === st.mode) this.record(true, `mode ${st.mode}, ${s.mode.name}`)
      return
    }
    if (s.mode?.n !== st.mode) return
    if (st.kind === 'joy') {
      const along = { up: s.stick.y, down: -s.stick.y, left: -s.stick.x, right: s.stick.x }[st.dir]
      const off = Math.max(Math.abs(s.stick.x), Math.abs(s.stick.y))
      if (off > JOY_DEADZONE) {
        if (!this.joyPeak || along > this.joyPeak.along) {
          this.joyPeak = { along, rx: s.stick.rx, ry: s.stick.ry }
        }
      } else if (this.joyPeak) {
        const peak = this.joyPeak
        this.joyPeak = null
        const pct = Math.round(Math.max(0, peak.along) * 100)
        this.record(peak.along >= JOY_PASS, `reached ${pct}% ${st.dir} (X ${peak.rx}, Y ${peak.ry})`)
      }
      return
    }
    if (s.active.length) {
      this.capture ??= new Set()
      for (const a of s.active) this.capture.add(a)
      this.quietSince = null
    } else if (this.capture && this.quietSince === null) {
      this.quietSince = this.now()
    }
  }

  /** Call often (every 50 ms): ends quiet attempts and moves on after a pass. */
  tick() {
    const t = this.now()
    if (this.result?.ok === true && this.passedAt !== null && t - this.passedAt >= ADVANCE_MS) {
      this.go(this.idx + 1)
      return
    }
    if (!this.capture || this.quietSince === null || t - this.quietSince < QUIET_MS) return
    const st = this.step
    const got = [...this.capture]
    this.capture = null
    this.quietSince = null
    if (st?.kind !== 'input' || this.result?.ok === true) return
    this.record(got.includes(st.input), got.map((id) => describe(this.spec, id)).join(' + '))
  }

  private record(ok: boolean | null, got: string) {
    const st = this.step
    if (!st) return
    this.results.set(this.idx, { asked: this.asked(st), got, ok })
    if (ok === true) this.passedAt = this.now()
  }
}
