"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useEffectChainState = void 0;
const react_1 = require("react");
const run_effect_chain_js_1 = require("./run-effect-chain.js");
const useEffectChainState = () => {
    const chainStateRef = (0, react_1.useRef)(null);
    const sizeRef = (0, react_1.useRef)(null);
    const unmountedRef = (0, react_1.useRef)(false);
    (0, react_1.useEffect)(() => {
        // StrictMode and Fast Refresh run the cleanup below and then this effect
        // again, after which `get()` must hand out a fresh state.
        unmountedRef.current = false;
        return () => {
            unmountedRef.current = true;
            if (chainStateRef.current) {
                (0, run_effect_chain_js_1.cleanupEffectChainState)(chainStateRef.current);
                chainStateRef.current = null;
                sizeRef.current = null;
            }
        };
    }, []);
    return (0, react_1.useMemo)(() => ({
        get: (width, height) => {
            // Async work such as a late decoded video frame can still get here
            // after unmount. Nothing would release a pool created at this point.
            if (unmountedRef.current) {
                return null;
            }
            if (!sizeRef.current ||
                sizeRef.current.width !== width ||
                sizeRef.current.height !== height) {
                if (chainStateRef.current) {
                    (0, run_effect_chain_js_1.cleanupEffectChainState)(chainStateRef.current);
                }
                chainStateRef.current = (0, run_effect_chain_js_1.createEffectChainState)(width, height);
                sizeRef.current = { width, height };
            }
            return chainStateRef.current;
        },
    }), []);
};
exports.useEffectChainState = useEffectChainState;
