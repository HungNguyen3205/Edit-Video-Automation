"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveSequenceDuration = exports.resolveSequenceContentDuration = void 0;
const resolveSequenceContentDuration = ({ durationInFrames, }) => {
    return durationInFrames !== null && durationInFrames !== void 0 ? durationInFrames : Infinity;
};
exports.resolveSequenceContentDuration = resolveSequenceContentDuration;
// Length of an item in its parent timeline. `durationInFrames` is measured in
// the child clock.
const resolveSequenceDuration = ({ durationInFrames, playbackRate, loop, }) => {
    if (loop) {
        return Infinity;
    }
    return ((0, exports.resolveSequenceContentDuration)({
        durationInFrames,
    }) / (playbackRate !== null && playbackRate !== void 0 ? playbackRate : 1));
};
exports.resolveSequenceDuration = resolveSequenceDuration;
