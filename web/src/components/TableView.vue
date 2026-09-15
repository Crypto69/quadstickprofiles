<script setup lang="ts">
/**
 * The raw rows, for people who know the spreadsheet: output, function, inputs,
 * comment — in file order, with the spreadsheet row number. Every keyword cell is
 * a constrained list from the catalog; there is no free-text keyword anywhere.
 *
 * Sequence rows and per-mode preference override rows are read-only: the format
 * allows both and the app round-trips them byte for byte, but neither is verified
 * on a device, so the editor will not invent or alter one.
 */
import { computed, ref } from 'vue'
import FunctionPicker from './FunctionPicker.vue'
import type { EditMapping } from '@/stores/document'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'

const ROW_OFFSET = 4 // data rows start at spreadsheet row 4

const catalog = useCatalogStore()
const docStore = useDocumentStore()

const mode = computed(() => docStore.selectedMode)
const consoleName = computed(() => docStore.doc?.console ?? 'playstation')

/**
 * A row with no input is "unused": the QuadStick reads it, but nothing you do
 * triggers it. A mode can easily carry twenty of them, which buries the rows that
 * actually do something — hence the toggle.
 *
 * The spreadsheet row number is worked out BEFORE filtering, so a hidden row does
 * not renumber the ones around it. The numbers stay the file's own, which is the
 * whole point of this view.
 */
const hideUnused = ref(false)

const allRows = computed(() =>
  (mode.value?.mappings ?? []).map((m, i) => ({ m, row: i + ROW_OFFSET })),
)

/** An unused row: an ordinary mapping with nothing to trigger it. */
function isUnused(m: EditMapping) {
  return m.kind === 'mapping' && m.inputs.length === 0
}

const unusedCount = computed(() => allRows.value.filter((r) => isUnused(r.m)).length)

const rows = computed(() =>
  hideUnused.value ? allRows.value.filter((r) => !isUnused(r.m)) : allRows.value,
)

/** Inputs offered in the dropdown: current names only, never the older ones. */
const inputOptions = computed(() => catalog.currentInputs)

/** Outputs grouped for the picker, under the profile's naming set — the store's one shape. */
const outputGroups = computed(() => catalog.outputGroups(consoleName.value))

function editable(m: EditMapping) {
  return m.kind === 'mapping' && m.inputs.length <= 1
}

/** The function cell as the device reads it: "repeat 5 2000", or "normal" (also for an empty cell). */
function fnText(m: EditMapping) {
  return (m.function || 'normal') + (m.params.length ? ' ' + m.params.join(' ') : '')
}

/**
 * The function and its parameters need more than a cell — a list plus up to two
 * named boxes — so the cell is a button that opens the picker in a row beneath it.
 * One open at a time keeps the table readable.
 */
const expandedKey = ref<string | null>(null)
function toggleFunction(m: EditMapping) {
  expandedKey.value = expandedKey.value === m.key ? null : m.key
}

/**
 * A value the catalog does not list — a keyword from a newer firmware, or an older
 * input name — is still the row's real value. It goes in as the first option,
 * marked "(current)", so it is visible and is not silently replaced by whatever
 * the browser shows first.
 */
const knownOutputs = computed(() => new Set((catalog.catalog?.outputs ?? []).map((o) => o.name)))
const knownInputs = computed(() => new Set(inputOptions.value.map((i) => i.name)))
function unknownOutput(m: EditMapping) {
  return m.output && !knownOutputs.value.has(m.output) ? m.output : null
}
function unknownInput(m: EditMapping) {
  const i = m.inputs[0]
  return i && !knownInputs.value.has(i) ? i : null
}

function why(m: EditMapping) {
  if (m.kind === 'preference') return 'A setting for this mode only — kept as it is'
  if (m.inputs.length > 1) return 'A sequence — kept as it is'
  return ''
}

function update(m: EditMapping, patch: Partial<EditMapping>) {
  if (!mode.value) return
  docStore.updateMapping(mode.value.key, m.key, patch)
}

/** The single input, or '' for an unused row (output listed but nothing triggers it). */
function setInput(m: EditMapping, value: string) {
  update(m, { inputs: value ? [value] : [] })
}

function remove(m: EditMapping) {
  if (!mode.value) return
  docStore.deleteMapping(mode.value.key, m.key)
}

function add() {
  if (!mode.value) return
  docStore.addMapping(mode.value.key)
}

/**
 * Findings that sit on a row of this mode, flattened for the list under the table.
 * Findings with no row (mode-level ones) belong in the Problems panel, not here.
 */
const rowProblems = computed(() => {
  const known = new Set(allRows.value.map(({ row }) => row))
  return docStore
    .findingsFor(docStore.selectedModeNumber)
    .filter((f) => f.row !== null && known.has(f.row))
    .map((f, i) => ({ id: `${f.row}-${i}`, row: f.row as number, severity: f.severity, message: f.message }))
})
</script>

<template>
  <div class="table-view">
    <div class="toolbar">
      <label class="check">
        <input v-model="hideUnused" type="checkbox" :disabled="!unusedCount" />
        Hide the {{ unusedCount }} {{ unusedCount === 1 ? 'row' : 'rows' }} nothing triggers
      </label>
      <p v-if="hideUnused" class="hint" role="status">
        Showing {{ rows.length }} of {{ allRows.length }}. The hidden rows are still in
        the file, and the row numbers below are still the file's own.
      </p>
    </div>

    <div class="scroll">
      <table>
        <caption class="sr-only">
          Every row of this mode, in the order the QuadStick reads them
        </caption>
        <thead>
          <tr>
            <th class="rownum">Row</th>
            <th>Output</th>
            <th>How it behaves</th>
            <th>Input</th>
            <th>Note</th>
            <th><span class="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="{ m, row } in rows" :key="m.key">
          <tr :class="{ locked: !editable(m) }">
            <th scope="row" class="rownum">{{ row }}</th>

            <!-- a preference override row: key in A, value in C -->
            <template v-if="m.kind === 'preference'">
              <td class="mono">{{ m.output }}</td>
              <td colspan="2">
                set to <b>{{ m.value }}</b> while this mode is active
              </td>
            </template>

            <template v-else>
              <td>
                <select
                  v-if="editable(m)"
                  class="cell"
                  :value="m.output"
                  :aria-label="`Output on row ${row}`"
                  @change="update(m, { output: ($event.target as HTMLSelectElement).value })"
                >
                  <option value="" disabled>choose…</option>
                  <option v-if="unknownOutput(m)" :value="unknownOutput(m)!">
                    (current) {{ unknownOutput(m) }}
                  </option>
                  <optgroup v-for="g in outputGroups" :key="g.grp" :label="g.grp">
                    <option v-for="o in g.items" :key="o.name" :value="o.name">{{ o.shown }}</option>
                  </optgroup>
                </select>
                <span v-else class="mono">{{ catalog.outputLabel(m.output, consoleName) }}</span>
              </td>

              <td>
                <button
                  v-if="editable(m)"
                  class="cell cell--button mono"
                  type="button"
                  :aria-label="`How row ${row} behaves: ${fnText(m)}`"
                  :aria-expanded="expandedKey === m.key"
                  @click="toggleFunction(m)"
                >
                  {{ fnText(m) }}
                </button>
                <span v-else class="mono">{{ fnText(m) }}</span>
              </td>

              <td>
                <select
                  v-if="editable(m)"
                  class="cell"
                  :value="m.inputs[0] ?? ''"
                  :aria-label="`Input on row ${row}`"
                  @change="setInput(m, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="">— nothing (unused row) —</option>
                  <option v-if="unknownInput(m)" :value="unknownInput(m)!">
                    (current) {{ unknownInput(m) }}
                  </option>
                  <option v-for="i in inputOptions" :key="i.name" :value="i.name">
                    {{ docStore.inputName(i.name, i.label ?? i.name) }}
                  </option>
                </select>
                <span v-else class="mono">{{ m.inputs.join(' then ') }}</span>
              </td>
            </template>

            <td>
              <input
                v-if="editable(m)"
                class="cell"
                type="text"
                :value="m.comment ?? ''"
                :aria-label="`Note on row ${row}`"
                @input="update(m, { comment: ($event.target as HTMLInputElement).value || null })"
              />
              <span v-else class="hint">{{ why(m) }}</span>
            </td>

            <td>
              <button
                v-if="editable(m)"
                class="btn btn--small btn--quiet btn--danger"
                type="button"
                :aria-label="`Delete row ${row}`"
                @click="remove(m)"
              >
                Delete
              </button>
            </td>
          </tr>

          <!-- the function picker for the row above, when its cell is open -->
          <tr v-if="expandedKey === m.key" class="details">
            <td colspan="6">
              <FunctionPicker
                :fn="m.function"
                :params="m.params"
                @update="(fn, params) => update(m, { function: fn, params })"
              />
              <button class="btn btn--small" type="button" @click="expandedKey = null">Done</button>
            </td>
          </tr>
          </template>
        </tbody>
      </table>
    </div>

    <p v-if="hideUnused && !rows.length" class="hint">
      Every row in this mode is waiting for an input. Untick the box above to see them.
    </p>

    <!-- problems, tied to the row they are on -->
    <ul v-if="rowProblems.length" class="row-problems">
      <li v-for="p in rowProblems" :key="p.id" :class="p.severity">
        <b>Row {{ p.row }}</b> · {{ p.message }}
      </li>
    </ul>

    <div class="row">
      <button class="btn btn--small" type="button" @click="add">Add a row</button>
      <p class="hint">
        Notes stay in this app. The QuadStick never sees them, and it stops reading a
        mode at the first row with no output.
      </p>
    </div>
  </div>
</template>

<style scoped>
.table-view {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.check {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--target);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}
.check input {
  width: 20px;
  height: 20px;
}
.check:has(input:disabled) {
  color: var(--ink-faint);
  cursor: default;
}
.toolbar .hint {
  margin: 0;
}

.scroll {
  overflow-x: auto;
}

table {
  border-collapse: collapse;
  width: 100%;
  font-size: var(--text-sm);
}
th,
td {
  border: 1px solid var(--line);
  padding: 1px 3px;
  text-align: left;
  vertical-align: middle;
}
thead th {
  background: var(--paper-sunk);
  font-size: var(--text-xs);
  white-space: nowrap;
}
.rownum {
  width: 3rem;
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  text-align: right;
}
tr.locked {
  background: var(--paper-sunk);
}

/* 44px tall (the pointer floor); the cell padding above is trimmed to match. */
.cell {
  width: 100%;
  min-height: var(--target);
  padding: 0 4px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  font: inherit;
}
.cell:hover,
.cell:focus {
  border-color: var(--line-strong);
  background: var(--paper);
}
.cell--button {
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
}
.cell--button[aria-expanded='true'] {
  border-color: var(--mode);
  background: var(--mode-soft);
}

tr.details td {
  padding: var(--sp-3);
  background: var(--mode-soft);
}
tr.details .btn {
  margin-top: var(--sp-3);
}

.row-problems {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--text-xs);
}
.row-problems li {
  padding-left: var(--sp-2);
  border-left: 3px solid var(--line);
}
.row-problems li.error {
  border-color: var(--error);
  color: var(--error);
  font-weight: 600;
}
.row-problems li.warning {
  border-color: var(--warning);
  color: var(--warning);
}
.row-problems li.info {
  border-color: var(--line-strong);
  color: var(--ink-soft);
}
</style>
