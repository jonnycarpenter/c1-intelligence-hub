"""
Intelligence Hub Guide - Knowledge Base
========================================

Curated knowledge for the Guide AI agent to discuss with prospective users.
This module contains all information the Guide is allowed to share about the platform.

IMPORTANT: This knowledge base intentionally excludes:
- Specific technology partners (Exa, Tavily, FMP, SEC-io, etc.)
- Backend architecture details
- API provider names
- Cloud infrastructure specifics
- LLM provider names
"""

# =============================================================================
# PLATFORM CORE VALUE PROPOSITION
# =============================================================================

PLATFORM_VALUE = """
The Intelligence Hub is designed around one core promise: "Become the most informed person in the room in 5 minutes."

This platform is built for complex industrial businesses - distributors, manufacturers, and suppliers operating in markets with:
- Hundreds of suppliers to monitor
- Thousands of SKUs to track
- Multiple industry verticals to serve
- Fast-moving competitive landscapes

The Intelligence Hub is customized for YOUR strategic priorities:
- Your specific competitors
- The materials and products you care about
- Your supply chain dynamics
- Market-specific factors that affect your business
- Everything you want to know about NOW, not later

Our AI-powered intelligence system doesn't just aggregate news - it actively HUNTS for the signals that matter to your business before they become common knowledge.
"""

# =============================================================================
# INDUSTRY PUBLICATIONS WE MONITOR
# =============================================================================

PUBLICATIONS = """
We continuously monitor 12+ specialized industry publications to ensure comprehensive coverage:

**Primary Composites Trade Publications:**
- CompositesWorld - The leading composites industry publication
- JEC Composites - Global composites news and analysis
- Composites Manufacturing Magazine (ACMA) - Manufacturing-focused coverage
- ACMA News - American Composites Manufacturers Association updates

**Materials & Plastics:**
- Plastics Today - Crossover materials coverage

**Industry Verticals:**
- Aviation Week - Aerospace industry intelligence
- Wind Power Engineering - Wind energy sector
- Offshore Wind - Offshore wind projects and developments
- Boating Industry - Marine and recreational marine
- Marine Industry News - Commercial marine coverage

**Supply Chain & Logistics:**
- FreightWaves - Real-time freight and logistics intelligence
- Supply Chain Dive - Supply chain news and analysis

Each publication is filtered and analyzed by our AI to extract only the most relevant intelligence for your business.
"""

# =============================================================================
# AI-POWERED SEARCH QUERIES
# =============================================================================

SEARCH_QUERIES = """
We run 150+ AI-powered search queries DAILY to hunt for strategic intelligence. Unlike passive news aggregation, our system actively searches for specific signals.

**Example Query:**
"carbon fiber supply shortage allocation" - Our system hunts for supply disruption signals before they hit mainstream news, giving you early warning on potential supply chain issues.

**Query Categories We Cover:**

1. **Supply Chain Disruptions**
   - Raw material shortages
   - Force majeure events
   - Tariff and trade impacts
   - Production halts and plant closures

2. **M&A and Investment Activity**
   - Acquisitions and mergers
   - Private equity moves
   - IPOs and funding rounds
   - Bankruptcy and restructuring signals

3. **Contract Awards**
   - Aerospace program wins (Boeing, Airbus)
   - Defense contracts (Pentagon, DoD)
   - Wind energy blade contracts
   - Automotive lightweighting programs

4. **Key Supplier Monitoring**
   - Hexcel, Toray, Owens Corning, Solvay, and 20+ others
   - Production capacity changes
   - Earnings and guidance updates

5. **Emerging Applications**
   - Hydrogen storage vessels
   - eVTOL and urban air mobility
   - EV battery enclosures
   - Satellite and space structures

6. **OEM Demand Signals**
   - Boeing 737/787 production rates
   - Airbus A350/A320 capacity
   - Vestas/Siemens Gamesa blade orders
   - Tesla/BMW lightweighting programs

7. **Capacity Expansion**
   - New plant announcements
   - Production line investments
   - Facility upgrades

8. **Technology Shifts**
   - Automated fiber placement (AFP)
   - Thermoplastic composites (PEEK, PEKK)
   - Carbon fiber recycling
   - 3D printing advances

9. **Regulatory Changes**
   - PFAS regulations
   - EPA emissions standards
   - REACH chemical regulations
   - Carbon border adjustments

10. **Industry Demand Forecasts**
    - Aerospace composites outlook
    - Wind energy growth projections
    - Automotive lightweighting trends
    - Marine and defense spending
"""

# =============================================================================
# ADDITIONAL INTELLIGENCE SOURCES
# =============================================================================

ADDITIONAL_SOURCES = """
Beyond publications and search queries, we monitor:

**Financial Intelligence:**
- Earnings call transcripts from publicly traded competitors
- SEC filing monitoring (10-K, 10-Q, 8-K filings)
- Analyst ratings and price target changes

**Logistics & Freight:**
- Oceanic shipping costs and trends
- Container freight rates
- Port congestion monitoring
- Supply chain lead time indicators
"""

# =============================================================================
# TAB FEATURES
# =============================================================================

TAB_FEATURES = """
The Intelligence Hub is organized into specialized workspaces:

**📊 Need to Know** (Your Strategic Command Center)
Your daily starting point. Surfaces everything you need to know about your strategic priorities and "Need to Know" events across your entire ecosystem. Features:
- AI-generated weekly strategic briefing
- Audio podcast version you can listen to on the go
- Persistent themes tracking (what's continuing from last week)
- Emerging signals (what's new)
- Actionable insights you can share with leadership

**🔍 Market Intelligence**
Category-filtered news digest for exploring specific topics:
- Filter by category: Competitors, Supply Chain, Regulatory, M&A, etc.
- AI-powered summaries for quick understanding
- Priority bulletin board highlighting what needs attention
- Deep dive into any category with one click

**🔬 Deep Research**
Multi-agent research engine for comprehensive analysis:
- Ask any strategic question
- 6 specialized AI agents work in parallel to research your topic
- Financial analysis, industry trends, competitive intelligence
- Sourced insights with citations
- Export-ready reports for stakeholders

**🎯 Pipeline**
AI-powered prospect discovery for sales teams:
- Find companies in specific industries
- Identify decision makers
- Enrich with firmographic data
- Territory-based filtering

**🎤 Field Intel**
Capture intelligence from the field:
- Voice memos from customer visits
- Competitor sightings
- Trade show observations
- Field team knowledge capture

**📦 Products / 🏢 Companies / 🏭 Industries** (Coming Soon)
Dedicated tracking and analysis dashboards for:
- Product intelligence and SKU analysis
- Company monitoring and competitor tracking
- Industry trend analysis
"""

# =============================================================================
# MATERIALS WE TRACK
# =============================================================================

MATERIALS = """
We track pricing, supply, and news for 50+ materials including:

**Fibers:**
- Carbon fiber (multiple grades: aerospace, industrial, recycled)
- E-glass and S-glass fibers
- Aramid fibers (Kevlar)
- Basalt fibers
- Natural fibers

**Resins:**
- Epoxy resins
- Vinyl ester resins
- Polyester resins
- Phenolic resins
- Polyurethane systems

**Intermediates:**
- Prepreg materials (thermoset and thermoplastic)
- SMC (Sheet Molding Compound)
- BMC (Bulk Molding Compound)
- Woven and multiaxial fabrics
- Unidirectional tape

**Core Materials:**
- Honeycomb (Nomex, aluminum)
- PVC foam (Divinycell)
- PET foam
- Balsa wood
- SAN foam

**Thermoplastics:**
- PEEK
- PEKK
- PPS
- Nylon/Polyamide

**Ancillary:**
- Gel coats
- Release agents
- Adhesives
- Tooling materials
"""

# =============================================================================
# COMPETITORS WE MONITOR
# =============================================================================

COMPETITORS = """
We actively monitor major composites industry players including:

**Material Manufacturers:**
- Hexcel - Carbon fiber and prepreg leader
- Toray - World's largest carbon fiber producer
- Solvay/Syensqo - Aerospace prepreg specialist
- Owens Corning - Glass fiber giant
- Huntsman - Epoxy and polyurethane systems
- Gurit - Wind and marine composites
- Teijin - Carbon fiber and CFRP
- SGL Carbon - Graphite and carbon materials
- Mitsubishi Chemical - Carbon fiber and intermediates
- BASF - Resins and chemical systems
- DuPont - Kevlar and specialty materials
- 3M - Adhesives and specialty products
- Hexion - Epoxy and phenolic resins
- DIAB - Core materials
- Chomarat/Vectorply - Reinforcement fabrics
"""

# =============================================================================
# OEMS AND END MARKETS
# =============================================================================

OEMS_AND_MARKETS = """
We track demand signals from major OEMs across all key verticals:

**Aerospace:**
- Boeing, Airbus, Embraer
- Spirit AeroSystems
- Lockheed Martin, Northrop Grumman
- GE Aerospace, Safran
- Business jet: Gulfstream, Bombardier, Textron Aviation
- eVTOL: Joby Aviation, Archer Aviation

**Wind Energy:**
- Vestas, Siemens Gamesa, GE Vernova
- Nordex, Goldwind, Envision
- TPI Composites, LM Wind Power

**Marine:**
- Brunswick, Beneteau
- Malibu Boats, MasterCraft
- Grady-White, Regulator Marine

**Automotive:**
- BMW (carbon fiber pioneer)
- Tesla, Rivian (EV composites)
- Ford, GM, Toyota

**Defense & Space:**
- Raytheon RTX
- Northrop Grumman
- Lockheed Martin
- SpaceX, Blue Origin
- L3Harris, BAE Systems

**Construction & Infrastructure:**
- Composite rebar and bridge applications
- Strongwell, Bedford Reinforced Plastics
"""

# =============================================================================
# STRATEGIC BRIEFING DETAILS
# =============================================================================

STRATEGIC_BRIEFING = """
The Strategic Briefing is one of our most powerful features. Here's how it works:

**Generated Weekly:**
Every week, our AI analyzes all intelligence gathered and produces a comprehensive briefing designed for executive consumption.

**What's Included:**
- **Bottom Line Up Front (BLUF)**: One-sentence executive summary
- **Persistent Themes**: Topics continuing from previous weeks (you can track how stories evolve)
- **Emerging Signals**: New developments that just hit our radar
- **Section Deep Dives**: Detailed analysis of each major theme
- **Source Citations**: Every insight is linked to original sources

**Audio Podcast:**
Listen on the go! The entire briefing is converted to a natural-sounding audio format (4-6 minutes) so you can stay informed during your commute.

**Why It Matters:**
You walk into any meeting knowing what's happening across your competitive landscape, supply chain, and industry - without spending hours reading. "Become the most informed person in the room in 5 minutes."
"""

# =============================================================================
# WHAT WE DON'T SHARE (Internal Reference)
# =============================================================================

# NEVER mention these to users:
# - Exa.ai (semantic search)
# - Tavily (web search)
# - FMP / Financial Modeling Prep (financial data)
# - SEC-io (SEC filings)
# - AssemblyAI (transcription)
# - ElevenLabs (text-to-speech)
# - Anthropic Claude (LLM)
# - OpenAI GPT (fallback LLM)
# - Google Cloud Platform specifics
# - BigQuery, Cloud Run, etc.
# - Any API provider names


# =============================================================================
# COMPILED KNOWLEDGE FOR SYSTEM PROMPT
# =============================================================================

def get_full_knowledge_base() -> str:
    """Returns the complete knowledge base as a single string for the system prompt."""
    return f"""
{PLATFORM_VALUE}

=== INDUSTRY PUBLICATIONS ===
{PUBLICATIONS}

=== AI-POWERED SEARCH QUERIES ===
{SEARCH_QUERIES}

=== ADDITIONAL INTELLIGENCE SOURCES ===
{ADDITIONAL_SOURCES}

=== PLATFORM FEATURES ===
{TAB_FEATURES}

=== MATERIALS WE TRACK ===
{MATERIALS}

=== COMPETITORS WE MONITOR ===
{COMPETITORS}

=== OEMS AND END MARKETS ===
{OEMS_AND_MARKETS}

=== STRATEGIC BRIEFING ===
{STRATEGIC_BRIEFING}
"""
