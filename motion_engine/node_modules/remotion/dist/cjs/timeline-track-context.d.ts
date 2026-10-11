export type TimelineTrack = {
    readonly id: string;
    readonly name: string;
};
export type TimelineTrackItem = TimelineTrack & {
    readonly role: 'track' | 'clip' | 'transition' | 'overlay';
};
export declare const TimelineTrackContext: import("react").Context<TimelineTrack | null>;
export declare const ExperimentalTracksEnabledContext: import("react").Context<boolean>;
