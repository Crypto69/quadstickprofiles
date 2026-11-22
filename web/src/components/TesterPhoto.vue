<script setup lang="ts">
/**
 * The front photo with the tester's live overlay: the mode LEDs lit by the
 * firmware's rule, each tube lit blue-green for a sip and orange for a puff (pale
 * for gentle), the lip button, and a dot for the joystick. A yellow ring marks
 * what the guided test asks for next.
 *
 * Positions come from device/layout.ts, the same measurements the editor's photo
 * uses, so the two photos agree. The overlay is an SVG in the photo's own pixel
 * space, so it scales with the image.
 */
import { computed } from 'vue'
import frontPhoto from '@/assets/front.webp'
import { FRONT_HOLES, FRONT_LEDS, ledsFor } from '@/device/layout'
import type { Stick, TesterInput, Tube } from '@/tester/decode'

const props = defineProps<{
  /** The mode the device is in, when the qstest marker says. */
  mode: number | null
  /** What each tube is doing right now (a mode-change flash on the side tube included). */
  lit: Partial<Record<Tube, Pick<TesterInput, 'action' | 'level'>>>
  stick: Stick | null
  /** The guided test's next ask: an input to ring, or the LEDs of a mode to reach. */
  target: { input: TesterInput } | { mode: number } | null
}>()

// front.webp is 1000 × 866; layout.ts measures in percent of that box.
const W = 1000
const H = 866
const px = (pct: number) => (pct * W) / 100
const py = (pct: number) => (pct * H) / 100

const TUBE_OF: Record<string, Tube> = {
  mp_left: 'left',
  mp_center: 'center',
  mp_right: 'right',
  right: 'side',
}
const TUBE_LABEL: Record<Tube, string> = {
  left: 'left',
  center: 'centre',
  right: 'right',
  side: 'side tube',
  lip: 'lip',
}
const TUBE_R = 34
/** How far above its tube the action label sits. The centre one sits higher so a
 *  combination (left + centre, both lit) does not print one label over the other. */
const actLift = (t: Tube) => (t === 'center' ? 108 : 76)

const tubes = FRONT_HOLES.map((h) => ({
  tube: TUBE_OF[h.prefix] as Tube,
  x: px(h.x),
  y: py(h.y),
}))

/** The lip pad and the joystick dial, measured off the same photo (dronecontrol's
 *  tester, 1348 × 1167 pixels there, in percent here). */
const LIP = { x: px(40.06), y: py(62.21), w: px(7.12), h: py(7.88) }
const DIAL = { x: px(49.55), y: py(46.27), r: px(11.13) }

const leds = computed(() => ledsFor(props.mode ?? 0))
const ledTargets = computed(() =>
  props.target && 'mode' in props.target ? ledsFor(props.target.mode) : null,
)

/** The tubes (and lip) the guided test is asking for. */
const aimed = computed<Set<Tube>>(() => {
  const t = props.target
  if (!t) return new Set()
  if ('mode' in t) return new Set<Tube>(['side'])
  return new Set(t.input.tubes)
})

/** What to write above a tube: what it is doing, else what to do with it. */
function actText(t: Tube): { text: string; cls: string } | null {
  const a = props.lit[t]
  if (a) {
    const text = a.action === 'press' ? 'PRESSED' : `${a.level === 'gentle' ? 'gentle ' : ''}${a.action}`
    return { text: text.toUpperCase(), cls: a.action }
  }
  const tg = props.target
  if (!tg || !aimed.value.has(t)) return null
  if ('mode' in tg) return { text: 'SIP ▸ / PUFF ◂', cls: 'aim' }
  const i = tg.input
  if (i.action === 'press') return { text: 'PRESS', cls: 'aim' }
  return { text: `${i.level === 'gentle' ? 'gentle ' : ''}${i.action}`.toUpperCase(), cls: 'aim' }
}

function tubeClass(t: Tube) {
  const a = props.lit[t]
  return [
    'tube',
    a && a.action,
    a && a.level === 'gentle' && 'soft',
    aimed.value.has(t) && !a && 'aim',
  ]
}

const dot = computed(() => {
  const s = props.stick
  return { x: DIAL.x + (s?.x ?? 0) * DIAL.r, y: DIAL.y - (s?.y ?? 0) * DIAL.r }
})
</script>

<template>
  <svg class="photo" :viewBox="`0 0 ${W} ${H}`" aria-hidden="true" focusable="false">
    <image :href="frontPhoto" x="0" y="0" :width="W" :height="H" />

    <g class="leds">
      <template v-for="(spot, i) in FRONT_LEDS" :key="i">
        <circle
          v-if="ledTargets && ledTargets[i] !== 'off'"
          class="led-aim"
          :cx="px(spot.x)"
          :cy="py(spot.y)"
          r="20"
        />
        <circle
          :class="['led', leds[i]]"
          :cx="px(spot.x)"
          :cy="py(spot.y)"
          r="11"
        />
        <text class="lednum" :x="px(spot.x)" :y="py(spot.y) - 26">{{ i + 1 }}</text>
      </template>
    </g>

    <g class="dial">
      <circle :cx="DIAL.x" :cy="DIAL.y" :r="DIAL.r" class="dial-ring" />
      <circle :cx="DIAL.x" :cy="DIAL.y" r="5" class="dial-centre" />
      <circle :cx="dot.x" :cy="dot.y" r="13" class="stick-dot" />
    </g>

    <g v-for="t in tubes" :key="t.tube">
      <circle :class="tubeClass(t.tube)" :cx="t.x" :cy="t.y" :r="TUBE_R" />
      <text class="partlabel" :x="t.x" :y="t.y - 46">{{ TUBE_LABEL[t.tube] }}</text>
      <text
        v-if="actText(t.tube)"
        :class="['actlabel', actText(t.tube)?.cls]"
        :x="t.x"
        :y="t.y - actLift(t.tube)"
      >
        {{ actText(t.tube)?.text }}
      </text>
    </g>

    <rect
      :class="['lip', lit.lip && 'on', aimed.has('lip') && !lit.lip && 'aim']"
      :x="LIP.x"
      :y="LIP.y"
      :width="LIP.w"
      :height="LIP.h"
      rx="8"
    />
    <text class="partlabel" :x="LIP.x + LIP.w / 2" :y="LIP.y + LIP.h / 2 + 8">lip</text>
    <text
      v-if="actText('lip')"
      :class="['actlabel', actText('lip')?.cls]"
      :x="LIP.x + LIP.w / 2"
      :y="LIP.y + LIP.h + 34"
    >
      {{ actText('lip')?.text }}
    </text>
  </svg>
</template>

<style scoped>
/* Brighter than the app's --sip / --puff: these sit on a black device, where the
   print colours disappear. Same hues, so the meaning carries over. */
.photo {
  --sip-glow: #2fc3d3;
  --puff-glow: #ff8a3a;
  --aim: #ffd23a;
  display: block;
  width: 100%;
  height: auto;
}

.led {
  fill: transparent;
  stroke: rgb(255 255 255 / 35%);
  stroke-width: 2;
}
.led.purple {
  fill: var(--led-purple);
  stroke: #e2c8ff;
  stroke-width: 4;
}
.led.blue {
  fill: var(--led-blue);
  stroke: #c9d6ff;
  stroke-width: 4;
}
.led.red {
  fill: var(--error);
  stroke: #ffc9c5;
  stroke-width: 4;
}
.led-aim {
  fill: none;
  stroke: var(--aim);
  stroke-width: 5;
  animation: pulse 1s ease-in-out infinite;
}
.lednum {
  fill: #fff;
  font-size: 20px;
  font-weight: 700;
  text-anchor: middle;
  paint-order: stroke;
  stroke: #000;
  stroke-width: 5px;
}

.dial-ring {
  fill: none;
  stroke: rgb(255 255 255 / 25%);
  stroke-width: 2;
  stroke-dasharray: 6 8;
}
.dial-centre {
  fill: rgb(255 255 255 / 50%);
}
.stick-dot {
  fill: var(--aim);
  stroke: #000;
  stroke-width: 3;
}

.tube {
  fill: transparent;
  stroke: transparent;
  stroke-width: 8;
}
.tube.sip {
  fill: var(--sip-glow);
  fill-opacity: 0.85;
  stroke: var(--sip-glow);
}
.tube.puff {
  fill: var(--puff-glow);
  fill-opacity: 0.85;
  stroke: var(--puff-glow);
}
.tube.soft {
  fill-opacity: 0.35;
}
.tube.aim,
.lip.aim {
  stroke: var(--aim);
  stroke-width: 9;
  animation: pulse 1s ease-in-out infinite;
}

.lip {
  fill: transparent;
  stroke: transparent;
  stroke-width: 6;
}
.lip.on {
  fill: var(--aim);
  fill-opacity: 0.55;
  stroke: var(--aim);
}

.partlabel,
.actlabel {
  text-anchor: middle;
  paint-order: stroke;
  stroke: #000;
}
.partlabel {
  fill: #fff;
  font-size: 20px;
  font-weight: 700;
  stroke-width: 5px;
}
.actlabel {
  font-size: 26px;
  font-weight: 800;
  stroke-width: 6px;
}
.actlabel.sip {
  fill: var(--sip-glow);
}
.actlabel.puff {
  fill: var(--puff-glow);
}
.actlabel.press,
.actlabel.aim {
  fill: var(--aim);
}

@keyframes pulse {
  50% {
    stroke-opacity: 0.25;
  }
}
</style>
