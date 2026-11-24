// Turning "the files the user picked" into "the files on the QuadStick's drive",
// for a backup. Two sources: a browser folder picker (<input webkitdirectory>) and
// the desktop shell's own folder dialog. The API re-checks every path; leaving the
// junk out here is what keeps a Mac's Spotlight index from being uploaded at all.

export interface DriveFile {
  /** Relative to the drive's top level, '/'-separated. */
  path: string
  data: Blob
}

// What a computer leaves on a removable drive. The firmware deletes dot-files at
// boot anyway. Same list as api/app/routers/backups.py.
const SYSTEM_FOLDERS = new Set(['system volume information', '$recycle.bin'])

/** A path a computer wrote, not the owner: any part is a dot-file or a system folder. */
export function isSystemPath(path: string): boolean {
  return path
    .split('/')
    .some((part) => part.startsWith('.') || SYSTEM_FOLDERS.has(part.toLowerCase()))
}

/**
 * The files from a folder picker. Each `webkitRelativePath` starts with the picked
 * folder's own name ("QUADSTICK/default.csv"), which is not part of the drive.
 */
export function filesFromFolderPicker(files: Iterable<File>): DriveFile[] {
  const out: DriveFile[] = []
  for (const file of files) {
    const rel = file.webkitRelativePath || file.name
    const path = rel.includes('/') ? rel.slice(rel.indexOf('/') + 1) : rel
    if (path && !isSystemPath(path)) out.push({ path, data: file })
  }
  return out
}

/** The desktop shell's answer (base64 per file, junk already left out) as blobs. */
export function filesFromDesktop(entries: { path: string; data: string }[]): DriveFile[] {
  return entries.map(({ path, data }) => {
    const bin = atob(data)
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    return { path, data: new Blob([bytes]) }
  })
}

const pad = (n: number) => String(n).padStart(2, '0')

/** `quadstick-backup-2026-11-22-2130.zip`, in local time: the time the list shows. */
export function backupZipName(when: Date): string {
  const day = `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`
  return `quadstick-backup-${day}-${pad(when.getHours())}${pad(when.getMinutes())}.zip`
}

/** "22 Nov 2026, 9:30 pm" — a backup is told apart from the others by when it was taken. */
export function backupWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** 1536 -> "1.5 KB". The drive holds KB-sized files, so no more precision than that. */
export function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Top-level `.csv` names, lowercased as the device lowercases them. */
function topLevelCsv(paths: Iterable<string>): Set<string> {
  const names = new Set<string>()
  for (const path of paths) {
    const name = path.toLowerCase()
    if (name.includes('/') || name.startsWith('.') || !name.endsWith('.csv')) continue
    names.add(name)
  }
  return names
}

/** The firmware leaves any name with `prefs.csv` in it off the profile switch. */
const isPrefsName = (name: string) => name.includes('prefs.csv')

/**
 * The profiles on the drive in the order the QuadStick counts them when you pick a
 * file with the joystick. This is the firmware's own list (`scan_files`, firmware
 * 2373, as read by QuadStick Config Manager): each name lowercased, any name holding
 * `prefs.csv` skipped, `default.csv` first, the rest in plain byte order — so
 * `game10.csv` comes before `game2.csv`, and `_x.csv` before `a.csv`. Folders and
 * dot-files are not read. The switch only reaches the first 32
 * (`MAX_SELECTABLE_FILES` in device/layout.ts); the caller says so for the rest.
 */
export function profilesOnDrive(paths: Iterable<string>): string[] {
  const names = [...topLevelCsv(paths)].filter((n) => !isPrefsName(n))
  const rest = names.filter((n) => n !== 'default.csv').sort((a, b) => (a < b ? -1 : a > b ? 1 : 0))
  return names.includes('default.csv') ? ['default.csv', ...rest] : rest
}

/**
 * Files that look like profiles but that the QuadStick will never offer: a name with
 * `prefs.csv` in it, such as `myprefs.csv`. `prefs.csv` itself is the device's
 * settings and is not one of them.
 */
export function skippedByTheSwitch(paths: Iterable<string>): string[] {
  return [...topLevelCsv(paths)].filter((n) => isPrefsName(n) && n !== 'prefs.csv').sort()
}

// ------------------------------------------------------------- replacing the profiles
// The desktop app can put profiles on the drive in place of the ones there now
// (`replace_profiles` in desktop/desktop_api.py). The shell checks everything again;
// this is the same rule, so the page can show the result before anything is written.

/** The profile switch reaches this many files (MAX_SELECTABLE_FILES in device/layout.ts). */
const MAX_PROFILE_FILES = 32

export interface ReplacePlan {
  /** What the drive's profile list will be, in the QuadStick's order. */
  after: string[]
  /** Profiles on the drive now that go (lowercased). They are in the backup. */
  removed: string[]
  /** No new profile is default.csv, so the drive's own one stays. */
  keptDefault: boolean
  /** Why it cannot be written as it stands. Empty when it can. */
  problems: string[]
}

/**
 * What a replace does to the drive. `onDrive` is every path on it now; `chosen` the
 * filenames of the profiles to put on it. Only the profile files swap: prefs.csv,
 * joystick.bin, folders and a name with `prefs.csv` in it stay as they are. When no
 * chosen profile is `default.csv`, the drive's own one stays: it is the profile the
 * QuadStick boots with.
 */
export function planReplace(onDrive: Iterable<string>, chosen: string[]): ReplacePlan {
  const now = profilesOnDrive(onDrive)
  const names = chosen.map((n) => n.toLowerCase())
  const keptDefault = !names.includes('default.csv') && now.includes('default.csv')
  const problems: string[] = []
  if (names.length === 0) problems.push('Tick at least one profile.')
  const twice = [...new Set(names.filter((n, i) => names.indexOf(n) !== i))]
  for (const n of twice) problems.push(`Two ticked profiles are called ${n}. Untick one of them.`)
  for (const n of names.filter(isPrefsName)) {
    problems.push(`${n} has prefs.csv in its name, so the QuadStick would never offer it.`)
  }
  const after = profilesOnDrive(keptDefault ? ['default.csv', ...names] : names)
  if (after.length > MAX_PROFILE_FILES) {
    problems.push(
      `That is ${after.length} profiles${keptDefault ? ' with default.csv' : ''}; the ` +
        `QuadStick can pick only ${MAX_PROFILE_FILES}. Untick some.`,
    )
  }
  const removed = now.filter((n) => !after.includes(n))
  return { after, removed, keptDefault, problems }
}

/** A blob as base64, for the desktop shell: pywebview passes only JSON. */
export async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  let bin = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(bin)
}
