const withoutDays = [
  { day: "Mon", status: "blank", note: "Blank page" },
  { day: "Tue", status: "late", note: "Still researching" },
  { day: "Wed", status: "rush", note: "Rushed draft" },
  { day: "Thu", status: "skip", note: "Skipped" },
  { day: "Fri", status: "off", note: "Off-brand" },
];

const withDays = [
  { day: "Mon", status: "ready", note: "Draft ready" },
  { day: "Tue", status: "approved", note: "Approved" },
  { day: "Wed", status: "live", note: "Published" },
  { day: "Thu", status: "ready", note: "Carousel queued" },
  { day: "Fri", status: "live", note: "Shipped" },
];

const statusClass: Record<string, string> = {
  blank: "cadence-bad",
  late: "cadence-bad",
  rush: "cadence-warn",
  skip: "cadence-bad",
  off: "cadence-warn",
  ready: "cadence-good",
  approved: "cadence-good",
  live: "cadence-live",
};

export function WeekCadence() {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="cadence-panel">
        <p className="text-xs font-semibold uppercase tracking-wide text-steel">Without ContentOS</p>
        <p className="mt-2 text-lg font-semibold text-ink">A typical LinkedIn week</p>
        <div className="mt-5 grid grid-cols-5 gap-2">
          {withoutDays.map((d) => (
            <div key={d.day} className={`cadence-day ${statusClass[d.status]}`}>
              <span className="text-[10px] font-semibold uppercase tracking-wide opacity-80">
                {d.day}
              </span>
              <span className="mt-2 text-[11px] leading-snug font-medium">{d.note}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="cadence-panel cadence-panel-good">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">With ContentOS</p>
        <p className="mt-2 text-lg font-semibold text-ink">Same week, on rails</p>
        <div className="mt-5 grid grid-cols-5 gap-2">
          {withDays.map((d) => (
            <div key={d.day} className={`cadence-day ${statusClass[d.status]}`}>
              <span className="text-[10px] font-semibold uppercase tracking-wide opacity-80">
                {d.day}
              </span>
              <span className="mt-2 text-[11px] leading-snug font-medium">{d.note}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
