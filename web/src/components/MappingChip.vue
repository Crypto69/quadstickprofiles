<script setup lang="ts">
// One mapping, as it appears inside a slot: the output's glyph or name, the game
// action if one is set, the function if it is not plain, and an "after …" tag when
// the row is a sequence (the row fires on its LAST input, after the earlier ones).
import { computed } from 'vue'
import type { EditMapping } from '@/stores/document'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'

const props = defineProps<{ mapping: EditMapping; consoleName: 'playstation' | 'xbox' }>()

const catalog = useCatalogStore()
const docStore = useDocumentStore()

const glyph = computed(() => catalog.outputGlyph(props.mapping.output, props.consoleName))
const name = computed(() => catalog.outputLabel(props.mapping.output, props.consoleName))
const action = computed(() =>
  docStore.actionFor(props.mapping.output, docStore.selectedMode?.name),
)

const fn = computed(() => {
  const m = props.mapping
  if (m.function === 'normal' && m.params.length === 0) return null
  return m.params.length ? `${m.function} ${m.params.join(' ')}` : m.function
})

/** A sequence row fires after the earlier inputs, which is worth saying. */
const after = computed(() => {
  const ins = props.mapping.inputs
  if (ins.length < 2) return null
  return ins
    .slice(0, -1)
    .map((i) => docStore.inputName(i, catalog.inputLabel(i)))
    .join(' then ')
})

const isSystem = computed(() =>
  (catalog.catalog?.mode_change_outputs ?? []).includes(props.mapping.output),
)
</script>

<template>
  <span class="chip" :class="{ system: isSystem }">
    <b v-if="glyph" class="glyph">{{ glyph }}</b>
    <span class="name">{{ action ?? name }}</span>
    <span v-if="action" class="key">{{ name }}</span>
    <span v-if="fn" class="fn">{{ fn }}</span>
    <span v-if="after" class="after">after {{ after }}</span>
  </span>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
  padding: 3px 6px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--paper);
  font-size: var(--text-xs);
  line-height: 1.3;
  text-align: left;
}

.glyph {
  font-size: var(--text-sm);
  font-weight: 700;
}
.chip.system .glyph,
.chip.system .name {
  color: var(--mode);
}

.name {
  font-weight: 600;
}
.key {
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.fn {
  padding: 1px 4px;
  border-radius: 3px;
  background: var(--ink);
  color: #fff;
  font-size: 0.85em;
  white-space: nowrap;
}

.after {
  width: 100%;
  color: var(--mode);
  font-size: 0.85em;
}
</style>
