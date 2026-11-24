<script setup lang="ts">
// What is on the QuadStick: each profile with its file number and the status lights
// that pick it (long hard sip, joystick until the lights match, lip). Files 1 to 16
// light like modes 1 to 16, from the table the editor and the printed card use; the
// profile switch then carries on to file 32 (`fileLedsFor`).
//
// The desktop app reads the drive itself, live, every few seconds. A browser cannot,
// so there — and in the desktop app while the QuadStick is unplugged — the list is
// what the newest backup holds, and says so.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import FileLeds from './FileLeds.vue'
import ReplaceDrive from './ReplaceDrive.vue'
import { MAX_SELECTABLE_FILES } from '@/device/layout'
import { backupWhen, profilesOnDrive, skippedByTheSwitch } from '@/lib/driveFiles'
import { useBackupsStore } from '@/stores/backups'
import { shellMessage, useDriveStore } from '@/stores/drive'

/** How often the desktop app looks at the drive again. */
const LOOK_EVERY_MS = 3000

const store = useBackupsStore()
const drive = useDriveStore()
const latest = computed(() => store.latest)

/** Live from the drive when the desktop app can see it; otherwise the newest backup. */
const fromDrive = computed(() => drive.live && drive.found)
const paths = computed(() =>
  fromDrive.value
    ? (drive.state?.files ?? []).map((f) => f.path)
    : (latest.value?.files.map((f) => f.path) ?? []),
)

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  if (!drive.live) return
  void drive.refresh()
  timer = setInterval(() => void drive.refresh(), LOOK_EVERY_MS)
})
onUnmounted(() => clearInterval(timer))

const chooseError = ref('')
async function chooseDrive() {
  chooseError.value = ''
  try {
    await drive.choose()
  } catch (e) {
    chooseError.value = shellMessage(e)
  }
}

const rows = computed(() =>
  profilesOnDrive(paths.value).map((name, i) => ({
    n: i + 1,
    name,
    reachable: i + 1 <= MAX_SELECTABLE_FILES,
  })),
)
const skipped = computed(() => skippedByTheSwitch(paths.value))
</script>

<template>
  <section class="card on-device" aria-labelledby="on-device-title">
    <h2 id="on-device-title">On the QuadStick</h2>

    <!-- The desktop app: what it sees on the drive, or what to plug in. -->
    <div v-if="drive.live" class="drive">
      <p v-if="drive.found" role="status">
        Reading the drive <b>{{ drive.state?.name }}</b> now.
      </p>
      <p v-else-if="drive.state" role="status">
        Plug in the QuadStick. The app looks for the drive called
        <b>{{ drive.state.name }}</b>.
      </p>
      <button class="btn btn--small" type="button" @click="chooseDrive">
        {{ drive.found ? 'Use a different drive…' : 'Choose the drive…' }}
      </button>
      <ReplaceDrive v-if="drive.writable" />
    </div>
    <p v-if="chooseError || drive.error" class="banner banner--error" role="alert">
      {{ chooseError || drive.error }}
    </p>

    <p v-if="!fromDrive && !store.loaded" role="status">Loading…</p>
    <p v-else-if="!fromDrive && !latest" class="hint">
      <template v-if="drive.live">Once it is plugged in, the profiles on it show here,</template>
      <template v-else>Back up the QuadStick above, and the profiles on it show here,</template>
      with the lights that pick each one.
    </p>
    <template v-else>
      <p class="hint">
        <template v-if="fromDrive" />
        <template v-else-if="latest && drive.live">
          Until then, this is what the newest backup holds, from
          <b>{{ backupWhen(latest.created_at) }}</b>.
        </template>
        <template v-else-if="latest">
          From the backup taken <b>{{ backupWhen(latest.created_at) }}</b>. Back up again after
          you change the drive.
        </template>
        To pick a profile: long hard sip on the side tube, move the joystick until the lights
        match, then press the lip.
      </p>

      <p v-if="rows.length === 0">
        {{ fromDrive ? 'There are no profiles on the drive.' : 'That backup has no profiles in it.' }}
      </p>

      <table v-else class="list">
        <thead>
          <tr>
            <th scope="col" class="num">File</th>
            <th scope="col" class="lights-head">
              <span class="sr-only">Lights</span>
              <span class="leds" aria-hidden="true">
                <span v-for="i in 5" :key="i" class="led-num">{{ i }}</span>
              </span>
            </th>
            <th scope="col">Profile</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name">
            <td class="num">{{ r.n }}</td>
            <td>
              <FileLeds :n="r.n" />
              <small v-if="!r.reachable" class="past">
                past {{ MAX_SELECTABLE_FILES }}: the QuadStick cannot pick it
              </small>
            </td>
            <td class="mono name">{{ r.name }}</td>
          </tr>
        </tbody>
      </table>

      <p v-if="skipped.length" class="hint skipped">
        Not on the list: <span class="mono">{{ skipped.join(', ') }}</span>. The QuadStick
        leaves out any file with <span class="mono">prefs.csv</span> in its name, so it can
        never be picked. Rename it to use it as a profile.
      </p>
    </template>
  </section>
</template>

<style scoped>
.on-device {
  padding: var(--sp-4);
}
.on-device h2 {
  margin: 0 0 var(--sp-1);
  font-size: var(--text-lg);
}
.on-device p {
  margin: 0 0 var(--sp-2);
}
.drive {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2) var(--sp-3);
  margin-bottom: var(--sp-2);
}
.drive p {
  margin: 0;
}
.banner--error {
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--error-soft);
  color: var(--error);
}

.list {
  border-collapse: collapse;
  width: 100%;
  max-width: 40rem;
}
.list th,
.list td {
  padding: var(--sp-2) var(--sp-3);
  text-align: left;
  vertical-align: middle;
  border-bottom: 1px solid var(--line);
}
.list th {
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--ink-soft);
}
.num {
  width: 3.5rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.list td.num {
  font-size: var(--text-lg);
}
.name {
  overflow-wrap: anywhere;
}

/* The header's numbers sit over the five lights (FileLeds.vue): same gap, same width. */
.leds {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.led-num {
  width: 16px;
  flex: none;
  text-align: center;
}
.past {
  display: block;
  color: var(--ink-soft);
}
.on-device p.skipped {
  margin-top: var(--sp-3);
}
</style>
