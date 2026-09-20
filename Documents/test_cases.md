# Test Cases

Rerun after any change to the prompt, schema, tools, or model. Record the result in **Last result**.

## 1. Comments by agent on specific dates
- **Question:** Tickets assigned to Bassam, which did he comment on on 2026-09-14 and 2026-09-15?
- **Failure:** Fetched all his tickets with full text (~273k chars), then Bedrock `ModelErrorException`.
- **Fix:** size guard, Bedrock retry, `no_comment_author` rule.
- **Expected:** One query on `freshdesk_conversations` with a date filter (`incoming=0`). States that no author column exists, so this means replies on tickets currently assigned to Bassam.
- **Last result:** ⬜

## 2. Escalated to R&D count
- **Question:** Number of tickets currently escalated to R&D.
- **Failure:** `internal_status` values used in the `status` filter, so only one condition matched.
- **Fix:** `internal_status` column meaning, `valid_values`, `escalated_to_rd` rule.
- **Expected:** Active AND (`status = 'On-Hold (Escalated)'` OR `internal_status` IN (Development In Progress, Escalation Complete, Development Deferred)).
- **Last result:** ⬜

## 3a. Last week's ticket count
- **Question:** How many tickets were reported last week?
- **Failure:** Added an unstated `status != Resolved/Closed` filter and used fragile date modifiers.
- **Fix:** injected date ranges, "only stated filters" rule.
- **Expected:** Count with `created_at >= last Monday AND < this Monday`, no status filter.
- **Last result:** ⬜

## 3b. Priority review of last week's tickets
- **Question:** Read descriptions, titles, and comments; which tickets are under-prioritized?
- **Failure:** Claimed it analyzed conversations but only queried tickets (~150k chars).
- **Fix:** size guard, "never claim unretrieved analysis" rule.
- **Expected:** Does not overclaim. Either reviews a bounded set with comments, or says what it could and couldn't check.
- **Last result:** ⬜

## 3c. Same review, including all comments
- **Question:** Did you check the comments for all tickets?
- **Failure:** Ticket-conversation JOIN returned ~1.9M chars, so input token limit exceeded.
- **Fix:** `_shrink_rows` size cap, `truncated` flag.
- **Expected:** No crash. Truncation stated, or batched by ticket.
- **Last result:** ⬜

## 4a. Open tickets for an agent
- **Question:** Tickets in Open status assigned to Youssef.
- **Failure:** Model printed the tool definition as its answer (Nova Lite).
- **Fix:** switched to Haiku 4.5, temperature 0, tool-spec-as-text retry.
- **Expected:** Correct list of Open tickets via a normal tool call.
- **Last result:** ⬜

## 4b. Last comment per ticket
- **Question:** Each of those tickets with the last comment added.
- **Failure:** Fetched all conversations and picked the latest itself. Named the assignee as author when another agent wrote the comment.
- **Fix:** canonical `last_comment` SQL, prompt line removed, `no_comment_author` rule.
- **Expected:** One query using the `MAX(created_at)` subquery, any comment by default. No author named unless the body is signed.
- **Last result:** ⬜

## 5. Active tickets, last comment, last 10 days
- **Question:** Last comment for all active tickets assigned to Youssef in the last 10 days.
- **Expected:** `status NOT IN ('Resolved','Closed')`, `created_at` in the range, `MAX(created_at)` pattern, 10-day range computed correctly.
- **Last result:** ✅ SQL correct (Haiku 4.5). Answer not yet reviewed.

## Guardrail tests
- `WITH x AS (SELECT 1) DELETE FROM freshdesk_tickets` → BLOCKED (read-only). ✅
- `SELECT 1; DELETE FROM freshdesk_tickets` → BLOCKED (one statement only). ✅
- `... WHERE subject LIKE '%update%'` → runs. ✅