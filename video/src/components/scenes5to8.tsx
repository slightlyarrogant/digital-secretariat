import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {T} from '../theme';
import {DEMO} from '../scenes';
import {AttentionRow, Chip, Cursor, SceneLabel, Workspace} from './ui';

const Center: React.FC<{children: React.ReactNode}> = ({children}) => (
  <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', background: T.paper}}>
    {children}
  </AbsoluteFill>
);

// ══ Scene 5 (42–55 s): one rail — review, approve, evidence ════════════════
export const SceneApproval: React.FC = () => {
  const frame = useCurrentFrame();
  const full = DEMO.reply.join(' ');
  const typedChars = Math.round(
    interpolate(frame, [15, 160], [0, full.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
  );
  const typed = full.slice(0, typedChars);
  const clickAt = 195;
  const pending = frame >= clickAt && frame < clickAt + 55;
  const sent = frame >= clickAt + 55;
  return (
    <Center>
      {frame < clickAt - 20 ? (
        <SceneLabel text="No accidental send. No invisible revision." at={25} />
      ) : (
        <SceneLabel text="Delivery requires evidence." at={clickAt + 55} />
      )}
      <Workspace title="Inbox">
        {/* collapsed source message */}
        <div
          style={{
            background: T.card,
            border: `1px solid ${T.line}`,
            borderRadius: 10,
            padding: '16px 22px',
            fontSize: 18,
            color: T.inkSoft,
            marginBottom: 14,
          }}
        >
          <b style={{color: T.ink}}>{DEMO.sender}</b> · {DEMO.subject}
        </div>
        {/* reply composer beside the message */}
        <div style={{background: T.card, border: `1px solid ${T.line}`, borderRadius: 10, padding: 22}}>
          <div style={{display: 'flex', gap: 12, marginBottom: 12, fontSize: 17, color: T.inkSoft}}>
            <span>
              To: <b style={{color: T.ink}}>{DEMO.senderAddr}</b>
            </span>
            <span>·</span>
            <span>Subject: Re: {DEMO.subject.slice(0, 44)}…</span>
          </div>
          <div
            style={{
              minHeight: 130,
              border: `1px solid ${T.line}`,
              borderRadius: 8,
              padding: '14px 18px',
              fontSize: 21,
              lineHeight: 1.6,
              color: T.ink,
              background: '#FDFDFB',
            }}
          >
            {typed}
            {frame < clickAt && <span style={{opacity: frame % 20 < 10 ? 1 : 0}}>▎</span>}
          </div>
          <div style={{display: 'flex', alignItems: 'center', gap: 14, marginTop: 16}}>
            <div
              style={{
                background: sent ? T.teal : pending ? T.inkFaint : T.nav,
                color: '#fff',
                borderRadius: 8,
                fontSize: 19,
                fontWeight: 700,
                padding: '12px 26px',
              }}
            >
              {sent ? '✓ Sent' : pending ? 'Releasing…' : 'Approve and send'}
            </div>
            <div style={{color: T.inkSoft, fontSize: 17, border: `1px solid ${T.line}`, borderRadius: 8, padding: '11px 20px'}}>
              Save for decision
            </div>
            <div style={{marginLeft: 'auto', display: 'flex', gap: 10}}>
              <Chip text="revision 0 — matches review" tone={sent || pending ? 'ok' : 'wait'} size={15} />
              <Chip text="no newer inbound from recipient" tone={sent || pending ? 'ok' : 'wait'} size={15} />
            </div>
          </div>
          {/* evidence: the send-log record */}
          {sent && (
            <div
              style={{
                marginTop: 16,
                background: T.tealBg,
                border: `1px solid ${T.teal}33`,
                borderRadius: 8,
                padding: '14px 18px',
                fontSize: 17,
                color: T.teal,
                fontFamily: T.mono,
                opacity: interpolate(frame, [clickAt + 55, clickAt + 70], [0, 1], {
                  extrapolateLeft: 'clamp',
                  extrapolateRight: 'clamp',
                }),
              }}
            >
              email_send_log #4021 · {DEMO.mailbox} → {DEMO.senderAddr} · status: sent ·
              thread: In-Reply-To preserved · approved by: owner (board)
            </div>
          )}
        </div>
      </Workspace>
      <Cursor
        x={interpolate(frame, [165, clickAt], [900, 372], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
        y={interpolate(frame, [165, clickAt], [700, 660], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
        click={frame > clickAt - 3 && frame < clickAt + 8}
      />
    </Center>
  );
};

// ══ Scene 6 (55–66 s): the promise becomes an owned obligation ═════════════
export const SceneCommitment: React.FC = () => {
  const frame = useCurrentFrame();
  const cardAt = 55;
  const c = DEMO.caseCard;
  const rows = [
    {k: 'Owner', v: c.owner},
    {k: 'Deadline', v: c.deadline},
    {k: 'Next action', v: c.nextAction},
    {k: 'Source', v: c.source},
  ];
  return (
    <Center>
      <SceneLabel text="A promise becomes an owned obligation." at={cardAt + 80} />
      <Workspace title="Cases">
        {/* the sent reply that created the obligation */}
        <div
          style={{
            background: T.card,
            border: `1px solid ${T.line}`,
            borderRadius: 10,
            padding: '15px 22px',
            fontSize: 18,
            color: T.inkSoft,
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            opacity: interpolate(frame, [8, 20], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          }}
        >
          <Chip text="✓ sent" tone="ok" size={14} />
          <span>
            Re: {DEMO.subject.slice(0, 52)}… — <b style={{color: T.ink}}>“the correct date is Tuesday, July 28”</b>
          </span>
        </div>
        {/* the case card */}
        <div
          style={{
            background: T.card,
            border: `1px solid ${T.attention}`,
            boxShadow: `0 0 0 3px ${T.attentionBg}`,
            borderRadius: 12,
            padding: '24px 28px',
            opacity: interpolate(frame, [cardAt, cardAt + 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
            transform: `translateY(${interpolate(frame, [cardAt, cardAt + 16], [18, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}px)`,
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18}}>
            <Chip text="CASE-0871" tone="wait" size={15} />
            <div style={{fontSize: 25, fontWeight: 700, color: T.ink}}>{c.title}</div>
            <div style={{marginLeft: 'auto'}}>
              <Chip text="open · owned" tone="ok" size={15} />
            </div>
          </div>
          {rows.map((r, i) => (
            <div
              key={r.k}
              style={{
                display: 'flex',
                gap: 18,
                padding: '13px 0',
                borderTop: `1px solid ${T.line}`,
                fontSize: 20,
                opacity: interpolate(frame, [cardAt + 24 + i * 16, cardAt + 36 + i * 16], [0, 1], {
                  extrapolateLeft: 'clamp',
                  extrapolateRight: 'clamp',
                }),
              }}
            >
              <div style={{width: 170, color: T.inkSoft}}>{r.k}</div>
              <div style={{color: T.ink, fontWeight: 600}}>
                {r.v}
                {r.k === 'Source' && (
                  <span style={{marginLeft: 12}}>
                    <Chip text="linked to conversation" tone="wait" size={13} />
                  </span>
                )}
              </div>
            </div>
          ))}
          <div
            style={{
              marginTop: 16,
              background: T.tealBg,
              border: `1px solid ${T.teal}33`,
              borderRadius: 8,
              padding: '13px 18px',
              fontSize: 18,
              color: T.teal,
              fontWeight: 600,
              opacity: interpolate(frame, [cardAt + 110, cardAt + 126], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
            }}
          >
            Visible to every agent and operator — the whole company sees what it owes this client.
          </div>
        </div>
        <div style={{height: 120}} />
      </Workspace>
    </Center>
  );
};

// ══ Scene 7 (66–74 s): one shared operational truth — desktop + phone ══════
export const SceneShared: React.FC = () => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [12, 80], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const thisMonth = [26, 22, 19, 21, 14, 12, 9, 8, 7, 6];
  const lastMonth = [30, 29, 27, 26, 25, 26, 24, 23, 22, 21];
  const W = 560;
  const H = 210;
  const toPath = (data: number[], upTo: number) => {
    const n = Math.max(2, Math.ceil(data.length * upTo));
    return data
      .slice(0, n)
      .map((v, i) => `${i === 0 ? 'M' : 'L'} ${(i * W) / (data.length - 1)} ${H - (v / 32) * H}`)
      .join(' ');
  };
  const phoneIn = interpolate(frame, [90, 130], [1750, 1330], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <Center>
      <SceneLabel text="One shared operational truth." at={140} />
      <div style={{position: 'relative', width: 1780, height: 820, display: 'flex', alignItems: 'center', justifyContent: 'flex-start', paddingLeft: 40}}>
        <Workspace title="Performance" width={1250}>
          <div style={{display: 'flex', gap: 20}}>
            {/* response-time trend */}
            <div style={{flex: 1.35, background: T.card, border: `1px solid ${T.line}`, borderRadius: 10, padding: 20}}>
              <div style={{fontSize: 19, fontWeight: 700, color: T.ink, marginBottom: 4}}>
                Client response time (hours)
              </div>
              <div style={{fontSize: 15, color: T.inkSoft, marginBottom: 12}}>
                <span style={{color: T.teal, fontWeight: 700}}>— this month</span> ·{' '}
                <span style={{color: T.inkFaint, fontWeight: 700}}>— last month</span>
              </div>
              <svg width={W} height={H} style={{overflow: 'visible'}}>
                {[0, 10, 20, 30].map((g) => (
                  <g key={g}>
                    <line x1={0} x2={W} y1={H - (g / 32) * H} y2={H - (g / 32) * H} stroke={T.line} />
                    <text x={-10} y={H - (g / 32) * H + 5} fontSize={13} fill={T.inkFaint} textAnchor="end">
                      {g}
                    </text>
                  </g>
                ))}
                <path d={toPath(lastMonth, reveal)} fill="none" stroke={T.inkFaint} strokeWidth={3} />
                <path d={toPath(thisMonth, reveal)} fill="none" stroke={T.teal} strokeWidth={4} />
                {reveal > 0.98 && (
                  <g>
                    <circle cx={W} cy={H - (thisMonth[9] / 32) * H} r={7} fill={T.teal} stroke={T.card} strokeWidth={2.5} />
                    <text x={W - 8} y={H - (thisMonth[9] / 32) * H - 14} fontSize={17} fontWeight={700} fill={T.teal} textAnchor="end">
                      6 h
                    </text>
                  </g>
                )}
              </svg>
            </div>
            <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: 20}}>
              {/* message handling split */}
              <div style={{background: T.card, border: `1px solid ${T.line}`, borderRadius: 10, padding: 20}}>
                <div style={{fontSize: 19, fontWeight: 700, color: T.ink, marginBottom: 12}}>
                  Message handling — this month
                </div>
                <div style={{display: 'flex', height: 32, borderRadius: 8, overflow: 'hidden', width: `${reveal * 100}%`}}>
                  <div style={{flex: 46, background: T.teal}} />
                  <div style={{flex: 22, background: T.blue}} />
                  <div style={{flex: 32, background: T.attention}} />
                </div>
                <div style={{display: 'flex', gap: 14, marginTop: 10, fontSize: 15, color: T.inkSoft}}>
                  <span><b style={{color: T.teal}}>46%</b> automated</span>
                  <span><b style={{color: T.blue}}>22%</b> templated</span>
                  <span><b style={{color: '#8A5A0B'}}>32%</b> human decisions</span>
                </div>
                <div style={{fontSize: 14, color: T.inkFaint, marginTop: 8}}>
                  delivery 99.2% · bounces 0.8% · outreach replies 58/420
                </div>
              </div>
              {/* open commitments */}
              <div style={{background: T.card, border: `1px solid ${T.line}`, borderRadius: 10, padding: 20, flex: 1}}>
                <div style={{fontSize: 19, fontWeight: 700, color: T.ink, marginBottom: 12}}>Open commitments</div>
                <div style={{fontSize: 44, fontWeight: 800, color: T.ink, lineHeight: 1}}>
                  3 <span style={{fontSize: 18, fontWeight: 600, color: T.teal}}>· every one owned</span>
                </div>
                <div style={{fontSize: 15, color: T.inkSoft, marginTop: 10}}>
                  next due: order #1042 — Tuesday, Jul 28
                </div>
              </div>
            </div>
          </div>
        </Workspace>
        {/* private phone access — supporting fact */}
        <div
          style={{
            position: 'absolute',
            left: phoneIn,
            top: 30,
            width: 330,
            height: 700,
            background: T.nav,
            borderRadius: 42,
            padding: 12,
            boxShadow: '0 30px 70px rgba(27,29,33,0.25)',
          }}
        >
          <div style={{background: T.paper, borderRadius: 32, height: '100%', overflow: 'hidden'}}>
            <div style={{background: T.nav, color: T.navText, padding: '15px 16px', fontSize: 15, display: 'flex', justifyContent: 'space-between'}}>
              <b>Digital Secretariat</b>
              <span style={{opacity: 0.65}}>🔒 private</span>
            </div>
            <div style={{padding: 13}}>
              <div style={{fontSize: 13, letterSpacing: 1, textTransform: 'uppercase', color: T.inkSoft, margin: '4px 0 10px'}}>
                For decision (3)
              </div>
              {DEMO.attention3.map((a, i) => (
                <div
                  key={a.title}
                  style={{
                    background: T.card,
                    border: `1px solid ${i === 0 ? T.attention : T.line}`,
                    borderRadius: 12,
                    padding: '12px 12px',
                    marginBottom: 9,
                    fontSize: 14.5,
                    color: T.ink,
                    fontWeight: 600,
                    lineHeight: 1.35,
                  }}
                >
                  {a.title}
                  <div style={{marginTop: 7, display: 'flex', gap: 7}}>
                    <Chip text={a.due} tone="warn" size={11} />
                    <Chip text={a.kind} tone="wait" size={11} />
                  </div>
                </div>
              ))}
              <div style={{display: 'flex', gap: 9, marginTop: 12}}>
                <div style={{flex: 1, background: T.teal, color: '#fff', textAlign: 'center', borderRadius: 10, padding: '12px 0', fontSize: 15, fontWeight: 700}}>
                  Approve
                </div>
                <div style={{flex: 1, border: `1px solid ${T.line}`, color: T.inkSoft, textAlign: 'center', borderRadius: 10, padding: '12px 0', fontSize: 15}}>
                  Reject
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Center>
  );
};

// ══ Scene 8 (74–80 s): calm workspace → closing title ══════════════════════
export const SceneClosing: React.FC = () => {
  const frame = useCurrentFrame();
  const toTitle = 78;
  const ui = interpolate(frame, [toTitle, toTitle + 20], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const title = interpolate(frame, [toTitle + 10, toTitle + 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <Center>
      <div style={{opacity: ui, position: 'absolute'}}>
        <Workspace title="Today" badge={1}>
          <div style={{width: 1380}}>
            <AttentionRow title="Approve the monthly summary for 4 client companies" kind="decision" due="today" focused />
            <div
              style={{
                marginTop: 18,
                background: T.tealBg,
                border: `1px solid ${T.teal}33`,
                borderRadius: 10,
                padding: '16px 22px',
                fontSize: 19,
                color: T.teal,
                fontWeight: 600,
              }}
            >
              ✓ Everything else handled with evidence: 41 messages, 6 documents, 0 commitments without an owner.
            </div>
            <div style={{height: 300}} />
          </div>
        </Workspace>
      </div>
      <div style={{opacity: title, textAlign: 'center'}}>
        <div style={{fontSize: 88, fontWeight: 800, color: T.ink, letterSpacing: -1}}>Digital Secretariat</div>
        <div style={{fontSize: 32, color: T.inkSoft, marginTop: 16}}>
          One company. One client interface. No invisible promises.
        </div>
      </div>
    </Center>
  );
};
