import React from 'react';
import type { TSequence } from './CompositionManager.js';
import type { CanUpdateSequencePropStatus, DragOverrideValue, GetDragOverrides, GetEffectDragOverrides, PropStatuses } from './use-schema.js';
import type { SourceNumericValue } from './use-schema.js';
import type { VideoConfigValues } from './video-config.js';
export type SequenceManagerContext = {
    registerSequence: (seq: TSequence) => void;
    updateSequence: ((seq: TSequence) => void) | null;
    unregisterSequence: (id: string) => void;
    sequences: TSequence[];
};
export type SequenceManagerRef = {
    current: TSequence[];
};
export type SequenceNodePath = Array<string | number>;
type SequenceManagerActions = Pick<SequenceManagerContext, 'registerSequence' | 'updateSequence' | 'unregisterSequence'>;
export declare const SequenceManagerActionsContext: React.Context<SequenceManagerActions>;
export declare const SequenceManager: React.Context<SequenceManagerContext>;
export declare const useSequenceManagerSequences: () => TSequence[];
export declare const SequenceManagerRefContext: React.Context<SequenceManagerRef>;
export declare const SequenceRegistrationContext: React.Context<boolean>;
export declare const DisableSequenceRegistrationContext: React.Context<boolean>;
export declare const DisableSequenceRegistrationProvider: React.FC<{
    readonly children: React.ReactNode;
}>;
export type VisualModePropStatuses = {
    propStatuses: PropStatuses;
};
export type VisualModePropStatusesRef = {
    current: PropStatuses;
};
export type VisualModeDragOverrides = {
    getDragOverrides: GetDragOverrides;
    getEffectDragOverrides: GetEffectDragOverrides;
};
type DragOverridesSubscription = {
    manager: SequenceManagerActions;
    subscribe: (key: string | null, listener: () => void) => () => void;
    getSnapshot: (key: string | null) => Record<string, DragOverrideValue>;
    subscribeEffects: (key: string | null, listener: () => void) => () => void;
    getEffectSnapshot: (key: string | null) => Record<string, Record<string, DragOverrideValue>>;
};
export declare const VisualModeDragOverridesSubscriptionContext: React.Context<DragOverridesSubscription | null>;
export type SequencePropsStatusRemapping = {
    previousNodePath: SequencePropsSubscriptionKey;
    nodePath: SequencePropsSubscriptionKey | null;
    result: CanUpdateSequencePropsResponse | null;
};
export type VisualModeSetters = {
    setDragOverrides: (nodePath: SequencePropsSubscriptionKey, key: string, value: DragOverrideValue) => void;
    clearDragOverrides: (nodePath: SequencePropsSubscriptionKey) => void;
    setEffectDragOverrides: (nodePath: SequencePropsSubscriptionKey, effectIndex: number, key: string, value: DragOverrideValue) => void;
    clearEffectDragOverrides: (nodePath: SequencePropsSubscriptionKey, effectIndex: number) => void;
    setPropStatuses: (nodePath: SequencePropsSubscriptionKey, values: (prev: CanUpdateSequencePropsResponse) => CanUpdateSequencePropsResponse) => void;
    remapPropStatuses: (remappings: readonly SequencePropsStatusRemapping[]) => void;
};
export type VisualModeBatchSetters = {
    setDragOverridesBatch: (overrides: readonly {
        readonly nodePath: SequencePropsSubscriptionKey;
        readonly key: string;
        readonly value: DragOverrideValue;
    }[]) => void;
    setEffectDragOverridesBatch: (overrides: readonly {
        readonly nodePath: SequencePropsSubscriptionKey;
        readonly effectIndex: number;
        readonly key: string;
        readonly value: DragOverrideValue;
    }[]) => void;
};
export type CanUpdateEffectPropsResponseTrue<Numeric = SourceNumericValue> = {
    canUpdate: true;
    callee: string;
    importPath: string | null;
    effectIndex: number;
    props: Record<string, CanUpdateSequencePropStatus<Numeric>>;
};
export type CannotUpdateEffectReason = 'not-found' | 'computed' | 'not-call-expression';
export type CannotUpdateSequenceReason = 'not-found' | 'error';
export type CanUpdateEffectPropsResponseFalse = {
    canUpdate: false;
    effectIndex: number;
    reason: CannotUpdateEffectReason;
};
export type CanUpdateEffectPropsResponse<Numeric = SourceNumericValue> = CanUpdateEffectPropsResponseTrue<Numeric> | CanUpdateEffectPropsResponseFalse;
export type CanUpdateSequencePropsResponseTrue<Numeric = SourceNumericValue> = {
    canUpdate: true;
    props: Record<string, CanUpdateSequencePropStatus<Numeric>>;
    effects: CanUpdateEffectPropsResponse<Numeric>[];
};
export type CanUpdateSequencePropsResponseFalse = {
    canUpdate: false;
    reason: CannotUpdateSequenceReason;
};
export type CanUpdateSequencePropsResponse<Numeric = SourceNumericValue> = CanUpdateSequencePropsResponseTrue<Numeric> | CanUpdateSequencePropsResponseFalse;
export declare const makeSequencePropsSubscriptionKey: (key: SequencePropsSubscriptionKey) => string;
export declare const VisualModePropStatusesContext: React.Context<VisualModePropStatuses>;
export declare const VisualModePropStatusesRefContext: React.Context<VisualModePropStatusesRef>;
export declare const VisualModeDragOverridesContext: React.Context<VisualModeDragOverrides>;
export declare const useDragOverridesForNodePath: (nodePath: SequencePropsSubscriptionKey | null) => Record<string, DragOverrideValue>;
export declare const useActiveFromDragOverrideKeys: () => ReadonlySet<string>;
export declare const useEffectDragOverridesForNodePath: (nodePath: SequencePropsSubscriptionKey | null, effectCount: number) => Record<string, Record<string, DragOverrideValue>>;
export declare const VisualModeSettersContext: React.Context<VisualModeSetters>;
export declare const VisualModeBatchSettersContext: React.Context<VisualModeBatchSetters | null>;
export type SequencePropsSubscriptionKey = {
    absolutePath: string;
    nodePath: SequenceNodePath;
    sequenceKeys: string[];
    effectKeys: string[][];
    /** Evaluation context of a rendered instance. Never part of source identity. */
    videoConfigValues: VideoConfigValues | null;
};
export type { VideoConfigValues } from './video-config.js';
export declare const SequenceManagerProvider: React.FC<{
    readonly children: React.ReactNode;
}>;
