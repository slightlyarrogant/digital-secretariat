# Digital Secretariat - submission

## Inspiration

We did not start with a hypothetical productivity problem. We found the problem inside our own
AI-operated company.

A partially working legacy module could continue a long conversation with a potential client while
the rest of the company had no reliable view of that exchange. Deadlines could be agreed in email
without becoming operational deadlines. Different processes could propose terms based on different
context. A message could create a real expectation for the client without creating an owner,
obligation, or next action inside the company.

That led to our central insight: the most important interface in an AI-operated company is not the
model. It is the boundary between the company and its clients. As AI increases the number and speed
of actions, that boundary needs stronger controls, not just a smarter inbox.

## What it does

Digital Secretariat is a communication control plane for AI-operated companies. It provides one
private workspace showing what clients sent, what the company plans to send, what was approved, what
the controlled gateway actually accepted, and which promises now need an owner and deadline.

An owner can read incoming email without leaving the operational board, prepare or edit a short
reply, and explicitly approve or reject a draft. Outbound messages pass through one canonical mail
rail. Revision checks prevent approval of text that changed after review, and a newer incoming
message can block a stale response. A message counts as sent only when the append-only send log
contains matching evidence from the canonical rail.

The same workspace connects communication with cases, obligations, deadlines, response quality,
delivery failures, template usage, and outreach results. It is available on a laptop or phone through
a private Tailscale network rather than a public login page.

GPT-5.6 helps interpret incoming communication, classify intent, identify missing context, and
prepare concise responses from approved company knowledge and templates. The model produces a
proposal; it does not receive the authority to send mail or rewrite operational truth.

## How we built it

We extracted Digital Secretariat from a working company system and turned it into an independent,
tested reference product. The control plane uses FastAPI and PostgreSQL. A separate read-only cache
process retrieves message content, while the web process never receives the IMAP credential. The
application runs as hardened systemd services, binds to localhost, and is exposed privately through
Tailscale Serve.

We designed outbound communication as a narrow command boundary rather than a general database or
SMTP integration. The browser cannot choose the sender address, recipient, threading headers, or
company identity. Deterministic code validates every proposal before the canonical rail can release
it.

We used Codex as an engineering partner throughout the build. Codex inspected the existing system,
followed failures across the interface, database, mail rail, authentication proxy, and deployment,
then helped us extract the reusable architecture without copying customer data or secrets. It also
implemented and ran focused tests, documented the security invariants, prepared the standalone
repository, and created a contract for an AI-guided installer that diagnoses problems instead of
silently guessing.

We used GPT-5.6 for the reasoning work around unstructured client communication: understanding
intent, locating missing facts, and drafting an appropriate proposed response. Its output remains
untrusted until deterministic validation and human approval are complete.

## Challenges we ran into

The hardest challenge was not generating email text. It was discovering and enforcing the real
organizational boundaries. Years of customized processes had different database assumptions,
different ways to identify a client, and more than one possible route to external communication.
Turning that into one product required explicit adapters and fail-closed behavior whenever data was
missing or ambiguous.

Authentication also required care. Tailscale provides the private network identity, but forwarded
identity headers are trustworthy only when they arrive from the configured local proxy. Approval
actions needed signed, expiring intent tokens, revision checks, and useful conflict states rather
than a button that merely appeared secure.

Prompt injection created a second boundary problem. Incoming email, attachments, OCR results,
websites, and model output all have to be treated as untrusted data. We kept GPT-5.6 away from SMTP,
database write credentials, the shell, and the secret store. The model can create a typed proposal;
deterministic code and a human decide whether it becomes an action.

Finally, extracting a reusable product from a live, customized system meant separating genuine
product capabilities from organization-specific joins, Polish interface text, production secrets,
and historical assumptions. We chose to document remaining gaps instead of hiding them behind a
demo.

## Accomplishments that we're proud of

We built a working approval and send rail rather than a visual prototype. An owner can inspect the
source message, edit the response, approve the exact revision, and see audited send evidence in one
workflow. Missing context, stale drafts, unauthorized identities, and unavailable send evidence fail
closed.

We are also proud that the security model consists of technical walls, not instructions asking a
model to behave. The AI layer cannot directly send external email, choose trusted addressing data,
or write arbitrary operational state.

The standalone distribution includes least-privilege database roles, additive migrations, hardened
service definitions, an atomic deployer with rollback, preflight and verification scripts, an
AI-led installation contract, and focused automated tests. This makes the project a credible base
for deployment, not only a hackathon recording.

Most importantly, we turned painful incidents into explicit invariants: no invisible revision, no
guessed recipient, no assumed delivery, and no external action without controlled authority.

## What we learned

AI does not remove organizational coordination problems. It accelerates them. A company can only
operate safely with multiple agents when they share the same evidence about clients, decisions,
promises, and deadlines.

We learned that “sent” must mean evidence from the canonical rail, not an agent's intention. A
promise in an email must become an owned operational object, not remain buried in a thread.
Prompt-injection defense must be based on capabilities and data flow, not solely on a stronger
system prompt.

We also learned that AI is valuable outside the runtime product. Codex could investigate an
installation failure, explain the problem, apply an approved repair, rerun verification, and keep an
append-only installation record. That is much more useful to a small company than an installer that
stops at the first unexpected dependency.

## What's next for Digital Secretariat

The next milestone is completing the English-only product interface and packaging the reference
distribution for repeatable pilots in small companies. We will add a versioned adapter SDK so a new
installation can map its mailboxes, client registry, obligations, and delivery gateway without
modifying the core product.

We also plan to connect additional client channels, introduce reviewed extraction of promises and
deadlines, expand company-specific policy controls, and make every commitment-bearing workflow
create an owned obligation. Network-level egress controls will help prevent retired processes from
bypassing the canonical communication rail.

The AI-guided installer will evolve into a migration and support agent with explicit approvals,
sanitized logs, compatibility checks, rollback, and reproducible verification. The long-term goal is
simple: let small companies scale their use of AI without scaling accidental communication,
invisible commitments, or fragmented client relationships.
