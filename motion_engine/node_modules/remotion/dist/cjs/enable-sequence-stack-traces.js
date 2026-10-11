"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getSingleChildComponent = exports.getStackForControls = exports.setStackForControls = exports.resolveComponentIdentity = exports.setComponentIdentityResolver = exports.getSequenceComponent = exports.setSequenceComponent = exports.addSequenceStackTraces = exports.getComponentsToAddStacksTo = exports.parseOriginalSourceStack = exports.makeOriginalSourceStack = exports.REMOTION_INTERNAL_STACK_PROP = void 0;
const react_1 = __importDefault(require("react"));
const componentsToAddStacksTo = [];
let sequenceComponent = null;
const stacksByControls = new WeakMap();
// Studio installs a resolver that maps refreshed component implementations to
// the stable family object maintained by React Refresh.
let componentIdentityResolver = null;
exports.REMOTION_INTERNAL_STACK_PROP = '_remotionInternalStack';
// Bundlers that know where a JSX element was written encode its source
// location as a synthetic stack frame, so consumers can skip symbolication.
const ORIGINAL_SOURCE_STACK_PREFIX = 'studio-original://';
const originalSourceStackPattern = /\(studio-original:\/\/([^\r\n]+):(\d+):(\d+)\)/;
const makeOriginalSourceStack = ({ fileName, lineNumber, columnNumber, }) => {
    return `Error\n    at remotionOriginalSource (${ORIGINAL_SOURCE_STACK_PREFIX}${encodeURIComponent(fileName)}:${lineNumber}:${columnNumber})`;
};
exports.makeOriginalSourceStack = makeOriginalSourceStack;
const parseOriginalSourceStack = (stack) => {
    if (!stack) {
        return null;
    }
    const match = stack.match(originalSourceStackPattern);
    if (!match) {
        return null;
    }
    return {
        fileName: decodeURIComponent(match[1]),
        line: Number(match[2]),
        column: Number(match[3]),
    };
};
exports.parseOriginalSourceStack = parseOriginalSourceStack;
const getComponentsToAddStacksTo = () => componentsToAddStacksTo;
exports.getComponentsToAddStacksTo = getComponentsToAddStacksTo;
const addSequenceStackTraces = (component) => {
    componentsToAddStacksTo.push(component);
};
exports.addSequenceStackTraces = addSequenceStackTraces;
const setSequenceComponent = (component) => {
    sequenceComponent = component;
};
exports.setSequenceComponent = setSequenceComponent;
const getSequenceComponent = () => sequenceComponent;
exports.getSequenceComponent = getSequenceComponent;
const setComponentIdentityResolver = (resolver) => {
    componentIdentityResolver = resolver;
};
exports.setComponentIdentityResolver = setComponentIdentityResolver;
const resolveComponentIdentity = (component) => {
    var _a;
    return (_a = componentIdentityResolver === null || componentIdentityResolver === void 0 ? void 0 : componentIdentityResolver(component)) !== null && _a !== void 0 ? _a : component;
};
exports.resolveComponentIdentity = resolveComponentIdentity;
const setStackForControls = (controls, stack) => {
    if (stack === undefined) {
        stacksByControls.delete(controls);
        return;
    }
    stacksByControls.set(controls, stack);
};
exports.setStackForControls = setStackForControls;
const getStackForControls = (controls) => {
    var _a;
    return (_a = stacksByControls.get(controls)) !== null && _a !== void 0 ? _a : null;
};
exports.getStackForControls = getStackForControls;
const getSingleChildComponent = (children) => {
    const mountedChildren = react_1.default.Children.toArray(children);
    if (mountedChildren.length !== 1) {
        return null;
    }
    const child = mountedChildren[0];
    if (!react_1.default.isValidElement(child)) {
        return null;
    }
    if (typeof child.type !== 'function' && typeof child.type !== 'object') {
        return null;
    }
    return (0, exports.resolveComponentIdentity)(child.type);
};
exports.getSingleChildComponent = getSingleChildComponent;
