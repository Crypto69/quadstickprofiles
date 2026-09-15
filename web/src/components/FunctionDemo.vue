<script setup lang="ts">
/**
 * A small picture of one output function: what you do on top, what the console
 * sees underneath, running on a loop. Under reduced motion it stops moving and
 * shows the whole pattern as a static chart instead — which is arguably clearer,
 * so nothing is lost.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { FunctionDemo } from '@/learn/topics'

const props = withDefaults(
  defineProps<{
    demo: FunctionDemo
    /** Set by the page's single play/pause control; null means "decide for yourself". */
    play?: boolean | null
  }>(),
  { play: null },
)

const TICK_MS = 320
const tick = ref(0)

/**
 * Read the preference before the first render, not in onMounted: the playhead is
 * driven by `playing`, so starting it true would flash one frame of movement at
 * someone who asked for none.
 */
const reduceMotion = ref(
  typeof window !== 'undefined' &&
    (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false),
)
const playing = ref(!reduceMotion.value)
let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  if (wanted()) start()
})

onBeforeUnmount(stop)

/** Whether this demo should be running right now. */
function wanted() {
  if (reduceMotion.value) return false
  return props.play ?? true
}

watch(
  () => props.play,
  () => (wanted() ? start() : stop()),
)

function start() {
  stop()
  playing.value = true
  timer = setInterval(() => {
    tick.value = (tick.value + 1) % props.demo.input.length
  }, TICK_MS)
}

function stop() {
  clearInterval(timer)
  timer = undefined
  playing.value = false
}

const inputNow = computed(() => props.demo.input[tick.value] ?? false)
const outputNow = computed(() => props.demo.output[tick.value] ?? false)

/** The whole pattern as a row of blocks — the static form, and the backdrop. */
function cells(series: boolean[]) {
  return series.map((on, i) => ({ on, i }))
}
</script>

<template>
  <figure class="demo">
    <figcaption>
      <b class="mono">{{ demo.name }}</b>
      <span>{{ demo.plain }}</span>
    </figcaption>

    <div class="tracks" :aria-label="`${demo.name}: ${demo.plain}`" role="img">
      <div class="track">
        <span class="tname">You</span>
        <span class="bars">
          <i
            v-for="c in cells(demo.input)"
            :key="c.i"
            class="bar bar--in"
            :class="{ on: c.on, now: !reduceMotion && playing && c.i === tick }"
          />
        </span>
      </div>
      <div class="track">
        <span class="tname">Console</span>
        <span class="bars">
          <i
            v-for="c in cells(demo.output)"
            :key="c.i"
            class="bar bar--out"
            :class="{ on: c.on, now: !reduceMotion && playing && c.i === tick }"
          />
        </span>
      </div>
    </div>

    <p v-if="!reduceMotion" class="live" aria-hidden="true">
      <span :class="{ lit: inputNow }">sipping</span>
      <span :class="{ lit: outputNow }">button pressed</span>
    </p>

    <p v-if="demo.note" class="hint">{{ demo.note }}</p>
  </figure>
</template>

<style scoped>
.demo {
  margin: 0;
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

figcaption {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
figcaption b {
  font-size: var(--text-sm);
}
figcaption span {
  font-size: var(--text-sm);
}

.tracks {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.track {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.tname {
  width: 4.5rem;
  flex: none;
  font-size: var(--text-xs);
  color: var(--ink-soft);
  text-align: right;
}
.bars {
  display: flex;
  gap: 2px;
  flex: 1 1 auto;
}

.bar {
  flex: 1 1 0;
  height: 18px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--paper-sunk);
}
.bar--in.on {
  background: var(--sip);
  border-color: var(--sip);
}
.bar--out.on {
  background: var(--mode);
  border-color: var(--mode);
}
/* the playhead: a ring, not a colour change, so it reads at a glance */
.bar.now {
  box-shadow: 0 0 0 2px var(--ink);
}

.live {
  display: flex;
  gap: var(--sp-3);
  margin: 0;
  font-size: var(--text-xs);
  color: var(--ink-faint);
}
.live .lit {
  color: var(--ink);
  font-weight: 700;
}

.hint {
  margin: 0;
}
</style>
