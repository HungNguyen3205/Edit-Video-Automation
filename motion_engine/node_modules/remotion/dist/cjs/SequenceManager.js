"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.SequenceManagerProvider = exports.VisualModeBatchSettersContext = exports.VisualModeSettersContext = exports.useEffectDragOverridesForNodePath = exports.useActiveFromDragOverrideKeys = exports.useDragOverridesForNodePath = exports.VisualModeDragOverridesContext = exports.VisualModePropStatusesRefContext = exports.VisualModePropStatusesContext = exports.makeSequencePropsSubscriptionKey = exports.VisualModeDragOverridesSubscriptionContext = exports.DisableSequenceRegistrationProvider = exports.DisableSequenceRegistrationContext = exports.SequenceRegistrationContext = exports.SequenceManagerRefContext = exports.useSequenceManagerSequences = exports.SequenceManager = exports.SequenceManagerActionsContext = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = __importStar(require("react"));
const sequence_order_marker_js_1 = require("./sequence-order-marker.js");
const use_remotion_environment_js_1 = require("./use-remotion-environment.js");
const use_sync_external_store_js_1 = require("./use-sync-external-store.js");
const useIsomorphicLayoutEffect = typeof window === 'undefined' ? react_1.default.useEffect : react_1.default.useLayoutEffect;
const defaultSequenceManager = {
    registerSequence: () => {
        throw new Error('SequenceManagerContext not initialized');
    },
    updateSequence: null,
    unregisterSequence: () => {
        throw new Error('SequenceManagerContext not initialized');
    },
    sequences: [],
};
exports.SequenceManagerActionsContext = react_1.default.createContext({
    registerSequence: defaultSequenceManager.registerSequence,
    updateSequence: defaultSequenceManager.updateSequence,
    unregisterSequence: defaultSequenceManager.unregisterSequence,
});
exports.SequenceManager = react_1.default.createContext(defaultSequenceManager);
const NativeSequenceManagerProvider = exports.SequenceManager.Provider;
const SequenceManagerProviderWithActions = ({ value, children }) => {
    const actions = (0, react_1.useMemo)(() => ({
        registerSequence: value.registerSequence,
        updateSequence: value.updateSequence,
        unregisterSequence: value.unregisterSequence,
    }), [value.registerSequence, value.updateSequence, value.unregisterSequence]);
    return (jsx_runtime_1.jsx(exports.SequenceManagerActionsContext.Provider, { value: actions, children: jsx_runtime_1.jsx(NativeSequenceManagerProvider, { value: value, children: children }) }));
};
// Keep custom SequenceManager.Provider trees in sync with the stable actions
// context while preserving the legacy reactive sequence-list context.
Object.defineProperty(exports.SequenceManager, 'Provider', {
    value: SequenceManagerProviderWithActions,
});
const useSequenceManagerSequences = () => {
    return (0, react_1.useContext)(exports.SequenceManager).sequences;
};
exports.useSequenceManagerSequences = useSequenceManagerSequences;
exports.SequenceManagerRefContext = react_1.default.createContext({
    current: [],
});
exports.SequenceRegistrationContext = react_1.default.createContext(false);
exports.DisableSequenceRegistrationContext = react_1.default.createContext(false);
const DisableSequenceRegistrationProvider = ({ children }) => {
    return react_1.default.createElement(exports.DisableSequenceRegistrationContext.Provider, { value: true }, children);
};
exports.DisableSequenceRegistrationProvider = DisableSequenceRegistrationProvider;
exports.VisualModeDragOverridesSubscriptionContext = react_1.default.createContext(null);
const ActiveFromDragOverrideKeysContext = react_1.default.createContext(null);
const SequenceManagerScopeProviders = ({ children, dragOverridesSubscription, fromKeys }) => {
    const manager = (0, react_1.useContext)(exports.SequenceManagerActionsContext);
    const scopedDragOverridesSubscription = (0, react_1.useMemo)(() => ({ ...dragOverridesSubscription, manager }), [dragOverridesSubscription, manager]);
    const activeFromDragOverrideKeys = (0, react_1.useMemo)(() => ({ manager, keys: fromKeys }), [fromKeys, manager]);
    return (jsx_runtime_1.jsx(ActiveFromDragOverrideKeysContext.Provider, { value: activeFromDragOverrideKeys, children: jsx_runtime_1.jsx(exports.VisualModeDragOverridesSubscriptionContext.Provider, { value: scopedDragOverridesSubscription, children: children }) }));
};
const emptyDragOverrides = {};
const emptyFromOverrideKeys = new Set();
const emptyEffectDragOverrides = {};
const makeSequencePropsSubscriptionKey = (key) => {
    return `${key.absolutePath}\0${key.nodePath.join('.')}\0${key.sequenceKeys.join('.')}\0${key.effectKeys.map((keys) => keys.join('.')).join('.')}`;
};
exports.makeSequencePropsSubscriptionKey = makeSequencePropsSubscriptionKey;
exports.VisualModePropStatusesContext = react_1.default.createContext({
    propStatuses: {},
});
exports.VisualModePropStatusesRefContext = react_1.default.createContext({
    current: {},
});
exports.VisualModeDragOverridesContext = react_1.default.createContext({
    getDragOverrides: () => {
        throw new Error('VisualModeDragOverridesContext not initialized');
    },
    getEffectDragOverrides: () => {
        throw new Error('VisualModeDragOverridesContext not initialized');
    },
});
/* eslint-disable react-hooks/rules-of-hooks */
const useDragOverridesForNodePath = (nodePath) => {
    const subscription = (0, react_1.useContext)(exports.VisualModeDragOverridesSubscriptionContext);
    const manager = (0, react_1.useContext)(exports.SequenceManagerActionsContext);
    const scopedSubscription = (subscription === null || subscription === void 0 ? void 0 : subscription.manager) === manager ? subscription : null;
    // Legacy providers only supply VisualModeDragOverridesContext. Its presence is
    // fixed for the lifetime of a mounted tree.
    const legacy = scopedSubscription === null
        ? (0, react_1.useContext)(exports.VisualModeDragOverridesContext)
        : null;
    const key = nodePath === null ? null : (0, exports.makeSequencePropsSubscriptionKey)(nodePath);
    const subscribe = (0, react_1.useCallback)((listener) => {
        var _a;
        return (_a = scopedSubscription === null || scopedSubscription === void 0 ? void 0 : scopedSubscription.subscribe(key, listener)) !== null && _a !== void 0 ? _a : (() => undefined);
    }, [key, scopedSubscription]);
    const getSnapshot = (0, react_1.useCallback)(() => {
        var _a;
        return (_a = scopedSubscription === null || scopedSubscription === void 0 ? void 0 : scopedSubscription.getSnapshot(key)) !== null && _a !== void 0 ? _a : emptyDragOverrides;
    }, [key, scopedSubscription]);
    const overrides = (0, use_sync_external_store_js_1.useSyncExternalStore)(subscribe, getSnapshot, getSnapshot);
    return legacy !== null && nodePath !== null
        ? legacy.getDragOverrides(nodePath)
        : overrides;
};
exports.useDragOverridesForNodePath = useDragOverridesForNodePath;
const useActiveFromDragOverrideKeys = () => {
    const snapshot = (0, react_1.useContext)(ActiveFromDragOverrideKeysContext);
    const manager = (0, react_1.useContext)(exports.SequenceManagerActionsContext);
    return (snapshot === null || snapshot === void 0 ? void 0 : snapshot.manager) === manager ? snapshot.keys : emptyFromOverrideKeys;
};
exports.useActiveFromDragOverrideKeys = useActiveFromDragOverrideKeys;
const useEffectDragOverridesForNodePath = (nodePath, effectCount) => {
    const subscription = (0, react_1.useContext)(exports.VisualModeDragOverridesSubscriptionContext);
    const manager = (0, react_1.useContext)(exports.SequenceManagerActionsContext);
    const scopedSubscription = (subscription === null || subscription === void 0 ? void 0 : subscription.manager) === manager ? subscription : null;
    // Legacy providers only supply VisualModeDragOverridesContext. Its presence is
    // fixed for the lifetime of a mounted tree.
    const legacy = scopedSubscription === null
        ? (0, react_1.useContext)(exports.VisualModeDragOverridesContext)
        : null;
    const key = nodePath === null ? null : (0, exports.makeSequencePropsSubscriptionKey)(nodePath);
    const subscribe = (0, react_1.useCallback)((listener) => {
        var _a;
        return (_a = scopedSubscription === null || scopedSubscription === void 0 ? void 0 : scopedSubscription.subscribeEffects(key, listener)) !== null && _a !== void 0 ? _a : (() => undefined);
    }, [key, scopedSubscription]);
    const getSnapshot = (0, react_1.useCallback)(() => {
        var _a;
        return (_a = scopedSubscription === null || scopedSubscription === void 0 ? void 0 : scopedSubscription.getEffectSnapshot(key)) !== null && _a !== void 0 ? _a : emptyEffectDragOverrides;
    }, [key, scopedSubscription]);
    const overrides = (0, use_sync_external_store_js_1.useSyncExternalStore)(subscribe, getSnapshot, getSnapshot);
    if (legacy !== null && nodePath !== null) {
        const legacyOverrides = {};
        for (let index = 0; index < effectCount; index++) {
            legacyOverrides[index] = legacy.getEffectDragOverrides(nodePath, index);
        }
        return legacyOverrides;
    }
    return overrides;
};
exports.useEffectDragOverridesForNodePath = useEffectDragOverridesForNodePath;
/* eslint-enable react-hooks/rules-of-hooks */
exports.VisualModeSettersContext = react_1.default.createContext({
    setDragOverrides: () => {
        throw new Error('VisualModeSettersContext not initialized');
    },
    clearDragOverrides: () => {
        throw new Error('VisualModeSettersContext not initialized');
    },
    setEffectDragOverrides: () => {
        throw new Error('VisualModeSettersContext not initialized');
    },
    clearEffectDragOverrides: () => {
        throw new Error('VisualModeSettersContext not initialized');
    },
    setPropStatuses: () => {
        throw new Error('VisualModeSettersContext not initialized');
    },
    remapPropStatuses: () => {
        throw new Error('VisualModeSettersContext not initialized');
    },
});
exports.VisualModeBatchSettersContext = react_1.default.createContext(null);
const effectDragOverridesKey = (nodePath, effectIndex) => `${(0, exports.makeSequencePropsSubscriptionKey)(nodePath)}.effects.${effectIndex}`;
const SequenceManagerProvider = ({ children }) => {
    const { isStudio } = (0, use_remotion_environment_js_1.useRemotionEnvironment)();
    const [sequenceManagerId] = (0, react_1.useState)(() => String(Math.random()));
    const committedOrderRef = (0, react_1.useRef)(null);
    const committedOrderIdsRef = (0, react_1.useRef)(null);
    const [sequences, setSequences] = (0, react_1.useState)([]);
    const sequencesRef = (0, react_1.useRef)(sequences);
    sequencesRef.current = sequences;
    const [dragOverrideState, setDragOverrideState] = (0, react_1.useState)(() => ({
        overrides: {},
        fromKeys: new Set(),
    }));
    const dragOverrides = dragOverrideState.overrides;
    const dragOverridesStore = (0, react_1.useRef)({
        snapshot: dragOverrides,
        listeners: new Map(),
    });
    const [effectDragOverridesState, setEffectDragOverridesState] = (0, react_1.useState)({});
    const effectDragOverridesStore = (0, react_1.useRef)({
        snapshot: effectDragOverridesState,
        byNode: new Map(),
        listeners: new Map(),
    });
    const [propStatuses, setPropStatusesMapState] = (0, react_1.useState)({});
    const propStatusesRef = (0, react_1.useRef)(propStatuses);
    propStatusesRef.current = propStatuses;
    const setDragOverridesBatch = (0, react_1.useCallback)((overrides) => {
        setDragOverrideState((prevState) => {
            var _a;
            const prev = prevState.overrides;
            let next = null;
            let nextFromKeys = prevState.fromKeys;
            for (const { nodePath, key, value } of overrides) {
                const mapKey = (0, exports.makeSequencePropsSubscriptionKey)(nodePath);
                const existing = (_a = (next !== null && next !== void 0 ? next : prev)[mapKey]) === null || _a === void 0 ? void 0 : _a[key];
                if (existing === value ||
                    ((existing === null || existing === void 0 ? void 0 : existing.type) === 'static' &&
                        value.type === 'static' &&
                        Object.is(existing.value, value.value))) {
                    continue;
                }
                if (next === null) {
                    next = { ...prev };
                }
                if (next[mapKey] === prev[mapKey]) {
                    next[mapKey] = { ...prev[mapKey] };
                }
                next[mapKey][key] = value;
                if (key === 'from' && !nextFromKeys.has(mapKey)) {
                    nextFromKeys = new Set(nextFromKeys);
                    nextFromKeys.add(mapKey);
                }
            }
            return next === null
                ? prevState
                : { overrides: next, fromKeys: nextFromKeys };
        });
    }, []);
    const setDragOverrides = (0, react_1.useCallback)((nodePath, key, value) => setDragOverridesBatch([{ nodePath, key, value }]), [setDragOverridesBatch]);
    const subscribeDragOverrides = (0, react_1.useCallback)((key, listener) => {
        if (key === null) {
            return () => undefined;
        }
        let listeners = dragOverridesStore.current.listeners.get(key);
        if (!listeners) {
            listeners = new Set();
            dragOverridesStore.current.listeners.set(key, listeners);
        }
        listeners.add(listener);
        return () => {
            listeners.delete(listener);
            if (listeners.size === 0) {
                dragOverridesStore.current.listeners.delete(key);
            }
        };
    }, []);
    const getDragOverridesSnapshot = (0, react_1.useCallback)((key) => {
        var _a;
        return key === null
            ? emptyDragOverrides
            : ((_a = dragOverridesStore.current.snapshot[key]) !== null && _a !== void 0 ? _a : emptyDragOverrides);
    }, []);
    useIsomorphicLayoutEffect(() => {
        var _a;
        const previous = dragOverridesStore.current.snapshot;
        dragOverridesStore.current.snapshot = dragOverrides;
        for (const key of new Set([
            ...Object.keys(previous),
            ...Object.keys(dragOverrides),
        ])) {
            if (previous[key] !== dragOverrides[key]) {
                for (const listener of (_a = dragOverridesStore.current.listeners.get(key)) !== null && _a !== void 0 ? _a : []) {
                    listener();
                }
            }
        }
    }, [dragOverrides]);
    const subscribeEffectDragOverrides = (0, react_1.useCallback)((key, listener) => {
        if (key === null) {
            return () => undefined;
        }
        let listeners = effectDragOverridesStore.current.listeners.get(key);
        if (!listeners) {
            listeners = new Set();
            effectDragOverridesStore.current.listeners.set(key, listeners);
        }
        listeners.add(listener);
        return () => {
            listeners.delete(listener);
            if (listeners.size === 0) {
                effectDragOverridesStore.current.listeners.delete(key);
            }
        };
    }, []);
    const getEffectDragOverridesSnapshot = (0, react_1.useCallback)((key) => {
        var _a;
        return key === null
            ? emptyEffectDragOverrides
            : ((_a = effectDragOverridesStore.current.byNode.get(key)) !== null && _a !== void 0 ? _a : emptyEffectDragOverrides);
    }, []);
    useIsomorphicLayoutEffect(() => {
        var _a;
        const previous = effectDragOverridesStore.current.snapshot;
        const byNode = new Map(effectDragOverridesStore.current.byNode);
        const changedNodes = new Set();
        for (const flatKey of new Set([
            ...Object.keys(previous),
            ...Object.keys(effectDragOverridesState),
        ])) {
            if (previous[flatKey] === effectDragOverridesState[flatKey]) {
                continue;
            }
            const separator = flatKey.lastIndexOf('.effects.');
            if (separator === -1) {
                throw new Error('Invalid effect drag override key');
            }
            const nodeKey = flatKey.slice(0, separator);
            const effectIndex = flatKey.slice(separator + '.effects.'.length);
            if (!changedNodes.has(nodeKey)) {
                byNode.set(nodeKey, { ...byNode.get(nodeKey) });
                changedNodes.add(nodeKey);
            }
            const next = byNode.get(nodeKey);
            if (effectDragOverridesState[flatKey] === undefined) {
                delete next[effectIndex];
            }
            else {
                next[effectIndex] = effectDragOverridesState[flatKey];
            }
        }
        for (const nodeKey of changedNodes) {
            if (Object.keys(byNode.get(nodeKey)).length === 0) {
                byNode.delete(nodeKey);
            }
        }
        effectDragOverridesStore.current.snapshot = effectDragOverridesState;
        effectDragOverridesStore.current.byNode = byNode;
        for (const nodeKey of changedNodes) {
            for (const listener of (_a = effectDragOverridesStore.current.listeners.get(nodeKey)) !== null && _a !== void 0 ? _a : []) {
                listener();
            }
        }
    }, [effectDragOverridesState]);
    const clearDragOverrides = (0, react_1.useCallback)((nodePath) => {
        setDragOverrideState((prevState) => {
            const prev = prevState.overrides;
            const key = (0, exports.makeSequencePropsSubscriptionKey)(nodePath);
            if (!prev[key]) {
                return prevState;
            }
            const next = { ...prev };
            delete next[key];
            const nextFromKeys = prevState.fromKeys.has(key)
                ? new Set(prevState.fromKeys)
                : prevState.fromKeys;
            nextFromKeys.delete(key);
            return { overrides: next, fromKeys: nextFromKeys };
        });
    }, []);
    const setEffectDragOverridesBatch = (0, react_1.useCallback)((overrides) => {
        setEffectDragOverridesState((prev) => {
            var _a;
            let next = null;
            for (const { nodePath, effectIndex, key, value } of overrides) {
                const mapKey = effectDragOverridesKey(nodePath, effectIndex);
                const existing = (_a = (next !== null && next !== void 0 ? next : prev)[mapKey]) === null || _a === void 0 ? void 0 : _a[key];
                if (existing === value ||
                    ((existing === null || existing === void 0 ? void 0 : existing.type) === 'static' &&
                        value.type === 'static' &&
                        Object.is(existing.value, value.value))) {
                    continue;
                }
                if (next === null) {
                    next = { ...prev };
                }
                if (next[mapKey] === prev[mapKey]) {
                    next[mapKey] = { ...prev[mapKey] };
                }
                next[mapKey][key] = value;
            }
            return next !== null && next !== void 0 ? next : prev;
        });
    }, []);
    const setEffectDragOverrides = (0, react_1.useCallback)((nodePath, effectIndex, key, value) => setEffectDragOverridesBatch([{ nodePath, effectIndex, key, value }]), [setEffectDragOverridesBatch]);
    const clearEffectDragOverrides = (0, react_1.useCallback)((nodePath, effectIndex) => {
        setEffectDragOverridesState((prev) => {
            const mapKey = effectDragOverridesKey(nodePath, effectIndex);
            if (!prev[mapKey]) {
                return prev;
            }
            const next = { ...prev };
            delete next[mapKey];
            return next;
        });
    }, []);
    const setPropStatuses = (0, react_1.useCallback)((nodePath, values) => {
        setPropStatusesMapState((prev) => {
            const key = (0, exports.makeSequencePropsSubscriptionKey)(nodePath);
            const prevKey = prev[key];
            const newKey = values(prevKey);
            if (prevKey === newKey) {
                return prev;
            }
            return { ...prev, [key]: newKey };
        });
    }, []);
    const remapPropStatuses = (0, react_1.useCallback)((remappings) => {
        setPropStatusesMapState((prev) => {
            const next = { ...prev };
            for (const remapping of remappings) {
                delete next[(0, exports.makeSequencePropsSubscriptionKey)(remapping.previousNodePath)];
            }
            for (const remapping of remappings) {
                if (remapping.nodePath !== null && remapping.result !== null) {
                    next[(0, exports.makeSequencePropsSubscriptionKey)(remapping.nodePath)] =
                        remapping.result;
                }
            }
            return next;
        });
    }, []);
    useIsomorphicLayoutEffect(() => {
        if (!isStudio) {
            return;
        }
        let unmounted = false;
        const onCommitOrder = (event) => {
            const { detail } = event;
            const managerOrder = detail.sequenceManagers.find((item) => item.managerId === sequenceManagerId);
            if (!managerOrder) {
                return;
            }
            const previousOrder = committedOrderIdsRef.current;
            if (previousOrder !== null &&
                previousOrder.length === managerOrder.sequenceIds.length &&
                previousOrder.every((sequenceId, index) => sequenceId === managerOrder.sequenceIds[index])) {
                return;
            }
            const order = new Map(managerOrder.sequenceIds.map((sequenceId, index) => [
                sequenceId,
                index,
            ]));
            committedOrderIdsRef.current = managerOrder.sequenceIds;
            committedOrderRef.current = order;
            queueMicrotask(() => {
                if (unmounted) {
                    return;
                }
                setSequences((currentSequences) => {
                    let changed = false;
                    const nextSequences = currentSequences.map((sequence) => {
                        var _a;
                        const timelineOrder = (_a = order.get(sequence.id)) !== null && _a !== void 0 ? _a : null;
                        if (sequence.timelineOrder === timelineOrder) {
                            return sequence;
                        }
                        changed = true;
                        return { ...sequence, timelineOrder };
                    });
                    return changed ? nextSequences : currentSequences;
                });
            });
        };
        window.addEventListener(sequence_order_marker_js_1.COMMIT_ORDER_EVENT, onCommitOrder);
        return () => {
            unmounted = true;
            window.removeEventListener(sequence_order_marker_js_1.COMMIT_ORDER_EVENT, onCommitOrder);
        };
    }, [isStudio, sequenceManagerId]);
    const registerSequence = (0, react_1.useCallback)((seq) => {
        setSequences((seqs) => {
            var _a;
            var _b;
            return [
                ...seqs,
                {
                    ...seq,
                    timelineOrder: (_b = (_a = committedOrderRef.current) === null || _a === void 0 ? void 0 : _a.get(seq.id)) !== null && _b !== void 0 ? _b : null,
                },
            ];
        });
    }, []);
    const updateSequence = (0, react_1.useCallback)((seq) => {
        setSequences((seqs) => {
            var _a;
            var _b;
            const index = seqs.findIndex((item) => item.id === seq.id);
            if (index === -1) {
                return seqs;
            }
            const previousSequence = seqs[index];
            const timelineOrder = (_b = (_a = committedOrderRef.current) === null || _a === void 0 ? void 0 : _a.get(seq.id)) !== null && _b !== void 0 ? _b : null;
            // A new registration getter does not necessarily change the metadata.
            let unchanged = Object.is(previousSequence.timelineOrder, timelineOrder);
            // The manager adds timelineOrder even if the incoming object omits it.
            let keyCount = 1;
            if (unchanged) {
                for (const key in seq) {
                    if (key === 'timelineOrder' ||
                        !Object.prototype.hasOwnProperty.call(seq, key)) {
                        continue;
                    }
                    keyCount++;
                    if (!Object.prototype.hasOwnProperty.call(previousSequence, key) ||
                        !Object.is(previousSequence[key], seq[key])) {
                        unchanged = false;
                        break;
                    }
                }
            }
            if (unchanged && Object.keys(previousSequence).length === keyCount) {
                return seqs;
            }
            const next = [...seqs];
            next[index] = { ...seq, timelineOrder };
            return next;
        });
    }, []);
    const unregisterSequence = (0, react_1.useCallback)((seq) => {
        setSequences((seqs) => seqs.filter((s) => s.id !== seq));
    }, []);
    const sequenceContext = (0, react_1.useMemo)(() => {
        return {
            registerSequence,
            sequences,
            updateSequence,
            unregisterSequence,
        };
    }, [registerSequence, sequences, unregisterSequence, updateSequence]);
    const dragOverridesSubscription = (0, react_1.useMemo)(() => ({
        subscribe: subscribeDragOverrides,
        getSnapshot: getDragOverridesSnapshot,
        subscribeEffects: subscribeEffectDragOverrides,
        getEffectSnapshot: getEffectDragOverridesSnapshot,
    }), [
        getDragOverridesSnapshot,
        getEffectDragOverridesSnapshot,
        subscribeDragOverrides,
        subscribeEffectDragOverrides,
    ]);
    const getDragOverrides = (0, react_1.useCallback)((nodePath) => {
        var _a;
        return (_a = dragOverrides[(0, exports.makeSequencePropsSubscriptionKey)(nodePath)]) !== null && _a !== void 0 ? _a : {};
    }, [dragOverrides]);
    const getEffectDragOverrides = (0, react_1.useCallback)((nodePath, effectIndex) => {
        var _a;
        return ((_a = effectDragOverridesState[effectDragOverridesKey(nodePath, effectIndex)]) !== null && _a !== void 0 ? _a : {});
    }, [effectDragOverridesState]);
    const propStatusesContext = (0, react_1.useMemo)(() => {
        return {
            propStatuses,
        };
    }, [propStatuses]);
    const dragOverridesContext = (0, react_1.useMemo)(() => {
        return {
            getDragOverrides,
            getEffectDragOverrides,
        };
    }, [getDragOverrides, getEffectDragOverrides]);
    const settersContext = (0, react_1.useMemo)(() => {
        return {
            setDragOverrides,
            clearDragOverrides,
            setEffectDragOverrides,
            clearEffectDragOverrides,
            setPropStatuses,
            remapPropStatuses,
        };
    }, [
        setDragOverrides,
        clearDragOverrides,
        setEffectDragOverrides,
        clearEffectDragOverrides,
        setPropStatuses,
        remapPropStatuses,
    ]);
    const batchSettersContext = (0, react_1.useMemo)(() => ({ setDragOverridesBatch, setEffectDragOverridesBatch }), [setDragOverridesBatch, setEffectDragOverridesBatch]);
    const providers = (jsx_runtime_1.jsx(exports.SequenceManagerRefContext.Provider, { value: sequencesRef, children: jsx_runtime_1.jsx(exports.SequenceManager.Provider, { value: sequenceContext, children: jsx_runtime_1.jsx(exports.VisualModePropStatusesRefContext.Provider, { value: propStatusesRef, children: jsx_runtime_1.jsx(exports.VisualModePropStatusesContext.Provider, { value: propStatusesContext, children: jsx_runtime_1.jsx(SequenceManagerScopeProviders, { dragOverridesSubscription: dragOverridesSubscription, fromKeys: dragOverrideState.fromKeys, children: jsx_runtime_1.jsx(exports.VisualModeDragOverridesContext.Provider, { value: dragOverridesContext, children: jsx_runtime_1.jsx(exports.VisualModeSettersContext.Provider, { value: settersContext, children: jsx_runtime_1.jsx(exports.VisualModeBatchSettersContext.Provider, { value: batchSettersContext, children: children }) }) }) }) }) }) }) }));
    return isStudio ? (jsx_runtime_1.jsx(sequence_order_marker_js_1.SequenceManagerOrderMarker, { managerId: sequenceManagerId, children: providers })) : (providers);
};
exports.SequenceManagerProvider = SequenceManagerProvider;
