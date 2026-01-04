# C1 Intelligence Hub: MVP Long Term Memory

## Overview

A minimal memory system for the C1 Intelligence Hub that enables:
1. **Manual preferences** - Topics to prioritize or exclude from intelligence
2. **Implicit memory** - Auto-saved queries/briefings when users take action (export, download)
3. **Time-weighted relevance** - Recent memories score higher, auto-cleanup after 60 days
4. **Team-scoped context** - Memories tagged by team for better relevance

No user authentication required. Memory is org-level with optional team filtering.

---

## Design Principles

### "Part of the Team" Feel
The memory system should create moments where the AI demonstrates it's been paying attention:
- **Proactive context surfacing**: "Based on your team's previous research on AOC pricing (saved Dec 15), I'll focus on what's changed since then..."
- **Soft personalization**: Team-relevant memories surface first
- **Institutional knowledge**: Pinned memories persist as organizational wisdom

### Teams (from C1 org structure)
1. Sales East
2. Sales West
3. Marketing
4. Product/Supplier
5. All Others

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY FLOW                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ALWAYS IN CONTEXT (~100 tokens)                            │
│  └─ org_preferences table                                   │
│     ├─ Priorities: ["resin pricing", "AOC"]                 │
│     └─ Blocks: ["Acme Corp"]                                │
│                                                             │
│  RETRIEVED WHEN RELEVANT (~200-500 tokens)                  │
│  └─ memory_log table (vector search)                        │
│     ├─ Past briefings user saved                            │
│     └─ Research queries that led to exports                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Table 1: org_preferences

Stores manual user preferences. Small, always loaded into agent context.

```sql
CREATE TABLE `c1_hub.org_preferences` (
  preference_id STRING NOT NULL,
  preference_type STRING NOT NULL,      -- 'prioritize' or 'block'
  target STRING NOT NULL,               -- entity/topic (e.g., "resin pricing", "AOC")
  description STRING,                   -- optional human-readable note
  active BOOL DEFAULT TRUE,
  team STRING,                          -- team scope (null = org-wide)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  created_by STRING                     -- name of person who added it
);
```

**Example data:**

| preference_id | preference_type | target | description | team | active |
|---------------|-----------------|--------|-------------|------|--------|
| pref_001 | prioritize | resin pricing | Key cost driver | null | true |
| pref_002 | prioritize | AOC | Primary competitor | null | true |
| pref_003 | block | Acme Corp | Not relevant to us | null | true |
| pref_004 | prioritize | midwest distribution | Regional focus | Sales East | true |

### Table 2: memory_log

Stores saved briefings and exported research. Uses Vertex AI embeddings for retrieval.

```sql
CREATE TABLE `c1_hub.memory_log` (
  memory_id STRING NOT NULL,
  source STRING NOT NULL,               -- 'pulse_briefing' or 'research_export'
  title STRING,                         -- brief label for UI display
  content TEXT NOT NULL,                -- the actual text (briefing or report summary)
  query STRING,                         -- if research_export, the original query
  entities ARRAY<STRING>,               -- extracted entities for filtering/display
  embedding ARRAY<FLOAT64>,             -- Vertex AI embedding vector
  team STRING NOT NULL,                 -- team that created this memory
  pinned BOOL DEFAULT FALSE,            -- pinned memories never expire (max 10 per team)
  expires_at TIMESTAMP,                 -- auto-set to created_at + 60 days (null if pinned)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  created_by STRING                     -- name of person who saved it
);
```

**Example data:**

| memory_id | source | title | content | team | pinned | expires_at |
|-----------|--------|-------|---------|------|--------|------------|
| mem_001 | pulse_briefing | Q1 Resin Alert | "Resin supply constraints expected..." | Product/Supplier | false | 2026-03-05 |
| mem_002 | research_export | AOC Pricing Analysis | "Analysis summary..." | Sales East | true | null |
| mem_003 | pulse_briefing | Midwest Distribution Update | "New warehouse opening..." | Sales East | false | 2026-02-28 |

### Memory Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY LIFECYCLE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Created ──► Active (0-60 days)                             │
│                │                                            │
│                ├──► Time-weighted scoring applies           │
│                │    (newer = higher relevance)              │
│                │                                            │
│                ├──► Day 60: Auto-archived/deleted           │
│                │    (unless pinned)                         │
│                │                                            │
│                └──► Pinned: Never expires                   │
│                     (max 10 per team)                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Trigger Points

### Pulse Tab → Memory (Explicit Save)

When user clicks "Save to Memory" on an ad-hoc briefing:

```javascript
// services/memory.js

async function saveBriefingToMemory(briefing, userName = 'anonymous', userTeam = 'All Others') {
  const memoryId = `mem_${Date.now()}`;
  
  // Extract entities (simple approach - can enhance later)
  const entities = await extractEntities(briefing.content);
  
  // Generate embedding via Vertex AI
  const embedding = await generateEmbedding(briefing.content);
  
  // Calculate expiration (60 days from now)
  const expiresAt = new Date();
  expiresAt.setDate(expiresAt.getDate() + 60);
  
  const query = `
    INSERT INTO \`c1_hub.memory_log\` 
    (memory_id, source, title, content, entities, embedding, team, pinned, expires_at, created_by)
    VALUES (@memoryId, 'pulse_briefing', @title, @content, @entities, @embedding, @team, FALSE, @expiresAt, @createdBy)
  `;
  
  await bigquery.query({
    query,
    params: {
      memoryId,
      title: briefing.title || `Briefing ${new Date().toLocaleDateString()}`,
      content: briefing.content,
      entities,
      embedding,
      team: userTeam,
      expiresAt: expiresAt.toISOString(),
      createdBy: userName
    }
  });
  
  return { memoryId, success: true };
}
```

### Research Tab → Memory (Implicit on Export)

When user downloads/exports a research report:

```javascript
// services/memory.js

async function saveResearchToMemory(query, reportSummary, userName = 'anonymous', userTeam = 'All Others') {
  const memoryId = `mem_${Date.now()}`;
  
  // Combine query and summary for better retrieval
  const contentForEmbedding = `Query: ${query}\n\nFindings: ${reportSummary}`;
  
  const entities = await extractEntities(contentForEmbedding);
  const embedding = await generateEmbedding(contentForEmbedding);
  
  // Calculate expiration (60 days from now)
  const expiresAt = new Date();
  expiresAt.setDate(expiresAt.getDate() + 60);
  
  const insertQuery = `
    INSERT INTO \`c1_hub.memory_log\` 
    (memory_id, source, title, content, query, entities, embedding, team, pinned, expires_at, created_by)
    VALUES (@memoryId, 'research_export', @title, @content, @query, @entities, @embedding, @team, FALSE, @expiresAt, @createdBy)
  `;
  
  await bigquery.query({
    query: insertQuery,
    params: {
      memoryId,
      title: truncate(query, 100),
      content: reportSummary,
      query: query,
      entities,
      embedding,
      team: userTeam,
      expiresAt: expiresAt.toISOString(),
      createdBy: userName
    }
  });
  
  return { memoryId, success: true };
}
```

---

## Memory Management Functions

### Pin/Unpin Memory (max 10 per team)

```javascript
// services/memory.js

const MAX_PINS_PER_TEAM = 10;

async function pinMemory(memoryId, userTeam) {
  // Check current pin count for team
  const countQuery = `
    SELECT COUNT(*) as pin_count 
    FROM \`c1_hub.memory_log\`
    WHERE team = @team AND pinned = TRUE
  `;
  
  const [countResult] = await bigquery.query({ 
    query: countQuery, 
    params: { team: userTeam } 
  });
  
  if (countResult[0].pin_count >= MAX_PINS_PER_TEAM) {
    return { 
      success: false, 
      error: `Maximum ${MAX_PINS_PER_TEAM} pinned memories per team. Unpin something first.` 
    };
  }
  
  // Pin the memory (remove expiration)
  const pinQuery = `
    UPDATE \`c1_hub.memory_log\`
    SET pinned = TRUE, expires_at = NULL
    WHERE memory_id = @memoryId
  `;
  
  await bigquery.query({ query: pinQuery, params: { memoryId } });
  return { success: true };
}

async function unpinMemory(memoryId) {
  // Unpin and set new expiration (60 days from now)
  const expiresAt = new Date();
  expiresAt.setDate(expiresAt.getDate() + 60);
  
  const unpinQuery = `
    UPDATE \`c1_hub.memory_log\`
    SET pinned = FALSE, expires_at = @expiresAt
    WHERE memory_id = @memoryId
  `;
  
  await bigquery.query({ 
    query: unpinQuery, 
    params: { memoryId, expiresAt: expiresAt.toISOString() } 
  });
  
  return { success: true };
}
```

### Cleanup Expired Memories (Scheduled Job)

Run daily via Cloud Scheduler or cron:

```javascript
// jobs/cleanupMemories.js

async function cleanupExpiredMemories() {
  const deleteQuery = `
    DELETE FROM \`c1_hub.memory_log\`
    WHERE expires_at IS NOT NULL 
      AND expires_at < CURRENT_TIMESTAMP()
      AND pinned = FALSE
  `;
  
  const [result] = await bigquery.query({ query: deleteQuery });
  
  console.log(`Memory cleanup: deleted ${result.numRowsAffected || 0} expired memories`);
  
  return { 
    success: true, 
    deletedCount: result.numRowsAffected || 0 
  };
}

module.exports = { cleanupExpiredMemories };
```

Cloud Scheduler config (add to `deploy/scheduler/`):
```yaml
# memory-cleanup.yaml
name: memory-cleanup
schedule: "0 3 * * *"  # Daily at 3 AM
timeZone: America/Chicago
httpTarget:
  uri: ${SERVICE_URL}/api/jobs/cleanup-memories
  httpMethod: POST
  headers:
    X-Job-Key: ${JOB_SECRET_KEY}
```

---

## Retrieval Functions

### Get Preferences (Always in Context)

```javascript
// services/memory.js

/**
 * Gets preferences for the user's team + org-wide preferences.
 * Team-specific preferences are merged with org-wide (team=null).
 */
async function getOrgPreferences(userTeam = null) {
  const query = `
    SELECT preference_id, preference_type, target, description, team
    FROM \`c1_hub.org_preferences\`
    WHERE active = TRUE
      AND (team IS NULL OR team = @userTeam)
    ORDER BY 
      CASE WHEN team IS NULL THEN 1 ELSE 0 END,  -- Team-specific first
      created_at DESC
  `;
  
  const [rows] = await bigquery.query({ query, params: { userTeam } });
  
  return {
    priorities: rows.filter(r => r.preference_type === 'prioritize').map(r => ({
      id: r.preference_id,
      target: r.target,
      description: r.description,
      team: r.team  // null = org-wide
    })),
    blocks: rows.filter(r => r.preference_type === 'block').map(r => ({
      id: r.preference_id,
      target: r.target,
      description: r.description,
      team: r.team
    }))
  };
}

// Format for injection into agent prompts
function formatPreferencesForPrompt(preferences) {
  let rules = '';
  
  const priorityTargets = preferences.priorities.map(p => p.target);
  const blockTargets = preferences.blocks.map(b => b.target);
  
  if (priorityTargets.length) {
    rules += `\nPRIORITY TOPICS - Pay special attention to: ${priorityTargets.join(', ')}`;
  }
  
  if (blockTargets.length) {
    rules += `\nSOFT EXCLUDE - Deprioritize (but don't completely hide) information about: ${blockTargets.join(', ')}`;
  }
  
  return rules || '\nNo specific preferences set.';
}
```

### Get Relevant Memories (Vector Search with Time-Weighting)

```javascript
// services/memory.js

/**
 * Retrieves relevant memories with time-weighted scoring and team prioritization.
 * 
 * Scoring formula:
 *   final_score = base_similarity * time_decay * team_boost * block_penalty
 * 
 * Where:
 *   - base_similarity: 1 - cosine_distance (0 to 1)
 *   - time_decay: 1.0 for today, decays to 0.3 at 60 days (linear)
 *   - team_boost: 1.2x for same team, 1.0x for other teams
 *   - block_penalty: 0.3x if topic matches a blocked preference
 * 
 * Adaptive retrieval:
 *   - Always returns top 3 results (with confidence indicators)
 *   - score >= 0.6: high confidence
 *   - score 0.4-0.6: medium confidence (shown with subtle styling)
 *   - score < 0.4: low confidence (still shown but noted)
 */
async function getRelevantMemories(currentQuery, userTeam, blockedTopics = [], maxResults = 5) {
  // Step 1: Embed the current query
  const queryEmbedding = await generateEmbedding(currentQuery);
  
  // Step 2: Vector search in BigQuery with time-weighting
  const query = `
    WITH scored_memories AS (
      SELECT 
        memory_id,
        source,
        title,
        content,
        query as original_query,
        entities,
        team,
        pinned,
        created_at,
        -- Base similarity (1 - cosine distance, so higher = better)
        (1 - ML.DISTANCE(embedding, @queryEmbedding, 'COSINE')) as base_similarity,
        -- Time decay: 1.0 at day 0, 0.3 at day 60 (linear decay)
        GREATEST(0.3, 1.0 - (TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, DAY) * 0.7 / 60)) as time_decay,
        -- Team boost: 1.2x for same team
        CASE WHEN team = @userTeam THEN 1.2 ELSE 1.0 END as team_boost
      FROM \`c1_hub.memory_log\`
      WHERE expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP()
    )
    SELECT 
      *,
      (base_similarity * time_decay * team_boost) as final_score,
      CASE 
        WHEN (base_similarity * time_decay * team_boost) >= 0.6 THEN 'high'
        WHEN (base_similarity * time_decay * team_boost) >= 0.4 THEN 'medium'
        ELSE 'low'
      END as confidence
    FROM scored_memories
    WHERE base_similarity > 0.3  -- Minimum relevance threshold
    ORDER BY final_score DESC
    LIMIT @maxResults
  `;
  
  const [rows] = await bigquery.query({
    query,
    params: { queryEmbedding, userTeam, maxResults }
  });
  
  // Apply block penalty in JS (easier to check array intersection)
  const processedRows = rows.map(row => {
    const matchesBlock = row.entities?.some(e => 
      blockedTopics.some(b => e.toLowerCase().includes(b.toLowerCase()))
    );
    
    return {
      ...row,
      final_score: matchesBlock ? row.final_score * 0.3 : row.final_score,
      confidence: matchesBlock ? 'low' : row.confidence,
      is_deprioritized: matchesBlock
    };
  });
  
  // Re-sort after block penalty and ensure we always return at least top 3
  return processedRows
    .sort((a, b) => b.final_score - a.final_score)
    .slice(0, Math.max(3, maxResults));
}

// Format for injection into agent context with "I remember when..." feel
function formatMemoriesForPrompt(memories) {
  if (!memories.length) {
    return '';
  }
  
  // Only include high/medium confidence memories in the prompt
  const relevantMemories = memories.filter(m => m.confidence !== 'low' && !m.is_deprioritized);
  
  if (!relevantMemories.length) {
    return '';
  }
  
  let context = '\n\n## Relevant Context from Past Intelligence\n';
  context += '_I found some related past work that may be helpful:_\n';
  
  relevantMemories.forEach(mem => {
    const sourceLabel = mem.source === 'pulse_briefing' ? 'Saved Briefing' : 'Past Research';
    const dateStr = new Date(mem.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const teamNote = mem.team ? ` (${mem.team})` : '';
    
    context += `\n**[${sourceLabel}${teamNote} - ${dateStr}]** ${mem.title}\n${mem.content}\n`;
  });
  
  return context;
}
```

### Combined Context Builder

```javascript
// services/memory.js

async function buildAgentContext(currentQuery, userTeam) {
  // Layer 1: Preferences (always included)
  // Gets both org-wide (team=null) and team-specific preferences
  const preferences = await getOrgPreferences(userTeam);
  const preferencesPrompt = formatPreferencesForPrompt(preferences);
  
  // Layer 2: Relevant memories (retrieved via vector search with time-weighting)
  const memories = await getRelevantMemories(currentQuery, userTeam, preferences.blocks);
  const memoriesPrompt = formatMemoriesForPrompt(memories);
  
  // Layer 3: Proactive context introduction (the "I remember when..." moment)
  const proactiveIntro = generateProactiveIntro(memories);
  
  return {
    preferences,
    memories,
    promptAddition: preferencesPrompt + memoriesPrompt,
    proactiveIntro  // Use this at the START of agent responses when relevant
  };
}

/**
 * Generates the "I remember when..." intro for agent responses.
 * Creates the "part of the team" feel by proactively referencing past work.
 */
function generateProactiveIntro(memories) {
  const highConfidence = memories.filter(m => m.confidence === 'high' && !m.is_deprioritized);
  
  if (!highConfidence.length) {
    return null;
  }
  
  const mostRelevant = highConfidence[0];
  const dateStr = new Date(mostRelevant.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const teamNote = mostRelevant.team ? `your ${mostRelevant.team} team's` : "your team's";
  
  if (mostRelevant.source === 'research_export') {
    return `Based on ${teamNote} previous research on "${mostRelevant.title}" (${dateStr}), I'll focus on what's changed or new...`;
  } else {
    return `I noticed this relates to a briefing ${teamNote} saved on ${dateStr} about "${mostRelevant.title}". I'll build on that context...`;
  }
}
```

---

## Vertex AI Embedding Helper

```javascript
// services/embeddings.js

const { PredictionServiceClient } = require('@google-cloud/aiplatform');

const client = new PredictionServiceClient();
const project = process.env.GCP_PROJECT;
const location = 'us-central1';
const model = 'text-embedding-004';  // or your current model

async function generateEmbedding(text) {
  const endpoint = `projects/${project}/locations/${location}/publishers/google/models/${model}`;
  
  const [response] = await client.predict({
    endpoint,
    instances: [{ content: text }],
  });
  
  return response.predictions[0].embeddings.values;
}

module.exports = { generateEmbedding };
```

---

## Entity Extraction Helper

Simple approach using Claude API (or can use regex for known entities):

```javascript
// services/entities.js

async function extractEntities(text) {
  // Option 1: Simple regex for known entities
  const knownEntities = [
    'AOC', 'Hexion', 'Ashland', 'BASF', 'Huntsman',  // competitors
    'resin', 'fiberglass', 'carbon fiber', 'gelcoat', // materials
    'midwest', 'southeast', 'northeast',              // regions
    'supply chain', 'pricing', 'distribution'         // topics
  ];
  
  const found = knownEntities.filter(entity => 
    text.toLowerCase().includes(entity.toLowerCase())
  );
  
  return found;
  
  // Option 2: Use Claude for richer extraction (more expensive)
  // const response = await anthropic.messages.create({
  //   model: 'claude-sonnet-4-20250514',
  //   max_tokens: 200,
  //   messages: [{
  //     role: 'user',
  //     content: `Extract key entities (companies, materials, topics, regions) from this text. Return as JSON array of strings only.\n\nText: ${text}`
  //   }]
  // });
  // return JSON.parse(response.content[0].text);
}

module.exports = { extractEntities };
```

---

## API Endpoints

```javascript
// routes/memory.js

const express = require('express');
const router = express.Router();
const { 
  getOrgPreferences, 
  addPreference, 
  removePreference,
  getMemoryLog,
  deleteMemory,
  saveBriefingToMemory,
  saveResearchToMemory
} = require('../services/memory');

// ============================================
// PREFERENCES CRUD
// ============================================

// GET /api/memory/preferences
router.get('/preferences', async (req, res) => {
  try {
    const preferences = await getOrgPreferences();
    res.json(preferences);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST /api/memory/preferences
router.post('/preferences', async (req, res) => {
  try {
    const { type, target, description } = req.body;
    const userName = req.headers['x-user-name'] || 'anonymous';
    
    const result = await addPreference(type, target, description, userName);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE /api/memory/preferences/:id
router.delete('/preferences/:id', async (req, res) => {
  try {
    await removePreference(req.params.id);
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================
// MEMORY LOG
// ============================================

// GET /api/memory/log
router.get('/log', async (req, res) => {
  try {
    const memories = await getMemoryLog();
    res.json(memories);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST /api/memory/log/briefing
router.post('/log/briefing', async (req, res) => {
  try {
    const { briefing } = req.body;
    const userName = req.headers['x-user-name'] || 'anonymous';
    
    const result = await saveBriefingToMemory(briefing, userName);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST /api/memory/log/research (called automatically on export)
router.post('/log/research', async (req, res) => {
  try {
    const { query, reportSummary } = req.body;
    const userName = req.headers['x-user-name'] || 'anonymous';
    
    const result = await saveResearchToMemory(query, reportSummary, userName);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE /api/memory/log/:id
router.delete('/log/:id', async (req, res) => {
  try {
    await deleteMemory(req.params.id);
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================
// PIN/UNPIN MEMORIES
// ============================================

// POST /api/memory/log/:id/pin
router.post('/log/:id/pin', async (req, res) => {
  try {
    const userTeam = req.headers['x-user-team'] || 'All Others';
    const result = await pinMemory(req.params.id, userTeam);
    
    if (!result.success) {
      return res.status(400).json(result);
    }
    
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST /api/memory/log/:id/unpin
router.post('/log/:id/unpin', async (req, res) => {
  try {
    const result = await unpinMemory(req.params.id);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============================================
// CLEANUP JOB (called by Cloud Scheduler)
// ============================================

// POST /api/jobs/cleanup-memories
router.post('/jobs/cleanup-memories', async (req, res) => {
  // Verify job key for security
  const jobKey = req.headers['x-job-key'];
  if (jobKey !== process.env.JOB_SECRET_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  
  try {
    const result = await cleanupExpiredMemories();
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
```

---

## Integration with LangGraph Workflow

Pass memory context into your research workflow:

```javascript
// When triggering deep research

async function runDeepResearch(userQuery, userName) {
  // Build context with memory
  const { preferences, memories, promptAddition } = await buildAgentContext(userQuery);
  
  // Call your LangGraph workflow with enriched state
  const result = await fetch(`${LANGGRAPH_SERVICE_URL}/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: userQuery,
      user_name: userName,
      preferences: preferences,
      memory_context: promptAddition,
      relevant_memories: memories
    })
  });
  
  return result.json();
}
```

In your LangGraph workflow (Python), inject into agent prompts:

```python
# In your query groomer or agent nodes

def industry_agent(state: C1State) -> dict:
    memory_context = state.get("memory_context", "")
    
    system_prompt = f"""You are the Industry Watcher agent for C1 Intelligence Hub.
    
{memory_context}

Analyze the following query and provide relevant industry intelligence.
"""
    
    # ... rest of agent logic
```

---

## React Components

### Preferences Management

```jsx
// components/PreferencesPanel.jsx

import { useState, useEffect } from 'react';

export function PreferencesPanel() {
  const [preferences, setPreferences] = useState({ priorities: [], blocks: [] });
  const [newTarget, setNewTarget] = useState('');
  const [newType, setNewType] = useState('prioritize');
  
  useEffect(() => {
    fetchPreferences();
  }, []);
  
  const fetchPreferences = async () => {
    const res = await fetch('/api/memory/preferences');
    const data = await res.json();
    setPreferences(data);
  };
  
  const addPreference = async () => {
    if (!newTarget.trim()) return;
    
    await fetch('/api/memory/preferences', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-User-Name': sessionStorage.getItem('c1_user_name') || 'anonymous'
      },
      body: JSON.stringify({ type: newType, target: newTarget })
    });
    
    setNewTarget('');
    fetchPreferences();
  };
  
  const removePreference = async (id) => {
    await fetch(`/api/memory/preferences/${id}`, { method: 'DELETE' });
    fetchPreferences();
  };
  
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-3">🎯 Priority Topics</h3>
        <p className="text-gray-400 text-sm mb-3">
          The system will highlight insights about these topics
        </p>
        
        <div className="space-y-2">
          {preferences.priorities.map(pref => (
            <div key={pref.id} className="flex items-center justify-between bg-gray-800 p-2 rounded">
              <span className="text-white">{pref.target}</span>
              <button 
                onClick={() => removePreference(pref.id)}
                className="text-gray-400 hover:text-red-400"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </div>
      
      <div>
        <h3 className="text-lg font-semibold text-white mb-3">🚫 Excluded Topics</h3>
        <p className="text-gray-400 text-sm mb-3">
          The system will filter out these topics
        </p>
        
        <div className="space-y-2">
          {preferences.blocks.map(pref => (
            <div key={pref.id} className="flex items-center justify-between bg-gray-800 p-2 rounded">
              <span className="text-white">{pref.target}</span>
              <button 
                onClick={() => removePreference(pref.id)}
                className="text-gray-400 hover:text-red-400"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </div>
      
      {/* Add new preference */}
      <div className="border-t border-gray-700 pt-4">
        <div className="flex gap-2">
          <select 
            value={newType} 
            onChange={(e) => setNewType(e.target.value)}
            className="bg-gray-700 text-white p-2 rounded"
          >
            <option value="prioritize">Prioritize</option>
            <option value="block">Exclude</option>
          </select>
          
          <input
            value={newTarget}
            onChange={(e) => setNewTarget(e.target.value)}
            placeholder="Topic or company name"
            className="flex-1 bg-gray-700 text-white p-2 rounded"
          />
          
          <button 
            onClick={addPreference}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Memory Log Display

```jsx
// components/MemoryLog.jsx

import { useState, useEffect } from 'react';
import { apiCall } from '../utils/api';
import { getCurrentUserTeam } from '../utils/user';

export function MemoryLog() {
  const [memories, setMemories] = useState([]);
  const userTeam = getCurrentUserTeam();
  
  useEffect(() => {
    fetchMemories();
  }, []);
  
  const fetchMemories = async () => {
    const res = await apiCall('/api/memory/log');
    const data = await res.json();
    setMemories(data);
  };
  
  const deleteMemory = async (id) => {
    await apiCall(`/api/memory/log/${id}`, { method: 'DELETE' });
    fetchMemories();
  };
  
  const togglePin = async (id, currentlyPinned) => {
    const endpoint = currentlyPinned ? 'unpin' : 'pin';
    const res = await apiCall(`/api/memory/log/${id}/${endpoint}`, { method: 'POST' });
    const data = await res.json();
    
    if (!data.success && data.error) {
      alert(data.error);  // Show max pins error
      return;
    }
    
    fetchMemories();
  };
  
  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };
  
  const getDaysUntilExpiry = (expiresAt) => {
    if (!expiresAt) return null;
    const now = new Date();
    const expiry = new Date(expiresAt);
    const days = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
    return days;
  };
  
  // Count pins for current team
  const teamPinCount = memories.filter(m => m.team === userTeam && m.pinned).length;
  
  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-white">📚 Memory Log</h3>
        <div className="text-right">
          <span className="text-gray-400 text-sm">{memories.length} items</span>
          <span className="text-gray-500 text-xs block">{teamPinCount}/10 pinned for {userTeam}</span>
        </div>
      </div>
      
      <div className="space-y-3">
        {memories.map(mem => {
          const daysLeft = getDaysUntilExpiry(mem.expires_at);
          const isMyTeam = mem.team === userTeam;
          
          return (
            <div key={mem.memory_id} className={`bg-gray-800 p-4 rounded-lg ${mem.pinned ? 'ring-1 ring-yellow-600' : ''}`}>
              <div className="flex justify-between items-start mb-2">
                <div className="flex items-center gap-2 flex-wrap">
                  {/* Source badge */}
                  <span className={`text-xs px-2 py-1 rounded ${
                    mem.source === 'pulse_briefing' 
                      ? 'bg-purple-900 text-purple-200' 
                      : 'bg-blue-900 text-blue-200'
                  }`}>
                    {mem.source === 'pulse_briefing' ? 'Saved Briefing' : 'Research Export'}
                  </span>
                  
                  {/* Team badge */}
                  <span className={`text-xs px-2 py-1 rounded ${
                    isMyTeam ? 'bg-green-900 text-green-200' : 'bg-gray-700 text-gray-300'
                  }`}>
                    {mem.team}
                  </span>
                  
                  {/* Pinned indicator */}
                  {mem.pinned && (
                    <span className="text-xs text-yellow-400">📌 Pinned</span>
                  )}
                  
                  {/* Expiry indicator */}
                  {!mem.pinned && daysLeft !== null && (
                    <span className={`text-xs ${daysLeft <= 7 ? 'text-red-400' : 'text-gray-500'}`}>
                      Expires in {daysLeft} days
                    </span>
                  )}
                  
                  <span className="text-gray-400 text-xs">
                    {formatDate(mem.created_at)}
                  </span>
                </div>
                
                <div className="flex items-center gap-2">
                  {/* Pin/Unpin button */}
                  <button 
                    onClick={() => togglePin(mem.memory_id, mem.pinned)}
                    className={`text-sm ${mem.pinned ? 'text-yellow-400 hover:text-yellow-300' : 'text-gray-500 hover:text-yellow-400'}`}
                    title={mem.pinned ? 'Unpin (will expire in 60 days)' : 'Pin (never expires)'}
                  >
                    {mem.pinned ? '📌' : '📍'}
                  </button>
                  
                  <button 
                    onClick={() => deleteMemory(mem.memory_id)}
                    className="text-gray-500 hover:text-red-400 text-sm"
                  >
                    Remove
                  </button>
                </div>
              </div>
              
              <h4 className="text-white font-medium mb-1">{mem.title}</h4>
              
              <p className="text-gray-300 text-sm line-clamp-2">{mem.content}</p>
              
              {mem.entities?.length > 0 && (
                <div className="flex gap-1 mt-2 flex-wrap">
                  {mem.entities.map(entity => (
                    <span key={entity} className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                      {entity}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        
        {memories.length === 0 && (
          <p className="text-gray-500 text-center py-8">
            No memories saved yet. Save briefings or export research to build memory.
          </p>
        )}
      </div>
    </div>
  );
}
```

### Save to Memory Button (for Pulse briefings)

```jsx
// components/SaveToMemoryButton.jsx

import { useState } from 'react';

export function SaveToMemoryButton({ briefing }) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  
  const handleSave = async () => {
    setSaving(true);
    
    try {
      await fetch('/api/memory/log/briefing', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-User-Name': sessionStorage.getItem('c1_user_name') || 'anonymous'
        },
        body: JSON.stringify({ briefing })
      });
      
      setSaved(true);
    } catch (error) {
      console.error('Failed to save:', error);
    } finally {
      setSaving(false);
    }
  };
  
  if (saved) {
    return (
      <span className="text-green-400 text-sm flex items-center gap-1">
        ✓ Saved to Memory
      </span>
    );
  }
  
  return (
    <button
      onClick={handleSave}
      disabled={saving}
      className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
    >
      {saving ? 'Saving...' : '📌 Save to Memory'}
    </button>
  );
}
```

---

## Frontend Implementation Status

### Completed (Jan 4, 2026)

**AdHocBriefing.tsx** - Added "Save to Memory" button:
- ✅ Bookmark icon button in ResponseCard header
- ✅ Loading/saved state management
- ✅ Calls `api.saveToMemory()` on click
- ✅ Visual feedback (bookmark → check icon when saved)

**page.tsx** - Implemented export with memory save:
- ✅ `handleExport()` now calls `/api/reports/export` 
- ✅ Downloads file as blob
- ✅ Auto-saves exported report to memory via `api.saveToMemory()`

**lib/api.ts** - Added memory API methods:
- ✅ `saveToMemory()` - POST /api/memory/log
- ✅ `getRelevantMemories()` - GET /api/memory/relevant
- ✅ `toggleMemoryPin()` - PATCH /api/memory/:id/pin
- ✅ `blockTopic()` - POST /api/memory/block
- ✅ All methods include `X-User-Name` and `X-User-Team` headers from localStorage

### Backend Endpoints Required

The frontend calls these endpoints (need backend implementation):

| Frontend Method | HTTP | Endpoint | Body/Query |
|----------------|------|----------|------------|
| `saveToMemory()` | POST | `/api/memory/log` | `{ type, question, answer, sources, confidence, tags }` |
| `getRelevantMemories()` | GET | `/api/memory/relevant` | `?query=...&limit=5` |
| `toggleMemoryPin()` | PATCH | `/api/memory/:id/pin` | `{ pinned: boolean }` |
| `blockTopic()` | POST | `/api/memory/block` | `{ topic: string }` |
| `handleExport()` | POST | `/api/reports/export` | `{ format, items, title }` |

---

## Checklist

### Database Setup
- [x] Create `org_preferences` table in BigQuery (SQL script: backend/scripts/create_memory_tables.sql)
- [x] Create `memory_log` table in BigQuery (SQL script: backend/scripts/create_memory_tables.sql)

### Core Services
- [x] Implement `generateEmbedding()` helper with Vertex AI (memory_service.py)
- [x] Implement `extractEntities()` helper (memory_service.py - using Vertex AI)
- [x] Build memory service functions (CRUD + retrieval) (memory_service.py)
- [x] Implement time-weighted scoring in `getRelevantMemories()` (memory_service.py)
- [x] Implement soft deprioritization for blocked topics (memory_service.py - 0.3x penalty)
- [x] Implement `pinMemory()` / `unpinMemory()` with 10-per-team limit (memory_service.py)
- [x] Implement `generateProactiveIntro()` for "I remember when..." moments (memory_service.py)

### API Endpoints
- [x] POST `/api/memory/log` - Save briefing/research to memory (memory.py router)
- [x] GET `/api/memory/relevant` - Vector search with time-weighting (memory.py router)
- [x] PATCH `/api/memory/:id/pin` - Toggle pin status (memory.py router)
- [x] POST `/api/memory/block` - Block topic from memory (memory.py router)
- [ ] POST `/api/reports/export` - Export report as PDF/DOCX/PPTX (TODO)
- [x] POST `/api/memory/cleanup` - Cleanup job with job key auth (memory.py router)

### Frontend - Login
- [ ] Add team dropdown to PasswordGate (c1-simple-login.md)
- [ ] Store team in sessionStorage
- [x] Pass `X-User-Team` header in API calls (implemented in api.ts)

### Frontend - Memory UI
- [x] Add SaveToMemoryButton to Pulse briefings (AdHocBriefing.tsx)
- [x] Wire research export to auto-save to memory (page.tsx)
- [ ] Add PreferencesPanel to Data & Preferences tab
- [ ] Add MemoryLog component to display saved items
- [ ] Add pin/unpin buttons in MemoryLog
- [ ] Show "expires in X days" for unpinned memories

### Integration
- [x] Build context helper for agent prompts (memory_service.py - build_agent_context())
- [ ] Update LangGraph workflow to receive memory context
- [ ] Add proactive intro to agent responses when relevant
- [ ] Test vector search retrieval quality
- [ ] Test time-decay scoring

### Scheduled Jobs
- [ ] Deploy memory cleanup job (Cloud Scheduler, daily at 3 AM)
- [ ] Add `JOB_SECRET_KEY` to environment variables

### Nice-to-Have (Future)
- [ ] Analytics: track which memories get retrieved most
- [ ] Memory "merge" feature for similar items
- [ ] Team memory sharing across teams
