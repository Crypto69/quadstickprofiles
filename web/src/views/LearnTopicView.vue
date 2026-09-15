<script setup lang="ts">
/**
 * One Learn page. The content is inline rather than in a CMS because it is nine
 * pages that change when the hardware facts change, and those facts live in docs/
 * beside it. Every number here traces to docs/ or a fixture.
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import FunctionDemo from '@/components/FunctionDemo.vue'
import frontPhoto from '@/assets/front.webp'
import rearPhoto from '@/assets/rear.webp'
import ps5Photo from '@/assets/ps5-controller.webp'
import { ledSentence, ledsFor } from '@/device/layout'
import { FUNCTION_DEMOS, PATTERNS, TOPICS, topicBySlug } from '@/learn/topics'
import { useCatalogStore } from '@/stores/catalog'

const props = defineProps<{ slug: string }>()

const catalog = useCatalogStore()

// The safety page quotes the firmware table from the catalog, so make sure it is
// loaded even when someone lands here directly from a link.
onMounted(() => {
  catalog.load().catch(() => {
    /* App.vue shows the connection banner */
  })
})

/** One control for all nine animations, rather than nine buttons down the page. */
const playDemos = ref(true)
const reduceMotion = ref(false)
onMounted(() => {
  reduceMotion.value = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false
})

const topic = computed(() => topicBySlug(props.slug))
const index = computed(() => TOPICS.findIndex((t) => t.slug === props.slug))
const prev = computed(() => (index.value > 0 ? TOPICS[index.value - 1] : null))
const next = computed(() => TOPICS[index.value + 1] ?? null)

const hiddenModes = computed(() => catalog.catalog?.hidden_drive_modes ?? {})
const emulationModes = computed(() => catalog.catalog?.emulation_modes ?? {})
const limits = computed(() => catalog.catalog?.limits ?? null)

/** All sixteen modes, each with its lights and the same thing in words. */
const ledRows = computed(() =>
  Array.from({ length: limits.value?.max_modes ?? 16 }, (_, i) => {
    const n = i + 1
    const lamps = ledsFor(n)
    return { n, lamps, words: ledSentence(lamps) }
  }),
)
</script>

<template>
  <article v-if="topic" class="topic">
    <p class="crumb"><RouterLink to="/learn">← How it works</RouterLink></p>
    <h1>{{ topic.title }}</h1>
    <p class="lede">{{ topic.blurb }}</p>

    <!-- 1 ------------------------------------------------------------------ -->
    <template v-if="slug === 'three-parts'">
      <p>
        A profile is a list of rows. Every row says the same three things, in this order:
      </p>
      <ol class="parts">
        <li><b>What the console sees</b> — a button, a stick push, a key. The "output".</li>
        <li><b>How it behaves</b> — held down, latched on, repeating. The "function".</li>
        <li><b>What you do</b> — a sip, a puff, the joystick, the lip button. The "input".</li>
      </ol>
      <p>
        So one row reads: <b>press R2</b>, <b>while held</b>, <b>when I sip on the centre
        hole</b>. That is the whole idea. Everything else is variations on it.
      </p>
      <p class="aside">
        The order looks backwards when you read it out loud, and it is — the file lists the
        output first because that is how the spreadsheet was laid out. The editor writes it
        as a sentence so you never have to think about the column order.
      </p>
    </template>

    <!-- 2 ------------------------------------------------------------------ -->
    <template v-if="slug === 'files-and-modes'">
      <p>
        One <b>file</b> is one game. It lives on the QuadStick's own flash drive as a
        <span class="mono">.csv</span>, and the device can hold well over a hundred of them.
      </p>
      <p>
        Inside a file are up to
        <b>{{ limits?.max_modes ?? 16 }} modes</b>. A mode is a complete set of mappings,
        and only one is active at a time. Each mode holds up to
        <b>{{ limits?.max_rows_per_mode ?? 128 }} rows</b>.
      </p>
      <h2>Why bother with modes?</h2>
      <p>
        Because there are only so many sips and puffs. Three holes plus the side tube, each
        with a sip and a puff, each soft or hard — that is sixteen, plus the hole
        combinations, the lip button, the joystick and any switches. A modern game wants
        more buttons than that.
      </p>
      <p>
        Modes multiply what you have. Your Fortnite file uses seven: one built around the
        left stick, one around the right stick, one around the D-pad, and others for
        building and for sprinting. The same sip does a different job in each.
      </p>
      <img :src="ps5Photo" alt="A PlayStation 5 controller, for comparison with the mappings" class="wide" />
      <p class="hint">
        Every one of those buttons has to come from somewhere on the QuadStick.
      </p>
    </template>

    <!-- 3 ------------------------------------------------------------------ -->
    <template v-if="slug === 'changing-mode'">
      <h2>Changing mode: instant</h2>
      <p>
        Changing mode is just another output. A row can say "next mode" or "previous mode",
        and you bind it to whatever you like — usually a sip or puff on the side tube,
        because that tube is out of the way of the game controls.
      </p>
      <p>
        It happens straight away, and it wraps around: past the last mode you are back at
        the first. If a mode has <b>no</b> row that changes mode, you cannot leave it — the
        only way out is unplugging the QuadStick. The editor warns you about that, and the
        mode map draws a dashed ring round any mode you are stuck in.
      </p>

      <h2>Changing file: slower, on purpose</h2>
      <p>Swapping to a different game is a deliberate, three-part move:</p>
      <ol class="steps">
        <li>A <b>long hard sip</b> on the side tube.</li>
        <li>Move the <b>joystick</b> until the status lights show the file you want.</li>
        <li>Press the <b>lip button</b>.</li>
      </ol>
      <p>
        Files are in alphabetical order, and
        <span class="mono">default.csv</span> is always number one. The next page explains
        how to read the lights.
      </p>
    </template>

    <!-- 4 ------------------------------------------------------------------ -->
    <template v-if="slug === 'lights'">
      <p>
        Five little lights across the top tell you which mode — or which file — you are on.
      </p>
      <ul class="plain">
        <li>Modes <b>1 to 5</b>: that one light is on, in <b class="purple">purple</b>.</li>
        <li>
          <b>6 to 9</b>: light 5 stays purple, and one more purple joins it. Add them up —
          light 5 plus light 2 means mode 7.
        </li>
        <li>
          <b>10 to 14</b>: light 5 turns <b class="blue">blue</b>, and the count starts again
          beside it. Blue 5 on its own is mode 10; blue 5 plus purple 2 is mode 12.
        </li>
        <li>
          <b>15 and 16</b>: light 5 turns <b class="red">red</b>. Red 5 on its own is 15; red 5
          plus purple 1 is 16.
        </li>
      </ul>
      <table class="leds-table">
        <caption>
          The pattern for every mode
        </caption>
        <thead>
          <tr>
            <th>Mode</th>
            <th>Lights</th>
            <th>In words</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in ledRows" :key="r.n">
            <th scope="row">{{ r.n }}</th>
            <td>
              <span class="leds">
                <i v-for="(c, i) in r.lamps" :key="i" :class="[c, { on: c !== 'off' }]" />
              </span>
            </td>
            <td class="words">{{ r.words }}</td>
          </tr>
        </tbody>
      </table>
      <p class="aside">
        The colour of light 5 is doing real work. Mode 5 and mode 10 both show light 5 on
        its own — purple for 5, blue for 10 — so look at the colour, not only at which
        light is lit. Every one of the sixteen modes has its own pattern.
      </p>
    </template>

    <!-- 5 ------------------------------------------------------------------ -->
    <template v-if="slug === 'soft-and-hard'">
      <p>
        Each hole notices <b>two</b> strengths, not one. A gentle sip and a firm sip are
        different inputs, so the number of things you can do doubles.
      </p>
      <dl class="pairs">
        <dt class="sip">Soft sip / soft puff</dt>
        <dd>Gentle. The QuadStick <b>beeps</b> to tell you it registered.</dd>
        <dt class="puff">Hard sip / hard puff</dt>
        <dd>Firm. It <b>clicks</b> instead.</dd>
      </dl>
      <p>
        The beep and the click matter: they are how you know which one the device thought you
        did, without looking away from the game.
      </p>
      <img :src="frontPhoto" alt="The front of the QuadStick, showing the four holes" class="wide" />
      <p>
        Where the line sits between soft and hard is a setting
        (<span class="mono">sip_puff_threshold</span>). If gentle sips keep triggering the
        firm action, raise it. That is on the "Which setting wins" page.
      </p>
      <p class="aside">
        Two or three holes at once also count as their own inputs — left and centre together
        is not the same as left, then centre. Your Fortnite profile uses that for the stick
        clicks.
      </p>
    </template>

    <!-- 6 ------------------------------------------------------------------ -->
    <template v-if="slug === 'functions'">
      <p>
        The middle part of a row decides <b>how</b> the button behaves. In each picture, the
        top row is what you are doing and the bottom row is what the console sees.
      </p>
      <p v-if="reduceMotion" class="hint">
        The pictures are still, because your system asks for less movement. The whole
        pattern is shown at once instead, which is arguably easier to read.
      </p>
      <button v-else class="btn btn--small" type="button" @click="playDemos = !playDemos">
        {{ playDemos ? 'Stop the pictures moving' : 'Start the pictures moving' }}
      </button>
      <div class="demos">
        <FunctionDemo v-for="d in FUNCTION_DEMOS" :key="d.name" :demo="d" :play="playDemos" />
      </div>
      <p class="aside">
        There are a few more in the editor's list — <span class="mono">duty</span>,
        <span class="mono">less_than</span>, <span class="mono">force_off</span> and the
        value steppers. Each one explains itself where you pick it.
      </p>
    </template>

    <!-- 7 ------------------------------------------------------------------ -->
    <template v-if="slug === 'patterns'">
      <p>
        These are real rows out of your own two profiles. Nothing here is made up — the file
        and mode are named under each one.
      </p>
      <div class="patterns">
        <section v-for="p in PATTERNS" :key="p.title" class="pattern card">
          <h2>{{ p.title }}</h2>
          <p>{{ p.what }}</p>
          <table v-if="p.rows.length" class="rows">
            <thead>
              <tr>
                <th>Output</th>
                <th>How</th>
                <th>When you</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in p.rows" :key="i">
                <td class="mono">{{ r.output }}</td>
                <td class="mono">{{ r.fn }}</td>
                <td class="mono">{{ r.input }}</td>
              </tr>
            </tbody>
          </table>
          <p class="src">From {{ p.source }}</p>
        </section>
      </div>
    </template>

    <!-- 8 ------------------------------------------------------------------ -->
    <template v-if="slug === 'settings'">
      <p>
        Settings like the sip threshold or the mouse speed can be set in three places. When
        two disagree, the more specific one wins:
      </p>
      <ol class="precedence">
        <li>
          <b>The device</b> — <span class="mono">prefs.csv</span> on the flash drive. Applies
          to everything.
        </li>
        <li><b>The profile</b> — its own settings, while that file is loaded.</li>
        <li><b>One mode</b> — a row inside a mode, while that mode is active.</li>
      </ol>
      <p>
        So a profile can run a higher threshold than the device normally uses, and a single
        mode inside it can go higher still.
      </p>
      <p class="aside">
        The per-mode kind is real in the file format but has <b>not</b> been tried on your
        device yet. This app keeps any it finds exactly as they are and shows them read-only,
        rather than guessing.
      </p>
    </template>

    <!-- 9 ------------------------------------------------------------------ -->
    <template v-if="slug === 'safety'">
      <h2>Leave default.csv alone</h2>
      <p>
        <span class="mono">default.csv</span> is always file number one, and the QuadStick
        leans on it. If it is broken or missing, <b>the flash drive stops appearing</b> when
        you plug the device into a computer — and getting it back needs a hardware reset.
      </p>
      <p>
        Give new profiles their own filename. The app refuses to export over
        <span class="mono">default.csv</span> without warning you.
      </p>

      <h2>The modes that hide the drive</h2>
      <p>
        The QuadStick can pretend to be several different controllers. Some of those pretend
        so thoroughly that the flash drive disappears too — which means you cannot copy a
        fixed profile across if something goes wrong.
      </p>
      <p><b>Which ones depends on the firmware:</b></p>
      <ul class="plain">
        <li v-for="(modes, fw) in hiddenModes" :key="fw">
          Firmware <b>{{ fw }}</b>: modes
          <b>{{ modes.join(', ') }}</b> hide the drive<span
            v-if="String(fw) === String(catalog.catalog?.default_firmware)"
          >
            — this is the one your device runs</span
          >.
        </li>
      </ul>
      <p>
        Your PlayStation profiles use mode
        <b>4</b> ({{ emulationModes['4'] }}), which keeps the drive visible. Good.
      </p>
      <p class="aside">
        If you do need one of the hiding modes, keep a profile you know works on the drive
        first. Getting out otherwise means the side-tube recovery: long hard sip, joystick to
        another file, lip press.
      </p>
      <img :src="rearPhoto" alt="The back of the QuadStick, showing its jacks and USB sockets" class="wide" />
    </template>

    <nav class="pager">
      <RouterLink v-if="prev" class="btn" :to="`/learn/${prev.slug}`">← {{ prev.title }}</RouterLink>
      <span class="spacer" />
      <RouterLink v-if="next" class="btn" :to="`/learn/${next.slug}`">{{ next.title }} →</RouterLink>
    </nav>
  </article>

  <p v-else>
    That page does not exist. <RouterLink to="/learn">Back to the list</RouterLink>
  </p>
</template>

<style scoped>
.topic {
  max-width: 46rem;
}
.crumb {
  margin: 0 0 var(--sp-2);
  font-size: var(--text-sm);
}
.lede {
  font-size: var(--text-lg);
  color: var(--ink-soft);
}
h2 {
  font-size: var(--text-lg);
  margin-top: var(--sp-5);
}

.aside {
  padding: var(--sp-3);
  border-left: 4px solid var(--line-strong);
  background: var(--paper-sunk);
  border-radius: 0 var(--radius) var(--radius) 0;
  font-size: var(--text-sm);
}

.parts,
.steps,
.precedence {
  padding-left: 1.4rem;
}
.parts li,
.steps li,
.precedence li {
  margin-bottom: var(--sp-2);
}

.plain {
  padding-left: 1.2rem;
}
.plain li {
  margin-bottom: var(--sp-2);
}

.wide {
  display: block;
  width: 100%;
  max-width: 420px;
  height: auto;
  margin: var(--sp-3) 0;
}

.pairs {
  margin: var(--sp-3) 0;
}
.pairs dt {
  font-weight: 700;
  margin-top: var(--sp-2);
}
.pairs dt.sip {
  color: var(--sip);
}
.pairs dt.puff {
  color: var(--puff);
}
.pairs dd {
  margin: 0 0 var(--sp-2);
}

.leds-table {
  border-collapse: collapse;
  margin: var(--sp-3) 0;
}
.leds-table caption {
  text-align: left;
  font-size: var(--text-xs);
  color: var(--ink-soft);
  padding-bottom: var(--sp-1);
}
.leds-table th,
.leds-table td {
  border: 1px solid var(--line);
  padding: 3px var(--sp-2);
  text-align: left;
  font-size: var(--text-sm);
}
.leds {
  display: inline-flex;
  gap: 3px;
}
.leds i {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 1px solid var(--ink-soft);
  background: #fff;
}
.leds i.on {
  background: var(--led);
  border-color: var(--led);
}
.leds i.purple,
b.purple {
  --led: var(--led-purple);
  color: var(--led-purple);
}
.leds i.blue,
b.blue {
  --led: var(--led-blue);
  color: var(--led-blue);
}
.leds i.red,
b.red {
  --led: var(--led-red);
  color: var(--led-red);
}
.words {
  font-size: var(--text-xs);
  color: var(--ink-soft);
}

.demos {
  display: grid;
  gap: var(--sp-3);
  margin: var(--sp-3) 0;
}

.patterns {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  margin: var(--sp-3) 0;
}
.pattern {
  padding: var(--sp-4);
}
.pattern h2 {
  margin-top: 0;
  font-size: var(--text-base);
}
.rows {
  border-collapse: collapse;
  margin: var(--sp-2) 0;
  width: 100%;
}
.rows th,
.rows td {
  border: 1px solid var(--line);
  padding: 3px var(--sp-2);
  text-align: left;
  font-size: var(--text-sm);
}
.rows thead th {
  background: var(--paper-sunk);
  font-size: var(--text-xs);
}
.src {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--ink-faint);
}

.pager {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-top: var(--sp-6);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--line);
}
</style>
