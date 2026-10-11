"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Track = exports.TrackWithoutSchema = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const enable_sequence_stack_traces_js_1 = require("./enable-sequence-stack-traces.js");
const interactivity_schema_js_1 = require("./interactivity-schema.js");
const Sequence_js_1 = require("./Sequence.js");
const timeline_track_context_js_1 = require("./timeline-track-context.js");
const with_interactivity_schema_js_1 = require("./with-interactivity-schema.js");
const trackSchema = {
    name: interactivity_schema_js_1.sequenceSchema.name,
    hidden: interactivity_schema_js_1.sequenceSchema.hidden,
};
// Series variants share the Track foundation while retaining their own
// Sequence props, layout defaults, and interactivity schemas.
const TrackWithoutSchema = ({ name = 'Track', children, layout = 'none', ...props }) => {
    const [id] = (0, react_1.useState)(() => String(Math.random()));
    const tracksEnabled = (0, react_1.useContext)(timeline_track_context_js_1.ExperimentalTracksEnabledContext);
    const value = (0, react_1.useMemo)(() => (tracksEnabled ? { id, name } : null), [id, name, tracksEnabled]);
    return (jsx_runtime_1.jsx(timeline_track_context_js_1.TimelineTrackContext.Provider, { value: value, children: jsx_runtime_1.jsx(Sequence_js_1.SequenceWithoutSchema, { ...props, name: name, layout: layout, _remotionInternalTimelineTrack: { role: 'track' }, children: children }) }));
};
exports.TrackWithoutSchema = TrackWithoutSchema;
/** Groups clips on one Studio timeline row and applies Sequence timing. */
exports.Track = (0, with_interactivity_schema_js_1.withInteractivitySchema)({
    Component: exports.TrackWithoutSchema,
    componentName: '<Track>',
    componentIdentity: 'dev.remotion.remotion.Track',
    schema: trackSchema,
    supportsEffects: false,
});
(0, enable_sequence_stack_traces_js_1.addSequenceStackTraces)(exports.Track);
