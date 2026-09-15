// Typed client for the FastAPI service. Every path is relative, so the same build
// works behind the nginx proxy and against the Vite dev proxy.
import type {
  Catalog, ConvertResult, ImportResult, Prefs, Profile, ProfileCreate, ProfilePatch,
  ProfileSummary, Validation,
} from './types'

export const API_BASE = '/api'

/**
 * Sent on every request so the API can tell the app apart from a cross-site form
 * post (api/app/csrf.py). A custom header cannot be set by a `<form>`, an `<img>`
 * or a `<script>` tag, which is the whole class of "simple" requests that reach
 * the API without a CORS preflight. Not a secret and not a token — there is no
 * login (single-user), so this plus the server's Origin check *is* the CSRF
 * defence. Change it here and in api/app/csrf.py together.
 */
export const REQUESTED_WITH_HEADER = 'X-Requested-With'
export const REQUESTED_WITH = 'QuadStickProfileStudio'

/** An API error that carries the validation findings, so the UI can say *why*. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly validation?: Validation,
  ) {
    super(message)
    this.name = 'ApiError'
  }

  /** Export and convert are refused with 409 while validation errors exist. */
  get isValidationBlock() {
    return this.status === 409
  }
}

type Query = Record<string, string | number | boolean | undefined | null>

function qs(params?: Query) {
  if (!params) return ''
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

/** FastAPI's error shapes: a string detail, a 422 validation list, or our 409 object. */
function messageFrom(status: number, body: unknown): { message: string; validation?: Validation } {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return { message: detail }
  if (Array.isArray(detail)) {
    // 422 from Pydantic: [{loc: [...], msg: "..."}]
    const parts = detail.map((d: { loc?: unknown[]; msg?: string }) => {
      const where = (d.loc ?? []).filter((x) => x !== 'body').join('.')
      return where ? `${where}: ${d.msg}` : String(d.msg)
    })
    return { message: parts.join('; ') || `Request rejected (${status})` }
  }
  if (detail && typeof detail === 'object') {
    const d = detail as { message?: string; validation?: Validation }
    return { message: d.message ?? `Request failed (${status})`, validation: d.validation }
  }
  return { message: `Request failed (${status})` }
}

async function raise(res: Response): Promise<never> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    /* a non-JSON error body (nginx, a proxy) leaves body null */
  }
  const { message, validation } = messageFrom(res.status, body)
  throw new ApiError(res.status, message, validation)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Headers, not a spread: an init may already carry Content-Type (json()) and a
  // FormData body must keep its browser-generated multipart boundary, so never
  // set Content-Type here.
  const headers = new Headers(init?.headers)
  headers.set(REQUESTED_WITH_HEADER, REQUESTED_WITH)
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) await raise(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

/** A file download: returns the bytes plus the filename the server chose. */
export interface Download {
  blob: Blob
  filename: string
  /**
   * Where the api container also wrote it (the exports/ share), already decoded.
   * The server percent-encodes it (api/app/headers.py) because header values are
   * Latin-1 and a home directory can be called Łukasz; an ASCII path is unchanged.
   */
  exportPath: string | null
}

/** Undo the server's percent-encoding of `X-Export-Path`. A malformed value is
 *  shown as-is rather than throwing: the export itself already succeeded. */
function exportPathFrom(res: Response): string | null {
  const raw = res.headers.get('X-Export-Path')
  if (raw === null) return null
  try {
    return decodeURIComponent(raw)
  } catch {
    return raw
  }
}

function filenameFrom(res: Response, fallback: string) {
  const cd = res.headers.get('Content-Disposition') ?? ''
  return /filename="?([^";]+)"?/.exec(cd)?.[1] ?? fallback
}

async function download(path: string, fallback: string): Promise<Download> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) await raise(res)
  return {
    blob: await res.blob(),
    filename: filenameFrom(res, fallback),
    exportPath: exportPathFrom(res),
  }
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  catalog: () => request<Catalog>('/catalog'),

  listProfiles: (opts?: { q?: string; validate?: boolean; templates?: boolean }) =>
    request<ProfileSummary[]>(
      `/profiles${qs({ q: opts?.q, validate: opts?.validate, templates: opts?.templates })}`,
    ),

  /** Start a profile from a starter one; the copy is never itself a starter. */
  createFromTemplate: (
    templateId: number,
    body: { name: string; csv_filename: string; game?: string },
  ) => request<Profile>(`/profiles/from-template/${templateId}`, json('POST', body)),

  getProfile: (id: number) => request<Profile>(`/profiles/${id}`),

  createProfile: (body: ProfileCreate) => request<Profile>('/profiles', json('POST', body)),

  replaceProfile: (id: number, body: ProfileCreate) =>
    request<Profile>(`/profiles/${id}`, json('PUT', body)),

  patchProfile: (id: number, body: ProfilePatch) =>
    request<Profile>(`/profiles/${id}`, json('PATCH', body)),

  deleteProfile: (id: number) => request<void>(`/profiles/${id}`, { method: 'DELETE' }),

  duplicateProfile: (id: number, opts?: { name?: string; csv_filename?: string }) =>
    request<Profile>(`/profiles/${id}/duplicate${qs(opts)}`, { method: 'POST' }),

  convertProfile: (id: number, body: { target: string; name?: string; csv_filename?: string }) =>
    request<ConvertResult>(`/profiles/${id}/convert`, json('POST', body)),

  importProfile: (file: File, opts?: { game?: string; name?: string; firmware?: number }) => {
    const form = new FormData()
    form.append('file', file)
    if (opts?.game) form.append('game', opts.game)
    if (opts?.name) form.append('name', opts.name)
    if (opts?.firmware) form.append('firmware', String(opts.firmware))
    return request<ImportResult>('/profiles/import', { method: 'POST', body: form })
  },

  validateProfile: (id: number) => request<Validation>(`/profiles/${id}/validate`),

  /** Live checks for an unsaved document; writes nothing. */
  validateDocument: (body: ProfileCreate) =>
    request<Validation>('/profiles/validate', json('POST', body)),

  exportCsv: (id: number, filename?: string) =>
    download(`/profiles/${id}/export.csv${qs({ filename })}`, filename ?? 'profile.csv'),

  exportXlsx: (id: number, filename?: string) =>
    download(`/profiles/${id}/export.xlsx${qs({ filename })}`, filename ?? 'profile.xlsx'),

  cardUrl: (id: number) => `${API_BASE}/profiles/${id}/card.html`,

  /** The compact three-column cheat sheet: game action | QuadStick | console button. */
  summaryUrl: (id: number) => `${API_BASE}/profiles/${id}/summary.html`,

  // ---------------------------------------------------------------- global prefs
  /**
   * The device's own settings (prefs.csv), underneath every profile. Which
   * emulation modes hide the flash drive depends on the firmware, so every call
   * carries the firmware the page is showing; the API falls back to its default
   * when none is given.
   */
  getPrefs: (firmware?: number | null) => request<Prefs>(`/prefs${qs({ firmware })}`),

  putPrefs: (preferences: Record<string, string>, firmware?: number | null) =>
    request<Prefs>(`/prefs${qs({ firmware })}`, json('PUT', { preferences })),

  importPrefs: (file: File, firmware?: number | null) => {
    const form = new FormData()
    form.append('file', file)
    return request<Prefs>(`/prefs/import${qs({ firmware })}`, { method: 'POST', body: form })
  },

  exportPrefs: (firmware?: number | null) =>
    download(`/prefs/export.csv${qs({ firmware })}`, 'prefs.csv'),
}

export type Api = typeof api
