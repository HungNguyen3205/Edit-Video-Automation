import React from 'react';
type FreezeProps = {
    readonly frame: number;
    readonly children: React.ReactNode;
    readonly active?: boolean | ((f: number) => boolean);
    readonly _remotionInternalIsPremounting?: boolean;
};
export declare const useIsInsideNonPremountFreeze: () => boolean;
export declare const Freeze: React.FC<FreezeProps>;
export {};
