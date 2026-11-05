"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { NusratAvatar } from "@/components/hero/nusrat-avatar";
import { callControls, type Caption } from "./call-room";

const CallRoom = dynamic(() => import("./call-room").then((mod) => mod.CallRoom), { ssr: false });

type Phase = "idle" | "requesting-mic" | "connecting" | "live" | "ended" | "error";
type ErrorKey =
  | "micDenied"
  | "noMic"
  | "network"
  | "agentTimeout"
  | "rateLimited"
  | "quota"
  | "notConfigured"
  | "generic";

export function CallWidget({ active }: { active: boolean }) {
  const t = useTranslations("call");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<ErrorKey | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [transcriptHeight, setTranscriptHeight] = useState(168);
  const drag = useRef<{ y: number; height: number } | null>(null);
  const terminal = useRef<"ended" | "error" | null>(null);
  const timer = useRef<number | null>(null);
  const booted = useRef(false);

  function stopTimer() {
    if (timer.current) window.clearInterval(timer.current);
  }

  function fail(key: ErrorKey) {
    terminal.current = "error";
    stopTimer();
    setError(key);
    setPhase("error");
    setToken(null);
  }

  async function start() {
    terminal.current = null;
    setError(null);
    setCaptions([]);
    setMuted(false);
    setSeconds(0);
    setPhase("requesting-mic");
    if (!navigator.mediaDevices?.getUserMedia) {
      fail("noMic");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      fail(name === "NotFoundError" || name === "OverconstrainedError" ? "noMic" : "micDenied");
      return;
    }
    setPhase("connecting");
    try {
      const response = await fetch("/api/livekit/token", { method: "POST" });
      const body = (await response.json().catch(() => ({}))) as {
        code?: string;
        detail?: { code?: string };
        token?: string;
        url?: string;
        call_id?: string;
      };
      const code = body.code ?? body.detail?.code;
      if (response.status === 429 || code === "rate_limited") return fail("rateLimited");
      if (code === "livekit_not_configured") return fail("notConfigured");
      if (code === "quota_or_livekit") return fail("quota");
      if (response.status === 503) return fail("notConfigured");
      if (!response.ok || !body.token || !body.url) return fail("network");
      setToken(body.token);
      setUrl(body.url);
    } catch {
      fail("network");
    }
  }

  useEffect(() => {
    const saved = Number(window.localStorage.getItem("bv-transcript-height"));
    if (saved >= 96 && saved <= 340) setTranscriptHeight(saved);
  }, []);

  useEffect(() => {
    if (active && !booted.current) {
      booted.current = true;
      void start();
    }
  }, [active]);

  function rememberHeight(next: number) {
    const height = Math.min(340, Math.max(96, next));
    setTranscriptHeight(height);
    window.localStorage.setItem("bv-transcript-height", String(height));
  }

  const clock = `${Math.floor(seconds / 60)}:${(seconds % 60).toString().padStart(2, "0")}`;
  const showRoom = Boolean(token && url && phase !== "ended" && phase !== "error");
  const presence =
    phase === "live" ? `${t("live")} · ${clock}` : phase === "connecting" || phase === "requesting-mic" ? t("connecting") : phase === "ended" ? t("ended") : t("waiting");

  return (
    <div id="talk" className="flex h-[640px] flex-col overflow-hidden rounded-[36px] border border-white/70 bg-white shadow-card">
      <div className="relative min-h-0 flex-1">
        <NusratAvatar status={presence} />
      </div>
      <div
        role="separator"
        aria-orientation="horizontal"
        aria-label={t("resize")}
        aria-valuemin={96}
        aria-valuemax={340}
        aria-valuenow={transcriptHeight}
        tabIndex={0}
        className="flex h-4 shrink-0 cursor-ns-resize items-center justify-center border-y border-line bg-foam"
        onPointerDown={(event) => {
          drag.current = { y: event.clientY, height: transcriptHeight };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          rememberHeight(drag.current.height + (drag.current.y - event.clientY));
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowUp") rememberHeight(transcriptHeight + 24);
          if (event.key === "ArrowDown") rememberHeight(transcriptHeight - 24);
        }}
      >
        <span className="h-1 w-12 rounded-full bg-line" />
      </div>
      <div className="flex shrink-0 flex-col bg-white" style={{ height: transcriptHeight }}>
        <div className="flex items-center justify-between gap-2 px-4 pt-3">
          <p className="bn text-xs font-semibold uppercase tracking-wide text-ink/60">{t("transcript")}</p>
          {phase === "live" ? (
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  const next = !muted;
                  setMuted(next);
                  void callControls()?.setMic(!next);
                }}
              >
                {muted ? t("unmute") : t("mute")}
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => {
                  terminal.current = "ended";
                  stopTimer();
                  callControls()?.hangup();
                  setToken(null);
                  setPhase("ended");
                }}
              >
                {t("end")}
              </Button>
            </div>
          ) : null}
        </div>
        <div className="bn min-h-0 flex-1 space-y-2 overflow-auto px-4 py-2 text-sm" aria-live="polite">
          {phase === "idle" ? <p className="text-ink/70">{t("idle")}</p> : null}
          {phase === "requesting-mic" ? <p>{t("mic")}</p> : null}
          {phase === "connecting" ? <p>{t("connecting")}</p> : null}
          {phase === "error" && error ? <p>{t(`errors.${error}`)}</p> : null}
          {phase === "ended" ? <p>{t("ended")}</p> : null}
          {captions.map((caption) => (
            <p key={caption.id} className={caption.final ? "text-ink" : "text-ink/55"}>
              <span className="font-semibold text-tide">{caption.speaker === "caller" ? t("you") : t("agent")}: </span>
              {caption.text}
            </p>
          ))}
        </div>
        {phase === "error" ? (
          <div className="px-4 pb-3">
            <Button size="sm" onClick={() => void start()}>
              {t("retry")}
            </Button>
          </div>
        ) : null}
      </div>
      {showRoom && token && url ? (
        <CallRoom
          token={token}
          url={url}
          onLive={() => {
            if (terminal.current) return;
            setPhase("live");
            stopTimer();
            timer.current = window.setInterval(() => setSeconds((value) => value + 1), 1000);
          }}
          onAgentTimeout={() => fail("agentTimeout")}
          onDisconnected={() => {
            if (terminal.current === "error") return;
            terminal.current = "ended";
            stopTimer();
            setPhase("ended");
            setToken(null);
          }}
          onError={() => fail("network")}
          onCaptions={(caption) =>
            setCaptions((current) => [...current.filter((item) => item.id !== caption.id), caption].slice(-40))
          }
        />
      ) : null}
    </div>
  );
}
