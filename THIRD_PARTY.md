# Source attribution and reuse record

Reference: https://github.com/Srijaali/ai-engineering
Reviewed revision: `8dbedf12d56c37f1ba467c626107a0e3ebc67d9f`.

The user confirmed permission to reuse source in this chat on 2026-10-26.
No repository-wide license was present in metadata or README when reviewed;
this record documents that confirmation, not an independent license grant.

Adapted portions:
- `backend/app/models/chat_client.py`: the duplicate-JSON-key rejecting decoder
  (`unique_object`), integrated in `backend/adapters/chat_completions.py`.
- `backend/app/prompts.py`: explicit outside-face viewpoint wording for move
  definitions, integrated identically across four models in `backend/presentation.py`.

The UI theme was independently implemented in the existing application. The
reference repository's credentials, identity, videos and saved experimental
results were not imported. Your existing server-only key and persistent suite
budget are retained. No paid inference was triggered during this adaptation.

This change does not claim that the entire reference backend was transplanted.
The verified local engine, Pure/Assisted conditions, oracle controls, result
provenance and persistent budget remain the runtime implementation. Changing the
look is a design change; this attribution remains visible in the project source.

New request wording is recorded as `oriented-color-net-v3` in game configuration
and resume fingerprints, preventing resumed trials from mixing prompt revisions.
