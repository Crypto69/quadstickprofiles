<script setup lang="ts">
/**
 * One setting, with the right control for its kind — a number with its range, a
 * yes/no, a list, or plain text — all driven by the catalog so the app cannot offer
 * a value the firmware would reject.
 *
 * An empty value means "don't set this", which is different from setting it to the
 * default: the level below (the device, or the profile) then decides.
 */
import { computed } from 'vue'
import type { PreferenceEntry } from '@/api/types'

const props = defineProps<{
  name: string
  entry: PreferenceEntry
  value: string | undefined
  /** What applies if this is left blank: the level below, in words. */
  inheritedFrom?: string
  inheritedValue?: string
}>()

const emit = defineEmits<{ update: [value: string] }>()

const id = computed(() => `pref-${props.name}`)
const set = computed(() => props.value !== undefined && props.value !== '')

const placeholder = computed(() => {
  if (props.inheritedValue !== undefined && props.inheritedValue !== '') {
    return props.inheritedValue
  }
  return props.entry.default ?? ''
})

const range = computed(() => {
  const { minimum: lo, maximum: hi, unit } = props.entry
  if (lo === undefined && hi === undefined) return null
  const u = unit ? ` ${unit}` : ''
  if (lo !== undefined && hi !== undefined) return `${lo} to ${hi}${u}`
  if (lo !== undefined) return `${lo} or more${u}`
  return `up to ${hi}${u}`
})

const choices = computed(() =>
  (props.entry.options ?? []).map((v) => ({
    value: v,
    label: props.entry.optionLabels?.[v] ?? v,
  })),
)

/** A toggle is stored as "0" or "1", so the checkbox maps to those. */
const checked = computed(() => props.value === '1')

function onToggle(e: Event) {
  emit('update', (e.target as HTMLInputElement).checked ? '1' : '0')
}

function onInput(e: Event) {
  emit('update', (e.target as HTMLInputElement | HTMLSelectElement).value)
}

function clear() {
  emit('update', '')
}
</script>

<template>
  <div class="pref" :class="{ set }">
    <div class="field">
      <label :for="id">
        {{ entry.label }}
        <code class="mono">{{ name }}</code>
      </label>

      <!-- yes / no -->
      <template v-if="entry.editor === 'toggle'">
        <span class="toggle">
          <input :id="id" type="checkbox" :checked="checked" @change="onToggle" />
          <span>{{ checked ? 'On' : 'Off' }}</span>
          <span v-if="!set" class="inherit-note">(not set)</span>
        </span>
      </template>

      <!-- pick one -->
      <select
        v-else-if="entry.editor === 'choice'"
        :id="id"
        class="input"
        :value="value ?? ''"
        @change="onInput"
      >
        <option value="">
          Leave it to {{ inheritedFrom ?? 'the QuadStick' }}{{
            placeholder ? ` (${choices.find((c) => c.value === placeholder)?.label ?? placeholder})` : ''
          }}
        </option>
        <option v-for="c in choices" :key="c.value" :value="c.value">{{ c.label }}</option>
      </select>

      <!-- a number, with its range -->
      <input
        v-else-if="entry.editor === 'integer'"
        :id="id"
        class="input"
        type="number"
        inputmode="numeric"
        :min="entry.minimum"
        :max="entry.maximum"
        :value="value ?? ''"
        :placeholder="placeholder"
        @input="onInput"
      />

      <!-- free text, e.g. a Bluetooth address -->
      <input
        v-else
        :id="id"
        class="input"
        type="text"
        :value="value ?? ''"
        :placeholder="placeholder"
        @input="onInput"
      />

      <div class="help">
        <p v-if="range && entry.editor === 'integer'" class="hint">
          {{ range }}<span v-if="entry.default">, normally {{ entry.default }}</span>
        </p>
        <p v-if="entry.description" class="hint desc">{{ entry.description }}</p>
        <p v-if="!set && inheritedFrom" class="hint inherited">
          Not set here — {{ inheritedFrom }} decides<span v-if="inheritedValue">
            ({{ inheritedValue }})</span
          >.
        </p>
      </div>
    </div>

    <button
      v-if="set"
      class="btn btn--small btn--quiet"
      type="button"
      :aria-label="`Stop setting ${entry.label} here`"
      @click="clear"
    >
      Unset
    </button>
  </div>
</template>

<style scoped>
.pref {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--line);
  border-left: 4px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
  container-type: inline-size;
}
/* A setting that is actually set here reads differently from one inherited. */
.pref.set {
  border-left-color: var(--mode);
  background: var(--paper);
}

.field {
  flex: 1 1 auto;
  min-width: 0;
}

label {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  flex-wrap: wrap;
  font-size: var(--text-sm);
  font-weight: 600;
}

/* Wide enough for two columns: the label and help on the left, the control on the
   right, so a long list of settings does not become a long scroll. */
@container (min-width: 560px) {
  .field {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 11rem;
    grid-template-areas: 'label control' 'help control';
    column-gap: var(--sp-3);
    align-items: start;
  }
  .field > label {
    grid-area: label;
  }
  .field > .input,
  .field > .toggle {
    grid-area: control;
    align-self: start;
  }
  .field > .help {
    grid-area: help;
  }
}
label code {
  /* --ink-soft, not --ink-faint: this is small text and has to clear 4.5:1 on the
     tinted card backgrounds too */
  color: var(--ink-soft);
  font-size: var(--text-xs);
  font-weight: 400;
}

.toggle {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--target);
}
.toggle input {
  width: 22px;
  height: 22px;
}

/* The description is the long part; keep it to two lines unless it is set here or
   the field has focus, so the list stays scannable. */
.help {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.help .hint {
  margin: 0;
}

.desc {
  max-width: 60ch;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pref.set .desc,
.pref:focus-within .desc,
.pref:hover .desc {
  -webkit-line-clamp: unset;
  overflow: visible;
}
.inherited {
  color: var(--ink-soft);
  font-style: italic;
}
.inherit-note {
  color: var(--ink-faint);
  font-size: var(--text-xs);
}
</style>
