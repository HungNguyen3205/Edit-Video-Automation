import React from 'react';
import type { SequenceControls } from './CompositionManager.js';
type ComponentIdentityResolver = (component: unknown) => unknown;
export declare const REMOTION_INTERNAL_STACK_PROP = "_remotionInternalStack";
export type OriginalSourceLocation = {
    fileName: string;
    line: number;
    column: number;
};
export declare const makeOriginalSourceStack: ({ fileName, lineNumber, columnNumber, }: {
    fileName: string;
    lineNumber: number;
    columnNumber: number;
}) => string;
export declare const parseOriginalSourceStack: (stack: string | null) => OriginalSourceLocation | null;
export declare const getComponentsToAddStacksTo: () => unknown[];
export declare const addSequenceStackTraces: (component: unknown) => void;
export declare const setSequenceComponent: (component: unknown) => void;
export declare const getSequenceComponent: () => unknown;
export declare const setComponentIdentityResolver: (resolver: ComponentIdentityResolver | null) => void;
export declare const resolveComponentIdentity: (component: unknown) => unknown;
export declare const setStackForControls: (controls: SequenceControls, stack: string | undefined) => void;
export declare const getStackForControls: (controls: SequenceControls) => string | null;
export declare const getSingleChildComponent: (children: React.ReactNode) => unknown;
export {};
