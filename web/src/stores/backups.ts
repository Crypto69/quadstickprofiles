// The backups of the QuadStick's flash drive, newest first. Shared because two parts
// of the device page read them: the backup box takes and restores them, and the
// "On the QuadStick" list shows what the newest one says is on the drive.
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import type { Backup } from '@/api/types'

export const useBackupsStore = defineStore('backups', () => {
  const backups = ref<Backup[]>([])
  const loaded = ref(false)
  const error = ref('')

  const latest = computed(() => backups.value[0] ?? null)

  async function load() {
    try {
      backups.value = await api.listBackups()
      error.value = ''
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loaded.value = true
    }
  }

  /** A backup just taken goes first: it is the newest. */
  function added(b: Backup) {
    backups.value = [b, ...backups.value.filter((x) => x.id !== b.id)]
  }

  function removed(id: number) {
    backups.value = backups.value.filter((x) => x.id !== id)
  }

  return { backups, loaded, error, latest, load, added, removed }
})
