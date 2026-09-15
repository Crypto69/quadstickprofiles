// Test doubles shaped like the real API responses (api/app/schemas.py).
import type { Budget, Catalog, Profile, ProfileSummary, Validation } from '@/api/types'

export function validation(over: Partial<Validation> = {}): Validation {
  return {
    errors: 0,
    warnings: 0,
    info: 0,
    findings: [],
    consequence: {},
    budget: null,
    unused_inputs: [],
    ...over,
  }
}

export function budget(over: Partial<Budget> = {}): Budget {
  return {
    modes_used: 1,
    modes_max: 16,
    rows_max: 128,
    modes: [
      { number: 1, name: 'Left joy', rows_used: 10, rows_free: 118, rows_active: 6, unused_inputs: ['lip_soft'] },
    ],
    preference_rows: 2,
    preference_rows_max: 61,
    firmware: 2373,
    ...over,
  }
}

export function summary(over: Partial<ProfileSummary> = {}): ProfileSummary {
  return {
    id: 1,
    name: 'ddfortnite',
    csv_filename: 'ddfortnite.csv',
    game: 'Fortnite',
    console: 'playstation',
    emulation_mode: 4,
    firmware: 2373,
    is_template: false,
    template_note: null,
    mode_count: 7,
    updated_at: '2026-09-12T10:00:00+00:00',
    validation: validation(),
    ...over,
  }
}

export function profile(over: Partial<Profile> = {}): Profile {
  return {
    id: 1,
    name: 'ddfortnite',
    csv_filename: 'ddfortnite.csv',
    game: 'Fortnite',
    console: 'playstation',
    firmware: 2373,
    is_template: false,
    template_note: null,
    notes: null,
    source_url: null,
    format_version: 'Version 1.4',
    created_at: '2026-09-12T10:00:00+00:00',
    updated_at: '2026-09-12T10:00:00+00:00',
    modes: [],
    preferences: {},
    game_actions: [],
    input_names: {},
    ...over,
  }
}

export function catalog(over: Partial<Catalog> = {}): Catalog {
  return {
    inputs: [
      { name: 'mp_center_sip', kind: 'mouthpiece', tube: 'center', action: 'sip', strength: 'hard', label: 'Centre sip', jack: null },
      { name: 'mp_center_puff', kind: 'mouthpiece', tube: 'center', action: 'puff', strength: 'hard', label: 'Centre puff', jack: null },
      { name: 'lip', kind: 'lip', tube: null, action: null, strength: null, label: 'Lip button', jack: null },
      { name: 'digital_in_1', kind: 'digital', tube: null, action: null, strength: null, label: 'Switch 1', jack: "bottom 'In' jack" },
      { name: 'digital_in_2', kind: 'digital', tube: null, action: null, strength: null, label: 'Switch 2', jack: "bottom 'In' jack" },
      { name: 'digital_in_3', kind: 'digital', tube: null, action: null, strength: null, label: 'Switch 3', jack: 'USB-A jack' },
      { name: 'digital_in_4', kind: 'digital', tube: null, action: null, strength: null, label: 'Switch 4', jack: 'USB-A jack' },
      { name: 'digital_in_5', kind: 'digital', tube: null, action: null, strength: null, label: 'Switch 5', jack: 'Lip button jack' },
      { name: 'digital_in_6', kind: 'digital', tube: null, action: null, strength: null, label: 'Switch 6', jack: 'Lip button jack' },
      { name: 'digital_in_7', kind: 'digital', tube: null, action: null, strength: null, label: 'Switch 7', jack: "top 'In 7-8' jack" },
      { name: 'digital_in_8', kind: 'digital', tube: null, action: null, strength: null, label: 'Switch 8', jack: "top 'In 7-8' jack" },
      { name: 'push', kind: 'legacy', tube: null, action: null, strength: null, label: 'Push on the joystick (older name)', jack: null },
      { name: 'mp_left_sip', kind: 'mouthpiece', tube: 'left', action: 'sip', strength: 'hard', label: 'Left sip', jack: null },
      { name: 'mp_right_sip', kind: 'mouthpiece', tube: 'right', action: 'sip', strength: 'hard', label: 'Right sip', jack: null },
      { name: 'mp_left_puff', kind: 'mouthpiece', tube: 'left', action: 'puff', strength: 'hard', label: 'Left puff', jack: null },
      { name: 'right_sip', kind: 'side', tube: null, action: 'sip', strength: 'hard', label: 'Side tube sip', jack: null },
      { name: 'right_puff', kind: 'side', tube: null, action: 'puff', strength: 'hard', label: 'Side tube puff', jack: null },
      { name: 'lip_soft', kind: 'lip', tube: null, action: null, strength: 'soft', label: 'Lip button (soft)', jack: null },
      { name: 'mp_left_center_sip', kind: 'mouthpiece', tube: 'left_center', action: 'sip', strength: 'hard', label: 'Left + Centre sip', jack: null },
    ],
    outputs: [
      { name: 'x', grp: 'button', ps_glyph: '✕', xbox_name: 'A', xbox_glyph: 'A', label: 'Cross' },
      { name: 'circle', grp: 'button', ps_glyph: '○', xbox_name: 'B', xbox_glyph: 'B', label: 'Circle' },
      { name: 'square', grp: 'button', ps_glyph: '□', xbox_name: 'X', xbox_glyph: 'X', label: 'Square' },
      { name: 'left_joy_up', grp: 'stick', ps_glyph: null, xbox_name: null, xbox_glyph: null, label: 'Left stick up' },
      { name: 'increment_mode', grp: 'system', ps_glyph: null, xbox_name: null, xbox_glyph: null, label: 'Next mode' },
      { name: 'decrement_mode', grp: 'system', ps_glyph: null, xbox_name: null, xbox_glyph: null, label: 'Previous mode' },
    ],
    functions: [
      { name: 'normal', max_params: 0, description: 'on while the input is active' },
      { name: 'toggle', max_params: 0, description: 'one action turns it on, the next turns it off' },
      { name: 'repeat', max_params: 2, description: 'auto-fires while held' },
      { name: 'force_off', max_params: 1, description: 'forces the output off' },
    ],
    tubes: { center: 'Centre' },
    tube_order: ['left', 'center', 'right'],
    joystick_directions: ['up', 'down', 'left', 'right'],
    joystick_zones: ['N', 'E', 'S', 'W'],
    digital_jacks: { '7': "top 'In' jack" },
    xbox_to_ps: { A: 'x' },
    no_xbox_equivalent: ['touch'],
    mode_change_outputs: ['increment_mode', 'decrement_mode', 'load_file'],
    output_families: { keyboard: '^kb_[a-z0-9_]+$', ir: '^ir_[a-z0-9_]+$' },
    preferences: {
      mouse_speed: {
        label: 'Mouse speed', category: 'Mouse', editor: 'integer', default: '100',
        minimum: 10, maximum: 200, unit: 'percent', modeOverride: true,
        description: 'How fast the pointer moves for the same push on the stick.',
      },
      mouse_response_curve: {
        label: 'Mouse response curve', category: 'Mouse', editor: 'choice', default: '1',
        options: ['0', '1', '2'],
        optionLabels: { '0': 'Linear', '1': 'Parabolic', '2': 'Steeper parabolic' },
        modeOverride: true,
      },
      volume: {
        label: 'Speaker volume', category: 'Sound and lights', editor: 'integer',
        default: '40', minimum: 0, maximum: 100, modeOverride: true,
      },
      joystick_dead_zone_shape: {
        label: 'Circular dead zone', category: 'Joystick', editor: 'toggle', default: '1',
        modeOverride: true, advanced: true,
      },
      bluetooth_remote_address: {
        label: 'Bluetooth remote address', category: 'Bluetooth', editor: 'text',
        default: '', modeOverride: true, advanced: true,
      },
    },
    preference_categories: ['Mouse', 'Sound and lights', 'Joystick', 'Bluetooth'],
    mode_overridable: ['mouse_speed', 'volume'],
    emulation_modes: { '4': 'DualShock 4 (PS4 / PS5 via adapter)', '6': 'DualShock 4, no USB drive' },
    hidden_drive_modes: { '2373': [5, 6, 7], '1476': [3, 5, 7] },
    firmware_versions: [2373, 1476],
    default_firmware: 2373,
    legacy_inputs: { push: 'Push on the joystick (older name)' },
    limits: {
      max_modes: 16, max_rows_per_mode: 128, max_keyword_chars: 63, max_line_bytes: 1023,
      max_function_param: 16383,
    },
    ...over,
  }
}

/** A canned non-200 response. Cloned per call, because a body can only be read once. */
export interface StubResponse {
  status: number
  body: string
  headers?: Record<string, string>
}

export function isStubResponse(v: unknown): v is StubResponse {
  return typeof v === 'object' && v !== null && 'status' in v && 'body' in v
}

/**
 * A fetch stub that routes by path, so a test only declares what it needs.
 * Every call builds a new Response: a Response body is single-use, and reusing one
 * makes a second call to the same route look like an empty body.
 */
export function stubFetch(routes: Record<string, unknown | (() => unknown)>) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = init?.method ?? 'GET'
    const key = `${method} ${url}`
    const match = key in routes ? routes[key] : routes[url]
    if (match === undefined) throw new Error(`No stub for ${key}`)
    const value = typeof match === 'function' ? (match as () => unknown)() : match
    if (isStubResponse(value)) {
      // 204 and 205 must not carry a body; the Response constructor rejects one.
      const body = value.status === 204 || value.status === 205 ? null : value.body
      return new Response(body, { status: value.status, headers: value.headers })
    }
    return new Response(JSON.stringify(value), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}

/** A refused export / convert: 409 with the findings that caused it. */
export function conflict(message: string, v: Validation): StubResponse {
  return {
    status: 409,
    body: JSON.stringify({ detail: { message, validation: v } }),
    headers: { 'Content-Type': 'application/json' },
  }
}

/** A 422 from Pydantic: a list of field errors. */
export function unprocessable(detail: { loc: unknown[]; msg: string }[]): StubResponse {
  return {
    status: 422,
    body: JSON.stringify({ detail }),
    headers: { 'Content-Type': 'application/json' },
  }
}

/** A file download, with the headers the API really sets. */
export function fileResponse(
  body: string,
  opts: { filename: string; contentType: string; exportPath?: string },
): StubResponse {
  return {
    status: 200,
    body,
    headers: {
      'Content-Type': opts.contentType,
      'Content-Disposition': `attachment; filename="${opts.filename}"`,
      ...(opts.exportPath ? { 'X-Export-Path': opts.exportPath } : {}),
    },
  }
}

/** A 204 No Content, as DELETE returns. */
export function noContent(): StubResponse {
  return { status: 204, body: '' }
}

/** A 404 with the API's `detail` string. */
export function notFound(message = 'Profile not found'): StubResponse {
  return {
    status: 404,
    body: JSON.stringify({ detail: message }),
    headers: { 'Content-Type': 'application/json' },
  }
}

/**
 * A fetch whose answers the test releases itself, in any order — for the race
 * tests, where what matters is which response lands last, not which was sent last.
 */
export function deferredFetch() {
  const calls: { key: string; release: (body: unknown, status?: number) => void }[] = []
  const fetch = vi.fn(
    (input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((resolve) => {
        const url = typeof input === 'string' ? input : input.toString()
        calls.push({
          key: `${init?.method ?? 'GET'} ${url}`,
          release: (body, status = 200) =>
            resolve(
              new Response(status === 204 ? null : JSON.stringify(body), {
                status,
                headers: { 'Content-Type': 'application/json' },
              }),
            ),
        })
      }),
  )
  return { fetch, calls }
}

/** A profile with modes, for the editor tests. */
export function editableProfile(over: Partial<Profile> = {}): Profile {
  return profile({
    modes: [
      {
        id: 1, position: 1, name: 'Left', label: 'Left joy', channel: 'usb',
        mappings: [
          {
            id: 1, row_order: 0, row: 4, kind: 'mapping', output: 'x', value: '',
            function: 'normal', params: [], inputs: ['mp_center_sip'], comment: null,
            is_sequence: false,
          },
          {
            id: 2, row_order: 1, row: 5, kind: 'mapping', output: 'increment_mode', value: '',
            function: 'normal', params: [], inputs: ['right_sip'], comment: null,
            is_sequence: false,
          },
          {
            id: 3, row_order: 2, row: 6, kind: 'mapping', output: 'circle', value: '',
            function: 'normal', params: [], inputs: ['mp_left_sip', 'mp_right_sip'],
            comment: null, is_sequence: true,
          },
        ],
      },
      {
        id: 2, position: 2, name: 'Right', label: 'Right joy', channel: 'usb',
        mappings: [
          {
            id: 4, row_order: 0, row: 4, kind: 'preference', output: 'mouse_speed', value: '150',
            function: 'normal', params: [], inputs: [], comment: null, is_sequence: false,
          },
          {
            id: 5, row_order: 1, row: 5, kind: 'mapping', output: 'decrement_mode', value: '',
            function: 'normal', params: [], inputs: ['right_puff'], comment: null,
            is_sequence: false,
          },
        ],
      },
    ],
    game_actions: [{ id: 1, output: 'x', action: 'Jump', mode_name: null }],
    input_names: { lip: 'Chin switch' },
    preferences: { mouse_speed: '100' },
    ...over,
  })
}

/** The device's own settings, as GET /api/prefs returns them. */
export function prefs(
  preferences: Record<string, string> = { volume: '40' },
  over: Partial<Validation> = {},
) {
  return { preferences, validation: validation(over) }
}
