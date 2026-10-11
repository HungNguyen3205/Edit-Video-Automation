import type { RefObject } from 'react';
import React from 'react';
type OutlineNode = Element | Text;
type OutlineRef = RefObject<Element | null>;
export declare const SequenceOutlineContext: React.Context<boolean>;
export declare const SequenceOutlineInternals: {
    createRef: () => OutlineRef;
    getNodes: (ref: OutlineRef) => readonly OutlineNode[] | null;
    setNodes: (ref: OutlineRef, nodes: readonly OutlineNode[]) => void;
};
export {};
