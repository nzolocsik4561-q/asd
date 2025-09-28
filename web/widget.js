// Minimal widget helper to format metric displays.
export function formatMetric(value, unit = '') {
  const rounded = Number.parseFloat(value).toFixed(2);
  return unit ? `${rounded} ${unit}`.trim() : rounded;
}

export function buildWidgetConfig(title, value, unit) {
  return {
    title,
    value: formatMetric(value, unit),
    generatedAt: new Date().toISOString(),
  };
}

// Emit a demo config when run directly with Node.
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log(buildWidgetConfig('demo', 42, 'pts'));
}
