import type { CanUpdateSequencePropSource, CanUpdateSequencePropStatus, SourceNumericValue } from './use-schema.js';
import type { VideoConfigValues } from './video-config.js';
export declare const evaluateSourceNumericValue: (expression: SourceNumericValue, config: VideoConfigValues | null) => number;
/** Resolve at the consumer, never in the shared source subscription cache. */
export declare const evaluateSourcePropStatuses: (props: Record<string, CanUpdateSequencePropSource>, config: VideoConfigValues | null) => Record<string, CanUpdateSequencePropStatus>;
