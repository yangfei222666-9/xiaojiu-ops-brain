# Butler in a Repo: a personal AI ops system on DeepSeek Harness

> Draft v0.4 · 2026-08-21 · methodology only. No personal data, no keys, no private paths.
> Every section carries a privacy gate: **[A]** publishable as-is · **[B]** publishable only in redacted form (per operator decision) · **[X]** internal only.
> This document describes patterns, not a particular operator's deployment. All examples are synthetic.

---

## 1. Overview — [A]

**Thesis.** An assistant that never trusts itself: every action leaves a receipt, every lesson is gated by evidence, and every future task is a line in a hook table.

This document describes a small, self-auditing personal ops system: a single AI agent (running on [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)) plus a handful of plain-text files and scheduled jobs, cooperating to run one person's daily automation — backups, monitoring, research, publishing, weekly reviews — without the agent silently drifting into fiction.

**The problem it solves.** A solo operator delegating work to an AI agent faces one recurring failure mode: the agent *says* it did something. Without an external ledger, "done" and "claimed done" are indistinguishable, and mistakes compound quietly across sessions. The conventional fixes — bigger prompts, more rules read at session start, fancier memory systems — all still live inside the agent's own context, where they can be ignored, forgotten, or hallucinated. This system moves the ground truth *outside* the agent, into files that are diff-able, greppable, and backed up like any other artifact of the operator.

**What you get from this document.** A copyable skeleton: seven files, a set of scheduling rules, a promotion flow for knowledge, and two verification mechanisms (an evidence gate and a multi-model review pipeline). Everything is plain text or JSONL. There is no product to install; the runtime is the only dependency.

**Explicit non-claims.** Nothing here guarantees correctness in your environment. No performance claims. No affiliation with, or endorsement by, any vendor — the named runtime is simply where this instance runs. The author's own numbers and outcomes are deliberately absent; the value is in the shapes, not the instances.

---

## 2. System Architecture Diagram — [A]

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
   │ single todo │ │ future  │ │ append-only  │ │ → rules.md   │ │ (N independent│
   │ authority   │ │ hooks   │ │ evidence     │ │ → MEMORY.md  │ │  reviewers)    │
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

---

## 3. Component Responsibilities

### 3.1 The Orchestrator: `launchd` — [A]

The scheduler is macOS `launchd`, used exactly as the platform intends: one LaunchAgent per concern, never one mega-script.

- **Jobs**: heartbeat (runs the smallest possible loop several times a day), monitoring fetch (hourly), daily backup, weekly audit/closeout, self-evolution review.
- **Shape of every job**: `ProgramArguments` points at a single shell script; stdout and stderr go to separate log files; the exit code is meaningful — non-zero is *surfaced to the receipt ledger*, not swallowed.
- **Idempotency rule**: every scheduled script must be safe to re-run with no side effects on re-entry. If a job cannot be made idempotent, it acquires a lock file and refuses to double-execute.
- Generic macOS tips only (keep-alive semantics, `caffeinate` for long batches) — no environment-specific plists are published here. **[B] for any plist with real usernames/paths; publish only `<placeholder>` versions.**

### 3.2 The Single Todo Source: `todo.md` — [A]

One file, one authority. Before the agent acts on any request, the task is registered there; when it completes, the line becomes `[x]` **plus a receipt reference**. The file has two sections: near-term (1–3 days) and horizon (everything else). The heartbeat re-reads it every cycle, so drift between sessions is bounded by the cycle length, not by the agent's memory.

Why a Markdown file instead of a task app: diff-able, backup-able, agent-editable, zero dependencies, and — critically — it is *outside* the agent's context window, so "I forgot what I promised" has a single auditable answer.

### 3.3 The Far-Future Hook Table: `hooks.md` — [A]

Four columns:

```text
| date       | trigger                 | action                    | status   |
|------------|-------------------------|---------------------------|----------|
| next Sun   | weekly review           | run audit step #N         | pending  |
| +7 days    | re-check observation    | verify candidate L<n>     | pending  |
```

Purpose: remember things across sessions — a "re-check in 7 days" note, a "verify tomorrow at 20:39" gate, a promised follow-up. The heartbeat scans the next seven days every cycle and surfaces due hooks as todo candidates. Generic example rows only.

### 3.4 The Receipt Ledger: `receipts.jsonl` — [A]

One JSONL line per completed action:

```json
{"ts": "<ISO-8601>", "action": "<verb + object, e.g. backup-verified>", "evidence": "<what was checked: hashes, counts, quoted results>"}
```

Rules: every side-effectful action writes a receipt; receipts record *evidence*, never feelings or promises; append-only (atomic append survives crashes); greppable and machine-checkable. **Real receipts are never published — only the schema above and synthetic examples. [B]→[A] once anonymized.**

### 3.5 The Three Knowledge Layers: Lessons → Rules → Memory — [A]

- **Lessons** (`lessons.jsonl`): numbered observations (`L1`, `L2`, …), each tied to an evidence pointer. A lesson is a *candidate* until proven.
- **Rules** (`operator-rules.md`): distilled operating law (`R1`, `R2`, …), promoted from lessons only after review. Rules carry precedence and revision history.
- **Memory** (`MEMORY.md`): the session spine — who the assistant is, what it manages, current snapshots. Read at the start of every session.

Promotion is one-directional and gated: *lesson → (review gate) → rule*. Memory records the *current* state, never claims about the future. Publish the shape and the flow — never the contents.

### 3.6 The Evidence Gate — [A] *(the heart of the document)*

Four negative principles define the system:

1. **Provider output is not truth.** Whatever the model says, however confident, is a claim until evidence exists.
2. **Local files are not canonical truth.** A file can be stale, corrupted, or written by a buggy script. It is evidence only after verification.
3. **Plans are not executions.** A plan is a todo line with no receipt.
4. **Candidates are not canonicals.** Multiple drafts of an idea are candidates until one earns a verified pointer.

Gate vocabulary (generic): `candidate / verified / disputed / superseded`. Verification requires a qualifying evidence pointer — a reproducible tool result, a hash comparison, an external source check — not an assertion.

The "cannot-claim" discipline: a claim without evidence is written as a candidate, or not written at all. This single rule, applied mechanically, eliminates the most common failure mode of agent assistants: confident fabrication that nobody notices until the backup is actually needed.

### 3.7 The Local Model Lane — [A]

Pattern: a small locally hosted model runs batch and offline jobs — extraction, first-pass classification, drafts, summaries of long transcripts. Its output is labeled `candidate_only` by construction and enters the same gate as everything else.

Lane assignment heuristic: **local for high-volume, low-stakes work; gated cloud calls for decisions; humans for irreversible actions.** The point is not "local is safer" — the gate treats all model output identically — but cost and volume separation: the cheap lane does the bulk, the expensive lane does the judgment, the human does the commitment.

*(Hardware specifics are intentionally omitted; generic description only. [B] if naming model/hardware combinations.)*

### 3.8 The Multi-Model Review Pipeline — [A]

Pattern: when a candidate artifact matters (a lesson, a rule, a growth claim), it is sent to N independent reviewers — different models, reached through independent channels — each returning a structured verdict:

```text
verdict ∈ { support | mixed | against | invalid }
optional: cannotClaim  (reviewer refuses to judge on provided evidence)
```

Results are `candidate_review_input` **only**. They can gate *review* — a claim that loses the review is downgraded — but they can never substitute for local evidence, and a unanimous `support` does not make anything true. The pipeline itself uses plain HTTP and no third-party SDK; every call is recorded in a usage ledger.

Publish the protocol and the verdict schema; never model accounts, endpoints, keys, or costs. *(Per operator decision, the approach — N independent reviews, structured verdicts, review-as-input-not-authority — is described without naming providers.)*

### 3.9 The Three-Machine Topology (role diagram only) — [B]

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


Three roles, three physical machines: `main` (agent home + primary storage), `aux` (second platform, used for cross-OS checks), `backup` (third physical copy).

Pattern: hourly handoff pulls between machines; backup freshness is verified by **sentinel comparison** — the tail hash of the latest receipt ledger is compared across copies — never by "the log said success".

**Publishing boundary (decided): publish only the role diagram and the sentinel-comparison idea. Machine identities, networks, and storage layouts stay internal. [X] for any real detail.**

---

## 4. Key Design Decisions — [A]

Each entry: what → why → trade-off → what was rejected.

1. **Markdown + JSONL files over databases.** *Why:* diff/grep/backup with zero daemons; the agent can read and write them with ordinary tools. *Trade-off:* no transactions, no rich queries. *Rejected:* a real database, a task app, a notes SaaS.
2. **Receipts for every side effect.** *Why:* auditability beats convenience; "no receipt" is a machine-checkable definition of "not done". *Trade-off:* discipline overhead on every action. *Rejected:* trusting the agent's verbal summary.
3. **One todo source + one hook table.** *Why:* removes "I forgot what I promised" as a failure class. *Trade-off:* two more files to keep consistent. *Rejected:* per-conversation task lists.
4. **Evidence-gated promotion (candidate → verified).** *Why:* the anti-hallucination mechanism; lessons become rules only after surviving review. *Trade-off:* slower knowledge accumulation. *Rejected:* auto-distilling anything the model finds interesting (volume over trust).
5. **Local lane for candidates, gated lanes for decisions.** *Why:* cost separation and clear labels. *Trade-off:* two model paths to maintain. *Rejected:* everything through one expensive endpoint.
6. **Multi-model review as input, never as authority.** *Why:* correlated errors exist inside any single model; independent reviewers catch over-claiming. *Trade-off:* review latency and token cost. *Rejected:* "the strongest model arbitrates".
7. **Scheduled idempotent scripts over long-running daemons.** *Why:* crash-safe, restart-safe, observable exit codes. *Trade-off:* coarser reactivity. *Rejected:* a resident process holding state.
8. **Backups verified by sentinels, not logs.** *Why:* logs record intent; a matching hash is one piece of evidence that a specific byte set is consistent. *Trade-off:* an extra comparison step. *Rejected:* "backup succeeded" as an exit code.

---

## 5. How to Replicate on Your Own Machine — [A]

Generic steps only; every path is a placeholder.

**Step 0 — prerequisites.** macOS with `launchctl`; a dedicated ops root directory under version control; the agent runtime of your choice with file access to that directory.

**Step 1 — the file skeleton.** Create six files: `todo.md`, `hooks.md`, `receipts.jsonl`, `lessons.jsonl`, `rules.md`, `MEMORY.md` (schemas in the appendix). Start `MEMORY.md` with the gate vocabulary — nothing else.

**Step 2 — three launchd jobs first.** Heartbeat (reads todo + hooks, writes a receipt), daily backup (copies the ops root, writes a receipt with file count + hash), weekly review (scans lessons, proposes promotions, writes a receipt). This is the smallest loop that produces receipts.

**Step 3 — adopt the gate vocabulary** before adding any further automation. Refuse to automate what you cannot audit.

**Step 4 — add hooks** only after the heartbeat reliably reads them for two weeks.

**Step 5 — add the local lane and the multi-model review** only after 2–4 weeks of stable receipts. Both are amplifiers; they amplify discipline or amplify drift depending on what came first.

Replication rule of thumb: every new component must *produce* a receipt before it is allowed to *consume* anything.

---

## 6. Common Pitfalls — [A]

Each with symptom → cause → fix.

1. **Agent says "done", no receipt exists.** → Evidence was never required. → Treat as not done; make the receipt rule mechanical.
2. **Scheduled job fails silently for weeks.** → Logs swallowed; exit codes ignored. → Separate `.log`/`.err.log`, non-zero exit → receipt entry, heartbeat greps for them.
3. **A follow-up promise forgotten between sessions.** → No single hook table. → `hooks.md` + 7-day scan.
4. **A lesson promoted to rule after one lucky run.** → Promotion gate too weak. → Require qualifying evidence + review before any promotion.
5. **Multi-model consensus treated as truth.** → Reviews misread as verdicts. → Reviews are candidate input only; truth requires local evidence.
6. **Backup "success" trusted from logs.** → Logs record intent, not fact. → Sentinel hash comparison across copies.
7. **Secrets leaking into published docs.** → No publishing boundary. → Every section carries a privacy gate; publish schema, never content.
8. **Non-idempotent script double-executes.** → No re-entry guard. → Idempotency rule from day one; lock files where it is impossible.

---

## 7. Privacy and Publishing Boundaries — [A]

| Section | Gate | Rule |
|---|---|---|
| 1–3.6, 4–8 (methodology core) | [A] | publish as-is; schemas and synthetic examples only |
| 3.7 local lane | [A] pattern / [B] specifics | generic description; no hardware/model naming without approval |
| 3.8 review pipeline | [A] | anonymous method description; no providers, accounts, endpoints, keys, or costs |
| 3.9 three-machine topology | [B] | role diagram + sentinel idea only; no identities/networks/layouts |
| real receipts, lessons, rules, memory | [X] | never published |
| screenshots of live environments | [B] | only after operator review |

Principles: publish **patterns, not instances**; redact hostnames, keys, tokens, real receipts, real lesson contents; the operator is the sole approver for anything beyond the methodology core. The document's value is the shapes — the honest claim is that the shapes work in one real deployment, and the reader is invited to verify that claim only as far as the published evidence allows.

---

## 8. Appendix: minimal file formats — [A]

Generic schemas only. All values are `<placeholders>`; examples are synthetic.

**`receipts.jsonl`** — one line per action:
```json
{"ts": "2026-08-20T09:00:00+08:00", "action": "daily-backup-verified", "evidence": "sha256 <hash>, 17384 files, sentinel match on backup host"}
<!-- Future direction: receipts may add structured fields (executor, scope, exit code, before/after snapshots); plain evidence text is the current minimum. -->
```

**`lessons.jsonl`** — one line per lesson:
```json
{"id": "L<NN>", "ts": "<ISO-8601>", "claim": "<what happened>", "evidence": "<pointer: session range / reproduced result / external check>", "status": "candidate | verified | disputed | superseded"}
```

**`rules.md`** — rule block header:
```text
# R<n> — <title>
## 状态: <生效日期> · 修订 <n> · 来源 lesson L<m>(经评审)
## 规则: <一条可执行约束>
## 翻转条件: <什么证据出现则本规则失效>
```

**`hooks.md`** — columns: `date | trigger | action | status` (see 3.3).

**`todo.md`** — sections `## near-term` / `## horizon`; completed lines carry `[x]` and a receipt reference.

**`MEMORY.md`** — skeleton: identity (who the assistant is), scope (what it manages), gate vocabulary (the four negative principles), current snapshots (pointers only, updated with receipts).

---

*Draft v0.4 · 2026-08-21 · methodology only. No personal data, keys, or private paths appear in this document. [B] sections are published strictly in the redacted form decided by the operator; [X] content exists nowhere in this text.*

### 3.10 Evidence & Verification Posture — [A]

This document is a **methodology description**, not an audit log: it shows shapes, schemas, and design rationale. The running deployment behind it keeps quantitative evidence (receipt counts, job success rates, failure drills) in its private ledger; the public copy publishes only anonymized schemas, per the [B]/[X] gates. Where the text says a shape "works in one real deployment", that claim rests on that private ledger and on the external review chain below — not on this document alone.

**Who verifies receipts beyond the agent that wrote them?** The system is deliberately not self-certifying: (1) a weekly ceremony re-audits the five growth metrics against the ledger; (2) a multi-model review pipeline reads lessons/rules and its output is treated only as candidate review input; (3) an independent model (Codex) audits the operator's own reports; (4) the human owner spot-checks. A lying agent would have to fool all four, and each check is itself logged.

**Failure degradation:** if a receipt cannot be written, the task is marked failed (fail-closed) rather than silently succeeding; automation surfaces the failure in the next heartbeat.

