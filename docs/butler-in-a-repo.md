# Butler in a Repo: a reference pattern for self-auditing personal AI ops on DeepSeek Harness

This document describes a reference pattern: one AI agent, a handful of plain-text files, and a few scheduled jobs, cooperating to run one person's daily automation — backups, monitoring, research, publishing, weekly reviews — without the agent silently drifting into fiction. Everything here is a shape you can copy; nothing here is a claim about any specific deployment. A minimal companion implementation (six file templates, a heartbeat script, a receipt validator, and contract tests) lives in [`reference/butler-skeleton/`](../reference/butler-skeleton/README.md).

## 1. Overview

**Thesis.** An assistant that does not trust itself by default: each side-effecting action leaves a receipt, every lesson is gated by evidence, and every future task is a line in a hook table.

**The problem it addresses.** A solo operator delegating work to an AI agent faces one recurring failure mode: the agent *says* it did something. Without an external ledger, "done" and "claimed done" are indistinguishable, and mistakes compound quietly across sessions. The conventional fixes — bigger prompts, more rules read at session start, fancier memory systems — all live inside the agent's own context, where they can be ignored, forgotten, or hallucinated. This pattern moves the ground truth *outside* the agent, into files that are diff-able, greppable, and backed up like any other artifact.

**What you get.** A copyable skeleton — six files plus one review pipeline — with scheduling rules, a promotion flow for knowledge, and two verification mechanisms (an evidence gate and a multi-model review pipeline). Everything is plain text or JSONL. Beyond the agent runtime, the only dependencies are the plain-text files themselves and the host scheduler.

**Explicit non-claims.** Nothing here guarantees correctness in your environment. No performance claims. No affiliation with, or endorsement by, any vendor — the named runtime is simply where the pattern was exercised. The value is in the shapes, not in any particular instance.

## 2. System Architecture

```text
                    ┌──────────────────────────────────────────────┐
                    │                   OPERATOR                    │
                    └───────────────┬──────────────────────────────┘
                                    │ one-line instruction
                                    ▼
                    ┌──────────────────────────────────────────────┐
                    │                 BUTLER (agent)                │
                    │        runs on the agent runtime;             │
                    │   reads MEMORY.md at every session start      │
                    └───┬──────────┬──────────┬──────────┬─────────┘
        registers task │  scans   │ appends  │ promotes │ submits candidate
            before act │  7 days  │ receipt  │  lesson  │ for review
                       ▼          ▼          ▼          ▼          ▼
   ┌─────────────┐ ┌─────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
   │  todo.md    │ │ hooks.md│ │receipts.jsonl│ │lessons.jsonl │ │ review pipeline│
   │ single todo │ │ future  │ │ append-only  │ │ → rules.md   │ │ (N reviewers)  │
   │ authority   │ │ hooks   │ │ evidence     │ │ → MEMORY.md  │ │                │
   └──────┬──────┘ └────┬────┘ └──────┬───────┘ └──────┬───────┘ └───────┬────────┘
          │             │             │                │                  │
          └─────────────┴──────┬──────┴────────────────┴──────────────────┘
                               ▼
                 ┌───────────────────────────────┐
                 │      SCHEDULER (launchd)      │
                 │ heartbeat · daily jobs ·      │
                 │ weekly audit · sentinel check │
                 └───────────────┬───────────────┘
                                 │ artifacts cross boundaries:
                                 │ todo lines, hook triggers,
                                 │ receipt hashes, handoff pulls
                                 ▼
        ┌────────────────┬───────────────┬────────────────┐
        │   main host    │    aux host   │  backup host   │
        │ agent home +   │ cross-OS      │ third physical │
        │ primary store  │ checks        │ copy           │
        └────────────────┴───────────────┴────────────────┘
```

Every arrow carries an *artifact* — a todo line, a hook trigger, a receipt hash, a handoff pull — never a credential and never a bare instruction. Hosts are roles (`main / aux / backup`), not names.

## 3. Component Responsibilities

### 3.1 The Orchestrator

The reference scheduler is macOS `launchd`, using one LaunchAgent per concern — a design choice, not a platform requirement — rather than one mega-script. Linux `systemd` timers and Windows Task Scheduler follow the same one-job-per-concern shape.

- **Jobs**: heartbeat (smallest possible loop, several times a day), monitoring fetch (hourly), daily backup, weekly audit/closeout, self-evolution review.
- **Shape of every job**: `ProgramArguments` points at a single shell script; stdout and stderr go to separate log files; the exit code is meaningful — non-zero exits fail the job, and failures are written to a separate alert marker, never swallowed.
- **Idempotency rule**: every scheduled script must be safe to re-run. If a job cannot be made idempotent, it acquires a lock file and refuses to double-execute.
- A launchd template with synthetic example paths ships in the companion skeleton (`com.example.butler-heartbeat.plist`).

### 3.2 The Single Todo Source

One file, one authority. Before the agent acts on any request, the task is registered there; when it completes, the line becomes `[x]` plus a receipt reference. Two sections: near-term (1–3 days) and horizon (everything else). The heartbeat re-reads it every cycle, so drift between sessions is bounded by the cycle length, not by the agent's memory.

Why Markdown instead of a task app: diff-able, backup-able, agent-editable, zero dependencies, and — critically — *outside* the agent's context window, so "I forgot what I promised" has a single auditable answer.

### 3.3 The Far-Future Hook Table

Four columns:

```text
| date       | trigger                 | action                    | status   |
|------------|-------------------------|---------------------------|----------|
| next Sun   | weekly review           | run audit step #N         | pending  |
| +7 days    | re-check observation    | verify candidate L<n>     | pending  |
```

Purpose: remember things across sessions — a "re-check in 7 days" note, a "verify tomorrow at 20:39" gate, a promised follow-up. The heartbeat scans the next seven days every cycle and surfaces due hooks as todo candidates. The scan logic is implemented (and boundary-tested) in the companion heartbeat script.

### 3.4 The Receipt Ledger

One JSONL line per completed action.

Minimal form:

```json
{"ts": "<ISO-8601>", "action": "<verb + object, e.g. backup-verified>", "evidence": "<what was checked: hashes, counts, quoted results>"}
```

Full form adds: `event_id`, `status` (`done | failed | skipped`), `scope`, `input_evidence`, `exit_code`, `artifact_hash`, `validator`, `validation_result`, `cannot_claim`, and `prev_hash` (sha256 of the previous logical line; the first entry carries none).

Rules: every side-effectful action writes a receipt; receipts record *evidence*, never feelings or promises; append-only (single-line appends — atomic per line is bounded by the filesystem and by the single-writer assumption; durability beyond that follows the backup chain); greppable and machine-checkable. A receipt proves a *record* exists; that the action truly happened is re-established by independent checks (exit codes, hash comparisons, second reads, the weekly ceremony) — never by the receipt alone. The hash chain is tamper *evidence*, not tamper proof; independent sentinel copies provide the real drift detection. Real receipts are never published — only schemas and synthetic examples.

### 3.5 The Three Knowledge Layers

- **Lessons** (`lessons.jsonl`): numbered observations (`L1`, `L2`, …), each tied to an evidence pointer. A lesson is a *candidate* until proven.
- **Rules** (`rules.md`): distilled operating law (`R1`, `R2`, …), promoted from lessons only after review. Rules carry precedence and revision history.
- **Memory** (`MEMORY.md`): the session spine — identity, scope, gate vocabulary, current snapshots. Read at the start of every session.

Promotion is one-directional and gated: *lesson → (review gate) → rule*. Memory records the *current* state, never claims about the future.

### 3.6 The Evidence Gate

Four negative principles define the pattern:

1. **Provider output is not truth.** Whatever the model says, however confident, is a claim until evidence exists.
2. **Local files are not canonical truth.** A file can be stale, corrupted, or written by a buggy script. It is evidence only after verification.
3. **Plans are not executions.** A plan is a todo line with no receipt.
4. **Candidates are not canonicals.** Multiple drafts of an idea are candidates until one earns a verified pointer.

Gate vocabulary (generic): `candidate / verified / disputed / superseded`. Verification requires a qualifying evidence pointer — a reproducible tool result, a hash comparison, an external source check — not an assertion. The "cannot-claim" discipline: a claim without evidence is written as a candidate, or not written at all. This single rule, applied mechanically, reduces the most common failure mode of agent assistants: confident fabrication that nobody notices until the backup is actually needed.

### 3.7 The Local Model Lane

A small locally hosted model runs batch and offline jobs — extraction, first-pass classification, drafts, summaries of long transcripts. Its output is labeled `candidate_only` by construction and enters the same gate as everything else.

Lane assignment heuristic: **local for high-volume, low-stakes work; gated cloud calls for decisions; humans for irreversible actions.** The point is not "local is safer" — the gate treats all model output identically — but cost and volume separation: the cheap lane does the bulk, the expensive lane does the judgment, the human does the commitment.

### 3.8 The Multi-Model Review Pipeline

When a candidate artifact matters (a lesson, a rule, a growth claim), it is sent to N reviewers — different models, reached through independent channels — each returning a structured verdict:

```text
verdict ∈ { support | mixed | against | invalid }
optional: cannotClaim  (reviewer refuses to judge on provided evidence)
```

Results are `candidate_review_input` **only**. They can gate *review* — a claim that loses the review is downgraded — but they can never substitute for local evidence, and a unanimous `support` does not make anything true. The pipeline uses HTTPS or a local trusted channel, no third-party SDK; every call is recorded in a usage ledger. Reviewer channels and credentials are deployment details and stay private.

### 3.9 The Three-Machine Topology

```text
        ┌──────────────┐      handoff (hourly pull)      ┌──────────────┐
        │  control hub │ ──────────────────────────────▶ │  backup host │
        │ (schedules,  │ ◀────────────────────────────── │ (third copy) │
        │  ledgers)    │           sentinel compare      └──────────────┘
        └──────┬───────┘
               │ ssh (read-only ops)
        ┌──────▼───────┐
        │  GPU worker  │
        │ (local LLM)  │
        └──────────────┘
```

Three roles: `main` (agent home + primary storage), `aux` (second platform, cross-OS checks), `backup` (third physical copy). Handoff pulls run hourly between machines; backup freshness is verified by **sentinel comparison** — the tail hash of the latest receipt ledger is compared across copies — never by "the log said success". Sentinel equality proves the copies *agree*, not that a restore works; a restore rehearsal in isolation is the check that counts, and its result is itself receipted.

### 3.10 Evidence & Verification Posture

This document is a **methodology description**, not an audit log: it shows shapes, schemas, and design rationale. Quantitative evidence (receipt counts, job success rates, failure drills) lives in a private ledger; the public copy publishes only anonymized schemas.

**Who verifies receipts beyond the agent that wrote them?** The pattern is deliberately not self-certifying: (1) a weekly ceremony re-audits the growth metrics against the ledger; (2) a multi-model review pipeline reads lessons/rules and its output is treated only as candidate review input; (3) an external model audits the operator's own reports; (4) the human owner spot-checks. Passing all four is treated as evidence, not proof: the checks share some inputs, model reviewers can err in correlated ways, and independence is bounded by what each checker actually reads. When checks disagree, resolution falls back to the private ledger, whose trust is bounded by its writers and validators (see 3.4); every check is itself logged.

**Failure degradation:** if a receipt cannot be written, the run fails closed (non-zero exit plus a failure marker on a separate alert path — configurable, outside the ledger directory) rather than silently succeeding, and no success receipt is written. The heartbeat also fails closed when its input files are missing or unreadable, so it never writes a receipt that claims work it could not do.

## 4. Key Design Decisions

Each entry: what → why → trade-off → what was rejected.

1. **Markdown + JSONL files over databases.** *Why:* diff/grep/backup with zero daemons. *Trade-off:* no transactions, no rich queries. *Rejected:* a real database, a task app, a notes SaaS.
2. **Receipts for every side effect.** *Why:* auditability beats convenience; "no receipt" is a machine-checkable definition of "not done". *Trade-off:* discipline overhead. *Rejected:* trusting the agent's verbal summary.
3. **One todo source + one hook table.** *Why:* removes "I forgot what I promised" as a failure class. *Trade-off:* two more files to keep consistent. *Rejected:* per-conversation task lists.
4. **Evidence-gated promotion (candidate → verified).** *Why:* the anti-hallucination mechanism. *Trade-off:* slower knowledge accumulation. *Rejected:* auto-distilling anything the model finds interesting.
5. **Local lane for candidates, gated lanes for decisions.** *Why:* cost separation and clear labels. *Trade-off:* two model paths to maintain. *Rejected:* everything through one expensive endpoint.
6. **Multi-model review as input, never as authority.** *Why:* correlated errors exist inside any single model. *Trade-off:* review latency and token cost. *Rejected:* "the strongest model arbitrates".
7. **Scheduled idempotent scripts over long-running daemons.** *Why:* crash-safe, restart-safe, observable exit codes. *Trade-off:* coarser reactivity. *Rejected:* a resident process holding state.
8. **Backups verified by sentinels, not logs.** *Why:* logs record intent; a matching hash shows a specific byte set is consistent. *Trade-off:* an extra comparison step. *Rejected:* "backup succeeded" as an exit code.

## 5. How to Replicate

The companion skeleton (`reference/butler-skeleton/`) contains the six templates, `heartbeat.sh`, `receipt-validator.py`, a launchd template, and 19 contract tests. The shortest loop:

```bash
# 1. run the contract tests
python3 -m unittest discover -s tests
# -> Ran 19 tests ... OK

# 2. run one heartbeat (append-only, hash-chained)
./heartbeat.sh
# -> [heartbeat] ok | open todos: 1 | due hooks: 0 | ledger receipts: 2

# 3. validate the ledger
python3 receipt-validator.py receipts.jsonl
# -> [ok] ledger valid

# 4. failure drills in an isolated root (never touch the shipped ledger)
D="$(mktemp -d)"; cp receipts.jsonl todo.md hooks.md "$D/"
printf 'corrupt\n' > "$D/receipts.jsonl"
BUTLER_ROOT="$D" BUTLER_ALERT_FILE="$D.alert" bash heartbeat.sh; echo "exit=$?"
# -> [heartbeat] ledger invalid -> fail-closed ; exit=1
```

Then, in order: (1) adopt the gate vocabulary before automating anything else; (2) add hooks only after the heartbeat reliably reads them for two weeks — the two-week and 2–4-week figures are empirical suggestions from the author's experience, not validated thresholds; (3) add the local lane and the multi-model review only after stable receipts. Both are amplifiers: they amplify discipline or amplify drift, depending on what came first.

Version note: the pattern was exercised on DeepSeek Harness `0.1.x`, which is a developer preview — pin your runtime version and re-verify against each release's notes.

Rule of thumb: every new component must *produce* a receipt before it is allowed to *consume* anything.

## 6. Common Pitfalls

Each with symptom → cause → fix.

1. **Agent says "done", no receipt exists.** → Evidence was never required. → Treat as not done; make the receipt rule mechanical.
2. **Scheduled job fails silently for weeks.** → Logs swallowed; exit codes ignored. → Separate `.log`/`.err.log`, non-zero exit → alert marker; the heartbeat's own checks cover its own inputs only.
3. **A follow-up promise forgotten between sessions.** → No single hook table. → `hooks.md` + 7-day scan.
4. **A lesson promoted to rule after one lucky run.** → Promotion gate too weak. → Require qualifying evidence + review before any promotion.
5. **Multi-model consensus treated as truth.** → Reviews misread as verdicts. → Reviews are candidate input only.
6. **Backup "success" trusted from logs.** → Logs record intent, not fact. → Sentinel hash comparison across copies.
7. **Secrets leaking into published docs.** → No publishing boundary. → Publish schema, never content (see section 7).
8. **Non-idempotent script double-executes.** → No re-entry guard. → Idempotency rule from day one; lock files where it is impossible.

## 7. Privacy and Publishing Boundaries

Publish **patterns, not instances**. The threat model is simple and absolute on one axis:

- **Never published**: hostnames, keys, tokens, real receipts, real lesson contents, machine identities, network layouts.
- **Published only after operator review**: screenshots of live environments, concrete plists with real paths (only `<placeholder>` versions go out).
- **Published freely**: schemas, synthetic examples, the role diagram, the sentinel-comparison idea, the review protocol (without provider credentials).

The operator is the sole approver for anything beyond the methodology core. If you are copying this pattern, apply the same rule to your own deployment data before publishing anything.

## 8. Appendix: Minimal File Formats

Generic schemas only; all values are `<placeholders>`, examples are synthetic.

**`receipts.jsonl`** — one line per action (full form fields listed in 3.4):

```json
{"ts": "2026-08-20T09:00:00+08:00", "event_id": "evt-1", "action": "daily-backup-verified", "status": "done", "scope": "<paths>", "input_evidence": "<pointer>", "exit_code": 0, "artifact_hash": "<sha256>", "validator": "<who, when>", "validation_result": "<quoted output>", "cannot_claim": "<what this does NOT prove>"}
```

**`lessons.jsonl`** — one line per lesson:

```json
{"id": "L<NN>", "ts": "<ISO-8601>", "claim": "<what happened>", "evidence": "<pointer>", "status": "candidate | verified | disputed | superseded"}
```

**`rules.md`** — rule block header:

```text
# R<n> — <title>
## Status: <effective date> · rev <n> · source lesson L<m> (post-review)
## Rule: <one executable constraint>
## Flip condition: <evidence that retires this rule>
```

**`hooks.md`** — columns: `date | trigger | action | status` (see 3.3).

**`todo.md`** — sections `near-term` / `horizon`; completed lines carry `[x]` and a receipt reference.

**`MEMORY.md`** — skeleton: identity, scope, gate vocabulary (the four negative principles), current snapshots (pointers only, updated with receipts).

**Weekly ceremony metrics (generic)** — the ceremony re-audits a fixed five-metric growth set; placeholders: receipts added · error hits · backup failures · lessons promoted · external actions. Real values never leave the private ledger.
