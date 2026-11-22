<script setup lang="ts">
// Backing up and restoring the QuadStick's flash drive, from the Profiles page.
//
// Back up: one button, then pick the drive. Every file on it is stored, byte for byte,
// under the time it was taken. Restore: pick a backup, get it back as one .zip, copy
// the files onto the drive. The copy onto the device stays manual, like every export.
import { computed, onMounted, ref } from 'vue'
import ModalDialog from './ModalDialog.vue'
import type { Download } from '@/api/client'
import { api } from '@/api/client'
import type { Backup } from '@/api/types'
import { saveBlob } from '@/composables/useDownload'
import { desktopApi, isDesktop } from '@/desktop'
import type { DriveFile } from '@/lib/driveFiles'
import {
  backupWhen, backupZipName, filesFromDesktop, filesFromFolderPicker, sizeLabel,
} from '@/lib/driveFiles'

const backups = ref<Backup[]>([])
const error = ref('')
const busy = ref(false)
/** The backup just taken, so the page can say it worked and when. */
const justSaved = ref<Backup | null>(null)

const latest = computed(() => backups.value[0] ?? null)
const desktop = isDesktop()

/** pywebview rejects with a plain {message} object rather than an Error. */
function say(e: unknown): string {
  if (e instanceof Error) return e.message
  const m = (e as { message?: unknown } | null)?.message
  return typeof m === 'string' ? m : String(e)
}

async function load() {
  try {
    backups.value = await api.listBackups()
  } catch (e) {
    error.value = say(e)
  }
}
onMounted(load)

// ------------------------------------------------------------------ back up
const folderInput = ref<HTMLInputElement | null>(null)

async function startBackup() {
  if (busy.value) return
  error.value = ''
  justSaved.value = null
  // A WebView's file input cannot pick a folder, so the desktop shell reads it.
  const shell = desktopApi()
  if (shell?.pick_drive_files) {
    try {
      const entries = await shell.pick_drive_files()
      if (entries) await save(filesFromDesktop(entries))
    } catch (e) {
      error.value = say(e)
    }
    return
  }
  folderInput.value?.click()
}

async function onFolderChosen(e: Event) {
  const input = e.target as HTMLInputElement
  const files = [...(input.files ?? [])]
  input.value = '' // let the same drive be chosen again next time
  if (files.length) await save(filesFromFolderPicker(files))
}

async function save(files: DriveFile[]) {
  if (files.length === 0) {
    error.value = 'That folder has no files in it. Pick the QuadStick drive itself.'
    return
  }
  busy.value = true
  try {
    const b = await api.createBackup(files)
    backups.value = [b, ...backups.value]
    justSaved.value = b
  } catch (e) {
    error.value = say(e)
  } finally {
    busy.value = false
  }
}

// ------------------------------------------------------------------ restore
const restoreOpen = ref(false)
const chosenId = ref<number | null>(null)
const chosen = computed(() => backups.value.find((b) => b.id === chosenId.value) ?? null)
const downloaded = ref<Download | null>(null)
const confirmingDelete = ref(false)
const restoreError = ref('')

function openRestore() {
  chosenId.value = latest.value?.id ?? null
  downloaded.value = null
  confirmingDelete.value = false
  restoreError.value = ''
  restoreOpen.value = true
}

function choose(id: number) {
  chosenId.value = id
  downloaded.value = null
  confirmingDelete.value = false
  restoreError.value = ''
}

async function downloadChosen() {
  const b = chosen.value
  if (!b || busy.value) return
  busy.value = true
  restoreError.value = ''
  try {
    const dl = await api.downloadBackup(b.id, backupZipName(new Date(b.created_at)))
    downloaded.value = dl
    saveBlob(dl.blob, dl.filename, dl.exportPath)
  } catch (e) {
    restoreError.value = say(e)
  } finally {
    busy.value = false
  }
}

async function deleteChosen() {
  const b = chosen.value
  if (!b || busy.value) return
  busy.value = true
  restoreError.value = ''
  try {
    await api.deleteBackup(b.id)
    backups.value = backups.value.filter((x) => x.id !== b.id)
    if (justSaved.value?.id === b.id) justSaved.value = null
    confirmingDelete.value = false
    downloaded.value = null
    chosenId.value = latest.value?.id ?? null
    if (!latest.value) restoreOpen.value = false
  } catch (e) {
    restoreError.value = say(e)
  } finally {
    busy.value = false
  }
}

function fileCount(b: Backup) {
  return `${b.file_count} ${b.file_count === 1 ? 'file' : 'files'}`
}
</script>

<template>
  <section class="card backup" aria-labelledby="backup-title">
    <div class="text">
      <h2 id="backup-title">QuadStick backup</h2>
      <p v-if="justSaved" class="saved" role="status">
        Backed up {{ fileCount(justSaved) }} on {{ backupWhen(justSaved.created_at) }}.
      </p>
      <p v-else-if="latest">
        Last backed up <b>{{ backupWhen(latest.created_at) }}</b> ({{ fileCount(latest) }}).
      </p>
      <p v-else>Not backed up yet.</p>
      <p class="hint">
        Plug in the QuadStick, then choose its drive when asked. Every file on it is saved here
        with the date, so you can put the drive back exactly as it was.
        <template v-if="!desktop">Your browser asks before it sends the files — only to this app.</template>
      </p>
      <p v-if="error" class="banner banner--error" role="alert">{{ error }}</p>
    </div>
    <div class="buttons">
      <button class="btn btn--primary" type="button" :disabled="busy" @click="startBackup">
        {{ busy && !restoreOpen ? 'Backing up…' : 'Back up the QuadStick' }}
      </button>
      <button class="btn" type="button" :disabled="!latest" @click="openRestore">
        Restore a backup…
      </button>
    </div>
    <input
      ref="folderInput"
      class="sr-only"
      type="file"
      webkitdirectory
      multiple
      aria-label="Choose the QuadStick drive to back up"
      @change="onFolderChosen"
    />
  </section>

  <ModalDialog :open="restoreOpen" title="Restore a backup" @close="restoreOpen = false">
    <div class="stack">
      <fieldset class="choices">
        <legend>Which backup?</legend>
        <label
          v-for="b in backups"
          :key="b.id"
          class="choice"
          :class="{ on: chosenId === b.id }"
        >
          <input
            type="radio"
            name="backup"
            :checked="chosenId === b.id"
            @change="choose(b.id)"
          />
          <span>
            <b>{{ backupWhen(b.created_at) }}</b>
            <small>{{ fileCount(b) }} · {{ sizeLabel(b.total_bytes) }}</small>
            <small class="mono files">{{ b.files.map((f) => f.path).join(', ') }}</small>
          </span>
        </label>
      </fieldset>

      <ol v-if="chosen" class="steps">
        <li>
          <b>Save the backup.</b> It comes as one file,
          <span class="mono">{{ backupZipName(new Date(chosen.created_at)) }}</span>.
        </li>
        <li><b>Open the .zip.</b> Inside are the {{ fileCount(chosen) }} from the drive.</li>
        <li>
          <b>Copy those files to the top level of the QuadStick drive.</b> Say “Replace” when
          asked. Files on the drive that are not in the backup stay there; delete them if you want
          the drive exactly as it was.
        </li>
        <li>
          <b>Eject the drive, then unplug the QuadStick and plug it back in.</b> It only reads
          its drive when it powers on.
        </li>
      </ol>

      <p v-if="downloaded" class="saved" role="status">
        <template v-if="desktop && downloaded.exportPath">
          Saved to <span class="mono">{{ downloaded.exportPath }}</span>.
        </template>
        <template v-else>Saved as <span class="mono">{{ downloaded.filename }}</span>.</template>
      </p>
      <p v-if="restoreError" class="banner banner--error" role="alert">{{ restoreError }}</p>

      <p v-if="confirmingDelete && chosen" class="confirm" role="alert">
        Delete the backup from {{ backupWhen(chosen.created_at) }}? This cannot be undone.
        <span class="confirm-buttons">
          <button class="btn btn--small" type="button" @click="confirmingDelete = false">
            Keep it
          </button>
          <button
            class="btn btn--small btn--danger"
            type="button"
            :disabled="busy"
            @click="deleteChosen"
          >
            Yes, delete it
          </button>
        </span>
      </p>
    </div>
    <template #actions>
      <button
        v-if="!confirmingDelete"
        class="btn btn--danger"
        type="button"
        :disabled="!chosen || busy"
        @click="confirmingDelete = true"
      >
        Delete this backup
      </button>
      <button class="btn" type="button" @click="restoreOpen = false">Close</button>
      <button
        class="btn btn--primary"
        type="button"
        :disabled="!chosen || busy"
        @click="downloadChosen"
      >
        {{ downloaded ? 'Save it again' : 'Save the backup (.zip)' }}
      </button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.backup {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--sp-3) var(--sp-4);
  padding: var(--sp-4);
}
.text {
  flex: 1 1 24rem;
}
.text h2 {
  margin: 0 0 var(--sp-1);
  font-size: var(--text-lg);
}
.text p {
  margin: 0 0 var(--sp-2);
}
.buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}

.saved {
  color: var(--ok);
  font-weight: 600;
}

.banner--error {
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--error-soft);
  color: var(--error);
}

.choices {
  margin: 0;
  padding: 0;
  border: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.choices legend {
  padding: 0 0 var(--sp-2);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--ink-soft);
}

/* The whole label is the target: one click anywhere on it chooses that backup. */
.choice {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  min-height: var(--target);
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
}
.choice.on {
  border-color: var(--mode);
  background: var(--mode-soft);
}
.choice:focus-within {
  outline: var(--focus);
  outline-offset: var(--focus-offset);
}
.choice input {
  width: 20px;
  height: 20px;
  margin-top: 2px;
  flex: none;
}
.choice b,
.choice small {
  display: block;
}
.choice small {
  color: var(--ink-soft);
  font-size: var(--text-sm);
}
.choice .files {
  font-size: var(--text-xs);
  overflow-wrap: anywhere;
}

.steps {
  margin: 0;
  padding-left: 1.5em;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.confirm {
  padding: var(--sp-3);
  border: 1px solid var(--error);
  border-radius: var(--radius);
}
.confirm-buttons {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}
</style>
