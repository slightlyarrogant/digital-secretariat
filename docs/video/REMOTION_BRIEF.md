# Remotion product-film brief

## Objective

Create an 80-second Polish product film that shows one transformation: operational noise becomes a
short, evidence-backed decision queue. The film must demonstrate the real product, not describe a
future autonomous assistant.

Primary audience: owners of Polish small service companies with growing email, documents, clients,
and deadlines. Secondary audience: technical evaluators who care about auditability and private
deployment.

## Core proposition

**Cyfrowy Sekretariat pokazuje właścicielowi, co wymaga decyzji, daje dowód i wykonuje zatwierdzone
działanie przez kontrolowaną szynę.**

Do not claim that AI replaces the office, answers every message, or installs without supervision.
The differentiator is disciplined operations: one attention queue, inline evidence, human approval,
measured outcomes, private access, and an installation agent that diagnoses rather than guesses.

## Format

- Master: 1920x1080, 30 fps, 80 seconds, H.264 MP4.
- Safe crop: keep critical UI inside a centered 1080x1080 area for later 9:16 adaptation.
- Audio: Polish voiceover, restrained percussive bed, UI sounds below narration.
- Captions: burned-in Polish captions, maximum two lines, phrase-level timing.
- No customer data. Record a deterministic demo dataset with fictional names and domains.

Remotion can create parameterized React compositions, preview them in Studio, and render MP4 with
audio. Start with `npx create-video@latest video` and verify the current licensing terms before
commercial production: <https://www.remotion.dev/>.

## Visual direction

- Quiet operational product film, not a startup landing-page animation.
- Paper-white workspace, near-black navigation, warm yellow attention signal, teal confirmed action,
  red reserved for real failure.
- Use the actual UI at readable scale. Zoom by reframing the capture, not by blurring the background.
- Motion is functional: row expansion, focus movement, decision state, chart reveal, device handoff.
- Avoid decorative gradients, floating cards, fake terminal code, green-on-black hacker imagery,
  stock-office footage, bokeh, and generic AI particles.
- Typography: Inter or the product font, normal letter spacing, sentence case.

## Remotion structure

Use one composition `ProductFilmPL` with `fps=30`, `durationInFrames=2400`, width `1920`, height
`1080`. Keep all timings in a `scenes.ts` data file so the edit can move without changing component
logic.

```text
video/src/
  Root.tsx
  ProductFilmPL.tsx
  scenes.ts
  components/
    ProductCapture.tsx
    FocusFrame.tsx
    MetricChart.tsx
    DeviceHandoff.tsx
    InstallLog.tsx
    Captions.tsx
  data/captions.pl.json
video/public/
  captures/       sanitized 60 fps screen recordings
  audio/voiceover-pl.wav
  audio/music.wav
  brand/
```

Use `Sequence` or `Series.Sequence` for scenes, `Audio` for narration/music, and spring/interpolate
only for short focus transitions. Freeze the last clean frame of each screen recording when timing
needs extension. Do not speed UI footage beyond legibility.

## Scene timeline

| Time | Frames | Picture | On-screen text |
|---|---:|---|---|
| 0-6 s | 0-179 | Fast but readable cuts: inbox count, calendar collision, invoice, unanswered lead. End on product name over the real workspace. | `Cyfrowy Sekretariat` |
| 6-14 s | 180-419 | Today view contracts many records into three ranked exceptions. Cursor does not wander. | `Dziś: 3 decyzje` |
| 14-25 s | 420-749 | Open one inbound mail inline. Show sender, mailbox, short preview, then full text without navigation. | `Treść i kontekst w jednym miejscu` |
| 25-36 s | 750-1079 | Write a two-sentence reply, click approve/send, show pending state then audited sent state. Briefly reveal revision/freshness protection. | `Człowiek zatwierdza` / `Szyna zapisuje dowód` |
| 36-46 s | 1080-1379 | Performance view: response-time trend, automatic/template share, delivery/bounce, outreach funnel. Animate only the data reveal. | `Nie tylko liczby. Trend i wynik.` |
| 46-56 s | 1380-1679 | Desktop view hands off to phone view through a simple spatial match cut. Tailscale service name and lock icon remain secondary. | `Prywatnie. Laptop i telefon.` |
| 56-68 s | 1680-2039 | Installation log: preflight detects missing Python 3.11 package, agent diagnoses, applies approved fix, reruns check, appends evidence. No secret values. | `Instalacja prowadzona przez AI` / `Diagnoza, zgoda, dowód` |
| 68-80 s | 2040-2399 | Return to calm Today view: zero hidden chaos, two deliberate decisions. Product name and literal offer close the film. | `Cyfrowy Sekretariat` / `Porządek, dowody, decyzje.` |

## Capture requirements

Record the application with Playwright against deterministic fixtures at 1440x900 and 390x844.
Create separate takes rather than one long mouse recording. Hide browser chrome unless the private
Tailscale URL is the subject of the shot. Use fictional addresses under `example.com`; scrub logs,
IDs, hostnames, tailnet names, and notifications before committing assets.

Required takes:

1. `today-ranked.webm`: Today view and three exceptions.
2. `inbox-expand.webm`: inbound row expands in place.
3. `reply-approve.webm`: type short response and approve.
4. `sent-evidence.webm`: sent status and matching audit evidence.
5. `performance.webm`: modern charts with at least two comparison periods.
6. `mobile-handoff.webm`: same state on phone viewport.
7. `installer-log.webm`: sanitized terminal/log UI with a real, rehearsed dependency recovery.

## Audio and captions

Record voiceover dry at 48 kHz/24 bit, close-mic, neutral Polish delivery around 145-155 words per
minute. Leave 150-250 ms between phrases. Duck music by 10-14 dB under speech. Captions should follow
spoken phrases rather than word-by-word karaoke; highlight at most one operational noun per phrase.

## Render and QA

```bash
cd video
npm install
npm run start
npx remotion render ProductFilmPL out/digital-secretariat-pl.mp4 \
  --codec=h264 --crf=18 --audio-codec=aac
```

QA at 100% scale and on an actual phone. Check UI legibility, caption safe areas, exact audio sync,
no private data, no blank frames, no layout shifts, and no claim unsupported by the recorded product.
Render a silent proof and a voiceover-only proof before the final mix.
