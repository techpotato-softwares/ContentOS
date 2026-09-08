const stages = [
  { label: "Train", hint: "Brand voice" },
  { label: "Insights", hint: "What to post" },
  { label: "Generate", hint: "Copy + creative" },
  { label: "Review", hint: "Human yes" },
  { label: "Publish", hint: "LinkedIn live" },
];

export function PipelineVisual() {
  return (
    <div className="pipeline" aria-label="ContentOS workflow">
      {stages.map((stage, i) => (
        <div key={stage.label} className="pipeline-node">
          <div className="pipeline-dot">
            <span>{String(i + 1).padStart(2, "0")}</span>
          </div>
          <p className="mt-3 text-sm font-semibold text-ink">{stage.label}</p>
          <p className="mt-1 text-xs text-steel">{stage.hint}</p>
          {i < stages.length - 1 && <span className="pipeline-connector" aria-hidden />}
        </div>
      ))}
    </div>
  );
}
