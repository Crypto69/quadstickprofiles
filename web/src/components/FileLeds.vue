<script setup lang="ts">
// The five status lights that pick file `n` with the profile switch, lit in the
// firmware's colours, with the same pattern in words for a screen reader. Used by
// the drive list and by the replace dialog's "after" list.
import { computed } from 'vue'
import { MAX_SELECTABLE_FILES, fileLedsFor, ledSentence } from '@/device/layout'

const props = defineProps<{ n: number }>()
const leds = computed(() => fileLedsFor(props.n))
const words = computed(() =>
  props.n <= MAX_SELECTABLE_FILES ? ledSentence(leds.value) : 'the QuadStick cannot pick this file',
)
</script>

<template>
  <span class="leds" :title="words">
    <i v-for="(c, i) in leds" :key="i" :class="[c, { on: c !== 'off' }]" aria-hidden="true" />
    <span class="sr-only">{{ words }}</span>
  </span>
</template>

<style scoped>
/* Same look as the mode rail: a lit dot is filled and ringed, an unlit one is a
   hollow circle. */
.leds {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.leds i {
  width: 16px;
  height: 16px;
  flex: none;
  border-radius: 50%;
  border: 2px solid var(--ink-soft);
  background: #fff;
}
.leds i.on {
  background: var(--led);
  border-color: var(--led);
  box-shadow: 0 0 0 2px var(--paper), 0 0 0 3px var(--led);
}
.leds i.purple {
  --led: var(--led-purple);
}
.leds i.blue {
  --led: var(--led-blue);
}
.leds i.red {
  --led: var(--led-red);
}
</style>
