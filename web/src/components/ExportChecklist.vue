<script setup lang="ts">
// The last step of getting a profile onto the QuadStick stays manual on purpose.
// This is the checklist for it: what was written, where it went, and
// the physical steps on the device — including the two things that can go wrong.
import { computed, ref, watch } from 'vue'
import ModalDialog from './ModalDialog.vue'
import type { Download } from '@/api/client'
import { saveBlob } from '@/composables/useDownload'
import { isDesktop } from '@/desktop'
import { ledSentence, ledsFor } from '@/device/layout'

/** A worked example of the LED rule, from the same table the screen and card use. */
const example = (n: number) => `${ledSentence(ledsFor(n))} is file ${n}`

const props = defineProps<{
  open: boolean
  download: Download | null
  profileName: string
}>()
const emit = defineEmits<{ close: [] }>()

const done = ref<Set<number>>(new Set())

// A fresh export is a fresh checklist.
watch(
  () => props.download,
  () => {
    done.value = new Set()
  },
)

const steps = computed(() => [
  {
    title: `Copy ${props.download?.filename ?? 'the file'} onto the QuadStick's flash drive`,
    detail:
      'Plug the QuadStick into this computer with the data cable. It shows up as a USB drive. ' +
      'Copy the file to the top level of that drive, not into a folder.',
  },
  {
    title: 'Do not replace default.csv',
    detail:
      'default.csv is always file number 1. If it is broken the flash drive stops appearing, ' +
      'and getting it back needs a hardware reset. Leave it alone.',
  },
  {
    title: 'Eject the drive, then unplug and replug the QuadStick',
    detail:
      'The QuadStick only re-reads its drive at power-on. At boot it deletes every non-.csv ' +
      'file (except joystick.bin) and every dot-file, so keep backups off the stick.',
  },
  {
    title: 'Pick the file on the device',
    detail:
      'Long hard sip on the side tube. Then move the joystick until the status LEDs show the ' +
      'file you want. Then press the lip button. Files are in alphabetical order. Files 1 to 5 ' +
      'light that one LED purple. 6 to 9: LED 5 purple plus one more — add them ' +
      `(${example(7)}). 10 to 14: LED 5 blue plus one more — add ten (${example(12)}). ` +
      `15 and 16: LED 5 red (${example(16)}).`,
  },
  {
    title: 'Check it in the game',
    detail: 'Print the reference card first if you want the mapping next to you while you try it.',
  },
])

const allDone = computed(() => done.value.size === steps.value.length)

function toggle(i: number) {
  const next = new Set(done.value)
  if (next.has(i)) next.delete(i)
  else next.add(i)
  done.value = next
}

// In the desktop build the file is already on disk, so the button shows it instead.
const desktop = isDesktop()

function saveAgain() {
  if (props.download) saveBlob(props.download.blob, props.download.filename, props.download.exportPath)
}
</script>

<template>
  <ModalDialog :open="open" title="Put this profile on the QuadStick" @close="emit('close')">
    <p v-if="download">
      <b>{{ download.filename }}</b> was saved from <b>{{ profileName }}</b>.
    </p>
    <p v-if="download?.exportPath" class="hint">
      <template v-if="desktop">Saved to <span class="mono">{{ download.exportPath }}</span>.</template>
      <template v-else
        >The server also wrote it to <span class="mono">{{ download.exportPath }}</span
        >, so you can reach it from the exports share.</template
      >
    </p>

    <ol class="steps">
      <li v-for="(s, i) in steps" :key="i" :class="{ done: done.has(i) }">
        <label>
          <input type="checkbox" :checked="done.has(i)" @change="toggle(i)" />
          <span>
            <b>{{ s.title }}</b>
            <span class="detail">{{ s.detail }}</span>
          </span>
        </label>
      </li>
    </ol>

    <p v-if="allDone" class="all-done" role="status">That's everything. Have fun.</p>

    <template #actions>
      <button v-if="download" class="btn" type="button" @click="saveAgain">
        {{ desktop ? 'Show in folder' : 'Save the file again' }}
      </button>
      <button class="btn btn--primary" type="button" @click="emit('close')">Done</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.steps {
  list-style: none;
  margin: var(--sp-4) 0 0;
  padding: 0;
  counter-reset: step;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.steps li {
  counter-increment: step;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
}
.steps li.done {
  background: var(--ok-soft);
  border-color: var(--ok);
}

/* The whole row is the target: one pointer, nothing to hold. */
.steps label {
  display: flex;
  gap: var(--sp-3);
  align-items: flex-start;
  min-height: var(--target);
  padding: var(--sp-3);
  cursor: pointer;
}

.steps input {
  flex: none;
  width: 22px;
  height: 22px;
  margin-top: 2px;
  accent-color: var(--ok);
}

.steps b::before {
  content: counter(step) '. ';
  color: var(--ink-faint);
}

.detail {
  display: block;
  margin-top: 2px;
  font-size: var(--text-sm);
  color: var(--ink-soft);
}

.all-done {
  margin: var(--sp-4) 0 0;
  font-weight: 700;
  color: var(--ok);
}
</style>
