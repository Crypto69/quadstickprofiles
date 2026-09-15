// The device's own settings — prefs.csv. One set, shared by every profile, and
// the bottom of the precedence chain: prefs.csv < a profile's own < a per-mode row.
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, api } from '@/api/client'
import { describe } from '@/api/errors'
import type { Download } from '@/api/client'
import type { Validation } from '@/api/types'

export const usePrefsStore = defineStore('prefs', () => {
  const values = ref<Record<string, string>>({})
  const saved = ref<string>('{}')
  const validation = ref<Validation | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  /** Values the API refused, kept so the page can show why. */
  const refused = ref<Validation | null>(null)
  /**
   * The firmware the settings are judged against — it decides which emulation
   * modes hide the flash drive. Sent on every call; null leaves it to the API's
   * default.
   */
  const firmware = ref<number | null>(null)

  const dirty = computed(() => JSON.stringify(values.value) !== saved.value)
  const canExport = computed(
    () => Object.keys(values.value).length > 0 && (validation.value?.errors ?? 0) === 0,
  )

  async function load() {
    loading.value = true
    error.value = null
    try {
      const p = await api.getPrefs(firmware.value)
      values.value = { ...p.preferences }
      saved.value = JSON.stringify(values.value)
      validation.value = p.validation
    } catch (e) {
      error.value = describe(e)
    } finally {
      loading.value = false
    }
  }

  /** An empty value means "don't set this at all", so the key is removed. */
  function set(key: string, value: string) {
    const next = { ...values.value }
    if (value === '') delete next[key]
    else next[key] = value
    values.value = next
  }

  function revert() {
    values.value = JSON.parse(saved.value) as Record<string, string>
    refused.value = null
  }

  async function save() {
    saving.value = true
    error.value = null
    refused.value = null
    try {
      const p = await api.putPrefs(values.value, firmware.value)
      values.value = { ...p.preferences }
      saved.value = JSON.stringify(values.value)
      validation.value = p.validation
      return true
    } catch (e) {
      // A 422 here means a value is outside what the firmware takes; keep the edit
      // on screen with the reason, rather than throwing the user's work away.
      if (e instanceof ApiError && e.status === 422) {
        refused.value = e.validation ?? null
        error.value = e.message
      } else {
        error.value = describe(e)
      }
      return false
    } finally {
      saving.value = false
    }
  }

  async function importFile(file: File) {
    loading.value = true
    error.value = null
    try {
      const p = await api.importPrefs(file, firmware.value)
      values.value = { ...p.preferences }
      saved.value = JSON.stringify(values.value)
      validation.value = p.validation
      return p
    } catch (e) {
      error.value = describe(e)
      return null
    } finally {
      loading.value = false
    }
  }

  async function exportFile(): Promise<Download | null> {
    error.value = null
    try {
      return await api.exportPrefs(firmware.value)
    } catch (e) {
      error.value = describe(e)
      return null
    }
  }

  return {
    values, validation, loading, saving, error, refused, firmware,
    dirty, canExport,
    load, set, revert, save, importFile, exportFile,
  }
})
