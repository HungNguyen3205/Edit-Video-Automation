import React from 'react';
import type { LayoutAndStyle, SequenceProps } from '../Sequence.js';
import { type LoopContextType } from './loop-context.js';
export type LoopProps = {
    readonly durationInFrames: number;
    readonly times?: number;
    readonly name?: string;
    readonly children: React.ReactNode;
} & LayoutAndStyle & Pick<SequenceProps, 'showInTimeline' | 'playbackRate'>;
export declare const LoopTimelineContext: React.Context<{
    startFrame: number;
    firstVisibleFrame: number;
    endFrame: number;
    playbackRate: number;
} | null>;
declare const useLoop: () => LoopContextType | null;
export declare const Loop: React.FC<LoopProps> & {
    useLoop: typeof useLoop;
};
export {};
