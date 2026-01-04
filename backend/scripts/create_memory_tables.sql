-- BigQuery Table Creation Script for Long-Term Memory Features
-- Run these commands in BigQuery Console or via bq CLI
-- Project: compositesone-hub-prod (or your project)
-- Dataset: c1_intelligence

-- =============================================================================
-- ORGANIZATION PREFERENCES TABLE
-- Stores user/team priorities and blocked topics
-- =============================================================================

CREATE TABLE IF NOT EXISTS `c1_intelligence.org_preferences` (
  id STRING NOT NULL,                    -- UUID
  type STRING NOT NULL,                  -- 'prioritize' or 'block'
  target STRING NOT NULL,                -- Topic/entity being prioritized or blocked
  description STRING,                    -- Optional description
  team STRING DEFAULT 'All Others',      -- Team scope: Sales East, Sales West, Marketing, Product/Supplier, All Others
  created_by STRING,                     -- Username who created
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  is_active BOOL DEFAULT TRUE,           -- Soft delete flag
  
  -- For auditing and cleanup
  updated_at TIMESTAMP,
  deactivated_at TIMESTAMP,
  deactivated_by STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY team, type
OPTIONS (
  description = 'Organization preferences for memory system (priorities and blocks)',
  labels = [('app', 'c1-intel-hub'), ('feature', 'long-term-memory')]
);

-- Indexes (BigQuery doesn't have traditional indexes, but clustering helps)
-- Cluster by team and type for faster filtered queries


-- =============================================================================
-- MEMORY LOG TABLE
-- Stores briefings and research exports with embeddings for vector search
-- =============================================================================

CREATE TABLE IF NOT EXISTS `c1_intelligence.memory_log` (
  id STRING NOT NULL,                    -- UUID
  source STRING NOT NULL,                -- 'briefing' or 'research_export'
  question STRING NOT NULL,              -- The query/question asked
  answer STRING NOT NULL,                -- The response/answer
  sources ARRAY<STRUCT<                  -- Source references
    title STRING,
    url STRING,
    snippet STRING
  >>,
  confidence STRING,                     -- Confidence level (high/medium/low)
  tags ARRAY<STRING>,                    -- Extracted entities/tags
  
  -- User/Team context
  user_name STRING,                      -- Who created this
  team STRING DEFAULT 'All Others',      -- Team scope
  
  -- Embedding for vector search
  embedding ARRAY<FLOAT64>,              -- text-embedding-004 vectors (768 dims)
  
  -- Pin and expiration
  pinned BOOL DEFAULT FALSE,             -- Pinned items never expire
  pinned_by STRING,                      -- Who pinned it
  pinned_at TIMESTAMP,                   -- When it was pinned
  expires_at TIMESTAMP,                  -- When it expires (60 days default, NULL if pinned)
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY team, pinned, source
OPTIONS (
  description = 'Memory log for briefings and research with vector embeddings',
  labels = [('app', 'c1-intel-hub'), ('feature', 'long-term-memory')]
);


-- =============================================================================
-- SAMPLE DATA (Optional - for testing)
-- =============================================================================

-- Sample preference: Prioritize a key customer
-- INSERT INTO `c1_intelligence.org_preferences` (id, type, target, description, team, created_by)
-- VALUES (
--   GENERATE_UUID(),
--   'prioritize',
--   'Boeing',
--   'Key customer - always include relevant news',
--   'Sales East',
--   'admin'
-- );

-- Sample preference: Block competitor spam
-- INSERT INTO `c1_intelligence.org_preferences` (id, type, target, description, team, created_by)
-- VALUES (
--   GENERATE_UUID(),
--   'block',
--   'CompetitorX press releases',
--   'Too much noise, not actionable',
--   'All Others',
--   'admin'
-- );


-- =============================================================================
-- USEFUL QUERIES FOR MAINTENANCE
-- =============================================================================

-- Count memories by team
-- SELECT team, COUNT(*) as count, SUM(IF(pinned, 1, 0)) as pinned_count
-- FROM `c1_intelligence.memory_log`
-- WHERE created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
-- GROUP BY team;

-- Find expired memories (for cleanup job)
-- SELECT id, question, team, created_at, expires_at
-- FROM `c1_intelligence.memory_log`
-- WHERE expires_at < CURRENT_TIMESTAMP() 
--   AND pinned = FALSE;

-- Check pin counts per team (max 10 per team)
-- SELECT team, COUNT(*) as pin_count
-- FROM `c1_intelligence.memory_log`
-- WHERE pinned = TRUE
-- GROUP BY team
-- ORDER BY pin_count DESC;

-- Active preferences by team
-- SELECT team, type, COUNT(*) as count
-- FROM `c1_intelligence.org_preferences`
-- WHERE is_active = TRUE
-- GROUP BY team, type
-- ORDER BY team, type;
