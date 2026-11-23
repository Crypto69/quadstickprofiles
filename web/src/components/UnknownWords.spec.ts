// A profile from somebody else's Google Sheet can hold a word the firmware does not
// know: an output name typed in an input column, a function that does not exist. The
// API stores such a word so the row can be fixed here, and never lists it in the
// catalog. Every editor screen has to show that profile without falling over, and the
// rows table has to show the word itself so it can be replaced.
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DeviceView from './DeviceView.vue'
import MappingEditor from './MappingEditor.vue'
import ModeMap from './ModeMap.vue'
import TableView from './TableView.vue'
import type { Profile } from '@/api/types'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'
import { budget, catalog, editableProfile, stubFetch, validation } from '@/test/factories'

type Row = Profile['modes'][number]['mappings'][number]

function row(id: number, over: Partial<Row>): Row {
  return {
    id, row_order: id - 1, row: id + 3, kind: 'mapping', output: 'x', value: '',
    function: 'normal', params: [], inputs: [], comment: null, is_sequence: false,
    ...over,
  }
}

/** One mode: a made-up output, a made-up function, and an output name used as an input. */
function strangeProfile(): Profile {
  return editableProfile({
    modes: [
      {
        id: 1, position: 1, name: 'Left', label: 'Left', channel: 'usb',
        mappings: [
          row(1, { output: 'fire_button', inputs: ['lip'] }),
          row(2, { output: 'x', function: 'hold', params: [5], inputs: ['mp_left_sip'] }),
          row(3, { output: 'circle', inputs: ['circle'] }),
          row(4, { output: 'increment_mode', inputs: ['right_sip'] }),
        ],
      },
    ],
  })
}

async function load() {
  vi.stubGlobal(
    'fetch',
    stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles/1': strangeProfile(),
      'POST /api/profiles/validate': validation({ budget: budget() }),
    }),
  )
  await useCatalogStore().load()
  const docStore = useDocumentStore()
  await docStore.load(1)
  return docStore
}

describe('a profile with words the firmware does not know', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('opens in the device view, the mode map and the mapping card', async () => {
    await load()
    expect(mount(DeviceView, { props: { selectedInput: null } }).find('table').exists()).toBe(true)
    expect(mount(ModeMap).find('svg').exists()).toBe(true)
    const card = mount(MappingEditor, { props: { input: 'lip' } })
    expect(card.text()).toContain('(current) fire_button')
  })

  it('shows each word on its row in the table, as the current value', async () => {
    const docStore = await load()
    const w = mount(TableView)
    const output = w.find<HTMLSelectElement>('select[aria-label="Output on row 4"]')
    expect(output.element.value).toBe('fire_button')
    expect(output.findAll('option')[1]!.text()).toBe('(current) fire_button')
    const input = w.find<HTMLSelectElement>('select[aria-label="Input on row 6"]')
    expect(input.element.value).toBe('circle')
    expect(input.text()).toContain('(current) circle')
    // nothing was rewritten just by looking
    expect(docStore.dirty).toBe(false)
    // and picking a real input replaces the typo
    await input.setValue('mp_left_puff')
    expect(docStore.doc!.modes[0]!.mappings[2]!.inputs).toEqual(['mp_left_puff'])
  })
})
