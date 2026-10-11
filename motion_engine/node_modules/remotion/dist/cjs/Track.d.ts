import React from 'react';
import { type SequenceProps } from './Sequence.js';
export type TrackProps = Pick<SequenceProps, 'children' | 'name' | 'from' | 'durationInFrames' | 'hidden' | 'showInTimeline'>;
export declare const TrackWithoutSchema: React.FC<SequenceProps>;
/** Groups clips on one Studio timeline row and applies Sequence timing. */
export declare const Track: React.ComponentType<TrackProps>;
