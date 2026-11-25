// The QuadStick's drive as the desktop app sees it, live. Only the desktop app can
// look at what is plugged in (desktop/desktop_api.py); in a browser `live` is false
// and the device page uses the newest backup instead.
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { DriveState } from '@/desktop'
import { desktopApi } from '@/desktop'
import type { DriveFile } from '@/lib/driveFiles'
import { filesFromDesktop } from '@/lib/driveFiles'

/** pywebview rejects with a plain {message} object rather than an Error. */
export function shellMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  const m = (e as { message?: unknown } | null)?.message
  return typeof m === 'string' ? m : String(e)
}

export const useDriveStore = defineStore('drive', () => {
  const state = ref<DriveState | null>(null)
  const error = ref('')

  /** This copy can look at the drive itself. */
  const live = computed(() => Boolean(desktopApi()?.quadstick_drive))
  const found = computed(() => state.value?.found === true)
  /** Plugged in, but the sandboxed Mac app may not open it until it is picked once. */
  const needsPermission = computed(() => state.value?.needs_permission === true)

  let asking = false

  /** Look again. The device page does this every few seconds, so one at a time. */
  async function refresh() {
    const shell = desktopApi()
    if (!shell?.quadstick_drive || asking) return
    asking = true
    try {
      state.value = await shell.quadstick_drive()
      error.value = ''
    } catch (e) {
      error.value = shellMessage(e)
    } finally {
      asking = false
    }
  }

  /** Ask which drive is the QuadStick. False when cancelled. Throws what the shell refused. */
  async function choose(): Promise<boolean> {
    const picked = await desktopApi()?.choose_quadstick_drive?.()
    if (!picked) return false
    state.value = picked
    error.value = ''
    return true
  }

  /** Every file on the drive, for a backup; null when it is not plugged in. */
  async function read(): Promise<DriveFile[] | null> {
    const entries = await desktopApi()?.read_quadstick_drive?.()
    return entries ? filesFromDesktop(entries) : null
  }

  /** This copy can write to the drive. */
  const writable = computed(() => Boolean(desktopApi()?.write_quadstick_drive))

  /** Put these profiles on the drive in place of the ones there. Throws what the shell refused. */
  async function write(files: { name: string; data: string }[]) {
    const shell = desktopApi()
    if (!shell?.write_quadstick_drive) throw new Error('Only the desktop app can write to the drive.')
    state.value = await shell.write_quadstick_drive(files)
    error.value = ''
  }

  return { state, error, live, found, needsPermission, writable, refresh, choose, read, write }
})
