// All timings live in data. 30 fps · 2205 frames · 73.5 s.
// Five scenes matched 1:1 to the submission voiceover blocks (VOICEOVER.md, 60-second script).
// Scene lengths are derived from the MEASURED ElevenLabs takes in public/audio/vo60/
// (0.4 s lead-in + take duration + 0.5 s tail; closing holds longer).
export type Cue = { from: number; to: number; lines: [string] | [string, string] };

export const SCENES = {
  overview: { from: 0, len: 438 },     // vo seg1 13.69s @ 0.40s
  problem: { from: 438, len: 417 },    // vo seg2 12.98s @ 15.00s
  codex: { from: 855, len: 449 },      // vo seg3 14.05s @ 28.90s
  gpt: { from: 1304, len: 377 },       // vo seg4 11.65s @ 43.87s
  rail: { from: 1681, len: 524 },      // vo seg5 15.46s @ 56.43s + closing hold
} as const;

// Voiceover anchor times in seconds (assemble_vo60 uses these verbatim).
export const VO_STARTS = [0.4, 15.0, 28.9, 43.87, 56.43];

// Burned captions: verbatim phrases of the narration, max 2 lines.
export const CAPTIONS: Cue[] = [
  { from: 12, to: 224, lines: ['We built Digital Secretariat, a communication', 'control plane for AI-operated companies.'] },
  { from: 230, to: 330, lines: ['It brings inbound email, client context,', 'response drafts, approvals, commitments,'] },
  { from: 334, to: 428, lines: ['deadlines, and delivery evidence', 'into one private workspace.'] },
  { from: 452, to: 560, lines: ['The problem came from our own operations.'] },
  { from: 566, to: 694, lines: ['Old automations and new agents could contact', 'the same client without sharing state.'] },
  { from: 700, to: 836, lines: ['That created invisible conversations, promises nobody', 'owned, and deadlines the company could not see.'] },
  { from: 869, to: 972, lines: ['We used Codex as an engineering partner.'] },
  { from: 978, to: 1118, lines: ['It inspected the existing system, traced failures across', 'the interface, database, mail rail, and deployment…'] },
  { from: 1124, to: 1286, lines: ['…then helped us extract, test, document,', 'and productize the working architecture.'] },
  { from: 1318, to: 1468, lines: ['We used GPT-5.6 to understand incoming communication,', 'classify intent, identify missing context…'] },
  { from: 1474, to: 1663, lines: ['…and prepare concise replies using approved', 'company knowledge and templates.'] },
  { from: 1695, to: 1788, lines: ['But the model is never the final authority.'] },
  { from: 1794, to: 1958, lines: ['External messages pass through one controlled rail, with', 'human approval, revision checks, and auditable delivery.'] },
  { from: 1964, to: 2150, lines: ['Digital Secretariat: one company,', 'one client interface, no invisible promises.'] },
];

// Deterministic demo fixtures — English only, fictional, example.com.
export const DEMO = {
  client: 'Harbor Print Ltd.',
  sender: 'James Whitfield',
  senderAddr: 'j.whitfield@harborprint.example.com',
  mailbox: 'office@company.example.com',
  threadSubject: 'June delivery schedule — order #1042',
  paths: {
    legacy: {
      name: 'legacy-notifier (cron job)',
      line: '“Your order ships Friday, July 24.”',
      status: 'SENT 09:14 — no review, no record',
    },
    agent: {
      name: 'sales-agent v2 (draft)',
      line: '“We propose delivery Tuesday, July 28.”',
      status: 'drafting — different terms, same client',
    },
    owner: {
      name: 'Owner',
      line: 'Sees neither message.',
      status: 'no shared record exists',
    },
  },
  casesSearchQuery: 'harbor friday delivery',
  subject: 'Delivery date for order #1042 — which is it?',
  body: [
    'Hello,',
    'we received two different delivery dates for order #1042:',
    'Friday, July 24 in one email and Tuesday, July 28 in another.',
    'Our print run depends on this. Which date is correct?',
    'Best regards, James Whitfield',
  ],
  attachments: ['order_1042.pdf', 'delivery_terms.pdf'],
  // GPT-5.6 analysis of the inbound message (scene 4).
  analysis: {
    intent: 'intent: delivery-date conflict — client asks for one binding date',
    context: 'missing context: none — order #1042 and both dates identified',
    template: 'template: delivery-confirmation (approved knowledge)',
  },
  reply: [
    'Apologies for the conflicting messages — the correct date is Tuesday, July 28.',
    'The earlier Friday notice was sent in error and is withdrawn. We will confirm the shipping slot by Thursday.',
  ],
  // Codex engineering log (scene 3).
  codexLog: [
    {t: 'codex» inspecting existing system: web app, database, mail rail, deployment', tone: 'ai'},
    {t: '✓ interface: approval actions traced to signed intent tokens', tone: 'ok'},
    {t: '✗ found: legacy module could send SMTP without the canonical rail', tone: 'err'},
    {t: 'codex» tracing failure across email_send_log → smtp_gateway → systemd units', tone: 'ai'},
    {t: 'fix» all outbound paths now fail closed unless released by the rail', tone: 'ok'},
    {t: 'codex» extracting reference product: adapters, migrations, hardened services', tone: 'ai'},
    {t: '✓ tests: revision checks, freshness gate, send-evidence — passing', tone: 'ok'},
    {t: '✓ documented: security invariants + AI-guided installer contract', tone: 'ok'},
  ],
  attention3: [
    { title: 'Reply to Harbor Print — conflicting delivery dates', kind: 'decision', due: 'today' },
    { title: 'Order #1042 — confirm shipping slot', kind: 'deadline', due: 'Jul 24' },
    { title: 'New contact: billing@lakeside-media.example.com', kind: 'relation', due: 'today' },
  ],
};
