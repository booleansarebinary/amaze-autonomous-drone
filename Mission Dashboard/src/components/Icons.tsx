import type { SVGProps } from "react"

export type IconName = "arrowLeft" | "arrowRight" | "battery" | "check" | "close" | "drone" | "home" | "minus" | "pause" | "play" | "plus" | "retry" | "satellite" | "signal" | "stop" | "sun" | "moon" | "warning"

type IconProps = SVGProps<SVGSVGElement> & { name: IconName size?: number }

export default function Icon({ name, size = 18, ...props }: IconProps) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  }

  const paths: Record<IconName, React.ReactNode> = {
    arrowLeft: (
      <>
        <path d="m15 18-6-6 6-6" />
        <path d="M9 12h11" />
      </>
    ),
    arrowRight: (
      <>
        <path d="m9 18 6-6-6-6" />
        <path d="M4 12h11" />
      </>
    ),
    battery: (
      <>
        <rect x="3" y="7" width="16" height="10" rx="3" />
        <path d="M21 10v4M6.5 10.5h7" />
      </>
    ),
    check: <path d="m5 12 4.2 4.2L19 6.8" />,
    close: (
      <>
        <path d="M7 7l10 10M17 7 7 17" />
      </>
    ),
    drone: (
      <>
        <path d="M8 11h8l2 4H6l2-4Z" />
        <path d="M8 12 4 7M16 12l4-5M3 7h4M17 7h4M12 11V8" />
        <circle cx="5" cy="7" r="2.5" />
        <circle cx="19" cy="7" r="2.5" />
      </>
    ),
    home: (
      <>
        <path d="m4 11 8-7 8 7" />
        <path d="M6.5 10v9h11v-9M10 19v-5h4v5" />
      </>
    ),
    minus: <path d="M5 12h14" />,
    pause: (
      <>
        <path d="M8 6v12M16 6v12" />
      </>
    ),
    play: <path d="m9 6 9 6-9 6V6Z" />,
    plus: <path d="M12 5v14M5 12h14" />,
    retry: (
      <>
        <path d="M19 8V4l-2 2a8 8 0 1 0 2.3 8" />
      </>
    ),
    satellite: (
      <>
        <path d="m8 16 3-3M5 19l3-3M12 4l8 8-4 1-5-5 1-4Z" />
        <path d="M13 15a5 5 0 0 0-4-4M15 18a9 9 0 0 0-7-7" />
      </>
    ),
    signal: (
      <>
        <path d="M5 18v-3M9.5 18v-6M14 18V9M18.5 18V5" />
      </>
    ),
    stop: <rect x="6" y="6" width="12" height="12" rx="3" />,
    sun: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </>
    ),
    moon: <path d="M20 15.5A8.5 8.5 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z" />,
    warning: (
      <>
        <path d="M10.2 4.6 2.8 18a2 2 0 0 0 1.8 3h14.8a2 2 0 0 0 1.8-3L13.8 4.6a2 2 0 0 0-3.6 0Z" />
        <path d="M12 9v4M12 17h.01" />
      </>
    ),
  }

  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      {...common}
      {...props}
    >
      {paths[name]}
    </svg>
  )
}
