import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { useFilePicker } from './useFilePicker'

function host(onFile: (f: File) => void) {
  const Host = defineComponent({
    setup() {
      return useFilePicker(onFile)
    },
    template: `
      <button type="button" @click="pickFile">Import</button>
      <input ref="fileInput" type="file" @change="onFileChosen" />
    `,
  })
  return mount(Host, { attachTo: document.body })
}

describe('useFilePicker', () => {
  it('opens the chooser from the button', async () => {
    const w = host(() => {})
    const input = w.find<HTMLInputElement>('input[type="file"]').element
    const click = vi.spyOn(input, 'click').mockImplementation(() => {})
    await w.find('button').trigger('click')
    expect(click).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('hands the chosen file over and lets the same file be chosen again', async () => {
    const onFile = vi.fn()
    const w = host(onFile)
    const input = w.find<HTMLInputElement>('input[type="file"]').element
    const file = new File(['x'], 'ddfortnite.csv')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    await w.find('input[type="file"]').trigger('change')
    expect(onFile).toHaveBeenCalledWith(file)
    expect(input.value).toBe('')
    w.unmount()
  })

  it('does nothing when the chooser is cancelled', async () => {
    const onFile = vi.fn()
    const w = host(onFile)
    await w.find('input[type="file"]').trigger('change')
    expect(onFile).not.toHaveBeenCalled()
    w.unmount()
  })
})
