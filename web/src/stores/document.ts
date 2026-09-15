// The profile being edited. Holds one working copy, tracks whether it differs from
// what was saved, and runs live checks against POST /api/profiles/validate — which
// writes nothing, so typing never touches the database. Saving is explicit.
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { api } from '@/api/client'
import { describe } from '@/api/errors'
import type {
  Budget, Channel, Console, Finding, MappingIn, ModeIn, Profile, ProfileCreate, ProfileMeta,
  Severity,
  Validation,
} from '@/api/types'

/** The editable document: a profile without its server-assigned ids. */
export interface EditDoc {
  name: string
  csv_filename: string
  game: string | null
  console: Console
  firmware: number
  notes: string | null
  modes: EditMode[]
  preferences: Record<string, string>
  input_names: Record<string, string>
  game_actions: { output: string; action: string; mode_name: string | null }[]
}

export interface EditMode {
  /** Stable within the session, so the UI can key on it across reorders. */
  key: string
  name: string
  label: string
  channel: Channel
  mappings: EditMapping[]
}

export interface EditMapping {
  key: string
  kind: 'mapping' | 'preference'
  output: string
  value: string
  function: string
  params: number[]
  inputs: string[]
  comment: string | null
}

let seq = 0
const nextKey = (prefix: string) => `${prefix}${++seq}`

function toEditMapping(m: MappingIn): EditMapping {
  return {
    key: nextKey('r'),
    kind: m.kind ?? 'mapping',
    output: m.output,
    value: m.value ?? '',
    function: m.function ?? 'normal', // '' is an empty cell: kept, so the file round-trips
    params: [...(m.params ?? [])],
    inputs: [...(m.inputs ?? [])],
    comment: m.comment ?? null,
  }
}

/** A wire body with the fields the editor cannot do without; a `Profile` is one. */
type Body = ProfileCreate & Pick<ProfileMeta, 'console' | 'firmware'>

/**
 * The one normaliser: every row gets a fresh key and the full `EditMapping` shape,
 * whether it arrives from GET (a `Profile`) or from the saved body on revert. A
 * preference row on the wire carries no `inputs`/`params`, and the views iterate
 * those for every row, so nothing may build an `EditDoc` any other way.
 */
export function fromBody(p: Body): EditDoc {
  return {
    name: p.name,
    csv_filename: p.csv_filename,
    game: p.game ?? null,
    console: p.console,
    firmware: p.firmware,
    notes: p.notes ?? null,
    modes: (p.modes ?? []).map((m) => ({
      key: nextKey('m'),
      name: m.name,
      label: m.label ?? '',
      channel: (m.channel ?? 'usb') as Channel,
      mappings: m.mappings.map(toEditMapping),
    })),
    preferences: { ...(p.preferences ?? {}) },
    input_names: { ...(p.input_names ?? {}) },
    game_actions: (p.game_actions ?? []).map((g) => ({
      output: g.output,
      action: g.action,
      mode_name: g.mode_name ?? null,
    })),
  }
}

export function fromProfile(p: Profile): EditDoc {
  return fromBody(p)
}

/** The wire shape for save and for the stateless validate. */
export function toBody(doc: EditDoc): ProfileCreate {
  return {
    name: doc.name,
    csv_filename: doc.csv_filename,
    game: doc.game,
    console: doc.console,
    firmware: doc.firmware,
    notes: doc.notes,
    modes: doc.modes.map(
      (m): ModeIn => ({
        name: m.name,
        label: m.label,
        channel: m.channel,
        mappings: m.mappings.map((r) =>
          r.kind === 'preference'
            ? { kind: 'preference', output: r.output, value: r.value, comment: r.comment }
            : {
                kind: 'mapping',
                output: r.output,
                function: r.function,
                params: r.params,
                inputs: r.inputs,
                comment: r.comment,
              },
        ),
      }),
    ),
    preferences: doc.preferences,
    input_names: doc.input_names,
    game_actions: doc.game_actions,
  }
}

export const useDocumentStore = defineStore('document', () => {
  const id = ref<number | null>(null)
  const doc = ref<EditDoc | null>(null)
  const saved = ref<string>('') // JSON of the last saved body, for the dirty check
  const validation = ref<Validation | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const checking = ref(false)
  const error = ref<string | null>(null)
  const selectedModeKey = ref<string | null>(null)

  const dirty = computed(() => doc.value !== null && JSON.stringify(toBody(doc.value)) !== saved.value)

  const selectedMode = computed(
    () => doc.value?.modes.find((m) => m.key === selectedModeKey.value) ?? doc.value?.modes[0] ?? null,
  )

  /** 1-based mode number: the rail's order *is* the mode number. */
  const selectedModeNumber = computed(() => {
    const i = doc.value?.modes.findIndex((m) => m.key === selectedMode.value?.key) ?? -1
    return i < 0 ? null : i + 1
  })

  const budget = computed<Budget | null>(() => validation.value?.budget ?? null)

  // No findings yet means no check has answered — not that the file is clean. The
  // button must stay off until a check says so, or a failed live check would
  // quietly enable an export the API is about to refuse.
  const canExport = computed(() => validation.value !== null && validation.value.errors === 0)

  /** Findings for one mode number, plus the file-level ones when asked. */
  function findingsFor(modeNumber: number | null): Finding[] {
    return (validation.value?.findings ?? []).filter((f) => f.mode === modeNumber)
  }

  const fileFindings = computed(() => (validation.value?.findings ?? []).filter((f) => f.mode === null))

  /** The worst severity present, for the bottom bar. */
  const worst = computed<Severity | null>(() => {
    const v = validation.value
    if (!v) return null
    if (v.errors) return 'error'
    if (v.warnings) return 'warning'
    if (v.info) return 'info'
    return null
  })

  // Generation counters. Responses can land out of order; only the newest request
  // of each kind may touch the store, or a slow old answer overwrites a new one —
  // for a check that means stale findings deciding whether export is allowed, for
  // a load it means the editor showing profile A while the route says B.
  let loadSeq = 0
  let checkSeq = 0

  async function load(profileId: number) {
    const seq = ++loadSeq
    loading.value = true
    error.value = null
    try {
      const p = await api.getProfile(profileId)
      if (seq !== loadSeq) return
      id.value = p.id
      doc.value = fromProfile(p)
      saved.value = JSON.stringify(toBody(doc.value))
      selectedModeKey.value = doc.value.modes[0]?.key ?? null
      await check()
    } catch (e) {
      if (seq !== loadSeq) return
      error.value = describe(e)
      doc.value = null
    } finally {
      if (seq === loadSeq) loading.value = false
    }
  }

  /** Live checks. Never writes; safe to call on every keystroke. */
  async function check() {
    if (!doc.value) return
    const seq = ++checkSeq
    checking.value = true
    error.value = null // a banner from an earlier failure must not outlive a success
    try {
      const v = await api.validateDocument(toBody(doc.value))
      if (seq !== checkSeq) return
      validation.value = v
    } catch (e) {
      if (seq !== checkSeq) return
      // A shape the API rejects outright (422) is itself a problem worth showing,
      // but it must not wipe the last good findings: only the banner changes.
      error.value = describe(e)
    } finally {
      if (seq === checkSeq) checking.value = false
    }
  }

  // Debounced: one request after editing settles, not one per keystroke.
  let timer: ReturnType<typeof setTimeout> | undefined
  function checkSoon(ms = 350) {
    clearTimeout(timer)
    timer = setTimeout(() => void check(), ms)
  }

  watch(
    () => (doc.value ? JSON.stringify(toBody(doc.value)) : ''),
    (now, before) => {
      if (now && before !== undefined && now !== before) checkSoon()
    },
  )

  async function save() {
    if (!doc.value || id.value === null) return false
    saving.value = true
    error.value = null
    try {
      const body = toBody(doc.value)
      // The reply is re-keyed, so the selected key would go stale and the rail
      // would highlight nothing. Position is the mode number; carry that across.
      const position = doc.value.modes.findIndex((m) => m.key === selectedMode.value?.key)
      const p = await api.replaceProfile(id.value, body)
      doc.value = fromProfile(p)
      saved.value = JSON.stringify(toBody(doc.value))
      selectedModeKey.value = (doc.value.modes[position] ?? doc.value.modes[0])?.key ?? null
      await check()
      return true
    } catch (e) {
      error.value = describe(e)
      return false
    } finally {
      saving.value = false
    }
  }

  function revert() {
    if (!saved.value) return
    // `saved` is the wire body, so it goes through the same normaliser as a GET:
    // fresh keys, and preference rows regain the inputs/params the views iterate.
    doc.value = fromBody(JSON.parse(saved.value) as Body)
    selectedModeKey.value = doc.value.modes[0]?.key ?? null
    void check()
  }

  // ---------------------------------------------------------------- modes
  function selectMode(key: string) {
    selectedModeKey.value = key
  }

  function addMode(name: string, max: number) {
    if (!doc.value || doc.value.modes.length >= max) return null
    const mode: EditMode = { key: nextKey('m'), name, label: name, channel: 'usb', mappings: [] }
    doc.value.modes.push(mode)
    selectedModeKey.value = mode.key
    return mode
  }

  /**
   * A mode's name and its label are one thing on the device (the C1 cell of the
   * Profile Name row), so they are renamed together and never differ. Both stay on
   * the wire because the file format carries both. The mode-scoped game actions
   * are keyed by mode name, so they follow the rename too — otherwise the printed
   * card would lose its labels the moment a mode was renamed.
   */
  function renameMode(key: string, name: string) {
    const m = doc.value?.modes.find((x) => x.key === key)
    if (!m || !doc.value) return
    const oldName = m.name
    m.name = name
    m.label = name
    for (const g of doc.value.game_actions) {
      if (g.mode_name === oldName) g.mode_name = name
    }
  }

  function deleteMode(key: string) {
    if (!doc.value) return
    const i = doc.value.modes.findIndex((m) => m.key === key)
    if (i < 0) return
    doc.value.modes.splice(i, 1)
    if (selectedModeKey.value === key) {
      selectedModeKey.value = doc.value.modes[Math.min(i, doc.value.modes.length - 1)]?.key ?? null
    }
  }

  /**
   * Reorder with buttons, never drag: the mode number *is* the position, and
   * dragging would need one pointer held while moving — which the owner cannot do.
   */
  function moveMode(key: string, delta: -1 | 1) {
    if (!doc.value) return
    const from = doc.value.modes.findIndex((m) => m.key === key)
    const to = from + delta
    if (from < 0 || to < 0 || to >= doc.value.modes.length) return
    const [m] = doc.value.modes.splice(from, 1)
    doc.value.modes.splice(to, 0, m!)
  }

  // ---------------------------------------------------------------- mappings
  function addMapping(modeKey: string, mapping: Partial<EditMapping> = {}) {
    const m = doc.value?.modes.find((x) => x.key === modeKey)
    if (!m) return null
    const row: EditMapping = {
      key: nextKey('r'),
      kind: 'mapping',
      output: '',
      value: '',
      function: 'normal',
      params: [],
      inputs: [],
      comment: null,
      ...mapping,
    }
    m.mappings.push(row)
    return row
  }

  function updateMapping(modeKey: string, rowKey: string, patch: Partial<EditMapping>) {
    const row = doc.value?.modes
      .find((x) => x.key === modeKey)
      ?.mappings.find((r) => r.key === rowKey)
    if (!row) return
    Object.assign(row, patch)
  }

  function deleteMapping(modeKey: string, rowKey: string) {
    const m = doc.value?.modes.find((x) => x.key === modeKey)
    if (!m) return
    const i = m.mappings.findIndex((r) => r.key === rowKey)
    if (i >= 0) m.mappings.splice(i, 1)
  }

  /** Every mapping in the selected mode that fires from this input. */
  function mappingsForInput(input: string): EditMapping[] {
    return (selectedMode.value?.mappings ?? []).filter(
      (r) => r.kind === 'mapping' && r.inputs.length > 0 && r.inputs[r.inputs.length - 1] === input,
    )
  }

  // ---------------------------------------------------------------- labels
  function actionFor(output: string, modeName?: string): string | null {
    if (!doc.value) return null
    const scoped = doc.value.game_actions.find((g) => g.mode_name === modeName && g.output === output)
    if (scoped) return scoped.action
    return doc.value.game_actions.find((g) => !g.mode_name && g.output === output)?.action ?? null
  }

  function setAction(output: string, action: string, modeName?: string | null) {
    if (!doc.value) return
    const name = modeName ?? null
    const existing = doc.value.game_actions.find((g) => g.mode_name === name && g.output === output)
    if (!action.trim()) {
      if (existing) doc.value.game_actions.splice(doc.value.game_actions.indexOf(existing), 1)
      return
    }
    if (existing) existing.action = action
    else doc.value.game_actions.push({ output, action, mode_name: name })
  }

  /**
   * The per-profile display name for an input, e.g. lip -> "Chin switch".
   *
   * A soft variant inherits the rename of its hard one: the profile column carries
   * `lip`, but `lip_soft` is the same physical button, so renaming one and leaving
   * the other reading "Lip button (soft)" would be incoherent. The suffix is kept
   * so the two are still told apart.
   */
  function inputName(input: string, fallback: string) {
    const names = doc.value?.input_names
    if (!names) return fallback
    if (names[input]) return names[input]
    if (input.endsWith('_soft')) {
      const hard = names[input.slice(0, -'_soft'.length)]
      if (hard) return `${hard} (soft)`
    }
    return fallback
  }

  function setInputName(input: string, name: string) {
    if (!doc.value) return
    if (name.trim()) doc.value.input_names[input] = name.trim()
    else delete doc.value.input_names[input]
  }

  function setPreference(key: string, value: string) {
    if (!doc.value) return
    if (value === '') delete doc.value.preferences[key]
    else doc.value.preferences[key] = value
  }

  return {
    id, doc, validation, loading, saving, checking, error, selectedModeKey,
    dirty, selectedMode, selectedModeNumber, budget, canExport, fileFindings, worst,
    load, check, checkSoon, save, revert, findingsFor,
    selectMode, addMode, renameMode, deleteMode, moveMode,
    addMapping, updateMapping, deleteMapping, mappingsForInput,
    actionFor, setAction, inputName, setInputName, setPreference,
  }
})
