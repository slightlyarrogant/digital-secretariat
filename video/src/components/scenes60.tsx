import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {T} from '../theme';
import {DEMO} from '../scenes';
import {AttentionRow, Chip, Cursor, SceneLabel, Workspace} from './ui';

const Center: React.FC<{children: React.ReactNode}> = ({children}) => (
  <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', background: T.paper}}>
    {children}
  </AbsoluteFill>
);

// ══ Scene 1 (0–14.6 s): what we built — one private workspace ══════════════
export const SceneOverview: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const wsIn = 150;
  const wsUp = spring({frame: frame - wsIn, fps, config: {damping: 200}});
  const facets = ['inbound email', 'client context', 'drafts', 'approvals', 'commitments', 'deadlines', 'delivery evidence'];
  return (
    <Center>
      {/* dominant product title first */}
      <div
        style={{
          textAlign: 'center',
          opacity: interpolate(frame, [8, 26], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          transform: `translateY(${-interpolate(wsUp, [0, 1], [0, 350])}px) scale(${interpolate(wsUp, [0, 1], [1, 0.5])})`,
        }}
      >
        <div style={{fontSize: 92, fontWeight: 800, color: T.ink, letterSpacing: -1}}>Digital Secretariat</div>
        <div style={{fontSize: 30, color: T.inkSoft, marginTop: 12}}>
          The communication control plane for AI-operated companies
        </div>
      </div>
      {/* facet chips gather under the title, then the workspace absorbs them */}
      <div
        style={{
          position: 'absolute',
          top: 700,
          display: 'flex',
          gap: 12,
          opacity: interpolate(frame, [wsIn - 10, wsIn + 6], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
        }}
      >
        {facets.map((f, i) => (
          <div
            key={f}
            style={{
              opacity: interpolate(frame, [40 + i * 12, 52 + i * 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
              background: T.card,
              border: `1px solid ${T.line}`,
              borderRadius: 999,
              padding: '10px 22px',
              fontSize: 19,
              color: T.ink,
              fontWeight: 600,
            }}
          >
            {f}
          </div>
        ))}
      </div>
      {/* the workspace — where all of it lives */}
      <div
        style={{
          position: 'absolute',
          top: interpolate(wsUp, [0, 1], [1100, 330]),
          opacity: interpolate(wsUp, [0, 0.3], [0, 1]),
        }}
      >
        <Workspace title="Today" badge={3}>
          <div style={{width: 1380}}>
            {DEMO.attention3.map((a, i) => (
              <div key={a.title} style={{opacity: interpolate(frame, [wsIn + 40 + i * 14, wsIn + 54 + i * 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
                <AttentionRow title={a.title} kind={a.kind} due={a.due} focused={i === 0 && frame > wsIn + 100} />
              </div>
            ))}
            <div
              style={{
                display: 'flex',
                gap: 10,
                marginTop: 14,
                opacity: interpolate(frame, [wsIn + 110, wsIn + 126], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
              }}
            >
              <Chip text="🔒 private — Tailscale identity, laptop and phone" tone="wait" size={16} />
              <Chip text="every send backed by evidence" tone="ok" size={16} />
            </div>
          </div>
        </Workspace>
      </div>
    </Center>
  );
};

// ══ Scene 2 (14.6–28.5 s): the problem from our own operations ═════════════
const PathCard: React.FC<{
  name: string;
  line: string;
  status: string;
  tone: 'err' | 'warn' | 'wait';
  in: number;
  conflict: boolean;
}> = ({name, line, status, tone, in: inAt, conflict}) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [inAt, inAt + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const edge = tone === 'err' ? T.red : tone === 'warn' ? T.attention : T.blue;
  return (
    <div
      style={{
        width: 470,
        background: T.card,
        border: `1px solid ${conflict ? T.red : T.line}`,
        boxShadow: conflict ? `0 0 0 3px ${T.redBg}` : '0 10px 24px rgba(27,29,33,0.07)',
        borderLeft: `5px solid ${edge}`,
        borderRadius: 10,
        padding: '22px 26px',
        opacity: o,
      }}
    >
      <div style={{fontSize: 16, color: T.inkSoft, fontFamily: T.mono, marginBottom: 10}}>{name}</div>
      <div style={{fontSize: 23, fontWeight: 700, color: T.ink, lineHeight: 1.4, minHeight: 96}}>{line}</div>
      <div style={{marginTop: 12}}>
        <Chip text={status} tone={tone} size={15} />
      </div>
    </div>
  );
};

export const SceneProblem: React.FC = () => {
  const frame = useCurrentFrame();
  const conflictAt = 130;
  const caseAt = 250; // the invisible obligation
  const p = DEMO.paths;
  return (
    <Center>
      <SceneLabel text="Two company voices. No shared state." at={conflictAt + 20} />
      <div style={{textAlign: 'center', marginBottom: 34, opacity: interpolate(frame, [6, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
        <div style={{fontSize: 24, color: T.inkSoft}}>
          One client · one thread: <b style={{color: T.ink}}>{DEMO.threadSubject}</b>
        </div>
      </div>
      <div style={{display: 'flex', gap: 26}}>
        <PathCard {...p.legacy} tone="err" in={16} conflict={frame > conflictAt} />
        <PathCard {...p.agent} tone="warn" in={48} conflict={frame > conflictAt} />
        <PathCard {...p.owner} tone="wait" in={80} conflict={false} />
      </div>
      <div
        style={{
          marginTop: 34,
          display: 'flex',
          gap: 16,
          alignItems: 'center',
          opacity: interpolate(frame, [conflictAt, conflictAt + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
        }}
      >
        <div
          style={{
            background: T.redBg,
            border: `1px solid ${T.red}44`,
            borderRadius: 10,
            padding: '14px 26px',
            fontSize: 21,
            fontWeight: 700,
            color: T.red,
          }}
        >
          Friday, July 24 ≠ Tuesday, July 28
        </div>
        <div
          style={{
            background: T.card,
            border: `1px solid ${T.line}`,
            borderRadius: 10,
            padding: '14px 26px',
            fontSize: 20,
            color: T.ink,
            fontFamily: T.mono,
            opacity: interpolate(frame, [caseAt, caseAt + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          }}
        >
          🔍 {DEMO.casesSearchQuery} → <b style={{color: T.red}}>no matching case found</b>
        </div>
      </div>
    </Center>
  );
};

// ══ Scene 3 (28.5–43.5 s): Codex as engineering partner ════════════════════
export const SceneCodex: React.FC = () => {
  const frame = useCurrentFrame();
  const log = DEMO.codexLog;
  const shown = Math.floor(interpolate(frame, [20, 360], [0, log.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const color = (tone: string) =>
    tone === 'err' ? T.red : tone === 'ok' ? T.teal : tone === 'ai' ? T.blue : T.ink;
  return (
    <Center>
      <SceneLabel text="Codex — engineering partner, not autopilot" at={30} />
      {/* light engineering log — no hacker-green terminals */}
      <div
        style={{
          width: 1340,
          background: T.card,
          border: `1px solid ${T.line}`,
          borderRadius: 14,
          boxShadow: '0 24px 60px rgba(27,29,33,0.10)',
          overflow: 'hidden',
        }}
      >
        <div style={{background: T.nav, color: T.navText, padding: '14px 22px', fontSize: 17, display: 'flex', gap: 10}}>
          <span style={{opacity: 0.6}}>●●●</span> codex — extraction of the reference product
        </div>
        <div style={{padding: '26px 30px', fontFamily: T.mono, fontSize: 21, lineHeight: 1.95, minHeight: 460}}>
          {log.slice(0, shown).map((l, i) => (
            <div key={i} style={{color: color(l.tone), fontWeight: l.tone === 'err' || l.tone === 'ok' ? 700 : 400}}>
              {l.t}
            </div>
          ))}
          {shown < log.length && <span style={{opacity: frame % 16 < 8 ? 1 : 0}}>▮</span>}
        </div>
      </div>
    </Center>
  );
};

// ══ Scene 4 (43.5–56 s): GPT-5.6 — proposal, not authority ═════════════════
export const SceneGPT: React.FC = () => {
  const frame = useCurrentFrame();
  const full = DEMO.reply.join(' ');
  const typeFrom = 160;
  const typedChars = Math.round(
    interpolate(frame, [typeFrom, 340], [0, full.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
  );
  const typed = full.slice(0, typedChars);
  const a = DEMO.analysis;
  const chips: [string, number][] = [
    [a.intent, 60],
    [a.context, 95],
    [a.template, 130],
  ];
  return (
    <Center>
      <SceneLabel text="GPT-5.6 prepares a proposal" at={typeFrom} />
      <Workspace title="Inbox">
        {/* the inbound message */}
        <div style={{background: T.card, border: `1px solid ${T.line}`, borderRadius: 10, padding: '16px 22px', marginBottom: 12}}>
          <div style={{fontSize: 20, fontWeight: 700, color: T.ink}}>{DEMO.subject}</div>
          <div style={{fontSize: 16, color: T.inkSoft, marginTop: 3}}>
            {DEMO.sender} · {DEMO.senderAddr} · mailbox: {DEMO.mailbox}
          </div>
          <div style={{fontSize: 18, color: T.ink, marginTop: 10, lineHeight: 1.5}}>
            {DEMO.body[1]} {DEMO.body[2]}
          </div>
        </div>
        {/* model analysis as typed, inspectable chips */}
        <div style={{display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap'}}>
          {chips.map(([text, at]) => (
            <div key={text} style={{opacity: interpolate(frame, [at, at + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
              <Chip text={text} tone="wait" size={16} />
            </div>
          ))}
        </div>
        {/* proposed reply — clearly a draft */}
        <div style={{background: T.card, border: `1px solid ${T.line}`, borderRadius: 10, padding: 20}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10}}>
            <Chip text="proposed draft — awaiting human decision" tone="warn" size={15} />
            <span style={{fontSize: 16, color: T.inkSoft}}>To: {DEMO.senderAddr}</span>
          </div>
          <div
            style={{
              minHeight: 110,
              border: `1px solid ${T.line}`,
              borderRadius: 8,
              padding: '13px 17px',
              fontSize: 20,
              lineHeight: 1.6,
              color: T.ink,
              background: '#FDFDFB',
            }}
          >
            {typed}
            {typedChars < full.length && frame > typeFrom && <span style={{opacity: frame % 20 < 10 ? 1 : 0}}>▎</span>}
          </div>
        </div>
        <div style={{height: 40}} />
      </Workspace>
    </Center>
  );
};

// ══ Scene 5 (56–73.5 s): the rail decides — approval, evidence, closing ════
export const SceneRail: React.FC = () => {
  const frame = useCurrentFrame();
  const clickAt = 110;
  const sentAt = clickAt + 50;
  const toTitle = 330;
  const pending = frame >= clickAt && frame < sentAt;
  const sent = frame >= sentAt;
  const ui = interpolate(frame, [toTitle, toTitle + 22], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const title = interpolate(frame, [toTitle + 12, toTitle + 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <Center>
      {frame < toTitle - 20 && (
        <div style={{opacity: ui}}>
          <SceneLabel text="Human approval. One rail. Auditable delivery." at={12} />
        </div>
      )}
      <div style={{opacity: ui, position: 'absolute'}}>
        <Workspace title="Inbox">
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
                border: `1px solid ${T.line}`,
                borderRadius: 8,
                padding: '14px 18px',
                fontSize: 20,
                lineHeight: 1.6,
                color: T.ink,
                background: '#FDFDFB',
              }}
            >
              {DEMO.reply.join(' ')}
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
              <div style={{marginLeft: 'auto', display: 'flex', gap: 10}}>
                <Chip text="revision 0 — matches review" tone={sent || pending ? 'ok' : 'wait'} size={15} />
                <Chip text="no newer inbound from recipient" tone={sent || pending ? 'ok' : 'wait'} size={15} />
              </div>
            </div>
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
                  opacity: interpolate(frame, [sentAt, sentAt + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
                }}
              >
                email_send_log #4021 · {DEMO.mailbox} → {DEMO.senderAddr} · status: sent ·
                thread: In-Reply-To preserved · approved by: owner
              </div>
            )}
          </div>
        </Workspace>
        <Cursor
          x={interpolate(frame, [40, clickAt], [900, 372], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
          y={interpolate(frame, [40, clickAt], [700, 610], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
          click={frame > clickAt - 3 && frame < clickAt + 8}
        />
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
