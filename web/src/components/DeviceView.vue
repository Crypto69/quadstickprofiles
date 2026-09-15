<script setup lang="ts">
/**
 * The hero of the editor: the device as the owner sees it. A photo with callouts that
 * point at the real parts, then the four-hole pressure grid, the hole combos, the
 * joystick, the lip button and the switch jacks — every one a slot you click once
 * to edit. Empty slots are visibly free.
 */
import { computed, ref } from 'vue'
import DeviceHotspot from './DeviceHotspot.vue'
import InputSlot from './InputSlot.vue'
import frontPhoto from '@/assets/front.webp'
import rearPhoto from '@/assets/rear.webp'
import {
  FRONT_HOLES, FRONT_HOTSPOTS, FRONT_LEDS, FRONT_PARTS, HOLE_COMBOS, REAR_HOTSPOTS,
  REAR_JACKS, STRENGTHS, inputFor, jackPart, ledSentence as ledWords, ledsFor,
} from '@/device/layout'
import type { PartKey } from '@/device/layout'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'

const props = defineProps<{ selectedInput: string | null }>()
const emit = defineEmits<{
  select: [input: string]
  /**
   * Every input the hovered part owns, so the editor can ring its own pane when
   * the input it is showing belongs to the part being pointed at. Empty on leave.
   */
  hover: [inputs: string[]]
}>()

const catalog = useCatalogStore()
const docStore = useDocumentStore()

const consoleName = computed(() => docStore.doc?.console ?? 'playstation')

function slotFor(input: string) {
  return {
    input,
    label: docStore.inputName(input, catalog.inputLabel(input)),
    mappings: docStore.mappingsForInput(input),
    selected: props.selectedInput === input,
  }
}

/**
 * Only show a combo column once something uses it, to keep the grid calm — and,
 * when a hole is picked on the photo, only the combos that hole takes part in.
 */
const usedCombos = computed(() =>
  HOLE_COMBOS.filter(
    (c) =>
      STRENGTHS.some((s) => docStore.mappingsForInput(inputFor(c.prefix, s.suffix)).length > 0) &&
      (pickedPart.value === null || comboUses(c.prefix, pickedPart.value)),
  ),
)

const joystickInputs = computed(() => catalog.catalog?.joystick_directions ?? [])
const joystickZones = computed(() => catalog.catalog?.joystick_zones ?? [])

/** Which joystick inputs this mode actually drives. */
const usedJoystick = computed(() =>
  [...joystickInputs.value, ...joystickZones.value].filter(
    (d) => docStore.mappingsForInput(d).length > 0 || docStore.mappingsForInput(`${d}_inner`).length > 0,
  ),
)

const lipInputs = ['lip', 'lip_soft']

/* --- pointing at the picture ---------------------------------------------- */
/**
 * Which part of the device the photo is pointed at, or null for "show everything".
 * Picking a part narrows the tables below to that part alone, which is the point:
 * the four-hole grid plus the jacks plus the joystick is a lot to read when you
 * only want to know what the lip button does.
 *
 * Clicking the picked part again clears it, so there is always a way back to the
 * whole device without hunting for a reset control.
 */
const pickedPart = ref<PartKey | null>(null)

/**
 * The part the pointer (or keyboard focus) is over right now. It lights the part on
 * the photo *and* outlines the section below that the part owns, so the picture
 * reads as an index of the page: point at a thing, see where its mappings are.
 * Hovering never changes what is on screen, only what is outlined.
 */
const hoveredPart = ref<PartKey | null>(null)

function pickPart(part: string) {
  pickedPart.value = pickedPart.value === part ? null : (part as PartKey)
}

function hoverPart(part: string | null) {
  hoveredPart.value = part as PartKey | null
  emit('hover', hoveredPart.value ? inputsOfPart(hoveredPart.value) : [])
}

/** True when a section is the one being pointed at, so it gets the green outline. */
function lit(...parts: PartKey[]) {
  return hoveredPart.value !== null && parts.includes(hoveredPart.value)
}

/** A combo column lights for any hole that takes part in it. */
function litCombo(comboPrefix: string) {
  return hoveredPart.value !== null && comboUses(comboPrefix, hoveredPart.value)
}

/** Every input a part owns, so a hotspot can count what is mapped to the whole part. */
function inputsOfPart(part: PartKey): string[] {
  if (part === 'lip') return lipInputs
  if (part === 'joystick') {
    return [...joystickInputs.value, ...joystickZones.value].flatMap((d) => [d, `${d}_inner`])
  }
  const jack = /^jack_(\d)$/.exec(part)
  if (jack) {
    const first = Number(jack[1])
    return [`digital_in_${first}`, `digital_in_${first + 1}`]
  }
  // a mouthpiece hole or the side tube: its four pressures, plus (for the holes)
  // every combo it takes part in, since those live on the same nozzle
  const own = STRENGTHS.map((s) => inputFor(part, s.suffix))
  const combos = HOLE_COMBOS.filter((c) => comboUses(c.prefix, part)).flatMap((c) =>
    STRENGTHS.map((s) => inputFor(c.prefix, s.suffix)),
  )
  return [...own, ...combos]
}

/** Does a combo prefix (mp_left_center, mp_triple) involve this hole? */
function comboUses(comboPrefix: string, part: PartKey) {
  if (comboPrefix === 'mp_triple') return part.startsWith('mp_')
  // mp_left_center -> left, center; a hole is mp_left -> left
  return comboPrefix.slice(3).split('_').includes(part.slice(3))
}

function countForPart(part: PartKey) {
  return inputsOfPart(part).reduce((n, i) => n + docStore.mappingsForInput(i).length, 0)
}

/** The profile's own name for a part, so a renamed lip button reads right on the photo. */
function partName(spot: { part: PartKey; title: string }) {
  return spot.part === 'lip' ? docStore.inputName('lip', spot.title) : spot.title
}

/** True when a section should be on screen: nothing picked, or this part is it. */
function showing(...parts: PartKey[]) {
  return pickedPart.value === null || parts.includes(pickedPart.value)
}

/** The hole columns to draw — all of them, or just the picked one. */
const shownHoles = computed(() =>
  FRONT_HOLES.filter((h) => showing(h.prefix as PartKey)),
)

const pickedName = computed(() => {
  const spot = [...FRONT_HOTSPOTS, ...REAR_HOTSPOTS].find((s) => s.part === pickedPart.value)
  return spot ? partName(spot) : ''
})

const shownJacks = computed(() => REAR_JACKS.filter((j) => showing(jackPart(j))))

/**
 * Which status LEDs the selected mode would light on the real device, and in what
 * colour. Shown on the photo so picking a mode in the rail tells you what you would
 * see on the device, which is the only feedback it gives about which mode is active.
 */
const litLeds = computed(() => {
  const n = docStore.selectedModeNumber
  return n ? ledsFor(n) : ledsFor(0)
})

const selectedModeName = computed(() => docStore.selectedMode?.name ?? '')

/**
 * The colour for the "Status LEDs" dot: whatever the lights are actually showing.
 * A fixed blue dot read as "the LEDs are blue" while every lit light beside it was
 * purple.
 *
 * Where the pattern mixes colours — modes 11–14 light LED 5 blue and one other
 * purple — the dot takes LED 5's, because that is the one the firmware uses to say
 * which round of counting you are in. With nothing lit it stays purple, the colour
 * modes 1–9 use and the first any row would light.
 */
const ledDotColour = computed(() => {
  const leds = litLeds.value
  const led5 = leds[4]
  const colour = led5 && led5 !== 'off' ? led5 : leds.find((c) => c !== 'off')
  return `var(--led-${colour ?? 'purple'})`
})

/** "LED 1 purple", or "LED 2 purple and LED 5 blue", for the caption under the photo. */
const ledSentence = computed(() => ledWords(litLeds.value))

/** The LED label is drawn with the LEDs themselves, in image coordinates. */
const otherParts = computed(() => FRONT_PARTS.filter((p) => p.marker !== 'led'))

/**
 * Where the "Status LEDs" callout hangs. Anchored clear to the left of LED 1 rather
 * than on it: sitting on the row, its own dot covered the first light, which is the
 * one the overlay needs visible for mode 1.
 */
const LED_LABEL = { x: 27, y: 15.7 }

/** A jack's inputs, but only the ones a profile can bind (1–8). */
function jackSlots(inputs: number[]) {
  return inputs.map((n) => `digital_in_${n}`)
}
</script>

<template>
  <div class="device">
    <!-- The photo is tall and narrow; the tables are wide and short. Side by side
         they fill the pane instead of leaving a column of dead space beside the
         device and pushing every mapping below the fold. -->
    <div class="device-split">
    <!-- the photo, with callouts anchored as percentages (src/device/layout.ts) -->
    <figure class="photo">
      <!-- The LEDs are positioned against the image, not the figure: the figure
           carries 9.5em of padding-top for the lifted callout labels, so a percentage
           measured off it lands well above the photo. The callouts stay on the figure
           because their percentages were tuned against that padded box. -->
      <div class="shot">
        <img :src="frontPhoto" alt="The front of the QuadStick: mouthpiece, side tube, lip button and joystick" />
        <span
          v-for="(led, i) in FRONT_LEDS"
          :key="`led-${i}`"
          class="led"
          :class="[litLeds[i], { lit: litLeds[i] !== 'off' }]"
          :style="{ left: `${led.x}%`, top: `${led.y}%` }"
          aria-hidden="true"
        />
        <!-- This one lives with the LEDs rather than with the other callouts, so it
             shares their coordinate space. Pointing it at the lights from the padded
             figure box is what put it above the photo in the first place.

             It hangs out to the left of the row, clear of LED 1: the right end runs
             into the case edge, below the row it collided with the Centre hole's
             lifted label, and anchored on LED 1 its own dot covered that light. -->
        <span
          class="callout callout--part callout--led side-left"
          :style="{
            left: `${LED_LABEL.x}%`,
            top: `${LED_LABEL.y}%`,
            '--led-now': ledDotColour,
          }"
        >
          <i aria-hidden="true" />
          <b>Status LEDs</b>
        </span>
        <!-- The parts themselves, clickable. They go last so they sit over the
             callout labels; the labels take no pointer events, so nothing under a
             label is unreachable. -->
        <DeviceHotspot
          v-for="s in FRONT_HOTSPOTS"
          :key="s.part"
          :spot="s"
          :name="partName(s)"
          :count="countForPart(s.part)"
          :picked="pickedPart === s.part"
          @pick="pickPart"
          @hover="hoverPart"
        />
      </div>
      <span
        v-for="h in FRONT_HOLES"
        :key="h.prefix"
        class="callout"
        :class="[`side-${h.side}`, { lifted: h.lift > 0 }]"
        :style="{ left: `${h.x}%`, top: `${h.y}%`, '--lift': `${h.lift * 1.6}em` }"
      >
        <i aria-hidden="true" />
        <b>{{ h.label }}</b>
      </span>
      <span
        v-for="p in otherParts"
        :key="p.label"
        class="callout callout--part"
        :class="[`side-${p.side}`, p.marker === 'led' && 'callout--led']"
        :style="{ left: `${p.x}%`, top: `${p.y}%` }"
      >
        <i aria-hidden="true" />
        <b>{{ p.label === 'Lip button' ? docStore.inputName('lip', 'Lip button') : p.label }}</b>
      </span>
      <figcaption>
        <span v-if="selectedModeName" class="led-key">
          In <b>{{ selectedModeName }}</b> the QuadStick lights {{ ledSentence }}.
        </span>
        Click a part of the picture to see only what it does.
        Sip means draw air in; puff means blow out. A soft one is gentle — the QuadStick
        beeps. A hard one is firm — it clicks.
      </figcaption>
    </figure>

    <div class="maps">
    <!-- what the photo is pointed at, and the way back to the whole device ---- -->
    <p v-if="pickedPart" class="picked-bar">
      <span>Showing only <b>{{ pickedName }}</b>.</span>
      <button type="button" class="link" @click="pickedPart = null">Show the whole device</button>
    </p>

    <!-- the four holes at four pressures ------------------------------------- -->
    <section v-if="shownHoles.length">
      <h3>Mouthpiece and side tube</h3>
      <div class="grid-scroll">
      <table class="grid" :class="{ narrow: shownHoles.length < FRONT_HOLES.length }">
        <thead>
          <tr>
            <th class="corner"><span class="sr-only">Pressure</span></th>
            <!-- A hole owns a column, not the whole table, so pointing at one on
                 the photo lights its column and leaves its neighbours alone. -->
            <th v-for="h in shownHoles" :key="h.prefix" :class="{ tube: h.sideTube, lit: lit(h.prefix) }">
              {{ h.full }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in STRENGTHS" :key="s.title" :class="[s.action, s.strength]">
            <th scope="row">{{ s.title }}</th>
            <td v-for="h in shownHoles" :key="h.prefix" :class="{ lit: lit(h.prefix) }">
              <InputSlot
                v-bind="slotFor(inputFor(h.prefix, s.suffix))"
                :console-name="consoleName"
                :tone="s.action"
                @select="emit('select', $event)"
              />
            </td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    <!-- holes used together -------------------------------------------------- -->
    <section v-if="usedCombos.length">
      <h3>Two or three holes together</h3>
      <div class="grid-scroll">
      <table class="grid">
        <thead>
          <tr>
            <th class="corner"><span class="sr-only">Pressure</span></th>
            <!-- A combo belongs to every hole in it, so pointing at the left hole
                 lights "Left + Centre" and "All three" as well as its own column. -->
            <th v-for="c in usedCombos" :key="c.prefix" :class="{ lit: litCombo(c.prefix) }">
              {{ c.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in STRENGTHS" :key="s.title" :class="[s.action, s.strength]">
            <th scope="row">{{ s.title }}</th>
            <td v-for="c in usedCombos" :key="c.prefix" :class="{ lit: litCombo(c.prefix) }">
              <InputSlot
                v-bind="slotFor(inputFor(c.prefix, s.suffix))"
                :console-name="consoleName"
                :tone="s.action"
                @select="emit('select', $event)"
              />
            </td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    </div><!-- /maps -->
    </div><!-- /device-split -->

    <div class="cols" :class="{ single: pickedPart !== null }">
      <!-- lip -------------------------------------------------------------- -->
      <section v-if="showing('lip')" :class="{ lit: lit('lip') }">
        <h3>{{ docStore.inputName('lip', 'Lip button') }}</h3>
        <div class="stack-slots">
          <InputSlot
            v-for="i in lipInputs"
            :key="i"
            v-bind="slotFor(i)"
            :console-name="consoleName"
            @select="emit('select', $event)"
          />
        </div>
      </section>

      <!-- joystick --------------------------------------------------------- -->
      <section v-if="showing('joystick')" :class="{ lit: lit('joystick') }">
        <h3>Joystick</h3>
        <div class="stack-slots">
          <InputSlot
            v-for="d in usedJoystick.length ? usedJoystick : joystickInputs"
            :key="d"
            v-bind="slotFor(d)"
            :console-name="consoleName"
            @select="emit('select', $event)"
          />
        </div>
        <p v-if="!usedJoystick.length" class="hint">
          Nothing on the joystick in this mode — it does nothing here.
        </p>
      </section>
    </div>

    <!-- switch jacks, on the back ------------------------------------------- -->
    <section v-if="shownJacks.length">
      <h3>Switch jacks</h3>
      <figure class="photo photo--rear">
        <img :src="rearPhoto" alt="The back of the QuadStick, showing the In 7-8, Lip 5-6, In 1-2 and In 3-4 jacks" />
        <span
          v-for="j in REAR_JACKS"
          :key="j.printed"
          class="callout"
          :class="`side-${j.side}`"
          :style="{ left: `${j.x}%`, top: `${j.y}%` }"
        >
          <i aria-hidden="true" />
          <b>{{ j.printed }}</b>
        </span>
        <DeviceHotspot
          v-for="s in REAR_HOTSPOTS"
          :key="s.part"
          :spot="s"
          :name="s.title"
          :count="countForPart(s.part)"
          :picked="pickedPart === s.part"
          @pick="pickPart"
          @hover="hoverPart"
        />
      </figure>
      <div class="jacks">
        <div v-for="j in shownJacks" :key="j.printed" class="jack" :class="{ lit: lit(jackPart(j)) }">
          <h4>
            {{ j.printed }}
            <small>{{ j.label }}</small>
          </h4>
          <InputSlot
            v-for="i in jackSlots(j.inputs)"
            :key="i"
            v-bind="slotFor(i)"
            :console-name="consoleName"
            @select="emit('select', $event)"
          />
        </div>
      </div>
      <p class="hint">
        The numbering follows what is printed on the case: the top jack is
        <b>7–8</b>, not 3–4.
      </p>
    </section>
  </div>
</template>

<style scoped>
.device {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  /* A flex item's default min-width is its content, so the 460px-min grid below
     would stretch this column and push the whole page sideways. min-width: 0 lets
     the grid's own scroll box do its job instead. */
  min-width: 0;
}
.device > section {
  min-width: 0;
}

h3 {
  font-size: var(--text-base);
  margin: 0 0 var(--sp-2);
}
h4 {
  margin: 0 0 var(--sp-1);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
}
h4 small {
  font-family: var(--font);
  font-weight: 400;
  color: var(--ink-soft);
  margin-left: var(--sp-1);
}

/* --- photo beside the tables ----------------------------------------------- */
/* A container query, not a media query: this component sits inside the editor's
   middle column, so the viewport width says nothing about the room it has. */
.device {
  container-type: inline-size;
}
.device-split {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-4);
  align-items: start;
}
.maps {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  min-width: 0;
}
/* The photo wants ~560px and a grid wants ~430px, so they only pair up once both
   fit; below that they stack as before. */
@container (min-width: 1020px) {
  .device-split {
    /* The photo column is sized to the photo, not stretched: at 1fr it left a
       tall empty strip under the picture. */
    grid-template-columns: 560px minmax(430px, 1fr);
  }
  .device-split > .photo {
    margin-bottom: 0;
  }
}

/* --- photo with callouts --------------------------------------------------- */
.photo {
  position: relative;
  margin: 0 0 var(--sp-4);
  max-width: 560px;
  /* room for the tallest lifted callout (5 label heights) plus the label itself */
  padding-top: 9.5em;
}
.photo--rear {
  max-width: 640px;
  padding-top: 0;
}
.photo img {
  display: block;
  width: 100%;
  height: auto;
}
.photo figcaption {
  margin-top: var(--sp-2);
  font-size: var(--text-xs);
  color: var(--ink-soft);
}

/* The image and its LED overlay, without the figure's callout padding.
   line-height: 0 kills the inline gap under the img, but it would also collapse
   the callout label inside here to nothing — hence the reset on .shot .callout. */
.shot {
  position: relative;
  line-height: 0;
}
.shot .callout {
  line-height: normal;
}

/* --- the status LEDs, lit for the selected mode ---------------------------- */
/* Sized in percent of the photo width so the dot tracks the LED at any photo size;
   an em or px size would drift off the light as the image scales. */
.led {
  position: absolute;
  width: 3.4%;
  aspect-ratio: 1;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  /* unlit ones stay a faint ring so you can see there are five of them */
  border: 1px solid rgb(255 255 255 / 35%);
  transition: background-color 120ms ease, box-shadow 120ms ease;
}
.led.lit {
  background: color-mix(in srgb, var(--led) 70%, transparent);
  border-color: var(--led);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--led) 45%, transparent);
}
/* The firmware's colours: purple for modes 1–9, LED 5 blue for 10–14, red for
   15–16. The colour is part of the count, so it is drawn, not just "on". */
.led.purple {
  --led: var(--led-purple);
}
.led.blue {
  --led: var(--led-blue);
}
.led.red {
  --led: var(--led-red);
}
/* Some people cannot tell the lit colours from each other or from the unlit ring,
   so the caption says in words which LEDs are lit, and in what colour. */
.led-key {
  display: block;
  color: var(--ink);
}

.callout {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 4px;
  transform: translate(-50%, -50%);
  pointer-events: none;
  white-space: nowrap;
}
.callout i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--callout);
  /* a dark ring as well as the white one, so the dot reads on the pale page
     background and on the black device alike */
  box-shadow:
    0 0 0 2px #fff,
    0 0 0 3px var(--callout-edge);
  flex: none;
}
.callout b {
  padding: 1px 5px;
  border-radius: 3px;
  background: rgb(255 255 255 / 92%);
  border: 1px solid var(--callout-edge);
  font-size: var(--text-xs);
}
.callout--part i {
  background: var(--callout);
}
/* The dot takes the colour the lights themselves are showing, so the label is a
   key to the row it points at. It used to be the app's mode blue, which read as
   "the LEDs are blue" while every light beside it was purple. --led-now is set on
   the element from the lit pattern; it falls back to purple, the colour of modes
   1–9 and the one an unlit row would light first. */
.callout--led i {
  background: var(--led-now, var(--led-purple));
}
.callout--led b {
  border-color: var(--led-now, var(--led-purple));
}
/* keep the label off the device itself */
.callout.side-left {
  flex-direction: row-reverse;
  transform: translate(-100%, -50%);
}
.callout.side-right {
  transform: translate(0, -50%);
}
.callout.side-above {
  flex-direction: column-reverse;
  transform: translate(-50%, -100%);
}
.callout.side-below {
  flex-direction: column;
  transform: translate(-50%, 0);
}

/* Neighbouring holes are ~10% of the width apart, so their labels would overlap.
   A lifted label rises by --lift with a leader line back down to its own dot. */
.callout.lifted {
  transform: translate(-50%, calc(-100% - var(--lift)));
}
.callout.lifted::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  width: 2px;
  height: var(--lift);
  background: var(--callout);
}

/* --- pointing at the photo lights the matching mappings -------------------- */
/* The other half of the link: the part washes green on the photo, and whatever
   holds its mappings down here is ringed in the same green at the same moment. It
   is what makes the picture an index of the page rather than an illustration.
   Outline rather than border, so nothing shifts by a pixel as it lights. */
.device section.lit,
.device .jack.lit {
  outline: 3px solid var(--callout-edge);
  outline-offset: 4px;
  border-radius: var(--radius);
}
/* A hole owns one column, so the cells light rather than the whole table. */
.grid th.lit,
.grid td.lit {
  background: color-mix(in srgb, var(--callout) 22%, var(--paper));
}
/* Beats the .soft row's sunk background and the side tube's blue heading, which
   would otherwise win on specificity and leave the lit column half-coloured. */
.grid tr.soft td.lit,
.grid thead th.tube.lit {
  background: color-mix(in srgb, var(--callout) 22%, var(--paper));
}

/* --- the pressure grid ---------------------------------------------------- */
.grid {
  border-collapse: collapse;
  width: 100%;
  table-layout: fixed;
}
.grid th,
.grid td {
  border: 1px solid var(--line);
  padding: 3px;
  vertical-align: top;
  /* chips wrap rather than being clipped by a narrow column */
  overflow-wrap: anywhere;
}
.grid thead th {
  background: var(--paper-sunk);
  font-size: var(--text-xs);
}
.grid thead th.tube {
  background: var(--mode-soft);
}
.grid tbody th {
  width: 5.5rem;
  text-align: left;
  font-size: var(--text-xs);
}
.grid tr.sip th {
  color: var(--sip);
}
.grid tr.puff th {
  color: var(--puff);
}
.grid tr.soft td {
  background: var(--paper-sunk);
}
.corner {
  background: transparent !important;
}

.cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-4);
  align-items: start;
}
/* With a part picked at most one of these two sections is on screen, so a
   two-column grid would leave the survivor stranded in a half-width column. */
.cols.single {
  grid-template-columns: 1fr;
}

/* --- the "showing only X" bar --------------------------------------------- */
/* Says what the photo narrowed the page to, and carries the way back, so picking a
   part is never a one-way door. */
.picked-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3);
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--callout-edge);
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--callout) 18%, var(--paper));
  font-size: var(--text-sm);
}
.picked-bar .link {
  min-height: var(--target);
  padding: 0 var(--sp-2);
  border: 0;
  background: none;
  color: var(--mode);
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}
.picked-bar .link:focus-visible {
  outline: var(--focus);
  outline-offset: var(--focus-offset);
}

.stack-slots {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.jacks {
  display: grid;
  /* minmax(0, …) so a narrow screen shrinks the columns instead of overflowing */
  grid-template-columns: repeat(auto-fit, minmax(min(150px, 100%), 1fr));
  gap: var(--sp-3);
  margin-top: var(--sp-3);
}
.jack {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

/* The grid cannot usefully squeeze below about 460px, so it scrolls inside its own
   box rather than pushing the whole page sideways. */
.grid-scroll {
  overflow-x: auto;
  max-width: 100%;
}
/* Four slot columns need ~100px each to hold a chip, plus the pressure heading.
   Below that the grid scrolls inside its own box rather than squeezing unreadably. */
.grid {
  min-width: 430px;
}
/* One hole picked on the photo means one slot column, which does not need the
   four-column floor — without this it stretches a single slot across 430px. */
.grid.narrow {
  min-width: 0;
  max-width: 22rem;
}
.grid tbody th {
  width: 4.5rem;
}

@media (max-width: 720px) {
  .cols {
    grid-template-columns: 1fr;
  }
}
</style>
