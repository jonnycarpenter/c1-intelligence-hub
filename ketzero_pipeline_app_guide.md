# KetZero Pipeline App - Product & Technical Guide

**Document Version**: 1.0  
**Created**: January 16, 2026  
**Purpose**: Comprehensive guide for building the standalone Pipeline prospecting product

---

## Executive Summary

The KetZero Pipeline is an AI-powered sales prospecting engine that combines neural search, firmographic enrichment, and intelligence corpus to help B2B sales teams discover qualified prospects, find decision makers, and identify buying signals.

This document provides the technical blueprint for extracting the Pipeline from C1 Intelligence Hub into a standalone, multi-tenant SaaS product.

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Core Value Propositions](#2-core-value-propositions)
3. [Architecture Overview](#3-architecture-overview)
4. [Data Sources & Integrations](#4-data-sources--integrations)
5. [Feature Roadmap](#5-feature-roadmap)
6. [Multi-Tenancy Design](#6-multi-tenancy-design)
7. [Monetization Strategy](#7-monetization-strategy)
8. [Technical Implementation Plan](#8-technical-implementation-plan)
9. [Migration from C1 Hub](#9-migration-from-c1-hub)
10. [Competitive Analysis](#10-competitive-analysis)
11. [Risk Mitigation](#11-risk-mitigation)

---

## 1. Product Vision

### The Problem

B2B sales teams waste 60%+ of their time on manual research:
- Searching for target companies across fragmented sources
- Finding the right decision makers
- Qualifying leads with outdated firmographic data
- Missing buying signals hidden in news and events

### The Solution

**KetZero Pipeline** is an AI-first prospecting platform that:
- Uses natural language to discover companies ("Find aerospace suppliers in Florida with >$50M revenue")
- Auto-enriches every prospect with firmographic intelligence
- Surfaces buying signals from news corpus in real-time
- Provides full contact profiles with one search (no "reveal" friction)
- Learns from user behavior to improve relevance

### Target Users

1. **Sales Development Reps (SDRs)** - High-volume prospecting
2. **Account Executives** - Deep account research
3. **Sales Ops / RevOps** - List building and data hygiene
4. **Business Development** - Partnership and vendor discovery

### Industries (Initial Focus)

- Manufacturing / Industrial
- Aerospace & Defense
- Energy & Utilities
- Technology / SaaS
- (Expandable based on customer demand)

---

## 2. Core Value Propositions

### For End Users

| Pain Point | Pipeline Solution |
|-----------|-------------------|
| Manual company research | AI-powered natural language search |
| Outdated contact data | Real-time enrichment with freshness indicators |
| No visibility into buying signals | Corpus integration surfaces relevant news |
| "Reveal" friction in tools like ZoomInfo | Full contact profiles on first search |
| Separate tools for companies vs contacts | Unified AI agent handles both seamlessly |

### For Sales Leaders

| Pain Point | Pipeline Solution |
|-----------|-------------------|
| Low data quality | Multiple enrichment sources + freshness tracking |
| Expensive data subscriptions | Usage-based pricing, not seat-based |
| Poor adoption of complex tools | Conversational AI - just ask |
| No accountability on data usage | Full audit trail per user/account |

---

## 3. Architecture Overview

### Current C1 Hub Architecture (Baseline)

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Pipeline    │  │ Chat Panel  │  │ Results Panel           │ │
│  │ Dashboard   │  │ (AI Agent)  │  │ (SearchBlock Cards)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Pipeline    │  │ MCP Tools   │  │ Services                │ │
│  │ Agent       │  │ (9 tools)   │  │ (Exa, Apollo, Logo)     │ │
│  │ (Claude)    │  │             │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External APIs                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Exa.ai      │  │ Apollo.io   │  │ Logo.dev                │ │
│  │ (Search)    │  │ (Enrich)    │  │ (Logos)                 │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Target Standalone Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    KetZero Pipeline SaaS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                   Multi-Tenant Layer                       │ │
│  │  • Tenant isolation (data, API keys, usage)               │ │
│  │  • White-label theming support                            │ │
│  │  • Per-tenant corpus (or shared industry corpus)          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                   Pipeline Core Engine                     │ │
│  │                                                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │ │
│  │  │ Agent       │  │ Tool        │  │ Enrichment       │  │ │
│  │  │ Orchestrator│──│ Registry    │──│ Pipeline         │  │ │
│  │  │             │  │             │  │                  │  │ │
│  │  └─────────────┘  └─────────────┘  └──────────────────┘  │ │
│  │         │                                    │            │ │
│  │         ▼                                    ▼            │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │              Provider Abstraction Layer              │ │ │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │ │ │
│  │  │  │ Exa.ai   │ │ Apollo   │ │ ZoomInfo │ │ Custom │ │ │ │
│  │  │  │ Provider │ │ Provider │ │ Provider │ │ CRM    │ │ │ │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                   Intelligence Layer                       │ │
│  │  • Industry Corpus (shared or per-tenant)                 │ │
│  │  • Buying Signal Detection                                │ │
│  │  • News Monitoring                                        │ │
│  │  • Competitor Intelligence                                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Sources & Integrations

### Current Integrations (C1 Hub)

| Source | Purpose | Cost Model | Quality |
|--------|---------|------------|---------|
| **Exa.ai** | Neural company search, lookalikes | Per-search | High for semantic |
| **Apollo.io** | Contact enrichment, firmographics | Per-reveal (contact), FREE (org) | High |
| **Logo.dev** | Company logos | Per-request | Excellent |
| **BigQuery Corpus** | News intelligence, buying signals | Self-hosted | Proprietary |

### Future Integrations (Standalone)

| Source | Purpose | Priority | Notes |
|--------|---------|----------|-------|
| **ZoomInfo** | Alt enrichment for enterprise | P2 | Higher cost, larger DB |
| **LinkedIn Sales Nav** | Contact validation | P2 | Compliance considerations |
| **Clearbit** | Company enrichment | P3 | Good tech stack data |
| **HubSpot/Salesforce** | CRM sync | P1 | Export/import contacts |
| **Slack/Teams** | Notifications | P2 | Buying signal alerts |
| **Customer's own data** | Custom enrichment | P1 | Upload CSV, API |

### Provider Abstraction Layer (Key Design)

```python
# Abstract interface - all providers implement this
class CompanySearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, filters: dict) -> List[Company]:
        pass
    
    @abstractmethod
    async def enrich(self, domain: str) -> CompanyEnrichment:
        pass

class ContactSearchProvider(ABC):
    @abstractmethod
    async def search(self, company: str, filters: dict) -> List[Contact]:
        pass

# Concrete implementations
class ExaCompanyProvider(CompanySearchProvider):
    """Exa.ai for semantic search"""
    pass

class ApolloProvider(CompanySearchProvider, ContactSearchProvider):
    """Apollo.io for enrichment and contacts"""
    pass

class ZoomInfoProvider(CompanySearchProvider, ContactSearchProvider):
    """ZoomInfo for enterprise customers"""
    pass
```

---

## 5. Feature Roadmap

### Phase 1: Foundation (Current - C1 Hub)
*Status: Mostly Complete*

- [x] AI agent with natural language understanding
- [x] Company search (semantic + filtered)
- [x] Contact search with enrichment
- [x] Department badges and data freshness
- [x] Company firmographic display
- [x] LinkedIn profile links
- [x] Logo rendering
- [ ] Export to CSV

### Phase 2: Auto-Reveal & Full Contact Data
*Target: 1-2 weeks after Phase 1*

- [ ] Auto-reveal top N contacts per search (configurable)
- [ ] Display full email/phone directly on cards
- [ ] Click-to-copy for contact info
- [ ] Monthly credit tracking at account level (not per-action)
- [ ] Credit usage dashboard in settings

### Phase 3: Rich Contact Profiles
*Target: 2-3 weeks after Phase 2*

- [ ] Contact photos (from Apollo reveal)
- [ ] Employment tenure calculation ("At company since 2018")
- [ ] Career history (last 2-3 roles)
- [ ] Expandable contact cards (compact → full view)
- [ ] "Copy all" button for CRM paste

### Phase 4: Corpus Intelligence Integration
*Target: 3-4 weeks after Phase 3*

- [ ] Company buying signals badge (🔥 Hot Lead)
- [ ] Contact-level news mentions
- [ ] Related contacts at same company
- [ ] Account intelligence summary
- [ ] Competitor activity alerts

### Phase 5: Multi-Tenancy & Productization
*Target: 6-8 weeks after Phase 4*

- [ ] Tenant management (create, configure, delete)
- [ ] Per-tenant API key vault
- [ ] Per-tenant usage tracking
- [ ] White-label theming (logo, colors)
- [ ] Custom corpus per tenant
- [ ] Billing integration (Stripe)
- [ ] User management (invite, roles)

### Phase 6: Enterprise Features
*Target: 10-12 weeks after Phase 5*

- [ ] SSO / SAML integration
- [ ] CRM sync (Salesforce, HubSpot)
- [ ] Saved searches with scheduling
- [ ] Team collaboration (shared lists)
- [ ] Audit logging
- [ ] Data retention policies
- [ ] SLA dashboard

---

## 6. Multi-Tenancy Design

### Tenant Isolation Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        Tenant: Acme Corp                        │
├─────────────────────────────────────────────────────────────────┤
│ API Keys:                                                       │
│   • Apollo: acme_apollo_key_xxx                                │
│   • Exa: acme_exa_key_xxx                                      │
│   • (or use shared KetZero keys with usage billing)            │
├─────────────────────────────────────────────────────────────────┤
│ Usage Tracking:                                                 │
│   • Searches: 1,234 this month                                 │
│   • Enrichments: 567 this month                                │
│   • Contact reveals: 89 this month                             │
├─────────────────────────────────────────────────────────────────┤
│ Corpus Access:                                                  │
│   • Shared: Manufacturing, Aerospace                           │
│   • Custom: Acme competitor watch list                         │
├─────────────────────────────────────────────────────────────────┤
│ Users:                                                          │
│   • Admin: admin@acme.com                                      │
│   • Users: sales1@acme.com, sales2@acme.com                    │
├─────────────────────────────────────────────────────────────────┤
│ Theming:                                                        │
│   • Logo: acme_logo.png                                        │
│   • Primary color: #1E3A8A                                     │
│   • Domain: pipeline.acme.com (optional)                       │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema (BigQuery/PostgreSQL)

```sql
-- Tenants table
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(63) UNIQUE NOT NULL,
    
    -- API keys (encrypted)
    apollo_api_key_encrypted TEXT,
    exa_api_key_encrypted TEXT,
    use_shared_keys BOOLEAN DEFAULT true,
    
    -- Theming
    logo_url TEXT,
    primary_color VARCHAR(7),
    custom_domain TEXT,
    
    -- Limits
    monthly_search_limit INT DEFAULT 10000,
    monthly_enrich_limit INT DEFAULT 5000,
    monthly_reveal_limit INT DEFAULT 500,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active'
);

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',  -- admin, user, viewer
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Usage tracking
CREATE TABLE usage_events (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    event_type VARCHAR(50),  -- search, enrich, reveal
    event_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Saved prospects (per tenant)
CREATE TABLE saved_prospects (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    company_domain VARCHAR(255),
    company_data JSONB,
    contacts JSONB[],
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 7. Monetization Strategy

### Pricing Models (Options)

#### Option A: Usage-Based Pricing
*Recommended for SMB market*

| Tier | Monthly Fee | Searches | Enrichments | Reveals | Overage |
|------|-------------|----------|-------------|---------|---------|
| Starter | $99 | 500 | 250 | 50 | $0.20/search |
| Growth | $299 | 2,000 | 1,000 | 200 | $0.15/search |
| Pro | $599 | 5,000 | 3,000 | 500 | $0.10/search |
| Enterprise | Custom | Unlimited | Unlimited | Custom | Negotiated |

#### Option B: Seat-Based Pricing
*Familiar for ZoomInfo competitors*

| Tier | Monthly/Seat | Seats | Features |
|------|--------------|-------|----------|
| Team | $99/seat | 5+ | Core search, 200 reveals/user |
| Business | $199/seat | 10+ | + Corpus intel, unlimited search |
| Enterprise | Custom | 25+ | + SSO, CRM sync, custom corpus |

#### Option C: Credits System
*Maximize flexibility*

- Buy credits in packs ($100 = 1,000 credits)
- Search = 1 credit
- Enrich = 2 credits
- Reveal = 5 credits
- Corpus query = 1 credit

### Cost Structure

| Cost Category | Per-Unit Cost | Notes |
|---------------|---------------|-------|
| Exa.ai search | ~$0.01/search | Bulk pricing available |
| Apollo enrich (org) | FREE | No credit cost |
| Apollo contact reveal | ~$0.20/reveal | 1 credit per reveal |
| Claude API | ~$0.003/1K tokens | ~$0.05/query |
| Logo.dev | ~$0.001/logo | Very cheap |
| GCP hosting | ~$500/month | Cloud Run, BigQuery |

**Gross Margin Target**: 70-80%

---

## 8. Technical Implementation Plan

### Codebase Structure (Standalone)

```
ketzero-pipeline/
├── packages/
│   ├── core/                    # Shared business logic
│   │   ├── agents/              # Agent orchestration
│   │   ├── providers/           # Data source providers
│   │   │   ├── base.py          # Abstract interfaces
│   │   │   ├── exa.py           # Exa.ai implementation
│   │   │   ├── apollo.py        # Apollo.io implementation
│   │   │   ├── zoominfo.py      # ZoomInfo (future)
│   │   │   └── custom.py        # Custom data sources
│   │   ├── enrichers/           # Post-search enrichment
│   │   │   ├── corpus.py        # News/intel corpus
│   │   │   ├── signals.py       # Buying signal detection
│   │   │   └── scoring.py       # Lead scoring
│   │   ├── models/              # Shared data models
│   │   └── utils/               # Shared utilities
│   │
│   ├── api/                     # FastAPI backend
│   │   ├── routes/              # API endpoints
│   │   ├── middleware/          # Auth, rate limiting, tenant
│   │   ├── schemas/             # Pydantic models
│   │   └── main.py              # FastAPI app
│   │
│   └── web/                     # Next.js frontend
│       ├── src/
│       │   ├── components/      # UI components
│       │   ├── hooks/           # React hooks
│       │   ├── lib/             # API client, utils
│       │   └── app/             # Next.js app router
│       └── public/
│
├── infra/                       # Infrastructure as code
│   ├── terraform/               # GCP/AWS resources
│   ├── kubernetes/              # K8s manifests (if needed)
│   └── docker/                  # Dockerfiles
│
├── scripts/                     # Operational scripts
│   ├── migrations/              # Database migrations
│   ├── seed/                    # Seed data
│   └── monitoring/              # Health checks
│
└── docs/                        # Documentation
    ├── api/                     # API docs
    ├── guides/                  # User guides
    └── internal/                # Internal docs
```

### Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend Framework | FastAPI | Async, OpenAPI, typing |
| Frontend Framework | Next.js 14 | App router, SSR, TypeScript |
| Database | PostgreSQL + BigQuery | Postgres for tenants/users, BQ for analytics |
| Auth | Clerk or Auth0 | Don't build auth |
| Hosting | GCP Cloud Run | Auto-scaling, pay-per-use |
| LLM Provider | Anthropic (Claude) | Best for tool use |
| Observability | LangSmith + Datadog | LLM traces + infra |

### Development Phases

#### Phase A: Extract Core (2 weeks)
1. Create new repo with monorepo structure
2. Copy Pipeline agent, tools, services from C1 Hub
3. Abstract provider interfaces
4. Create minimal FastAPI app
5. Verify core flows work standalone

#### Phase B: Multi-Tenant Foundation (3 weeks)
1. Add tenant/user database schema
2. Implement auth middleware
3. Add API key vault per tenant
4. Implement usage tracking
5. Add basic admin UI

#### Phase C: Frontend Port (2 weeks)
1. Copy Pipeline components from C1 Hub
2. Add tenant-aware routing
3. Implement settings/admin pages
4. Add user management UI

#### Phase D: Production Hardening (2 weeks)
1. Rate limiting
2. Error handling
3. Logging/monitoring
4. Automated testing
5. CI/CD pipeline

---

## 9. Migration from C1 Hub

### What to Copy (Directly Usable)

| Component | Source Path | Notes |
|-----------|-------------|-------|
| Pipeline Agent | `backend/app/agents/pipeline/` | Core orchestration |
| Pipeline Tools | `backend/app/mcp/tools/pipeline_search.py` | Search tools |
| Apollo Service | `backend/app/services/apollo_service.py` | Enrichment |
| Exa Service | `backend/app/services/exa_service.py` | Neural search |
| Logo Service | `backend/app/services/logo_service.py` | Branding |
| Pipeline Dashboard | `frontend/src/components/pipeline/` | UI components |
| Pipeline Hook | `frontend/src/hooks/usePipeline.ts` | State management |
| Types | `frontend/src/types/index.ts` | TypeScript types |

### What to Leave (C1-Specific)

| Component | Reason |
|-----------|--------|
| Weekly Briefing generators | C1 intelligence product |
| Digest system | C1 content curation |
| Ad-hoc briefing | C1 research product |
| Deep Research workflow | C1 research product |
| Podcast generation | C1 audio product |

### What to Build New

| Component | Purpose |
|-----------|---------|
| Tenant management | Multi-tenancy |
| User authentication | Clerk/Auth0 integration |
| Usage metering | Billing foundation |
| Admin dashboard | Tenant configuration |
| Onboarding flow | New customer setup |
| API key management | Secure key storage |

---

## 10. Competitive Analysis

### Direct Competitors

| Competitor | Strengths | Weaknesses | Our Advantage |
|------------|-----------|------------|---------------|
| **ZoomInfo** | Huge database, established | Expensive ($15K+/yr), complex UI | AI-first UX, usage-based pricing |
| **Apollo.io** | Good data, affordable | Manual search, no AI agent | Conversational AI, corpus intel |
| **LinkedIn Sales Nav** | Social proof, relationship data | No firmographics, LinkedIn-only | Multi-source, full enrichment |
| **Clearbit** | Great tech stack data | Limited contacts | Combined company + contact |
| **Cognism** | GDPR compliant, EU data | Less US coverage | US focus initially |

### Differentiation

1. **AI-First**: Natural language queries vs. form-based search
2. **No Friction**: Full data upfront, no per-contact reveal
3. **Intelligence Layer**: Buying signals from news corpus
4. **Usage-Based Pricing**: Pay for what you use
5. **Industry Specialization**: Start with manufacturing/aerospace

---

## 11. Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Apollo API changes | High | Provider abstraction layer |
| LLM cost spikes | Medium | Usage caps, caching, model fallbacks |
| Data quality issues | High | Multi-source validation, freshness tracking |
| Scaling challenges | Medium | GCP auto-scaling, queue-based processing |

### Business Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Apollo ToS violation | High | Legal review, compliance monitoring |
| Competition from incumbents | Medium | Niche focus, speed to market |
| Customer churn | Medium | Usage analytics, health scoring |
| Pricing pressure | Medium | Value-based positioning, not cost |

### Data/Privacy Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| GDPR compliance | High | EU data handling policies |
| CCPA compliance | Medium | California privacy policies |
| Data breach | High | Encryption, access controls, SOC2 |

---

## Appendix A: API Specification (Draft)

### Core Endpoints

```yaml
# Search companies
POST /api/v1/search/companies
{
  "query": "aerospace suppliers in Florida",
  "filters": {
    "min_revenue": 50000000,
    "min_employees": 100,
    "states": ["Florida", "Texas"]
  },
  "limit": 25
}

# Search contacts
POST /api/v1/search/contacts
{
  "company_domain": "hexcel.com",
  "department": "purchasing",
  "seniorities": ["director", "vp"],
  "limit": 10
}

# Get company enrichment
GET /api/v1/companies/{domain}/enrich

# Get company intelligence (corpus)
GET /api/v1/companies/{domain}/intelligence

# Chat with agent
POST /api/v1/chat
{
  "session_id": "uuid",
  "message": "Find purchasing managers at these companies"
}
```

### Webhook Events

```yaml
# Buying signal detected
{
  "event": "buying_signal_detected",
  "company_domain": "hexcel.com",
  "signal_type": "expansion",
  "summary": "Hexcel announces $500M factory expansion",
  "article_url": "https://..."
}
```

---

## Appendix B: Sample User Flows

### Flow 1: Quick Company Search

```
User: "Find aerospace composites suppliers in the southwest"
Agent: [calls search_companies with filters]
Result: 25 company cards with logos, employees, revenue
User: "Show me contacts at Hexcel"
Agent: [calls find_company_contacts]
Result: 10 contact cards with name, title, department, email/phone
User: "Export these to CSV"
Agent: [generates download]
```

### Flow 2: Account Research

```
User: "Tell me everything about Spirit AeroSystems"
Agent: [calls enrich_company + get_entity_mentions]
Chat: "Spirit AeroSystems: 18K employees, $7B revenue, recent news about Boeing 737 MAX supply chain..."
Result: Company card with full firmographics + news timeline
User: "Find their procurement team"
Agent: [calls find_company_contacts with department=purchasing]
Result: Contact cards for procurement leadership
```

### Flow 3: Buying Signal Hunt

```
User: "Which of my saved accounts have recent funding or expansion news?"
Agent: [queries corpus for saved account domains]
Chat: "3 of your saved accounts have recent activity:
- Toray: $200M investment in US carbon fiber capacity
- Solvay: Acquired small composites startup
- Hexcel: Hiring surge in Phoenix facility"
User: "Show me contacts at Toray"
...
```

---

## Appendix C: Success Metrics

### Product Metrics

| Metric | Target (6 months) |
|--------|-------------------|
| Monthly Active Users | 500 |
| Searches per user/month | 200 |
| Conversion (trial → paid) | 25% |
| Net Revenue Retention | 110% |
| NPS | 40+ |

### Technical Metrics

| Metric | Target |
|--------|--------|
| Search latency (p95) | < 2s |
| Uptime | 99.9% |
| Error rate | < 0.1% |
| LLM cost per search | < $0.10 |

---

*Document maintained by: KetZero Engineering*  
*Last updated: January 16, 2026*
