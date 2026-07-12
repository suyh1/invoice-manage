type BrandMarkProps = {
  className?: string;
};

export function BrandMark({ className }: BrandMarkProps) {
  const classes = ["brand-symbol", className].filter(Boolean).join(" ");

  return (
    <svg
      aria-hidden="true"
      className={classes}
      data-brand-mark
      focusable="false"
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect fill="#0a0a0a" height="64" rx="14" width="64" />
      <g
        fill="none"
        stroke="#dededb"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3.5"
      >
        <path d="M19 13h-3a4 4 0 0 0-4 4v4" data-brand-scan-corner />
        <path d="M45 13h3a4 4 0 0 1 4 4v4" data-brand-scan-corner />
        <path d="M19 51h-3a4 4 0 0 1-4-4v-4" data-brand-scan-corner />
        <path d="M45 51h3a4 4 0 0 0 4-4v-4" data-brand-scan-corner />
      </g>
      <path d="M21 17h16l8 8v22H21z" data-brand-invoice fill="#fff" />
      <path d="M37 17v8h8" fill="#ececea" />
      <g fill="none" stroke="#0a0a0a" strokeLinecap="round" strokeWidth="2.6">
        <path d="M27 31h12" />
        <path d="M27 37h12" />
        <path d="M27 43h8" />
      </g>
    </svg>
  );
}
