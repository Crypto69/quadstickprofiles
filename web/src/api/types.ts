// Mirrors api/app/schemas.py. Outputs are always PlayStation names on the wire;
// `console` decides what the user sees and what an export writes.
export type Console = 'playstation' | 'xbox'
export type Severity = 'error' | 'warning' | 'info'
/** A mode's C3 cell: how that mode reaches the console. Per mode, never per profile. */
export type Channel = 'none' | 'usb' | 'bluetooth' | 'both'
export type MappingKind = 'mapping' | 'preference'

export interface InputEntry {
  name: string
  kind: string | null // mouthpiece | side | lip | joystick | digital | usb | legacy
  tube: string | null
  action: string | null // sip | puff, or a joystick direction
  strength: string | null // hard | soft, or a joystick ring
  label: string | null
  jack: string | null // digital_in_* -> the physical jack it lives on
}

export interface OutputEntry {
  name: string // canonical (PlayStation)
  grp: string | null
  ps_glyph: string | null
  xbox_name: string | null
  xbox_glyph: string | null
  label: string | null
}

export interface FunctionEntry {
  name: string
  max_params: number | null
  description: string | null
}

export type PreferenceEditor = 'integer' | 'toggle' | 'choice' | 'text'

export interface PreferenceEntry {
  label: string
  category: string
  editor: PreferenceEditor
  default?: string
  minimum?: number
  maximum?: number
  unit?: string
  description?: string
  /** For `choice`: the values the firmware accepts. */
  options?: string[]
  /** Human names for those values, where we have them from the manual. */
  optionLabels?: Record<string, string>
  /** Whether a per-mode override row may set it. */
  modeOverride?: boolean
  /** Hidden behind "show the fiddly ones" by default. */
  advanced?: boolean
}

export interface Limits {
  max_modes: number
  max_rows_per_mode: number
  max_keyword_chars: number
  max_line_bytes: number
  /** The largest function parameter the firmware stores (a 14-bit field). */
  max_function_param: number
}

export interface Catalog {
  inputs: InputEntry[]
  outputs: OutputEntry[]
  functions: FunctionEntry[]
  tubes: Record<string, string>
  tube_order: string[]
  joystick_directions: string[]
  joystick_zones: string[]
  digital_jacks: Record<string, string>
  xbox_to_ps: Record<string, string>
  no_xbox_equivalent: string[]
  mode_change_outputs: string[]
  output_families: Record<string, string>
  preferences: Record<string, PreferenceEntry>
  preference_categories: string[]
  mode_overridable: string[]
  emulation_modes: Record<string, string>
  hidden_drive_modes: Record<string, number[]>
  firmware_versions: number[]
  default_firmware: number
  legacy_inputs: Record<string, string>
  limits: Limits
}

export interface Finding {
  severity: Severity
  mode: number | null
  row: number | null
  message: string
  /** A stable identifier for the rule, so a view never has to match on prose. */
  code?: string
}

export interface ModeBudget {
  number: number
  name: string
  rows_used: number
  rows_free: number
  rows_active: number
  unused_inputs: string[]
}

export interface Budget {
  modes_used: number
  modes_max: number
  rows_max: number
  modes: ModeBudget[]
  preference_rows: number
  preference_rows_max: number
  firmware: number
}

export interface Validation {
  errors: number
  warnings: number
  info: number
  findings: Finding[]
  /** What the device actually does, per severity present. */
  consequence: Partial<Record<Severity, string>>
  budget: Budget | null
  /** Inputs free in every mode. */
  unused_inputs: string[]
}

export interface MappingIn {
  kind?: MappingKind
  output: string // an output name, or a preference key when kind === 'preference'
  value?: string
  function?: string
  params?: number[]
  inputs?: string[]
  comment?: string | null
}

export interface Mapping extends MappingIn {
  id: number
  row_order: number
  row: number // spreadsheet row, for matching findings
  is_sequence: boolean
}

export interface ModeIn {
  name: string
  label?: string
  channel?: Channel
  mappings: MappingIn[]
}

export interface Mode extends ModeIn {
  id: number
  position: number // = mode number
  mappings: Mapping[]
}

export interface GameActionIn {
  output: string
  action: string
  mode_name?: string | null
}

export interface GameAction extends GameActionIn {
  id: number
}

export interface ProfileMeta {
  name: string
  csv_filename: string
  game?: string | null
  console: Console
  firmware: number
  notes?: string | null
  source_url?: string | null
  /** A starter profile to copy from, rather than one of the user's own. */
  is_template?: boolean
  template_note?: string | null
}

export interface ProfileSummary {
  id: number
  name: string
  csv_filename: string
  game: string | null
  console: Console
  /** Derived by the API from the `enable_DS3_emulation` preference row; never stored. */
  emulation_mode: number | null
  firmware: number
  is_template: boolean
  template_note: string | null
  mode_count: number
  updated_at: string | null
  validation: Validation | null
}

export interface Profile extends ProfileMeta {
  id: number
  format_version: string
  created_at: string | null
  updated_at: string | null
  modes: Mode[]
  preferences: Record<string, string>
  game_actions: GameAction[]
  input_names: Record<string, string>
}

export interface ProfileCreate extends Partial<ProfileMeta> {
  name: string
  csv_filename: string
  modes?: ModeIn[]
  preferences?: Record<string, string>
  game_actions?: GameActionIn[]
  input_names?: Record<string, string>
}

export interface ImportResult {
  profile: Profile
  findings: Validation
}

export interface ConvertResult {
  profile: Profile
  notes: Finding[]
  suggested_csv_filename: string
}

export interface Prefs {
  preferences: Record<string, string>
  validation: Validation
}
