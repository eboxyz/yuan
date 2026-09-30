// Dev-only. Compiles tracker-setup/templates/dashboard/static/tailwind.css, which every
// generated dashboard loads locally (no CDN). Theme moved here from _partials.j2.
// Rebuild after changing classes in the dashboard templates: ./build.sh (./build.sh --check to verify).
const base = {
    darkMode: "class",
    theme: { extend: {
      "colors": {
        "surface-container": "#f9ecde", "on-tertiary-fixed": "#002204", "error-container": "#ffdad6",
        "surface-dim": "#e5d8ca", "background": "#fff8f3", "primary": "#b71422", "on-error": "#ffffff",
        "on-background": "#211b12", "secondary-fixed": "#ffe16d", "on-surface": "#211b12", "on-primary": "#ffffff",
        "surface-container-highest": "#eee0d2", "outline-variant": "#e4beba", "on-primary-fixed": "#410004",
        "on-secondary-fixed": "#221b00", "surface": "#fff8f3", "on-surface-variant": "#5b403e",
        "tertiary-fixed-dim": "#78dc77", "on-primary-container": "#fffbff", "inverse-primary": "#ffb3ae",
        "surface-container-lowest": "#ffffff", "on-secondary-fixed-variant": "#544600", "surface-tint": "#ba1724",
        "surface-container-low": "#fff1e3", "on-primary-fixed-variant": "#930014", "error": "#ba1a1a",
        "primary-container": "#db3237", "outline": "#8f6f6d", "inverse-on-surface": "#fcefe0",
        "inverse-surface": "#362f26", "surface-variant": "#eee0d2", "secondary-container": "#fcd400",
        "surface-bright": "#fff8f3", "tertiary-container": "#1e862d", "on-secondary-container": "#6e5c00",
        "on-error-container": "#93000a", "primary-fixed-dim": "#ffb3ae", "tertiary-fixed": "#94f990",
        "primary-fixed": "#ffdad7", "tertiary": "#006b1b", "on-tertiary-fixed-variant": "#005313",
        "on-secondary": "#ffffff", "on-tertiary": "#ffffff", "on-tertiary-container": "#f7fff1",
        "secondary-fixed-dim": "#e9c400", "surface-container-high": "#f3e6d8", "secondary": "#705d00"
      },
      "borderRadius": { "DEFAULT": "1rem", "lg": "2rem", "xl": "3rem", "full": "9999px" },
      "spacing": { "section-margin": "48px", "stack-gap": "12px", "gutter": "16px", "unit": "8px", "container-padding": "24px" },
      "fontFamily": {
        "headline-lg-mobile": ["Plus Jakarta Sans"], "label-caps": ["Quicksand"], "body-lg": ["Quicksand"],
        "body-md": ["Quicksand"], "headline-md": ["Plus Jakarta Sans"], "headline-lg": ["Plus Jakarta Sans"]
      },
      "fontSize": {
        "headline-lg-mobile": ["32px", { "lineHeight": "1.2", "fontWeight": "800" }],
        "label-caps": ["14px", { "lineHeight": "1.0", "letterSpacing": "0.05em", "fontWeight": "700" }],
        "body-lg": ["18px", { "lineHeight": "1.6", "fontWeight": "500" }],
        "body-md": ["16px", { "lineHeight": "1.5", "fontWeight": "500" }],
        "headline-md": ["28px", { "lineHeight": "1.3", "fontWeight": "700" }],
        "headline-lg": ["40px", { "lineHeight": "1.2", "letterSpacing": "-0.02em", "fontWeight": "800" }]
      }
    } }
  };
module.exports = {
  ...base,
  content: [
    "../../tracker-setup/templates/dashboard/*.j2",
    "../../tracker-setup/scripts/generate_project.py",  // stage-chip classes are chosen there
  ],
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/container-queries")],
};
