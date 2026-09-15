<script setup lang="ts">
import { computed } from 'vue'
import type { Validation } from '@/api/types'
import { healthOf } from '@/stores/profiles'

const props = defineProps<{ validation: Validation | null | undefined }>()

const health = computed(() => healthOf(props.validation))

const text = computed(() => {
  const v = props.validation
  if (!v) return 'Not checked'
  if (v.errors) return `${v.errors} ${v.errors === 1 ? 'error' : 'errors'}`
  if (v.warnings) return `${v.warnings} ${v.warnings === 1 ? 'warning' : 'warnings'}`
  return 'Clean'
})

/** The badge says what the device would do, not just a count. */
const title = computed(() => {
  const v = props.validation
  if (!v) return 'This profile has not been checked yet'
  if (v.errors) return v.consequence.error ?? 'The QuadStick will not read this profile correctly'
  if (v.warnings) return v.consequence.warning ?? 'Loads, but some rows will not behave as expected'
  return 'No problems found'
})

const cls = computed(
  () =>
    ({
      errors: 'badge--error',
      warnings: 'badge--warning',
      clean: 'badge--ok',
      unknown: 'badge--info',
    })[health.value],
)
</script>

<template>
  <span class="badge" :class="cls" :title="title">{{ text }}</span>
</template>
