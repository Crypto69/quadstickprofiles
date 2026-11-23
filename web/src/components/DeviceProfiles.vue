<script setup lang="ts">
// What is on the QuadStick: each profile with its file number and the status lights
// that pick it (long hard sip, joystick until the lights match, lip). The numbers come
// from the same LED table as the modes, the editor and the printed card (`ledsFor`),
// because the device uses one table for both.
//
// The desktop app reads the drive itself, live, every few seconds. A browser cannot,
// so there — and in the desktop app while the QuadStick is unplugged — the list is
// what the newest backup holds, and says so.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ledSentence, ledsFor } from '@/device/layout'
import { backupWhen, profilesOnDrive } from '@/lib/driveFiles'
import { useBackupsStore } from '@/stores/backups'
import { shellMessage, useDriveStore } from '@/stores/drive'

/** The QuadStick's lights only count this far. */
const LAST_LIT = 16
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
  profilesOnDrive(paths.value).map((name, i) => {
    const n = i + 1
    const leds = ledsFor(n)
    return { n, name, leds, words: n <= LAST_LIT ? ledSentence(leds) : 'no light pattern' }
  }),
)
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
              <span class="leds" :title="r.words">
                <i
                  v-for="(c, li) in r.leds"
                  :key="li"
                  :class="[c, { on: c !== 'off' }]"
                  aria-hidden="true"
                />
                <span class="sr-only">{{ r.words }}</span>
              </span>
              <small v-if="r.n > LAST_LIT" class="past">past {{ LAST_LIT }}: no lights</small>
            </td>
            <td class="mono name">{{ r.name }}</td>
          </tr>
        </tbody>
      </table>
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

/* The five status LEDs, as on the device, lit in the firmware's colours. Same look
   as the mode rail: a lit dot is filled and ringed, an unlit one is a hollow circle. */
.leds {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.leds i,
.led-num {
  width: 16px;
  flex: none;
}
.leds i {
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--ink-soft);
  background: #fff;
}
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
.led-num {
  text-align: center;
}
.past {
  display: block;
  color: var(--ink-soft);
}
</style>
