// All timings live in data (brief: "Keep scene timings and text in scenes.ts").
// 30 fps · 2400 frames · 80 s. Scene windows follow the brief's timeline table.
export type Cue = { from: number; to: number; lines: [string] | [string, string] };

export const SCENES = {
  conflict: { from: 0, len: 240 },
  consequence: { from: 240, len: 300 },
  reveal: { from: 540, len: 330 },
  inbound: { from: 870, len: 390 },
  approval: { from: 1260, len: 390 },
  commitment: { from: 1650, len: 330 },
  shared: { from: 1980, len: 240 },
  closing: { from: 2220, len: 180 },
} as const;

// Burned-in captions: phrase-level lines from VOICEOVER.md, max 2 lines.
export const CAPTIONS: Cue[] = [
  { from: 10, to: 112, lines: ['An AI-operated company can communicate', 'faster than it coordinates.'] },
  { from: 118, to: 232, lines: ['A legacy job, a new agent, and a human may', 'each tell the same client something different.'] },
  { from: 252, to: 372, lines: ['That is how accidental emails leave and a', 'fourteen-message thread stays invisible…'] },
  { from: 378, to: 530, lines: ['…and a promised Friday deadline becomes an', 'obligation nobody owns or even knows exists.'] },
  { from: 552, to: 660, lines: ['The most important interface in an AI company', 'is not the model.'] },
  { from: 666, to: 768, lines: ['It is the boundary between', 'the company and its clients.'] },
  { from: 774, to: 860, lines: ['Digital Secretariat controls that boundary.'] },
  { from: 885, to: 1048, lines: ['Every inbound message arrives with shared context:', 'sender, mailbox, content, attachments…'] },
  { from: 1054, to: 1248, lines: ['…relationship, and current company state.', 'Every agent starts from the same evidence.'] },
  { from: 1272, to: 1358, lines: ['Outbound communication follows one rail.'] },
  { from: 1364, to: 1478, lines: ['The reviewed revision, recipient, and thread', 'come from trusted data.'] },
  { from: 1484, to: 1638, lines: ['A newer message stops a stale reply.', 'Nothing counts as sent without evidence.'] },
  { from: 1662, to: 1758, lines: ['A promise does not disappear inside email.'] },
  { from: 1764, to: 1965, lines: ['It becomes an owned obligation with a deadline,', 'next action, and link to the conversation.'] },
  { from: 1992, to: 2205, lines: ['Response time, delivery, bounces, outreach, and', 'open commitments now describe one company.'] },
  { from: 2232, to: 2308, lines: ['Digital Secretariat.', 'The client interface for AI-operated companies.'] },
  { from: 2314, to: 2392, lines: ['One company. One client interface.', 'No invisible promises.'] },
];

// Deterministic demo fixtures — English only, fictional, example.com (brief requirement).
export const DEMO = {
  client: 'Harbor Print Ltd.',
  sender: 'James Whitfield',
  senderAddr: 'j.whitfield@harborprint.example.com',
  mailbox: 'office@company.example.com',
  threadSubject: 'June delivery schedule — order #1042',
  // Scene 1: three paths speak for the company at once.
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
  // Scene 2: the thread and the invisible promise.
  thread: [
    { who: 'James Whitfield', text: 'Can you confirm the delivery date for order #1042?' },
    { who: 'legacy-notifier', text: 'Your order ships Friday, July 24.', promise: true },
    { who: 'James Whitfield', text: 'Great — we will plan the print run around Friday.' },
    { who: 'sales-agent v2', text: 'Draft: We propose delivery Tuesday, July 28.', conflict: true },
  ],
  casesSearchQuery: 'harbor friday delivery',
  // Scene 4: the inbound message with full context.
  subject: 'Delivery date for order #1042 — which is it?',
  body: [
    'Hello,',
    'we received two different delivery dates for order #1042:',
    'Friday, July 24 in one email and Tuesday, July 28 in another.',
    'Our print run depends on this. Which date is correct?',
    'Best regards, James Whitfield',
  ],
  attachments: ['order_1042.pdf', 'delivery_terms.pdf'],
  // Scene 5: one reviewed reply with an explicit date.
  reply: [
    'Apologies for the conflicting messages — the correct date is Tuesday, July 28.',
    'The earlier Friday notice was sent in error and is withdrawn. We will confirm the shipping slot by Thursday.',
  ],
  // Scene 6: the promise as an owned obligation.
  caseCard: {
    title: 'Deliver order #1042 by Tuesday, July 28',
    owner: 'Operations — M. Reyes',
    deadline: 'Jul 28',
    nextAction: 'Confirm shipping slot by Thursday, Jul 24',
    source: 'Reply #14 in thread “June delivery schedule”',
  },
  attention3: [
    { title: 'Reply to Harbor Print — conflicting delivery dates', kind: 'decision', due: 'today' },
    { title: 'Order #1042 — confirm shipping slot', kind: 'deadline', due: 'Jul 24' },
    { title: 'New contact: billing@lakeside-media.example.com', kind: 'relation', due: 'today' },
  ],
};
