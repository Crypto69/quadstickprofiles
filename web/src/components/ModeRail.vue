<script setup lang="ts">
/**
 * The modes, in order. The order *is* the mode number, so reordering renumbers.
 * Up/down buttons rather than drag: dragging needs one pointer held while moving,
 * which is exactly what this app must never require.
 */
import { computed, nextTick, ref } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import ModalDialog from './ModalDialog.vue'
import { ledPatternClashes, ledsFor } from '@/device/layout'
import type { EditMode } from '@/stores/document'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'

const catalog = useCatalogStore()
const docStore = useDocumentStore()

const renaming = ref<string | null>(null)
const draftName = ref('')
const newName = ref('')
const confirmDelete = ref<EditMode | null>(null)

/**
 * The rename box and the button that opened it, so focus can go in and come back.
 * Function refs, because a plain `ref` inside v-for collects an array rather than
 * the one element being rendered.
 */
let renameBox: HTMLInputElement | null = null
const renameButtons = new Map<string, HTMLElement>()
function trackRenameBox(el: Element | ComponentPublicInstance | null) {
  renameBox = el instanceof HTMLInputElement ? el : null
}
function trackRenameButton(key: string, el: Element | ComponentPublicInstance | null) {
  if (el instanceof HTMLElement) renameButtons.set(key, el)
  else renameButtons.delete(key)
}

const modes = computed(() => docStore.doc?.modes ?? [])
const maxModes = computed(() => catalog.catalog?.limits.max_modes ?? 16)
const full = computed(() => modes.value.length >= maxModes.value)

/** Rows used in each mode, from the live validation budget. */
function rows(position: number) {
  return docStore.budget?.modes.find((m) => m.number === position) ?? null
}

/** How many problems sit in this mode, so the rail shows where to look. */
function problems(position: number) {
  const f = docStore.findingsFor(position)
  return {
    errors: f.filter((x) => x.severity === 'error').length,
    warnings: f.filter((x) => x.severity === 'warning').length,
  }
}

function clashes(position: number) {
  return ledPatternClashes(position, modes.value.length)
}

async function startRename(key: string, name: string) {
  renaming.value = key
  draftName.value = name
  await nextTick()
  renameBox?.select()
}

/**
 * One field renames the mode: its name and its label are the same cell on the
 * device, so the store sets both, and the game actions scoped to the old name
 * follow it (see `renameMode`).
 */
function commitRename() {
  if (renaming.value && draftName.value.trim()) {
    docStore.renameMode(renaming.value, draftName.value.trim())
  }
  closeRename()
}

/** Ends a rename, and puts the keyboard back on the button that started it. */
function closeRename() {
  const key = renaming.value
  renaming.value = null
  if (key) nextTick(() => renameButtons.get(key)?.focus())
}

/** A mode's rows all go with it, so the delete asks first, like the Library's. */
function deleteConfirmed() {
  if (confirmDelete.value) docStore.deleteMode(confirmDelete.value.key)
  confirmDelete.value = null
}

function addMode() {
  const name = newName.value.trim() || `Mode ${modes.value.length + 1}`
  docStore.addMode(name, maxModes.value)
  newName.value = ''
}
</script>

<template>
  <nav class="rail" aria-label="Modes">
    <h2>Modes</h2>

    <ol>
      <li
        v-for="(m, i) in modes"
        :key="m.key"
        :class="{ current: m.key === docStore.selectedModeKey }"
      >
        <!-- While renaming, the text box stands in for the select button: it is a
             sibling, never a child of the button, so Enter and Escape are its own
             and a mouse can focus it in every browser. -->
        <div v-if="renaming === m.key" class="pick renaming">
          <span class="num">{{ i + 1 }}</span>
          <input
            :ref="trackRenameBox"
            v-model="draftName"
            class="input rename"
            type="text"
            :aria-label="`Rename mode ${i + 1}`"
            @keydown.enter.prevent="commitRename"
            @keydown.esc.prevent="closeRename"
            @blur="commitRename"
          />
        </div>
        <button
          v-else
          type="button"
          class="pick"
          :aria-current="m.key === docStore.selectedModeKey ? 'true' : undefined"
          @click="docStore.selectMode(m.key)"
        >
          <span class="num">{{ i + 1 }}</span>
          <!-- The name gets the full width of the button, with the lights and the
               badge on their own line beneath it. Sharing one row, the name was
               squeezed to "Left Anal…" by five dots it did not need to sit beside. -->
          <span class="names">
            <b>{{ m.name }}</b>
            <span class="under">
              <small v-if="rows(i + 1)">{{ rows(i + 1)!.rows_used }} rows</small>
              <span class="leds" aria-hidden="true">
                <i v-for="(c, li) in ledsFor(i + 1)" :key="li" :class="[c, { on: c !== 'off' }]" />
              </span>
              <span v-if="problems(i + 1).errors" class="badge badge--error">
                {{ problems(i + 1).errors }}
              </span>
              <span v-else-if="problems(i + 1).warnings" class="badge badge--warning">
                {{ problems(i + 1).warnings }}
              </span>
            </span>
          </span>
        </button>

        <div class="mode-actions">
          <button
            class="btn btn--small btn--quiet"
            type="button"
            :disabled="i === 0"
            :aria-label="`Move ${m.name} up, to mode ${i}`"
            @click="docStore.moveMode(m.key, -1)"
          >
            ↑
          </button>
          <button
            class="btn btn--small btn--quiet"
            type="button"
            :disabled="i === modes.length - 1"
            :aria-label="`Move ${m.name} down, to mode ${i + 2}`"
            @click="docStore.moveMode(m.key, 1)"
          >
            ↓
          </button>
          <button
            :ref="(el) => trackRenameButton(m.key, el)"
            class="btn btn--small btn--quiet"
            type="button"
            :aria-label="`Rename ${m.name}`"
            @click="startRename(m.key, m.name)"
          >
            Rename
          </button>
          <button
            class="btn btn--small btn--quiet btn--danger"
            type="button"
            :aria-label="`Delete ${m.name}`"
            @click="confirmDelete = m"
          >
            Delete
          </button>
        </div>

        <p v-if="clashes(i + 1).length" class="clash">
          The lights for this mode look the same as mode
          {{ clashes(i + 1).join(' and ') }} — you cannot tell them apart on the device.
        </p>
      </li>
    </ol>

    <div class="add">
      <div class="field">
        <label for="new-mode">Add a mode</label>
        <input
          id="new-mode"
          v-model="newName"
          class="input"
          type="text"
          placeholder="Driving"
          :disabled="full"
          @keydown.enter="addMode"
        />
      </div>
      <button class="btn btn--small" type="button" :disabled="full" @click="addMode">Add</button>
      <p class="hint">
        {{ modes.length }} of {{ maxModes }} modes.
        <span v-if="full">That is the most the QuadStick reads.</span>
      </p>
    </div>

    <!-- delete asks first: a mode takes every one of its rows with it ---------- -->
    <ModalDialog :open="confirmDelete !== null" title="Delete this mode?" @close="confirmDelete = null">
      <p v-if="confirmDelete">
        <b>{{ confirmDelete.name }}</b> and its
        {{ confirmDelete.mappings.length }}
        {{ confirmDelete.mappings.length === 1 ? 'row' : 'rows' }} will be removed from this
        profile, and the modes after it move up a number. Nothing changes on the QuadStick
        until you export.
      </p>
      <template #actions>
        <button class="btn" type="button" @click="confirmDelete = null">Keep it</button>
        <button class="btn btn--danger" type="button" @click="deleteConfirmed">Delete</button>
      </template>
    </ModalDialog>
  </nav>
</template>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.rail h2 {
  margin: 0;
  font-size: var(--text-base);
}

ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

li {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
  overflow: hidden;
}
li.current {
  border-color: var(--mode);
  box-shadow: inset 0 0 0 1px var(--mode);
}

.pick {
  display: flex;
  /* The number sits against the name's first line, not the middle of a two-line
     block, now that the lights hang below the name. */
  align-items: flex-start;
  gap: var(--sp-2);
  width: 100%;
  min-height: var(--target);
  padding: var(--sp-2);
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font: inherit;
}
.pick:hover {
  background: var(--paper-sunk);
}

.num {
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--mode);
  color: #fff;
  font-weight: 700;
  font-size: var(--text-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.names {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1 1 auto;
  min-width: 0;
}
/* "Left Analog", "Mouse Scroll": a mode name is words, so it wraps to a second
   line rather than being cut to "Left Anal…". The rail is narrow and a truncated
   name is the one thing in this list you cannot work around. */
.names b {
  overflow-wrap: anywhere;
}
.names small {
  color: var(--ink-faint);
  font-size: var(--text-xs);
  white-space: nowrap;
}
/* Row count, lights and the problem badge, under the name and out of its way. */
.under {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.pick.renaming {
  cursor: default;
  align-items: center;
}
.pick.renaming:hover {
  background: transparent;
}
.rename {
  min-height: var(--target);
  flex: 1 1 auto;
  min-width: 0;
}

.leds {
  display: inline-flex;
  align-items: center;
  /* A lit dot draws a 3px ring outside itself, so the gap keeps neighbours apart
     and the margin keeps the ring off the name above and the buttons below. */
  gap: 6px;
  margin: 3px 0;
  flex: none;
}
.leds i {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--ink-soft);
  background: #fff;
}
/* Lit in the colour the firmware uses: LED 5's colour tells which round of
   counting the mode is in, so mode 5 (purple) and mode 10 (blue) differ. */
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

.mode-actions {
  display: flex;
  gap: 2px;
  padding: 0 var(--sp-2) var(--sp-2);
  flex-wrap: wrap;
}

.clash {
  margin: 0;
  padding: var(--sp-2);
  background: var(--warning-soft);
  color: var(--warning);
  font-size: var(--text-xs);
}

.add {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-2);
  flex-wrap: wrap;
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.add .field {
  flex: 1 1 8rem;
}
.add .hint {
  width: 100%;
  margin: 0;
}
</style>
