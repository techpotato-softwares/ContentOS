# Content OS × LinkedIn Skills — Feature Map

Roadmap companion for embedding the quality IP from this repo into a **Content OS** product (generator + calendar + brand voice + optional publish). This is **not** a plan to run autonomous LinkedIn engagement bots.

**Sister doc:** [`CLIPX-FEATURE-MAP.md`](./CLIPX-FEATURE-MAP.md) — asset → channel-native transform (repurpose wedge). Share one quality layer; do not duplicate product surfaces.

**How to use this doc**

1. Pick a phase (P0 → P3) for the next sprint.
2. Open the linked skill / reference; treat those files as the source of truth for rules and copy.
3. Port logic into Content OS as product features (templates, scorers, rewrite passes), not as Claude skill loaders unless you explicitly want agent-mode UX.

**Linear (ContentOS Full Build)** — epic [TEC-99 · 0094](https://linear.app/techpotato-2/issue/TEC-99); milestone *LinkedIn Skills Quality Layer*. Sort by title (letters matter).

| Order | Ticket | Feature |
|---|---|---|
| P0 | 0095a → 0095b → 0096 → 0097a → 0097b → 0098 → 0099 → 0100a → 0100b | Niche → algo → kit → angles → hooks → draft → humanizer → audit → approval gates |
| P1 | 0102 → 0103 → 0104 → 0105 → 0106 | Planner → repurpose → illustrate → profile → optional QA |
| P2 | 0107a → 0107b → 0108 → 0109a → 0109b → 0109c → 0110 | Taxonomy → benchmarks → extractor → comment → reply → segments → threads |
| P3 | 0113 | Employee advocacy |

Build order hub: [TEC-5 · START HERE](https://linear.app/techpotato-2/issue/TEC-5). Gaps `0101` / `0111` / `0112` intentional after resequence.

**Product thesis (keep forever)**

The agent is **trained on the customer’s niche** and **understands each platform’s algorithm** (LinkedIn, Instagram, and later channels) before it suggests or builds anything. Content OS does **not** blindly spray posts onto social — it only recommends and drafts work that is positioned to earn **measurable reach, engagement, and growth**. We believe in **numbers that add value**: impressions, meaningful interactions, saves/shares, follower quality, and pipeline outcomes — not vanity volume.

**Design principle (keep forever)**

```
Niche + brand kit + platform algo model
  → Brief / goal (growth metric, not “just post”)
  → Hook + angle selection (platform-native)
  → Draft trained on niche patterns that win
  → Humanizer + algo checklist (LinkedIn / Instagram / …)
  → Optional: image + schedule
  → Human approve → publish
  → Learn from numbers → retrain suggestions
```

Do **not** auto-publish without approval. See [`lib/approval.py`](../lib/approval.py).

---

## Pipeline overview

| Stage | Content OS feature | Primary sources |
|---|---|---|
| 0. Niche | Niche training + ICP / category model | Brand kit + niche corpus (F-00); [`references/voice-profile.md`](../references/voice-profile.md) |
| 1. Brand | Voice & brand profile | [`references/voice-profile.md`](../references/voice-profile.md) |
| 2. Plan | Calendar / pillars / week mix | [`linkedin-content-planner`](../skills/linkedin-content-planner/SKILL.md) |
| 3. Angle | Founder / topic angles | [`references/founder-topics.md`](../references/founder-topics.md) |
| 4. Hook | Formula picker by goal | [`references/hook-formulas.md`](../references/hook-formulas.md) |
| 5. Draft | Post generator (niche + platform native) | [`linkedin-post-writer`](../skills/linkedin-post-writer/SKILL.md) |
| 6. QA | Humanize + audit | [`linkedin-humanizer`](../skills/linkedin-humanizer/SKILL.md) |
| 7. Algo | Platform algorithm checklist (LI / IG / …) | [`references/algorithm-heuristics.md`](../references/algorithm-heuristics.md) · F-00 |
| 8. Visual | Illustrate / quote card | [`lib/pixfaro_client.py`](../lib/pixfaro_client.py), humanizer illustration sub-skill |
| 9. Ship | Approve + publish / schedule | [`lib/publora_client.py`](../lib/publora_client.py), [`lib/approval.py`](../lib/approval.py) |
| 10. Learn | Hook reverse-engineer + growth loop | [`linkedin-hook-extractor`](../skills/linkedin-hook-extractor/SKILL.md) · F-16 |
| 11. Repurpose | Cross-platform → channel-native | [`linkedin-repurposer`](../skills/linkedin-repurposer/SKILL.md) |

---

## Priority legend

| Priority | Meaning for Content OS |
|---|---|
| **P0** | Core generator moat — ship first |
| **P1** | Differentiated product depth — next |
| **P2** | Growth / distribution / research add-ons |
| **P3** | Team / enterprise / later modules |
| **Skip** | Do not build into Content OS as autopilot growth |

---

## P0 — Generator moat (must add)

These turn a generic LLM writer into a **niche-trained, algorithm-aware** quality engine — not a blind social poster.

### F-00 · Niche-trained agent + platform algorithm intelligence

| Field | Detail |
|---|---|
| **Content OS feature** | Train / condition the agent on the customer’s **niche** (industry, ICP, offer, proof patterns, taboo topics) and on **per-platform algorithm models** (LinkedIn feed, Instagram Reels/feed/Stories). Generation and suggestions only run *after* niche + platform context is loaded. |
| **User value** | Content that can go **viral *in their niche*** — shaped for how LinkedIn vs Instagram actually rank and distribute — instead of generic AI copy blasted to every network. Growth is judged by **numbers that matter** (reach quality, saves, shares, comments that convert, follower quality, pipeline), not post count. |
| **Product stance** | **No blind posting.** Suggest → draft → score against niche + algo → human approve. Refuse or warn when a brief ignores niche fit or platform constraints. |
| **Implement from** | Niche: extend [`references/voice-profile.md`](../references/voice-profile.md) (ICP, examples, hard rules) + optional corpus of winning niche posts. Algo: [`references/algorithm-heuristics.md`](../references/algorithm-heuristics.md) (LinkedIn); add Instagram algorithm heuristics as a sibling reference when shipping IG. Scoring ties to F-05 audit + F-16 metrics taxonomy. |
| **Also wire** | F-01 brand kit · F-02 goals that map to growth metrics · F-03/F-05 draft + pass/fail · F-12 niche-aware hook learning · F-16 dashboards for value/growth KPIs |
| **Platforms (v1 → v2)** | **v1:** LinkedIn-first niche + algo. **v2:** Instagram (format, retention, audio/visual hooks, hashtag/search) with the same “train → understand algo → then suggest/build” gate. |
| **Acceptance** | (1) Generation blocked or warned if niche profile incomplete. (2) Every suggestion states target platform + algo rationale (e.g. dwell, early engagement, saves). (3) UI surfaces predicted/tracked growth metrics — not “posted successfully” alone. (4) No auto-publish path that skips niche/algo checks. |

### F-01 · Voice & brand kit

| Field | Detail |
|---|---|
| **Content OS feature** | Onboarding form + editable brand kit that every generation pass loads |
| **User value** | Posts sound like the customer, not like ChatGPT |
| **Implement from** | [`references/voice-profile.md`](../references/voice-profile.md) (sections 1–6: fingerprint, ICP, hard rules, CTA, examples, brand assets) |
| **Also enforce** | [`references/voice-rules.md`](../references/voice-rules.md) · root summary in [`SKILL.md`](../SKILL.md) §Voice rules |
| **Builder UX** | Optional auto-fill from past posts: [`skills/linkedin-humanizer/sub-skills/voice-profile.md`](../skills/linkedin-humanizer/sub-skills/voice-profile.md) · [`skills/linkedin-humanizer/references/voice-fingerprint.md`](../skills/linkedin-humanizer/references/voice-fingerprint.md) |
| **Acceptance** | Drafts refuse to ship if brand kit `filled: no` *or* clearly fall back to global voice rules with a UI warning |

### F-02 · Hook formula library + goal-based picker

| Field | Detail |
|---|---|
| **Content OS feature** | “Pick hook by goal” (comments / reposts / likes / saves) → fill skeleton → draft |
| **User value** | Structured openings with proven shapes instead of random first lines |
| **Implement from** | [`references/hook-formulas.md`](../references/hook-formulas.md) (F1–F20) |
| **Skill workflow** | [`skills/linkedin-post-writer/SKILL.md`](../skills/linkedin-post-writer/SKILL.md) (formula table + engagement-goal split) |
| **Local copy note** | Post-writer also mirrors hooks at [`skills/linkedin-post-writer/references/hook-formulas.md`](../skills/linkedin-post-writer/references/hook-formulas.md) — **prefer root** as canonical |
| **Acceptance** | User can select goal → see 2–4 formula options → generate into chosen skeleton |

### F-03 · Post draft generator (LinkedIn-native)

| Field | Detail |
|---|---|
| **Content OS feature** | Single-post generator: topic + goal + formula → draft in sweet-spot length |
| **Implement from** | [`skills/linkedin-post-writer/SKILL.md`](../skills/linkedin-post-writer/SKILL.md) |
| **Hard constraints** | 900–1,300 chars · hook in first ~210 chars (mobile fold) — see [`references/voice-rules.md`](../references/voice-rules.md) and [`references/algorithm-heuristics.md`](../references/algorithm-heuristics.md) |
| **Checklist before return** | [`skills/linkedin-post-writer/references/humanizer-checklist.md`](../skills/linkedin-post-writer/references/humanizer-checklist.md) |
| **Acceptance** | Output includes hook formula id, char count, fold preview, CTA placement note |

### F-04 · Humanizer (AI-tell scrub)

| Field | Detail |
|---|---|
| **Content OS feature** | Post-generation rewrite pass + “Fix AI slop” button on any draft |
| **Implement from** | [`skills/linkedin-humanizer/SKILL.md`](../skills/linkedin-humanizer/SKILL.md) |
| **Rules** | [`skills/linkedin-humanizer/references/scrub-rules.md`](../skills/linkedin-humanizer/references/scrub-rules.md) · tiers: [`tier-rationale.md`](../skills/linkedin-humanizer/references/tier-rationale.md) · examples: [`examples.md`](../skills/linkedin-humanizer/references/examples.md) |
| **UI modes** | forensic / strict / aesthetic / all (match skill tiers) |
| **Acceptance** | Density of blacklisted vocab + em-dash rate reported; rewrite is optional, never silent |

### F-05 · Pre-publish audit (pass / fail)

| Field | Detail |
|---|---|
| **Content OS feature** | Scorecard before “Ready to schedule”: algo + AI-tell gates |
| **Implement from** | [`skills/linkedin-humanizer/sub-skills/post-audit.md`](../skills/linkedin-humanizer/sub-skills/post-audit.md) |
| **Checklists** | [`audit-checklist.md`](../skills/linkedin-humanizer/references/audit-checklist.md) · [`audit-ai-tells.md`](../skills/linkedin-humanizer/references/audit-ai-tells.md) · examples: [`audit-examples.md`](../skills/linkedin-humanizer/references/audit-examples.md) |
| **Algo rules** | [`references/algorithm-heuristics.md`](../references/algorithm-heuristics.md) (timing, length, hashtags, link placement, first 60 min, penalties) |
| **Mirrored copy** | [`skills/linkedin-post-writer/references/algorithm-heuristics.md`](../skills/linkedin-post-writer/references/algorithm-heuristics.md) — prefer root |
| **Acceptance** | Draft shows pass/fail per rule; blocking fails require override reason |

### F-06 · Founder angle library

| Field | Detail |
|---|---|
| **Content OS feature** | Toggle “Founder mode” → suggest A1–A10 angles before formula pick |
| **Implement from** | [`references/founder-topics.md`](../references/founder-topics.md) |
| **Paired formulas** | F17–F20 in [`references/hook-formulas.md`](../references/hook-formulas.md) |
| **Planner pillars** | Founders set in [`skills/linkedin-content-planner/references/pillars-framework.md`](../skills/linkedin-content-planner/references/pillars-framework.md) (Conviction / Building in public / The math / Proof) |
| **Acceptance** | Founder users get angle → formula → draft path; general users skip angles |

---

## P1 — Calendar, repurpose, profile (product depth)

### F-07 · Weekly / monthly content planner

| Field | Detail |
|---|---|
| **Content OS feature** | Calendar generator: pillars, formats, hooks, times, comment targets |
| **Implement from** | [`skills/linkedin-content-planner/SKILL.md`](../skills/linkedin-content-planner/SKILL.md) |
| **Framework** | [`pillars-framework.md`](../skills/linkedin-content-planner/references/pillars-framework.md) |
| **Example output** | [`example-plan-week.md`](../skills/linkedin-content-planner/references/example-plan-week.md) |
| **Acceptance** | 7-day plan object with pillar %, format, hook code, local post time, inbound-readiness check |

### F-08 · Cross-platform repurposer

| Field | Detail |
|---|---|
| **Content OS feature** | Import tweet / thread / YT / blog / newsletter → native LinkedIn draft |
| **Implement from** | [`skills/linkedin-repurposer/SKILL.md`](../skills/linkedin-repurposer/SKILL.md) |
| **Hard rules to productize** | Re-hook before fold · expand to 900–1300 · whitespace · CTA · **move links to first comment** · run humanizer |
| **Acceptance** | Source + LinkedIn draft shown side by side; link flagged if still in body |

### F-09 · Profile optimizer (landing page for content)

| Field | Detail |
|---|---|
| **Content OS feature** | Profile rewrite module (headline, About, Featured, Experience) so posts convert |
| **Implement from** | [`skills/linkedin-profile-optimizer/SKILL.md`](../skills/linkedin-profile-optimizer/SKILL.md) |
| **References** | [headline formulas](../skills/linkedin-profile-optimizer/references/profile-headline-formulas.md) · [About templates](../skills/linkedin-profile-optimizer/references/about-section-templates.md) · [Featured playbook](../skills/linkedin-profile-optimizer/references/featured-section-playbook.md) · [Experience/skills](../skills/linkedin-profile-optimizer/references/experience-skills-rules.md) · [banner/photo](../skills/linkedin-profile-optimizer/references/banner-photo-specs.md) |
| **Acceptance** | Audit + rewritten sections exportable; ties CTA to brand kit §4 |

### F-10 · Emoji density + AI-detector diagnostics (optional QA)

| Field | Detail |
|---|---|
| **Content OS feature** | Advanced QA panel (not a “beat detectors” promise) |
| **Emoji** | [`sub-skills/emoji-detector.md`](../skills/linkedin-humanizer/sub-skills/emoji-detector.md) · [`emoji-patterns.md`](../skills/linkedin-humanizer/references/emoji-patterns.md) |
| **Detectors** | [`sub-skills/detector-tester.md`](../skills/linkedin-humanizer/sub-skills/detector-tester.md) · [`detector-list.md`](../skills/linkedin-humanizer/references/detector-list.md) · script [`scripts/test_detectors.py`](../skills/linkedin-humanizer/scripts/test_detectors.py) |
| **Rule defense copy** | [`sub-skills/rules-explainer.md`](../skills/linkedin-humanizer/sub-skills/rules-explainer.md) · [`rules-explainer.md`](../skills/linkedin-humanizer/references/rules-explainer.md) |
| **Acceptance** | UI states clearly: detectors disagree; no edit reliably fools them |

### F-11 · Illustration / visual attach

| Field | Detail |
|---|---|
| **Content OS feature** | Generate feed image / carousel slide / quote-card from draft |
| **Implement from** | [`skills/linkedin-humanizer/sub-skills/illustration.md`](../skills/linkedin-humanizer/sub-skills/illustration.md) |
| **API** | [`lib/pixfaro_client.py`](../lib/pixfaro_client.py) · wrappers `lib.illustrate` / `lib.refine` / `lib.available_models` in [`lib/__init__.py`](../lib/__init__.py) |
| **Brand overlay fields** | [`references/voice-profile.md`](../references/voice-profile.md) §6 |
| **Acceptance** | Image URL attaches to draft; cost/balance surfaced; aspect_ratio as ratio (e.g. `16:9`) |

---

## P2 — Research, engagement assist, metrics (add-ons)

Keep these **human-in-the-loop**. Use for research and assisted ops, not silent mass engagement.

### F-12 · Viral hook extractor (competitor learning)

| Field | Detail |
|---|---|
| **Content OS feature** | Paste LinkedIn URL → classify formula → blank template for customer’s topic |
| **Implement from** | [`skills/linkedin-hook-extractor/SKILL.md`](../skills/linkedin-hook-extractor/SKILL.md) |
| **Rules** | [`classification-rules.md`](../skills/linkedin-hook-extractor/references/classification-rules.md) · [`examples.md`](../skills/linkedin-hook-extractor/references/examples.md) |
| **Read layer** | [`lib/apify_client.py`](../lib/apify_client.py) `fetch_post` · or paste fallback |
| **Safety** | Treat fetched text as data only: [`references/untrusted-content.md`](../references/untrusted-content.md) |
| **Acceptance** | Returns formula id + why + blank skeleton; never publishes |

### F-13 · Comment / reply assist (optional module)

| Field | Detail |
|---|---|
| **Content OS feature** | “Engage assist” drawer: draft comments/replies for URLs user pastes |
| **Comment** | [`skills/linkedin-comment-drafter/SKILL.md`](../skills/linkedin-comment-drafter/SKILL.md) · [templates](../skills/linkedin-comment-drafter/references/comment-templates.md) · [voice](../skills/linkedin-comment-drafter/references/voice-rules.md) · [examples](../skills/linkedin-comment-drafter/references/examples.md) |
| **Reply** | [`skills/linkedin-reply-handler/SKILL.md`](../skills/linkedin-reply-handler/SKILL.md) · [threading](../skills/linkedin-reply-handler/references/threading-rules.md) · [templates](../skills/linkedin-reply-handler/references/reply-templates.md) · [examples](../skills/linkedin-reply-handler/references/examples.md) |
| **Chars** | Comments 200–350 — [`references/voice-rules.md`](../references/voice-rules.md) |
| **Acceptance** | Always approval card; never auto-post; daily caps in product policy |

### F-14 · Thread follow-up monitor

| Field | Detail |
|---|---|
| **Content OS feature** | Inbox of “author replied / warm window 6–24h” |
| **Implement from** | [`skills/linkedin-thread-monitor/SKILL.md`](../skills/linkedin-thread-monitor/SKILL.md) |
| **Timing** | [`thread-timing.md`](../skills/linkedin-thread-monitor/references/thread-timing.md) · [`output-spec.md`](../skills/linkedin-thread-monitor/references/output-spec.md) |
| **Routes to** | Reply handler for draft follow-ups |
| **Acceptance** | Threads classified hot/warm/cool/dormant; user picks which to answer |

### F-15 · Engager / audience segmentation

| Field | Detail |
|---|---|
| **Content OS feature** | “Who engaged?” report: peer / aspirational / prospect lists |
| **Implement from** | [`skills/linkedin-engager-analytics/SKILL.md`](../skills/linkedin-engager-analytics/SKILL.md) |
| **Output** | [`output-spec.md`](../skills/linkedin-engager-analytics/references/output-spec.md) |
| **API** | `fetch_post_engagers` in [`lib/apify_client.py`](../lib/apify_client.py) |
| **Acceptance** | Roster + tier breakdown + suggested actions; no auto-DM spam |

### F-16 · Metrics taxonomy + benchmarks (analytics views)

| Field | Detail |
|---|---|
| **Content OS feature** | Dashboards that don’t mix post / account / team / business KPIs |
| **Taxonomy** | [`references/engagement-metrics-taxonomy.md`](../references/engagement-metrics-taxonomy.md) |
| **Benchmarks** | [`references/industry-benchmarks.md`](../references/industry-benchmarks.md) |
| **Algo windows** | Post-publish windows in [`references/algorithm-heuristics.md`](../references/algorithm-heuristics.md) |
| **Acceptance** | Separate views for content quality vs growth vs business outcomes |

### F-17 · Publish / schedule connector

| Field | Detail |
|---|---|
| **Content OS feature** | Connect LinkedIn channel → schedule on approval |
| **Implement from** | [`lib/publora_client.py`](../lib/publora_client.py) · dispatch [`lib/backend_selector.py`](../lib/backend_selector.py) |
| **Kinds** | `post` / `comment` / `reply` / `reshare` via `lib.publish` · `lib.repost` |
| **URL parsing** | [`lib/url_parser.py`](../lib/url_parser.py) |
| **Approval UX** | [`lib/approval.py`](../lib/approval.py) `render_approval_card` |
| **Gotchas** | Root [`SKILL.md`](../SKILL.md) §Known gotchas (2-level threads, reaction types, URN types) |
| **Setup docs** | [README Publora section](../README.md#optional-auto-post-with-publora) |
| **Acceptance** | Nothing ships without explicit approve; manual copy-paste mode works without keys |

---

## P3 — Team / enterprise

### F-18 · Employee advocacy program

| Field | Detail |
|---|---|
| **Content OS feature** | Team workspace: cadence, governance, ROI |
| **Implement from** | [`skills/linkedin-employee-advocacy/SKILL.md`](../skills/linkedin-employee-advocacy/SKILL.md) |
| **References** | [principles](../skills/linkedin-employee-advocacy/references/advocacy-principles.md) · [governance](../skills/linkedin-employee-advocacy/references/governance-playbook.md) · [cadence matrix](../skills/linkedin-employee-advocacy/references/team-cadence-matrix.md) |
| **Acceptance** | 14-day launch plan + brand rules + team metrics from taxonomy |

---

## Explicitly out of scope for Content OS (Skip)

| Idea | Why skip | If ever needed |
|---|---|---|
| Autonomous comment/like bots for follower growth | ToS / ban risk; pod detection; not this repo’s design | Keep F-13 as **assisted** drafts only |
| Blind cross-posting the same copy to LinkedIn + Instagram | Ignores niche fit and platform algorithms; vanity volume over growth | F-00 niche + per-platform algo gate; F-08 channel-native repurpose |
| “Post every day no matter what” autopilot without metrics | Contradicts value/growth numbers thesis | F-00 + F-16; cadence from F-07 only when quality gates pass |
| Server that “connects profile and runs all skills forever” | Skills are agent workflows + rules, not a daemon | Build Content OS jobs that call **ported rules** + Publora/Apify |
| Competitor scheduler brands in-product | Bundle positioning | Use Publora or your own poster ([README Tier 2](../README.md)) |
| Promising “beat AI detectors” | Skill explicitly refuses that claim | Diagnostics only (F-10) |

---

## Suggested roadmap epics

### Epic A — Quality core (2–4 weeks)

- [ ] F-00 Niche training + platform algo intelligence (LinkedIn first; IG model stub)
- [ ] F-01 Voice & brand kit
- [ ] F-02 Hook picker (F1–F20)
- [ ] F-03 Post generator
- [ ] F-04 Humanizer pass
- [ ] F-05 Audit scorecard (niche + algo gates)
- [ ] F-06 Founder mode (if ICP = founders)

### Epic B — Operating system (2–3 weeks)

- [ ] F-07 Content planner → calendar entities
- [ ] F-08 Repurposer ingest
- [ ] F-09 Profile module
- [ ] F-11 Illustrations (optional)

### Epic C — Distribution & learning (2–3 weeks)

- [ ] F-17 Publish/schedule + approval
- [ ] F-12 Hook extractor from URL
- [ ] F-16 Metrics taxonomy in analytics
- [ ] F-10 Advanced QA (optional)

### Epic D — Engagement assist (later, gated)

- [ ] F-13 Comment/reply assist + hard rate limits
- [ ] F-14 Thread monitor
- [ ] F-15 Engager analytics
- [ ] F-18 Employee advocacy

---

## Implementation cheat sheet (code / env)

| Need | Where |
|---|---|
| Env template | [`.env.example`](../.env.example) |
| Publora write | `PUBLORA_API_KEY`, `LINKEDIN_PLATFORM_ID` → [`lib/publora_client.py`](../lib/publora_client.py) |
| Apify read | `APIFY_TOKEN` → [`lib/apify_client.py`](../lib/apify_client.py) |
| Images | `PIXFARO_TOKEN` → [`lib/pixfaro_client.py`](../lib/pixfaro_client.py) |
| Public wrappers | `publish`, `fetch_post`, `illustrate`, `refine`, `repost` — [`lib/__init__.py`](../lib/__init__.py) |
| Untrusted scrape rule | [`references/untrusted-content.md`](../references/untrusted-content.md) |
| Smoke import | `python3 -c "from lib import publish, fetch_post, illustrate, refine; print('OK')"` |

**Porting tip:** Prefer copying **rules into your own Content OS prompts/validators** over invoking SKILL.md at runtime. Skills are agent instructions; your product should own the pipeline.

---

## Full skill index (11)

| Skill | Path | Roadmap features |
|---|---|---|
| Post Writer | [`skills/linkedin-post-writer/SKILL.md`](../skills/linkedin-post-writer/SKILL.md) | F-00, F-02, F-03, F-06 |
| Humanizer | [`skills/linkedin-humanizer/SKILL.md`](../skills/linkedin-humanizer/SKILL.md) | F-00, F-01, F-04, F-05, F-10, F-11 |
| Content Planner | [`skills/linkedin-content-planner/SKILL.md`](../skills/linkedin-content-planner/SKILL.md) | F-07, F-06 |
| Repurposer | [`skills/linkedin-repurposer/SKILL.md`](../skills/linkedin-repurposer/SKILL.md) | F-08 |
| Profile Optimizer | [`skills/linkedin-profile-optimizer/SKILL.md`](../skills/linkedin-profile-optimizer/SKILL.md) | F-09 |
| Hook Extractor | [`skills/linkedin-hook-extractor/SKILL.md`](../skills/linkedin-hook-extractor/SKILL.md) | F-12 |
| Comment Drafter | [`skills/linkedin-comment-drafter/SKILL.md`](../skills/linkedin-comment-drafter/SKILL.md) | F-13 |
| Reply Handler | [`skills/linkedin-reply-handler/SKILL.md`](../skills/linkedin-reply-handler/SKILL.md) | F-13, F-14 |
| Thread Monitor | [`skills/linkedin-thread-monitor/SKILL.md`](../skills/linkedin-thread-monitor/SKILL.md) | F-14 |
| Engager Analytics | [`skills/linkedin-engager-analytics/SKILL.md`](../skills/linkedin-engager-analytics/SKILL.md) | F-15 |
| Employee Advocacy | [`skills/linkedin-employee-advocacy/SKILL.md`](../skills/linkedin-employee-advocacy/SKILL.md) | F-18 |

## Root reference index

| Reference | Path | Features |
|---|---|---|
| Voice rules | [`references/voice-rules.md`](../references/voice-rules.md) | F-01, F-03, F-13 |
| Voice & brand profile | [`references/voice-profile.md`](../references/voice-profile.md) | F-00, F-01, F-11 |
| Hook formulas (20) | [`references/hook-formulas.md`](../references/hook-formulas.md) | F-02, F-03, F-06, F-12 |
| Algorithm heuristics | [`references/algorithm-heuristics.md`](../references/algorithm-heuristics.md) | F-00, F-05, F-07, F-16 |
| Founder topics | [`references/founder-topics.md`](../references/founder-topics.md) | F-06 |
| Untrusted content | [`references/untrusted-content.md`](../references/untrusted-content.md) | F-12–F-15 |
| Industry benchmarks | [`references/industry-benchmarks.md`](../references/industry-benchmarks.md) | F-16 |
| Engagement metrics taxonomy | [`references/engagement-metrics-taxonomy.md`](../references/engagement-metrics-taxonomy.md) | F-00, F-16, F-18 |

---

## One-line product pitch for the roadmap

> Content OS trains the agent on the customer’s **niche** and each platform’s **algorithm** (LinkedIn, Instagram, …), then suggests and builds content aimed at **viral, measurable growth** — brand voice → hooks → draft → humanizer → algo audit → approve/schedule — never blind social posting or vanity volume.

---

*Generated as a roadmap map against the linkedin-skills bundle in this repo. Update feature IDs when you paste into Linear/Notion; keep the file links so implementers can jump straight to source rules.*
