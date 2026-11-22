// Hand-built QuadStick input reports for the tester's tests: the first ten bytes
// of the 64-byte PS4-layout frame, byte 0 the report id (see tester/decode.ts).
import specJson from './tester-spec.json'
import type { TesterSpec } from '@/tester/decode'

/** The spec the API serves, as core/qsprofile/tester.py generates it.
 *  tests/test_tester.py fails when this copy falls behind. */
export const testerSpec = specJson as TesterSpec

/** A report: the hat in byte 5's low nibble (15 = released), the rest as given. */
export function frame(
  opts: { hat?: number; b5?: number; b6?: number; b7?: number; x?: number; y?: number } = {},
): number[] {
  const b = [1, opts.x ?? 128, opts.y ?? 128, 128, 128, 0, 0, 0, 0, 0]
  b[5] = (opts.hat ?? 15) | (opts.b5 ?? 0)
  b[6] = opts.b6 ?? 0
  b[7] = opts.b7 ?? 0
  return b
}
