<script setup lang="ts">
import { computed } from 'vue'
import type { Finding, Severity, Validation } from '@/api/types'

const props = withDefaults(
  defineProps<{
    validation: Validation | null | undefined
    /** Hide the info findings behind a toggle; errors and warnings always show. */
    collapseInfo?: boolean
    limit?: number
  }>(),
  { collapseInfo: true },
)

const ORDER: Severity[] = ['error', 'warning', 'info']

const findings = computed(() => props.validation?.findings ?? [])

const shown = computed(() => {
  let list = findings.value
  if (props.collapseInfo) list = list.filter((f) => f.severity !== 'info')
  return props.limit ? list.slice(0, props.limit) : list
})

const hiddenCount = computed(() => findings.value.length - shown.value.length)

/** Consequence lines for the severities actually present, worst first. */
const consequences = computed(() => {
  const c = props.validation?.consequence ?? {}
  return ORDER.filter((s) => c[s]).map((s) => ({ severity: s, text: c[s] as string }))
})

function where(f: Finding) {
  const bits: string[] = []
  if (f.mode !== null) bits.push(`Mode ${f.mode}`)
  if (f.row !== null) bits.push(`row ${f.row}`)
  return bits.join(', ')
}
</script>

<template>
  <div v-if="findings.length" class="findings">
    <p v-for="c in consequences" :key="c.severity" class="consequence" :class="`is-${c.severity}`">
      {{ c.text }}
    </p>

    <ul>
      <li v-for="(f, i) in shown" :key="i" :class="f.severity">
        <span class="sev">{{ f.severity }}</span>
        <span>
          <b v-if="where(f)" class="where">{{ where(f) }}</b>
          {{ f.message }}
        </span>
      </li>
    </ul>

    <p v-if="hiddenCount > 0" class="hint">
      {{ hiddenCount }} more {{ hiddenCount === 1 ? 'note' : 'notes' }} not shown.
    </p>
  </div>
  <p v-else class="hint">No problems found.</p>
</template>

<style scoped>
.findings ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.findings li {
  display: flex;
  gap: var(--sp-3);
  align-items: baseline;
  padding-left: var(--sp-3);
  border-left: 4px solid var(--line);
  font-size: var(--text-sm);
}
.findings li.error {
  border-color: var(--error);
}
.findings li.warning {
  border-color: var(--warning);
}
.findings li.info {
  border-color: var(--line-strong);
  color: var(--ink-soft);
}

.sev {
  flex: none;
  width: 4.5rem;
  font-size: var(--text-xs);
  font-weight: 700;
  text-transform: capitalize;
  color: var(--ink-soft);
}
li.error .sev {
  color: var(--error);
}
li.warning .sev {
  color: var(--warning);
}

.where {
  font-weight: 700;
}
.where::after {
  content: ' · ';
  font-weight: 400;
  color: var(--ink-faint);
}

.consequence {
  margin: 0 0 var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  font-size: var(--text-sm);
  font-weight: 600;
}
.consequence.is-error {
  background: var(--error-soft);
  color: var(--error);
}
.consequence.is-warning {
  background: var(--warning-soft);
  color: var(--warning);
}
.consequence.is-info {
  background: var(--info-soft);
  color: var(--ink-soft);
}
</style>
