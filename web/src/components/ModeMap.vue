<script setup lang="ts">
/**
 * How the modes connect: which input takes you from one to the next, and — the
 * point of the diagram — which modes you cannot get out of. A mode with no
 * increment_mode / decrement_mode / load_file is a trap on the device: the only
 * way out is unplugging it.
 */
import { computed } from 'vue'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'

const catalog = useCatalogStore()
const docStore = useDocumentStore()

const modes = computed(() => docStore.doc?.modes ?? [])
const changeOutputs = computed(() => new Set(catalog.catalog?.mode_change_outputs ?? []))

interface Node {
  n: number
  name: string
  x: number
  y: number
  exits: { output: string; input: string; to: number | null }[]
  trapped: boolean
}

const R = 26

/** Modes on a circle, which keeps the arrows short however many there are. */
const nodes = computed<Node[]>(() => {
  const list = modes.value
  const cx = 200
  const cy = 150
  const radius = list.length <= 1 ? 0 : Math.min(120, 40 + list.length * 9)
  return list.map((m, i) => {
    const angle = (i / Math.max(1, list.length)) * Math.PI * 2 - Math.PI / 2
    const exits = m.mappings
      .filter((r) => r.kind === 'mapping' && changeOutputs.value.has(r.output) && r.inputs.length)
      .map((r) => ({
        output: r.output,
        input: r.inputs[r.inputs.length - 1]!,
        to: destination(r.output, i + 1, list.length),
      }))
    return {
      n: i + 1,
      name: m.name,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      exits,
      trapped: exits.length === 0,
    }
  })
})

/** increment/decrement wrap around; load_file leaves the profile entirely. */
function destination(output: string, from: number, total: number): number | null {
  if (output === 'increment_mode') return from >= total ? 1 : from + 1
  if (output === 'decrement_mode') return from <= 1 ? total : from - 1
  return null // load_file: another profile
}

const edges = computed(() =>
  nodes.value.flatMap((node) =>
    node.exits
      .filter((e) => e.to !== null && e.to !== node.n)
      .map((e) => {
        const to = nodes.value.find((x) => x.n === e.to)!
        return { from: node, to, input: e.input, output: e.output }
      }),
  ),
)

const trapped = computed(() => nodes.value.filter((n) => n.trapped))

/** Shorten the line so the arrowhead lands on the edge of the circle, not in it. */
function edgePath(e: { from: Node; to: Node }) {
  const dx = e.to.x - e.from.x
  const dy = e.to.y - e.from.y
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len
  const x1 = e.from.x + ux * (R + 2)
  const y1 = e.from.y + uy * (R + 2)
  const x2 = e.to.x - ux * (R + 6)
  const y2 = e.to.y - uy * (R + 6)
  return `M ${x1} ${y1} L ${x2} ${y2}`
}

function inputLabel(input: string) {
  return docStore.inputName(input, catalog.inputLabel(input))
}
</script>

<template>
  <div class="map">
    <svg viewBox="0 0 400 300" role="img" :aria-label="`How the ${modes.length} modes connect`">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6"
                orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--ink-soft)" />
        </marker>
      </defs>

      <path
        v-for="(e, i) in edges"
        :key="i"
        :d="edgePath(e)"
        class="edge"
        marker-end="url(#arrow)"
      />

      <g v-for="n in nodes" :key="n.n" :class="{ trapped: n.trapped }">
        <circle :cx="n.x" :cy="n.y" :r="R" class="node" />
        <text :x="n.x" :y="n.y + 5" class="node-num">{{ n.n }}</text>
        <text :x="n.x" :y="n.y + R + 14" class="node-name">{{ n.name }}</text>
      </g>
    </svg>

    <div class="legend">
      <p v-if="trapped.length" class="trap-warning">
        You cannot leave
        {{ trapped.map((t) => `mode ${t.n} (${t.name})`).join(', ') }}
        — nothing in there changes mode, so the only way out is unplugging the QuadStick.
      </p>
      <p v-else class="hint">Every mode has a way out.</p>

      <ul v-if="edges.length" class="edges">
        <li v-for="(e, i) in edges" :key="i">
          <b>{{ e.from.n }} → {{ e.to.n }}</b>
          {{ inputLabel(e.input) }}
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.map {
  display: grid;
  grid-template-columns: minmax(260px, 400px) 1fr;
  gap: var(--sp-4);
  align-items: start;
}

svg {
  width: 100%;
  height: auto;
}

.edge {
  stroke: var(--ink-soft);
  stroke-width: 1.5;
  fill: none;
}

.node {
  fill: var(--mode-soft);
  stroke: var(--mode);
  stroke-width: 2;
}
.trapped .node {
  fill: var(--warning-soft);
  stroke: var(--warning);
  stroke-dasharray: 4 3;
}

.node-num {
  text-anchor: middle;
  font-size: 15px;
  font-weight: 700;
  fill: var(--mode);
}
.trapped .node-num {
  fill: var(--warning);
}

.node-name {
  text-anchor: middle;
  font-size: 11px;
  fill: var(--ink-soft);
}

.trap-warning {
  margin: 0 0 var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--warning-soft);
  color: var(--warning);
  font-size: var(--text-sm);
  font-weight: 600;
}

.edges {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: var(--text-xs);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

@media (max-width: 720px) {
  .map {
    grid-template-columns: 1fr;
  }
}
</style>
