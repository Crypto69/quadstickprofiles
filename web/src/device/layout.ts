/**
 * Where the callouts sit on the device photos, as data rather than hard-coded CSS,
 * so the positions can be tested and adjusted in one place.
 *
 * Coordinates are percentages of the image box, measured off `images/front.png`
 * and `images/rear.png` (the authority for the jack labels — see docs/hardware.md).
 */
export interface Callout {
  /** Anchor point on the photo, as a percentage of width/height. */
  x: number
  y: number
  /** Which side of the anchor the label sits on, so labels don't cover the device. */
  side: 'left' | 'right' | 'above' | 'below'
  label: string
  /**
   * 'led' draws the dot in the mode blue instead of the default callout green,
   * so the pointer reads as part of the mode display (the mode rail, the mode
   * list on the card) rather than as one more part of the case. The lights
   * themselves are drawn in their own colours by `ledsFor()`.
   */
  marker?: 'led'
}

/** The four sip/puff holes, left to right as you look at the front of the device. */
export interface HoleCallout extends Callout {
  /**
   * The input prefix: mp_left, mp_center, mp_right, or right (the side tube).
   * It doubles as the hole's `PartKey`, so clicking the hole on the photo and
   * reading its column out of this table use one name, not two that can drift.
   */
  prefix: Extract<PartKey, 'mp_left' | 'mp_center' | 'mp_right' | 'right'>
  /** True for the side tube, which is a different gesture from a mouthpiece hole. */
  sideTube: boolean
  /**
   * How far to lift the label above its dot, counted in label heights (rendered as
   * `em`), so labels on neighbouring holes never overlap at any photo size. A
   * leader line joins the label back to its dot.
   */
  lift: number
  /**
   * The full name, used where there is room — the grid heading. `label` is the
   * short form the photo callout uses, because the holes sit close together.
   */
  full: string
}

/**
 * front.png: the mouthpiece bar sits across the middle, four nozzles in a row.
 * Left to right: left hole, centre hole, right hole, then the side tube on its own
 * mount further right. The lip button is the pad below the bar; the joystick is the
 * disc behind it; the five status LEDs run across the top.
 */
export const FRONT_HOLES: HoleCallout[] = [
  // The four nozzles sit in one row, about 10% of the width apart, so their labels
  // would collide if they all sat on the same line. `lift` fans them out vertically,
  // in label-heights, while each dot stays on its own hole and a leader line joins
  // the two. It is measured in rows of text rather than a percentage of the image:
  // the labels are a fixed text size, so a percentage lift shrinks with the photo
  // and the labels collide again on a wide screen. Labels are one word each to stay
  // narrow; the grid below spells out which hole is which anyway.
  //
  // Centre stops at 4, not 5: a fifth step carried it into the status LED row and
  // it covered LED 3, which the mode overlay needs readable. None of the three
  // labels overlap each other horizontally, so dropping one costs nothing.
  { prefix: 'mp_left', label: 'Left', full: 'Left hole', x: 38, y: 57, side: 'above', sideTube: false, lift: 1 },
  { prefix: 'mp_center', label: 'Centre', full: 'Centre hole', x: 48.5, y: 57, side: 'above', sideTube: false, lift: 4 },
  { prefix: 'mp_right', label: 'Right', full: 'Right hole', x: 59, y: 57, side: 'above', sideTube: false, lift: 3 },
  { prefix: 'right', label: 'Side tube', full: 'Side tube', x: 74.5, y: 57, side: 'right', sideTube: true, lift: 0 },
]

/**
 * The other parts worth pointing at. These sit clear of the lifted hole labels,
 * which rise from y≈57 up the centre of the image — hence the joystick label
 * going out to the left rather than straight up.
 */
export const FRONT_PARTS: Callout[] = [
  { label: 'Lip button', x: 49, y: 72, side: 'below' },
  { label: 'Joystick', x: 34, y: 38, side: 'left' },
  // Kept for the `marker: 'led'` contract and the layout tests, but DeviceView
  // filters this one out and draws it inside the image box instead, anchored to
  // FRONT_LEDS[0]. These x/y are figure-space and do not apply there — the whole
  // reason it moved is that figure-space percentages miss the photo entirely.
  { label: 'Status LEDs', x: 66.6, y: 15.7, side: 'below', marker: 'led' },
]

/**
 * Where the five status LEDs sit on front.webp, so the selected mode can be shown
 * lit on the photo the way it would look on the device. Measured off the image:
 * one row, evenly spaced, all at the same height.
 *
 * Index 0 is LED 1, matching `ledsFor()`.
 */
export interface LedSpot {
  /** Centre of the LED, as a percentage of the image box. */
  x: number
  y: number
}

export const FRONT_LEDS: LedSpot[] = [
  { x: 33.4, y: 15.7 },
  { x: 41.8, y: 15.7 },
  { x: 50.1, y: 15.7 },
  { x: 58.4, y: 15.7 },
  { x: 66.6, y: 15.7 },
]

/**
 * rear.png, left column top to bottom: In 7-8, Lip 5-6, In 1-2. On the right,
 * beside the USB-A socket: In 3-4. Note the numbering — the top jack is 7-8,
 * not 3-4, which is the mistake this layout exists to stop repeating.
 */
export interface JackCallout extends Callout {
  /** The digital_in_* numbers this jack carries. */
  inputs: number[]
  /** The text printed on the case. */
  printed: string
}

export const REAR_JACKS: JackCallout[] = [
  { printed: 'In 7-8', inputs: [7, 8], label: 'Top jack', x: 14, y: 30, side: 'left' },
  { printed: 'Lip 5-6', inputs: [5, 6], label: 'Lip jack', x: 14, y: 50, side: 'left' },
  { printed: 'In 1-2', inputs: [1, 2], label: 'Bottom jack', x: 14, y: 70, side: 'left' },
  { printed: 'In 3-4', inputs: [3, 4], label: 'USB-A', x: 87, y: 62, side: 'right' },
]

/**
 * The back photo is clickable the same way the front is: one hit area per jack,
 * sitting on the socket its callout points at. The jacks are ~20% of the height
 * apart down the left edge, so r = 5 keeps them from overlapping.
 */
export const REAR_HOTSPOTS: Hotspot[] = REAR_JACKS.map((j) => ({
  part: jackPart(j),
  x: j.x,
  y: j.y,
  r: 5,
  title: j.printed,
  hint: `${j.label}: switch inputs ${j.inputs.join(' and ')}.`,
}))

/**
 * A jack's part key, named by its lower input number. Every REAR_JACKS entry has
 * inputs, so the 0 fallback is unreachable — it exists so the key is a real
 * PartKey rather than `jack_undefined` for a hand-edited jack with an empty list.
 */
export function jackPart(jack: { inputs: number[] }): PartKey {
  return `jack_${jack.inputs[0] ?? 0}`
}

/**
 * The clickable areas on the front photo. Pointing at a part of the picture and
 * being shown only that part's mappings is the whole point of the device view, so
 * each part gets a real hit area over the photo rather than a decorative dot.
 *
 * Shapes are percentages of the image box, like the callouts. A circle is given a
 * radius in percent of the image *width* (the photo is taller than it is wide, so
 * a single percentage would draw an ellipse); the CSS keeps it round with
 * `aspect-ratio`.
 */
export interface Hotspot {
  /** Which group of inputs this part owns — the key the view filters on. */
  part: PartKey
  /** Centre of the hit area. */
  x: number
  y: number
  /** Circle radius, as a percentage of the image width. */
  r: number
  /** What the tooltip says: the name, then what the part does. */
  title: string
  hint: string
}

/**
 * The parts of the device a mapping can hang off. `lip` and the joystick are single
 * parts; each mouthpiece hole and the side tube are their own part because they are
 * pressed independently and carry four inputs each.
 */
export type PartKey =
  | 'mp_left'
  | 'mp_center'
  | 'mp_right'
  | 'right'
  | 'lip'
  | 'joystick'
  /** A rear jack, named by its lower input number: jack_1, jack_3, jack_5, jack_7. */
  | `jack_${number}`

/**
 * Measured off `images/front.png`, the same image the callouts were measured on, so
 * a hotspot sits under its own callout dot. The three nozzles are about 10% of the
 * width apart, so their radii stop short of touching: r = 4.2 leaves a sliver
 * between neighbours rather than letting one swallow the next.
 */
export const FRONT_HOTSPOTS: Hotspot[] = [
  {
    part: 'mp_left', x: 38, y: 57, r: 4.2,
    title: 'Left hole',
    hint: 'The left hole of the mouthpiece. Sip or puff on it, softly or hard.',
  },
  {
    part: 'mp_center', x: 48.5, y: 57, r: 4.2,
    title: 'Centre hole',
    hint: 'The centre hole of the mouthpiece. Sip or puff on it, softly or hard.',
  },
  {
    part: 'mp_right', x: 59, y: 57, r: 4.2,
    title: 'Right hole',
    hint: 'The right hole of the mouthpiece. Sip or puff on it, softly or hard.',
  },
  {
    part: 'right', x: 74.5, y: 57, r: 4.6,
    title: 'Side tube',
    hint: 'The tube on its own mount to the right. Usually changes mode.',
  },
  {
    part: 'lip', x: 49, y: 72, r: 9,
    title: 'Lip button',
    hint: 'The pad under the mouthpiece. Press it with your lip or chin.',
  },
  {
    part: 'joystick', x: 47, y: 37, r: 13,
    title: 'Joystick',
    hint: 'The disc behind the mouthpiece. Move your head to push it.',
  },
]

/** The four pressure levels, in the order the printed card shows them. */
export const STRENGTHS = [
  { action: 'puff', strength: 'soft', title: 'Soft puff', suffix: '_puff_soft' },
  { action: 'puff', strength: 'hard', title: 'Puff', suffix: '_puff' },
  { action: 'sip', strength: 'hard', title: 'Sip', suffix: '_sip' },
  { action: 'sip', strength: 'soft', title: 'Soft sip', suffix: '_sip_soft' },
] as const

/** The input keyword for a hole at a given pressure, e.g. mp_left + sip -> mp_left_sip. */
export function inputFor(prefix: string, suffix: string) {
  return `${prefix}${suffix}`
}

/**
 * Holes you can sip or puff on together. These are real inputs in the catalog
 * (`mp_left_center_sip` and so on), not a UI invention, so they get their own
 * panel rather than a cell in the four-hole grid.
 */
export const HOLE_COMBOS = [
  { prefix: 'mp_left_center', label: 'Left + Centre' },
  { prefix: 'mp_right_center', label: 'Right + Centre' },
  { prefix: 'mp_left_right', label: 'Left + Right' },
  { prefix: 'mp_triple', label: 'All three' },
] as const

/**
 * What one status LED shows. The colour is part of the firmware's encoding — mode 5
 * and mode 10 both light LED 5 alone, purple for one and blue for the other — so
 * on/off is not enough to tell the user which mode is active. This enum is shared
 * with `render.leds()` in core/qsprofile so the card and the screen say the same.
 */
export type LedColour = 'off' | 'purple' | 'blue' | 'red'

/** The five LEDs, index 0 = LED 1, for a mode number. */
export type LedPattern = LedColour[]

/**
 * Which of the five status LEDs are lit, and in what colour, for a mode number.
 * Straight from the firmware (`update_active_config_leds`):
 *
 *   1–5    LED n purple
 *   6–9    LED 5 purple, plus LED (n − 5) purple — add them up
 *   10     LED 5 blue
 *   11–14  LED 5 blue, plus LED (n − 10) purple — add ten
 *   15     LED 5 red
 *   16     LED 5 red, plus LED 1 purple
 *
 * So LED 5's colour says which round of counting you are in. Past 16 the QuadStick
 * reads no more modes, and every LED is reported off.
 *
 * This mirrors `render.leds()` in core/qsprofile exactly — the printed card and the
 * screen must agree, or the card stops being trustworthy.
 */
export function ledsFor(modeNumber: number): LedPattern {
  const leds: LedPattern = ['off', 'off', 'off', 'off', 'off']
  const n = Math.trunc(modeNumber)
  if (n < 1 || n > 16) return leds
  if (n <= 5) {
    leds[n - 1] = 'purple'
  } else if (n <= 9) {
    leds[4] = 'purple'
    leds[n - 6] = 'purple'
  } else if (n <= 14) {
    leds[4] = 'blue'
    if (n > 10) leds[n - 11] = 'purple'
  } else {
    leds[4] = 'red'
    if (n === 16) leds[0] = 'purple'
  }
  return leds
}

/**
 * The pattern in words — "LED 5 blue", "LED 2 purple and LED 5 blue" — for people who
 * cannot tell the colours apart on screen, and for the caption under the photo.
 */
export function ledSentence(leds: LedPattern): string {
  const lit = leds.flatMap((c, i) => (c === 'off' ? [] : [`LED ${i + 1} ${c}`]))
  return lit.length ? lit.join(' and ') : 'no LED'
}

/**
 * Two modes whose LED patterns are identical cannot be told apart on the device.
 * Now that colour is modelled there is no such pair among modes 1–16 — mode 10 is
 * LED 5 blue where mode 5 is LED 5 purple — so for the current firmware table this
 * is unreachable. It stays because the lights are the only feedback about which
 * mode is active, and a future firmware table may collide again.
 */
export function ledPatternClashes(modeNumber: number, total: number): number[] {
  const mine = ledsFor(modeNumber).join()
  const out: number[] = []
  for (let n = 1; n <= total; n++) {
    if (n !== modeNumber && ledsFor(n).join() === mine) out.push(n)
  }
  return out
}
