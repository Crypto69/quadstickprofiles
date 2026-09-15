// One place that turns whatever was thrown into the line a store shows the user.
// Every store used to carry its own copy of this; keep them all on this one so a
// change in wording (or in what counts as a message) happens once.

/** The message from an Error — an ApiError included — or the value spelt out. */
export function describe(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}
