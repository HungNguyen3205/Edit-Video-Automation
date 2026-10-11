import type { Backend } from './effect-types.js';
type CanvasPair = readonly [HTMLCanvasElement, HTMLCanvasElement];
export declare class CanvasPool {
    private readonly width;
    private readonly height;
    private readonly pairs;
    private readonly allocated;
    private readonly lostContexts;
    private readonly onContextLost;
    private disposed;
    constructor(width: number, height: number, onContextLost: (canvas: HTMLCanvasElement) => void);
    getPair(backend: Backend): CanvasPair;
    assertContextNotLost(canvas: HTMLCanvasElement): void;
    dispose(): void;
    private allocateCanvas;
}
export {};
