import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  useVideoConfig as _, // keep import but avoid unused warning
} from "remotion";

interface HeroTitleProps {
  title: string;
  subtitle?: string;
  accentColor?: string;
}

export const HeroTitle: React.FC<HeroTitleProps> = ({
  title,
  subtitle,
  accentColor = "#22D3EE",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Split on "|" for 2-line titles, or use the full text as one line
  const lines = title.includes("|")
    ? title.split("|").map((l) => l.trim())
    : [title];

  // Per-character spring for each line
  const renderLine = (line: string, lineIndex: number) => {
    const chars = line.split("");
    const lineOffset = lineIndex * 25; // stagger each line

    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          flexWrap: "wrap",
          gap: 2,
          overflow: "hidden",
        }}
      >
        {chars.map((char, i) => {
          const delay = lineOffset + i * 1.5;
          const charSpring = spring({
            frame: frame - delay,
            fps,
            config: { damping: 10, stiffness: 160 },
          });

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                opacity: charSpring,
                transform: `translateY(${interpolate(charSpring, [0, 1], [40, 0])}px)`,
                color: charSpring < 1
                  ? "rgba(255,255,255,0.3)"
                  : lineIndex === 0 ? accentColor : "#FFFFFF",
                textShadow:
                  lineIndex === 0 && charSpring >= 1
                    ? `0 0 20px ${accentColor}44, 0 0 40px ${accentColor}22`
                    : "0 2px 8px rgba(0,0,0,0.5)",
                whiteSpace: char === " " ? "pre" as const : undefined,
                minWidth: char === " " ? "0.3em" : undefined,
              }}
            >
              {char}
            </span>
          );
        })}
      </div>
    );
  };

  const lastCharOffset = lines.reduce((sum, l) => sum + l.length * 1.5, 0);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background:
          "radial-gradient(ellipse at center, rgba(15,23,42,0.35) 0%, rgba(15,23,42,0.55) 100%)",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: "88%" }}>
        {/* Title lines */}
        <div
          style={{
            fontSize: 80,
            fontWeight: 800,
            fontFamily: "Space Grotesk, Inter, system-ui, sans-serif",
            lineHeight: 1.3,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {lines.map((line, i) => (
            <div key={i}>{renderLine(line, i)}</div>
          ))}
        </div>

        {/* Subtitle */}
        {subtitle && (
          <div
            style={{
              marginTop: 28,
              opacity: spring({
                frame: frame - lastCharOffset - 8,
                fps,
                config: { damping: 20 },
              }),
              transform: `translateY(${interpolate(
                spring({
                  frame: frame - lastCharOffset - 8,
                  fps,
                  config: { damping: 15, stiffness: 80 },
                }),
                [0, 1],
                [12, 0]
              )}px)`,
              fontSize: 24,
              fontWeight: 500,
              color: "#94A3B8",
              fontFamily: "Space Grotesk, Inter, system-ui, sans-serif",
              letterSpacing: "0.15em",
              textTransform: "uppercase",
            }}
          >
            {subtitle}
          </div>
        )}

        {/* Animated underline */}
        <div
          style={{
            margin: "28px auto 0",
            height: 3,
            backgroundColor: accentColor,
            borderRadius: 2,
            boxShadow: `0 0 12px ${accentColor}66`,
            width: interpolate(
              spring({
                frame: frame - lastCharOffset - 10,
                fps,
                config: { damping: 12, stiffness: 50 },
              }),
              [0, 1],
              [0, 320]
            ),
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
