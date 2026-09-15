<script setup lang="ts">
// The fixed bar along the bottom of an editing page. Its colour is the page's
// worst finding, so the state is visible without reading anything.
import type { Severity } from '@/api/types'

defineProps<{ severity?: Severity | null }>()
</script>

<template>
  <div class="bottom" :class="severity ? `is-${severity}` : 'is-ok'">
    <slot />
  </div>
</template>

<style scoped>
.bottom {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  padding: var(--sp-2) var(--sp-4);
  background: var(--paper);
  border-top: 3px solid var(--line);
}
.bottom.is-error {
  border-top-color: var(--error);
  background: var(--error-soft);
}
.bottom.is-warning {
  border-top-color: var(--warning);
  background: var(--warning-soft);
}
.bottom.is-ok {
  border-top-color: var(--ok);
}
</style>
