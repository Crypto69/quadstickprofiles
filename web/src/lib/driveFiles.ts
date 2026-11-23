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

/**
 * The profiles on the drive in the order the QuadStick counts them when you pick a
 * file with the joystick: `default.csv` is always file 1, then every other top-level
 * `.csv` in alphanumeric order (docs/research-report.md §2). `prefs.csv` holds the
 * device's settings, not a profile, so it has no number. The device lowercases names,
 * so they are shown and sorted that way. Folders and dot-files are not read.
 */
export function profilesOnDrive(paths: Iterable<string>): string[] {
  const names = new Set<string>()
  for (const path of paths) {
    const name = path.toLowerCase()
    if (name.includes('/') || name.startsWith('.') || !name.endsWith('.csv')) continue
    if (name === 'prefs.csv') continue
    names.add(name)
  }
  const rest = [...names].filter((n) => n !== 'default.csv').sort((a, b) => (a < b ? -1 : a > b ? 1 : 0))
  return names.has('default.csv') ? ['default.csv', ...rest] : rest
}
