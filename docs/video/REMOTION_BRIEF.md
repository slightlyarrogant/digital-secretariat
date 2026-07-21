# Remotion product-film brief

## Language requirement

The entire film must be in English. This includes the title, product UI, demo data, email examples,
on-screen text, voiceover, captions, subtitles, filename, description, thumbnail, and call to action.
Non-English customer content must not appear in the master product film. This requirement follows
`docs/LANGUAGE_POLICY.md` and blocks release when violated.

## Working title

**Digital Secretariat — The Client Interface for AI-Operated Companies**

Closing line: **One company. One client interface. No invisible promises.**

## Objective

Create an 80-second English product film about the highest-risk boundary in an AI-operated company:
communication with clients. Multiple agents, legacy jobs, inbox automations, and half-retired modules
can each speak for the company while operating on different state. The result is not merely inbox
clutter. It is conflicting promises, accidental mail, deadlines the company cannot see, and client
obligations nobody owns.

The film must show how Digital Secretariat establishes one observable client interface: inbound
communication is registered with context, outbound mail passes through a canonical approval and
delivery rail, and commitments become shared operational state instead of remaining hidden inside a
thread.

## Positioning

**Digital Secretariat is the communication control plane for an AI-operated company. It gives every
agent and operator one shared account of what the company received, what it promised, what requires
a decision, and what was actually sent.**

This is stronger than “a better inbox” and more credible than “an autonomous office.” The product
does not promise that AI cannot make a mistake. It provides enforceable boundaries, human decision
gates, shared state, and evidence so mistakes do not silently become the company's external truth.

## Claims boundary

Show implemented evidence: inline inbound content, controlled drafts, human approval, revision and
freshness checks, canonical SMTP release, send-log evidence, cases/obligations, measurements, and
private owner access. Do not imply that every legacy channel is already intercepted or that every
promise is extracted automatically. Phrase this as the operating model the company adopts and the
control plane the product makes possible.

AI-led installation belongs in a separate technical walkthrough. It must not compete with the core
sales message in this film.

## Format

- Master: 1920x1080, 30 fps, 80 seconds, H.264 MP4.
- Safe crop: keep critical UI inside a centered 1080x1080 area for a later 9:16 cut.
- Audio: English voiceover, restrained percussive bed, UI sounds below narration.
- Captions: burned-in English captions, maximum two lines, phrase-level timing.
- Demo data: English only, deterministic, fictional, and under `example.com`.

Remotion can create parameterized React compositions, preview them in Studio, and render MP4 with
audio. Start with `npx create-video@latest video` and verify current licensing terms before
commercial production: <https://www.remotion.dev/>.

## Visual direction

- Operational product film, not a generic AI commercial.
- Open with real-looking conflicting communication paths, not abstract notification bubbles.
- Paper-white workspace, near-black navigation, warm yellow attention, teal confirmed action, red
  reserved for an actual conflict or failed control.
- Use readable captures of the real UI. Reframe captures instead of blurring them.
- Motion must express causality: hidden send, conflicting promise, registered inbound, approval,
  delivery evidence, owned obligation, shared company state.
- Avoid decorative gradients, floating cards, stock-office footage, green-on-black terminals,
  glowing AI particles, humanoid robots, and claims presented as fake customer quotes.
- All visible product-owned strings and titles must be English.

## Remotion structure

Use one composition `ProductFilmEN` with `fps=30`, `durationInFrames=2400`, width `1920`, height
`1080`. Keep scene timings and text in `scenes.ts`; no product copy may be embedded in animation
components.

```text
video/src/
  Root.tsx
  ProductFilmEN.tsx
  scenes.ts
  components/
    CommunicationPaths.tsx
    ProductCapture.tsx
    FocusFrame.tsx
    ApprovalRail.tsx
    CommitmentState.tsx
    Captions.tsx
  data/captions.en.json
video/public/
  captures/       sanitized English 60 fps screen recordings
  audio/voiceover-en.wav
  audio/music.wav
  brand/
```

Use `Sequence` or `Series.Sequence` for scenes and `Audio` for narration/music. Use spring and
interpolate only for focus transitions. Never accelerate UI footage beyond legibility.

## Scene timeline

| Time | Frames | Picture | On-screen text |
|---|---:|---|---|
| 0-8 s | 0-239 | Three real-looking company processes operate in parallel: a legacy job sends a promise, an agent drafts different terms, and the owner sees neither. The same fictional client and thread make the conflict obvious. | `Three systems can speak as one company.` |
| 8-18 s | 240-539 | Reveal the consequences inside one English thread: fourteen messages, “delivery by Friday,” a missed date, and no matching case. Do not dramatize with stock footage. | `The client heard a promise.` / `The company did not record it.` |
| 18-29 s | 540-869 | The parallel paths collapse into one product workspace. Product name is the first dominant title. | `Digital Secretariat` / `The client interface for AI-operated companies` |
| 29-42 s | 870-1259 | Open the inbound message inline. Show sender, receiving mailbox, content, attachments, relationship, and existing company state without leaving the workspace. | `Every inbound message becomes shared context.` |
| 42-55 s | 1260-1649 | Write a short English response with an explicit date. Show the human approval, revision/freshness gate, canonical release, and matching send-log evidence. | `No accidental send.` / `No invisible revision.` / `Delivery requires evidence.` |
| 55-66 s | 1650-1979 | Move the visible promise into Cases: owner, deadline, next action, and source message. Show that the whole company can see what it now owes the client. Use an implemented or clearly labelled proposal flow. | `A promise becomes an owned obligation.` |
| 66-74 s | 1980-2219 | Show the same shared state driving response-time, delivery, bounce, template-use, and outreach measurements. Briefly show private laptop/phone access as a supporting fact. | `One shared operational truth.` |
| 74-80 s | 2220-2399 | Return to the calm workspace with one deliberate decision. End on the product name and closing line. | `Digital Secretariat` / `One company. One client interface. No invisible promises.` |

## Capture requirements

Record with Playwright against deterministic English fixtures at 1440x900 and 390x844. Create
separate takes. Hide browser chrome unless private access is the subject. Use only fictional English
names and `example.com` addresses. Scrub IDs, hostnames, tailnet names, notifications, logs, and any
legacy Polish interface strings before committing an asset.

Required takes:

1. `parallel-client-conflict.webm`: rehearsed fictional conflict between two send paths.
2. `inbox-expand-en.webm`: English inbound row expands in place.
3. `reply-approve-en.webm`: explicit date, approval, and freshness/revision control.
4. `sent-evidence-en.webm`: sent state linked to send-log evidence.
5. `commitment-owned-en.webm`: source-linked case with owner, deadline, and next action.
6. `performance-en.webm`: communication and outreach trends derived from shared state.
7. `mobile-private-en.webm`: the same decision on the English mobile UI.

## Audio and captions

Record the English voiceover dry at 48 kHz/24 bit, close-mic, neutral international delivery around
145-155 words per minute. Leave 150-250 ms between phrases. Duck music by 10-14 dB under speech.
Captions follow phrases, not word-by-word karaoke. Do not capitalize every word in titles.

## Render and QA

```bash
cd video
npm install
npm run start
npx remotion render ProductFilmEN out/digital-secretariat-client-interface-en.mp4 \
  --codec=h264 --crf=18 --audio-codec=aac
```

QA at 100% scale and on an actual phone. Reject the render when any product-owned string, title,
caption, voiceover line, metadata value, or thumbnail text is not English. Also check UI legibility,
caption safe areas, audio sync, private data, blank frames, layout shifts, and unsupported claims.
Render a silent proof and a voiceover-only proof before the final mix.
