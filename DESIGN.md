# Design

## Theme

An author works during a focused afternoon review session on a laptop, comparing source chapters against generated screenplay scenes and fixing structure errors before submitting a demo. The interface should be light, quiet, and editorial, with enough density for real work.

## Color

Use a restrained light product palette with tinted neutrals and one practical accent.

- Surface: `oklch(98% 0.006 85)`
- Panel: `oklch(95.5% 0.008 85)`
- Panel Strong: `oklch(92% 0.01 85)`
- Text: `oklch(24% 0.012 75)`
- Muted Text: `oklch(49% 0.018 75)`
- Border: `oklch(86% 0.012 85)`
- Accent: `oklch(56% 0.12 190)`
- Accent Soft: `oklch(93% 0.035 190)`
- Success: `oklch(58% 0.11 150)`
- Warning: `oklch(68% 0.12 75)`
- Error: `oklch(57% 0.14 28)`

## Typography

Use system UI fonts:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
```

Keep product text compact:

- Page title: 20px, 700
- Section title: 14px, 700
- Body: 14px, 400
- Label: 12px, 600
- Code/YAML: 13px, monospace

## Layout

Use a full-height product shell:

- Top bar: fixed height, project status, model status, exports.
- Left rail: source input, chapter tree, source paragraphs.
- Main panel: pipeline, story bible summary, scene cards.
- Right panel: YAML editor, preview, validation tabs.

Desktop is primary. Mobile should remain readable by stacking panels vertically, but the main demo target is laptop/desktop.

## Components

- Buttons use consistent rectangular controls with 6px radius.
- Cards are only for scene items and repeated story objects.
- Use tabs for YAML/Preview/Errors.
- Use badges for provider status, validation state, scene metadata.
- Use inline error panels instead of blocking modals.

## Motion

Use minimal 150ms transitions for hover, selected tabs, and loading state changes. Do not animate layout or run decorative page-load choreography.
