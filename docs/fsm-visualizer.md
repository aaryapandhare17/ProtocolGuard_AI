# FSM visualizer and recorded-session replay

Open **FSM visualizer** in the administrator dashboard. The page reads the verified backend
DFA definition and recorded banking sessions; it does not run a second detector in JavaScript.
The separate [formal DFA documentation](fsm.md) explains the protocol and acceptance rules.

## Explore the graph

React Flow renders all eight backend states, with LOGGED_OUT highlighted initially and CLOSED
marked as accepting. Explicit protocol rules are grouped by source/target pair. A `+N` label
indicates additional event symbols on that edge; hovering shows the complete event list.
Self-transitions have loop paths. Pan, zoom, and Fit View allow inspection on smaller screens.

By default the graph emphasizes banking actions. **Show enforcement edges** adds explicit
BLOCK_ACCOUNT/ACCESS_BLOCKED routes to BLOCKED. Undefined pairs are summarized as default
rejection rather than drawing every rejecting edge at once. When replay selects an invalid
transition, that specific route to REJECTED appears in red with its triggering event.

The current state and valid transition are blue; rejected evidence is red. BLOCKED is an
explicit enforced restriction, not necessarily an undefined transition. The accepting state
has a separate outline. Labels, legend, checkpoint cards and the transition table retain
textual context so color is not the only indication of meaning.

## Replay actual evidence

Choose a session by account name, opaque session reference, latest state and timestamp.
The session list shows up to 100 recorded banking traces. Administrator authentication traces
are excluded. The user-detail page also links directly to its latest supported banking session.
A URL such as `/fsm?session=...` restores the selected recording.

Controls operate entirely on the downloaded recording:

- **Play/Pause:** advance at the selected interval; playback stops at the last event.
  Playing from the end restarts at the initial checkpoint.
- **Previous/Next:** step exactly one persisted transition and stop playback.
- **Reset:** return to the trace's recorded initial state.
- **Checkpoint slider:** seek directly through the trace; zero means before the first event.
- **Table step buttons:** select the prefix ending at a particular event.
- **Speed:** 0.4, 0.8 or 1.5 seconds per event.

The checkpoint card reports only violations seen so far. A valid prefix is not labeled a
complete session; CLOSED is accepted only when the analyzed prefix has no prior violations.
A separate card shows the backend's final recorded classification. The active event and
violation explanation stay visible alongside the highlighted history row.

Recorded timestamps, before/after states, event symbols, validity and explanations come from
the backend replay response. They are not generated for the graph. A recorded post-logout
request can therefore show an accepted CLOSED prefix followed by a final rejected state.

## Snapshots, partial history, and safety

Selecting or explicitly refreshing a trace takes a new snapshot. Live session-list updates
do not replace a trace halfway through replay. Refreshing or switching sessions stops play
and returns to checkpoint zero. Obsolete fetches and playback timers are canceled.

Legacy traces whose original prefix is missing retain their stored initial state and show a
partial-history warning. Any acceptance applies only to available evidence; the browser does
not invent login events or reconstruct missing transitions. Missing/invalid session references
show the backend error. An empty session list still allows exploration of the actual DFA.

Replay makes only authenticated read requests to the existing FSM APIs. It cannot submit
banking events, modify risk, revoke sessions, block accounts or change history. Authentication
and enforcement remain backend responsibilities. Both graph code and React Flow styling are
loaded lazily with this page, leaving unrelated dashboard routes separate.

## Verification

Automated checks cover prefix/completion distinction, rejecting/blocked semantics, grouped
explicit edges, selected default rejection, partial-history messaging, stepping, seeking,
reset, play/pause timing, end-state controls and read-only request behavior. Existing backend
FSM/replay and admin authorization tests run against the session-list username addition.

A Chromium workflow used real accepted and rejected recordings to verify all graph states,
playback/seek controls, the red rejection route, enforcement-edge toggle, user-detail deep links,
trace refresh and mobile Fit View. The newest persisted event ID remained unchanged throughout
replay, confirming that interacting with the visualizer created no security events.
