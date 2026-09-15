import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DeviceView from './DeviceView.vue'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'
import { FRONT_HOTSPOTS, FRONT_LEDS, REAR_HOTSPOTS, STRENGTHS } from '@/device/layout'
import { budget, catalog, editableProfile, stubFetch, validation } from '@/test/factories'

async function setup(selectedInput: string | null = null) {
  vi.stubGlobal(
    'fetch',
    stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles/1': editableProfile(),
      'POST /api/profiles/validate': validation({ budget: budget() }),
    }),
  )
  const cat = useCatalogStore()
  await cat.load()
  const docStore = useDocumentStore()
  await docStore.load(1)
  const w = mount(DeviceView, { props: { selectedInput } })
  return { w, docStore }
}

describe('DeviceView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('shows the four holes with the side tube last', async () => {
    const { w } = await setup()
    const headers = w.findAll('thead th').map((h) => h.text())
    expect(headers).toContain('Left hole')
    expect(headers).toContain('Centre hole')
    expect(headers).toContain('Right hole')
    expect(headers).toContain('Side tube')
  })

  it('offers all four pressure levels, softest puff first', async () => {
    const { w } = await setup()
    const rows = w.findAll('tbody th').map((t) => t.text())
    expect(rows.slice(0, 4)).toEqual(['Soft puff', 'Puff', 'Sip', 'Soft sip'])
  })

  it('marks an unmapped slot as free, not just blank', async () => {
    const { w } = await setup()
    const empties = w.findAll('.slot.empty')
    expect(empties.length).toBeGreaterThan(0)
    expect(empties[0]!.text()).toContain('free')
    // a real mapping is not marked empty
    const mapped = w.findAll('.slot').filter((s) => !s.classes().includes('empty'))
    expect(mapped.length).toBeGreaterThan(0)
  })

  it('shows what is mapped, with the game action rather than the keyword', async () => {
    const { w } = await setup()
    // x is mapped to mp_center_sip and labelled "Jump"
    const slot = w.findAll('.slot').find((s) => s.text().includes('Jump'))
    expect(slot).toBeTruthy()
  })

  it('tells the caller which input was clicked', async () => {
    const { w } = await setup()
    const slot = w.findAll('.slot').find((s) => s.attributes('aria-label')?.startsWith('Centre sip'))
    expect(slot).toBeTruthy()
    await slot!.trigger('click')
    expect(w.emitted('select')![0]).toEqual(['mp_center_sip'])
  })

  it('names every slot for a screen reader, saying whether it is free', async () => {
    const { w } = await setup()
    for (const s of w.findAll('.slot')) {
      const label = s.attributes('aria-label') ?? ''
      expect(label).toMatch(/free, nothing mapped|\d+ mapped/)
    }
  })

  it('uses the profile name for an input, not the catalog name', async () => {
    const { w, docStore } = await setup()
    expect(docStore.doc!.input_names.lip).toBe('Chin switch')
    expect(w.text()).toContain('Chin switch')
    expect(w.text()).not.toContain('Lip button')
  })

  it('labels the rear jacks the way the case is printed', async () => {
    const { w } = await setup()
    const text = w.text()
    expect(text).toContain('In 7-8')
    expect(text).toContain('Lip 5-6')
    expect(text).toContain('In 1-2')
    expect(text).toContain('In 3-4')
    expect(text).toContain('the top jack is')
  })

  it('has a slot for every switch input 1 through 8', async () => {
    const { w } = await setup()
    const labels = w.findAll('.slot').map((s) => s.attributes('aria-label') ?? '')
    for (const n of [1, 2, 3, 4, 5, 6, 7, 8]) {
      expect(labels.some((l) => l.includes(`Switch ${n}`) || l.includes(`digital_in_${n}`))).toBe(
        true,
      )
    }
  })

  it('hides the hole-combo grid until something uses one', async () => {
    const { w, docStore } = await setup()
    expect(w.text()).not.toContain('Two or three holes together')
    docStore.addMapping(docStore.doc!.modes[0]!.key, {
      inputs: ['mp_left_center_sip'],
      output: 'square',
    })
    await w.vm.$nextTick()
    expect(w.text()).toContain('Two or three holes together')
    expect(w.text()).toContain('Left + Centre')
  })

  it('says the joystick does nothing when nothing is bound to it', async () => {
    const { w } = await setup()
    expect(w.text()).toContain('it does nothing here')
  })

  it('marks the selected slot as pressed', async () => {
    const { w } = await setup('mp_center_sip')
    const selected = w.findAll('.slot').filter((s) => s.classes().includes('selected'))
    expect(selected).toHaveLength(1)
    expect(selected[0]!.attributes('aria-pressed')).toBe('true')
  })

  it('lights the status LEDs for the selected mode', async () => {
    const { w, docStore } = await setup()
    const leds = w.findAll('.led')
    expect(leds).toHaveLength(5)
    // mode 1 lights LED 1 only
    expect(leds.map((l) => l.classes().includes('lit'))).toEqual([
      true, false, false, false, false,
    ])

    docStore.selectMode(docStore.doc!.modes[1]!.key)
    await w.vm.$nextTick()
    expect(w.findAll('.led').map((l) => l.classes().includes('lit'))).toEqual([
      false, true, false, false, false,
    ])
  })

  it('says in words which LEDs are lit, and in what colour', async () => {
    const { w, docStore } = await setup()
    expect(w.find('.led-key').text()).toContain('LED 1 purple')

    // mode 12: the colour is the only thing separating it from mode 7
    for (let i = 3; i <= 12; i++) docStore.addMode(`M${i}`, 16)
    docStore.selectMode(docStore.doc!.modes[11]!.key)
    await w.vm.$nextTick()
    expect(w.find('.led-key').text()).toContain('LED 2 purple and LED 5 blue')
  })

  it('colours the lit LEDs the way the firmware does', async () => {
    const { w, docStore } = await setup()
    const colourOf = (led: ReturnType<typeof w.findAll>[number]) =>
      ['purple', 'blue', 'red'].find((c) => led.classes().includes(c)) ?? 'off'
    expect(w.findAll('.led').map(colourOf)).toEqual(['purple', 'off', 'off', 'off', 'off'])

    for (let i = 3; i <= 15; i++) docStore.addMode(`M${i}`, 16)
    docStore.selectMode(docStore.doc!.modes[9]!.key) // mode 10
    await w.vm.$nextTick()
    expect(w.findAll('.led').map(colourOf)).toEqual(['off', 'off', 'off', 'off', 'blue'])
    docStore.selectMode(docStore.doc!.modes[14]!.key) // mode 15
    await w.vm.$nextTick()
    expect(w.findAll('.led').map(colourOf)).toEqual(['off', 'off', 'off', 'off', 'red'])
  })

  // The figure has 9.5em of padding-top for the lifted callout labels, so a
  // percentage measured off it lands above the image. Both the LED dots and their
  // label must therefore live inside .shot, which wraps the image alone.
  it('positions the LEDs and their label against the image, not the padded figure', async () => {
    const { w } = await setup()
    const shot = w.find('.shot')
    expect(shot.exists()).toBe(true)
    expect(shot.findAll('.led')).toHaveLength(5)
    expect(shot.find('img').exists()).toBe(true)
    // the Status LEDs callout belongs with them, not with the figure's callouts
    const label = shot.find('.callout--led')
    expect(label.exists()).toBe(true)
    expect(label.text()).toContain('Status LEDs')
    // and it is not also rendered among the figure-space callouts
    const outside = w.findAll('.callout--led').filter((c) => !c.element.closest('.shot'))
    expect(outside).toHaveLength(0)
  })

  // Anchored on LED 1, the label's own dot covered that light — the one the
  // overlay lights for mode 1.
  it('keeps the Status LEDs label clear of the lights themselves', async () => {
    const { w } = await setup()
    const label = w.find('.shot .callout--led')
    const left = Number.parseFloat(label.attributes('style')!.match(/left:\s*([\d.]+)%/)![1]!)
    // left of every LED, by more than the dot's own radius (1.7% of the photo)
    for (const led of FRONT_LEDS) expect(left).toBeLessThan(led.x - 1.7)
  })

  // The dot was the app's mode blue, which read as "the LEDs are blue" while every
  // lit light beside it was purple.
  it('colours the Status LEDs dot the way the lights are lit', async () => {
    const { w, docStore } = await setup()
    const dot = () => w.find('.shot .callout--led').attributes('style') ?? ''
    expect(dot()).toContain('--led-purple')

    // mode 10 lights LED 5 blue
    for (let i = 3; i <= 15; i++) docStore.addMode(`M${i}`, 16)
    docStore.selectMode(docStore.doc!.modes[9]!.key)
    await w.vm.$nextTick()
    expect(dot()).toContain('--led-blue')

    // mode 12 is LED 2 purple *and* LED 5 blue: LED 5 says which round of counting
    docStore.selectMode(docStore.doc!.modes[11]!.key)
    await w.vm.$nextTick()
    expect(dot()).toContain('--led-blue')

    // mode 15 lights LED 5 red
    docStore.selectMode(docStore.doc!.modes[14]!.key)
    await w.vm.$nextTick()
    expect(dot()).toContain('--led-red')
  })

  it('carries alt text on both photos', async () => {
    const { w } = await setup()
    const alts = w.findAll('img').map((i) => i.attributes('alt') ?? '')
    expect(alts).toHaveLength(2)
    for (const a of alts) expect(a.length).toBeGreaterThan(20)
  })

  // --- clicking the picture itself -----------------------------------------
  const spotFor = (w: Awaited<ReturnType<typeof setup>>['w'], part: string) =>
    w.findAll('.hotspot')[[...FRONT_HOTSPOTS, ...REAR_HOTSPOTS].findIndex((s) => s.part === part)]!

  it('puts a clickable part over every callout on both photos', async () => {
    const { w } = await setup()
    expect(w.findAll('.hotspot')).toHaveLength(FRONT_HOTSPOTS.length + REAR_HOTSPOTS.length)
    // front hotspots belong with the image, not the padded figure, like the LEDs
    expect(w.findAll('.shot .hotspot')).toHaveLength(FRONT_HOTSPOTS.length)
  })

  it('names each part and what it does, for people who never see the tooltip', async () => {
    const { w } = await setup()
    const label = spotFor(w, 'mp_left').attributes('aria-label') ?? ''
    expect(label).toContain('Left hole')
    expect(label).toContain('Sip or puff')
    expect(label).toMatch(/mapped here in this mode/)
  })

  it('shows a tooltip on hover and hides it again', async () => {
    const { w } = await setup()
    const spot = spotFor(w, 'lip')
    expect(spot.find('.tip').exists()).toBe(false)
    await spot.trigger('mouseenter')
    // the name comes first: "what is this thing" is what the tooltip is for
    expect(spot.find('.tip b').text()).toBe('Chin switch')
    expect(spot.find('.tip').text()).toContain('Press it with your lip or chin')
    await spot.trigger('mouseleave')
    expect(spot.find('.tip').exists()).toBe(false)
  })

  // Keyboard users get the same explanation the mouse does, not a dead control.
  it('shows the tooltip on keyboard focus too', async () => {
    const { w } = await setup()
    const spot = spotFor(w, 'joystick')
    await spot.trigger('focus')
    expect(spot.find('.tip').exists()).toBe(true)
    await spot.trigger('blur')
    expect(spot.find('.tip').exists()).toBe(false)
  })

  it('uses the profile name for the lip button on the photo', async () => {
    const { w } = await setup()
    expect(spotFor(w, 'lip').attributes('aria-label')).toContain('Chin switch')
  })

  it('counts what the whole part carries, not just one input', async () => {
    const { w, docStore } = await setup()
    // the fixture maps x to mp_center_sip
    expect(spotFor(w, 'mp_center').attributes('aria-label')).toContain('1 thing mapped')
    docStore.addMapping(docStore.doc!.modes[0]!.key, {
      inputs: ['mp_center_puff'],
      output: 'circle',
    })
    await w.vm.$nextTick()
    expect(spotFor(w, 'mp_center').attributes('aria-label')).toContain('2 things mapped')
  })

  it('narrows the page to one hole when that hole is clicked', async () => {
    const { w } = await setup()
    await spotFor(w, 'mp_left').trigger('click')
    const headers = w.findAll('thead th').map((h) => h.text())
    expect(headers).toContain('Left hole')
    expect(headers).not.toContain('Centre hole')
    expect(headers).not.toContain('Side tube')
    // the other parts' sections go with them (the photo callouts stay — the whole
    // device is still in the picture, it is only the tables that narrow)
    const headings = w.findAll('h3').map((h) => h.text())
    expect(headings).not.toContain('Joystick')
    expect(headings).not.toContain('Switch jacks')
    expect(w.text()).toContain('Showing only')
  })

  it('shows only the lip button when the lip button is clicked', async () => {
    const { w } = await setup()
    await spotFor(w, 'lip').trigger('click')
    expect(w.text()).toContain('Chin switch')
    expect(w.text()).not.toContain('Mouthpiece and side tube')
    expect(w.text()).not.toContain('Switch jacks')
    const labels = w.findAll('.slot').map((s) => s.attributes('aria-label') ?? '')
    expect(labels.every((l) => l.startsWith('Chin switch'))).toBe(true)
  })

  it('shows only its own two inputs when a rear jack is clicked', async () => {
    const { w } = await setup()
    await spotFor(w, 'jack_7').trigger('click')
    const labels = w.findAll('.slot').map((s) => s.attributes('aria-label') ?? '')
    expect(labels).toHaveLength(2)
    expect(labels.join(' ')).toContain('Switch 7')
    expect(labels.join(' ')).toContain('Switch 8')
    expect(labels.join(' ')).not.toContain('Switch 1')
  })

  it('marks the picked part as pressed and the rest as not', async () => {
    const { w } = await setup()
    await spotFor(w, 'right').trigger('click')
    const pressed = w.findAll('.hotspot').filter((s) => s.attributes('aria-pressed') === 'true')
    expect(pressed).toHaveLength(1)
    expect(pressed[0]!.attributes('aria-label')).toContain('Side tube')
  })

  // Picking a part must never be a one-way door.
  it('clears the pick when the same part is clicked again', async () => {
    const { w } = await setup()
    const headings = () => w.findAll('h3').map((h) => h.text())
    await spotFor(w, 'mp_right').trigger('click')
    expect(headings()).not.toContain('Joystick')
    await spotFor(w, 'mp_right').trigger('click')
    expect(headings()).toContain('Joystick')
    expect(w.text()).not.toContain('Showing only')
  })

  it('offers a way back to the whole device', async () => {
    const { w } = await setup()
    await spotFor(w, 'lip').trigger('click')
    await w.find('.picked-bar .link').trigger('click')
    expect(w.text()).toContain('Mouthpiece and side tube')
    expect(w.text()).toContain('Switch jacks')
    expect(w.find('.picked-bar').exists()).toBe(false)
  })

  it('keeps a picked hole its combos, and drops the ones it is not in', async () => {
    const { w, docStore } = await setup()
    const mode = docStore.doc!.modes[0]!.key
    docStore.addMapping(mode, { inputs: ['mp_left_center_sip'], output: 'square' })
    docStore.addMapping(mode, { inputs: ['mp_right_center_sip'], output: 'circle' })
    await w.vm.$nextTick()
    await spotFor(w, 'mp_left').trigger('click')
    expect(w.text()).toContain('Left + Centre')
    expect(w.text()).not.toContain('Right + Centre')
  })

  // Hovering links the two halves: the part lights on the photo, and whatever holds
  // its mappings lights below. Without it the picture is only an illustration.
  // `.lit` is also the status-LED overlay's class, so these count only the things
  // that carry mappings — sections, grid cells and jacks.
  const litParts = (w: Awaited<ReturnType<typeof setup>>['w']) =>
    w.findAll('section.lit, .jack.lit, .grid .lit')

  it('lights the matching section while a part is hovered', async () => {
    const { w } = await setup()
    expect(litParts(w)).toHaveLength(0)
    await spotFor(w, 'lip').trigger('mouseenter')
    const lit = w.findAll('section.lit')
    expect(lit).toHaveLength(1)
    expect(lit[0]!.find('h3').text()).toBe('Chin switch')
    await spotFor(w, 'lip').trigger('mouseleave')
    expect(litParts(w)).toHaveLength(0)
  })

  it('lights only the hovered hole, as a column', async () => {
    const { w } = await setup()
    await spotFor(w, 'mp_left').trigger('mouseenter')
    expect(w.find('thead th.lit').text()).toBe('Left hole')
    // one heading plus the four pressures below it, and nothing else
    expect(w.findAll('.grid .lit')).toHaveLength(1 + STRENGTHS.length)
    expect(w.findAll('section.lit')).toHaveLength(0)
  })

  it('lights the combos a hovered hole takes part in', async () => {
    const { w, docStore } = await setup()
    const mode = docStore.doc!.modes[0]!.key
    docStore.addMapping(mode, { inputs: ['mp_left_center_sip'], output: 'square' })
    docStore.addMapping(mode, { inputs: ['mp_right_center_sip'], output: 'circle' })
    await w.vm.$nextTick()
    await spotFor(w, 'mp_left').trigger('mouseenter')
    const headings = w.findAll('thead th.lit').map((h) => h.text())
    expect(headings).toContain('Left hole')
    expect(headings).toContain('Left + Centre')
    expect(headings).not.toContain('Right + Centre')
  })

  // The editor pane lives in EditorView, so the device view hands it the inputs
  // rather than reaching across: the pane rings itself when it is showing one.
  it('tells the page which inputs the hovered part owns', async () => {
    const { w } = await setup()
    await spotFor(w, 'mp_left').trigger('mouseenter')
    const inputs = w.emitted('hover')!.at(-1)![0] as string[]
    expect(inputs).toContain('mp_left_sip')
    expect(inputs).toContain('mp_left_puff_soft')
    // the combos the left hole takes part in come with it
    expect(inputs).toContain('mp_left_center_sip')
    expect(inputs).toContain('mp_triple_puff')
    expect(inputs).not.toContain('mp_right_center_sip')
    expect(inputs).not.toContain('mp_center_sip')

    await spotFor(w, 'mp_left').trigger('mouseleave')
    expect(w.emitted('hover')!.at(-1)![0]).toEqual([])
  })

  it('gives the lip button and a jack their own inputs', async () => {
    const { w } = await setup()
    await spotFor(w, 'lip').trigger('mouseenter')
    expect(w.emitted('hover')!.at(-1)![0]).toEqual(['lip', 'lip_soft'])
    await spotFor(w, 'jack_7').trigger('mouseenter')
    expect(w.emitted('hover')!.at(-1)![0]).toEqual(['digital_in_7', 'digital_in_8'])
  })

  it('lights only the hovered jack', async () => {
    const { w } = await setup()
    await spotFor(w, 'jack_1').trigger('mouseenter')
    const lit = w.findAll('.jack.lit')
    expect(lit).toHaveLength(1)
    expect(lit[0]!.text()).toContain('In 1-2')
  })

  // Keyboard users get the same link the mouse does.
  it('lights the matching section on keyboard focus too', async () => {
    const { w } = await setup()
    await spotFor(w, 'joystick').trigger('focus')
    expect(w.find('section.lit h3').text()).toBe('Joystick')
    await spotFor(w, 'joystick').trigger('blur')
    expect(litParts(w)).toHaveLength(0)
  })

  it('still selects an input for the editor after a part is picked', async () => {
    const { w } = await setup()
    await spotFor(w, 'mp_center').trigger('click')
    const slot = w.findAll('.slot').find((s) => s.attributes('aria-label')?.startsWith('Centre sip'))
    await slot!.trigger('click')
    expect(w.emitted('select')!.at(-1)).toEqual(['mp_center_sip'])
  })
})
