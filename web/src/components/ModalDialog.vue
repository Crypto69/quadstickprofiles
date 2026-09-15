<script setup lang="ts">
// A dialog that is operable with one pointer and with the keyboard: Escape closes,
// focus moves in on open and back out on close, and nothing needs a held key.
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{ open: boolean; title: string; describedBy?: string }>()
const emit = defineEmits<{ close: [] }>()

const panel = ref<HTMLElement | null>(null)
let returnFocusTo: HTMLElement | null = null

async function activate() {
  returnFocusTo = document.activeElement as HTMLElement | null
  await nextTick()
  // focus the panel itself, not the first control: a screen reader then reads the title
  panel.value?.focus()
  document.addEventListener('keydown', onKeydown)
}

function deactivate() {
  document.removeEventListener('keydown', onKeydown)
  returnFocusTo?.focus?.()
  returnFocusTo = null
}

// `immediate` matters: a dialog whose `open` is already true on mount must still
// take focus and listen for Escape, or it traps the user with no keyboard way out.
watch(() => props.open, (open) => (open ? activate() : deactivate()), { immediate: true })

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  }
}

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="scrim" @click.self="emit('close')">
      <div
        ref="panel"
        class="panel card"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        :aria-describedby="describedBy"
        tabindex="-1"
      >
        <header>
          <h2>{{ title }}</h2>
          <button class="btn btn--quiet btn--small" type="button" @click="emit('close')">
            Close
          </button>
        </header>
        <div class="body">
          <slot />
        </div>
        <footer v-if="$slots.actions">
          <slot name="actions" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.scrim {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--sp-5) var(--sp-4);
  overflow: auto;
  background: rgb(29 29 27 / 45%);
}

.panel {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
}
.panel:focus-visible {
  outline: var(--focus);
  outline-offset: 4px;
}

header,
footer {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-4) var(--sp-5);
}
header {
  border-bottom: 1px solid var(--line);
}
header h2 {
  margin: 0;
  flex: 1 1 auto;
  font-size: var(--text-lg);
}
footer {
  border-top: 1px solid var(--line);
  justify-content: flex-end;
  flex-wrap: wrap;
}

.body {
  padding: var(--sp-5);
}
</style>
