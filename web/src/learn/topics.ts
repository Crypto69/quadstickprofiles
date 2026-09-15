/**
 * The Learn section's content, as data so it can be routed, searched and tested.
 * Every fact here is from docs/ or the fixtures — nothing is invented. Where a
 * claim comes from a specific file, the source is named in the text.
 */
export interface Topic {
  slug: string
  title: string
  /** One line for the index. */
  blurb: string
}

export const TOPICS: Topic[] = [
  {
    slug: 'three-parts',
    title: 'The three parts of every row',
    blurb: 'What you do, how it behaves, what the console sees.',
  },
  {
    slug: 'files-and-modes',
    title: 'Files, modes and rows',
    blurb: 'Why modes exist: there are only so many sips and puffs.',
  },
  {
    slug: 'changing-mode',
    title: 'Changing mode, and changing file',
    blurb: 'One is instant. The other needs the joystick and the lights.',
  },
  {
    slug: 'lights',
    title: 'Reading the lights',
    blurb: 'One to five, one purple light each. Past five, LED 5 says which round: purple, blue or red.',
  },
  {
    slug: 'soft-and-hard',
    title: 'Soft and hard',
    blurb: 'Two thresholds double your inputs. A beep or a click tells you which.',
  },
  {
    slug: 'functions',
    title: 'How an output can behave',
    blurb: 'Hold, toggle, repeat, pulse, tap, delay — with a picture of each.',
  },
  {
    slug: 'patterns',
    title: 'Tricks from your own profiles',
    blurb: 'Real rows from the Fortnite and Call of Duty files.',
  },
  {
    slug: 'settings',
    title: 'Which setting wins',
    blurb: 'The device, then the profile, then the mode.',
  },
  {
    slug: 'safety',
    title: 'Staying out of trouble',
    blurb: 'default.csv, and the modes that hide the flash drive.',
  },
]

export const topicBySlug = (slug: string) => TOPICS.find((t) => t.slug === slug) ?? null

/**
 * The output functions worth animating, in teaching order. `description` is the
 * catalog's own wording; `plain` is the same idea without jargon. `phases` drive
 * the animation: each is [inputHeld, outputOn] over equal slices of the loop.
 */
export interface FunctionDemo {
  name: string
  plain: string
  /** True where the input is held, over 12 equal ticks. */
  input: boolean[]
  /** True where the output is pressed, over the same 12 ticks. */
  output: boolean[]
  note?: string
}

const T = true
const F = false

export const FUNCTION_DEMOS: FunctionDemo[] = [
  {
    name: 'normal',
    plain: 'On while you hold it. Let go and it stops.',
    input: [F, F, T, T, T, T, T, F, F, F, F, F],
    output: [F, F, T, T, T, T, T, F, F, F, F, F],
  },
  {
    name: 'toggle',
    plain: 'One sip turns it on and it stays on. The next sip turns it off.',
    input: [F, T, F, F, F, F, T, F, F, F, F, F],
    output: [F, T, T, T, T, T, F, F, F, F, F, F],
    note: 'Handy for aiming down sights, so you do not have to keep sipping.',
  },
  {
    name: 'repeat',
    plain: 'Presses again and again while you hold it.',
    input: [F, T, T, T, T, T, T, T, F, F, F, F],
    output: [F, T, F, T, F, T, F, T, F, F, F, F],
    note: 'Takes two numbers: how fast, and how long to wait before it starts.',
  },
  {
    name: 'pulse',
    plain: 'One short press, however long you hold it.',
    input: [F, T, T, T, T, T, T, F, F, F, F, F],
    output: [F, T, F, F, F, F, F, F, F, F, F, F],
  },
  {
    name: 'tap',
    plain: 'A quick tap presses it. Holding on does nothing.',
    input: [F, T, F, F, T, T, T, T, T, F, F, F],
    output: [F, T, F, F, F, F, F, F, F, F, F, F],
  },
  {
    name: 'delay_on',
    plain: 'Waits a moment before it starts, so a quick sip does nothing.',
    input: [F, T, T, T, T, T, T, F, F, F, F, F],
    output: [F, F, F, T, T, T, T, F, F, F, F, F],
    note: 'Your Fortnite profile uses this on a soft left puff for the right stick click.',
  },
  {
    name: 'delay_off',
    plain: 'Stays on a little after you let go.',
    input: [F, T, T, T, F, F, F, F, F, F, F, F],
    output: [F, T, T, T, T, T, F, F, F, F, F, F],
  },
  {
    name: 'delayed_latch',
    plain: 'A quick press is a quick press. Hold it and it latches on.',
    input: [F, T, F, F, T, T, T, T, F, F, F, F],
    output: [F, T, F, F, T, T, T, T, T, T, T, T],
  },
  {
    name: 'greater_than',
    plain: 'Only comes on once you sip or puff harder than a set amount.',
    input: [F, F, T, T, T, T, T, F, F, F, F, F],
    output: [F, F, F, F, T, T, F, F, F, F, F, F],
    note: 'The picture shows pressure rising and falling past the line.',
  },
]

/**
 * Real rows from the fixtures, used as worked examples. Each one was read out of
 * the file named in `source` — see the Stage 3 tests, which check they are still
 * there.
 */
export interface Pattern {
  title: string
  what: string
  rows: { output: string; fn: string; input: string }[]
  source: string
}

export const PATTERNS: Pattern[] = [
  {
    title: 'Three modes for three ways of aiming',
    what:
      'Your Fortnite file has a Left joy mode, a Right joy mode and a D-Pad mode. ' +
      'The same sips do different jobs in each, which is how seven modes cover a ' +
      'whole game.',
    rows: [],
    source: 'ddfortnite.csv, modes 1, 3 and 5',
  },
  {
    title: 'Aim down sights, hands-free',
    what:
      'A puff on the left hole turns aiming on and leaves it on. Another puff turns ' +
      'it off. You are not holding anything while you aim.',
    rows: [{ output: 'left_2', fn: 'toggle', input: 'mp_left_puff' }],
    source: 'ddfortnite.csv, modes 4 to 7',
  },
  {
    title: 'Sprint that stays on',
    what: 'Same trick in Call of Duty: sip on the left and centre holes together to latch sprint.',
    rows: [{ output: 'left_3', fn: 'toggle', input: 'mp_left_center_sip' }],
    source: 'cod.csv, modes 1 to 5',
  },
  {
    title: 'Auto-sprint by pushing the stick',
    what:
      'Pushing the joystick up also clicks the left stick, which is what sprint is ' +
      'on a controller. So moving forward sprints, with no sip at all.',
    rows: [{ output: 'left_3', fn: 'normal', input: 'up' }],
    source: 'ddfortnite.csv, modes 6 and 7',
  },
  {
    title: 'Both stick clicks from one sip',
    what:
      'One sip on the left and centre holes presses both stick clicks at once. Two ' +
      'rows, the same input — the QuadStick does both.',
    rows: [
      { output: 'left_3', fn: 'normal', input: 'mp_left_center_sip' },
      { output: 'right_3', fn: 'normal', input: 'mp_left_center_sip' },
    ],
    source: 'ddfortnite.csv, mode 1',
  },
  {
    title: 'A gentle puff that waits',
    what:
      'A soft left puff clicks the right stick, but only after a moment. A quick ' +
      'puff by accident does nothing.',
    rows: [{ output: 'right_3', fn: 'delay_on', input: 'mp_left_puff_soft' }],
    source: 'ddfortnite.csv, modes 4 to 7',
  },
]
