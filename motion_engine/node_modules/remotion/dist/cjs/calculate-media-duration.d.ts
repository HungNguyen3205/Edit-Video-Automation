export declare const calculateMediaDuration: ({ trimAfter, mediaDurationInFrames, playbackRate, trimBefore, }: {
    mediaDurationInFrames: number;
    playbackRate: number;
    trimBefore: number | undefined;
    trimAfter: number | undefined;
}) => number;
export declare const getMediaTrimAfter: ({ durationInFrames, trimAfter, trimBefore, }: {
    readonly durationInFrames: number | undefined;
    readonly trimAfter: number | undefined;
    readonly trimBefore: number | undefined;
}) => number | undefined;
