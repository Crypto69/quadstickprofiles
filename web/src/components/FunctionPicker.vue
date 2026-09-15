<script setup lang="ts">
// The output function, in plain English, with its parameters. Every option comes
// from the catalog, so the UI can never offer a function the firmware rejects.
import { computed } from 'vue'
import { useCatalogStore } from '@/stores/catalog'
import type { FunctionParam } from '@/api/types'

const props = defineProps<{ fn: string; params: FunctionParam[] }>()
const emit = defineEmits<{ update: [fn: string, params: FunctionParam[]] }>()

const catalog = useCatalogStore()

const functions = computed(() => catalog.catalog?.functions ?? [])
/** An empty function cell is written back empty, but the device reads it as `normal`. */
const fnName = computed(() => props.fn || 'normal')
const current = computed(() => catalog.functionsByName.get(fnName.value) ?? null)
const maxParams = computed(() => current.value?.max_params ?? 0)

/**
 * Names, hints and firmware defaults for the parameters a function takes. Read from
 * the firmware's DataFlow.c (via QCM's FunctionParameters.cs), not from a guess: a
 * wrong label here writes a number into the wrong slot on the device.
 *
 * `default` is what the firmware uses when the parameter is absent. It is shown as a
 * placeholder, and used to fill an earlier slot when a later one is set, so the
 * emitted list is always positional.
 */
const PARAM_META: Record<string, { label: string; hint: string; default: number }[]> = {
  repeat: [
    { label: 'Presses per second', hint: 'How fast it auto-fires while held', default: 5 },
    { label: 'Hold delay (ms)', hint: 'Wait this long before it starts repeating', default: 2000 },
  ],
  pulse: [
    { label: 'Press length (ms)', hint: 'How long each press lasts', default: 100 },
    { label: 'Count', hint: 'How many presses per trigger. Empty or 0 means one', default: 1 },
  ],
  duty: [
    {
      label: 'Cycle (ms)',
      hint: 'Length of one on-and-off cycle. How hard you sip or puff sets how much of it is on',
      default: 100,
    },
  ],
  greater_than: [
    { label: 'Threshold (%)', hint: 'Fires above this pressure', default: 50 },
    {
      label: 'Upper limit (%)',
      hint: 'Stops firing above this pressure. Empty means no upper limit',
      default: 100,
    },
  ],
  less_than: [{ label: 'Threshold (%)', hint: 'Fires below this pressure', default: 50 }],
  force_off: [
    { label: 'Delay (ms)', hint: 'Wait this long before forcing it off. Empty means at once', default: 0 },
  ],
  delayed_latch: [{ label: 'Hold time (ms)', hint: 'Hold this long to latch it on', default: 500 }],
  delay_off: [{ label: 'Extra time (ms)', hint: 'Stays on this long after you let go', default: 200 }],
  delay_on: [
    { label: 'Delay (ms)', hint: 'Waits this long before starting', default: 200 },
    {
      label: 'Then for (ms)',
      hint: 'How long it then stays on. Empty means while held; exactly 1 means latch it on',
      default: 0,
    },
  ],
  tap: [
    { label: 'Tap length (ms)', hint: 'Longer than this counts as a hold', default: 300 },
    { label: 'Press length (ms)', hint: 'How long the tap press lasts. Exactly 1 means toggle', default: 100 },
  ],
  increment_value: [
    { label: 'Step (%)', hint: 'How much to change it by', default: 1 },
    { label: 'Every (ms)', hint: 'Repeat interval while held', default: 200 },
  ],
  decrement_value: [
    { label: 'Step (%)', hint: 'How much to change it by', default: 1 },
    { label: 'Every (ms)', hint: 'Repeat interval while held', default: 200 },
  ],
}

/**
 * The largest parameter the firmware stores (a 14-bit field), from the catalog so
 * the box and the core validator agree. Out-of-range values are an export-blocking
 * finding from the validator; the box just says so first. The fallback only
 * matters before the catalog has loaded, and it is the firmware's own limit.
 */
const maxParam = computed(() => catalog.catalog?.limits.max_function_param ?? 16383)

const paramMeta = computed(() => (PARAM_META[fnName.value] ?? []).slice(0, maxParams.value))

/**
 * A parameter the file holds as a non-numeric token. It round-trips untouched, so
 * the box has to show it rather than render blank — a `type="number"` input drops a
 * value it cannot parse, and typing over the blank would silently delete the token
 * without the user ever seeing what was there.
 */
function isText(i: number) {
  return typeof props.params[i] === 'string'
}

function pick(name: string) {
  // A newly chosen function starts bare, the way every row in the fixtures is
  // written: the firmware applies its own defaults when a parameter is absent, and
  // the boxes show those defaults as placeholders. Writing them out would change
  // the file for no gain.
  emit('update', name, [])
}

/**
 * Parameters are positional, so clearing box i means "this one and everything after
 * it are absent" — the firmware cannot skip a slot. Setting a later box first fills
 * the earlier ones with their firmware defaults, so what is emitted is what the
 * device will see. Decimals are truncated, as the firmware's atoi would do.
 */
function setParam(i: number, raw: string) {
  const text = raw.trim()
  const n = Number(text)
  if (text === '' || !Number.isFinite(n)) {
    emit('update', fnName.value, props.params.slice(0, i))
    return
  }
  const next = [...props.params]
  while (next.length < i) next.push(paramMeta.value[next.length]?.default ?? 0)
  next[i] = Math.trunc(n)
  emit('update', fnName.value, next)
}
</script>

<template>
  <div class="picker">
    <div class="field">
      <label for="fn">How it behaves</label>
      <select id="fn" class="input" :value="fnName" @change="pick(($event.target as HTMLSelectElement).value)">
        <option v-for="f in functions" :key="f.name" :value="f.name">
          {{ f.name }} — {{ f.description }}
        </option>
      </select>
    </div>

    <p v-if="current?.description" class="hint doc">{{ current.description }}</p>

    <div v-if="paramMeta.length" class="params">
      <div v-for="(m, i) in paramMeta" :key="m.label" class="field">
        <label :for="`p${i}`">{{ m.label }}</label>
        <input
          :id="`p${i}`"
          class="input"
          :type="isText(i) ? 'text' : 'number'"
          inputmode="numeric"
          min="0"
          step="1"
          :max="maxParam"
          :aria-invalid="isText(i) || undefined"
          :value="params[i] ?? ''"
          :placeholder="String(m.default)"
          @input="setParam(i, ($event.target as HTMLInputElement).value)"
        />
        <p v-if="isText(i)" class="hint hint--warn" role="alert">
          <b class="mono">{{ params[i] }}</b> is not a whole number; the QuadStick reads it as
          0. Type a number to replace it.
        </p>
        <p class="hint">{{ m.hint }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.doc {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  background: var(--paper-sunk);
  border-radius: var(--radius);
}
.hint--warn {
  color: var(--warning);
  font-weight: 600;
}
.params {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--sp-3);
}
</style>
