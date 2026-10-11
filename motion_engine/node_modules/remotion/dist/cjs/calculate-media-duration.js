"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getMediaTrimAfter = exports.calculateMediaDuration = void 0;
const calculateMediaDuration = ({ trimAfter, mediaDurationInFrames, playbackRate, trimBefore, }) => {
    let duration = mediaDurationInFrames;
    // Account for trimAfter
    if (typeof trimAfter !== 'undefined') {
        duration = trimAfter;
    }
    // Account for trimBefore
    if (typeof trimBefore !== 'undefined') {
        duration -= trimBefore;
    }
    return duration / playbackRate;
};
exports.calculateMediaDuration = calculateMediaDuration;
const getMediaTrimAfter = ({ durationInFrames, trimAfter, trimBefore, }) => {
    const durationAsTrimAfter = durationInFrames === undefined
        ? undefined
        : (trimBefore !== null && trimBefore !== void 0 ? trimBefore : 0) + durationInFrames;
    if (durationAsTrimAfter === undefined) {
        return trimAfter;
    }
    return trimAfter === undefined
        ? durationAsTrimAfter
        : Math.min(trimAfter, durationAsTrimAfter);
};
exports.getMediaTrimAfter = getMediaTrimAfter;
