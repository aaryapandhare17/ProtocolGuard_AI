# Banking-session finite-state machine

## Purpose and formal definition

The DFA describes the order of banking-session actions. It can flag a balance request
before login or a second transfer request while another request is pending. It cannot
infer intent from every legal sequence: repeated failed logins, for example, are valid
protocol behavior but can still be abusive. Frequency indicators and ML will handle
that evidence in later features.

Formally, **M = (Q, Σ, δ, q₀, F)**:

- **Q** = {LOGGED_OUT, AUTHENTICATING, AUTHENTICATED, VIEWING_ACCOUNT,
  TRANSFER_PENDING, CLOSED, BLOCKED, REJECTED}.
- **Σ** = {LOGIN_ATTEMPT, LOGIN_SUCCESS, LOGIN_FAILED, VIEW_BALANCE, VIEW_HISTORY,
  TRANSFER_REQUEST, TRANSFER_RECORDED, RETURN, CANCEL_TRANSFER, LOGOUT,
  UNAUTHORIZED_REQUEST, RATE_LIMIT_TRIGGERED, ACCESS_BLOCKED, BLOCK_ACCOUNT}.
- **δ** is the deterministic transition function in the table below. Every unspecified
  state/event pair goes to REJECTED. REJECTED is an absorbing sink.
- **q₀** = LOGGED_OUT.
- **F** = {CLOSED}.

CLOSED is a separate state so an empty trace or a failed login is never mistaken for
a completed banking session. The version identifier is `bank-session-v1`.

## Transition table

Each slash-separated alternative represents its own explicit transition.

| Current state | Event | Next state |
| --- | --- | --- |
| LOGGED_OUT | LOGIN_ATTEMPT | AUTHENTICATING |
| AUTHENTICATING | LOGIN_SUCCESS | AUTHENTICATED |
| AUTHENTICATING | LOGIN_FAILED | LOGGED_OUT |
| AUTHENTICATED / VIEWING_ACCOUNT | VIEW_BALANCE / VIEW_HISTORY | VIEWING_ACCOUNT |
| AUTHENTICATED / VIEWING_ACCOUNT | TRANSFER_REQUEST | TRANSFER_PENDING |
| VIEWING_ACCOUNT | RETURN | AUTHENTICATED |
| TRANSFER_PENDING | TRANSFER_RECORDED / CANCEL_TRANSFER | AUTHENTICATED |
| AUTHENTICATED / VIEWING_ACCOUNT / TRANSFER_PENDING | LOGOUT | CLOSED |
| Any state except CLOSED / REJECTED | BLOCK_ACCOUNT / ACCESS_BLOCKED | BLOCKED |
| Any unspecified pair, including all events from CLOSED / REJECTED | Any event in Σ | REJECTED |

`TRANSFER_RECORDED` means that the backend recorded a simulated request; no financial
transaction occurred. It follows TRANSFER_REQUEST in the same database transaction.
This lets another legitimate transfer request start afterward. RETURN and CANCEL_TRANSFER
are supported by the engine for later simulation/replay, but have no public banking endpoint.
BLOCK_ACCOUNT is reserved for the later blocking feature; no automatic blocking is added here.
Events outside Σ are reported as invalid input and rejected by the pure analysis engine as well.

## Prefixes, accepted sessions, and suspicious traces

A **valid prefix** is a trace that can still become a complete accepted session without
violations. Examples are an empty trace, LOGIN_ATTEMPT, or
LOGIN_ATTEMPT → LOGIN_SUCCESS → VIEW_BALANCE. None is accepted yet.

A **complete accepted session** reaches CLOSED, for example:

```text
LOGGED_OUT --LOGIN_ATTEMPT--> AUTHENTICATING
           --LOGIN_SUCCESS--> AUTHENTICATED
           --VIEW_BALANCE--> VIEWING_ACCOUNT
           --VIEW_HISTORY--> VIEWING_ACCOUNT
           --TRANSFER_REQUEST--> TRANSFER_PENDING
           --TRANSFER_RECORDED--> AUTHENTICATED
           --LOGOUT--> CLOSED
```

A **suspicious trace** includes an undefined transition or reaches BLOCKED. For example,
LOGGED_OUT + VIEW_BALANCE enters REJECTED with an explanation. Every subsequent event
stays rejected, preserving the original violation. The invalid-transition count includes
each rejected subsequent event, not just the first error. An enforced BLOCKED trace can
be suspicious without containing an undefined transition.

The `accepted` field describes protocol acceptance, not a security guarantee.
A valid failed-login trace remains a prefix; it does not mean failed-login bursts are safe.
Timestamps and request frequencies do not change DFA acceptance.

## Event persistence and authorization

`services/events.py` processes the event and updates the session state in the caller's
transaction. Each security event stores initial/final transition states and versioned
JSON evidence containing its event, validity, and violation explanation. The event log
retains every transition rather than overwriting previous evidence.

Login attempts now have their own session record before password verification. Failed
attempts are immediately revoked and never receive a session cookie. Their attempt and
failure events can therefore be replayed together. Each successful login gets an independent
session, including when the same account signs in in two browsers. Admin events have
`scope: admin` and are excluded from the banking DFA. Unauthorized requests without a
recognized session get an individual LOGGED_OUT → REJECTED event; they are not invented
as a shared user session.

SQLite transactions use BEGIN IMMEDIATE to serialize read/modify/write operations.
Concurrent banking requests cannot overwrite each other's transition state. Failed
requests still commit their security evidence through the existing database dependency.

Authentication continues to verify the session, expiry, revocation, role, account status,
and CSRF token independently. A DFA state can neither grant access nor replace these
checks. A detected protocol violation currently records evidence; risk scoring and
automatic blocking will be added later.

## Administrator API

These read-only routes require a verified administrator cookie:

- `GET /api/admin/fsm`: formal definition and all 112 state/event pairs, with a flag
  indicating explicit transitions versus default rejection.
- `GET /api/admin/fsm/sessions`: the latest 100 sessions with supported banking evidence.
- `GET /api/admin/fsm/sessions/{session_id}`: replayed states, events, violations,
  classification, and persisted evidence with timestamps and event IDs.

Session identifiers in the API are stored one-way token digests, never raw cookie values.
Bank users and unauthenticated callers cannot access these APIs. Use the existing
`POST /api/admin/auth/login` in `/docs` with the provisioned admin credentials first;
Swagger's browser receives the session cookie. Then call the read-only routes above.
The React Flow admin visualizer will be implemented in its later planned feature.

No schema change or database reset is needed. Previous records without versioned FSM
evidence are preserved and excluded from replay. A trace with a missing historical prefix
has `complete_trace: false`; any acceptance refers only to the analyzed suffix. Sessions
without supported evidence are not listed, and replay returns 404 for them.

## Checks and viva questions

Run `python -m pytest backend/tests/test_fsm.py` with the backend environment activated.
Tests cover accepted sessions, valid prefixes, unknown/invalid events, sink behavior,
blocked state semantics, the complete transition function, persisted replay, failed requests,
admin isolation, multiple sessions on a shared IP, concurrent requests, old records,
and database reopen.

**Why is this a DFA?** Each state/event pair has exactly one next state, including an
explicit default to the rejecting sink.

**Why not use the DFA as authentication?** The DFA only models observed event order.
Possessing a state name proves nothing about a password, session cookie, or user role.

**Why are repeated balance/history actions allowed?** Refreshes and normal browsing
repeat these actions. Their frequency may be suspicious even though their order is valid.

**Why does logout reach CLOSED?** It distinguishes a completed authenticated session
from an empty trace or unsuccessful login, both of which end at LOGGED_OUT.

**Can a legal sequence be an attack?** Yes. The DFA contributes protocol evidence;
behavioral indicators and the planned ML detectors add other evidence.
