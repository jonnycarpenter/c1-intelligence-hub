# Bulletin Board Implementation Guide

> **Purpose**: Drop-in implementation guide for adding an LLM-powered "Priority Spotlight" bulletin board that surfaces contextual guidance for high-priority items.

## Feature Overview

The Bulletin Board replaces a static greeting header with a dynamic, LLM-generated component that:
1. Fetches HIGH/CRITICAL priority items from the last 72 hours
2. Auto-extends to 7 days if no recent items exist
3. Uses Claude Haiku to generate 1-3 brief, actionable guidance bullets
4. Falls back to templated bullets if LLM fails

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React/Next.js)                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  BulletinBoard.tsx                                        │  │
│  │  - Fetches /api/stats/discovery/bulletin                  │  │
│  │  - Loading/Error/Empty states                             │  │
│  │  - Dark glassmorphism UI                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  api.ts                                                   │  │
│  │  - BulletinBoardResponse interface                        │  │
│  │  - getBulletinBoard() function                            │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  routers/stats.py                                         │  │
│  │  GET /api/stats/discovery/bulletin                        │  │
│  │  - Fetches priority items from storage                    │  │
│  │  - Calls BulletinBoardGenerator                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  generators/bulletin_board.py                             │  │
│  │  - Loads LLM prompt                                       │  │
│  │  - Groups items by category                               │  │
│  │  - Calls Claude Haiku                                     │  │
│  │  - Parses JSON response                                   │  │
│  │  - Fallback templated bullets                             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  agent_prompts/bulletin_board_prompt.md                   │  │
│  │  - LLM system prompt                                      │  │
│  │  - Output format (JSON array)                             │  │
│  │  - Examples                                               │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `inputs/agent_prompts/bulletin_board_prompt.md` | CREATE | LLM prompt for Haiku |
| `generators/bulletin_board.py` | CREATE | Generator class |
| `api/schemas.py` | MODIFY | Add `BulletinBoardResponse` model |
| `api/routers/stats.py` | MODIFY | Add `/discovery/bulletin` endpoint |
| `frontend/src/lib/api.ts` | MODIFY | Add type + `getBulletinBoard()` |
| `frontend/src/components/feed/BulletinBoard.tsx` | CREATE | React component |
| Parent view component | MODIFY | Import and render `<BulletinBoard />` |

---

## Step 1: Create LLM Prompt

**File**: `inputs/agent_prompts/bulletin_board_prompt.md`

```markdown
# Bulletin Board Contextualizer

You are a concise intelligence analyst for a CPG brand intelligence platform. Your job is to generate **brief, actionable guidance** for where to look in the category monitoring dashboard.

## Input
You will receive HIGH or CRITICAL priority articles from the last 72 hours (or 7 days if 72h is empty), grouped by category.

## Output Format
Generate 1-3 bullet points (max 3), one for each top category that has priority items. Each bullet should be:
- **15-25 words max**
- Mention the category name naturally
- Include a 1-2 word directional context (what the news is about)
- Include recency if notable (e.g., "just 2 hours ago")

## Style
- Friendly but professional
- No hype or marketing language
- Focus on actionable direction ("Check out", "Look into", "Note the")
- Use plain category names: "Consumer Trends", "Health & Regulatory", "Competitor Moves", etc.

## Category Display Names
- competitor_move → "Competitor Moves"
- market_dynamics → "Market Dynamics"
- health_regulatory → "Health & Regulatory"
- marketing_campaign → "Marketing Campaigns"
- retail_distribution → "Retail & Distribution"
- earnings_financial → "Earnings & Financial"
- consumer_trends → "Consumer Trends"
- client_direct → "Client News"
- supply_ingredient → "Supply & Ingredients"
- packaging → "Packaging"

## Examples

Good:
- "Check out Consumer Trends – 3 items on GLP-1 sentiment, latest just 5 hours ago."
- "Look into Health & Regulatory – a new FDA action dropped 2 hours ago."
- "Note 4 Competitor Moves this week, mostly around Starry's retail push."

Bad (too long/vague):
- "There are several interesting updates in the consumer trends category that you might want to review when you have time."
- "The health and regulatory section has some new information."

## Response Format
Return ONLY a JSON array of strings, no explanation:
```json
["bullet 1", "bullet 2", "bullet 3"]
```

If no categories have priority items, return:
```json
["All clear – no urgent items in the last few days. Explore the categories below."]
```
```

> **Customization**: Update the category display names mapping to match your project's taxonomy.

---

## Step 2: Create Bulletin Board Generator

**File**: `generators/bulletin_board.py`

```python
"""
Bulletin Board Generator
========================

Generates contextual guidance bullets for the Market Intelligence bulletin board.
Uses Haiku LLM to create brief, actionable pointers to priority content.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Category display name mapping - CUSTOMIZE FOR YOUR PROJECT
CATEGORY_DISPLAY_NAMES = {
    "competitor_move": "Competitor Moves",
    "market_dynamics": "Market Dynamics",
    "health_regulatory": "Health & Regulatory",
    "marketing_campaign": "Marketing Campaigns",
    "retail_distribution": "Retail & Distribution",
    "earnings_financial": "Earnings & Financial",
    "consumer_trends": "Consumer Trends",
    "client_direct": "Client News",
    "supply_ingredient": "Supply & Ingredients",
    "packaging": "Packaging",
}


class BulletinBoardGenerator:
    """Generates contextual bulletin board guidance using Haiku LLM."""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required")
        self.client = Anthropic(api_key=self.api_key)
        self._prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> str:
        """Load the bulletin board prompt template."""
        # CUSTOMIZE PATH for your project structure
        prompt_path = Path(__file__).parent.parent.parent / "inputs" / "agent_prompts" / "bulletin_board_prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        # Fallback minimal prompt
        return """Generate 1-3 brief bullet points guiding users to priority content. 
Return JSON array of strings only."""
    
    async def generate(
        self,
        priority_items: List[Dict[str, Any]],
        hours_window: int = 72,
        extended: bool = False
    ) -> Dict[str, Any]:
        """
        Generate bulletin board content.
        
        Args:
            priority_items: List of HIGH/CRITICAL articles with category, title, published_at
            hours_window: Time window used (72 or 168)
            extended: Whether we extended from 72h to 7 days due to no items
            
        Returns:
            {
                "bullets": ["bullet 1", "bullet 2", ...],
                "total_priority_items": int,
                "categories_covered": ["consumer_trends", ...],
                "time_window_hours": int,
                "extended_to_7_days": bool,
                "generated_at": str
            }
        """
        # Group by category
        by_category: Dict[str, List[Dict]] = {}
        for item in priority_items:
            cat = item.get("primary_category") or item.get("category") or "uncategorized"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)
        
        # Sort categories by count (descending), take top 3
        sorted_categories = sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)[:3]
        
        if not sorted_categories:
            # No priority items
            return {
                "bullets": ["All clear – no urgent items in the last few days. Explore the categories below."],
                "total_priority_items": 0,
                "categories_covered": [],
                "time_window_hours": hours_window,
                "extended_to_7_days": extended,
                "generated_at": datetime.utcnow().isoformat()
            }
        
        # Prepare context for LLM
        context = self._build_context(sorted_categories, hours_window, extended)
        
        # Call Haiku
        try:
            bullets = await self._call_haiku(context)
        except Exception as e:
            logger.error(f"Haiku call failed: {e}")
            # Fallback to templated bullets
            bullets = self._generate_fallback_bullets(sorted_categories)
        
        return {
            "bullets": bullets,
            "total_priority_items": len(priority_items),
            "categories_covered": [cat for cat, _ in sorted_categories],
            "time_window_hours": hours_window,
            "extended_to_7_days": extended,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _build_context(
        self,
        sorted_categories: List[tuple],
        hours_window: int,
        extended: bool
    ) -> str:
        """Build context string for LLM."""
        now = datetime.utcnow()
        lines = []
        
        time_label = "7 days" if extended else "72 hours"
        lines.append(f"Priority items from the last {time_label}:\n")
        
        for category, items in sorted_categories:
            display_name = CATEGORY_DISPLAY_NAMES.get(category, category.replace("_", " ").title())
            lines.append(f"\n## {display_name} ({len(items)} items)")
            
            # Add up to 5 sample titles with recency
            for item in items[:5]:
                title = item.get("title", "Untitled")[:80]
                pub_at = item.get("published_at")
                recency = ""
                if pub_at:
                    try:
                        pub_dt = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                        hours_ago = (now - pub_dt.replace(tzinfo=None)).total_seconds() / 3600
                        if hours_ago < 1:
                            recency = " (just now)"
                        elif hours_ago < 6:
                            recency = f" ({int(hours_ago)}h ago)"
                        elif hours_ago < 24:
                            recency = " (today)"
                        elif hours_ago < 48:
                            recency = " (yesterday)"
                    except:
                        pass
                lines.append(f"  - {title}{recency}")
        
        return "\n".join(lines)
    
    async def _call_haiku(self, context: str) -> List[str]:
        """Call Claude Haiku to generate bullets."""
        # Synchronous call (Anthropic SDK)
        response = self.client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=300,
            system=self._prompt_template,
            messages=[
                {"role": "user", "content": context}
            ]
        )
        
        # Parse response
        content = response.content[0].text.strip()
        
        # Extract JSON array
        if content.startswith("["):
            try:
                bullets = json.loads(content)
                if isinstance(bullets, list) and all(isinstance(b, str) for b in bullets):
                    return bullets[:3]  # Max 3
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON in response
        import re
        match = re.search(r'\[.*?\]', content, re.DOTALL)
        if match:
            try:
                bullets = json.loads(match.group())
                if isinstance(bullets, list):
                    return [str(b) for b in bullets[:3]]
            except:
                pass
        
        # Fallback: treat as single bullet
        return [content[:200]] if content else ["Check out the priority items below."]
    
    def _generate_fallback_bullets(
        self,
        sorted_categories: List[tuple]
    ) -> List[str]:
        """Generate templated bullets without LLM."""
        now = datetime.utcnow()
        bullets = []
        
        for category, items in sorted_categories[:3]:
            display_name = CATEGORY_DISPLAY_NAMES.get(category, category.replace("_", " ").title())
            count = len(items)
            
            # Find most recent item
            recency = ""
            if items:
                most_recent = items[0]
                pub_at = most_recent.get("published_at")
                if pub_at:
                    try:
                        pub_dt = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                        hours_ago = (now - pub_dt.replace(tzinfo=None)).total_seconds() / 3600
                        if hours_ago < 3:
                            recency = f", latest just {int(hours_ago)} hours ago"
                        elif hours_ago < 24:
                            recency = ", latest today"
                    except:
                        pass
            
            bullet = f"Check out {display_name} – {count} priority item{'s' if count != 1 else ''}{recency}."
            bullets.append(bullet)
        
        return bullets
```

---

## Step 3: Add Pydantic Schema

**File**: `api/schemas.py` — Add this model:

```python
from pydantic import BaseModel, Field
from typing import List

class BulletinBoardResponse(BaseModel):
    """Contextual guidance for the Market Intelligence bulletin board."""
    bullets: List[str] = Field(description="1-3 contextual guidance bullets")
    total_priority_items: int = Field(description="Total HIGH/CRITICAL items found")
    categories_covered: List[str] = Field(default_factory=list, description="Categories included in bullets")
    time_window_hours: int = Field(description="Time window used (72 or 168)")
    extended_to_7_days: bool = Field(default=False, description="True if no items in 72h, extended to 7 days")
    generated_at: str = Field(description="ISO timestamp of generation")
```

---

## Step 4: Add API Endpoint

**File**: `api/routers/stats.py` (or wherever your stats endpoints live)

```python
from ..schemas import BulletinBoardResponse

@router.get("/discovery/bulletin", response_model=BulletinBoardResponse)
async def get_bulletin_board():
    """
    Get contextual guidance bullets for the Market Intelligence bulletin board.
    
    Analyzes HIGH/CRITICAL priority items from the last 72 hours (or 7 days if none).
    Uses Haiku LLM to generate 1-3 brief, actionable guidance bullets pointing
    users to the most important content.
    
    Returns:
    - bullets: 1-3 contextual guidance strings
    - total_priority_items: Count of HIGH/CRITICAL items found
    - categories_covered: Which categories are mentioned
    - time_window_hours: 72 or 168 (if extended)
    - extended_to_7_days: True if no items in 72h
    """
    import os
    import traceback
    from datetime import datetime
    from ..schemas import BulletinBoardResponse
    # CUSTOMIZE: Import your generator from the correct path
    from generators.bulletin_board import BulletinBoardGenerator
    
    try:
        # CUSTOMIZE: Get your storage/database client
        storage = get_storage()
        
        # 1. Try 72 hours first
        hours = 72
        priority_items = []
        
        # CUSTOMIZE: Adapt this to your data model
        for priority in ["critical", "high"]:
            articles = await storage.get_articles_by_priority(priority, hours=hours, limit=100)
            for article in articles:
                priority_items.append({
                    "id": article.id,
                    "title": article.title,
                    "primary_category": article.primary_category,
                    "priority": article.priority,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                    "source_name": article.source_name,
                })
        
        # 2. If no items in 72h, extend to 7 days
        extended = False
        if len(priority_items) == 0:
            hours = 168  # 7 days
            extended = True
            for priority in ["critical", "high"]:
                articles = await storage.get_articles_by_priority(priority, hours=hours, limit=100)
                for article in articles:
                    priority_items.append({
                        "id": article.id,
                        "title": article.title,
                        "primary_category": article.primary_category,
                        "priority": article.priority,
                        "published_at": article.published_at.isoformat() if article.published_at else None,
                        "source_name": article.source_name,
                    })
        
        # 3. Sort by published_at (most recent first)
        priority_items.sort(
            key=lambda x: x.get("published_at") or "",
            reverse=True
        )
        
        # 4. Generate bulletin board content
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            # Fallback without LLM
            generator = BulletinBoardGenerator.__new__(BulletinBoardGenerator)
            bullets = generator._generate_fallback_bullets([
                (cat, [i for i in priority_items if i.get("primary_category") == cat])
                for cat in set(i.get("primary_category") for i in priority_items)
            ][:3])
            return BulletinBoardResponse(
                bullets=bullets,
                total_priority_items=len(priority_items),
                categories_covered=[],
                time_window_hours=hours,
                extended_to_7_days=extended,
                generated_at=datetime.utcnow().isoformat()
            )
        
        generator = BulletinBoardGenerator(anthropic_api_key=api_key)
        result = await generator.generate(priority_items, hours_window=hours, extended=extended)
        return BulletinBoardResponse(**result)
        
    except Exception as e:
        print(f"Error in bulletin board endpoint: {e}")
        traceback.print_exc()
        # Return graceful fallback
        return BulletinBoardResponse(
            bullets=["Check out the category themes below for the latest intelligence."],
            total_priority_items=0,
            categories_covered=[],
            time_window_hours=72,
            extended_to_7_days=False,
            generated_at=datetime.utcnow().isoformat()
        )
```

---

## Step 5: Add Frontend API Client

**File**: `frontend/src/lib/api.ts`

```typescript
// Add interface
export interface BulletinBoardResponse {
  bullets: string[]
  total_priority_items: number
  categories_covered: string[]
  time_window_hours: number
  extended_to_7_days: boolean
  generated_at: string
}

// Add to your api object
export const api = {
  // ... existing methods
  
  getBulletinBoard: () =>
    fetchApi<BulletinBoardResponse>('/api/stats/discovery/bulletin', { timeout: 30000 }),
}
```

---

## Step 6: Create React Component

**File**: `frontend/src/components/feed/BulletinBoard.tsx`

```tsx
'use client'

import { useState, useEffect } from 'react'
import { Sparkles, Zap, Loader2, Clock } from 'lucide-react'
import { api, BulletinBoardResponse } from '@/lib/api'
import { cn } from '@/lib/utils'

interface BulletinBoardProps {
    className?: string
}

export default function BulletinBoard({ className }: BulletinBoardProps) {
    const [data, setData] = useState<BulletinBoardResponse | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<Error | null>(null)

    useEffect(() => {
        let isMounted = true

        async function fetchBulletin() {
            try {
                setIsLoading(true)
                const result = await api.getBulletinBoard()
                if (isMounted) {
                    setData(result)
                    setError(null)
                }
            } catch (err) {
                if (isMounted) {
                    setError(err instanceof Error ? err : new Error('Failed to load bulletin'))
                }
            } finally {
                if (isMounted) {
                    setIsLoading(false)
                }
            }
        }

        fetchBulletin()

        return () => {
            isMounted = false
        }
    }, [])

    // Loading state
    if (isLoading) {
        return (
            <div className={cn(
                "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-xl p-4 border border-white/10",
                className
            )}>
                <div className="flex items-center gap-2 text-white/60">
                    <Loader2 size={14} className="animate-spin" />
                    <span className="text-xs font-medium">Loading priority insights...</span>
                </div>
            </div>
        )
    }

    // Error state - show fallback
    if (error || !data) {
        return (
            <div className={cn(
                "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-xl p-4 border border-white/10",
                className
            )}>
                <div className="flex items-center gap-2 text-white/50">
                    <Sparkles size={14} />
                    <span className="text-sm">Explore the category themes below for the latest intelligence.</span>
                </div>
            </div>
        )
    }

    // No priority items
    if (data.total_priority_items === 0) {
        return (
            <div className={cn(
                "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-xl p-4 border border-white/10",
                className
            )}>
                <div className="flex items-center gap-2 text-emerald-400/80">
                    <Sparkles size={14} />
                    <span className="text-sm font-medium">All clear – no urgent items in the last few days.</span>
                </div>
            </div>
        )
    }

    return (
        <div className={cn(
            "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-xl overflow-hidden border border-white/10 shadow-lg",
            className
        )}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-white/10 bg-white/5">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-gradient-to-br from-amber-500/20 to-orange-500/20 rounded-lg">
                            <Zap size={14} className="text-amber-400" />
                        </div>
                        <h3 className="text-xs font-bold text-white/90 uppercase tracking-widest">
                            Priority Spotlight
                        </h3>
                    </div>
                    <div className="flex items-center gap-1.5 text-white/40">
                        <Clock size={10} />
                        <span className="text-[10px] font-medium">
                            {data.extended_to_7_days ? 'Last 7 days' : 'Last 72 hours'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Bullets */}
            <div className="p-4 space-y-3">
                {data.bullets.map((bullet, idx) => (
                    <div
                        key={idx}
                        className="flex items-start gap-3 group"
                    >
                        <span className={cn(
                            "flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0 mt-0.5",
                            idx === 0
                                ? "bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-lg shadow-orange-500/20"
                                : "bg-white/10 text-white/50"
                        )}>
                            {idx + 1}
                        </span>
                        <p className={cn(
                            "text-sm leading-relaxed",
                            idx === 0 ? "text-white font-medium" : "text-white/70"
                        )}>
                            {bullet}
                        </p>
                    </div>
                ))}
            </div>

            {/* Footer - Total count */}
            {data.total_priority_items > 0 && (
                <div className="px-4 py-2.5 border-t border-white/10 bg-white/5">
                    <p className="text-[10px] text-white/40 font-medium">
                        {data.total_priority_items} priority item{data.total_priority_items !== 1 ? 's' : ''} across{' '}
                        {data.categories_covered.length} categor{data.categories_covered.length !== 1 ? 'ies' : 'y'}
                    </p>
                </div>
            )}
        </div>
    )
}
```

---

## Step 7: Integrate Into Parent View

Import and render the component in your discovery/market intelligence view:

```tsx
import BulletinBoard from './BulletinBoard'

// In your JSX, replace the old greeting header:
<BulletinBoard />
```

---

## Dependencies

### Backend
```
anthropic>=0.20.0
```

### Frontend
```
lucide-react  # For icons (Sparkles, Zap, Loader2, Clock)
```

### Environment Variables
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Customization Checklist

- [ ] Update `CATEGORY_DISPLAY_NAMES` in `bulletin_board.py` to match your taxonomy
- [ ] Update category names in `bulletin_board_prompt.md` to match
- [ ] Adjust the prompt style/tone for your audience
- [ ] Update path in `_load_prompt_template()` to match your project structure
- [ ] Adapt the endpoint's data fetching logic to your storage layer
- [ ] Customize the React component styling (colors, borders, fonts) to match your design system

---

## Testing

### Backend Test
```bash
curl http://localhost:8000/api/stats/discovery/bulletin | jq
```

Expected response:
```json
{
  "bullets": [
    "Check out Consumer Trends – 3 items on GLP-1 sentiment, latest just 5 hours ago.",
    "Look into Health & Regulatory – a new FDA action dropped 2 hours ago."
  ],
  "total_priority_items": 5,
  "categories_covered": ["consumer_trends", "health_regulatory"],
  "time_window_hours": 72,
  "extended_to_7_days": false,
  "generated_at": "2026-01-25T18:30:00"
}
```

### Frontend Test
1. Verify loading spinner appears briefly
2. Verify bullets render with numbered badges
3. Verify time window indicator shows correctly
4. Verify footer shows item/category counts
5. Test with no priority items (should show "All clear" message)

---

## Example Output

```
┌────────────────────────────────────────────────────────────────────┐
│ ⚡ PRIORITY SPOTLIGHT                              Last 72 hours   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ❶  Check out Consumer Trends – 3 items on GLP-1 sentiment,       │
│     latest just 5 hours ago.                                       │
│                                                                    │
│  ②  Look into Health & Regulatory – a new FDA action dropped      │
│     2 hours ago.                                                   │
│                                                                    │
│  ③  Note 4 Competitor Moves this week, mostly around Starry's     │
│     retail push.                                                   │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│ 5 priority items across 3 categories                               │
└────────────────────────────────────────────────────────────────────┘
```

---

## Notes

1. **LLM Choice**: Uses Claude 3.5 Haiku (`claude-3-5-haiku-latest`) for speed and cost. You can swap to a different model if needed.

2. **Fallback Strategy**: If the LLM call fails or no API key is set, the system generates templated bullets based on category counts and recency.

3. **Time Window Auto-Extension**: If no HIGH/CRITICAL items exist in 72 hours, the system automatically extends to 7 days so users always see something useful.

4. **Max 3 Bullets**: The system limits output to 3 bullets to keep the UI clean and scannable.

5. **Top 3 Categories**: Only the top 3 categories by item count are included to prevent overwhelming the LLM context.
