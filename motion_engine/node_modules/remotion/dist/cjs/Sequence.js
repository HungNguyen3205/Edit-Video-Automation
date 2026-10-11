"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SequenceWithoutFrom = exports.Sequence = exports.SequenceWithoutSchema = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
/* eslint-disable @typescript-eslint/no-use-before-define */
const react_1 = require("react");
const AbsoluteFillElement_js_1 = require("./AbsoluteFillElement.js");
const enable_sequence_stack_traces_js_1 = require("./enable-sequence-stack-traces.js");
const freeze_js_1 = require("./freeze.js");
const get_sequence_boundary_tolerance_js_1 = require("./get-sequence-boundary-tolerance.js");
const interactivity_schema_js_1 = require("./interactivity-schema.js");
const loop_context_js_1 = require("./loop/loop-context.js");
const resolve_sequence_duration_js_1 = require("./resolve-sequence-duration.js");
const sequence_crop_js_1 = require("./sequence-crop.js");
const sequence_order_marker_js_1 = require("./sequence-order-marker.js");
const sequence_outline_js_1 = require("./sequence-outline.js");
const SequenceContext_js_1 = require("./SequenceContext.js");
const SequenceManager_js_1 = require("./SequenceManager.js");
const is_inside_series_js_1 = require("./series/is-inside-series.js");
const timeline_position_state_js_1 = require("./timeline-position-state.js");
const timeline_track_context_js_1 = require("./timeline-track-context.js");
const use_premounting_js_1 = require("./use-premounting.js");
const use_remotion_environment_js_1 = require("./use-remotion-environment.js");
const use_sequence_registration_js_1 = require("./use-sequence-registration.js");
const use_video_config_js_1 = require("./use-video-config.js");
const v5_flag_js_1 = require("./v5-flag.js");
const with_interactivity_schema_js_1 = require("./with-interactivity-schema.js");
const SeriesContentVisibilityContext = (0, react_1.createContext)(true);
const EMPTY_EFFECTS = [];
const RegularSequenceRefForwardingFunction = ({ from = 0, trimBefore = 0, playbackRate = 1, loop = false, freeze, durationInFrames, children, name, height, width, showInTimeline = true, hidden = false, controls, _remotionInternalEffects, _remotionInternalTimelineTrack: timelineTrackItem, _remotionInternalLoopDisplay: loopDisplay, _remotionInternalStack: stack, _remotionInternalDocumentationLink: documentationLink, _remotionInternalSingleChildComponent: singleChildComponent, _remotionInternalPremountDisplay: premountDisplay, _remotionInternalPostmountDisplay: postmountDisplay, _remotionInternalIsMedia: isMedia, outlineRef: passedRefForOutline, cropLeft, cropRight, cropTop, cropBottom, ...other }, ref) => {
    var _a, _b, _c, _d, _e, _f;
    const { layout = 'absolute-fill' } = other;
    const [id] = (0, react_1.useState)(() => String(Math.random()));
    const parentSequence = (0, react_1.useContext)(SequenceContext_js_1.SequenceContext);
    const timelineTrack = (0, react_1.useContext)(timeline_track_context_js_1.TimelineTrackContext);
    const timelineTrackRole = (_a = timelineTrackItem === null || timelineTrackItem === void 0 ? void 0 : timelineTrackItem.role) !== null && _a !== void 0 ? _a : 'clip';
    const parentPlaybackRate = (_b = parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.playbackRate) !== null && _b !== void 0 ? _b : 1;
    const cumulativePlaybackRate = parentPlaybackRate * playbackRate;
    const cumulatedFrom = parentSequence
        ? parentSequence.cumulatedFrom + parentSequence.relativeFrom
        : 0;
    if (layout !== 'absolute-fill' && layout !== 'none') {
        throw new TypeError(`The layout prop of <Sequence /> expects either "absolute-fill" or "none", but you passed: ${layout}`);
    }
    const cropProps = { cropLeft, cropRight, cropTop, cropBottom };
    const hasCropProp = Object.values(cropProps).some((value) => value !== undefined);
    if (layout === 'none' && hasCropProp) {
        throw new TypeError('The cropLeft, cropRight, cropTop and cropBottom props of <Sequence /> are only supported with layout="absolute-fill".');
    }
    (0, sequence_crop_js_1.validateSequenceCrop)(cropProps);
    const { left: resolvedCropLeft, right: resolvedCropRight, top: resolvedCropTop, bottom: resolvedCropBottom, } = (0, sequence_crop_js_1.resolveSequenceCrop)(cropProps);
    // @ts-expect-error
    if (layout === 'none' && typeof other.style !== 'undefined') {
        throw new TypeError('If layout="none", you may not pass a style. Passed: ' +
            // @ts-expect-error
            JSON.stringify(other.style));
    }
    const contentDurationInFrames = (0, resolve_sequence_duration_js_1.resolveSequenceContentDuration)({
        durationInFrames,
    });
    if (typeof contentDurationInFrames !== 'number') {
        throw new TypeError(`You passed to durationInFrames an argument of type ${typeof contentDurationInFrames}, but it must be a number.`);
    }
    if (contentDurationInFrames <= 0) {
        throw new TypeError(`durationInFrames must be positive, but got ${contentDurationInFrames}`);
    }
    if (typeof from !== 'number') {
        throw new TypeError(`You passed to the "from" props of your <Sequence> an argument of type ${typeof from}, but it must be a number.`);
    }
    if (!Number.isFinite(from)) {
        throw new TypeError(`The "from" prop of a sequence must be finite, but got ${from}.`);
    }
    if (typeof trimBefore !== 'number') {
        throw new TypeError(`You passed to the "trimBefore" prop of your <Sequence> an argument of type ${typeof trimBefore}, but it must be a number.`);
    }
    if (trimBefore < 0) {
        throw new TypeError(`The "trimBefore" prop of <Sequence /> must be greater than or equal to 0, but got ${trimBefore}.`);
    }
    if (Number.isNaN(trimBefore)) {
        throw new TypeError('The "trimBefore" prop of <Sequence /> must be a real number, but it is NaN.');
    }
    if (!Number.isFinite(trimBefore)) {
        throw new TypeError(`The "trimBefore" prop of <Sequence /> must be finite, but it is ${trimBefore}.`);
    }
    if (typeof loop !== 'boolean') {
        throw new TypeError(`The "loop" prop of <Sequence /> must be a boolean, but is of type ${typeof loop}.`);
    }
    if (loop && !Number.isFinite(contentDurationInFrames)) {
        throw new Error('The "loop" prop of <Sequence /> requires a finite "durationInFrames" prop, because a <Sequence /> has no intrinsic duration.');
    }
    if (typeof freeze !== 'undefined' && freeze !== null) {
        if (typeof freeze !== 'number') {
            throw new TypeError(`The "freeze" prop of <Sequence /> must be a number, but is of type ${typeof freeze}.`);
        }
        if (Number.isNaN(freeze)) {
            throw new TypeError(`The "freeze" prop of <Sequence /> must be a real number, but it is NaN.`);
        }
        if (!Number.isFinite(freeze)) {
            throw new TypeError(`The "freeze" prop of <Sequence /> must be finite, but it is ${freeze}.`);
        }
    }
    const absoluteFrame = (0, timeline_position_state_js_1.useTimelinePosition)();
    const lastPlaybackRate = (0, react_1.useRef)({ playbackRate, frame: absoluteFrame });
    if (typeof playbackRate !== 'number' ||
        !Number.isFinite(playbackRate) ||
        playbackRate <= 0) {
        throw new TypeError(`The "playbackRate" prop of <Sequence /> must be a positive finite number, but got ${playbackRate}.`);
    }
    if (lastPlaybackRate.current.frame !== absoluteFrame &&
        lastPlaybackRate.current.playbackRate !== playbackRate) {
        throw new Error('The "playbackRate" prop of <Sequence /> must be constant. Animating playbackRate is not supported.');
    }
    lastPlaybackRate.current = { playbackRate, frame: absoluteFrame };
    const videoConfig = (0, use_video_config_js_1.useVideoConfig)();
    const effectiveDurationInFrames = (0, resolve_sequence_duration_js_1.resolveSequenceDuration)({
        durationInFrames,
        playbackRate,
        loop,
    });
    const windowRelativeFrom = from - trimBefore / playbackRate;
    const parentSequenceDuration = parentSequence
        ? Math.min(parentSequence.durationInFrames - windowRelativeFrom, effectiveDurationInFrames)
        : effectiveDurationInFrames;
    const actualDurationInFrames = Math.max(0, Math.min(videoConfig.durationInFrames - from, parentSequenceDuration));
    // A looped sequence repeats the child range selected by `durationInFrames`. Each
    // iteration lasts `loopPeriod` parent frames and moves the clock origin,
    // while the visible window stays at [from, from + effectiveDurationInFrames).
    const frameInParent = (absoluteFrame - cumulatedFrom) * parentPlaybackRate;
    const loopPeriod = loop && Number.isFinite(contentDurationInFrames)
        ? contentDurationInFrames / playbackRate
        : null;
    let loopIteration = 0;
    if (loopPeriod !== null) {
        const loopsElapsed = (frameInParent - from) / loopPeriod;
        const nearestIteration = Math.round(loopsElapsed);
        // Fractional periods and nested playback rates can put an exact loop
        // boundary a few floating-point units before the next iteration.
        const isAtBoundary = Math.abs(loopsElapsed - nearestIteration) <=
            Number.EPSILON * Math.max(1, Math.abs(loopsElapsed)) * 4;
        const lastIteration = Math.ceil(actualDurationInFrames / loopPeriod) - 1;
        loopIteration = Math.max(0, Math.min(lastIteration, isAtBoundary ? nearestIteration : Math.floor(loopsElapsed)));
    }
    const loopOffset = loopPeriod === null ? 0 : loopIteration * loopPeriod;
    const clockFrom = from + loopOffset;
    const effectiveRelativeFrom = clockFrom - trimBefore / playbackRate;
    const relativeFrom = effectiveRelativeFrom / parentPlaybackRate;
    const absoluteFrom = ((_c = parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.absoluteFrom) !== null && _c !== void 0 ? _c : 0) + relativeFrom;
    // Inside a loop, the local clock ends after `durationInFrames`, except in a final
    // iteration that the parent cuts short.
    const localClockEnd = loopPeriod === null
        ? actualDurationInFrames * playbackRate + trimBefore
        : Math.min(loopPeriod, actualDurationInFrames - loopOffset) *
            playbackRate +
            trimBefore;
    const sequenceRegistrationEnabled = (0, react_1.useContext)(SequenceManager_js_1.SequenceRegistrationContext);
    const canvasOutlinesEnabled = (0, react_1.useContext)(sequence_outline_js_1.SequenceOutlineContext);
    const env = (0, use_remotion_environment_js_1.useRemotionEnvironment)();
    const shouldDiscoverOutline = env.isStudio || canvasOutlinesEnabled;
    const automaticOutlineRef = (0, react_1.useMemo)(() => shouldDiscoverOutline && layout === 'none' && !passedRefForOutline
        ? sequence_outline_js_1.SequenceOutlineInternals.createRef()
        : null, [shouldDiscoverOutline, layout, passedRefForOutline]);
    const wrapperRefForOutline = (0, react_1.useRef)(null);
    const refForOutline = other.layout === 'none'
        ? (passedRefForOutline !== null && passedRefForOutline !== void 0 ? passedRefForOutline : automaticOutlineRef)
        : (passedRefForOutline !== null && passedRefForOutline !== void 0 ? passedRefForOutline : wrapperRefForOutline);
    const premounting = (0, react_1.useMemo)(() => {
        // || is intentional, ?? would not trigger on `false`
        return ((parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.premounting) ||
            Boolean(other._remotionInternalIsPremounting));
    }, [other._remotionInternalIsPremounting, parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.premounting]);
    const postmounting = (0, react_1.useMemo)(() => {
        // || is intentional, ?? would not trigger on `false`
        return ((parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.postmounting) ||
            Boolean(other._remotionInternalIsPostmounting));
    }, [other._remotionInternalIsPostmounting, parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.postmounting]);
    // `cumulatedNegativeFrom` answers: "How many frames of this media have
    // already elapsed before the first visible frame of this sequence?"
    //
    // This is intentionally based on the effective sequence start, not on adding
    // all negative `from` values. See the asset-calculation tests for:
    // - "Should calculate startFrom correctly with negative offset (Html5Audio)"
    // - "same as above, but with <Sequence from={0}> inbetween"
    // - "same as above, but a positive child offset cancels part of the negative parent offset"
    //
    // In particular, <Sequence from={-20}><Sequence from={10}> should have a
    // 10-frame pre-roll, because the positive child offset cancels part of the
    // negative parent offset. But <Sequence from={10}><Sequence from={-5}>
    // should still trim 5 frames from the media once the parent starts.
    const currentSequenceStart = cumulatedFrom + relativeFrom;
    const parentSequenceStart = parentSequence
        ? parentSequence.cumulatedFrom + parentSequence.relativeFrom
        : 0;
    const parentFirstFrame = parentSequence
        ? parentSequenceStart -
            parentSequence.cumulatedNegativeFrom / parentPlaybackRate
        : 0;
    const firstFrame = Math.max(0, parentFirstFrame, cumulatedFrom + clockFrom / parentPlaybackRate);
    const cumulatedNegativeFrom = (currentSequenceStart - firstFrame) * cumulativePlaybackRate;
    const contextValue = (0, react_1.useMemo)(() => {
        var _a, _b, _c;
        return {
            playbackRate: cumulativePlaybackRate,
            absoluteFrom,
            cumulatedFrom,
            relativeFrom,
            cumulatedNegativeFrom,
            durationInFrames: localClockEnd,
            parentFrom: (_a = parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.relativeFrom) !== null && _a !== void 0 ? _a : 0,
            id,
            height: (_b = height !== null && height !== void 0 ? height : parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.height) !== null && _b !== void 0 ? _b : null,
            width: (_c = width !== null && width !== void 0 ? width : parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.width) !== null && _c !== void 0 ? _c : null,
            premounting,
            postmounting,
            premountDisplay: premountDisplay !== null && premountDisplay !== void 0 ? premountDisplay : null,
            postmountDisplay: postmountDisplay !== null && postmountDisplay !== void 0 ? postmountDisplay : null,
        };
    }, [
        cumulatedFrom,
        absoluteFrom,
        relativeFrom,
        cumulativePlaybackRate,
        localClockEnd,
        parentSequence,
        id,
        height,
        width,
        premounting,
        postmounting,
        premountDisplay,
        postmountDisplay,
        cumulatedNegativeFrom,
    ]);
    const loopContextValue = (0, react_1.useMemo)(() => {
        if (loopPeriod === null) {
            return null;
        }
        return {
            iteration: loopIteration,
            durationInFrames: contentDurationInFrames,
        };
    }, [contentDurationInFrames, loopIteration, loopPeriod]);
    const resolvedLoopDisplay = (0, react_1.useMemo)(() => {
        if (loopDisplay || loopPeriod === null) {
            return loopDisplay;
        }
        return {
            numberOfTimes: actualDurationInFrames / loopPeriod,
            startOffset: 0,
            durationInFrames: loopPeriod,
        };
    }, [actualDurationInFrames, loopDisplay, loopPeriod]);
    const timelineClipName = (0, react_1.useMemo)(() => {
        return name !== null && name !== void 0 ? name : '';
    }, [name]);
    const resolvedDocumentationLink = documentationLink !== null && documentationLink !== void 0 ? documentationLink : 'https://www.remotion.dev/docs/sequence';
    const isInsideSeries = (0, react_1.useContext)(is_inside_series_js_1.IsInsideSeriesContext);
    // Our assumption: Stack doesnt' change. After we symbolicate we assign it a nodePath
    // and if it changes, it would lead to-remounting of the sequence.
    const stackRef = (0, react_1.useRef)(null);
    stackRef.current = controls
        ? ((_e = (_d = (0, enable_sequence_stack_traces_js_1.getStackForControls)(controls)) !== null && _d !== void 0 ? _d : stack) !== null && _e !== void 0 ? _e : null)
        : (stack !== null && stack !== void 0 ? stack : null);
    const getStack = (0, react_1.useCallback)(() => stackRef.current, []);
    const registeredFrozenFrame = typeof freeze === 'number' ? freeze : null;
    const currentFrame = registeredFrozenFrame !== null && registeredFrozenFrame !== void 0 ? registeredFrozenFrame : (absoluteFrame - currentSequenceStart) * cumulativePlaybackRate;
    const currentFrameRef = (0, react_1.useRef)(currentFrame);
    (0, react_1.useLayoutEffect)(() => {
        currentFrameRef.current = currentFrame;
    }, [currentFrame]);
    const getCurrentFrame = (0, react_1.useCallback)(() => currentFrameRef.current, []);
    const registeredTrimBefore = trimBefore === 0 ? null : trimBefore;
    const parentCumulatedNegativeFrom = (_f = parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.cumulatedNegativeFrom) !== null && _f !== void 0 ? _f : 0;
    const startMediaFrom = isMedia && isMedia.type !== 'image'
        ? isMedia.data.startMediaFrom +
            parentCumulatedNegativeFrom -
            cumulatedNegativeFrom
        : null;
    const mediaFrameAtSequenceZero = isMedia && isMedia.type !== 'image'
        ? isMedia.data.startMediaFrom + parentCumulatedNegativeFrom
        : null;
    const frozenMediaFrame = isMedia && isMedia.type !== 'image' && mediaFrameAtSequenceZero !== null
        ? registeredFrozenFrame === null
            ? null
            : mediaFrameAtSequenceZero +
                (resolvedLoopDisplay
                    ? registeredFrozenFrame % resolvedLoopDisplay.durationInFrames
                    : registeredFrozenFrame) *
                    isMedia.data.playbackRate
        : null;
    const controlsSchema = controls === null || controls === void 0 ? void 0 : controls.schema;
    const controlsRuntimeValues = controls === null || controls === void 0 ? void 0 : controls.runtimeValues;
    const controlsOverrideId = controls === null || controls === void 0 ? void 0 : controls.overrideId;
    const controlsSupportsEffects = controls === null || controls === void 0 ? void 0 : controls.supportsEffects;
    const controlsComponentIdentity = controls === null || controls === void 0 ? void 0 : controls.componentIdentity;
    const controlsComponentName = controls === null || controls === void 0 ? void 0 : controls.componentName;
    const controlsVideoConfigValues = controls === null || controls === void 0 ? void 0 : controls.videoConfigValues;
    const isInsideNonPremountFreeze = (0, freeze_js_1.useIsInsideNonPremountFreeze)();
    const canInferDuration = (controlsComponentIdentity === 'dev.remotion.remotion.Series' ||
        controlsComponentIdentity ===
            'dev.remotion.transitions.TransitionSeries') &&
        !loop &&
        registeredFrozenFrame === null &&
        !isInsideNonPremountFreeze &&
        !hidden;
    const autoDuration = canInferDuration && durationInFrames === undefined;
    const isSeriesChild = controlsComponentIdentity === 'dev.remotion.remotion.Series.Sequence' ||
        controlsComponentIdentity ===
            'dev.remotion.transitions.TransitionSeries.Sequence' ||
        controlsComponentIdentity ===
            'dev.remotion.transitions.TransitionSeries.Transition' ||
        controlsComponentIdentity ===
            'dev.remotion.transitions.TransitionSeries.Overlay';
    const seriesContentVisible = (0, react_1.useContext)(SeriesContentVisibilityContext);
    const effectRuntimeValues = (0, react_1.useMemo)(() => {
        var _a;
        return (_a = _remotionInternalEffects === null || _remotionInternalEffects === void 0 ? void 0 : _remotionInternalEffects.runtimeValues) !== null && _a !== void 0 ? _a : null;
    }, [_remotionInternalEffects]);
    const registrationControls = (0, react_1.useMemo)(() => {
        if (controlsSchema === undefined ||
            controlsRuntimeValues === undefined ||
            controlsOverrideId === undefined ||
            controlsSupportsEffects === undefined ||
            controlsComponentIdentity === undefined ||
            controlsComponentName === undefined ||
            controlsVideoConfigValues === undefined) {
            return null;
        }
        return {
            schema: controlsSchema,
            runtimeValues: controlsRuntimeValues,
            overrideId: controlsOverrideId,
            supportsEffects: controlsSupportsEffects,
            componentIdentity: controlsComponentIdentity,
            componentName: controlsComponentName,
            videoConfigValues: controlsVideoConfigValues,
        };
    }, [
        controlsComponentIdentity,
        controlsComponentName,
        controlsVideoConfigValues,
        controlsOverrideId,
        controlsRuntimeValues,
        controlsSchema,
        controlsSupportsEffects,
    ]);
    const getSequenceForRegistration = (0, react_1.useCallback)(() => {
        var _a, _b, _c;
        const trackRegistration = timelineTrack
            ? {
                timelineTrack: {
                    ...timelineTrack,
                    role: timelineTrackRole,
                },
            }
            : {};
        if (isMedia) {
            if (isMedia.type === 'image') {
                return {
                    ...trackRegistration,
                    sequencePlaybackRate: playbackRate,
                    type: 'image',
                    controls: registrationControls,
                    effects: _remotionInternalEffects !== null && _remotionInternalEffects !== void 0 ? _remotionInternalEffects : EMPTY_EFFECTS,
                    effectRuntimeValues,
                    displayName: timelineClipName,
                    documentationLink: resolvedDocumentationLink,
                    duration: actualDurationInFrames,
                    from,
                    trimBefore: registeredTrimBefore,
                    id,
                    loopDisplay: resolvedLoopDisplay,
                    parent: (_a = parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.id) !== null && _a !== void 0 ? _a : null,
                    postmountDisplay: postmountDisplay !== null && postmountDisplay !== void 0 ? postmountDisplay : null,
                    premountDisplay: premountDisplay !== null && premountDisplay !== void 0 ? premountDisplay : null,
                    showInTimeline,
                    timelineOrder: null,
                    src: isMedia.src,
                    getStack,
                    getCurrentFrame,
                    refForOutline: refForOutline !== null && refForOutline !== void 0 ? refForOutline : null,
                    isInsideSeries,
                    frozenFrame: registeredFrozenFrame,
                    singleChildComponent: singleChildComponent !== null && singleChildComponent !== void 0 ? singleChildComponent : null,
                };
            }
            return {
                ...trackRegistration,
                type: isMedia.type,
                sequencePlaybackRate: playbackRate,
                controls: registrationControls,
                effects: _remotionInternalEffects !== null && _remotionInternalEffects !== void 0 ? _remotionInternalEffects : EMPTY_EFFECTS,
                effectRuntimeValues,
                displayName: timelineClipName,
                documentationLink: resolvedDocumentationLink,
                doesVolumeChange: isMedia.data.doesVolumeChange,
                duration: actualDurationInFrames,
                from,
                trimBefore: registeredTrimBefore,
                id,
                loopDisplay: resolvedLoopDisplay,
                parent: (_b = parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.id) !== null && _b !== void 0 ? _b : null,
                playbackRate: isMedia.data.playbackRate,
                postmountDisplay: postmountDisplay !== null && postmountDisplay !== void 0 ? postmountDisplay : null,
                premountDisplay: premountDisplay !== null && premountDisplay !== void 0 ? premountDisplay : null,
                showInTimeline,
                timelineOrder: null,
                src: isMedia.data.src,
                getStack,
                getCurrentFrame,
                startMediaFrom: startMediaFrom !== null && startMediaFrom !== void 0 ? startMediaFrom : isMedia.data.startMediaFrom,
                mediaFrameAtSequenceZero,
                volume: isMedia.data.volumes,
                muted: isMedia.data.muted,
                refForOutline: refForOutline !== null && refForOutline !== void 0 ? refForOutline : null,
                isInsideSeries,
                frozenFrame: registeredFrozenFrame,
                frozenMediaFrame,
                singleChildComponent: singleChildComponent !== null && singleChildComponent !== void 0 ? singleChildComponent : null,
            };
        }
        return {
            ...trackRegistration,
            from,
            sequencePlaybackRate: playbackRate,
            trimBefore: registeredTrimBefore,
            duration: actualDurationInFrames,
            ...(autoDuration ? { autoDuration: true } : {}),
            ...(canInferDuration ? { canInferDuration: true } : {}),
            ...(isSeriesChild ? { unclippedDuration: effectiveDurationInFrames } : {}),
            id,
            displayName: timelineClipName,
            documentationLink: resolvedDocumentationLink,
            parent: (_c = parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.id) !== null && _c !== void 0 ? _c : null,
            type: 'sequence',
            showInTimeline,
            timelineOrder: null,
            loopDisplay: resolvedLoopDisplay,
            getStack,
            getCurrentFrame,
            premountDisplay: premountDisplay !== null && premountDisplay !== void 0 ? premountDisplay : null,
            postmountDisplay: postmountDisplay !== null && postmountDisplay !== void 0 ? postmountDisplay : null,
            controls: registrationControls,
            effects: _remotionInternalEffects !== null && _remotionInternalEffects !== void 0 ? _remotionInternalEffects : EMPTY_EFFECTS,
            effectRuntimeValues,
            refForOutline: refForOutline !== null && refForOutline !== void 0 ? refForOutline : null,
            isInsideSeries,
            frozenFrame: registeredFrozenFrame,
            singleChildComponent: singleChildComponent !== null && singleChildComponent !== void 0 ? singleChildComponent : null,
        };
    }, [
        id,
        timelineTrack,
        timelineTrackRole,
        getCurrentFrame,
        getStack,
        timelineClipName,
        playbackRate,
        parentSequence === null || parentSequence === void 0 ? void 0 : parentSequence.id,
        actualDurationInFrames,
        autoDuration,
        canInferDuration,
        isSeriesChild,
        effectiveDurationInFrames,
        from,
        registeredTrimBefore,
        showInTimeline,
        resolvedLoopDisplay,
        premountDisplay,
        postmountDisplay,
        registrationControls,
        _remotionInternalEffects,
        effectRuntimeValues,
        isMedia,
        resolvedDocumentationLink,
        refForOutline,
        isInsideSeries,
        registeredFrozenFrame,
        startMediaFrom,
        mediaFrameAtSequenceZero,
        frozenMediaFrame,
        singleChildComponent,
    ]);
    (0, use_sequence_registration_js_1.useSequenceRegistration)({
        getSequence: env.isStudio || sequenceRegistrationEnabled
            ? getSequenceForRegistration
            : null,
        id,
    });
    // Use an exclusive end so fractional clocks and frozen subframes remain visible.
    const endThreshold = from + effectiveDurationInFrames;
    const boundaryTolerance = (0, get_sequence_boundary_tolerance_js_1.getSequenceBoundaryTolerance)({
        absoluteFrame,
        cumulatedFrom,
        from,
        parentPlaybackRate,
        durationInFrames: effectiveDurationInFrames,
    });
    const content = !seriesContentVisible || frameInParent - from < -boundaryTolerance
        ? null
        : frameInParent - endThreshold >= -boundaryTolerance
            ? null
            : children;
    const frozenContent = content === null || typeof freeze === 'undefined' || freeze === null ? (content) : (jsx_runtime_1.jsx(freeze_js_1.Freeze, { frame: freeze, children: content }));
    const loopedContent = frozenContent === null || loopContextValue === null ? (frozenContent) : (jsx_runtime_1.jsx(loop_context_js_1.LoopContext.Provider, { value: loopContextValue, children: frozenContent }));
    const styleIfThere = other.layout === 'none' ? undefined : other.style;
    const cropClipPath = (0, sequence_crop_js_1.getSequenceCropClipPath)({
        left: resolvedCropLeft,
        right: resolvedCropRight,
        top: resolvedCropTop,
        bottom: resolvedCropBottom,
        style: styleIfThere,
    });
    const sequenceRef = (0, react_1.useCallback)((node) => {
        wrapperRefForOutline.current = node;
        if (typeof ref === 'function') {
            ref(node);
        }
        else if (ref) {
            ref.current = node;
        }
    }, [ref]);
    const defaultStyle = (0, react_1.useMemo)(() => {
        return {
            flexDirection: undefined,
            ...(width ? { width } : {}),
            ...(height ? { height } : {}),
            ...(styleIfThere !== null && styleIfThere !== void 0 ? styleIfThere : {}),
            ...(cropClipPath
                ? {
                    clipPath: cropClipPath,
                }
                : {}),
        };
    }, [cropClipPath, height, styleIfThere, width]);
    if (ref !== null && layout === 'none') {
        throw new TypeError('It is not supported to pass both a `ref` and `layout="none"` to <Sequence />.');
    }
    if (hidden) {
        return shouldDiscoverOutline ? (jsx_runtime_1.jsx(sequence_order_marker_js_1.SequenceOrderMarker, { sequenceId: id, outlineChildrenRef: automaticOutlineRef, children: null })) : null;
    }
    // Retain resolved scene registrations so Studio can recover the natural end
    // even when seeking past an explicit wrapper trim. Scene contents stay hidden.
    const retainSeriesRegistration = env.isStudio && canInferDuration;
    const renderedContent = loopedContent === null ? (retainSeriesRegistration ? (children) : null) : other.layout === 'none' ? (loopedContent) : (jsx_runtime_1.jsx(AbsoluteFillElement_js_1.AbsoluteFillElement, { ref: sequenceRef, style: defaultStyle, className: other.className, children: loopedContent }));
    const sequenceContent = (jsx_runtime_1.jsx(SequenceContext_js_1.SequenceContext.Provider, { value: contextValue, children: retainSeriesRegistration ? (jsx_runtime_1.jsx(SeriesContentVisibilityContext.Provider, { value: content !== null, children: renderedContent })) : (renderedContent) }));
    // Keep the provider mounted when track grouping changes so clip state survives.
    const sequence = (jsx_runtime_1.jsx(timeline_track_context_js_1.TimelineTrackContext.Provider, { value: timelineTrackRole === 'track' ||
            (timelineTrackRole === 'clip' && !showInTimeline)
            ? timelineTrack
            : null, children: sequenceContent }));
    return shouldDiscoverOutline ? (jsx_runtime_1.jsx(sequence_order_marker_js_1.SequenceOrderMarker, { sequenceId: id, outlineChildrenRef: automaticOutlineRef, children: sequence })) : (sequence);
};
const RegularSequence = (0, react_1.forwardRef)(RegularSequenceRefForwardingFunction);
const PremountedPostmountedSequenceRefForwardingFunction = (props, ref) => {
    if (props.layout === 'none') {
        throw new Error('`<Sequence>` with `premountFor` and `postmountFor` props does not support layout="none"');
    }
    const { style: passedStyle, from = 0, durationInFrames, premountFor = 0, postmountFor = 0, styleWhilePremounted, styleWhilePostmounted, ...otherProps } = props;
    const { freezeFrame, isPremountingOrPostmounting, postmountingActive, premountingActive, premountingStyle, } = (0, use_premounting_js_1.usePremounting)({
        from,
        durationInFrames: (0, resolve_sequence_duration_js_1.resolveSequenceDuration)({
            durationInFrames,
            playbackRate: otherProps.playbackRate,
            loop: otherProps.loop,
        }),
        premountFor,
        postmountFor,
        style: passedStyle !== null && passedStyle !== void 0 ? passedStyle : null,
        styleWhilePremounted: styleWhilePremounted !== null && styleWhilePremounted !== void 0 ? styleWhilePremounted : null,
        styleWhilePostmounted: styleWhilePostmounted !== null && styleWhilePostmounted !== void 0 ? styleWhilePostmounted : null,
        hideWhilePremounted: 'opacity',
    });
    return (jsx_runtime_1.jsx(freeze_js_1.Freeze, { frame: freezeFrame, active: isPremountingOrPostmounting, _remotionInternalIsPremounting: premountingActive, children: jsx_runtime_1.jsx(SequenceInner, { ref: ref, from: from, durationInFrames: durationInFrames, style: premountingStyle !== null && premountingStyle !== void 0 ? premountingStyle : undefined, _remotionInternalPremountDisplay: premountFor, _remotionInternalPostmountDisplay: postmountFor, _remotionInternalIsPremounting: premountingActive, _remotionInternalIsPostmounting: postmountingActive, ...otherProps }) }));
};
const PremountedPostmountedSequence = (0, react_1.forwardRef)(PremountedPostmountedSequenceRefForwardingFunction);
const SequenceRefForwardingFunction = (props, ref) => {
    var _a;
    const env = (0, use_remotion_environment_js_1.useRemotionEnvironment)();
    const { fps } = (0, use_video_config_js_1.useVideoConfig)();
    if (props.layout !== 'none' && !env.isRendering) {
        const effectivePremountFor = v5_flag_js_1.ENABLE_V5_BREAKING_CHANGES
            ? ((_a = props.premountFor) !== null && _a !== void 0 ? _a : fps)
            : props.premountFor;
        if (effectivePremountFor || props.postmountFor) {
            return (jsx_runtime_1.jsx(PremountedPostmountedSequence, { ref: ref, ...props, premountFor: effectivePremountFor }));
        }
    }
    return jsx_runtime_1.jsx(RegularSequence, { ...props, ref: ref });
};
const SequenceInner = (0, react_1.forwardRef)(SequenceRefForwardingFunction);
exports.SequenceWithoutSchema = SequenceInner;
/*
 * @description A component that time-shifts its children and wraps them in an absolutely positioned <div>.
 * @see [Documentation](https://www.remotion.dev/docs/sequence)
 */
exports.Sequence = (0, with_interactivity_schema_js_1.withInteractivitySchema)({
    Component: SequenceInner,
    componentName: '<Sequence>',
    componentIdentity: 'dev.remotion.remotion.Sequence',
    schema: interactivity_schema_js_1.sequenceSchema,
    supportsEffects: false,
});
exports.SequenceWithoutFrom = (0, with_interactivity_schema_js_1.withInteractivitySchema)({
    Component: SequenceInner,
    componentName: '<Sequence>',
    componentIdentity: null,
    schema: interactivity_schema_js_1.sequenceSchemaWithoutFrom,
    supportsEffects: false,
});
