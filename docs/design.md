# Design system — "calm futuristic"

Futuristic but professional: think mission-control dashboard, not gaming UI.
Dark-first, depth through glass and light, color used for meaning.

## Tokens (CSS variables in `static/css/app.css`)
- Background: `#070A12` (base), `#0C1120` (raised), subtle radial glow top-left (accent at 8 % opacity).
- Surface: glass cards — `rgba(255,255,255,0.04)`, 1px border `rgba(255,255,255,0.08)`, `backdrop-blur`, radius 16px.
- Text: `#E6EAF2` primary, `#8A93A6` secondary, `#5A6377` muted.
- Accent: cyan `#22D3EE` (primary action, focus), violet `#8B5CF6` (secondary, AI features).
- Meaning: income/positive `#34D399`, spending/negative `#F87171`, warning `#FBBF24`.
- Chart series: 8 categorical slots in `web/charts.py::CATEGORICAL` (dataviz reference, dark steps), assigned in order, never cycled; 9+ → "Other". Same color everywhere a category appears.
- Light theme: optional, later.

## Type
- Inter for UI; **JetBrains Mono / tabular numbers for all amounts** (columns line up, feels "instrument").
- Amounts: `12 345 kr` (nb-NO, narrow no-break space grouping, `insights.formatting.format_nok`); negative shown with − sign and red.

## Components
- Sidebar (icons + labels, collapsible), top bar with global date-range picker + import button.
- KPI tile: label, big number, delta chip vs. previous period, tiny sparkline.
- Chart card: title, one-line insight sentence above the chart ("Food is up 18 % vs. average").
- Tables: sticky header, row hover glow, inline category pill (click to change).
- Empty states with one clear next action.
- AI content marked with a violet edge + "AI" chip and a "what the AI saw" link.

## Motion + interaction
- 150–250 ms ease-out; numbers count up on load; charts animate in once, not on every update.
- Hover on any chart point → tooltip with exact value; click → drill-down to transactions.
- Keyboard: `/` search, `g d` dashboard, `g t` transactions. Respect `prefers-reduced-motion`.

## Charts (ECharts shared theme)
- Transparent background, faint grid lines, no chart junk, direct labels over legends where possible.
- Gradient area fills (accent → transparent) for trends; rounded bars.
