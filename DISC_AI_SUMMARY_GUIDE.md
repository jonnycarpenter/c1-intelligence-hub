# Discovery AI Summary Feature - Implementation Guide

> A comprehensive guide for AI coding assistants to implement inline AI-powered category summaries in a Discovery/Feed page.

## Overview

This guide documents how to build an **inline AI summary feature** that provides on-demand thematic analysis for grouped content. When a user clicks "AI Summary" on a category accordion, an LLM analyzes the items and surfaces:
- **2 Key Themes** (strategic groupings of related items)
- **One-off Summary** (count and description of remaining ungrouped items)

The result appears in a beautiful dark glassmorphism drawer that slides in below the accordion header.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     AI SUMMARY DATA FLOW                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     GET /api/summary/{category}    ┌─────────────┐ │
│  │  Frontend   │ ─────────────────────────────────► │   Backend   │ │
│  │  Component  │                                     │   Router    │ │
│  │             │ ◄───────────────────────────────── │             │ │
│  │  (React)    │     DiscoverySummaryResponse       │  (FastAPI)  │ │
│  └──────┬──────┘                                     └──────┬──────┘ │
│         │                                                   │        │
│         │ Renders drawer                                    │        │
│         │ with themes                                       │        │
│         ▼                                                   ▼        │
│  ┌─────────────┐                                     ┌─────────────┐ │
│  │  Glassmorp- │                                     │  Summary    │ │
│  │  hism Card  │                                     │  Generator  │ │
│  │  UI         │                                     │  (LLM)      │ │
│  └─────────────┘                                     └─────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Backend Implementation

### 1. Pydantic Schemas

```python
# schemas.py
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field

class DiscoveryTheme(BaseModel):
    """A significant trend or topic identified within a category."""
    title: str  # e.g., "M&A Surge" or "Pricing Pressures"
    content: str  # 1-2 sentence AI summary

class DiscoverySummaryResponse(BaseModel):
    """Thematic summary for inline AI summary drawer."""
    category: str
    period_label: str = "Past 30-days"
    themes: List[DiscoveryTheme]
    one_off_summary: str  # e.g., "8 one-off stories about product launches and pricing"
    article_count: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. LLM Summary Generator

The generator class handles the LLM prompt engineering and response parsing.

```python
# generators/discovery_summary.py
import json
from typing import List, Dict, Any

class DiscoverySummaryGenerator:
    """
    Generates thematic summaries for category accordion drawers.
    Matches the "Key Theme 1/2" and "One-off stories" structure.
    """
    
    PROMPT = """You are a senior analyst prepping a category-specific thematic breakdown for an executive intelligence hub.

CATEGORY: {category}
PERIOD: Last 30 days
ARTICLE COUNT: {article_count}

ARTICLES:
{articles_text}

YOUR TASK:
1. Identify the 2 most significant "Key Themes" in this category from the last 30 days. Each theme should group related articles.
2. Summarize the remaining articles as "one-off stories" by grouping their topics (e.g., "8 one-off stories about product launches and pricing").

RESPONSE FORMAT (JSON ONLY):
{{
    "themes": [
        {{
            "title": "Clear Descriptive Theme Title",
            "content": "1-2 sentence analytical summary of this theme."
        }},
        {{
            "title": "Clear Descriptive Theme Title",
            "content": "1-2 sentence analytical summary of this theme."
        }}
    ],
    "one_off_summary": "X one-off stories about [topic A], [topic B], and [topic C]"
}}

RULES:
- Be punchy, analytical, and direct. Skip the fluff.
- If there aren't enough articles for 2 distinct themes, provide 1 theme and adjust the one_off_summary.
- If the articles are fragmented, provide 0 themes and use one_off_summary to describe the activity.
- Ensure the one_off_summary includes the count of articles it covers.
"""

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022"):
        """Initialize with API key and model selection."""
        self.api_key = api_key
        self.model = model
        # Initialize your LLM client here (Anthropic, OpenAI, etc.)

    async def generate(self, category: str, articles: List[Any]) -> Dict[str, Any]:
        """Generate thematic summary for a category."""
        if not articles:
            return {
                "category": category,
                "period_label": "Past 30-days",
                "themes": [],
                "one_off_summary": "No recent articles in this category.",
                "article_count": 0
            }

        # Format articles for the prompt (title and summary)
        articles_text = ""
        for i, a in enumerate(articles[:40]):  # Analyze top 40 for context
            title = getattr(a, 'title', 'Untitled')
            summary = getattr(a, 'summary', '') or getattr(a, 'description', '')
            articles_text += f"[{i+1}] {title}\nSummary: {summary[:300]}\n\n"

        prompt = self.PROMPT.format(
            category=category.replace('_', ' ').title(),
            article_count=len(articles),
            articles_text=articles_text
        )

        try:
            # Call your LLM here - example with Anthropic
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0,  # Deterministic for consistent summaries
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text.strip()
            
            # Extract JSON from potential markdown wrapping
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            return {
                "category": category,
                "period_label": "Past 30-days",
                "themes": data.get("themes", []),
                "one_off_summary": data.get("one_off_summary", ""),
                "article_count": len(articles)
            }
        except Exception as e:
            # Fallback response on error
            return {
                "category": category,
                "period_label": "Past 30-days",
                "themes": [],
                "one_off_summary": f"{len(articles)} articles detected. Summary generation encountered an error.",
                "article_count": len(articles)
            }
```

### 3. FastAPI Endpoint

```python
# routers/stats.py (or a dedicated router)
from fastapi import APIRouter, HTTPException
from .schemas import DiscoverySummaryResponse
from .generators.discovery_summary import DiscoverySummaryGenerator
import os

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/discovery/summary/{category}", response_model=DiscoverySummaryResponse)
async def get_discovery_category_summary(category: str):
    """
    Get a thematic AI summary for a specific category (last 30 days).
    
    Returns 2 key themes and a summary of one-off stories.
    """
    # 1. Fetch articles for this category (adjust to your data layer)
    articles = await storage.get_articles_by_category(
        category=category,
        hours=720,  # 30 days
        limit=50
    )
    
    # 2. Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")  # or OPENAI_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM API key not configured")
    
    # 3. Generate summary
    generator = DiscoverySummaryGenerator(api_key=api_key)
    result = await generator.generate(category, articles)
    
    return DiscoverySummaryResponse(**result)
```

---

## Frontend Implementation

### 1. TypeScript Types

```typescript
// lib/api.ts or types/index.ts
export interface DiscoveryTheme {
  title: string
  content: string
}

export interface DiscoverySummaryResponse {
  category: string
  period_label: string
  themes: DiscoveryTheme[]
  one_off_summary: string
  article_count: number
  generated_at: string
}
```

### 2. API Client Function

```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

async function fetchApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`)
  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`)
  }
  return response.json()
}

export const api = {
  getDiscoverySummary: (category: string) =>
    fetchApi<DiscoverySummaryResponse>(`/api/stats/discovery/summary/${category}`),
}
```

### 3. React Component: CategoryAccordion with AI Summary

```tsx
// components/CategoryAccordion.tsx
'use client'

import { useState } from 'react'
import { 
  ChevronDown, ChevronRight, Sparkles, Loader2, X, 
  Target, Zap, TrendingUp 
} from 'lucide-react'
import { api, DiscoverySummaryResponse } from '@/lib/api'
import { cn } from '@/lib/utils'

interface CategoryAccordionProps {
  category: string
  items: any[]
  categoryLabel: string
  defaultOpen?: boolean
}

export default function CategoryAccordion({
  category,
  items,
  categoryLabel,
  defaultOpen = false,
}: CategoryAccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const [summary, setSummary] = useState<DiscoverySummaryResponse | null>(null)
  const [isLoadingSummary, setIsLoadingSummary] = useState(false)
  const [isSummaryVisible, setIsSummaryVisible] = useState(false)

  const handleFetchSummary = async (e: React.MouseEvent) => {
    e.stopPropagation() // Don't toggle accordion

    // Toggle visibility if already loaded
    if (isSummaryVisible) {
      setIsSummaryVisible(false)
      return
    }

    setIsSummaryVisible(true)

    // Only fetch if not cached
    if (!summary) {
      setIsLoadingSummary(true)
      try {
        const data = await api.getDiscoverySummary(category)
        setSummary(data)
      } catch (err) {
        console.error('Failed to fetch summary:', err)
      } finally {
        setIsLoadingSummary(false)
      }
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Accordion Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "w-full flex items-center justify-between p-4 transition-colors",
          isOpen ? "bg-gray-50 border-b" : "hover:bg-gray-50"
        )}
      >
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-900 text-sm">{categoryLabel}</h3>
          <span className="text-xs text-gray-500">{items.length} items</span>
        </div>

        <div className="flex items-center gap-3">
          {/* ⭐ AI SUMMARY BUTTON - Premium Gradient Styling */}
          <button
            onClick={handleFetchSummary}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all border shadow-sm",
              isSummaryVisible
                ? "bg-gradient-to-r from-teal-500 to-emerald-500 text-white border-white/20 ring-2 ring-teal-500/20 shadow-lg scale-105"
                : "bg-white text-teal-600 border-teal-500/30 hover:bg-teal-50 hover:border-teal-500/50 active:scale-95"
            )}
          >
            {isLoadingSummary ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Sparkles 
                size={12} 
                className={cn(
                  "animate-sparkle",
                  isSummaryVisible ? "text-white" : "text-teal-500"
                )} 
              />
            )}
            AI Summary
          </button>

          {/* Chevron */}
          {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </div>
      </button>

      {/* ⭐ GLASSMORPHISM AI SUMMARY DRAWER */}
      {isSummaryVisible && (
        <div className="mx-4 mb-4 relative z-10 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="bg-slate-900/95 text-white rounded-xl p-6 shadow-2xl border border-white/10 backdrop-blur-xl relative overflow-hidden animate-float">
            {/* Ambient background glows */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-teal-500/20 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />

            {/* Close button */}
            <button
              onClick={() => setIsSummaryVisible(false)}
              className="absolute top-4 right-4 p-1.5 hover:bg-white/10 rounded-full transition-colors z-10"
            >
              <X size={14} />
            </button>

            {isLoadingSummary ? (
              /* Loading State */
              <div className="flex flex-col items-center justify-center py-10 space-y-4">
                <div className="relative">
                  <Loader2 size={32} className="animate-spin text-teal-500 opacity-80" />
                  <Sparkles size={14} className="absolute -top-1 -right-1 text-yellow-400 animate-pulse" />
                </div>
                <div className="text-center space-y-1">
                  <p className="text-sm font-bold tracking-tight">Synthesizing {categoryLabel} Insights</p>
                  <p className="text-[10px] uppercase tracking-widest opacity-50 font-bold">LLM Thematic Analysis</p>
                </div>
              </div>
            ) : summary ? (
              /* Summary Content */
              <div className="space-y-6 relative z-10">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <Sparkles size={14} className="text-yellow-400" />
                      <h4 className="text-sm font-bold tracking-tight uppercase">
                        {categoryLabel} — Strategic Themes
                      </h4>
                    </div>
                    <p className="text-[10px] uppercase tracking-widest opacity-60 font-black">
                      {summary.period_label} • {summary.article_count} Signals Processed
                    </p>
                  </div>
                </div>

                {/* Theme Cards Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {summary.themes.map((theme, idx) => (
                    <div 
                      key={idx} 
                      className="group p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all duration-300"
                    >
                      <div className="flex items-start gap-3">
                        {/* Icon anchor */}
                        <div className="w-8 h-8 shrink-0 flex items-center justify-center rounded-lg bg-gradient-to-br from-white/10 to-white/5 border border-white/10 group-hover:from-teal-500/20 group-hover:to-blue-500/20 transition-colors">
                          {idx === 0 ? (
                            <TrendingUp size={16} className="text-teal-400" />
                          ) : (
                            <Zap size={16} className="text-blue-400" />
                          )}
                        </div>
                        <div className="space-y-1">
                          <h5 className="text-sm font-bold leading-tight group-hover:text-teal-400 transition-colors">
                            {theme.title}
                          </h5>
                          <p className="text-xs leading-relaxed opacity-70 font-medium italic">
                            "{theme.content}"
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* One-off Summary Footer */}
                <div className="pt-4 border-t border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Target size={14} className="text-pink-400" />
                    <p className="text-[11px] font-bold opacity-80 italic leading-snug">
                      {summary.one_off_summary}
                    </p>
                  </div>
                  <button
                    onClick={() => setIsOpen(true)}
                    className="shrink-0 flex items-center gap-1.5 text-[10px] uppercase font-black tracking-widest text-teal-400 hover:text-white transition-colors"
                  >
                    Explore all signals
                    <ChevronRight size={12} />
                  </button>
                </div>
              </div>
            ) : (
              /* Error State */
              <div className="py-6 text-center">
                <p className="text-sm opacity-60 italic">Failed to generate summary. Please try again.</p>
              </div>
            )}
          </div>

          {/* Stem connector triangle (optional) */}
          <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[8px] border-l-transparent border-r-[8px] border-r-transparent border-b-[8px] border-b-slate-900/95" />
        </div>
      )}

      {/* Accordion Content (collapsed items) */}
      {isOpen && (
        <div className="p-4 space-y-3 bg-gray-50/50 max-h-[600px] overflow-y-auto">
          {items.map((item) => (
            <div key={item.id} className="p-3 bg-white rounded-lg border">
              {item.title}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

---

## CSS Animations

Add these to your global CSS file:

```css
/* globals.css */

/* Sparkle rotation animation for AI Summary button icon */
@keyframes sparkle-rotate {
  0% {
    transform: scale(1) rotate(0deg);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.2) rotate(180deg);
    opacity: 1;
  }
  100% {
    transform: scale(1) rotate(360deg);
    opacity: 0.8;
  }
}

/* Subtle float animation for glassmorphism drawer */
@keyframes float-subtle {
  0% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-3px);
  }
  100% {
    transform: translateY(0px);
  }
}

.animate-sparkle {
  animation: sparkle-rotate 2s ease-in-out infinite;
}

.animate-float {
  animation: float-subtle 3s ease-in-out infinite;
}
```

If using Tailwind CSS v4 with `@theme`, you can also add:

```css
@theme inline {
  /* AI accent colors */
  --color-chalk-teal: #2DD4BF;
  --color-chalk-blue: #60A5FA;
  --color-chalk-yellow: #FFDE4D;
  --color-chalk-magenta: #F472B6;
}
```

---

## Key Design Principles

### 1. On-Demand Loading
- Summary is **only fetched when user clicks** "AI Summary" button
- Cached in component state to avoid re-fetching
- Toggle behavior: clicking again hides the drawer (no API call)

### 2. Visual Hierarchy
- **Button states**: White default → Gradient when active
- **Drawer**: Dark glassmorphism stands out from light category cards
- **Theme cards**: Icon-anchored for quick scanning (TrendingUp, Zap)

### 3. Loading Experience
- Show spinning loader with context ("Synthesizing X Insights")
- Subtle badge shows "LLM Thematic Analysis" to set expectations
- Animations (sparkle, float) add premium polish

### 4. Graceful Degradation
- Empty category → "No recent articles in this category"
- LLM error → Fallback message with article count
- 0-1 themes → Adjust one_off_summary to cover everything

### 5. Responsive Grid
- Themes display in 2-column grid on desktop
- Collapse to single column on mobile
- One-off summary footer with CTA button

---

## Prompt Engineering Notes

### Why This Prompt Works

1. **Structured Output**: Forces JSON-only response for reliable parsing
2. **Explicit Rules**: Clear handling for edge cases (0-1 themes)
3. **Analytical Tone**: "Be punchy, analytical, direct. Skip the fluff."
4. **Count Requirement**: `one_off_summary` must include the article count

### Tuning Tips

- **Temperature 0**: Deterministic output for consistent summaries
- **Max 40 articles**: Keeps prompt within context limits while providing enough signal
- **300-char summaries**: Enough context without overwhelming the LLM
- **Model choice**: Claude Haiku or GPT-3.5-turbo for speed; GPT-4/Claude Sonnet for quality

---

## Checklist for Implementation

- [ ] **Backend**
  - [ ] Create `DiscoveryTheme` and `DiscoverySummaryResponse` Pydantic models
  - [ ] Create `DiscoverySummaryGenerator` class with LLM prompt
  - [ ] Add `/api/stats/discovery/summary/{category}` endpoint
  - [ ] Handle LLM API key configuration

- [ ] **Frontend**
  - [ ] Add TypeScript types for `DiscoverySummaryResponse`
  - [ ] Add `getDiscoverySummary(category)` API client function
  - [ ] Add AI Summary button to category accordion
  - [ ] Build glassmorphism drawer component
  - [ ] Add loading, error, and success states
  - [ ] Add CSS animations (`animate-sparkle`, `animate-float`)

- [ ] **Polish**
  - [ ] Test with 0, 1, 2+ themes scenarios
  - [ ] Verify mobile responsiveness
  - [ ] Test error handling (API down, rate limits)
  - [ ] Optimize for fast initial load (lazy fetch)

---

## Example Output

When the user clicks "AI Summary" on a "Competitor Moves" category:

```json
{
  "category": "competitor_move",
  "period_label": "Past 30-days",
  "themes": [
    {
      "title": "Prebiotic Soda Price Wars",
      "content": "Olipop and Poppi are engaging in aggressive promotional pricing across major retailers, with Costco emerging as a key battleground."
    },
    {
      "title": "Energy Drink M&A Activity",
      "content": "Celsius acquisition rumors intensify as PepsiCo and Monster both signal interest in the functional energy segment."
    }
  ],
  "one_off_summary": "12 one-off stories about new product launches, sponsorship deals, and international expansion",
  "article_count": 34
}
```

This renders as a beautiful dark drawer with two icon-anchored theme cards and a footer summarizing the remaining stories.
