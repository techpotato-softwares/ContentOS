"use client";

import { FormEvent, HTMLInputTypeAttribute, useState } from "react";

export function ContactForm() {
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="glass-card rounded-2xl border border-accent/35 p-8 md:p-10">
        <p className="eyebrow">Request received</p>
        <h2 className="display mt-3 text-3xl text-ink md:text-4xl">Thanks — we got it.</h2>
        <p className="mt-4 text-lg leading-relaxed text-steel">
          This form is front-end only for now. We&apos;ll follow up on your work email once CRM wiring
          is live. Prefer faster? Email{" "}
          <a href="mailto:hello@contentos.app" className="text-accent hover:underline">
            hello@contentos.app
          </a>
          .
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <span className="trust-chip">
            <span className="trust-chip-dot" />
            Usually reply within 1 business day
          </span>
        </div>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="glass-card rounded-2xl border border-[var(--line)] p-6 md:p-8"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">Demo request</p>
          <p className="mt-1 text-sm text-steel">Takes about a minute. No spam — just a walkthrough.</p>
        </div>
        <span className="trust-chip">
          <span className="trust-chip-dot" />
          20-min session
        </span>
      </div>

      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        <Field label="Full name" name="name" required />
        <Field label="Work email" name="email" type="email" required />
        <Field label="Company" name="company" required />
        <Field label="Role" name="role" />
      </div>

      <div className="mt-5">
        <label htmlFor="segment" className="text-sm font-medium text-ink">
          I am…
        </label>
        <select id="segment" name="segment" className="field-input mt-2" defaultValue="team">
          <option value="team">In-house marketing team</option>
          <option value="agency">Agency</option>
          <option value="founder">Founder / personal brand</option>
          <option value="other">Other</option>
        </select>
      </div>

      <div className="mt-5">
        <label htmlFor="message" className="text-sm font-medium text-ink">
          What should we cover in the demo?
        </label>
        <textarea
          id="message"
          name="message"
          rows={5}
          className="field-input mt-2 resize-y"
          placeholder="Brands, posting volume, approval workflow…"
        />
      </div>

      <button type="submit" className="btn-primary btn-demo mt-7 w-full sm:w-auto">
        Submit request
      </button>
      <p className="mt-4 text-xs text-steel">
        By submitting, you agree we may contact you about ContentOS. No credit card required.
      </p>
    </form>
  );
}

function Field({
  label,
  name,
  type = "text",
  required = false,
}: {
  label: string;
  name: string;
  type?: HTMLInputTypeAttribute;
  required?: boolean;
}) {
  return (
    <div>
      <label htmlFor={name} className="text-sm font-medium text-ink">
        {label}
        {required && <span className="text-accent"> *</span>}
      </label>
      <input id={name} name={name} type={type} required={required} className="field-input mt-2" />
    </div>
  );
}
