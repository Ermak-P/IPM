# Synthetic domain overview

All rules below are fictional examples for architecture experiments.

- Campaign Management owns campaign names, content references and lifecycle.
  Campaign is an aggregate with a single authoritative transition method.
- Content Management owns immutable items and named groups. ContentType explicitly
  defines Banner=1 (short placement), Modal=2 (overlay), Inline=3 (embedded message).
  These values have no relationship to any corporate enum.
- Targeting owns an audience per campaign, evaluated against a synthetic user.
  Country equality is case-insensitive; minimum age is inclusive. Both conditions
  must match. The evaluator has no knowledge of lifecycle states.
- Distribution joins campaign, content, targeting and synchronized lifecycle state
  to produce a publication receipt and impression event.
- External Management validates a fictional partner DTO, maps its title and audience,
  and maintains an external-ID-to-internal-GUID link. It cannot set lifecycle state.
- Statistics consumes identifier-only impression and interaction events. It neither
  loads nor depends on Campaign aggregates, content or targeting repositories.
- State Synchronization copies campaign lifecycle state to the distribution projection
  synchronously after creation/transition. Deletion removes the projection.

Principal example: import a draft, create and associate banner content, move to Ready
then Active, publish for a matching synthetic user, consume the resulting impression,
submit an interaction, consume again, finish the campaign and observe deletion refusal.
