import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface TextCardProps {
  text: string;
  subtitle?: string;
  fontSize?: number;
  color?: string;
  accentColor?: string;
  backgroundColor?: string;
}

export const TextCard: React.FC<TextCardProps> = ({
  text,
  subtitle,
  fontSize = 48,
  color = "#FFFFFF",
  accentColor = "#F59E0B",
  backgroundColor = "#0F172A",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Card slide-up entrance
  const cardSpring = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 90 },
    from: 1.1,
    to: 1,
  });

  const cardOpacity = spring({
    frame,
    fps,
    config: { damping: 22 },
    from: 0,
    to: 1,
  });

  // Accent bar grow
  const barSpring = spring({
    frame: frame - 4,
    fps,
    config: { damping: 14, stiffness: 70 },
  });

  // Text fade-in (slightly delayed)
  const textOpacity = spring({
    frame: frame - 6,
    fps,
    config: { damping: 20 },
  });

  // Subtitle fade-in
  const subOpacity = spring({
    frame: frame - 10,
    fps,
    config: { damping: 20 },
  });

  const subSlide = spring({
    frame: frame - 10,
    fps,
    config: { damping: 15, stiffness: 80 },
  });

  // Fade-out at end of scene (last 12 frames)
  const { durationInFrames } = useVideoConfig();
  const fadeOutStart = durationInFrames - 12;
  const fadeOut = interpolate(frame, [fadeOutStart, durationInFrames], [1, 0.3], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Split on | for two-line display
  const lines = text.includes("|")
    ? text.split("|").map((l) => l.trim())
    : [text];

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: `linear-gradient(135deg, ${backgroundColor} 0%, #1E293B 100%)`,
        padding: 40,
      }}
    >
      {/* Card container */}
      <div
        style={{
          opacity: cardOpacity * fadeOut,
          transform: `translateY(${interpolate(cardSpring, [0, 1], [60, 0])}px) scale(${cardSpring})`,
          background: `linear-gradient(160deg, rgba(30,41,59,0.95) 0%, rgba(15,23,42,0.98) 100%)`,
          borderRadius: 20,
          border: `1px solid ${accentColor}33`,
          padding: "48px 52px",
          maxWidth: "86%",
          width: "100%",
          boxShadow: `0 0 40px ${accentColor}15, 0 8px 32px rgba(0,0,0,0.4)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        {/* Accent bar */}
        <div
          style={{
            height: 4,
            width: interpolate(barSpring, [0, 1], [0, 80]),
            backgroundColor: accentColor,
            borderRadius: 2,
            marginBottom: 28,
            boxShadow: `0 0 12px ${accentColor}44`,
          }}
        />

        {/* Text */}
        <div
          style={{
            opacity: textOpacity * fadeOut,
            fontSize,
            color,
            fontFamily: "Inter, system-ui, sans-serif",
            fontWeight: 700,
            textAlign: "center",
            lineHeight: 1.3,
            textShadow: "0 2px 8px rgba(0,0,0,0.4)",
            maxWidth: "100%",
          }}
        >
          {lines.map((line, i) => (
            <div key={i} style={{ marginBottom: i < lines.length - 1 ? 6 : 0 }}>
              {line}
            </div>
          ))}
        </div>

        {/* Subtitle */}
        {subtitle && (
          <div
            style={{
              marginTop: 20,
              opacity: subOpacity * fadeOut,
              transform: `translateY(${interpolate(subSlide, [0, 1], [10, 0])}px)`,
              fontSize: 22,
              fontWeight: 400,
              color: accentColor,
              fontFamily: "Inter, system-ui, sans-serif",
              letterSpacing: "0.05em",
              textAlign: "center",
              maxWidth: "90%",
              lineHeight: 1.4,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
