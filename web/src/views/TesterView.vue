<script setup lang="ts">
/**
 * The QuadStick tester: what the device reports, live, on its photo, and a
 * guided check of every tube one at a time. Practice as much as checking.
 *
 * The browser reads the QuadStick over WebHID (tester/hid.ts); the page decodes
 * the raw reports (tester/decode.ts) with the spec the API generates alongside
 * the `qstest` profile (core/qsprofile/tester.py), and runs the guided test
 * (tester/guided.ts). Nothing is stored and nothing is sent to the device.
 */
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { api, type Download } from '@/api/client'
import { describe as errorText } from '@/api/errors'
import ExportChecklist from '@/components/ExportChecklist.vue'
import TesterPhoto from '@/components/TesterPhoto.vue'
import { saveBlob } from '@/composables/useDownload'
import { openExternal } from '@/composables/useExternalLink'
import { isDesktop } from '@/desktop'
import { ledSentence, ledsFor } from '@/device/layout'
import {
  activeInputs, describe, hat, HAT_RELEASED, litTubes, modeOf, rawButtons, sideTubeFor,
  stickOf, TUBE_NAME, type Report, type TesterInput, type TesterSpec, type Tube,
} from '@/tester/decode'
import { GuidedTest, type Step } from '@/tester/guided'
import { unsupportedReason, useQuadStickHid } from '@/tester/hid'

const spec = shallowRef<TesterSpec | null>(null)
const loadError = ref('')
const test = ref<GuidedTest | null>(null)

/** The side tube flashes when the mode changes: the report never shows it. */
const FLASH_MS = 900
const flash = ref<{ action: 'sip' | 'puff'; until: number } | null>(null)
const clock = ref(performance.now())
let lastMode: number | null = null

function onReport(r: Report) {
  const sp = spec.value
  if (!sp) return
  const m = modeOf(sp, r)
  if (m && lastMode !== null && m.n !== lastMode) {
    const action = sideTubeFor(lastMode, m.n, sp.modes.length)
    if (action) flash.value = { action, until: performance.now() + FLASH_MS }
  }
  if (m) lastMode = m.n
  test.value?.report({ mode: m, active: activeInputs(m, r), stick: stickOf(r) })
}

const hid = useQuadStickHid(onReport)
const why = unsupportedReason()
const desktop = isDesktop()

// ---- what the latest report says ---------------------------------------------
const report = computed(() => hid.report.value)
const mode = computed(() => (spec.value && report.value ? modeOf(spec.value, report.value) : null))
const active = computed(() => (report.value ? activeInputs(mode.value, report.value) : []))
const stick = computed(() => (report.value ? stickOf(report.value) : null))
const buttons = computed(() => (report.value ? rawButtons(report.value) : []))

const lit = computed(() => {
  const on: Partial<Record<Tube, Pick<TesterInput, 'action' | 'level'>>> = spec.value
    ? litTubes(spec.value, active.value)
    : {}
  const f = flash.value
  if (f && clock.value < f.until && !on.side) on.side = { action: f.action, level: 'hard' }
  return on
})

const pct = (v: number) => `${v >= 0 ? '+' : ''}${Math.round(v * 100)}%`
const stickWords = computed(() => {
  const s = stick.value
  if (!s) return '—'
  const h = s.x > 0.05 ? ' right' : s.x < -0.05 ? ' left' : ''
  const v = s.y > 0.05 ? ' up' : s.y < -0.05 ? ' down' : ''
  return `X ${s.rx} (${pct(s.x)}${h}), Y ${s.ry} (${pct(s.y)}${v})`
})

// ---- the guided test ---------------------------------------------------------
const step = computed<Step | null>(() => test.value?.step ?? null)
const result = computed(() => test.value?.result ?? null)
const wrongMode = computed(
  () => step.value && step.value.kind !== 'mode' && report.value && mode.value?.n !== step.value.mode,
)

/** What the photo rings: the asked input, or the LEDs of the mode to go to. */
const target = computed(() => {
  const st = step.value
  if (!st || !spec.value || result.value?.ok === true) return null
  if (st.kind === 'mode') return { mode: st.mode }
  if (st.kind === 'input') {
    const input = spec.value.inputs[st.input]
    return input ? { input } : null
  }
  return null
})

function modeName(n: number) {
  return spec.value?.modes.find((m) => m.n === n)?.name ?? ''
}

/** The asked input, split so the page can colour the sip / puff part. */
function instruction(st: Step) {
  if (st.kind !== 'input' || !spec.value) return null
  const i = spec.value.inputs[st.input]
  if (!i || i.action === 'press') return null
  const where = i.tubes.map((t) => TUBE_NAME[t]).join(' + ')
  return {
    action: i.action,
    what: `${i.level === 'gentle' ? 'Gentle' : 'Hard'} ${i.action}`,
    where: i.tubes[0] === 'side' ? 'the side tube' : `the ${where} tube${i.tubes.length > 1 ? 's together' : ''}`,
  }
}

const results = computed(() =>
  test.value ? [...test.value.results.entries()].sort((a, b) => a[0] - b[0]) : [],
)

let timer = 0
onMounted(async () => {
  try {
    spec.value = await api.testerSpec()
    test.value = new GuidedTest(spec.value)
  } catch (e) {
    loadError.value = errorText(e)
  }
  // Ends quiet attempts, moves on after a pass, and lets the side-tube flash expire.
  timer = window.setInterval(() => {
    clock.value = performance.now()
    test.value?.tick()
  }, 50)
})
onBeforeUnmount(() => window.clearInterval(timer))

// ---- the qstest profile --------------------------------------------------------
const exported = ref<Download | null>(null)
const exportError = ref('')
async function downloadProfile() {
  exportError.value = ''
  try {
    const d = await api.exportTesterProfile()
    saveBlob(d.blob, d.filename, d.exportPath)
    exported.value = d
  } catch (e) {
    exportError.value = errorText(e)
  }
}

function openInBrowser() {
  openExternal('/tester')
}
const here = typeof window !== 'undefined' ? `${window.location.origin}/tester` : '/tester'
</script>

<template>
  <div class="stack">
    <header>
      <h1>Test your QuadStick</h1>
      <p class="lede">
        See every sip, puff, lip press and joystick move the moment the QuadStick reports it,
        and check every tube one at a time. Good for practice too. This page only listens:
        it never changes anything on the device.
      </p>
    </header>

    <p v-if="loadError" class="banner--error" role="alert">
      Could not load the tester: {{ loadError }}
    </p>

    <ol class="setup">
      <li class="card">
        <h2>Put the test profile on the QuadStick</h2>
        <p>
          The tester needs its own profile, <span class="mono">qstest.csv</span>. It tells the
          page which mode the QuadStick is in and which tube was used. Copy it on as a new
          file; your other profiles keep their numbers.
        </p>
        <button class="btn" type="button" @click="downloadProfile">Download qstest.csv</button>
        <p v-if="exportError" class="banner--error" role="alert">{{ exportError }}</p>
      </li>
      <li class="card">
        <h2>Connect</h2>
        <template v-if="why === 'insecure'">
          <p class="warn">
            This browser only lets a secure page read USB, and this page came over plain http from
            another computer. Open the tester on the computer the QuadStick is plugged into: in the
            desktop app, or at the app's HTTPS address (the Tailscale step in the NAS guide).
          </p>
        </template>
        <template v-else-if="why === 'browser' && desktop">
          <p>
            The app window cannot read USB. Open this page in Chrome or Edge on this computer.
          </p>
          <button class="btn btn--primary" type="button" @click="openInBrowser">
            Open the tester in your browser
          </button>
          <p class="hint">
            If it opens in Safari or Firefox, copy this address into Chrome or Edge:
            <span class="mono">{{ here }}</span>
          </p>
        </template>
        <template v-else-if="why === 'browser'">
          <p class="warn">This browser cannot read USB devices. Open this page in Chrome or Edge.</p>
        </template>
        <template v-else>
          <p v-if="hid.connected.value" class="ok" role="status">
            Connected: {{ hid.device.value?.productName || 'QuadStick' }}
          </p>
          <p v-else>
            Plug the QuadStick in with its data cable, then pick it from the browser's list. The
            browser remembers it, so next time it connects by itself.
          </p>
          <div class="row">
            <button
              v-if="!hid.connected.value"
              class="btn btn--primary"
              type="button"
              @click="hid.connect"
            >
              Connect the QuadStick
            </button>
            <button v-else class="btn btn--quiet" type="button" @click="hid.disconnect">
              Disconnect
            </button>
          </div>
          <p v-if="hid.error.value" class="banner--error" role="alert">{{ hid.error.value }}</p>
        </template>
      </li>
    </ol>

    <div class="layout">
      <figure class="device">
        <TesterPhoto :mode="mode?.n ?? null" :lit="lit" :stick="stick" :target="target" />
        <figcaption>
          <span class="key"><i class="sw sw--sip" /> sip</span>
          <span class="key"><i class="sw sw--puff" /> puff</span>
          <span class="key"><i class="sw sw--soft" /> pale = gentle</span>
          <span class="key"><i class="sw sw--aim" /> do this next</span>
        </figcaption>
      </figure>

      <div class="panel">
        <section class="card" aria-labelledby="mode-h">
          <h2 id="mode-h" class="label">Mode</h2>
          <template v-if="!report">
            <p class="big">—</p>
            <p class="hint">
              {{ hid.connected.value ? 'Waiting for the QuadStick to report…' : 'Not connected yet.' }}
            </p>
          </template>
          <template v-else-if="mode">
            <p class="big">
              <b>{{ mode.n }}</b> {{ mode.name }}
            </p>
            <p>{{ mode.help }}</p>
            <p class="hint">The QuadStick shows {{ ledSentence(ledsFor(mode.n)) }}.</p>
          </template>
          <template v-else>
            <p class="big"><b>?</b> Not the test profile</p>
            <p>
              The QuadStick is not in one of qstest's modes
              <template v-if="hat(report) !== HAT_RELEASED">(the d-pad reads {{ hat(report) }})</template>.
              To select it: a long hard sip on the side tube, the joystick until the LEDs show
              qstest's file number, then the lip button.
            </p>
          </template>
        </section>

        <section class="card guided" aria-labelledby="guided-h">
          <h2 id="guided-h" class="label">
            Guided test
            <span v-if="test && step"> · {{ step.section }} · step {{ test.idx + 1 }} of {{ test.plan.length }}</span>
          </h2>

          <div aria-live="polite">
            <template v-if="test && step">
              <p v-if="step.kind === 'mode'" class="ask">
                Go to <b>mode {{ step.mode }}</b>: {{ modeName(step.mode) }}
              </p>
              <p v-else-if="step.kind === 'joy'" class="ask">
                Push the joystick <b>all the way {{ step.dir }}</b>, then let it centre
              </p>
              <p v-else-if="instruction(step)" class="ask">
                <span :class="instruction(step)?.action">{{ instruction(step)?.what }}</span>
                on {{ instruction(step)?.where }}
              </p>
              <p v-else class="ask">Press the <b>lip button</b></p>

              <p v-if="wrongMode" class="warn">
                Go back to <b>mode {{ step.mode }}</b> for this step.
              </p>
              <p v-else-if="step.kind === 'mode'" class="hint">
                Side tube: sip for the next mode, puff for the previous one. The yellow rings
                show the LEDs for mode {{ step.mode }}.
              </p>
              <p v-else-if="step.kind === 'joy'" class="hint">
                It counts when the joystick reaches at least 85% of its travel.
              </p>
              <p v-else class="hint">Then let go. The result shows what the QuadStick reported.</p>

              <p v-if="result?.ok === true" class="verdict ok">✓ Registered: {{ result.got }}</p>
              <p v-else-if="result?.ok === false" class="verdict bad">
                ✗ Not what was asked. The QuadStick reported: {{ result.got }}. Just try again.
              </p>
            </template>
            <p v-else-if="test?.finished" class="ask">
              Done: {{ test.passed }} of {{ test.results.size }} registered as asked.
            </p>
            <p v-else class="hint">
              Start the test to be walked through every tube, one at a time, or pick one section.
            </p>
          </div>

          <div v-if="test" class="row buttons">
            <button class="btn btn--primary" type="button" @click="test.start()">
              {{ test.running ? 'Start again' : 'Start the test' }}
            </button>
            <template v-if="test.running">
              <button class="btn" type="button" @click="test.skip()">Skip</button>
              <button class="btn" type="button" :disabled="test.idx === 0" @click="test.back()">
                Back
              </button>
            </template>
          </div>
          <div v-if="test && !test.running" class="row buttons">
            <span class="hint">Or one section:</span>
            <button
              v-for="s in test.sections"
              :key="s.name"
              class="btn btn--small"
              type="button"
              @click="test.start(s.name)"
            >
              {{ s.mode }} · {{ s.name }}
            </button>
          </div>
        </section>

        <section class="card" aria-labelledby="live-h">
          <h2 id="live-h" class="label">Right now</h2>
          <ul v-if="report && mode && active.length && spec" class="live">
            <li v-for="id in active" :key="id" :class="spec.inputs[id]?.action">
              {{ describe(spec, id) }}
            </li>
          </ul>
          <p v-else-if="report && !mode && buttons.length" class="live">
            Buttons: {{ buttons.join(', ') }}
          </p>
          <p v-else class="hint">{{ report ? 'Nothing pressed.' : '—' }}</p>
          <p class="stick">Joystick <b class="mono">{{ stickWords }}</b></p>
        </section>

        <section v-if="results.length" class="card" aria-labelledby="results-h">
          <h2 id="results-h" class="label">Results</h2>
          <table class="results">
            <thead>
              <tr><th>#</th><th>Asked</th><th>Registered</th><th><span class="sr-only">Outcome</span></th></tr>
            </thead>
            <tbody>
              <tr v-for="[i, r] in results" :key="i">
                <td>{{ i + 1 }}</td>
                <td>{{ r.asked }}</td>
                <td>{{ r.got }}</td>
                <td :class="r.ok === true ? 'ok' : r.ok === false ? 'bad' : 'skip'">
                  {{ r.ok === true ? '✓' : r.ok === false ? '✗' : 'skipped' }}
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </div>

    <ExportChecklist
      :open="exported !== null"
      :download="exported"
      profile-name="qstest"
      @close="exported = null"
    />
  </div>
</template>

<style scoped>
.setup > li,
.panel > .card {
  padding: var(--sp-4) var(--sp-5);
}
.setup h2 {
  margin: 0;
  font-size: var(--text-lg);
}

.lede {
  font-size: var(--text-lg);
  color: var(--ink-soft);
  max-width: 46rem;
}

.setup {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
  gap: var(--sp-4);
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: setup;
}
.setup > li {
  counter-increment: setup;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-3);
}
.setup h2::before {
  content: counter(setup) '. ';
  color: var(--mode);
}
.setup p {
  margin: 0;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(20rem, 1fr);
  gap: var(--sp-5);
  align-items: start;
}
@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

.device {
  margin: 0;
  position: sticky;
  top: var(--sp-4);
  background: var(--paper-sunk);
  border-radius: var(--radius-lg);
  padding: var(--sp-3);
}
.device figcaption {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4);
  justify-content: center;
  font-size: var(--text-sm);
  color: var(--ink-soft);
}
.key {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
}
.sw {
  display: inline-block;
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
}
.sw--sip {
  background: var(--sip);
}
.sw--puff {
  background: var(--puff);
}
.sw--soft {
  background: var(--sip);
  opacity: 0.35;
}
.sw--aim {
  border: 3px solid #d9a900;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.panel .card > p {
  margin: var(--sp-2) 0 0;
}
.label {
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-soft);
  margin: 0;
}
.big {
  font-size: var(--text-xl);
  font-weight: 700;
}
.big b {
  font-size: var(--text-2xl);
  margin-right: var(--sp-2);
  color: var(--mode);
}

.ask {
  font-size: var(--text-xl);
  font-weight: 700;
  line-height: 1.25;
}
.ask .sip,
.ask .puff {
  text-transform: uppercase;
}
.verdict {
  font-weight: 700;
}
.ok {
  color: var(--ok);
  font-weight: 700;
}
.bad {
  color: var(--error);
}
.warn {
  color: var(--warning);
  font-weight: 600;
}
.buttons {
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
  align-items: center;
}

.live {
  margin: var(--sp-2) 0 0;
  padding: 0;
  list-style: none;
  font-size: var(--text-lg);
  font-weight: 700;
}
.live li.press {
  color: var(--ink);
}
.stick {
  color: var(--ink-soft);
}
.stick b {
  color: var(--ink);
  font-weight: 600;
}

.results {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
  margin-top: var(--sp-2);
}
.results th {
  text-align: left;
  color: var(--ink-soft);
  font-weight: 600;
  padding: var(--sp-1);
}
.results td {
  padding: var(--sp-1);
  border-top: 1px solid var(--line);
  vertical-align: top;
}
.results td.skip {
  color: var(--ink-soft);
}
</style>
