import React from 'react';
import {AbsoluteFill, Series, useCurrentFrame} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Inter';
import {SCENES, CAPTIONS} from './scenes';
import {T, FPS} from './theme';
import {SceneConflict, SceneConsequence, SceneReveal, SceneInbound} from './components/scenes1to4';
import {SceneApproval, SceneCommitment, SceneShared, SceneClosing} from './components/scenes5to8';

const {fontFamily} = loadFont('normal', {weights: ['400', '600', '700', '800'], subsets: ['latin']});

// Burned-in captions: bottom of frame, max 2 lines (global film timeline).
const Captions: React.FC = () => {
  const frame = useCurrentFrame();
  const cue = CAPTIONS.find((c) => frame >= c.from && frame <= c.to);
  if (!cue) return null;
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 46}}>
      <div
        style={{
          background: 'rgba(22,24,28,0.92)',
          color: '#F3F1EA',
          borderRadius: 12,
          padding: '14px 30px',
          fontSize: 30,
          lineHeight: 1.45,
          textAlign: 'center',
          maxWidth: 1240,
          fontWeight: 600,
        }}
      >
        {cue.lines.map((l) => (
          <div key={l}>{l}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

export const ProductFilmEN: React.FC = () => {
  return (
    <AbsoluteFill style={{background: T.paper, fontFamily}}>
      <Series>
        <Series.Sequence durationInFrames={SCENES.conflict.len} premountFor={FPS}>
          <SceneConflict />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.consequence.len} premountFor={FPS}>
          <SceneConsequence />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.reveal.len} premountFor={FPS}>
          <SceneReveal />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.inbound.len} premountFor={FPS}>
          <SceneInbound />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.approval.len} premountFor={FPS}>
          <SceneApproval />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.commitment.len} premountFor={FPS}>
          <SceneCommitment />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.shared.len} premountFor={FPS}>
          <SceneShared />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.closing.len} premountFor={FPS}>
          <SceneClosing />
        </Series.Sequence>
      </Series>
      <Captions />
    </AbsoluteFill>
  );
};
