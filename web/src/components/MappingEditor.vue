<script setup lang="ts">
/**
 * Edits everything mapped to one input, as sentences:
 * "Press [output] when you [input] as [function]".
 *
 * Every keyword field is a constrained list from the catalog — never free text,
 * so the editor cannot produce a name the QuadStick would reject. Sequence and
 * per-mode preference rows are shown read-only: the file format allows both, but
 * neither is verified on a device yet (see docs/file-format.md).
 */
import { computed, ref } from 'vue'
import FunctionPicker from './FunctionPicker.vue'
import type { EditMapping } from '@/stores/document'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'

const props = defineProps<{ input: string }>()

const catalog = useCatalogStore()
const docStore = useDocumentStore()

const expandedKey = ref<string | null>(null)

const label = computed(() => docStore.inputName(props.input, catalog.inputLabel(props.input)))
const consoleName = computed(() => docStore.doc?.console ?? 'playstation')
const modeKey = computed(() => docStore.selectedMode?.key ?? null)
const modeName = computed(() => docStore.selectedMode?.name)

const mappings = computed(() => docStore.mappingsForInput(props.input))

/** Outputs grouped for the picker, under the profile's naming set — the store's one shape. */
const outputGroups = computed(() => catalog.outputGroups(consoleName.value))

/**
 * An output the catalog does not list is still the row's real value: it goes in as
 * the first option, marked "(current)", so it is visible and is not silently
 * replaced by whatever the browser shows first.
 */
const knownOutputs = computed(
  () => new Set((catalog.catalog?.outputs ?? []).map((o) => o.name)),
)
function unknownOutput(row: EditMapping) {
  return row.output && !knownOutputs.value.has(row.output) ? row.output : null
}

function add() {
  if (!modeKey.value) return
  const row = docStore.addMapping(modeKey.value, { inputs: [props.input], output: '' })
  if (row) expandedKey.value = row.key
}

function update(row: EditMapping, patch: Partial<EditMapping>) {
  if (!modeKey.value) return
  docStore.updateMapping(modeKey.value, row.key, patch)
}

function remove(row: EditMapping) {
  if (!modeKey.value) return
  docStore.deleteMapping(modeKey.value, row.key)
}

/** A row with more than one input fires last in a sequence; we don't edit those yet. */
function isSequence(row: EditMapping) {
  return row.kind === 'mapping' && row.inputs.length > 1
}

function sequenceText(row: EditMapping) {
  return row.inputs
    .map((i) => docStore.inputName(i, catalog.inputLabel(i)))
    .join(' then ')
}

function actionFor(row: EditMapping) {
  return docStore.actionFor(row.output, modeName.value) ?? ''
}

/** The mapping as one readable sentence, for assistive technology. */
function sentenceFor(row: EditMapping) {
  const out = row.output
    ? catalog.outputLabel(row.output, consoleName.value)
    : 'nothing yet'
  const fn = row.function || 'normal' // an empty cell reads as normal on the device
  const how =
    fn === 'normal' && !row.params.length
      ? ''
      : ` as ${fn}${row.params.length ? ' ' + row.params.join(' ') : ''}`
  return `Press ${out} when you ${label.value}${how}.`
}

function setAction(row: EditMapping, value: string) {
  docStore.setAction(row.output, value, modeName.value ?? null)
}
</script>

<template>
  <div class="editor">
    <header>
      <h3>{{ label }}</h3>
      <code class="mono">{{ input }}</code>
      <span v-if="catalog.isLegacyInput(input)" class="badge badge--warning">older name</span>
    </header>

    <p v-if="!mappings.length" class="hint">
      Nothing happens when you use this yet.
    </p>

    <ul class="rows">
      <li v-for="row in mappings" :key="row.key" class="row-card">
        <!-- a sequence row: read-only until one is verified on a device -->
        <template v-if="isSequence(row)">
          <p class="sentence">
            Press <b>{{ catalog.outputLabel(row.output, consoleName) }}</b> when you do
            <b>{{ sequenceText(row) }}</b> in that order.
          </p>
          <p class="hint">
            This is a sequence — more than one input, performed in order. The app keeps it
            exactly as it is, because sequences are not verified on a device yet.
          </p>
        </template>

        <!-- an ordinary mapping -->
        <template v-else>
          <!-- A screen reader gets the mapping as one plain sentence, which also
               describes the control: the select is named by its own sr-only label and
               stays in the accessibility tree — nothing focusable is ever hidden. -->
          <p class="sentence">
            <span :id="`sent-${row.key}`" class="sr-only">{{ sentenceFor(row) }}</span>
            <span>
              Press
              <select
                :id="`out-${row.key}`"
                class="inline"
                :value="row.output"
                :aria-describedby="`sent-${row.key}`"
                @change="update(row, { output: ($event.target as HTMLSelectElement).value })"
              >
                <option value="" disabled>choose an output…</option>
                <option v-if="unknownOutput(row)" :value="unknownOutput(row)!">
                  (current) {{ unknownOutput(row) }}
                </option>
                <optgroup v-for="g in outputGroups" :key="g.grp" :label="g.grp">
                  <option v-for="o in g.items" :key="o.name" :value="o.name">
                    {{ o.shown }}{{ o.label !== o.name ? ` — ${o.label}` : '' }}
                  </option>
                </optgroup>
              </select>
              when you <b>{{ label }}</b>
              <span v-if="(row.function || 'normal') !== 'normal' || row.params.length">
                as <b>{{ row.function || 'normal' }}{{ row.params.length ? ' ' + row.params.join(' ') : '' }}</b>
              </span>.
            </span>
          </p>
          <label class="sr-only" :for="`out-${row.key}`">
            Output pressed when you use {{ label }}
          </label>

          <div class="row-actions">
            <button
              class="btn btn--small btn--quiet"
              type="button"
              :aria-expanded="expandedKey === row.key"
              @click="expandedKey = expandedKey === row.key ? null : row.key"
            >
              {{ expandedKey === row.key ? 'Hide details' : 'Details' }}
            </button>
            <button class="btn btn--small btn--danger" type="button" @click="remove(row)">
              Remove
            </button>
          </div>

          <div v-if="expandedKey === row.key" class="details">
            <FunctionPicker
              :fn="row.function"
              :params="row.params"
              @update="(fn, params) => update(row, { function: fn, params })"
            />

            <div class="field">
              <label :for="`act-${row.key}`">What this does in the game</label>
              <input
                :id="`act-${row.key}`"
                class="input"
                type="text"
                :value="actionFor(row)"
                placeholder="Fire, Jump, Aim down sights…"
                @input="setAction(row, ($event.target as HTMLInputElement).value)"
              />
              <p class="hint">This is what the printed card shows instead of the button name.</p>
            </div>

            <div class="field">
              <label :for="`c-${row.key}`">Note to yourself</label>
              <input
                :id="`c-${row.key}`"
                class="input"
                type="text"
                :value="row.comment ?? ''"
                @input="update(row, { comment: ($event.target as HTMLInputElement).value || null })"
              />
              <p class="hint">Kept in this app only — notes are never written to the QuadStick.</p>
            </div>
          </div>
        </template>
      </li>
    </ul>

    <button class="btn btn--small" type="button" @click="add">Add something here</button>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
header h3 {
  margin: 0;
  font-size: var(--text-lg);
}
header code {
  color: var(--ink-faint);
  font-size: var(--text-xs);
}

.rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.row-card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: var(--sp-3);
  background: var(--paper);
}

.sentence {
  margin: 0;
  line-height: 1.8;
}

select.inline {
  min-height: var(--target);
  max-width: 100%;
  padding: 0 var(--sp-2);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--paper);
}

.row-actions {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}

.details {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
</style>
