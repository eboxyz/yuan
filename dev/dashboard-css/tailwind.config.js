// Dev-only. Compiles tracker-setup/templates/dashboard/static/tailwind.css, which every
// generated dashboard loads locally (no CDN). Theme moved here from _partials.j2.
// Colours: the Yuan palette (designs/serene_bamboo_sanctuary, Material 3 tokens), except
// on-primary-container and on-tertiary-container are white: the design's tinted values
// were only ~4.5:1 on small bold text; white is 6.4:1. secondary-container is a softer
// mint (#c3ecd6, user asked for softer than the design's #92f7c3; menu text stays 4.6:1).
// Rebuild after changing classes in the dashboard templates: ./build.sh (./build.sh --check to verify).
const base = {
    darkMode: "class",
    theme: { extend: {
      "colors": {
        "surface-container": "#efeeeb", "on-tertiary-fixed": "#3c0700", "error-container": "#ffdad6",
        "surface-dim": "#dbdad7", "background": "#fbf9f6", "primary": "#0f5238", "on-error": "#ffffff",
        "on-background": "#1b1c1a", "secondary-fixed": "#92f7c3", "on-surface": "#1b1c1a", "on-primary": "#ffffff",
        "surface-container-highest": "#e4e2df", "outline-variant": "#bfc9c1", "on-primary-fixed": "#002114",
        "on-secondary-fixed": "#002113", "surface": "#fbf9f6", "on-surface-variant": "#404943",
        "tertiary-fixed-dim": "#ffb4a2", "on-primary-container": "#ffffff", "inverse-primary": "#95d4b3",
        "surface-container-lowest": "#ffffff", "on-secondary-fixed-variant": "#005235", "surface-tint": "#2c694e",
        "surface-container-low": "#f5f3f0", "on-primary-fixed-variant": "#0e5138", "error": "#ba1a1a",
        "primary-container": "#2d6a4f", "outline": "#707973", "inverse-on-surface": "#f2f0ed",
        "inverse-surface": "#30312f", "surface-variant": "#e4e2df", "secondary-container": "#c3ecd6",
        "surface-bright": "#fbf9f6", "tertiary-container": "#a43e24", "on-secondary-container": "#00734d",
        "on-error-container": "#93000a", "primary-fixed-dim": "#95d4b3", "tertiary-fixed": "#ffdad2",
        "primary-fixed": "#b1f0ce", "tertiary": "#84270f", "on-tertiary-fixed-variant": "#83260e",
        "on-secondary": "#ffffff", "on-tertiary": "#ffffff", "on-tertiary-container": "#ffffff",
        "secondary-fixed-dim": "#75daa8", "surface-container-high": "#eae8e5", "secondary": "#006c48"
      },
      "borderRadius": { "DEFAULT": "1rem", "lg": "2rem", "xl": "3rem", "full": "9999px" },
      "spacing": { "section-margin": "48px", "stack-gap": "12px", "gutter": "16px", "unit": "8px", "container-padding": "24px" },
      "fontFamily": {
        "headline-lg-mobile": ["Plus Jakarta Sans"], "label-caps": ["Plus Jakarta Sans"], "body-lg": ["Plus Jakarta Sans"],
        "body-md": ["Plus Jakarta Sans"], "headline-md": ["Plus Jakarta Sans"], "headline-lg": ["Plus Jakarta Sans"]
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
