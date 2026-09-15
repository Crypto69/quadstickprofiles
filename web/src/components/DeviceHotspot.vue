<script setup lang="ts">
/**
 * One clickable part of the device, drawn over the photo. Hovering it washes the
 * part pale green and names it; clicking picks it, which narrows the tables below
 * to that part alone.
 *
 * It is a real <button>, not a div with a click handler, so it is reachable by
 * keyboard and announced as pressable — the editor's rule everywhere else. Keyboard
 * focus shows the same wash as the mouse does, so the two ways of driving it look
 * the same.
 */
import { computed, ref } from 'vue'
import type { Hotspot } from '@/device/layout'

const props = defineProps<{
  spot: Hotspot
  /** True when this part is the one the tables are filtered to. */
  picked: boolean
  /** How many mappings this part carries in the selected mode, for the tooltip. */
  count: number
  /** The profile's own name for the part, if it renamed it (lip -> "Chin switch"). */
  name: string
}>()

/**
 * `pick` narrows the page to this part; `hover` tells the view which part the
 * pointer is over, so the matching section below can be outlined at the same time
 * the part lights up on the photo. Both ends of the link glow together, which is
 * what makes the photo readable as an index of the page rather than a picture.
 */
const emit = defineEmits<{ pick: [part: string]; hover: [part: string | null] }>()

/** Shown on hover and on keyboard focus alike. */
const open = ref(false)

function enter() {
  open.value = true
  emit('hover', props.spot.part)
}

function leave() {
  open.value = false
  emit('hover', null)
}

const mapped = computed(() =>
  props.count === 0
    ? 'Nothing mapped here in this mode.'
    : props.count === 1
      ? '1 thing mapped here in this mode.'
      : `${props.count} things mapped here in this mode.`,
)

/**
 * The accessible name carries what the tooltip says, because a tooltip that only
 * appears on hover reaches nobody using a screen reader.
 */
const described = computed(() => `${props.name}. ${props.spot.hint} ${mapped.value}`)
</script>

<template>
  <button
    type="button"
    class="hotspot"
    :class="{ picked, open }"
    :style="{ left: `${spot.x}%`, top: `${spot.y}%`, '--r': `${spot.r}%` }"
    :aria-label="described"
    :aria-pressed="picked"
    @click="emit('pick', spot.part)"
    @mouseenter="enter"
    @mouseleave="leave"
    @focus="enter"
    @blur="leave"
  >
    <!-- The tooltip is decoration for the mouse; the button's aria-label above
         already says the same thing, so this is hidden from assistive tech rather
         than read out twice. -->
    <span v-if="open" class="tip" aria-hidden="true">
      <b>{{ name }}</b>
      <i>{{ spot.hint }}</i>
      <i>{{ mapped }}</i>
    </span>
  </button>
</template>

<style scoped>
/* Sized from the image width (--r is a percentage of it) and kept round with
   aspect-ratio, because the photo is taller than it is wide: a height percentage
   would draw an ellipse that drifts off the part as the photo scales. */
.hotspot {
  position: absolute;
  width: calc(var(--r) * 2);
  aspect-ratio: 1;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  border: 2px solid transparent;
  background: transparent;
  padding: 0;
  cursor: pointer;
  /* Above the callout labels, which are pointer-events: none anyway, so a label
     lying over a part never blocks the click. */
  z-index: 2;
  transition:
    background-color 120ms ease,
    border-color 120ms ease;
}

/* The pale green wash from the device photo itself — the same green the lip button
   and the left nozzle are moulded in, so the highlight reads as "this part" rather
   than as a UI overlay. */
.hotspot:hover,
.hotspot.open {
  background: color-mix(in srgb, var(--callout) 38%, transparent);
  border-color: color-mix(in srgb, var(--callout-edge) 70%, transparent);
}

/* The picked part stays washed after the pointer leaves, so you can see which part
   the tables below are showing without keeping the mouse on the photo. */
.hotspot.picked {
  background: color-mix(in srgb, var(--callout) 30%, transparent);
  border-color: var(--callout-edge);
  box-shadow: 0 0 0 2px #fff;
}

/* The app's focus ring, on top of the wash, so tabbing to a part is obvious. */
.hotspot:focus-visible {
  outline: var(--focus);
  outline-offset: var(--focus-offset);
}

/* --- the tooltip ---------------------------------------------------------- */
/* Hangs below the part rather than above it: the parts sit in the lower half of
   the photo, and above would cover the neighbours you are about to point at. */
.tip {
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: max-content;
  max-width: 15rem;
  padding: var(--sp-2);
  border-radius: var(--radius);
  border: 1px solid var(--line-strong);
  background: var(--paper);
  box-shadow: 0 2px 10px rgb(0 0 0 / 25%);
  text-align: left;
  white-space: normal;
  line-height: 1.35;
  pointer-events: none;
}
/* The name reads first and largest: "what is this thing" is the question the
   tooltip exists to answer, and the two grey lines under it are the detail. */
.tip b {
  font-size: var(--text-sm);
  color: var(--ink);
}
.tip i {
  font-style: normal;
  font-size: var(--text-xs);
  color: var(--ink-soft);
}
</style>
