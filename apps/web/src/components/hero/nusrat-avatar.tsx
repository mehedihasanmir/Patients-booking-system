"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useVoice } from "@/lib/voice";

export function NusratAvatar({ status }: { status: string }) {
  const t = useTranslations("call");
  const level = useVoice((state) => state.level);
  const callerLevel = useVoice((state) => state.callerLevel);
  const active = useVoice((state) => state.active);
  const [mouth, setMouth] = useState(0);
  const [listen, setListen] = useState(0);
  const levelRef = useRef(level);
  const callerRef = useRef(callerLevel);
  levelRef.current = level;
  callerRef.current = callerLevel;

  useEffect(() => {
    let frame = 0;
    let shown = 0;
    let heard = 0;
    let lastMouth = -1;
    let lastListen = -1;
    const tick = () => {
      shown += (levelRef.current - shown) * 0.38;
      heard += (callerRef.current - heard) * 0.3;
      if (Math.abs(shown - lastMouth) > 0.012 || Math.abs(heard - lastListen) > 0.012) {
        lastMouth = shown;
        lastListen = heard;
        setMouth(shown);
        setListen(heard);
      }
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const speaking = mouth > 0.045;
  const listening = !speaking && listen > 0.05;
  const label = speaking ? t("speaking") : listening ? t("listening") : status;
  const open = Math.min(1, mouth * 5.4);
  const tilt = listening ? -0.8 : 0;
  const mouthMask = "radial-gradient(ellipse 22% 13% at 50% 55%, #000 46%, transparent 76%)";

  return (
    <div className="relative h-full min-h-[280px] overflow-hidden bg-[#d5e4e0]">
      <div
        className="absolute inset-0 origin-center transition-transform duration-500"
        style={{ transform: `rotate(${tilt}deg)` }}
      >
        <div className="nusrat-breath absolute inset-0 origin-center">
          <img
            src="/nusrat/nusrat-idle.jpg"
            alt=""
            className="absolute inset-0 h-full w-full object-cover object-[center_38%]"
          />
          <img
            src="/nusrat/nusrat-speak.jpg"
            alt=""
            className="absolute inset-0 h-full w-full object-cover object-[center_38%]"
            style={{ opacity: Math.min(1, open * 1.15), WebkitMaskImage: mouthMask, maskImage: mouthMask }}
          />
        </div>
      </div>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[#072e2c]/20 to-transparent" />

      <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full bg-white/90 px-3 py-1.5 text-xs shadow-card backdrop-blur">
        <span
          className={`h-2.5 w-2.5 rounded-full ${speaking ? "bg-tide" : listening ? "bg-gold" : active ? "bg-tide" : "bg-ink/30"}`}
          style={{ transform: `scale(${1 + (speaking ? open : listen) * 0.6})` }}
        />
        <span className="bn font-semibold text-deep">{label}</span>
      </div>

      <p className="bn absolute right-4 top-4 rounded-full bg-white/90 px-3 py-1.5 text-xs font-semibold text-deep shadow-card">
        {t("agent")}
      </p>

      <div className="absolute bottom-4 left-4 right-4 flex items-end gap-3">
        <Meter label={t("you")} value={listen} tone="bg-gold" />
        <Meter label={t("agent")} value={open} tone="bg-tide" />
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}

function Meter({ label, value, tone }: { label: string; value: number; tone: string }) {
  const bars = [0.35, 0.7, 1, 0.75, 0.45];
  return (
    <div className="flex items-end gap-1 rounded-2xl bg-white/85 px-2 py-1.5 backdrop-blur">
      <span className="bn pb-0.5 text-[10px] font-semibold text-ink/70">{label}</span>
      {bars.map((scale, index) => (
        <span
          key={index}
          className={`w-1 rounded-full ${tone}`}
          style={{ height: `${6 + Math.min(1, value * 1.4) * 18 * scale}px`, opacity: 0.35 + value }}
        />
      ))}
    </div>
  );
}
