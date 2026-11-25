<script setup lang="ts">
// Put profiles from the Profiles page onto the QuadStick, in place of the ones on it
// now. Desktop apps only: a web page cannot write to a USB drive, so the NAS keeps
// the export-and-copy steps.
//
// Tick the profiles, see the drive's new numbered list, press one button. The app
// then backs the drive up (the same backup as "Back up the QuadStick"), exports each
// profile through the ordinary export (which refuses one with errors), and hands the
// files to the shell, which writes them and flushes (desktop/desktop_api.py
// `replace_profiles`). Only the profile files swap; prefs.csv and the rest stay.
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import FileLeds from './FileLeds.vue'
import ModalDialog from './ModalDialog.vue'
import { api } from '@/api/client'
import type { Backup, ProfileSummary } from '@/api/types'
import { backupWhen, blobToBase64, planReplace } from '@/lib/driveFiles'
import { useBackupsStore } from '@/stores/backups'
import { shellMessage as say, useDriveStore } from '@/stores/drive'

const drive = useDriveStore()
const backups = useBackupsStore()

const open = ref(false)
const loading = ref(false)
const profiles = ref<ProfileSummary[]>([])
const ticked = ref<Set<number>>(new Set())
const phase = ref<'choose' | 'working' | 'done'>('choose')
const step = ref('')
const error = ref('')
/** The backup taken just before writing: the drive as it was. */
const before = ref<Backup | null>(null)

const errorsIn = (p: ProfileSummary) => p.validation?.errors ?? 0

async function start() {
  open.value = true
  phase.value = 'choose'
  error.value = ''
  before.value = null
  loading.value = true
  try {
    profiles.value = await api.listProfiles({ validate: true })
    // Tick every profile that can go on, once per file name: the list is newest
    // first, so of two called cod.csv the one edited last is ticked.
    const names = new Set<string>()
    const on = new Set<number>()
    for (const p of profiles.value) {
      const name = p.csv_filename.toLowerCase()
      if (errorsIn(p) || names.has(name) || name.includes('prefs.csv')) continue
      names.add(name)
      on.add(p.id)
    }
    ticked.value = on
  } catch (e) {
    error.value = say(e)
  } finally {
    loading.value = false
  }
}

function toggle(id: number) {
  const next = new Set(ticked.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  ticked.value = next
}

const chosen = computed(() => profiles.value.filter((p) => ticked.value.has(p.id)))
const plan = computed(() =>
  planReplace(
    (drive.state?.files ?? []).map((f) => f.path),
    chosen.value.map((p) => p.csv_filename),
  ),
)
const canWrite = computed(
  () => drive.found && !loading.value && phase.value === 'choose' && plan.value.problems.length === 0,
)
const count = (n: number) => `${n} ${n === 1 ? 'profile' : 'profiles'}`

async function write() {
  if (!canWrite.value) return
  phase.value = 'working'
  error.value = ''
  before.value = null
  try {
    step.value = 'Backing up the drive…'
    const files = await drive.read()
    if (!files) throw new Error('The QuadStick is not plugged in. Nothing was changed.')
    before.value = await api.createBackup(files)
    backups.added(before.value)

    step.value = 'Getting the profiles ready…'
    const out: { name: string; data: string }[] = []
    for (const p of chosen.value) {
      const dl = await api.exportCsv(p.id) // refuses a profile with errors
      out.push({ name: p.csv_filename, data: await blobToBase64(dl.blob) })
    }

    step.value = 'Writing to the drive…'
    await drive.write(out)
    phase.value = 'done'
  } catch (e) {
    error.value = say(e)
    phase.value = 'choose'
  }
}
</script>

<template>
  <button
    class="btn btn--small btn--primary"
    type="button"
    :disabled="!drive.found"
    :title="drive.found ? '' : drive.needsPermission ? 'Choose the drive first' : 'Plug in the QuadStick first'"
    @click="start"
  >
    Put my profiles on the QuadStick…
  </button>

  <ModalDialog :open="open" title="Put my profiles on the QuadStick" @close="open = false">
    <div v-if="phase === 'done'" class="stack" role="status">
      <p class="saved">
        Done. The QuadStick drive has {{ count(plan.after.length) }} on it now, and it is safe
        to unplug.
      </p>
      <p v-if="before">
        The drive as it was is in the backup from <b>{{ backupWhen(before.created_at) }}</b>.
      </p>
      <p>
        <b>Unplug the QuadStick and plug it back in.</b> It only reads its drive when it powers
        on.
      </p>
    </div>

    <p v-else-if="phase === 'working'" class="working" role="status">{{ step }}</p>

    <div v-else class="stack">
      <p>
        Tick the profiles to put on the QuadStick. They take the place of the profiles on it now.
        The app backs up the drive first, so you can put it back.
      </p>
      <p v-if="loading" role="status">Loading…</p>
      <p v-else-if="profiles.length === 0 && !error">
        There are no profiles on the Profiles page yet.
      </p>

      <fieldset v-else-if="profiles.length" class="choices">
        <legend>Profiles</legend>
        <template v-for="p in profiles" :key="p.id">
          <div v-if="errorsIn(p)" class="choice blocked">
            <span>
              <b>{{ p.name }}</b>
              <small class="mono">{{ p.csv_filename }}</small>
              <small class="why">
                Has {{ errorsIn(p) }} {{ errorsIn(p) === 1 ? 'error' : 'errors' }}, so it cannot go
                on.
                <RouterLink :to="{ name: 'profile', params: { id: p.id } }">Fix it</RouterLink>
              </small>
            </span>
          </div>
          <label v-else class="choice" :class="{ on: ticked.has(p.id) }">
            <input type="checkbox" :checked="ticked.has(p.id)" @change="toggle(p.id)" />
            <span>
              <b>{{ p.name }}</b>
              <small class="mono">{{ p.csv_filename }}</small>
              <small v-if="p.game">{{ p.game }}</small>
            </span>
          </label>
        </template>
      </fieldset>

      <div v-if="!loading && profiles.length" class="after">
        <h3>The QuadStick after</h3>
        <ol v-if="plan.after.length" class="after-list">
          <li v-for="(name, i) in plan.after" :key="name">
            <span class="num">{{ i + 1 }}</span>
            <FileLeds :n="i + 1" />
            <span class="mono">{{ name }}</span>
            <small v-if="name === 'default.csv' && plan.keptDefault">(already there)</small>
          </li>
        </ol>
        <p v-if="plan.keptDefault" class="hint">
          <span class="mono">default.csv</span> stays as it is: none of the ticked profiles is
          called that. The QuadStick starts with it.
        </p>
        <p v-if="plan.removed.length" class="hint">
          Taken off the drive: <span class="mono">{{ plan.removed.join(', ') }}</span>. They stay in
          the backup.
        </p>
        <p class="hint">
          <span class="mono">prefs.csv</span> and every other file on the drive stay as they are.
          What is saved in the app goes on the drive.
        </p>
      </div>

      <ul v-if="plan.problems.length && !loading && profiles.length" class="banner banner--warn">
        <li v-for="m in plan.problems" :key="m">{{ m }}</li>
      </ul>
      <p v-if="!drive.found" class="banner banner--warn">
        {{ drive.needsPermission ? 'Choose the drive first.' : 'Plug in the QuadStick first.' }}
      </p>
    </div>

    <div v-if="error" class="banner banner--error" role="alert">
      <p>{{ error }}</p>
      <p v-if="before">
        The backup from <b>{{ backupWhen(before.created_at) }}</b> has the drive as it was. Restore
        it if the QuadStick misbehaves.
      </p>
    </div>

    <template #actions>
      <button class="btn" type="button" :disabled="phase === 'working'" @click="open = false">
        {{ phase === 'done' ? 'Close' : 'Cancel' }}
      </button>
      <button
        v-if="phase !== 'done'"
        class="btn btn--primary"
        type="button"
        :disabled="!canWrite"
        @click="write"
      >
        Back up, then put {{ count(chosen.length) }} on
      </button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.saved {
  color: var(--ok);
  font-weight: 600;
}
.working {
  font-weight: 600;
}
.banner {
  margin: 0;
  padding: var(--sp-3);
  border-radius: var(--radius);
}
.banner p {
  margin: 0 0 var(--sp-1);
}
ul.banner {
  padding-left: 1.75em;
}
.banner--error {
  margin-top: var(--sp-3);
  background: var(--error-soft);
  color: var(--error);
}
.banner--warn {
  background: var(--warning-soft);
  color: var(--warning);
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

/* The whole label is the target: one click anywhere on it ticks that profile. */
.choice {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  min-height: var(--target);
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
label.choice {
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
.choice.blocked {
  border-style: dashed;
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
.choice .why {
  color: var(--error);
}

.after h3 {
  margin: 0 0 var(--sp-2);
  font-size: var(--text-base);
}
.after p {
  margin: var(--sp-2) 0 0;
}
.after-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.after-list li {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.after-list .num {
  width: 2rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
</style>
