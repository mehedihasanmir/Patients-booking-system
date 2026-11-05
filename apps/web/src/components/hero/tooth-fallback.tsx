export function ToothFallback() {
  return (
    <svg viewBox="0 0 200 240" className="h-full w-full" role="img" aria-label="Tooth">
      <defs>
        <linearGradient id="tooth" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#d7f3ef" />
        </linearGradient>
      </defs>
      <ellipse cx="100" cy="126" rx="78" ry="78" fill="none" stroke="#149a96" strokeOpacity="0.45" />
      <path
        d="M100 28c18 0 34 14 38 34 6 28 18 40 18 68 0 36-20 78-38 78s-28-30-38-62c-8 32-22 62-38 62s-28-42-28-78c0-28 12-40 18-68 6-22 22-34 50-34z"
        fill="url(#tooth)"
        stroke="#0f6e68"
        strokeOpacity="0.25"
      />
    </svg>
  );
}
