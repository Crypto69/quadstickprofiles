<script setup lang="ts">
/**
 * The QuadStick's own settings — its `prefs.csv`. These apply to every profile,
 * so this page explains the precedence up front and is honest that the file has to
 * be copied across by hand like any other.
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import BottomBar from '@/components/BottomBar.vue'
import FindingsList from '@/components/FindingsList.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import PreferencesEditor from '@/components/PreferencesEditor.vue'
import type { Download } from '@/api/client'
import { saveBlob } from '@/composables/useDownload'
import { isDesktop } from '@/desktop'
import { useFilePicker } from '@/composables/useFilePicker'
import { useCatalogStore } from '@/stores/catalog'
import { usePrefsStore } from '@/stores/prefs'

const catalog = useCatalogStore()
const prefs = usePrefsStore()

const exported = ref<Download | null>(null)
const desktop = isDesktop()

onMounted(async () => {
  await catalog.load().catch(() => {})
  // Judge the settings against the owner's firmware unless a page already chose one.
  if (prefs.firmware === null) prefs.firmware = catalog.catalog?.default_firmware ?? null
  await prefs.load()
})

const firmwares = computed(() => catalog.catalog?.firmware_versions ?? [])

/**
 * A different firmware means a different set of drive-hiding modes, so the API
 * re-checks the saved settings. Unsaved edits stay put: the next save is judged
 * against the new firmware anyway.
 */
function firmwareChanged() {
  if (!prefs.dirty) void prefs.load()
}

/**
 * The drive warning is decided here from the catalog, live against the value on
 * screen, not by matching the API's prose: whether an emulation mode hides the
 * flash drive is a fact of the firmware table, and prefs.csv applies at every
 * boot, so a mistake here would hide the drive for every profile.
 */
const emulationValue = computed(() => prefs.values.enable_DS3_emulation ?? '')
const emulationNumber = computed(() => {
  const raw = emulationValue.value.trim()
  return /^\d+$/.test(raw) ? Number(raw) : null
})
/** true: hides the drive. false: stays visible. null: unknown firmware, cannot tell. */
const driveWarning = computed(() =>
  catalog.hidesFlashDrive(
    emulationNumber.value,
    prefs.firmware ?? catalog.catalog?.default_firmware ?? 0,
  ),
)

const { fileInput, pickFile, onFileChosen } = useFilePicker((file) => prefs.importFile(file))

async function doExport() {
  const dl = await prefs.exportFile()
  if (!dl) return
  exported.value = dl
  saveBlob(dl.blob, dl.filename, dl.exportPath)
}
</script>

<template>
  <div class="stack">
    <header class="head">
      <div>
        <h1>The QuadStick's own settings</h1>
        <p class="lede">
          These apply whatever profile is loaded. A profile can set its own value for any
          of them, and that wins while it is loaded.
        </p>
      </div>
      <div class="spacer" />
      <button class="btn" type="button" @click="pickFile">Import prefs.csv…</button>
      <button
        class="btn"
        type="button"
        :disabled="!prefs.canExport"
        :title="prefs.canExport ? '' : 'Nothing to export yet, or there are errors to fix'"
        @click="doExport"
      >
        Export prefs.csv
      </button>
      <input
        ref="fileInput"
        class="sr-only"
        type="file"
        accept=".csv"
        aria-label="Choose a prefs.csv to import"
        @change="onFileChosen"
      />
    </header>

    <ol class="precedence">
      <li>
        <b>Here</b> — the device's <span class="mono">prefs.csv</span>.
        <RouterLink to="/learn/settings">How this works</RouterLink>
      </li>
      <li>Then <b>the profile</b>, while that file is loaded.</li>
      <li>Then <b>one mode</b> inside it, while that mode is active.</li>
    </ol>

    <p v-if="prefs.error" class="banner--error" role="alert">{{ prefs.error }}</p>

    <div v-if="prefs.refused" class="banner--error">
      <p><b>Those values were not saved.</b></p>
      <FindingsList :validation="prefs.refused" />
    </div>

    <div class="field firmware">
      <label for="prefs-fw">Firmware on the QuadStick</label>
      <select id="prefs-fw" v-model.number="prefs.firmware" class="input" @change="firmwareChanged">
        <option v-for="f in firmwares" :key="f" :value="f">{{ f }}</option>
      </select>
      <p class="hint">
        Decides which pretend-controller modes hide the flash drive. The owner's device
        runs {{ catalog.catalog?.default_firmware ?? 2373 }}.
      </p>
    </div>

    <p v-if="driveWarning" class="warn">
      Emulation mode {{ emulationValue }} hides the flash drive on firmware
      {{ prefs.firmware }}. Set device-wide, that applies to every profile at every boot:
      you could not copy a fixed file across, and getting the drive back needs a hardware
      reset. Pick a mode that keeps it visible, or set it in one profile instead.
    </p>
    <p v-else-if="driveWarning === null" class="warn">
      Firmware {{ prefs.firmware }} is not one this app knows, so it cannot tell whether
      emulation mode {{ emulationValue }} keeps the flash drive visible. Set device-wide,
      a wrong guess hides the drive for every profile.
    </p>

    <p v-if="prefs.loading" role="status">Loading…</p>

    <template v-else>
      <PreferencesEditor
        :values="prefs.values"
        inherited-from="the QuadStick's own built-in value"
        @update="prefs.set"
      />

      <section v-if="prefs.validation?.findings.length" class="card pad">
        <h2>Checks</h2>
        <FindingsList :validation="prefs.validation" :collapse-info="false" />
      </section>
    </template>
  </div>

  <BottomBar :severity="prefs.validation?.errors ? 'error' : null">
    <p class="msg">
      <template v-if="prefs.dirty">Not saved yet.</template>
      <template v-else>Saved. Export the file and copy it onto the flash drive.</template>
    </p>
    <div class="spacer" />
    <button
      class="btn btn--small"
      type="button"
      :disabled="!prefs.dirty || prefs.saving"
      @click="prefs.revert()"
    >
      Undo my changes
    </button>
    <button
      class="btn btn--small btn--primary"
      type="button"
      :disabled="!prefs.dirty || prefs.saving"
      @click="prefs.save()"
    >
      {{ prefs.saving ? 'Saving…' : prefs.dirty ? 'Save' : 'Saved' }}
    </button>
  </BottomBar>

  <ModalDialog
    :open="exported !== null"
    title="Put these settings on the QuadStick"
    @close="exported = null"
  >
    <p v-if="exported">
      <b>{{ exported.filename }}</b> was saved.
    </p>
    <p v-if="exported?.exportPath" class="hint">
      <template v-if="desktop">Saved to <span class="mono">{{ exported.exportPath }}</span>.</template>
      <template v-else
        >The server also wrote it to <span class="mono">{{ exported.exportPath }}</span>.</template
      >
    </p>
    <ol class="steps">
      <li>
        Copy <span class="mono">prefs.csv</span> to the top level of the QuadStick's flash
        drive, replacing the one already there.
      </li>
      <li>
        Eject the drive, then unplug and replug the QuadStick — it only re-reads its drive
        at power-on. At boot it deletes every non-.csv file (except
        <span class="mono">joystick.bin</span>) and every dot-file, so keep backups off the
        stick.
      </li>
      <li>
        Leave <span class="mono">default.csv</span> alone — that one is a profile, not
        settings, and breaking it hides the drive.
      </li>
    </ol>
    <template #actions>
      <button class="btn btn--primary" type="button" @click="exported = null">Done</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.stack {
  padding-bottom: 5rem;
}

.head {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.head h1 {
  margin: 0 0 var(--sp-1);
}
.lede {
  margin: 0;
  color: var(--ink-soft);
  max-width: 44rem;
}

.precedence {
  margin: 0;
  padding-left: 1.4rem;
  font-size: var(--text-sm);
}
.precedence li {
  margin-bottom: 2px;
}

.firmware {
  max-width: 24rem;
}

.banner--error {
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--error-soft);
  color: var(--error);
}
.banner--error p {
  margin: 0 0 var(--sp-2);
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

.pad {
  padding: var(--sp-4);
}
.pad h2 {
  margin-top: 0;
  font-size: var(--text-lg);
}

.steps {
  padding-left: 1.4rem;
}
.steps li {
  margin-bottom: var(--sp-2);
}

.msg {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
}
</style>
