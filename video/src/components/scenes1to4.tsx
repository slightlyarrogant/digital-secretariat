import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {T} from '../theme';
import {DEMO} from '../scenes';
import {Chip, Cursor, SceneLabel, Workspace} from './ui';

const Center: React.FC<{children: React.ReactNode}> = ({children}) => (
  <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', background: T.paper}}>
    {children}
  </AbsoluteFill>
);

// ══ Scene 1 (0–8 s): three systems speak as one company ════════════════════
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

export const SceneConflict: React.FC = () => {
  const frame = useCurrentFrame();
  const conflictAt = 150; // both dates on screen → contradiction highlighted
  const p = DEMO.paths;
  return (
    <Center>
      <SceneLabel text="Three systems can speak as one company." at={conflictAt + 24} />
      <div style={{textAlign: 'center', marginBottom: 34, opacity: interpolate(frame, [4, 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
        <div style={{fontSize: 24, color: T.inkSoft}}>
          One client · one thread: <b style={{color: T.ink}}>{DEMO.threadSubject}</b>
        </div>
      </div>
      <div style={{display: 'flex', gap: 26}}>
        <PathCard {...p.legacy} tone="err" in={18} conflict={frame > conflictAt} />
        <PathCard {...p.agent} tone="warn" in={52} conflict={frame > conflictAt} />
        <PathCard {...p.owner} tone="wait" in={86} conflict={false} />
      </div>
      {/* the contradiction, stated by the product state — not a slogan */}
      <div
        style={{
          marginTop: 34,
          background: T.redBg,
          border: `1px solid ${T.red}44`,
          borderRadius: 10,
          padding: '14px 30px',
          fontSize: 22,
          fontWeight: 700,
          color: T.red,
          opacity: interpolate(frame, [conflictAt, conflictAt + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
        }}
      >
        Friday, July 24 ≠ Tuesday, July 28 — the same client, two company voices
      </div>
    </Center>
  );
};

// ══ Scene 2 (8–18 s): the promise the company never recorded ═══════════════
export const SceneConsequence: React.FC = () => {
  const frame = useCurrentFrame();
  const searchAt = 168; // Cases search reveals: no matching case
  const typedQuery = DEMO.casesSearchQuery.slice(
    0,
    Math.round(interpolate(frame, [searchAt + 10, searchAt + 55], [0, DEMO.casesSearchQuery.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}))
  );
  const noResult = frame > searchAt + 70;
  return (
    <Center>
      {frame < searchAt ? (
        <SceneLabel text="The client heard a promise." at={70} />
      ) : (
        <SceneLabel text="The company did not record it." at={searchAt + 78} />
      )}
      <div style={{display: 'flex', gap: 26, alignItems: 'flex-start'}}>
        {/* the thread — 14 messages, promise highlighted */}
        <div style={{width: 780, background: T.card, border: `1px solid ${T.line}`, borderRadius: 12, overflow: 'hidden', boxShadow: '0 24px 60px rgba(27,29,33,0.10)'}}>
          <div style={{background: T.nav, color: T.navText, padding: '16px 24px', fontSize: 19, display: 'flex', justifyContent: 'space-between'}}>
            <b>{DEMO.threadSubject}</b>
            <span style={{opacity: 0.65}}>14 messages</span>
          </div>
          <div style={{padding: '20px 24px'}}>
            {DEMO.thread.map((m, i) => {
              const inAt = 12 + i * 22;
              const o = interpolate(frame, [inAt, inAt + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
              const hl = m.promise && frame > 110;
              return (
                <div
                  key={i}
                  style={{
                    opacity: o,
                    background: hl ? T.attentionBg : 'transparent',
                    border: hl ? `1px solid ${T.attention}` : '1px solid transparent',
                    borderRadius: 8,
                    padding: '12px 14px',
                    marginBottom: 8,
                    fontSize: 20,
                    lineHeight: 1.5,
                  }}
                >
                  <b style={{color: m.conflict ? T.red : T.ink}}>{m.who}:</b>{' '}
                  <span style={{color: T.ink}}>{m.text}</span>
                  {hl && (
                    <div style={{marginTop: 8}}>
                      <Chip text="promised date — deadline passed, no owner" tone="err" size={15} />
                    </div>
                  )}
                </div>
              );
            })}
            <div style={{fontSize: 16, color: T.inkFaint, textAlign: 'center', paddingTop: 4}}>
              … 10 more messages in this thread …
            </div>
          </div>
        </div>
        {/* Cases search — comes up empty */}
        <div
          style={{
            width: 560,
            background: T.card,
            border: `1px solid ${T.line}`,
            borderRadius: 12,
            overflow: 'hidden',
            boxShadow: '0 24px 60px rgba(27,29,33,0.10)',
            opacity: interpolate(frame, [searchAt, searchAt + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          }}
        >
          <div style={{background: T.nav, color: T.navText, padding: '16px 24px', fontSize: 19, fontWeight: 700}}>
            Cases
          </div>
          <div style={{padding: '22px 24px'}}>
            <div
              style={{
                border: `1px solid ${T.line}`,
                borderRadius: 8,
                padding: '13px 16px',
                fontSize: 20,
                color: T.ink,
                background: '#FDFDFB',
                fontFamily: T.mono,
              }}
            >
              🔍 {typedQuery}
              {!noResult && <span style={{opacity: frame % 20 < 10 ? 1 : 0}}>▎</span>}
            </div>
            {noResult && (
              <div
                style={{
                  marginTop: 18,
                  background: T.redBg,
                  border: `1px solid ${T.red}44`,
                  borderRadius: 8,
                  padding: '18px 20px',
                  fontSize: 21,
                  fontWeight: 700,
                  color: T.red,
                  opacity: interpolate(frame, [searchAt + 70, searchAt + 84], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
                }}
              >
                No matching case found.
                <div style={{fontSize: 17, fontWeight: 400, color: T.inkSoft, marginTop: 8}}>
                  The Friday promise exists only inside the email thread.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Center>
  );
};

// ══ Scene 3 (18–29 s): the paths collapse into one product workspace ═══════
export const SceneReveal: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const titleIn = 40;
  const wsIn = 170;
  const converge = spring({frame: frame - 6, fps, config: {damping: 200}});
  const wsUp = spring({frame: frame - wsIn, fps, config: {damping: 200}});
  const paths = [DEMO.paths.legacy.name, DEMO.paths.agent.name, DEMO.paths.owner.name];
  return (
    <Center>
      {/* three path chips converge toward the center */}
      {paths.map((name, i) => {
        const startX = [-560, 0, 560][i];
        const x = interpolate(converge, [0, 1], [startX, 0]);
        const o = interpolate(frame, [titleIn - 14, titleIn + 4], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return (
          <div
            key={name}
            style={{
              position: 'absolute',
              top: 300,
              transform: `translateX(${x}px)`,
              opacity: o,
              background: T.card,
              border: `1px solid ${T.line}`,
              borderRadius: 999,
              padding: '12px 26px',
              fontSize: 19,
              fontFamily: T.mono,
              color: T.inkSoft,
            }}
          >
            {name}
          </div>
        );
      })}
      {/* product name — the first dominant title */}
      <div
        style={{
          textAlign: 'center',
          opacity: interpolate(frame, [titleIn, titleIn + 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          transform: `translateY(${interpolate(frame, [titleIn, titleIn + 18], [16, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) - interpolate(wsUp, [0, 1], [0, 350])}px) scale(${interpolate(wsUp, [0, 1], [1, 0.5])})`,
        }}
      >
        <div style={{fontSize: 92, fontWeight: 800, color: T.ink, letterSpacing: -1}}>Digital Secretariat</div>
        <div style={{fontSize: 30, color: T.inkSoft, marginTop: 12}}>
          The client interface for AI-operated companies
        </div>
      </div>
      {/* one workspace rises beneath the title */}
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
              <div key={a.title} style={{opacity: interpolate(frame, [wsIn + 30 + i * 14, wsIn + 44 + i * 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
                <div
                  style={{
                    display: 'flex', alignItems: 'center', gap: 18, background: T.card,
                    border: `1px solid ${i === 0 ? T.attention : T.line}`, borderRadius: 10,
                    padding: '18px 22px', marginBottom: 12, fontSize: 21,
                  }}
                >
                  <span style={{width: 10, height: 10, borderRadius: 999, background: a.kind === 'deadline' ? T.blue : T.attention}} />
                  <span style={{color: T.ink, fontWeight: 600, flex: 1}}>{a.title}</span>
                  <span style={{color: T.inkSoft, fontSize: 17}}>{a.kind}</span>
                  <Chip text={a.due} tone="warn" />
                </div>
              </div>
            ))}
          </div>
        </Workspace>
      </div>
    </Center>
  );
};

// ══ Scene 4 (29–42 s): inbound opens inline with full shared context ═══════
export const SceneInbound: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const clickAt = 70;
  const open = spring({frame: frame - clickAt, fps, config: {damping: 200}});
  const bodyH = interpolate(open, [0, 1], [0, 430]);
  return (
    <Center>
      <SceneLabel text="Every inbound message becomes shared context." at={clickAt + 45} />
      <Workspace title="Inbox">
        <div
          style={{
            background: T.card,
            border: `1px solid ${frame > clickAt ? T.attention : T.line}`,
            borderRadius: 10,
            overflow: 'hidden',
          }}
        >
          {/* row header */}
          <div style={{display: 'flex', alignItems: 'center', gap: 16, padding: '20px 24px'}}>
            <Chip text="client asks for a decision" tone="warn" />
            <div style={{flex: 1}}>
              <div style={{fontSize: 22, fontWeight: 700, color: T.ink}}>{DEMO.subject}</div>
              <div style={{fontSize: 17, color: T.inkSoft, marginTop: 3}}>
                {DEMO.sender} · {DEMO.senderAddr}
              </div>
            </div>
            <Chip text={`mailbox: ${DEMO.mailbox}`} tone="wait" />
            <div
              style={{
                fontSize: 26,
                color: T.inkFaint,
                transform: `rotate(${interpolate(open, [0, 1], [0, 90])}deg)`,
              }}
            >
              ›
            </div>
          </div>
          {/* preview → full content, without leaving the workspace */}
          <div style={{height: bodyH, overflow: 'hidden', borderTop: open > 0.02 ? `1px solid ${T.line}` : 'none'}}>
            <div style={{padding: '22px 26px', fontSize: 21, lineHeight: 1.65, color: T.ink}}>
              {DEMO.body.map((l) => (
                <div key={l}>{l}</div>
              ))}
              <div style={{display: 'flex', gap: 12, marginTop: 18, flexWrap: 'wrap'}}>
                {DEMO.attachments.map((a) => (
                  <Chip key={a} text={`📎 ${a}`} tone="wait" size={16} />
                ))}
                <Chip text="relationship: 14 messages · 1 open conflict" tone="warn" size={16} />
                <Chip text="company state: two dates sent — needs one answer" tone="err" size={16} />
              </div>
            </div>
          </div>
        </div>
        <div style={{height: 470 - Math.min(430, bodyH)}} />
      </Workspace>
      <Cursor
        x={interpolate(frame, [14, clickAt], [1500, 1210], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
        y={interpolate(frame, [14, clickAt], [780, 340], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
        click={frame > clickAt - 3 && frame < clickAt + 10}
      />
    </Center>
  );
};
