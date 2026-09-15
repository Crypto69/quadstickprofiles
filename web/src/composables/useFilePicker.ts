// A hidden <input type="file"> behind a visible button: one click opens the
// chooser (single-pointer, no drag-and-drop), and the input is reset after each
// pick so the same file can be chosen again.
import { ref } from 'vue'

export function useFilePicker(onFile: (file: File) => unknown) {
  /** Bind with `ref="fileInput"` on the hidden input. */
  const fileInput = ref<HTMLInputElement | null>(null)

  function pickFile() {
    fileInput.value?.click()
  }

  async function onFileChosen(e: Event) {
    const input = e.target as HTMLInputElement
    const file = input.files?.[0]
    input.value = '' // let the same file be chosen again
    if (file) await onFile(file)
  }

  return { fileInput, pickFile, onFileChosen }
}
