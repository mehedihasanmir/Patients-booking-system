"use client";

import { useEffect, useRef } from "react";
import { LiveKitRoom, RoomAudioRenderer, useRoomContext } from "@livekit/components-react";
import {
  ParticipantKind,
  RoomEvent,
  Track,
  type LocalTrack,
  type Participant,
  type RemoteTrack,
  type TranscriptionSegment,
} from "livekit-client";
import { useVoice } from "@/lib/voice";

type Controls = {
  setMic: (enabled: boolean) => Promise<void>;
  hangup: () => void;
};

let controls: Controls | null = null;
export function callControls() {
  return controls;
}

export type Caption = { id: string; speaker: "agent" | "caller"; text: string; final: boolean };

function isAgent(participant: Participant) {
  return participant.kind === ParticipantKind.AGENT || participant.identity.startsWith("agent");
}

function RoomBridge({
  onLive,
  onAgentTimeout,
  onCaptions,
}: {
  onLive: () => void;
  onAgentTimeout: () => void;
  onCaptions: (caption: Caption) => void;
}) {
  const room = useRoomContext();
  const setLevel = useVoice((state) => state.setLevel);
  const setCallerLevel = useVoice((state) => state.setCallerLevel);
  const setActive = useVoice((state) => state.setActive);
  const live = useRef(false);
  const onLiveRef = useRef(onLive);
  const onTimeoutRef = useRef(onAgentTimeout);
  const onCaptionsRef = useRef(onCaptions);
  onLiveRef.current = onLive;
  onTimeoutRef.current = onAgentTimeout;
  onCaptionsRef.current = onCaptions;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!live.current) onTimeoutRef.current();
    }, 10000);
    const mark = (participant: Participant) => {
      if (!isAgent(participant) || live.current) return;
      live.current = true;
      window.clearTimeout(timer);
      setActive(true);
      onLiveRef.current();
    };
    room.remoteParticipants.forEach(mark);
    room.on(RoomEvent.ParticipantConnected, mark);
    const onTx = (segments: TranscriptionSegment[], participant?: Participant) => {
      const speaker = participant && participant.identity.startsWith("caller") ? "caller" : "agent";
      segments.forEach((segment) => {
        onCaptionsRef.current({ id: segment.id, speaker, text: segment.text, final: segment.final });
      });
    };
    room.on(RoomEvent.TranscriptionReceived, onTx);

    const audio = new AudioContext();
    const analyser = audio.createAnalyser();
    const callerAnalyser = audio.createAnalyser();
    analyser.fftSize = 256;
    callerAnalyser.fftSize = 256;
    const bins = new Uint8Array(analyser.frequencyBinCount);
    const callerBins = new Uint8Array(callerAnalyser.frequencyBinCount);
    const attach = (track: RemoteTrack | LocalTrack, target: AnalyserNode) => {
      if (track.kind !== Track.Kind.Audio) return;
      const source = audio.createMediaStreamSource(new MediaStream([track.mediaStreamTrack]));
      source.connect(target);
      void audio.resume();
    };
    const onTrack = (track: RemoteTrack) => attach(track, analyser);
    const onLocal = (track: LocalTrack) => attach(track, callerAnalyser);
    room.localParticipant.audioTrackPublications.forEach((publication) => {
      if (publication.track) onLocal(publication.track);
    });
    controls = {
      setMic: async (enabled) => {
        await room.localParticipant.setMicrophoneEnabled(enabled);
      },
      hangup: () => room.disconnect(),
    };
    const onLocalPublished = (publication: { track?: LocalTrack | null }) => {
      if (publication.track) onLocal(publication.track);
    };
    room.on(RoomEvent.TrackSubscribed, onTrack);
    room.on(RoomEvent.LocalTrackPublished, onLocalPublished);
    const meter = window.setInterval(() => {
      analyser.getByteFrequencyData(bins);
      callerAnalyser.getByteFrequencyData(callerBins);
      const average = bins.reduce((sum, value) => sum + value, 0) / bins.length / 255;
      const caller = callerBins.reduce((sum, value) => sum + value, 0) / callerBins.length / 255;
      setLevel(average);
      setCallerLevel(caller);
    }, 80);

    return () => {
      window.clearTimeout(timer);
      window.clearInterval(meter);
      room.off(RoomEvent.ParticipantConnected, mark);
      room.off(RoomEvent.TranscriptionReceived, onTx);
      room.off(RoomEvent.TrackSubscribed, onTrack);
      room.off(RoomEvent.LocalTrackPublished, onLocalPublished);
      controls = null;
      setActive(false);
      setLevel(0);
      setCallerLevel(0);
      void audio.close();
    };
  }, [room, setActive, setCallerLevel, setLevel]);

  return <RoomAudioRenderer />;
}

export function CallRoom({
  token,
  url,
  onLive,
  onAgentTimeout,
  onDisconnected,
  onError,
  onCaptions,
}: {
  token: string;
  url: string;
  onLive: () => void;
  onAgentTimeout: () => void;
  onDisconnected: () => void;
  onError: () => void;
  onCaptions: (caption: Caption) => void;
}) {
  return (
    <LiveKitRoom
      token={token}
      serverUrl={url}
      connect
      audio
      video={false}
      onDisconnected={onDisconnected}
      onError={onError}
    >
      <RoomBridge onLive={onLive} onAgentTimeout={onAgentTimeout} onCaptions={onCaptions} />
    </LiveKitRoom>
  );
}
