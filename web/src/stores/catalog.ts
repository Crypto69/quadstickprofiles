// The catalog is the single source of truth for every keyword the UI may produce,
// and it comes from core/qsprofile/catalog.py via GET /api/catalog. It never
// changes while the app is open, so it is fetched once and cached.
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import { describe } from '@/api/errors'
import type { Catalog, FunctionEntry, InputEntry, OutputEntry } from '@/api/types'

/** One entry in an output picker. */
export interface OutputOption {
  /** The canonical (PlayStation) keyword — what gets stored. */
  name: string
  /** How it reads under the profile's console, e.g. `x` on PlayStation, `A` on Xbox. */
  shown: string
  /** The friendly description ("Cross"), falling back to the keyword. */
  label: string
}

/** One `<optgroup>`: the catalog group and its outputs, in catalog order. */
export interface OutputGroup {
  grp: string
  items: OutputOption[]
}

export const useCatalogStore = defineStore('catalog', () => {
  const catalog = ref<Catalog | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let inflight: Promise<void> | null = null

  /** Fetch once; concurrent callers share the same request. */
  async function load(force = false) {
    if (catalog.value && !force) return
    if (inflight && !force) return inflight
    loading.value = true
    error.value = null
    inflight = (async () => {
      try {
        catalog.value = await api.catalog()
      } catch (e) {
        error.value = describe(e)
        throw e
      } finally {
        loading.value = false
        inflight = null
      }
    })()
    return inflight
  }

  const loaded = computed(() => catalog.value !== null)

  const inputsByName = computed(() => {
    const m = new Map<string, InputEntry>()
    for (const i of catalog.value?.inputs ?? []) m.set(i.name, i)
    return m
  })

  const outputsByName = computed(() => {
    const m = new Map<string, OutputEntry>()
    for (const o of catalog.value?.outputs ?? []) m.set(o.name, o)
    return m
  })

  const functionsByName = computed(() => {
    const m = new Map<string, FunctionEntry>()
    for (const f of catalog.value?.functions ?? []) m.set(f.name, f)
    return m
  })

  /** Inputs the UI should offer, i.e. everything except the older names. */
  const currentInputs = computed(() =>
    (catalog.value?.inputs ?? []).filter((i) => i.kind !== 'legacy'),
  )

  const isLegacyInput = (name: string) => name in (catalog.value?.legacy_inputs ?? {})

  /** What the user should see for an output, under the profile's naming set. */
  function outputLabel(name: string, consoleName: 'playstation' | 'xbox' = 'playstation') {
    const o = outputsByName.value.get(name)
    if (!o) return name
    if (consoleName === 'xbox' && o.xbox_name) return o.xbox_name
    return name
  }

  function outputGlyph(name: string, consoleName: 'playstation' | 'xbox' = 'playstation') {
    const o = outputsByName.value.get(name)
    if (!o) return null
    return (consoleName === 'xbox' ? o.xbox_glyph : o.ps_glyph) ?? null
  }

  /** The friendly label ("Fire", "Left stick up"), falling back to the keyword. */
  const outputDescription = (name: string) => outputsByName.value.get(name)?.label ?? name
  const inputLabel = (name: string) => inputsByName.value.get(name)?.label ?? name

  /**
   * Outputs grouped for a picker, under the profile's naming set. One shape for
   * every dropdown: `name` is the canonical keyword to store, `shown` is how it reads
   * on this console (x / A), `label` is the friendly description ("Cross"). Catalog
   * order is kept within and across groups.
   */
  function outputGroups(consoleName: 'playstation' | 'xbox' = 'playstation'): OutputGroup[] {
    const groups = new Map<string, OutputOption[]>()
    for (const o of catalog.value?.outputs ?? []) {
      const grp = o.grp ?? 'other'
      if (!groups.has(grp)) groups.set(grp, [])
      groups.get(grp)!.push({
        name: o.name,
        shown: outputLabel(o.name, consoleName),
        label: o.label ?? o.name,
      })
    }
    return [...groups.entries()].map(([grp, items]) => ({ grp, items }))
  }

  /**
   * Does this emulation mode hide the flash drive on this firmware?
   *
   * `null` means "cannot tell": the firmware is not one the catalog knows. It used
   * to borrow the default firmware's set, and the editor then said the drive "stays
   * visible … Good" about a build nobody has checked. A view must treat `null` as
   * unknown, never as safe.
   */
  function hidesFlashDrive(
    emulationMode: number | null | undefined,
    firmware: number,
  ): boolean | null {
    if (emulationMode === null || emulationMode === undefined) return false
    const fw = catalog.value?.hidden_drive_modes
    if (!fw) return false
    const modes = fw[String(firmware)]
    if (!modes) return null
    return modes.includes(emulationMode)
  }

  return {
    catalog,
    loading,
    error,
    loaded,
    load,
    inputsByName,
    outputsByName,
    functionsByName,
    currentInputs,
    isLegacyInput,
    outputLabel,
    outputGlyph,
    outputDescription,
    inputLabel,
    outputGroups,
    hidesFlashDrive,
  }
})
