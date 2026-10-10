// Lityra app icon supplied in dark and light variants.
export function Logo({ className = "", dark = false, size = 64 }) {
  return (
    <span className={`inline-flex items-center ${className}`}>
      <img
        src={dark ? "/brand/favicon-dark.png" : "/brand/favicon-light.png"}
        alt="Lityra"
        className="object-contain rounded-lg"
        style={{ height: size, width: size }}
      />
    </span>
  );
}
