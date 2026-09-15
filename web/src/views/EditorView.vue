<script setup lang="ts">
/**
 * The editor. Mode rail on the left; the selected mode's device view, table view,
 * mode map, preferences and input names in the main area; a bottom bar that always
 * says what the QuadStick would do with this profile as it stands.
 *
 * Checks are live but never write: every edit re-posts the in-progress document to
 * POST /api/profiles/validate. Saving is explicit, and export stays blocked while
 * there are errors.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import BottomBar from '@/components/BottomBar.vue'
import DeviceView from '@/components/DeviceView.vue'
import ExportChecklist from '@/components/ExportChecklist.vue'
import FindingsList from '@/components/FindingsList.vue'
import MappingEditor from '@/components/MappingEditor.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import ModeMap from '@/components/ModeMap.vue'
import ModeRail from '@/components/ModeRail.vue'
import PreferencesEditor from '@/components/PreferencesEditor.vue'
import TableView from '@/components/TableView.vue'
import ValidationBadge from '@/components/ValidationBadge.vue'
import type { Download } from '@/api/client'
import { ApiError, api } from '@/api/client'
import { describe } from '@/api/errors'
import type { Channel, Validation } from '@/api/types'
import { saveBlob } from '@/composables/useDownload'
import { openExternal } from '@/composables/useExternalLink'
import { unknownFirmwareWarning } from '@/device/flashDrive'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'
import { usePrefsStore } from '@/stores/prefs'

const props = defineProps<{ id: string }>()

const catalog = useCatalogStore()
const docStore = useDocumentStore()
const prefs = usePrefsStore()

type Tab = 'device' | 'table' | 'map' | 'settings'
const tab = ref<Tab>('device')
const selectedInput = ref<string | null>(null)
/**
 * The inputs owned by the part being pointed at on the device photo. It exists so
 * the link the photo draws reaches this pane too: point at the left tube and
 * everything it drives is ringed, including the editor open beside it.
 */
const hoveredInputs = ref<string[]>([])
const sideLit = computed(
  () => selectedInput.value !== null && hoveredInputs.value.includes(selectedInput.value),
)
const exported = ref<Download | null>(null)
/** An export refused for errors: the reason and the findings behind it. */
const blocked = ref<{ message: string; validation: Validation | null } | null>(null)

const profileId = computed(() => Number(props.id))

onMounted(async () => {
  await catalog.load().catch(() => {})
  await docStore.load(profileId.value)
  // so a blank profile setting can show the device value that will apply instead
  prefs.load().catch(() => {})
})

// Only load when the id really moved on: a change the route guard below refused
// leaves the loaded profile where it is, and reloading it would discard the edits.
watch(profileId, (id) => {
  if (id === docStore.id) return
  void docStore.load(id)
})

// Leaving with unsaved work would lose it silently, so ask.
function warnIfDirty(e: BeforeUnloadEvent) {
  if (docStore.dirty) {
    e.preventDefault()
    e.returnValue = ''
  }
}
onMounted(() => window.addEventListener('beforeunload', warnIfDirty))
onBeforeUnmount(() => window.removeEventListener('beforeunload', warnIfDirty))

function okToLeave() {
  if (!docStore.dirty) return true
  return window.confirm('You have unsaved changes. Leave without saving?')
}
onBeforeRouteLeave(okToLeave)
// Opening another profile is a params-only change on the same route, which
// onBeforeRouteLeave never sees; it would otherwise drop the edits without asking.
onBeforeRouteUpdate((to, from) => (to.params.id === from.params.id ? true : okToLeave()))

const doc = computed(() => docStore.doc)
const mode = computed(() => docStore.selectedMode)
const budgetForMode = computed(() =>
  docStore.budget?.modes.find((m) => m.number === docStore.selectedModeNumber) ?? null,
)

/** The bottom bar's line: what the device would do, not just a count. */
const consequence = computed(() => {
  const v = docStore.validation
  if (!v) return null
  const worst = docStore.worst
  if (!worst) return 'No problems found. This will load and behave as written.'
  return v.consequence[worst] ?? null
})

/**
 * The two halves of the strip. Errors and warnings are things to fix; info is a
 * description of what the profile does, and a correct profile has plenty.
 *
 * They are split rather than listed together because mixing them made deliberate
 * design read as a fault — an input that fires an action *and* changes mode, say,
 * which is how the owner's own chin press works.
 */
const findings = computed(() => docStore.validation?.findings ?? [])
const toFix = computed(() => findings.value.filter((f) => f.severity !== 'info'))
const notes = computed(() => findings.value.filter((f) => f.severity === 'info'))

/**
 * What the strip is called. Once every error and warning is gone, what is left
 * is only information, and calling it "Problems" told the owner there was still
 * something to fix.
 */
const panelTitle = computed(() => (toFix.value.length ? 'Problems' : 'Nothing to fix'))

/**
 * The emulation mode is the file's own `enable_DS3_emulation` preference row.
 * There is no profile column: one existed once and never reached the device, so
 * the picker reads and writes the row itself. Picking "not set" deletes the row,
 * and the QuadStick falls back to prefs.csv.
 */
const EMULATION_KEY = 'enable_DS3_emulation'
const emulationMode = computed({
  get: () => doc.value?.preferences[EMULATION_KEY] ?? '',
  set: (v: string) => docStore.setPreference(EMULATION_KEY, v),
})

const emulationModes = computed(() =>
  Object.entries(catalog.catalog?.emulation_modes ?? {}).map(([n, label]) => ({
    value: n,
    label: `${n} — ${label}`,
  })),
)

/** A row value the catalog does not list still shows, rather than a blank select. */
const emulationUnlisted = computed(
  () => emulationMode.value !== '' && !emulationModes.value.some((e) => e.value === emulationMode.value),
)

/** The row as a number; null when unset or not a whole number (the checker says so). */
const emulationNumber = computed(() => {
  const raw = emulationMode.value.trim()
  return /^\d+$/.test(raw) ? Number(raw) : null
})

/**
 * true: this mode hides the flash drive on this firmware. false: it stays visible.
 * null: the firmware is not one the catalog knows, so nobody can say — and the
 * page must not call that "Good".
 */
const driveWarning = computed(() =>
  doc.value ? catalog.hidesFlashDrive(emulationNumber.value, doc.value.firmware) : false,
)

/**
 * "Connected by" is a per-mode cell (C3) in the file, not a profile attribute. The
 * control shows the modes' shared value, says "mixed" when they differ, and writes
 * every mode when changed — an owner wants one answer, not sixteen.
 */
type ChannelPick = Channel | 'mixed'
const channel = computed<ChannelPick>({
  get: () => {
    const modes = doc.value?.modes ?? []
    const first = modes[0]?.channel ?? 'usb'
    return modes.every((m) => m.channel === first) ? first : 'mixed'
  },
  set: (v) => {
    if (v === 'mixed' || !doc.value) return
    for (const m of doc.value.modes) m.channel = v
  },
})

const CHANNEL_OPTIONS: { value: Channel; label: string }[] = [
  { value: 'usb', label: 'USB cable' },
  { value: 'bluetooth', label: 'Bluetooth' },
  { value: 'both', label: 'USB cable and Bluetooth' },
  { value: 'none', label: 'Neither' },
]

const firmwares = computed(() => catalog.catalog?.firmware_versions ?? [])

/** Inputs worth offering a rename for: the ones actually used in this profile. */
const renameableInputs = computed(() => {
  const used = new Set<string>()
  for (const m of doc.value?.modes ?? []) {
    // preference rows carry no inputs (and after an undo may lack the field entirely)
    for (const r of m.mappings) {
      if (r.kind !== 'mapping') continue
      for (const i of r.inputs ?? []) used.add(i)
    }
  }
  for (const i of Object.keys(doc.value?.input_names ?? {})) used.add(i)
  used.add('lip') // this one gets renamed, so always offer it
  return [...used].sort()
})

function selectInput(input: string) {
  selectedInput.value = input
  if (tab.value !== 'device') tab.value = 'device'
}

/** Clicking a finding takes you to where it lives. */
function goToFinding(f: { mode: number | null; row: number | null }) {
  if (f.mode !== null) {
    const m = doc.value?.modes[f.mode - 1]
    if (m) docStore.selectMode(m.key)
  }
  tab.value = f.row !== null ? 'table' : 'device'
}

async function doExport() {
  if (docStore.dirty && !(await docStore.save())) return
  // The live check is debounced, so the button can be enabled on stale findings.
  // save() re-checks; trust that answer before asking the API for a file.
  if (!docStore.canExport) {
    blocked.value = {
      message: 'Fix the errors first — the QuadStick would not read this.',
      validation: docStore.validation,
    }
    return
  }
  try {
    const dl = await api.exportCsv(profileId.value)
    exported.value = dl
    saveBlob(dl.blob, dl.filename, dl.exportPath)
  } catch (e) {
    if (e instanceof ApiError && e.isValidationBlock) {
      // the API's own re-check said no: show its findings, not just the sentence
      blocked.value = { message: e.message, validation: e.validation ?? null }
    } else {
      docStore.error = describe(e)
    }
  }
}

function printCard() {
  openExternal(api.cardUrl(profileId.value))
}

function printSummary() {
  openExternal(api.summaryUrl(profileId.value))
}
</script>

<template>
  <p v-if="docStore.loading" role="status">Loading the profile…</p>

  <p v-else-if="!doc" class="banner--error">
    {{ docStore.error ?? 'Could not load that profile.' }}
    <RouterLink to="/">Back to the library</RouterLink>
  </p>

  <div v-else class="editor-shell">
    <header class="head">
      <div>
        <p class="crumb"><RouterLink to="/">← All profiles</RouterLink></p>
        <h1>{{ doc.name }}</h1>
        <p class="facts">
          <span v-if="doc.game">{{ doc.game }}</span>
          <span>{{ doc.console === 'xbox' ? 'Xbox' : 'PlayStation' }} names</span>
          <span class="mono">{{ doc.csv_filename }}</span>
        </p>
      </div>
      <div class="spacer" />
      <ValidationBadge :validation="docStore.validation" />
    </header>

    <p v-if="docStore.error" class="banner--error" role="alert">{{ docStore.error }}</p>

    <p v-if="driveWarning" class="warn">
      Emulation mode {{ emulationMode }} hides the flash drive on firmware
      {{ doc.firmware }}. If this profile turns out to be wrong you cannot simply copy a
      new file over — keep a known-good profile on the drive.
    </p>

    <div class="layout">
      <aside class="rail-col card">
        <ModeRail />
      </aside>

      <main class="work">
        <div class="tabs" role="tablist" aria-label="Editor views">
          <button
            v-for="t in (['device', 'table', 'map', 'settings'] as Tab[])"
            :key="t"
            class="tab"
            type="button"
            role="tab"
            :aria-selected="tab === t"
            :class="{ on: tab === t }"
            @click="tab = t"
          >
            {{ { device: 'The device', table: 'Rows', map: 'Mode map', settings: 'Settings' }[t] }}
          </button>
        </div>

        <div v-if="mode" class="mode-head">
          <h2>{{ docStore.selectedModeNumber }}. {{ mode.name }}</h2>
          <p v-if="budgetForMode" class="hint">
            {{ budgetForMode.rows_free }} of {{ docStore.budget!.rows_max }} rows still free
            ({{ budgetForMode.rows_active }} do something, {{ budgetForMode.rows_used }} used)
          </p>
        </div>

        <!-- the device ------------------------------------------------------- -->
        <section v-show="tab === 'device'" class="pane">
          <div class="device-cols">
            <DeviceView
              :selected-input="selectedInput"
              @select="selectInput"
              @hover="hoveredInputs = $event"
            />
            <!-- Ringed when the part being pointed at on the photo owns the input
                 this pane is showing, so hovering a tube marks everything it
                 drives — the tables under the photo and this pane alike. -->
            <div class="side card" :class="{ lit: sideLit }">
              <MappingEditor v-if="selectedInput" :input="selectedInput" />
              <p v-else class="hint">
                Click anything on the device to see what it does and change it.
              </p>
            </div>
          </div>
        </section>

        <!-- rows ------------------------------------------------------------- -->
        <section v-show="tab === 'table'" class="pane">
          <TableView />
        </section>

        <!-- mode map --------------------------------------------------------- -->
        <section v-show="tab === 'map'" class="pane">
          <ModeMap />
        </section>

        <!-- profile settings ------------------------------------------------- -->
        <section v-show="tab === 'settings'" class="pane stack">
          <div class="card pad">
            <h3>This profile</h3>
            <div class="grid-fields">
              <div class="field">
                <label for="p-name">Name</label>
                <input id="p-name" v-model="doc.name" class="input" type="text" />
              </div>
              <div class="field">
                <label for="p-game">Game</label>
                <input id="p-game" v-model="doc.game" class="input" type="text" />
              </div>
              <div class="field">
                <label for="p-file">Filename on the QuadStick</label>
                <input id="p-file" v-model="doc.csv_filename" class="input" type="text" />
                <p class="hint">Ends in .csv, no spaces or commas.</p>
              </div>
              <div class="field">
                <label for="p-console">Button names</label>
                <select id="p-console" v-model="doc.console" class="input">
                  <option value="playstation">PlayStation</option>
                  <option value="xbox">Xbox</option>
                </select>
              </div>
              <div class="field">
                <label for="p-fw">Firmware on the QuadStick</label>
                <select id="p-fw" v-model.number="doc.firmware" class="input">
                  <option v-for="f in firmwares" :key="f" :value="f">{{ f }}</option>
                </select>
                <p class="hint">
                  Decides which pretend-controller modes hide the flash drive. The owner's
                  device runs {{ catalog.catalog?.default_firmware ?? 2373 }}.
                </p>
              </div>
              <div class="field wide-field">
                <label for="p-emu">How it pretends to be a controller</label>
                <select id="p-emu" v-model="emulationMode" class="input">
                  <option value="">not set</option>
                  <option v-if="emulationUnlisted" :value="emulationMode">
                    (current) {{ emulationMode }}
                  </option>
                  <option v-for="e in emulationModes" :key="e.value" :value="e.value">
                    {{ e.label }}
                  </option>
                </select>
                <p v-if="driveWarning" class="hint drive">
                  This one <b>hides the flash drive</b> on firmware {{ doc.firmware }}. You
                  would not be able to copy a fixed profile across — keep one you know
                  works on the drive first.
                </p>
                <p v-else-if="driveWarning === null" class="hint drive">
                  {{ unknownFirmwareWarning(doc.firmware, emulationMode) }}
                </p>
                <p v-else-if="emulationMode !== ''" class="hint">
                  The flash drive stays visible on firmware {{ doc.firmware }}. Good.
                </p>
                <p v-else class="hint">
                  Not set, so the device uses its own (prefs.csv). The owner's PlayStation
                  profiles use <b>4</b>.
                </p>
                <p class="hint">
                  Written to the file as its
                  <span class="mono">enable_DS3_emulation</span> preference row.
                </p>
              </div>
              <div class="field">
                <label for="p-channel">Connected by</label>
                <select id="p-channel" v-model="channel" class="input" :disabled="!doc.modes.length">
                  <option v-if="channel === 'mixed'" value="mixed" disabled>
                    mixed — differs between modes
                  </option>
                  <option v-for="c in CHANNEL_OPTIONS" :key="c.value" :value="c.value">
                    {{ c.label }}
                  </option>
                </select>
                <p class="hint">Every mode carries its own; picking one here sets them all.</p>
              </div>
            </div>
          </div>

          <div class="card pad">
            <h3>What you call each input</h3>
            <p class="hint">
              Only changes what this app and the printed card call it. The QuadStick still
              reads the real keyword.
            </p>
            <div class="grid-fields">
              <div v-for="i in renameableInputs" :key="i" class="field">
                <label :for="`in-${i}`">{{ catalog.inputLabel(i) }} <code class="mono">{{ i }}</code></label>
                <input
                  :id="`in-${i}`"
                  class="input"
                  type="text"
                  :value="doc.input_names[i] ?? ''"
                  :placeholder="catalog.inputLabel(i)"
                  @input="docStore.setInputName(i, ($event.target as HTMLInputElement).value)"
                />
              </div>
            </div>
          </div>

          <div class="card pad">
            <h3>Settings for this profile</h3>
            <p class="hint">
              These win over the QuadStick's own settings while this profile is loaded.
              Leave one blank and the device decides —
              <RouterLink to="/device">its settings are here</RouterLink>.
            </p>
            <PreferencesEditor
              :values="doc.preferences"
              inherited-from="the QuadStick's own settings"
              :inherited="prefs.values"
              @update="docStore.setPreference"
            />
          </div>
        </section>
      </main>
    </div>

    <!-- problems, under the work. They belong beside nothing in particular, and
         as a right-hand rail they stole width the device pane needed. -->
    <section class="problems-strip card">
      <h2>{{ panelTitle }}</h2>
      <p v-if="docStore.checking" class="hint" role="status">Checking…</p>

      <!-- Things to fix: errors block the export, warnings are worth a look. -->
      <ul v-if="toFix.length" class="problems">
        <li v-for="(f, i) in toFix" :key="`fix-${i}`" :class="f.severity">
          <button type="button" class="jump" @click="goToFinding(f)">
            <b v-if="f.mode !== null">Mode {{ f.mode }}<template v-if="f.row"> · row {{ f.row }}</template></b>
            <span>{{ f.message }}</span>
          </button>
        </li>
      </ul>

      <!-- Notes describe what the profile does. A profile can be exactly right and
           still have plenty of these, so they are kept apart from the list above:
           mixed in, a deliberate design read as a fault the owner had to defend. -->
      <details v-if="notes.length" class="notes" :open="!toFix.length">
        <summary>
          What this profile does
          <small>{{ notes.length }} {{ notes.length === 1 ? 'note' : 'notes' }} — nothing to fix</small>
        </summary>
        <ul class="problems">
          <li v-for="(f, i) in notes" :key="`note-${i}`" class="info">
            <button type="button" class="jump" @click="goToFinding(f)">
              <b v-if="f.mode !== null">Mode {{ f.mode }}<template v-if="f.row"> · row {{ f.row }}</template></b>
              <span>{{ f.message }}</span>
            </button>
          </li>
        </ul>
      </details>

      <p v-if="!toFix.length && !notes.length" class="hint">
        This profile will load and behave as written.
      </p>
    </section>

    <!-- the bottom bar, always saying what the device would do ---------------- -->
    <BottomBar :severity="docStore.worst">
      <p class="consequence">{{ consequence }}</p>
      <div class="spacer" />
      <p v-if="docStore.budget" class="hint counts">
        {{ docStore.budget.modes_used }}/{{ docStore.budget.modes_max }} modes
      </p>
      <button
        class="btn btn--small"
        type="button"
        :disabled="!docStore.dirty || docStore.saving"
        @click="docStore.revert()"
      >
        Undo my changes
      </button>
      <button
        class="btn btn--small btn--primary"
        type="button"
        :disabled="!docStore.dirty || docStore.saving"
        @click="docStore.save()"
      >
        {{ docStore.saving ? 'Saving…' : docStore.dirty ? 'Save' : 'Saved' }}
      </button>
      <button class="btn btn--small" type="button" @click="printCard">
        Print detailed sheets
      </button>
      <button class="btn btn--small" type="button" @click="printSummary">Print summary</button>
      <button
        class="btn btn--small"
        type="button"
        :disabled="!docStore.canExport"
        :title="docStore.canExport ? '' : 'Fix the errors first — the QuadStick would not read this'"
        @click="doExport"
      >
        Export CSV
      </button>
    </BottomBar>
  </div>

  <ExportChecklist
    :open="exported !== null"
    :download="exported"
    :profile-name="doc?.name ?? ''"
    @close="exported = null"
  />

  <!-- export refused ------------------------------------------------------- -->
  <ModalDialog :open="blocked !== null" title="Export refused" @close="blocked = null">
    <template v-if="blocked">
      <p>{{ blocked.message }}</p>
      <FindingsList :validation="blocked.validation" />
    </template>
    <template #actions>
      <button class="btn btn--primary" type="button" @click="blocked = null">Close</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.editor-shell {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding-bottom: 5rem; /* clear of the fixed bottom bar */
}

/* The editor holds three columns plus a grid, so it needs more width than the
   library's reading measure. It breaks out of the page's centred measure and sits
   1cm from each screen edge — centring it wasted a wide gutter on the left while
   the device pane had nothing to do with the space.

   #main, not `main`: the editor nests its own <main class="work"> inside the page
   one, so a bare element selector would hit both. The id also outweighs App.vue's
   scoped `main` rule, which would otherwise keep the 1180px cap. */
:global(#main:has(.editor-shell)) {
  max-width: none;
  margin: 0;
  padding-inline: 1cm;
}

.crumb {
  margin: 0;
  font-size: var(--text-sm);
}
.head {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-4);
  flex-wrap: wrap;
}
.head h1 {
  margin: 0;
  font-size: var(--text-xl);
}
.facts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1) var(--sp-3);
  margin: 0;
  font-size: var(--text-sm);
  color: var(--ink-soft);
}
.facts span + span::before {
  content: '·';
  margin-right: var(--sp-3);
  color: var(--line-strong);
}

.banner--error {
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--error-soft);
  color: var(--error);
}
.warn {
  margin: 0;
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--warning-soft);
  color: var(--warning);
  font-weight: 600;
  font-size: var(--text-sm);
}

.layout {
  display: grid;
  grid-template-columns: 18rem minmax(0, 1fr);
  gap: var(--sp-3);
  align-items: start;
}

.rail-col {
  padding: var(--sp-3);
  position: sticky;
  top: var(--sp-3);
  max-height: calc(100vh - 8rem);
  overflow-y: auto;
}

/* Findings read fine in a few short columns under the work, and this way they do
   not compete with the device pane for width. */
.problems-strip {
  padding: var(--sp-3);
}
.problems-strip h2 {
  margin: 0 0 var(--sp-2);
  font-size: var(--text-base);
}

/* --- "What this profile does" --------------------------------------------- */
/* Folded away while there is anything to fix, so the short list of real problems
   is not buried under a long list of notes; open by default once the profile is
   clean, where the notes are the only thing left to read. */
.notes {
  margin-top: var(--sp-3);
  border-top: 1px solid var(--line);
  padding-top: var(--sp-2);
}
.notes summary {
  min-height: var(--target);
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  cursor: pointer;
  font-weight: 600;
  font-size: var(--text-sm);
}
.notes summary small {
  font-weight: 400;
  color: var(--ink-soft);
}
.notes summary:focus-visible {
  outline: var(--focus);
  outline-offset: var(--focus-offset);
}
.notes .problems {
  margin-top: var(--sp-2);
}

.work {
  min-width: 0;
}

.tabs {
  display: flex;
  gap: var(--sp-1);
  flex-wrap: wrap;
  margin-bottom: var(--sp-3);
}
.tab {
  min-height: var(--target);
  padding: 0 var(--sp-4);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--paper);
  font-weight: 600;
  font-size: var(--text-sm);
  cursor: pointer;
}
.tab.on {
  background: var(--mode);
  border-color: var(--mode);
  color: #fff;
}

.mode-head {
  margin-bottom: var(--sp-3);
}
.mode-head h2 {
  margin: 0;
  font-size: var(--text-lg);
}
.mode-head .hint {
  margin: 0;
}

/* One column by default: the grid needs ~430px and the mapping panel ~19rem, so
   they only sit side by side once there is room for both.

   This is a container query, not a media query: the shell is capped at 1560px and
   sits between two rails, so the viewport width says nothing useful about how much
   room this pane actually has. */
.pane {
  container-type: inline-size;
}
.device-cols {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-4);
  align-items: start;
}
.device-cols > * {
  min-width: 0;
}
/* The device pane now puts its photo and tables side by side, so the mapping
   panel only joins them once there is room for all three. */
@container (min-width: 1340px) {
  .device-cols {
    grid-template-columns: minmax(0, 1fr) 19rem;
  }
}
.pane {
  min-width: 0;
}
.side {
  padding: var(--sp-3);
  position: sticky;
  top: var(--sp-3);
}
/* The same ring the device view puts round a part's tables, so pointing at a tube
   marks everything it drives in one colour. Outline, not border, so the pane does
   not shift as it lights. */
.side.lit {
  outline: 3px solid var(--callout-edge);
  outline-offset: 3px;
}

.pad {
  padding: var(--sp-4);
}
.pad h3 {
  margin-top: 0;
}

.wide-field {
  grid-column: 1 / -1;
}
.drive {
  color: var(--warning);
  font-weight: 600;
}

.grid-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--sp-3);
}

details {
  border-top: 1px solid var(--line);
  padding: var(--sp-2) 0;
}
summary {
  min-height: var(--target);
  display: flex;
  align-items: center;
  font-weight: 600;
  cursor: pointer;
}

.problems {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
  gap: var(--sp-1) var(--sp-3);
  align-items: start;
}
.problems li {
  border-left: 4px solid var(--line);
}
.problems li.error {
  border-color: var(--error);
}
.problems li.warning {
  border-color: var(--warning);
}
.problems li.info {
  border-color: var(--line-strong);
}
.jump {
  display: block;
  width: 100%;
  padding: var(--sp-2);
  border: 0;
  background: transparent;
  text-align: left;
  font: inherit;
  font-size: var(--text-xs);
  cursor: pointer;
}
.jump:hover {
  background: var(--paper-sunk);
}
.jump b {
  display: block;
}

.consequence {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
}
.counts {
  margin: 0;
}

/* Below this the three columns cannot all hold their content, so they stack and
   the work column gets the full width. */
@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .rail-col,
  .side {
    position: static;
    max-height: none;
  }
}
</style>
