"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SequenceOutlineInternals = exports.SequenceOutlineContext = void 0;
const react_1 = __importDefault(require("react"));
exports.SequenceOutlineContext = react_1.default.createContext(false);
// Keep automatic groups separate from the public, single-element outlineRef.
// A group only exposes .current when it has exactly one element, so consumers
// that require an actual element never accidentally act on part of a group.
const nodesByRef = new WeakMap();
exports.SequenceOutlineInternals = {
    createRef: () => {
        const ref = { current: null };
        nodesByRef.set(ref, []);
        return ref;
    },
    getNodes: (ref) => {
        var _a;
        return (_a = nodesByRef.get(ref)) !== null && _a !== void 0 ? _a : null;
    },
    setNodes: (ref, nodes) => {
        const previous = nodesByRef.get(ref);
        if ((previous === null || previous === void 0 ? void 0 : previous.length) === nodes.length &&
            previous.every((node, index) => node === nodes[index])) {
            return;
        }
        nodesByRef.set(ref, nodes);
        ref.current =
            nodes.length === 1 && nodes[0].nodeType === 1
                ? nodes[0]
                : null;
    },
};
