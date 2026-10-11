import type { InteractivitySchema } from './interactivity-schema.js';
import type { ExtrapolateType, InterpolateOutputOption } from './interpolate.js';
import type { CanUpdateSequencePropsResponse, SequencePropsSubscriptionKey } from './SequenceManager.js';
import type { VideoConfigValues } from './video-config.js';
export type CanUpdateSequencePropStatusStatic<Numeric = number> = {
    status: 'static';
    codeValue: unknown;
    keyframeDisplayOffsetAdjustment: Numeric | null;
    /** Multiplies the element's local frame to recover the source frame clock. */
    keyframePlaybackRateAdjustment?: Numeric;
    /** False when the source frame clock cannot be represented by the Studio. */
    canKeyframe?: false;
    numericExpression?: VideoConfigNumericExpression;
};
export type CanUpdateSequencePropStatusKeyframe<Numeric = number> = {
    frame: Numeric;
    value: unknown;
    frameExpression?: VideoConfigNumericExpression;
};
/** Source bindings remain independent of the configuration of a mounted instance. */
export type VideoConfigNumericBinding = {
    type: 'video-config';
    field: keyof VideoConfigValues;
} | {
    type: 'constant';
    value: number;
};
export type VideoConfigNumericExpression = {
    type: 'literal';
    value: number;
} | {
    type: 'video-config-value';
    identifier: string;
    binding: VideoConfigNumericBinding;
} | {
    type: 'video-config-multiplication';
    identifier: string;
    binding: VideoConfigNumericBinding;
    multiplier: number;
    factorPosition: 'left' | 'right';
} | {
    type: 'video-config-subtraction';
    identifier: string;
    binding: VideoConfigNumericBinding;
    subtrahend: number;
} | {
    type: 'binary';
    operator: '+' | '-' | '*' | '/';
    left: SourceNumericValue;
    right: SourceNumericValue;
};
export type SourceNumericValue = number | VideoConfigNumericExpression;
export type CanUpdateSequencePropSource = CanUpdateSequencePropStatus<SourceNumericValue>;
export type CanUpdateSequencePropStatusLinearEasing = {
    type: 'linear';
};
export type CanUpdateSequencePropStatusStep1Easing = {
    type: 'step1';
};
export type CanUpdateSequencePropStatusBezierEasing = {
    type: 'bezier';
    x1: number;
    y1: number;
    x2: number;
    y2: number;
};
export type CanUpdateSequencePropStatusSpringEasing = {
    type: 'spring';
    allowTail: boolean | null;
    damping: number;
    mass: number;
    stiffness: number;
    overshootClamping: boolean;
    durationRestThreshold: number | null;
};
export type CanUpdateSequencePropStatusEasing = CanUpdateSequencePropStatusLinearEasing | CanUpdateSequencePropStatusStep1Easing | CanUpdateSequencePropStatusBezierEasing | CanUpdateSequencePropStatusSpringEasing;
export declare const DEFAULT_LINEAR_EASING: CanUpdateSequencePropStatusLinearEasing;
export type CanUpdateSequencePropStatusClamping = {
    left: ExtrapolateType;
    right: ExtrapolateType;
};
export type CanUpdateSequencePropStatusInterpolationFunction = 'interpolate' | 'interpolateColors' | 'interpolatePaths';
export type CanUpdateSequencePropStatusComputed = {
    status: 'computed';
};
export type CanUpdateSequencePropStatusKeyframed<Numeric = number> = {
    status: 'keyframed';
    interpolationFunction: CanUpdateSequencePropStatusInterpolationFunction;
    /**
     * Subtracted after applying keyframePlaybackRateAdjustment to the controlled
     * element's local frame when evaluating the interpolation.
     * This is non-zero when the useCurrentFrame() call is outside a timing
     * element that wraps the controlled element.
     */
    keyframeDisplayOffsetAdjustment: Numeric | null;
    /** Defaults to 1 for statuses produced without a playback rate conversion. */
    keyframePlaybackRateAdjustment?: Numeric;
    keyframes: CanUpdateSequencePropStatusKeyframe<Numeric>[];
    easing: CanUpdateSequencePropStatusEasing[];
    clamping: CanUpdateSequencePropStatusClamping;
    posterize: number | undefined;
    output: InterpolateOutputOption | undefined;
};
export type CanUpdateSequencePropStatusFalse = CanUpdateSequencePropStatusComputed;
export type CanUpdateSequencePropStatus<Numeric = number> = CanUpdateSequencePropStatusStatic<Numeric> | CanUpdateSequencePropStatusKeyframed<Numeric> | CanUpdateSequencePropStatusFalse;
export type DragOverrideValue = {
    readonly type: 'static';
    readonly value: unknown;
} | {
    readonly type: 'keyframed';
    readonly status: CanUpdateSequencePropStatusKeyframed;
};
export type DragOverrides = Record<string, Record<string, DragOverrideValue>>;
export type EffectDragOverrides = Record<string, Record<string, DragOverrideValue>>;
export type PropStatuses = Record<string, CanUpdateSequencePropsResponse>;
export type GetPropStatuses = (nodePath: SequencePropsSubscriptionKey) => Record<string, CanUpdateSequencePropStatus> | undefined;
export type GetEffectPropStatuses = (nodePath: SequencePropsSubscriptionKey, effectIndex: number) => Record<string, CanUpdateSequencePropStatus> | undefined;
export type GetDragOverrides = (nodePath: SequencePropsSubscriptionKey) => DragOverrides[string];
export type GetEffectDragOverrides = (nodePath: SequencePropsSubscriptionKey, effectIndex: number) => Record<string, DragOverrideValue>;
export declare const makeStaticDragOverride: (value: unknown) => DragOverrideValue;
export declare const makeKeyframedDragOverride: ({ status, frame, value, defaultEasing, }: {
    status: CanUpdateSequencePropStatusKeyframed<number>;
    frame: number;
    value: unknown;
    defaultEasing?: CanUpdateSequencePropStatusEasing | undefined;
}) => DragOverrideValue;
export declare const getStaticDragOverrideValue: (dragOverrideValue: DragOverrideValue | undefined) => unknown;
export declare const isKeyframedStatus: (status: CanUpdateSequencePropStatus<number> | null) => status is CanUpdateSequencePropStatusKeyframed<number>;
export declare const computeEffectiveSchemaValuesDotNotation: ({ schema, currentValue, overrideValues, propStatus, frame, }: {
    schema: InteractivitySchema;
    currentValue: Record<string, unknown>;
    overrideValues: Record<string, DragOverrideValue>;
    propStatus: Record<string, CanUpdateSequencePropStatus<number>> | undefined;
    frame: number | null;
}) => {
    merged: Record<string, unknown>;
    propsToDelete: Set<string>;
};
