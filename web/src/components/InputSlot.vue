<script setup lang="ts">
// One input on the device: everything mapped to it, or a dashed empty slot. The
// whole slot is a single button, so assigning a mapping is one click with no
// held keys — the rule the whole editor follows.
import { computed } from 'vue'
import MappingChip from './MappingChip.vue'
import type { EditMapping } from '@/stores/document'

const props = defineProps<{
  input: string
  /** Display name, which the profile may have renamed (lip -> "Chin switch"). */
  label: string
  mappings: EditMapping[]
  consoleName: 'playstation' | 'xbox'
  /** sip / puff colours the slot border, matching the printed card. */
  tone?: 'sip' | 'puff' | null
  selected?: boolean
}>()

const emit = defineEmits<{ select: [input: string] }>()

const empty = computed(() => props.mappings.length === 0)

const describedAs = computed(() =>
  empty.value
    ? `${props.label}: free, nothing mapped`
    : `${props.label}: ${props.mappings.length} mapped`,
)
</script>

<template>
  <button
    type="button"
    class="slot"
    :class="[
      tone ? `is-${tone}` : '',
      { empty, selected },
    ]"
    :aria-label="describedAs"
    :aria-pressed="selected"
    @click="emit('select', input)"
  >
    <span class="slot-label">{{ label }}</span>
    <span v-if="empty" class="free">free</span>
    <MappingChip
      v-for="m in mappings"
      :key="m.key"
      :mapping="m"
      :console-name="consoleName"
    />
  </button>
</template>

<style scoped>
.slot {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 3px;
  width: 100%;
  min-height: var(--target);
  padding: var(--sp-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
  cursor: pointer;
  text-align: left;
  font: inherit;
}
.slot:hover {
  border-color: var(--line-strong);
  background: var(--paper-sunk);
}
.slot.selected {
  border-color: var(--mode);
  box-shadow: inset 0 0 0 1px var(--mode);
}

/* An empty slot is visibly free rather than just blank — the same hatching the
   printed card uses for an unused cell. */
.slot.empty {
  border-style: dashed;
  background: repeating-linear-gradient(45deg, #fff 0 6px, var(--paper-sunk) 6px 7px);
}

.slot.is-sip {
  border-left: 4px solid var(--sip);
}
.slot.is-puff {
  border-left: 4px solid var(--puff);
}

.slot-label {
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--ink-soft);
}

.free {
  font-size: var(--text-xs);
  color: var(--ink-faint);
  font-style: italic;
}
</style>
