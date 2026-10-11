"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.evaluateSourcePropStatuses = exports.evaluateSourceNumericValue = void 0;
const evaluateSourceNumericValue = (expression, config) => {
    var _a;
    if (typeof expression === 'number') {
        return expression;
    }
    if (expression.type === 'literal') {
        return expression.value;
    }
    if (expression.type === 'binary') {
        const left = (0, exports.evaluateSourceNumericValue)(expression.left, config);
        const right = (0, exports.evaluateSourceNumericValue)(expression.right, config);
        switch (expression.operator) {
            case '+':
                return left + right;
            case '-':
                return left - right;
            case '*':
                return left * right;
            case '/':
                return left / right;
            default:
                throw new Error('Unknown source expression operator');
        }
    }
    const value = expression.binding.type === 'constant'
        ? expression.binding.value
        : ((_a = config === null || config === void 0 ? void 0 : config[expression.binding.field]) !== null && _a !== void 0 ? _a : NaN);
    if (expression.type === 'video-config-multiplication') {
        return value * expression.multiplier;
    }
    if (expression.type === 'video-config-subtraction') {
        return value - expression.subtrahend;
    }
    return value;
};
exports.evaluateSourceNumericValue = evaluateSourceNumericValue;
const evaluatedProps = new WeakMap();
/** Resolve at the consumer, never in the shared source subscription cache. */
const evaluateSourcePropStatuses = (props, config) => {
    var _a;
    const configKey = config === null
        ? ''
        : `${config.durationInFrames}:${config.fps}:${config.width}:${config.height}`;
    const cached = (_a = evaluatedProps.get(props)) !== null && _a !== void 0 ? _a : new Map();
    const existing = cached.get(configKey);
    if (existing)
        return existing;
    const result = Object.fromEntries(Object.entries(props).map(([key, status]) => {
        var _a;
        if (status.status === 'computed') {
            return [key, status];
        }
        const adjustment = status.keyframeDisplayOffsetAdjustment === null
            ? null
            : (0, exports.evaluateSourceNumericValue)(status.keyframeDisplayOffsetAdjustment, config);
        const rate = (0, exports.evaluateSourceNumericValue)((_a = status.keyframePlaybackRateAdjustment) !== null && _a !== void 0 ? _a : 1, config);
        if ((adjustment !== null && !Number.isFinite(adjustment)) ||
            !Number.isFinite(rate) ||
            rate <= 0) {
            return [key, { status: 'computed' }];
        }
        const timing = {
            keyframeDisplayOffsetAdjustment: adjustment,
            ...(status.keyframePlaybackRateAdjustment === undefined
                ? {}
                : { keyframePlaybackRateAdjustment: rate }),
        };
        if (status.status === 'static') {
            const value = status.numericExpression === undefined
                ? status.codeValue
                : (0, exports.evaluateSourceNumericValue)(status.numericExpression, config);
            return [
                key,
                status.numericExpression !== undefined && !Number.isFinite(value)
                    ? { status: 'computed' }
                    : { ...status, ...timing, codeValue: value },
            ];
        }
        const keyframes = status.keyframes.map((keyframe) => ({
            ...keyframe,
            frame: (0, exports.evaluateSourceNumericValue)(keyframe.frame, config),
        }));
        if (keyframes.some((keyframe, index) => !Number.isFinite(keyframe.frame) ||
            (index > 0 && keyframe.frame <= keyframes[index - 1].frame))) {
            return [key, { status: 'computed' }];
        }
        return [key, { ...status, ...timing, keyframes }];
    }));
    cached.set(configKey, result);
    if (cached.size > 8)
        cached.delete(cached.keys().next().value);
    evaluatedProps.set(props, cached);
    return result;
};
exports.evaluateSourcePropStatuses = evaluateSourcePropStatuses;
