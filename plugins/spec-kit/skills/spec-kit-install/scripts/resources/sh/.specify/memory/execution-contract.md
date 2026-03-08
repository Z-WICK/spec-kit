# Subagent Execution Contract (Constitution v2.4.0)

Apply this contract to every subagent dispatch in enhanced workflows (`pipeline`, `fixbug`, and future additions).

## 1. Chunked Write

- When writing large files (>200 lines), write in chunks of <=200 lines.
- Use `Create` for the first chunk, then `Edit` to append.

## 2. Dynamic Timeout Tier

Select timeout based on task scope:

- Small task (<=1 file, low complexity): `timeout=180`
- Medium task (2-5 files or moderate complexity): `timeout=420`
- Large task (6+ files, migration-heavy, or integration-heavy): `timeout=600`

Do not use a fixed timeout for all tasks.

## 3. Retry and Backoff

- Retry 1: wait 15 seconds
- Retry 2: wait 30 seconds
- If still failing after retry 2: split scope and re-dispatch once
- If split run still fails: stop and report blocking details

## 4. Prompt Footer

Append this single-line footer to each subagent prompt:

`Execution Contract: chunked write, dynamic timeout tier, and retry metadata apply.`

## 5. Failure Reporting

On timeout/failure, record:

- Task/subagent identifier
- Timeout tier used
- Retry count
- Known progress/evidence produced
- Next retry/split decision
