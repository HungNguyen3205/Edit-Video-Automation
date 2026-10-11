"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.HtmlInCanvas = exports.htmlInCanvasSchema = exports.getHtmlInCanvasUnsupportedMessage = exports.HTML_IN_CANVAS_UNSUPPORTED_MESSAGE = exports.isHtmlInCanvasNestingSupported = exports.isHtmlInCanvasSupported = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const run_effect_chain_js_1 = require("./effects/run-effect-chain.js");
const use_effect_chain_state_js_1 = require("./effects/use-effect-chain-state.js");
const use_memoized_effects_js_1 = require("./effects/use-memoized-effects.js");
const enable_sequence_stack_traces_js_1 = require("./enable-sequence-stack-traces.js");
const freeze_js_1 = require("./freeze.js");
const interactivity_schema_js_1 = require("./interactivity-schema.js");
const resolve_sequence_duration_js_1 = require("./resolve-sequence-duration.js");
const Sequence_js_1 = require("./Sequence.js");
const use_crop_style_js_1 = require("./use-crop-style.js");
const use_delay_render_js_1 = require("./use-delay-render.js");
const use_premounting_js_1 = require("./use-premounting.js");
const use_remotion_environment_js_1 = require("./use-remotion-environment.js");
const with_interactivity_schema_js_1 = require("./with-interactivity-schema.js");
// `transferControlToOffscreen()` may only be called once per canvas — a second
// call throws an `InvalidStateError`. The layout effect that needs the
// `OffscreenCanvas` can run more than once for the same canvas element: its
// dependencies (e.g. the paint callback) can change identity without the
// canvas remounting, and React StrictMode intentionally double-invokes
// effects. Cache the transferred `OffscreenCanvas` per canvas element so
// re-runs reuse it instead of throwing.
const transferredOffscreenCanvases = new WeakMap();
const getTransferredOffscreenCanvas = (canvas) => {
    const existing = transferredOffscreenCanvases.get(canvas);
    if (existing) {
        return existing;
    }
    const offscreen = canvas.transferControlToOffscreen();
    transferredOffscreenCanvases.set(canvas, offscreen);
    return offscreen;
};
// Memoize the support check across the session — neither the platform
// capability nor the chrome://flags toggle can change between calls.
// SSR results are not cached so the check runs again once `document` exists.
let cachedSupport = null;
const isHtmlInCanvasSupported = () => {
    if (cachedSupport !== null) {
        return cachedSupport;
    }
    if (typeof document === 'undefined') {
        return false;
    }
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    cachedSupport =
        typeof (ctx === null || ctx === void 0 ? void 0 : ctx.drawElementImage) === 'function' &&
            typeof canvas.requestPaint === 'function' &&
            typeof canvas.captureElementImage === 'function' &&
            'transferControlToOffscreen' in HTMLCanvasElement.prototype;
    return cachedSupport;
};
exports.isHtmlInCanvasSupported = isHtmlInCanvasSupported;
const MINIMUM_CHROME_VERSION_FOR_NESTED_HTML_IN_CANVAS = 157;
const isHtmlInCanvasNestingSupported = () => {
    var _a;
    if (!(0, exports.isHtmlInCanvasSupported)() || typeof navigator === 'undefined') {
        return false;
    }
    const chromeVersion = (_a = navigator.userAgent.match(/(?:Chrome|Chromium)\/(\d+)/)) === null || _a === void 0 ? void 0 : _a[1];
    return (chromeVersion !== undefined &&
        Number(chromeVersion) >= MINIMUM_CHROME_VERSION_FOR_NESTED_HTML_IN_CANVAS);
};
exports.isHtmlInCanvasNestingSupported = isHtmlInCanvasNestingSupported;
/** Generic fallback for consumers that cannot inspect the current browser. */
exports.HTML_IN_CANVAS_UNSUPPORTED_MESSAGE = 'HTML in Canvas requires Chrome 149 or newer with Canvas Draw Element enabled at chrome://flags/#canvas-draw-element.';
const getHtmlInCanvasUnsupportedMessage = () => {
    var _a;
    if (typeof document === 'undefined') {
        return `HTML in Canvas is unavailable because there is no browser document. ${exports.HTML_IN_CANVAS_UNSUPPORTED_MESSAGE}`;
    }
    const userAgent = typeof navigator === 'undefined' ? '' : navigator.userAgent;
    const chromiumVersion = (_a = userAgent.match(/(?:Chrome|Chromium)\/(\d+)/)) === null || _a === void 0 ? void 0 : _a[1];
    let browser = 'this browser';
    if (userAgent.includes('Edg/')) {
        browser = 'Microsoft Edge';
    }
    else if (userAgent.includes('Chromium/')) {
        browser = 'Chromium';
    }
    else if (chromiumVersion) {
        browser = 'Chrome';
    }
    else if (userAgent.includes('Firefox/')) {
        browser = 'Firefox';
    }
    else if (userAgent.includes('Safari/')) {
        browser = 'Safari';
    }
    if (chromiumVersion && Number(chromiumVersion) >= 149) {
        const flagUrl = browser === 'Microsoft Edge'
            ? 'edge://flags/#canvas-draw-element'
            : 'chrome://flags/#canvas-draw-element';
        return `HTML in Canvas is unavailable. Enable Canvas Draw Element at ${flagUrl} and fully restart ${browser}.`;
    }
    if (chromiumVersion) {
        return `HTML in Canvas is not supported in ${browser} ${chromiumVersion}. Use a Chromium-based browser running version 149 or newer.`;
    }
    return `HTML in Canvas is not supported in ${browser}. Use Chrome 149 or newer.`;
};
exports.getHtmlInCanvasUnsupportedMessage = getHtmlInCanvasUnsupportedMessage;
function assertHtmlInCanvasDimensions(width, height) {
    if (typeof width !== 'number' || typeof height !== 'number') {
        throw new Error(`HtmlInCanvas: \`width\` and \`height\` must be numbers. Received width=${String(width)}, height=${String(height)}.`);
    }
    if (!Number.isInteger(width) || width <= 0) {
        throw new Error(`HtmlInCanvas: \`width\` must be a positive integer. Received: ${String(width)}.`);
    }
    if (!Number.isInteger(height) || height <= 0) {
        throw new Error(`HtmlInCanvas: \`height\` must be a positive integer. Received: ${String(height)}.`);
    }
}
function resolveHtmlInCanvasPixelDensity(pixelDensity) {
    if (pixelDensity === undefined) {
        return 1;
    }
    if (typeof pixelDensity !== 'number' ||
        !Number.isFinite(pixelDensity) ||
        pixelDensity <= 0) {
        throw new Error(`HtmlInCanvas: \`pixelDensity\` must be a positive finite number. Received: ${String(pixelDensity)}.`);
    }
    return pixelDensity;
}
const isMissingPaintRecordError = (error) => {
    return error instanceof DOMException && error.name === 'InvalidStateError';
};
const missingPaintRecordMessage = 'HtmlInCanvas: Expected the element to be inside the viewport during rendering, but Chrome had no cached paint record for it.';
const resizePaintTarget = ({ target, width, height, }) => {
    if (target.width !== width) {
        target.width = width;
    }
    if (target.height !== height) {
        target.height = height;
    }
};
const defaultOnPaint = ({ canvas, elementImage, }) => {
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        throw new Error('Failed to acquire 2D context for <HtmlInCanvas> canvas');
    }
    ctx.reset();
    ctx.drawElementImage(elementImage, 0, 0);
};
/* eslint-enable react/require-default-props */
const HtmlInCanvasAncestorContext = (0, react_1.createContext)(false);
const HtmlInCanvasContent = (0, react_1.forwardRef)(({ width, height, effects, children, canvasSiblings, onPaint, onInit, pixelDensity, controls, style, }, ref) => {
    var _a, _b;
    const isInsideAncestorHtmlInCanvas = (0, react_1.useContext)(HtmlInCanvasAncestorContext);
    assertHtmlInCanvasDimensions(width, height);
    if (isInsideAncestorHtmlInCanvas && !(0, exports.isHtmlInCanvasNestingSupported)()) {
        throw new Error(`Nested <HtmlInCanvas> components require Chrome ${MINIMUM_CHROME_VERSION_FOR_NESTED_HTML_IN_CANVAS} or newer with HTML-in-canvas enabled.`);
    }
    const resolvedPixelDensity = resolveHtmlInCanvasPixelDensity(pixelDensity);
    const canvasWidth = Math.ceil(width * resolvedPixelDensity);
    const canvasHeight = Math.ceil(height * resolvedPixelDensity);
    const { delayRender, continueRender, cancelRender } = (0, use_delay_render_js_1.useDelayRender)();
    const { isClientSideRendering, isRendering } = (0, use_remotion_environment_js_1.useRemotionEnvironment)();
    const canRetryMissingPaintRecord = !isRendering || isClientSideRendering;
    const usesDirectLayoutCanvas = onPaint === undefined && onInit === undefined;
    if (!(0, exports.isHtmlInCanvasSupported)()) {
        cancelRender(new Error((0, exports.getHtmlInCanvasUnsupportedMessage)()));
    }
    const canvas2dRef = (0, react_1.useRef)(null);
    const paintTargetRef = (0, react_1.useRef)(null);
    const divRef = (0, react_1.useRef)(null);
    const canvasSizeKey = `${width}x${height}@${resolvedPixelDensity}-${usesDirectLayoutCanvas ? 'direct' : 'offscreen'}`;
    const setLayoutCanvasRef = (0, react_1.useCallback)((node) => {
        canvas2dRef.current = node;
        if (typeof ref === 'function') {
            ref(node);
        }
        else if (ref) {
            ref.current = node;
        }
    }, [ref]);
    const chainState = (0, use_effect_chain_state_js_1.useEffectChainState)();
    const memoizedEffects = (0, use_memoized_effects_js_1.useMemoizedEffects)({
        effects,
        overrideId: (_a = controls === null || controls === void 0 ? void 0 : controls.overrideId) !== null && _a !== void 0 ? _a : null,
        videoConfigValues: (_b = controls === null || controls === void 0 ? void 0 : controls.videoConfigValues) !== null && _b !== void 0 ? _b : null,
    });
    // Refs so the paint handler always reads fresh values.
    const effectsRef = (0, react_1.useRef)(memoizedEffects);
    effectsRef.current = memoizedEffects;
    const onPaintRef = (0, react_1.useRef)(onPaint);
    onPaintRef.current = onPaint;
    const onInitRef = (0, react_1.useRef)(onInit);
    onInitRef.current = onInit;
    const initializedRef = (0, react_1.useRef)(false);
    const onInitCleanupRef = (0, react_1.useRef)(null);
    const unmountedRef = (0, react_1.useRef)(false);
    const onPaintCb = (0, react_1.useCallback)(async () => {
        const element = divRef.current;
        if (!element) {
            throw new Error('Canvas or scene element not found');
        }
        const paintTarget = paintTargetRef.current;
        if (!paintTarget) {
            throw new Error('HtmlInCanvas: paint target is not ready because the canvas is remounting');
        }
        resizePaintTarget({
            target: paintTarget,
            width: canvasWidth,
            height: canvasHeight,
        });
        try {
            const placeholderCanvas = canvas2dRef.current;
            if (!placeholderCanvas) {
                throw new Error('Canvas not found');
            }
            const handle = delayRender('onPaint');
            if (!initializedRef.current) {
                const currentOnInit = onInitRef.current;
                if (!currentOnInit) {
                    initializedRef.current = true;
                }
                else {
                    // `onInit` may be async (e.g. WebGPU
                    // `requestAdapter`/`requestDevice`). Do not reuse this capture for
                    // `onPaint`: awaiting initialization can invalidate its paint context.
                    let initImage;
                    try {
                        initImage = placeholderCanvas.captureElementImage(element);
                    }
                    catch (error) {
                        if (isMissingPaintRecordError(error) &&
                            canRetryMissingPaintRecord) {
                            // The web renderer explicitly drives additional paint cycles, so a
                            // transient missing record can be retried without failing the render.
                            continueRender(handle);
                            return;
                        }
                        if (isMissingPaintRecordError(error)) {
                            throw new Error(missingPaintRecordMessage);
                        }
                        throw error;
                    }
                    initializedRef.current = true;
                    try {
                        if (paintTarget instanceof HTMLCanvasElement) {
                            throw new Error('HtmlInCanvas: onInit requires an OffscreenCanvas paint target');
                        }
                        const cleanup = await currentOnInit({
                            canvas: paintTarget,
                            element,
                            elementImage: initImage,
                            pixelDensity: resolvedPixelDensity,
                        });
                        if (typeof cleanup !== 'function') {
                            throw new Error('HtmlInCanvas: when `onInit` is provided, it must return a cleanup function, or a Promise that resolves to one.');
                        }
                        if (unmountedRef.current) {
                            cleanup();
                        }
                        else {
                            onInitCleanupRef.current = cleanup;
                        }
                    }
                    finally {
                        initImage.close();
                    }
                }
            }
            let elImage;
            try {
                elImage = placeholderCanvas.captureElementImage(element);
            }
            catch (error) {
                // `captureElementImage` throws `InvalidStateError` when the
                // element is outside the viewport (no cached paint record).
                // Skip this paint cycle — the canvas retains its last state.
                if (isMissingPaintRecordError(error) && canRetryMissingPaintRecord) {
                    continueRender(handle);
                    return;
                }
                if (isMissingPaintRecordError(error)) {
                    throw new Error(missingPaintRecordMessage);
                }
                throw error;
            }
            try {
                const currentOnPaint = onPaintRef.current;
                if (currentOnPaint) {
                    if (paintTarget instanceof HTMLCanvasElement) {
                        throw new Error('HtmlInCanvas: onPaint requires an OffscreenCanvas paint target');
                    }
                    const paintResult = currentOnPaint({
                        canvas: paintTarget,
                        element,
                        elementImage: elImage,
                        pixelDensity: resolvedPixelDensity,
                    });
                    if (paintResult) {
                        await paintResult;
                    }
                }
                else {
                    defaultOnPaint({
                        canvas: paintTarget,
                        element,
                        elementImage: elImage,
                        pixelDensity: resolvedPixelDensity,
                    });
                }
                // `null` once unmounted, e.g. when an async `onPaint` resolves late.
                const state = chainState.get(canvasWidth, canvasHeight);
                if (state) {
                    await (0, run_effect_chain_js_1.runEffectChain)({
                        state,
                        source: paintTarget,
                        effects: effectsRef.current,
                        output: paintTarget,
                        width: canvasWidth,
                        height: canvasHeight,
                    });
                }
            }
            finally {
                elImage.close();
            }
            continueRender(handle);
        }
        catch (error) {
            cancelRender(error);
        }
    }, [
        canvasHeight,
        canvasWidth,
        chainState,
        continueRender,
        cancelRender,
        delayRender,
        resolvedPixelDensity,
        canRetryMissingPaintRecord,
    ]);
    // Default paint handlers draw synchronously on the layout canvas itself.
    // Custom handlers retain the transferred OffscreenCanvas API.
    (0, react_1.useLayoutEffect)(() => {
        var _a;
        const placeholder = canvas2dRef.current;
        if (!placeholder) {
            throw new Error('Canvas not found');
        }
        placeholder.setAttribute('content', 'drawable');
        placeholder.layoutSubtree = true;
        (_a = divRef.current) === null || _a === void 0 ? void 0 : _a.setAttribute('drawable', '');
        const paintTarget = usesDirectLayoutCanvas
            ? placeholder
            : getTransferredOffscreenCanvas(placeholder);
        paintTargetRef.current = paintTarget;
        resizePaintTarget({
            target: paintTarget,
            width: canvasWidth,
            height: canvasHeight,
        });
        initializedRef.current = false;
        unmountedRef.current = false;
        placeholder.addEventListener('paint', onPaintCb);
        return () => {
            var _a;
            placeholder.removeEventListener('paint', onPaintCb);
            paintTargetRef.current = null;
            initializedRef.current = false;
            unmountedRef.current = true;
            (_a = onInitCleanupRef.current) === null || _a === void 0 ? void 0 : _a.call(onInitCleanupRef);
            onInitCleanupRef.current = null;
        };
    }, [
        onPaintCb,
        cancelRender,
        canvasWidth,
        canvasHeight,
        usesDirectLayoutCanvas,
    ]);
    const onPaintChangedRef = (0, react_1.useRef)(false);
    (0, react_1.useLayoutEffect)(() => {
        var _a;
        if (!onPaintChangedRef.current) {
            onPaintChangedRef.current = true;
            return;
        }
        const canvas = canvas2dRef.current;
        if (!canvas) {
            return;
        }
        (_a = canvas.requestPaint) === null || _a === void 0 ? void 0 : _a.call(canvas);
    }, [onPaint, memoizedEffects]);
    (0, react_1.useLayoutEffect)(() => {
        const canvas = canvas2dRef.current;
        if (!canvas) {
            return;
        }
        const handle = delayRender('waiting for first paint after canvas resize');
        canvas.addEventListener('paint', () => {
            continueRender(handle);
        }, { once: true });
        return () => {
            continueRender(handle);
        };
    }, [width, height, continueRender, delayRender, canvasSizeKey]);
    const innerStyle = (0, react_1.useMemo)(() => {
        return {
            width,
            height,
        };
    }, [width, height]);
    const canvasStyle = (0, react_1.useMemo)(() => {
        return {
            width,
            height,
            ...(style !== null && style !== void 0 ? style : {}),
        };
    }, [height, style, width]);
    return (jsx_runtime_1.jsx(HtmlInCanvasAncestorContext.Provider, { value: true, children: jsx_runtime_1.jsxs("canvas", { ref: setLayoutCanvasRef, width: canvasWidth, height: canvasHeight, style: canvasStyle, children: [
                jsx_runtime_1.jsx("div", { ref: divRef, style: innerStyle, children: children }), canvasSiblings] }, canvasSizeKey) }));
});
HtmlInCanvasContent.displayName = 'HtmlInCanvasContent';
const HtmlInCanvasInner = (0, react_1.forwardRef)(({ width, height, effects = [], children, onPaint, onInit, pixelDensity, _remotionInternalCanvasSiblings, controls, style, cropLeft, cropRight, cropTop, cropBottom, durationInFrames, premountFor, postmountFor, styleWhilePremounted, styleWhilePostmounted, name, ...sequenceProps }, ref) => {
    var _a;
    const memoizedEffectDefinitions = (0, use_memoized_effects_js_1.useMemoizedEffectDefinitions)(effects);
    const actualRef = (0, react_1.useRef)(null);
    const setCanvasRef = (0, react_1.useCallback)((node) => {
        actualRef.current = node;
        if (typeof ref === 'function') {
            ref(node);
        }
        else if (ref) {
            ref.current = node;
        }
    }, [ref]);
    const { effectivePremountFor, effectivePostmountFor, freezeFrame, isPremountingOrPostmounting, premountingActive, postmountingActive, premountingStyle, } = (0, use_premounting_js_1.usePremounting)({
        from: (_a = sequenceProps.from) !== null && _a !== void 0 ? _a : 0,
        durationInFrames: (0, resolve_sequence_duration_js_1.resolveSequenceDuration)({
            durationInFrames,
            playbackRate: sequenceProps.playbackRate,
            loop: sequenceProps.loop,
        }),
        premountFor: premountFor !== null && premountFor !== void 0 ? premountFor : null,
        postmountFor: postmountFor !== null && postmountFor !== void 0 ? postmountFor : null,
        style: style !== null && style !== void 0 ? style : null,
        styleWhilePremounted: styleWhilePremounted !== null && styleWhilePremounted !== void 0 ? styleWhilePremounted : null,
        styleWhilePostmounted: styleWhilePostmounted !== null && styleWhilePostmounted !== void 0 ? styleWhilePostmounted : null,
        hideWhilePremounted: 'opacity',
    });
    const croppedStyle = (0, use_crop_style_js_1.useCropStyle)({
        cropLeft,
        cropRight,
        cropTop,
        cropBottom,
        style: premountingStyle,
        componentName: '<HtmlInCanvas />',
    });
    return (jsx_runtime_1.jsx(freeze_js_1.Freeze, { frame: freezeFrame, active: isPremountingOrPostmounting, _remotionInternalIsPremounting: premountingActive, children: jsx_runtime_1.jsx(Sequence_js_1.Sequence, { layout: "none", durationInFrames: durationInFrames, name: name !== null && name !== void 0 ? name : '<HtmlInCanvas>', _remotionInternalDocumentationLink: "https://www.remotion.dev/docs/remotion/html-in-canvas", controls: controls, _remotionInternalEffects: memoizedEffectDefinitions, ...sequenceProps, _remotionInternalPremountDisplay: effectivePremountFor || null, _remotionInternalPostmountDisplay: effectivePostmountFor || null, _remotionInternalIsPremounting: premountingActive, _remotionInternalIsPostmounting: postmountingActive, children: jsx_runtime_1.jsx(HtmlInCanvasContent, { ref: setCanvasRef, width: width, height: height, effects: effects, onPaint: onPaint, onInit: onInit, pixelDensity: pixelDensity, canvasSiblings: _remotionInternalCanvasSiblings !== null && _remotionInternalCanvasSiblings !== void 0 ? _remotionInternalCanvasSiblings : null, controls: controls, style: croppedStyle !== null && croppedStyle !== void 0 ? croppedStyle : undefined, children: children }) }) }));
});
HtmlInCanvasInner.displayName = 'HtmlInCanvas';
exports.htmlInCanvasSchema = {
    ...interactivity_schema_js_1.baseSchema,
    ...interactivity_schema_js_1.premountSchema,
    pixelDensity: {
        type: 'number',
        min: 1,
        max: 3,
        step: 0.1,
        default: 1,
        description: 'Pixel density',
        hiddenFromList: false,
    },
    ...interactivity_schema_js_1.transformSchema,
    ...interactivity_schema_js_1.backgroundSchema,
    ...interactivity_schema_js_1.borderSchema,
    ...interactivity_schema_js_1.borderRadiusSchema,
    ...interactivity_schema_js_1.cropSchema,
};
const HtmlInCanvasWrapped = (0, with_interactivity_schema_js_1.withInteractivitySchema)({
    Component: HtmlInCanvasInner,
    componentName: '<HtmlInCanvas>',
    componentIdentity: 'dev.remotion.remotion.HtmlInCanvas',
    schema: exports.htmlInCanvasSchema,
    supportsEffects: true,
});
exports.HtmlInCanvas = Object.assign(HtmlInCanvasWrapped, {
    isSupported: exports.isHtmlInCanvasSupported,
    isNestingSupported: exports.isHtmlInCanvasNestingSupported,
});
exports.HtmlInCanvas.displayName = 'HtmlInCanvas';
(0, enable_sequence_stack_traces_js_1.addSequenceStackTraces)(exports.HtmlInCanvas);
