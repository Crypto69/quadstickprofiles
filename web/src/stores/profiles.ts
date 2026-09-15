// The Library's state: the list, the search box, and every action on a profile.
// Export and print are here too, because both are "produce a file from a profile"
// and both must respect the rule that errors block export.
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, api } from '@/api/client'
import { describe } from '@/api/errors'
import type { Download } from '@/api/client'
import type { Console, ImportResult, Profile, ProfileSummary, Validation } from '@/api/types'

export type Health = 'clean' | 'warnings' | 'errors' | 'unknown'

/** One badge per profile, from the validation counts. */
export function healthOf(v: Validation | null | undefined): Health {
  if (!v) return 'unknown'
  if (v.errors > 0) return 'errors'
  if (v.warnings > 0) return 'warnings'
  return 'clean'
}

/** A refused export: the reason, and the findings that caused it. */
export interface Blocked {
  profileId: number
  message: string
  validation: Validation | null
}

export const useProfilesStore = defineStore('profiles', () => {
  const profiles = ref<ProfileSummary[]>([])
  /** The starter profiles, loaded separately so the library stays the user's own. */
  const templates = ref<ProfileSummary[]>([])
  const search = ref('')
  /**
   * Library filters. Both are facts already on every summary, and the list is small
   * enough to live in memory, so these narrow it here rather than through the API —
   * ticking a box costs no request and cannot leave the list stale.
   *
   * Empty set = no filter on that group, which is not the same as "all ticked":
   * unticking the last box returns everything instead of showing nothing.
   */
  const consoleFilter = ref<Set<Console>>(new Set())
  const emulationFilter = ref<Set<number>>(new Set())
  const loading = ref(false)
  const busyId = ref<number | null>(null) // the profile a long action is running on
  const error = ref<string | null>(null)
  const blocked = ref<Blocked | null>(null) // an export refused for validation errors
  const lastImport = ref<ImportResult | null>(null) // drives the import-findings dialog

  /**
   * Generation counter. Typing in the search box, and every action that reloads the
   * list afterwards, can leave two requests in flight; a slow older answer landing
   * last would show results for a query the user has already moved on from — or
   * raise a banner for a search that has since succeeded. Only the newest may write.
   */
  let loadSeq = 0

  async function load(opts?: { q?: string }) {
    const seq = ++loadSeq
    loading.value = true
    error.value = null
    try {
      const q = opts?.q ?? search.value
      const list = await api.listProfiles({ q: q || undefined, validate: true })
      if (seq !== loadSeq) return
      profiles.value = list
    } catch (e) {
      if (seq !== loadSeq) return
      error.value = describe(e)
    } finally {
      if (seq === loadSeq) loading.value = false
    }
  }

  /** Run an action against one profile, tracking busy state and errors. */
  async function act<T>(id: number, fn: () => Promise<T>): Promise<T | null> {
    busyId.value = id
    error.value = null
    blocked.value = null
    try {
      return await fn()
    } catch (e) {
      if (e instanceof ApiError && e.isValidationBlock) {
        blocked.value = { profileId: id, message: e.message, validation: e.validation ?? null }
      } else {
        error.value = describe(e)
      }
      return null
    } finally {
      busyId.value = null
    }
  }

  /**
   * A profile whose emulation mode is absent (no `enable_DS3_emulation` row) answers
   * to no device box. That is deliberate: we do not know what it runs on, and guessing
   * a default here would hide it from the one filter that would have found it.
   */
  function matchesFilters(p: ProfileSummary) {
    if (consoleFilter.value.size && !consoleFilter.value.has(p.console)) return false
    if (emulationFilter.value.size) {
      if (p.emulation_mode === null) return false
      if (!emulationFilter.value.has(p.emulation_mode)) return false
    }
    return true
  }

  /** What the library renders: the loaded list, narrowed by the ticked boxes. */
  const visible = computed(() => profiles.value.filter(matchesFilters))

  /**
   * The consoles and emulation modes actually present in the library. A filter the
   * user cannot reach a profile through is worse than no filter: `emulation_mode` is
   * absent from every profile that never set `enable_DS3_emulation`, which is most of
   * them, so offering all eight device chips would be eight dead ends. The view offers
   * only these (plus anything already ticked).
   */
  const presentConsoles = computed(() => new Set(profiles.value.map((p) => p.console)))

  const presentEmulations = computed(() => {
    const s = new Set<number>()
    for (const p of profiles.value) if (p.emulation_mode !== null) s.add(p.emulation_mode)
    return s
  })

  const filtering = computed(() => consoleFilter.value.size > 0 || emulationFilter.value.size > 0)

  /**
   * How many profiles each box would leave, counted with that box's own group ignored.
   * Within a group the boxes are an OR, so a count must not be narrowed by its
   * siblings — otherwise ticking "Xbox" would show "PlayStation 0" and read as if
   * adding it did nothing.
   */
  const consoleCounts = computed(() => {
    const m = new Map<Console, number>()
    for (const p of profiles.value) {
      if (emulationFilter.value.size && (p.emulation_mode === null || !emulationFilter.value.has(p.emulation_mode))) continue
      m.set(p.console, (m.get(p.console) ?? 0) + 1)
    }
    return m
  })

  const emulationCounts = computed(() => {
    const m = new Map<number, number>()
    for (const p of profiles.value) {
      if (consoleFilter.value.size && !consoleFilter.value.has(p.console)) continue
      if (p.emulation_mode === null) continue
      m.set(p.emulation_mode, (m.get(p.emulation_mode) ?? 0) + 1)
    }
    return m
  })

  function toggleConsole(c: Console) {
    const next = new Set(consoleFilter.value)
    next.has(c) ? next.delete(c) : next.add(c)
    consoleFilter.value = next
  }

  function toggleEmulation(mode: number) {
    const next = new Set(emulationFilter.value)
    next.has(mode) ? next.delete(mode) : next.add(mode)
    emulationFilter.value = next
  }

  function clearFilters() {
    consoleFilter.value = new Set()
    emulationFilter.value = new Set()
  }

  const byId = computed(() => {
    const m = new Map<number, ProfileSummary>()
    for (const p of profiles.value) m.set(p.id, p)
    return m
  })

  const health = (p: ProfileSummary) => healthOf(p.validation)
  const canExport = (p: ProfileSummary) => (p.validation?.errors ?? 0) === 0

  // ---------------------------------------------------------------- actions
  async function importFile(file: File, opts?: { game?: string; name?: string; firmware?: number }) {
    loading.value = true
    error.value = null
    try {
      const result = await api.importProfile(file, opts)
      lastImport.value = result
      await load()
      return result
    } catch (e) {
      error.value = describe(e)
      return null
    } finally {
      loading.value = false
    }
  }

  function dismissImport() {
    lastImport.value = null
  }

  function dismissBlocked() {
    blocked.value = null
  }

  /** Clear the last failure. Opening a dialog that shows errors inside itself calls
   *  this, so a failure left over from an earlier action is not read as this one's. */
  function dismissError() {
    error.value = null
  }

  async function duplicate(id: number, opts?: { name?: string; csv_filename?: string }) {
    const p = await act(id, () => api.duplicateProfile(id, opts))
    if (p) await load()
    return p
  }

  async function convert(id: number, target: Console, opts?: { name?: string; csv_filename?: string }) {
    const r = await act(id, () => api.convertProfile(id, { target, ...opts }))
    if (r) await load()
    return r
  }

  /**
   * Change a profile's name and the filename the QuadStick loads it by, and nothing
   * else. PATCH, not PUT: the device goes by the filename, so this is the edit the
   * owner reaches for most, and PUT would mean fetching and resending every mode and
   * preference just to change two strings — with the whole document at risk if the
   * library's copy were stale. PATCH ignores `modes` and `preferences` by design
   * (see ProfilePatch), which is exactly the guarantee wanted here.
   */
  async function rename(id: number, body: { name: string; csv_filename: string }) {
    const p = await act(id, () => api.patchProfile(id, body))
    if (p) await load()
    return p
  }

  async function remove(id: number) {
    const ok = await act(id, async () => {
      await api.deleteProfile(id)
      return true
    })
    if (ok) await load()
    return ok === true
  }

  async function loadTemplates() {
    try {
      templates.value = await api.listProfiles({ templates: true })
    } catch (e) {
      error.value = describe(e)
    }
  }

  async function createFromTemplate(
    templateId: number,
    body: { name: string; csv_filename: string; game?: string },
  ) {
    loading.value = true
    error.value = null
    try {
      const p = await api.createFromTemplate(templateId, body)
      await load()
      return p
    } catch (e) {
      error.value = describe(e)
      return null
    } finally {
      loading.value = false
    }
  }

  async function create(body: { name: string; csv_filename: string; game?: string }) {
    loading.value = true
    error.value = null
    try {
      const p = await api.createProfile(body)
      await load()
      return p
    } catch (e) {
      error.value = describe(e)
      return null
    } finally {
      loading.value = false
    }
  }

  /** CSV or XLSX. Returns the bytes; the caller decides how to hand them over. */
  async function exportFile(id: number, kind: 'csv' | 'xlsx', filename?: string) {
    return act(id, () => (kind === 'csv' ? api.exportCsv(id, filename) : api.exportXlsx(id, filename)))
  }

  async function validate(id: number): Promise<Validation | null> {
    return act(id, () => api.validateProfile(id))
  }

  async function get(id: number): Promise<Profile | null> {
    return act(id, () => api.getProfile(id))
  }

  return {
    profiles, templates, search, loading, busyId, error, blocked, lastImport,
    consoleFilter, emulationFilter, visible, filtering, consoleCounts, emulationCounts,
    presentConsoles, presentEmulations,
    byId, health, canExport,
    load, loadTemplates, importFile, dismissImport, dismissBlocked, dismissError, duplicate, convert,
    rename, remove, create, createFromTemplate, exportFile, validate, get,
    toggleConsole, toggleEmulation, clearFilters,
  }
})

export type { Download }
