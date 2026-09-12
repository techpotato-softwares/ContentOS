import Image from "next/image";

type Variant = "panel" | "banner" | "card" | "flush";

type Props = {
  src: string;
  alt: string;
  className?: string;
  priority?: boolean;
  sizes?: string;
  variant?: Variant;
  eyebrow?: string;
  caption?: string;
  badge?: string;
};

/** Branded marketing imagery — framed like ContentOS product surfaces. */
export function MarketingImage({
  src,
  alt,
  className = "",
  priority = false,
  sizes = "(max-width: 768px) 100vw, 50vw",
  variant = "panel",
  eyebrow,
  caption,
  badge,
}: Props) {
  const showMeta = Boolean(eyebrow || caption || badge);

  return (
    <figure className={`img-stage img-stage-${variant} relative ${className}`}>
      <div className="img-atmosphere" aria-hidden>
        <span className="img-orb img-orb-a" />
        <span className="img-orb img-orb-b" />
      </div>

      <div className="img-shell">
        {variant !== "flush" && (
          <div className="img-chrome" aria-hidden>
            <span className="img-chrome-dots">
              <i />
              <i />
              <i />
            </span>
            <span className="img-chrome-title">ContentOS</span>
            {badge ? <span className="img-chrome-badge">{badge}</span> : null}
          </div>
        )}

        <div className="img-frame">
          <Image
            src={src}
            alt={alt}
            fill
            priority={priority}
            loading={priority ? undefined : "lazy"}
            sizes={sizes}
            className="img-photo object-cover"
          />
          <div className="img-scrim" aria-hidden />
          <div className="img-edge-glow" aria-hidden />
          <span className="img-corner img-corner-tl" aria-hidden />
          <span className="img-corner img-corner-br" aria-hidden />

          {showMeta && (
            <figcaption className="img-meta">
              {eyebrow ? <p className="img-meta-eyebrow">{eyebrow}</p> : null}
              {caption ? <p className="img-meta-caption">{caption}</p> : null}
            </figcaption>
          )}
        </div>
      </div>
    </figure>
  );
}

/** Full-bleed atmospheric layer for heroes — soft light behind content. */
export function HeroAtmosphere({
  src = "/images/hero-atmosphere.webp",
  opacity = 0.4,
  priority = true,
}: {
  src?: string;
  opacity?: number;
  priority?: boolean;
}) {
  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden>
      <div className="img-atmosphere img-atmosphere-hero is-animated">
        <span className="img-orb img-orb-a" />
        <span className="img-orb img-orb-b" />
      </div>
      <Image
        src={src}
        alt=""
        fill
        priority={priority}
        sizes="100vw"
        className="object-cover"
        style={{ opacity }}
      />
      <div className="absolute inset-0 bg-gradient-to-r from-[#07110e] via-[#07110e]/88 to-[#07110e]/55" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#07110e] via-transparent to-[#07110e]/70" />
    </div>
  );
}
