<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import ExportChecklist from '@/components/ExportChecklist.vue'
import FindingsList from '@/components/FindingsList.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import ValidationBadge from '@/components/ValidationBadge.vue'
import type { Download } from '@/api/client'
import { api } from '@/api/client'
import type { Console, ProfileSummary } from '@/api/types'
import { saveBlob } from '@/composables/useDownload'
import { openExternal } from '@/composables/useExternalLink'
import { useFilePicker } from '@/composables/useFilePicker'
import { unknownFirmwareWarning } from '@/device/flashDrive'
import { convertedName, copyName, csvFilenameForName } from '@/lib/filename'
import { useCatalogStore } from '@/stores/catalog'
import { useProfilesStore } from '@/stores/profiles'

const store = useProfilesStore()
const catalog = useCatalogStore()

const exported = ref<Download | null>(null)
const exportedFrom = ref('')
const confirmDelete = ref<ProfileSummary | null>(null)
const newProfile = ref<{
  open: boolean
  name: string
  filename: string
  game: string
  /** null = start blank; otherwise the starter profile to copy. */
  from: number | null
}>({ open: false, name: '', filename: '', game: '', from: null })

// The catalog answers the drive-hiding question per firmware, so the warning on a
// library row depends on it. App.vue loads it too; load() is cached and shared, so
// asking again here costs nothing and stops the warning depending on load order.
onMounted(() => {
  store.load()
  store.loadTemplates()
  catalog.load().catch(() => {
    /* App.vue shows the connection banner */
  })
})

// Debounced search: one request after typing stops, not one per keystroke.
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(
  () => store.search,
  () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => store.load(), 250)
  },
)

const empty = computed(() => !store.loading && store.profiles.length === 0)
const searching = computed(() => store.search.trim().length > 0)
/** Loaded profiles exist, but every one is filtered out. A different, fixable state. */
const filteredOut = computed(
  () => !store.loading && store.profiles.length > 0 && store.visible.length === 0,
)

/**
 * Filter-chip names for the emulation modes. The catalog's own strings spell out the
 * hardware ("DualShock 4 (PS4 / PS5 via adapter)") because a validation message has to
 * be unambiguous; a row of chips has no room for that, so these are the short forms.
 * Anything the catalog gains beyond this list still gets a chip, under its own name.
 */
const SHORT_MODE_LABELS: Record<number, string> = {
  0: 'PC / Mac / PS3',
  1: 'PS3 (DualShock 3)',
  2: 'x360ce',
  3: 'Xbox 360',
  4: 'PS4 / PS5',
  5: 'Switch',
  6: 'PS4 / PS5, no drive',
  7: 'PS4 wireless',
}

/**
 * The device chips to offer: the emulation modes some profile actually uses, plus any
 * still ticked, so unticking the last profile of a mode does not yank the chip out from
 * under the pointer mid-click.
 */
const emulationChips = computed(() =>
  Object.entries(catalog.catalog?.emulation_modes ?? {})
    .map(([k, full]) => ({ mode: Number(k), label: SHORT_MODE_LABELS[Number(k)] ?? full, full }))
    .filter((e) => store.presentEmulations.has(e.mode) || store.emulationFilter.has(e.mode))
    .sort((a, b) => a.mode - b.mode),
)

const consoleChips = computed(() =>
  (['playstation', 'xbox'] as Console[]).filter(
    (c) => store.presentConsoles.has(c) || store.consoleFilter.has(c),
  ),
)

/**
 * A group with one chip cannot narrow anything — every profile already matches it — so
 * it is only noise. The bar itself goes when that leaves nothing worth showing.
 */
const showConsoleGroup = computed(() => consoleChips.value.length > 1)
const showEmulationGroup = computed(() => emulationChips.value.length > 1)
const showFilters = computed(() => showConsoleGroup.value || showEmulationGroup.value)

function consoleLabel(c: Console) {
  return c === 'xbox' ? 'Xbox' : 'PlayStation'
}

/** The other naming set, i.e. what "convert" would produce. */
function otherConsole(c: Console): Console {
  return c === 'xbox' ? 'playstation' : 'xbox'
}

function updated(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

/**
 * Warn on the library card when a profile would hide the flash drive. `null` is a
 * firmware the catalog does not know, which gets its own warning: the card must not
 * stay silent as if the drive were safe.
 */
function driveWarning(p: ProfileSummary) {
  return catalog.hidesFlashDrive(p.emulation_mode, p.firmware)
}

// ------------------------------------------------------------------ actions
const { fileInput, pickFile, onFileChosen } = useFilePicker((file) => store.importFile(file))

async function doExport(p: ProfileSummary) {
  const dl = await store.exportFile(p.id, 'csv')
  if (!dl) return // a 409 sets store.blocked, which the dialog below shows
  exported.value = dl
  exportedFrom.value = p.name
  // Hand the file over straight away; the checklist can save it again.
  saveBlob(dl.blob, dl.filename, dl.exportPath)
}

function printCard(p: ProfileSummary) {
  // The card is a generated HTML page with its own print stylesheet, so it prints
  // from its own tab (or the system browser, in the desktop build) rather than
  // through this app's layout.
  openExternal(api.cardUrl(p.id))
}

function printSummary(p: ProfileSummary) {
  // Same deal, but the compact three-column sheet for taping next to the monitor.
  openExternal(api.summaryUrl(p.id))
}

// ---------------------------------------------------------- name and filename
/**
 * The QuadStick loads a profile by its *filename*. Duplicate used to fire straight
 * away and invent both halves, leaving a name and a file that told different stories
 * ("cvcodww2 (copy)" living in `cvcodww2_copy.csv`) and no way to tell which file on
 * the stick was which without going hunting. So all three now ask, and the filename
 * box fills itself in from the name as it is typed: name a copy once and the pair
 * matches for free.
 *
 * Making them differ is then perfectly fine and nothing complains — the firmware
 * never reads the name, so a descriptive label beside a terse filename is a good
 * profile, not a broken one. The auto-fill is a convenience, not a rule.
 */
type NameJob =
  | { kind: 'duplicate'; profile: ProfileSummary }
  | { kind: 'convert'; profile: ProfileSummary; target: Console }
  | { kind: 'rename'; profile: ProfileSummary }

const job = ref<NameJob | null>(null)
const jobName = ref('')
/** Empty means "follow the name"; anything typed here is the user's own choice and
 *  is never rewritten from under them. */
const jobFilename = ref('')

const JOB_TITLES: Record<NameJob['kind'], string> = {
  duplicate: 'Make a copy',
  convert: 'Convert to the other button names',
  rename: 'Rename this profile',
}
const JOB_CONFIRM: Record<NameJob['kind'], string> = {
  duplicate: 'Make the copy',
  convert: 'Convert',
  rename: 'Save',
}

const jobTitle = computed(() => (job.value ? JOB_TITLES[job.value.kind] : ''))
const jobConfirm = computed(() => (job.value ? JOB_CONFIRM[job.value.kind] : ''))

/** What the filename field will send: what was typed, else what the name suggests. */
const jobFilenameFinal = computed(
  () => jobFilename.value.trim() || csvFilenameForName(jobName.value),
)

function openJob(next: NameJob) {
  job.value = next
  const p = next.profile
  jobName.value =
    next.kind === 'duplicate'
      ? copyName(p.name)
      : next.kind === 'convert'
        ? convertedName(p.name, next.target)
        : p.name
  // Rename starts from what the profile has now, so an untouched save changes nothing.
  // The other two start empty, so the field follows the name as it is typed.
  jobFilename.value = next.kind === 'rename' ? p.csv_filename : ''
  store.dismissError()
}

function closeJob() {
  job.value = null
}

/**
 * Guarded on both sides, like Delete: a second activation while the first request is
 * away would send it twice, and this audience activates a button twice more readily
 * than most. The dialog closes only on success, so a failure stays where it can be
 * read instead of vanishing behind the scrim.
 */
async function runJob() {
  const j = job.value
  if (!j || store.busyId === j.profile.id) return
  const name = jobName.value.trim()
  if (!name) return
  const csv_filename = jobFilenameFinal.value
  const ok =
    j.kind === 'duplicate'
      ? await store.duplicate(j.profile.id, { name, csv_filename })
      : j.kind === 'convert'
        ? await store.convert(j.profile.id, j.target, { name, csv_filename })
        : await store.rename(j.profile.id, { name, csv_filename })
  if (ok) job.value = null
}

async function createProfile() {
  const name = newProfile.value.name.trim()
  const filename = newProfile.value.filename.trim() || csvFilenameForName(name)
  const game = newProfile.value.game.trim() || undefined
  const from = newProfile.value.from
  const p = from
    ? await store.createFromTemplate(from, { name, csv_filename: filename, game })
    : await store.create({ name, csv_filename: filename, game })
  if (p) newProfile.value = { open: false, name: '', filename: '', game: '', from: null }
}

/**
 * Delete, guarded on both sides. A second activation while the first DELETE is
 * running would send it twice and show the second one's 404 as an error after the
 * first succeeded — and this audience activates a button twice more easily than
 * most. The dialog closes only on success, so a failure stays where the user can
 * read it instead of vanishing behind a banner they never see.
 */
async function doDelete() {
  const p = confirmDelete.value
  if (!p || store.busyId === p.id) return
  if (await store.remove(p.id)) confirmDelete.value = null
}

/** Prefill the name and game from the starter, so one click is usually enough. */
function chooseStart(id: number | null) {
  newProfile.value.from = id
  const t = store.templates.find((x) => x.id === id)
  if (t && !newProfile.value.name.trim()) {
    newProfile.value.name = t.game ?? t.name
    newProfile.value.game = t.game ?? ''
  }
}

const suggestedFilename = computed(
  () => newProfile.value.filename.trim() || csvFilenameForName(newProfile.value.name),
)
</script>

<template>
  <div class="stack">
    <header class="head">
      <h1>Profiles</h1>
      <div class="spacer" />
      <div class="field search">
        <label for="search">Search by game or name</label>
        <input
          id="search"
          v-model="store.search"
          class="input"
          type="search"
          placeholder="Fortnite…"
          autocomplete="off"
        />
      </div>
      <button class="btn" type="button" @click="pickFile">Import a file…</button>
      <button class="btn btn--primary" type="button" @click="newProfile.open = true">
        New profile
      </button>
      <input
        ref="fileInput"
        class="sr-only"
        type="file"
        accept=".csv,.xlsx"
        :aria-label="'Choose a .xlsx or .csv profile to import'"
        @change="onFileChosen"
      />
    </header>

    <p class="hint">
      Import the <b>.xlsx</b> you downloaded from the Google Sheet (File → Download → Excel), or a
      <b>.csv</b> copied off the QuadStick. Nothing is sent anywhere; this runs on your own machine.
    </p>

    <!-- Filters. Only groups that can actually narrow the list appear; with one profile,
         or one kind of profile, the whole bar would be clutter above the answer. -->
    <section v-if="showFilters" class="filters" aria-label="Filter profiles">
      <fieldset v-if="showConsoleGroup" class="group">
        <legend>Button names</legend>
        <label
          v-for="c in consoleChips"
          :key="c"
          class="chip"
          :class="{ on: store.consoleFilter.has(c) }"
        >
          <input
            type="checkbox"
            :checked="store.consoleFilter.has(c)"
            @change="store.toggleConsole(c)"
          />
          <span>{{ consoleLabel(c) }}</span>
          <span class="count">{{ store.consoleCounts.get(c) ?? 0 }}</span>
        </label>
      </fieldset>

      <fieldset v-if="showEmulationGroup" class="group">
        <legend>Device</legend>
        <label
          v-for="e in emulationChips"
          :key="e.mode"
          class="chip"
          :class="{ on: store.emulationFilter.has(e.mode) }"
          :title="e.full"
        >
          <input
            type="checkbox"
            :checked="store.emulationFilter.has(e.mode)"
            @change="store.toggleEmulation(e.mode)"
          />
          <span>{{ e.label }}</span>
          <span class="count">{{ store.emulationCounts.get(e.mode) ?? 0 }}</span>
        </label>
      </fieldset>

      <button
        v-if="store.filtering"
        class="btn btn--small btn--quiet"
        type="button"
        @click="store.clearFilters()"
      >
        Clear filters
      </button>
    </section>

    <p v-if="store.error" class="banner banner--error" role="alert">{{ store.error }}</p>

    <p v-if="store.loading" role="status">Loading…</p>

    <p v-else-if="empty && searching">
      No profile matches “{{ store.search }}”.
      <button class="btn btn--small btn--quiet" type="button" @click="store.search = ''">
        Clear the search
      </button>
    </p>

    <p v-else-if="filteredOut">
      No profile matches the filters you ticked.
      <button class="btn btn--small btn--quiet" type="button" @click="store.clearFilters()">
        Clear filters
      </button>
    </p>

    <section v-else-if="empty" class="card empty">
      <h2>Nothing here yet</h2>
      <p>
        Import a profile to get started. A Google Sheet download (<span class="mono">.xlsx</span>)
        and a file from the QuadStick (<span class="mono">.csv</span>) both work.
      </p>
      <button class="btn btn--primary" type="button" @click="pickFile">Import a file…</button>
    </section>

    <ul v-else class="profiles">
      <li v-for="p in store.visible" :key="p.id" class="card profile">
        <div class="main">
          <h2>
            <RouterLink :to="`/profiles/${p.id}`">{{ p.name }}</RouterLink>
          </h2>
          <p class="facts">
            <span v-if="p.game">{{ p.game }}</span>
            <span>{{ consoleLabel(p.console) }} names</span>
            <span class="mono">{{ p.csv_filename }}</span>
            <span>{{ p.mode_count }} {{ p.mode_count === 1 ? 'mode' : 'modes' }}</span>
            <span>Edited {{ updated(p.updated_at) }}</span>
          </p>
          <p v-if="driveWarning(p)" class="drive-warning">
            Emulation mode {{ p.emulation_mode }} hides the flash drive on firmware
            {{ p.firmware }}. A mistake in this profile needs the side-tube recovery.
          </p>
          <p v-else-if="driveWarning(p) === null" class="drive-warning">
            {{ unknownFirmwareWarning(p.firmware, p.emulation_mode ?? '') }}
          </p>
        </div>

        <div class="badges">
          <ValidationBadge :validation="p.validation" />
        </div>

        <div class="actions">
          <RouterLink class="btn btn--small" :to="`/profiles/${p.id}`">Open</RouterLink>
          <button
            class="btn btn--small"
            type="button"
            :disabled="store.busyId === p.id || !store.canExport(p)"
            :title="store.canExport(p) ? '' : 'Fix the errors first — the QuadStick would not read this'"
            @click="doExport(p)"
          >
            Export CSV
          </button>
          <button class="btn btn--small" type="button" @click="printCard(p)">
            Print detailed sheets
          </button>
          <button class="btn btn--small" type="button" @click="printSummary(p)">
            Print summary
          </button>
          <button
            class="btn btn--small"
            type="button"
            title="Change the name and the filename the QuadStick loads it by"
            @click="openJob({ kind: 'rename', profile: p })"
          >
            Rename
          </button>
          <button
            class="btn btn--small"
            type="button"
            :disabled="store.busyId === p.id"
            @click="openJob({ kind: 'duplicate', profile: p })"
          >
            Duplicate
          </button>
          <button
            class="btn btn--small"
            type="button"
            :disabled="store.busyId === p.id"
            :title="`Make a copy using ${consoleLabel(otherConsole(p.console))} button names`"
            @click="openJob({ kind: 'convert', profile: p, target: otherConsole(p.console) })"
          >
            To {{ consoleLabel(otherConsole(p.console)) }}
          </button>
          <button class="btn btn--small btn--danger" type="button" @click="confirmDelete = p">
            Delete
          </button>
        </div>
      </li>
    </ul>
  </div>

  <!-- import findings ------------------------------------------------------ -->
  <ModalDialog
    :open="store.lastImport !== null"
    title="Imported"
    @close="store.dismissImport()"
  >
    <template v-if="store.lastImport">
      <p>
        <b>{{ store.lastImport.profile.name }}</b> imported with
        {{ store.lastImport.profile.modes.length }} modes, stored under
        {{ consoleLabel(store.lastImport.profile.console) }} names.
      </p>
      <p v-if="store.lastImport.findings.errors" class="hint">
        Export stays blocked until the errors are fixed.
      </p>
      <FindingsList :validation="store.lastImport.findings" :collapse-info="false" />
    </template>
    <template #actions>
      <RouterLink
        v-if="store.lastImport"
        class="btn btn--primary"
        :to="`/profiles/${store.lastImport.profile.id}`"
        @click="store.dismissImport()"
      >
        Open it
      </RouterLink>
      <button class="btn" type="button" @click="store.dismissImport()">Stay here</button>
    </template>
  </ModalDialog>

  <!-- export refused ------------------------------------------------------- -->
  <ModalDialog
    :open="store.blocked !== null"
    title="Export refused"
    @close="store.dismissBlocked()"
  >
    <template v-if="store.blocked">
      <p>{{ store.blocked.message }}</p>
      <FindingsList :validation="store.blocked.validation" />
    </template>
    <template #actions>
      <RouterLink
        v-if="store.blocked"
        class="btn btn--primary"
        :to="`/profiles/${store.blocked.profileId}`"
        @click="store.dismissBlocked()"
      >
        Open the profile
      </RouterLink>
      <button class="btn" type="button" @click="store.dismissBlocked()">Close</button>
    </template>
  </ModalDialog>

  <!-- export checklist ----------------------------------------------------- -->
  <ExportChecklist
    :open="exported !== null"
    :download="exported"
    :profile-name="exportedFrom"
    @close="exported = null"
  />

  <!-- new profile ---------------------------------------------------------- -->
  <ModalDialog
    :open="newProfile.open"
    title="New profile"
    @close="newProfile.open = false"
  >
    <div class="stack">
      <fieldset class="starts">
        <legend>Start from</legend>
        <label class="start" :class="{ on: newProfile.from === null }">
          <input
            type="radio"
            name="start"
            :checked="newProfile.from === null"
            @change="chooseStart(null)"
          />
          <span>
            <b>Nothing</b>
            <small>An empty profile. You add every mode and mapping yourself.</small>
          </span>
        </label>
        <label
          v-for="t in store.templates"
          :key="t.id"
          class="start"
          :class="{ on: newProfile.from === t.id }"
        >
          <input
            type="radio"
            name="start"
            :checked="newProfile.from === t.id"
            @change="chooseStart(t.id)"
          />
          <span>
            <b>{{ t.name }}</b>
            <small>{{ t.template_note }}</small>
            <small class="facts">
              {{ t.mode_count }} modes · {{ consoleLabel(t.console) }} names
            </small>
          </span>
        </label>
      </fieldset>

      <div class="field">
        <label for="np-name">Name</label>
        <input id="np-name" v-model="newProfile.name" class="input" type="text" />
      </div>
      <div class="field">
        <label for="np-game">Game (optional)</label>
        <input id="np-game" v-model="newProfile.game" class="input" type="text" />
      </div>
      <div class="field">
        <label for="np-file">Filename on the QuadStick</label>
        <input
          id="np-file"
          v-model="newProfile.filename"
          class="input"
          type="text"
          :placeholder="suggestedFilename"
        />
        <p class="hint">
          Must end in <span class="mono">.csv</span>, with no spaces or commas. Not
          <span class="mono">default.csv</span> — that one is special.
        </p>
      </div>
    </div>
    <template #actions>
      <button class="btn" type="button" @click="newProfile.open = false">Cancel</button>
      <button
        class="btn btn--primary"
        type="button"
        :disabled="!newProfile.name.trim() || store.loading"
        @click="createProfile"
      >
        Create
      </button>
    </template>
  </ModalDialog>

  <!-- rename / duplicate / convert ------------------------------------------ -->
  <!-- One dialog for all three, because all three ask the same question: what should
       this profile be called, and what should its file on the QuadStick be called. -->
  <ModalDialog :open="job !== null" :title="jobTitle" @close="closeJob()">
    <div v-if="job" class="stack">
      <p v-if="job.kind === 'duplicate'">
        A copy of <b>{{ job.profile.name }}</b>. It gets its own file, so both can sit on
        the QuadStick at once.
      </p>
      <p v-else-if="job.kind === 'convert'">
        A copy of <b>{{ job.profile.name }}</b> using
        {{ consoleLabel(job.target) }} button names. The original is left as it is.
      </p>
      <p v-else>
        <b>{{ job.profile.name }}</b> keeps all its modes and mappings. Renaming the file
        here does not rename the copy already on the QuadStick — export it again.
      </p>

      <div class="field">
        <label for="job-name">Name</label>
        <input id="job-name" v-model="jobName" class="input" type="text" />
      </div>
      <div class="field">
        <label for="job-file">Filename on the QuadStick</label>
        <input
          id="job-file"
          v-model="jobFilename"
          class="input"
          type="text"
          :placeholder="csvFilenameForName(jobName)"
        />
        <p class="hint">
          Follows the name unless you type your own. Must end in
          <span class="mono">.csv</span>, with no spaces or commas.
        </p>
      </div>

      <!-- the page banner sits behind the scrim, so a failure has to be said here -->
      <p v-if="store.error" class="banner banner--error" role="alert">{{ store.error }}</p>
    </div>
    <template #actions>
      <button class="btn" type="button" @click="closeJob()">Cancel</button>
      <button
        class="btn btn--primary"
        type="button"
        :disabled="!jobName.trim() || (job !== null && store.busyId === job.profile.id)"
        @click="runJob"
      >
        {{ jobConfirm }}
      </button>
    </template>
  </ModalDialog>

  <!-- delete --------------------------------------------------------------- -->
  <ModalDialog
    :open="confirmDelete !== null"
    title="Delete this profile?"
    @close="confirmDelete = null"
  >
    <p v-if="confirmDelete">
      <b>{{ confirmDelete.name }}</b> will be removed from this app. Any copy already on the
      QuadStick's flash drive stays there.
    </p>
    <!-- the page banner sits behind the scrim, so a failure has to be said here -->
    <p v-if="store.error" class="banner banner--error" role="alert">{{ store.error }}</p>
    <template #actions>
      <button class="btn" type="button" @click="confirmDelete = null">Keep it</button>
      <button
        class="btn btn--danger"
        type="button"
        :disabled="confirmDelete !== null && store.busyId === confirmDelete.id"
        @click="doDelete"
      >
        Delete
      </button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.head {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.head h1 {
  margin: 0;
}

.search {
  min-width: 16rem;
}

/* Filter bar --------------------------------------------------------------- */
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2) var(--sp-4);
}

.group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  margin: 0;
  padding: 0;
  border: 0;
}
.group legend {
  /* A floated legend sits inline with its chips instead of above them, which keeps
     the whole bar to one line on a wide screen. */
  float: left;
  padding: 0 var(--sp-2) 0 0;
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--ink-soft);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* The checkbox stays real (keyboard and screen readers get it for free) but the whole
   chip is the target, so a single pointer never has to hit the small square. */
.chip {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--target);
  padding: 0 var(--sp-3);
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--paper);
  font-size: var(--text-sm);
  cursor: pointer;
  user-select: none;
}
.chip:hover {
  border-color: var(--line-strong);
}
.chip.on {
  border-color: var(--mode);
  background: var(--mode-soft);
  font-weight: 600;
}
.chip input {
  width: 18px;
  height: 18px;
  flex: none;
  margin: 0;
}
.chip:focus-within {
  outline: var(--focus);
  outline-offset: var(--focus-offset);
}

.count {
  min-width: 1.25em;
  text-align: center;
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
  color: var(--ink-soft);
}
.chip.on .count {
  color: var(--ink);
}

.banner--error {
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--error-soft);
  color: var(--error);
}

.empty {
  padding: var(--sp-6);
  text-align: center;
}
.empty h2 {
  margin-top: 0;
}

.profiles {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.profile {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--sp-2) var(--sp-4);
  padding: var(--sp-4);
  align-items: start;
}

.main h2 {
  margin: 0 0 var(--sp-1);
  font-size: var(--text-lg);
}
.main h2 a {
  color: var(--ink);
  text-decoration: none;
}
.main h2 a:hover {
  text-decoration: underline;
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

.drive-warning {
  margin: var(--sp-2) 0 0;
  font-size: var(--text-sm);
  color: var(--warning);
  font-weight: 600;
}

.badges {
  grid-column: 2;
  grid-row: 1;
}

.actions {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  padding-top: var(--sp-2);
  border-top: 1px solid var(--line);
}

.starts {
  margin: 0;
  padding: 0;
  border: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.starts legend {
  padding: 0;
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--ink-soft);
}

/* Each choice is a whole label, so one click anywhere on it selects — no need to
   hit a small radio button. */
.start {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  min-height: var(--target);
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
}
.start.on {
  border-color: var(--mode);
  background: var(--mode-soft);
}
.start input {
  width: 20px;
  height: 20px;
  margin-top: 2px;
  flex: none;
}
.start b {
  display: block;
}
.start small {
  display: block;
  color: var(--ink-soft);
  font-size: var(--text-sm);
}
.start .facts {
  color: var(--ink-faint);
  font-size: var(--text-xs);
}

@media (max-width: 640px) {
  .profile {
    grid-template-columns: 1fr;
  }
  .badges {
    grid-column: 1;
    grid-row: auto;
  }
}
</style>
