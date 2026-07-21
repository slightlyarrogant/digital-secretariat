import React from 'react';
import {AbsoluteFill, Series, useCurrentFrame} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Inter';
import {SCENES, CAPTIONS} from './scenes';
import {T, FPS} from './theme';
import {SceneOverview, SceneProblem, SceneCodex, SceneGPT, SceneRail} from './components/scenes60';

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
        <Series.Sequence durationInFrames={SCENES.overview.len} premountFor={FPS}>
          <SceneOverview />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.problem.len} premountFor={FPS}>
          <SceneProblem />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.codex.len} premountFor={FPS}>
          <SceneCodex />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.gpt.len} premountFor={FPS}>
          <SceneGPT />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.rail.len} premountFor={FPS}>
          <SceneRail />
        </Series.Sequence>
      </Series>
      <Captions />
    </AbsoluteFill>
  );
};
