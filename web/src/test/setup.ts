// Vitest runs in jsdom. Nothing here should reach the network: every test that
// touches the API stubs fetch.
import { beforeEach, vi } from 'vitest'

beforeEach(() => {
  vi.restoreAllMocks()
})

// jsdom has no URL.createObjectURL, which the export path uses.
if (!('createObjectURL' in URL)) {
  Object.defineProperty(URL, 'createObjectURL', { value: vi.fn(() => 'blob:test'), writable: true })
  Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), writable: true })
}
