# Domain Docs

How engineering skills should consume this repository's domain documentation.

## Before exploring, read these

- `CONTEXT.md` at the repository root.
- `CONTEXT-MAP.md` instead, if one is introduced later.
- Relevant ADRs under `docs/adr/`.

If a file does not exist, proceed silently. Domain documentation and ADRs are
created lazily when terminology or architectural decisions are resolved.

## File structure

This is a single-context repository:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── easyprent_accounting/
```

## Use the glossary's vocabulary

Use terms as defined in `CONTEXT.md`. Do not drift to synonyms that the glossary
explicitly marks as undesirable.

If a required concept is absent, reconsider whether new terminology is necessary
or record the gap for domain modeling.

## Flag ADR conflicts

Explicitly identify output that contradicts an existing ADR instead of silently
overriding the decision.
