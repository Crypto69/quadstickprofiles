<script setup lang="ts">
/**
 * The settings, grouped by category, with the fiddly ones folded away. Used for
 * both the device's own settings and a profile's, which differ only in what a blank
 * value falls back to.
 */
import { computed, ref } from 'vue'
import PreferenceField from './PreferenceField.vue'
import { useCatalogStore } from '@/stores/catalog'

const props = defineProps<{
  values: Record<string, string>
  /** What a blank value falls back to, named for the user. */
  inheritedFrom?: string
  /** The values from that level, so a blank field can show what will apply. */
  inherited?: Record<string, string>
  /** Only these keys, in this order. Used for the "what you changed" summary. */
  only?: string[]
}>()

const emit = defineEmits<{ update: [key: string, value: string] }>()

const catalog = useCatalogStore()
const showAdvanced = ref(false)
const search = ref('')

const all = computed(() => Object.entries(catalog.catalog?.preferences ?? {}))

const matching = computed(() => {
  const q = search.value.trim().toLowerCase()
  return all.value.filter(([name, entry]) => {
    if (props.only && !props.only.includes(name)) return false
    if (!showAdvanced.value && entry.advanced && !isSet(name)) return false
    if (!q) return true
    return (
      name.toLowerCase().includes(q) ||
      entry.label.toLowerCase().includes(q) ||
      (entry.description ?? '').toLowerCase().includes(q)
    )
  })
})

const groups = computed(() => {
  const out = new Map<string, [string, (typeof all.value)[number][1]][]>()
  for (const [name, entry] of matching.value) {
    const cat = entry.category || 'Other'
    if (!out.has(cat)) out.set(cat, [])
    out.get(cat)!.push([name, entry])
  }
  return [...out.entries()]
})

function isSet(name: string) {
  const v = props.values[name]
  return v !== undefined && v !== ''
}

const setCount = computed(() => Object.keys(props.values).filter(isSet).length)
const advancedCount = computed(() => all.value.filter(([, e]) => e.advanced).length)
</script>

<template>
  <div class="editor">
    <div class="controls row">
      <div class="field grow">
        <label for="pref-search">Find a setting</label>
        <input
          id="pref-search"
          v-model="search"
          class="input"
          type="search"
          placeholder="threshold, mouse, volume…"
          autocomplete="off"
        />
      </div>
      <label class="check">
        <input v-model="showAdvanced" type="checkbox" />
        Show the fiddly ones ({{ advancedCount }})
      </label>
    </div>

    <p class="hint">
      {{ setCount }} {{ setCount === 1 ? 'setting is' : 'settings are' }} set here.
      Anything left blank is decided by
      {{ inheritedFrom ?? 'the QuadStick' }}.
    </p>

    <p v-if="!groups.length" class="hint">Nothing matches “{{ search }}”.</p>

    <details v-for="[cat, items] in groups" :key="cat" class="group" open>
      <summary>
        {{ cat }}
        <span class="count">{{ items.filter(([n]) => isSet(n)).length }} of {{ items.length }} set</span>
      </summary>
      <div class="fields">
        <PreferenceField
          v-for="[name, entry] in items"
          :key="name"
          :name="name"
          :entry="entry"
          :value="values[name]"
          :inherited-from="inheritedFrom"
          :inherited-value="inherited?.[name]"
          @update="(v) => emit('update', name, v)"
        />
      </div>
    </details>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.controls {
  align-items: flex-end;
}
.grow {
  flex: 1 1 14rem;
}
.check {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--target);
  font-size: var(--text-sm);
  font-weight: 600;
}
.check input {
  width: 20px;
  height: 20px;
}

.group {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper-sunk);
}
summary {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-height: var(--target);
  padding: 0 var(--sp-3);
  font-weight: 700;
  cursor: pointer;
}
.count {
  margin-left: auto;
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--ink-soft);
}

.fields {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3);
  padding-top: 0;
}
</style>
