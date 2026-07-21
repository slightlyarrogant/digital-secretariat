import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {T} from '../theme';

// ── Shared product frame: navigation bar + workspace area ──────────────────
export const Workspace: React.FC<{
  children: React.ReactNode;
  title?: string;
  badge?: number;
  width?: number;
}> = ({children, title = 'Today', badge, width = 1440}) => (
  <div
    style={{
      width,
      background: T.card,
      borderRadius: 14,
      border: `1px solid ${T.line}`,
      boxShadow: '0 24px 60px rgba(27,29,33,0.10)',
      overflow: 'hidden',
    }}
  >
    <div
      style={{
        background: T.nav,
        color: T.navText,
        display: 'flex',
        alignItems: 'center',
        gap: 28,
        padding: '0 28px',
        height: 62,
        fontSize: 20,
      }}
    >
      <div style={{fontWeight: 700, letterSpacing: 0.3}}>Digital Secretariat</div>
      {['Today', 'Inbox', 'Cases', 'Relations', 'Performance'].map((t) => (
        <div
          key={t}
          style={{
            opacity: t === title ? 1 : 0.55,
            borderBottom: t === title ? `3px solid ${T.attention}` : '3px solid transparent',
            paddingTop: 3,
            height: 59,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          {t}
          {t === 'Today' && badge !== undefined && (
            <span
              style={{
                background: T.attention,
                color: T.nav,
                borderRadius: 999,
                fontSize: 15,
                fontWeight: 700,
                padding: '1px 10px',
              }}
            >
              {badge}
            </span>
          )}
        </div>
      ))}
      <div style={{marginLeft: 'auto', fontSize: 15, opacity: 0.6}}>
        secretariat.tail▮▮▮.ts.net 🔒
      </div>
    </div>
    <div style={{padding: 28, background: T.paper}}>{children}</div>
  </div>
);

// ── Attention-queue row ─────────────────────────────────────────────────────
export const AttentionRow: React.FC<{
  title: string;
  kind: string;
  due: string;
  focused?: boolean;
  opacity?: number;
}> = ({title, kind, due, focused, opacity = 1}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: 18,
      background: T.card,
      border: `1px solid ${focused ? T.attention : T.line}`,
      boxShadow: focused ? `0 0 0 3px ${T.attentionBg}` : 'none',
      borderRadius: 10,
      padding: '18px 22px',
      marginBottom: 12,
      opacity,
      fontSize: 21,
    }}
  >
    <span
      style={{
        width: 10,
        height: 10,
        borderRadius: 999,
        background: kind === 'deadline' ? T.blue : T.attention,
        flexShrink: 0,
      }}
    />
    <span style={{color: T.ink, fontWeight: 600, flex: 1}}>{title}</span>
    <span style={{color: T.inkSoft, fontSize: 17}}>{kind}</span>
    <span
      style={{
        background: T.attentionBg,
        color: '#8A5A0B',
        borderRadius: 999,
        fontSize: 15,
        fontWeight: 700,
        padding: '3px 12px',
      }}
    >
      {due}
    </span>
  </div>
);

export const Chip: React.FC<{
  text: string;
  tone: 'wait' | 'ok' | 'warn' | 'err';
  size?: number;
}> = ({text, tone, size = 15}) => {
  const c = {
    wait: {bg: T.blueBg, fg: T.blue},
    ok: {bg: T.tealBg, fg: T.teal},
    warn: {bg: T.attentionBg, fg: '#8A5A0B'},
    err: {bg: T.redBg, fg: T.red},
  }[tone];
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        borderRadius: 999,
        fontSize: size,
        fontWeight: 700,
        padding: '4px 12px',
        whiteSpace: 'nowrap',
      }}
    >
      {text}
    </span>
  );
};

// ── Scene label (on-screen text from the brief, not voiceover captions) ─────
export const SceneLabel: React.FC<{text: string; at?: number}> = ({text, at = 8}) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [at, at + 12], [0, 1], {extrapolateRight: 'clamp'});
  const y = interpolate(frame, [at, at + 12], [10, 0], {extrapolateRight: 'clamp'});
  return (
    <div
      style={{
        position: 'absolute',
        top: 54,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
        opacity: o,
        transform: `translateY(${y}px)`,
      }}
    >
      <div
        style={{
          background: T.nav,
          color: T.navText,
          fontSize: 26,
          fontWeight: 600,
          borderRadius: 999,
          padding: '10px 28px',
        }}
      >
        {text}
      </div>
    </div>
  );
};

// ── Cursor (calm — brief: motion must express causality, not wander) ───────
export const Cursor: React.FC<{x: number; y: number; click?: boolean}> = ({x, y, click}) => (
  <div style={{position: 'absolute', left: x, top: y, pointerEvents: 'none'}}>
    {click && (
      <div
        style={{
          position: 'absolute',
          left: -14,
          top: -14,
          width: 28,
          height: 28,
          borderRadius: 999,
          border: `3px solid ${T.teal}`,
          opacity: 0.7,
        }}
      />
    )}
    <svg width="26" height="26" viewBox="0 0 24 24">
      <path
        d="M4 2 L20 12 L12 13.5 L9 21 Z"
        fill={T.ink}
        stroke={T.card}
        strokeWidth="1.6"
      />
    </svg>
  </div>
);
