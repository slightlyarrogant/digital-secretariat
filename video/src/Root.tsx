import React from 'react';
import {Composition} from 'remotion';
import {ProductFilmEN} from './ProductFilmEN';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="ProductFilmEN"
    component={ProductFilmEN}
    durationInFrames={2490}
    fps={30}
    width={1920}
    height={1080}
  />
);
