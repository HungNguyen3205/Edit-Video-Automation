"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CanvasPool = void 0;
const webgl2_context_error_js_1 = require("./webgl2-context-error.js");
// Per-chain canvas pool. Each chain owns its own pool; pools are not shared
// across chains because dimensions are chain-specific.
//
// Canvases are allocated lazily on first use of a given backend. Once
// allocated, they are reused every frame for the chain's lifetime. Contexts
// are created with the cross-backend alpha/sRGB contract enforced (see
// `effect-types.ts`).
//
// Browsers keep only a limited number of WebGL contexts alive (16 in Chrome
// and Safari) and force-lose the oldest one beyond that, while unreferenced
// canvases are only collected lazily. `dispose()` therefore releases the
// contexts and backing stores as soon as the chain is torn down instead of
// leaving that to the garbage collector.
class CanvasPool {
    width;
    height;
    pairs = new Map();
    // Tracked individually rather than through `pairs` so that a canvas whose
    // sibling failed to allocate still gets released.
    allocated = [];
    lostContexts = new Set();
    onContextLost;
    disposed = false;
    constructor(width, height, onContextLost) {
        this.width = width;
        this.height = height;
        this.onContextLost = onContextLost;
    }
    getPair(backend) {
        if (this.disposed) {
            throw new Error('Effect chain state was used after it had been cleaned up');
        }
        const existing = this.pairs.get(backend);
        if (existing) {
            return existing;
        }
        const pair = [
            this.allocateCanvas(backend),
            this.allocateCanvas(backend),
        ];
        this.pairs.set(backend, pair);
        return pair;
    }
    assertContextNotLost(canvas) {
        if (this.lostContexts.has(canvas)) {
            throw new Error('WebGL context was lost during canvas effect rendering. ' +
                'This typically happens in headless or memory-constrained environments (e.g. Remotion Lambda). ' +
                'Try reducing concurrency or increasing the Lambda function memory.');
        }
    }
    // Makes the pool unusable and releases its resources right away.
    dispose() {
        var _a;
        if (this.disposed) {
            return;
        }
        this.disposed = true;
        for (const { canvas, gl } of this.allocated) {
            // Frees the slot in the browser's live-context budget immediately.
            // Resizing to 0x0 drops the backing store even where the extension
            // is unavailable.
            (_a = gl === null || gl === void 0 ? void 0 : gl.getExtension('WEBGL_lose_context')) === null || _a === void 0 ? void 0 : _a.loseContext();
            canvas.width = 0;
            canvas.height = 0;
        }
        this.allocated.length = 0;
        this.pairs.clear();
        this.lostContexts.clear();
    }
    allocateCanvas(backend) {
        const canvas = document.createElement('canvas');
        canvas.width = this.width;
        canvas.height = this.height;
        switch (backend) {
            case '2d': {
                const ctx = canvas.getContext('2d', {
                    colorSpace: 'srgb',
                });
                if (!ctx) {
                    throw new Error('Failed to acquire 2D context for canvas effect');
                }
                this.allocated.push({ canvas, gl: null });
                return canvas;
            }
            case 'webgl2': {
                const ctx = canvas.getContext('webgl2', {
                    premultipliedAlpha: true,
                    alpha: true,
                    preserveDrawingBuffer: true,
                });
                if (!ctx) {
                    throw (0, webgl2_context_error_js_1.createWebGL2ContextError)('canvas effect');
                }
                canvas.addEventListener('webglcontextlost', (e) => {
                    // `dispose()` loses the context on purpose. Not preventing the
                    // default keeps the browser from restoring a context nobody uses.
                    if (this.disposed) {
                        return;
                    }
                    e.preventDefault();
                    this.lostContexts.add(canvas);
                    this.onContextLost(canvas);
                });
                canvas.addEventListener('webglcontextrestored', () => {
                    if (this.disposed) {
                        return;
                    }
                    // A restored context starts from the initial GL state.
                    ctx.pixelStorei(ctx.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
                    this.lostContexts.delete(canvas);
                });
                ctx.pixelStorei(ctx.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
                this.allocated.push({ canvas, gl: ctx });
                return canvas;
            }
            case 'webgpu': {
                if (typeof navigator === 'undefined' || !('gpu' in navigator)) {
                    throw new Error('WebGPU is not available in this environment for canvas effect');
                }
                this.allocated.push({ canvas, gl: null });
                return canvas;
            }
            default: {
                const exhaustive = backend;
                throw new Error(`Unknown effect backend: ${exhaustive}`);
            }
        }
    }
}
exports.CanvasPool = CanvasPool;
