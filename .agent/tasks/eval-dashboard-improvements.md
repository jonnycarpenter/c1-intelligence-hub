# Eval Dashboard Improvements Spec

> **Status**: Tiers 1–3 COMPLETE. Tier 4 ready for implementation.
> **Created**: 2026-02-11
> **Updated**: 2026-02-11 — Tiers 2 & 3 implemented in one session
> **Owner**: AI Quality / Evals system

## Current State (Tier 1 — DONE)

The AI Quality tab is fully wired end-to-end:

- **Mode**: `'evals'` added to `Mode` type in `frontend/src/types/index.ts`
- **Sidebar**: "AI Quality" nav item with `BarChart3` icon (amber) in `frontend/src/components/layout/Sidebar.tsx`
- **Page render**: Dynamic import + full-width render block in `frontend/src/app/page.tsx`
- **API client**: `api.getEvalDashboard(days)` + `api.submitFeedback(data)` in `frontend/src/lib/api.ts`
- **Backend routes**: `/api/evals/dashboard` + `/api/feedback` mounted in `backend/app/main.py`

### Existing Files

| File | Purpose | Lines |
|------|---------|-------|
| `frontend/src/components/evals/EvalDashboard.tsx` | Main dashboard component (T2+T3 features) | ~900 |
| `frontend/src/components/ui/FeedbackWidget.tsx` | Thumbs up/down widget (used in ResearchReport + WeeklyBriefingSection) | 103 |
| `frontend/src/lib/api.ts` | `getEvalDashboard()`, `runEvalJudge()`, `getEvalJobStatus()`, `getEvalReports()`, `submitFeedback()` | — |
| `backend/app/api/routes/evals.py` | `/dashboard`, `/run-judge`, `/run-judge/status`, `/reports` | ~355 |
| `backend/app/api/routes/feedback.py` | POST feedback + GET `/summary` | 148 |
| `backend/app/evals/quality_metrics.py` | `compute_quality_report(days_back, period_end)` — deterministic BQ queries | ~165 |
| `backend/app/evals/llm_judge.py` | **NEW** — `run_eval_batch()`, `get_eval_job_status()` — reusable LLM judge | ~220 |
| `backend/app/evals/token_tracker.py` | `TokenTracker` class — in-memory buffer + BQ flush | 218 |
| `backend/app/evals/__init__.py` | Exports `token_tracker` singleton | 10 |
| `backend/scripts/testing/eval_llm_judge.py` | Batch eval with Claude Haiku judge (CLI — now also available via API T3.1) | 214 |
| `backend/scripts/monitoring/eval_dashboard.py` | CLI dashboard script | 295 |

### BigQuery Tables

| Table | Key Columns |
|-------|-------------|
| `llm_token_usage` | id, model, provider, input_tokens, output_tokens, total_tokens, estimated_cost_usd, caller, created_at |
| `eval_results` | id, report_id, report_type, eval_model, factual_grounding_score, coherence_score, actionability_score, overall_score, *_reasoning, eval_time_seconds, created_at |
| `user_feedback` | id, report_id, report_type, rating (positive/negative), comment, section_id, created_at |
| `deep_research_reports` | id, query, executive_summary, final_report (JSON), sources_count, validation_passed, citation_count, overall_confidence, research_time_seconds, created_at |
| `weekly_briefings` | id, sections (JSON), generated_at |

### Current Dashboard Sections (4-panel grid)

1. **Quality Metrics (Deep Research)** — citation health %, validation pass rate, avg citations, avg sources, research time, confidence distribution bar
2. **LLM-as-Judge Scores** — factual grounding, coherence, actionability, overall (ScoreBar components, 1–5 scale)
3. **Token Usage & Cost** — input/output tokens, total cost, DailyTrendChart (CSS bar sparkline), collapsible CostTable (by model, by caller)
4. **User Feedback** — total ratings, positive/negative counts, satisfaction rate gauge bar

### Current Stat Cards (top row, 4 cards)

1. Reports Generated (deep research count + weekly briefing sub)
2. Total LLM Cost (formatted cost + API call count)
3. Avg Quality Score (overall judge /5 or N/A)
4. User Satisfaction (positive rate % or N/A)

---

## Tier 2 — Visual Polish ✅ DONE

> **Goal**: Make the existing dashboard feel premium. No new endpoints needed.
> **Estimated effort**: ~1 session
> **Completed**: 2026-02-11

### T2.1 — Skeleton Loading States

Replace the current single spinner with per-section skeleton placeholders.

**File**: `frontend/src/components/evals/EvalDashboard.tsx`

**What to do**:
- Create a `SkeletonCard` component: rounded-xl with `animate-pulse` gray blocks matching StatCard layout
- Create a `SkeletonSection` component: rounded-xl with pulse blocks matching section card layout (header + 3 rows)
- When `loading && !data`, render 4 `SkeletonCard` in the stat row + 4 `SkeletonSection` in the grid instead of the single centered spinner
- Pattern reference: look at how other dashboards in the app handle loading states

```tsx
// Example skeleton
function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-start gap-4 animate-pulse">
      <div className="w-10 h-10 rounded-lg bg-slate-200" />
      <div className="flex-1 space-y-2">
        <div className="h-3 w-20 bg-slate-200 rounded" />
        <div className="h-6 w-16 bg-slate-200 rounded" />
        <div className="h-2 w-24 bg-slate-100 rounded" />
      </div>
    </div>
  )
}
```

### T2.2 — Animated Stat Card Counters

Stat card values should count up from 0 on initial load.

**File**: `frontend/src/components/evals/EvalDashboard.tsx`

**What to do**:
- Create a `useAnimatedNumber(target: number, duration: number = 800)` hook that uses `requestAnimationFrame` to lerp from 0 to target
- Apply to numeric StatCard values: report count, cost, satisfaction %
- For cost values, animate the raw number and format during render
- Use `useRef` + `useEffect` to trigger on `data` change

```tsx
function useAnimatedNumber(target: number, duration = 800) {
  const [value, setValue] = useState(0)
  const ref = useRef<number>(0)
  
  useEffect(() => {
    const start = ref.current
    const startTime = performance.now()
    const animate = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
      setValue(start + (target - start) * eased)
      if (progress < 1) requestAnimationFrame(animate)
      else ref.current = target
    }
    requestAnimationFrame(animate)
  }, [target, duration])
  
  return value
}
```

### T2.3 — Proper Tooltips on DailyTrendChart

Replace `title` attribute hover with a positioned tooltip div.

**File**: `frontend/src/components/evals/EvalDashboard.tsx` — `DailyTrendChart` component (line ~166)

**What to do**:
- Track `hoveredIndex` state in `DailyTrendChart`
- On `onMouseEnter`, set `hoveredIndex`; on `onMouseLeave`, clear it
- Render an absolutely-positioned tooltip div above the hovered bar showing date, cost, and call count
- Remove the `title` attribute from bars
- Use `pointer-events-none` on the tooltip to prevent flicker

```tsx
// Inside the bar div, add:
{hoveredIndex === i && (
  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-slate-800 text-white text-[10px] rounded-md whitespace-nowrap pointer-events-none z-10">
    <div className="font-medium">{d.date}</div>
    <div>${d.cost_usd.toFixed(4)} · {d.calls} calls</div>
  </div>
)}
```

### T2.4 — Responsive Grid

The top stat cards and main grid are hardcoded to `grid-cols-4` and `grid-cols-2`.

**File**: `frontend/src/components/evals/EvalDashboard.tsx`

**What to do**:
- Stat cards: change `grid-cols-4` → `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`
- Main grid: change `grid-cols-2` → `grid-cols-1 lg:grid-cols-2`
- These are simple class changes, lines ~314 and ~329

### T2.5 — Relative Timestamps

The footer shows an absolute ISO timestamp.

**File**: `frontend/src/components/evals/EvalDashboard.tsx` — footer section (line ~503)

**What to do**:
- Create a `timeAgo(isoString: string)` util that returns "2 min ago", "1 hour ago", etc.
- Replace `{new Date(data.generated_at).toLocaleString()}` with `{timeAgo(data.generated_at)}`
- Also show the absolute time on hover via `title` attribute

```tsx
function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
```

### T2.6 — Empty State Illustration Upgrade

The current `EmptyState` uses a plain `AlertCircle` icon.

**File**: `frontend/src/components/evals/EvalDashboard.tsx` — `EmptyState` component (line ~103)

**What to do**:
- Add a subtle dashed-border outline box around the empty state
- Use section-specific icons (pass the icon from the parent) instead of generic AlertCircle
- Add a "Get Started" link/hint that's more actionable (e.g., "Run a Deep Research query →")

---

## Tier 3 — New Functionality ✅ DONE

> **Goal**: Major new features. Backend + frontend changes.
> **Estimated effort**: 2–3 sessions (completed in 1)
> **Completed**: 2026-02-11
>
> **What was built**:
> - T3.1: "Run Eval" button with modal (count/model picker), background job, polling, auto-refresh on complete
> - T3.2: Recent feedback comments with thumb icons, report type badges, relative timestamps
> - T3.3: Recharts AreaChart replacing CSS sparkline (amber gradient, grid, axis labels, tooltip)
> - T3.4: "Recent Evaluations" expandable table with color-coded scores and full reasoning
> - T3.5: Auto-refresh toggle (60s interval) with green badge
> - T3.6: CSV export (summary + by-model + by-caller + daily trend)
> - T3.7: Cost alert banner ($5.00 threshold), stat card turns red when exceeded
> - T3.8: Compare toggle → fetches previous period, delta arrows (↑↓%) on all stat cards

### T3.1 — "Run Eval Now" Button

Trigger the LLM-as-Judge evaluation from the dashboard UI instead of requiring a CLI script.

**Backend** — `backend/app/api/routes/evals.py`:
- Add `POST /api/evals/run-judge` endpoint
- Accept `{ count: int, model: str }` (defaults: 5, "claude-haiku-4-5")
- Extract the core logic from `backend/scripts/testing/eval_llm_judge.py` into a reusable async function in `backend/app/evals/llm_judge.py` (new file)
- The new file should export `async def run_eval_batch(count, model) -> dict` returning `{ evaluated: int, avg_scores: {...}, errors: int }`
- The route should run this in background (not block the HTTP response) — use `asyncio.create_task()` and return `{ status: "started", count: N }`
- Add `GET /api/evals/run-judge/status` to check if a job is currently running + last run result

**Frontend** — `frontend/src/components/evals/EvalDashboard.tsx`:
- Add "Run Eval" button next to the Refresh button in the header
- Button shows a modal/popover to pick count (5/10/20) and model
- After clicking run, show "Evaluation running..." state with a pulse animation
- Poll `/api/evals/run-judge/status` every 5s until complete, then auto-refresh dashboard

**Frontend** — `frontend/src/lib/api.ts`:
- Add `runEvalJudge(count, model)` method → POST `/api/evals/run-judge`
- Add `getEvalJobStatus()` method → GET `/api/evals/run-judge/status`

### T3.2 — Recent Feedback Comments Display

The dashboard's User Feedback section shows only aggregate numbers. Show recent comments too.

**Backend** — Already supported! `feedback.py` GET `/summary` returns `recent_comments` array. The evals dashboard endpoint (`_get_feedback_summary` in `evals.py`) does NOT currently return comments though.

**Backend** — `backend/app/api/routes/evals.py`:
- Update `_get_feedback_summary()` to also query recent comments (copy the pattern from `feedback.py` lines 112–130):
  ```python
  # Add after the summary query in _get_feedback_summary:
  comments_query = f"""
      SELECT report_type, rating, comment, created_at
      FROM `{dataset}.user_feedback`
      WHERE created_at >= @cutoff AND comment IS NOT NULL AND comment != ''
      ORDER BY created_at DESC
      LIMIT 5
  """
  ```
- Add `recent_comments` to the return dict

**Frontend** — `frontend/src/components/evals/EvalDashboard.tsx`:
- In the User Feedback section, after the satisfaction gauge, add a "Recent Comments" list
- Each comment shows: rating icon (thumb up/down), comment text, report type badge, relative timestamp
- If no comments, show small hint "No comments yet"

**Frontend types** — Update `DashboardData.user_feedback` interface:
```tsx
user_feedback: {
  total_feedback: number
  positive_count?: number
  negative_count?: number
  positive_rate?: number
  recent_comments?: Array<{
    report_type: string
    rating: string
    comment: string
    created_at: string
  }>
}
```

### T3.3 — Recharts Cost Trend Line Chart

Replace the CSS-only sparkline (`DailyTrendChart`) with a proper Recharts line chart.

**Prerequisites**: `recharts` is likely already installed (check `package.json`). If not, `npm install recharts`.

**File**: `frontend/src/components/evals/EvalDashboard.tsx`

**What to do**:
- Replace `DailyTrendChart` component with a Recharts `AreaChart`
- Show cost on Y-axis (formatted as $), date on X-axis
- Add a second line for daily call count (right Y-axis)
- Use amber fill gradient for cost area, dotted line for call count
- Include `Tooltip`, `ResponsiveContainer` for proper sizing
- The chart should be ~200px tall

```tsx
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

function CostTrendChart({ data }: { data: Array<{ date: string; cost_usd: number; calls: number }> }) {
  if (!data?.length) return null
  return (
    <div className="mt-4">
      <p className="text-xs font-medium text-slate-500 mb-2">Daily Cost Trend</p>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `$${v}`} />
          <Tooltip formatter={(v: number) => [`$${v.toFixed(4)}`, 'Cost']} />
          <Area type="monotone" dataKey="cost_usd" stroke="#f59e0b" fill="url(#costGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
```

### T3.4 — Per-Report Eval Detail View

Click a row to see individual report eval scores and reasoning.

**Backend** — `backend/app/api/routes/evals.py`:
- Add `GET /api/evals/reports` endpoint returning recent eval results with report context:
  ```python
  @router.get("/reports")
  async def get_eval_reports(days: int = 30, limit: int = 20):
      """Return individual eval results with report metadata."""
      query = f"""
          SELECT e.*, r.query, r.overall_confidence, r.sources_count
          FROM `{dataset}.eval_results` e
          LEFT JOIN `{dataset}.deep_research_reports` r ON e.report_id = r.id
          WHERE e.created_at >= @cutoff
          ORDER BY e.created_at DESC
          LIMIT @limit
      """
  ```

**Frontend** — `frontend/src/lib/api.ts`:
- Add `getEvalReports(days, limit)` method

**Frontend** — `frontend/src/components/evals/EvalDashboard.tsx`:
- Add a new section below the 4-panel grid: "Recent Evaluations" table
- Columns: Query (truncated), Overall, Factual, Coherence, Actionability, Confidence, Date
- Clicking a row expands to show full reasoning text for each dimension
- Color-code scores: green ≥4, amber ≥3, red <3

### T3.5 — Auto-Refresh Toggle

**File**: `frontend/src/components/evals/EvalDashboard.tsx`

**What to do**:
- Add an auto-refresh toggle (circular arrows icon with on/off state) next to the Refresh button
- When enabled, poll `api.getEvalDashboard(days)` every 60 seconds
- Use `setInterval` inside a `useEffect` that cleans up on unmount
- Show a subtle "Auto-refreshing" badge when active
- Follow the existing pattern in `frontend/src/hooks/useDigest.ts` (lines 79–168) which already implements auto-refresh with `setInterval`

### T3.6 — CSV Export

**File**: `frontend/src/components/evals/EvalDashboard.tsx`

**What to do**:
- Add a "Download CSV" button (Download icon) next to Refresh
- On click, serialize current `data` into CSV format:
  - Section 1: Summary stats (one row)
  - Section 2: By-model cost breakdown
  - Section 3: By-caller cost breakdown  
  - Section 4: Daily trend data
- Use `Blob` + `URL.createObjectURL` + programmatic `<a>` click to trigger download
- Filename: `eval-dashboard-{days}d-{date}.csv`

```tsx
function exportToCsv(data: DashboardData) {
  const lines: string[] = []
  // Header
  lines.push('Section,Metric,Value')
  lines.push(`Summary,Total Reports,${data.quality_metrics.deep_research.total_reports}`)
  lines.push(`Summary,Total Cost,$${data.token_usage_and_cost.total_cost_usd}`)
  // ... etc
  // By model
  data.token_usage_and_cost.by_model?.forEach(m => {
    lines.push(`By Model,${m.model},${m.calls},${m.cost_usd},${m.tokens}`)
  })
  // Daily trend
  data.token_usage_and_cost.daily_trend?.forEach(d => {
    lines.push(`Daily,${d.date},${d.calls},${d.cost_usd},${d.tokens}`)
  })
  
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-dashboard-${data.period_days}d-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
```

### T3.7 — Cost Alerts / Budget Threshold

Visual indicator when costs exceed a configurable threshold.

**Frontend** — `frontend/src/components/evals/EvalDashboard.tsx`:
- Add a `COST_ALERT_THRESHOLD_USD` constant (default: 5.00 for 30-day window)
- If `total_cost_usd > threshold`, show a yellow/red alert banner below the stat cards:
  "⚠️ LLM costs ($X.XX) exceed the $Y.YY threshold for the last {days} days"
- The StatCard for cost should change to red background when threshold exceeded
- Optionally: allow the threshold to be set via a small settings popover

### T3.8 — Date Range Comparison

Compare current period with previous period (e.g., "vs. previous 30 days").

**Backend** — `backend/app/api/routes/evals.py`:
- Add optional `compare=true` query param to `/dashboard`
- When `compare=true`, run the same queries for the previous period (e.g., days 31–60)
- Return `previous_period` alongside current data

**Frontend** — `frontend/src/components/evals/EvalDashboard.tsx`:
- Add toggle/checkbox "Compare with previous period"
- StatCards show delta arrows: ↑12% or ↓5% vs previous period
- Color the delta: green for improvements (more reports, higher scores, lower cost), red for regressions

---

## Tier 4 — Advanced Features

> **Goal**: Power-user features. Larger architectural additions.
> **Estimated effort**: 3–4 sessions

### T4.1 — Sub-Tabs Navigation

Break the single dashboard into focused sub-views.

**File**: `frontend/src/components/evals/EvalDashboard.tsx`

**What to do**:
- Add a horizontal tab bar below the header: **Overview** | **Cost Explorer** | **Quality** | **Feedback**
- `Overview` = current 4-card + 4-panel layout (condensed)
- `Cost Explorer` = full cost breakdown: trend chart (larger), by-model table, by-caller table, daily table with sortable columns, cumulative cost line
- `Quality` = deep research metrics + judge scores + per-report eval table (from T3.4) + confidence trends over time
- `Feedback` = all feedback entries (paginated), sentiment analysis, comment word cloud, satisfaction trend over time
- Track active sub-tab in component state
- Each sub-tab can be a separate component file for code splitting:
  - `frontend/src/components/evals/CostExplorer.tsx`
  - `frontend/src/components/evals/QualityView.tsx`
  - `frontend/src/components/evals/FeedbackView.tsx`

### T4.2 — Ingestion Health Integration

Show ingestion pipeline health alongside AI quality metrics.

**Backend** — `backend/app/api/routes/evals.py`:
- Add `GET /api/evals/ingestion-health` endpoint
- Query `ingestion_events` table for:
  - Total events per source in the period
  - Error rates per source
  - Last successful run per source
  - Articles ingested per day trend

**Frontend** — New sub-tab or section on Overview:
- Show a source health grid: each source (RSS, Exa, SEC, etc.) with green/yellow/red status dot
- Show articles-per-day sparkline
- Highlight sources that haven't run in >24h

### T4.3 — Anomaly Detection Highlights

Surface unusual patterns automatically.

**Backend** — `backend/app/evals/anomaly_detection.py` (new file):
- Compute rolling averages for key metrics (cost, token usage, eval scores)
- Flag when current period deviates >2 standard deviations from the rolling average
- Return anomaly list: `[{ metric, current_value, expected_range, severity }]`

**Backend** — `backend/app/api/routes/evals.py`:
- Add anomaly data to the `/dashboard` response (new `anomalies` key)

**Frontend** — `frontend/src/components/evals/EvalDashboard.tsx`:
- Show anomaly alerts at the top of the dashboard (below header, above stat cards)
- Each anomaly: icon + description + severity badge (warning/critical)
- Examples: "Cost spike: $4.20 today (normal: $0.80–$1.50)", "Quality drop: Overall score 2.1/5 (usually 3.8+)"

### T4.4 — Slack/Webhook Alerts

Send alerts when thresholds are breached.

**Backend** — `backend/app/evals/alerts.py` (new file):
- Define alert rules: cost threshold, quality threshold, feedback threshold
- `async def check_and_alert(dashboard_data)` — runs after dashboard data is computed
- Sends to a Slack webhook URL (from env var `SLACK_WEBHOOK_URL`)
- Store alert history in a new `eval_alerts` BigQuery table

**Backend** — `backend/app/api/routes/evals.py`:
- Add `GET /api/evals/alerts` to list recent alerts
- Add `POST /api/evals/alerts/config` to update alert thresholds

**Frontend** — New section or badge:
- Show a bell icon with unread alert count
- Click to see alert history
- Settings panel to configure thresholds and webhook URL

### T4.5 — Model Pricing Auto-Update

Keep the token cost estimates accurate.

**Backend** — `backend/app/evals/token_tracker.py`:
- The `MODEL_PRICING` dict (line ~40) is hardcoded. Add a mechanism to:
  1. Load overrides from a `model_pricing.json` file if it exists
  2. Add an API endpoint to update pricing: `POST /api/evals/pricing`
  3. Log a warning if an unknown model is encountered (currently falls back to DEFAULT_PRICING silently)

**Frontend** — Small admin section (could be in Cost Explorer sub-tab):
- Show current model pricing table
- Allow editing prices inline
- Save back via API

### T4.6 — Eval Trend Charts Over Time

Show how quality scores are trending over weeks/months.

**Backend** — `backend/app/api/routes/evals.py`:
- Add `GET /api/evals/trends` endpoint
- Return weekly aggregated data:
  ```python
  SELECT DATE_TRUNC(created_at, WEEK) as week,
         AVG(overall_score), AVG(factual_grounding_score),
         COUNT(*) as eval_count
  FROM eval_results
  GROUP BY week ORDER BY week
  ```

**Frontend** — Quality sub-tab or new section:
- Recharts line chart showing score trends over time
- One line per dimension (factual, coherence, actionability, overall)
- Time range selector (last 4 weeks, 8 weeks, 12 weeks)

---

## Implementation Priority

Recommended order for remaining work:

| Session | Items | Why |
|---------|-------|-----|
| ~~**Session 1**~~ | ~~T2.1–T2.6~~ | ✅ Done |
| ~~**Session 2–3**~~ | ~~T3.1–T3.8~~ | ✅ Done |
| **Session 4** | T4.1, T4.6 | Sub-tabs architecture + eval trend charts |
| **Session 5** | T4.2, T4.3 | Ingestion health + anomaly detection |
| **Session 6** | T4.4, T4.5 | Slack alerts + pricing management |

## Verification

After each session, run:

```bash
# Frontend build
cd frontend && npm run build

# Backend syntax check
cd backend && python -c "import ast; ast.parse(open('app/api/routes/evals.py').read()); print('OK')"

# Full backend import (requires GCP credentials)
cd backend && python -c "from app.mcp.server import get_all_mcp_tools; print('OK')"
```
