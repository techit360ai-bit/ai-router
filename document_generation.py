"""
TECHIT -- DOCUMENT GENERATION ENGINE
======================================
Module: document_generation.py
Layer:  Incubation Hub -- Document Factory

Design Philosophy
─────────────────
Founders spend weeks writing business plans and days creating pitch decks.
TechIT eliminates this entirely -- generating every document in minutes,
from the analysis already computed by the platform.

The Document Generation Engine is:
  "Notion + McKinsey Report + Pitch Deck -- generated instantly."

It sits AFTER analysis and converts AI outputs into:
  -> investor-ready
  -> shareable
  -> downloadable
  -> structured documents

This turns TechIT into:
  👉 Startup Operating System
  👉 Document Factory
  👉 Investor Preparation Engine

Position in Incubation Hub
───────────────────────────
  Idea Intake       (existing)
  AI Evaluation     (existing)
  Startup Builder   (existing)
  Idea & Solution Hub (new -- idea_solution_hub.py)
  📄 Document Generation (NEW -- this file)
  Cohorts           (existing)
  Training Ecosystem (existing)

Route: /incubator/documents

8 Document Types
─────────────────
  1. Executive Summary      -- 1–2 pages, investor-facing
  2. Full Business Plan     -- 10–25 pages, comprehensive
  3. Pitch Deck             -- slide-by-slide structure
  4. Investor Report        -- deep analysis with EVI-I and signals
  5. Unicorn Analysis Report -- 10 drivers, benchmarking, insights
  6. Product Roadmap        -- MVP -> Beta -> Launch -> Scale
  7. Financial Projection   -- revenue model, cost structure, forecast
  8. Market Research Report -- TAM/SAM/SOM, trends, competition

New TaskTypes added to ai_router_core.py
─────────────────────────────────────────
  DOCUMENT_EXECUTIVE_SUMMARY   DOCUMENT_BUSINESS_PLAN
  DOCUMENT_PITCH_DECK          DOCUMENT_INVESTOR_REPORT
  DOCUMENT_UNICORN_REPORT      DOCUMENT_PRODUCT_ROADMAP
  DOCUMENT_FINANCIAL_PROJECTION DOCUMENT_MARKET_RESEARCH

New AgentTypes added to agent_orchestration.py
────────────────────────────────────────────────
  DOCUMENT_GENERATION_AGENT    DOCUMENT_EXPORT_AGENT

New DB Tables (added to database_schema.py)
────────────────────────────────────────────
  generated_documents    document_exports    document_templates
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================================
# ENUMERATIONS
# ============================================================================

class DocumentType(Enum):
    EXECUTIVE_SUMMARY       = "executive_summary"
    BUSINESS_PLAN           = "business_plan"
    PITCH_DECK              = "pitch_deck"
    INVESTOR_REPORT         = "investor_report"
    UNICORN_ANALYSIS_REPORT = "unicorn_analysis_report"
    PRODUCT_ROADMAP         = "product_roadmap"
    FINANCIAL_PROJECTION    = "financial_projection"
    MARKET_RESEARCH_REPORT  = "market_research_report"


class DocumentStyle(Enum):
    CONCISE     = "concise"     # shortest, highest density
    STANDARD    = "standard"    # balanced -- default
    DETAILED    = "detailed"    # maximum depth


class DocumentAudience(Enum):
    FOUNDER_USE = "founder_use"     # internal operations
    INVESTORS   = "investors"       # VC / angel ready
    ACCELERATORS = "accelerators"   # programme applications


class ExportFormat(Enum):
    PDF         = "pdf"
    NOTION_DOC  = "notion_doc"
    GOOGLE_DOC  = "google_doc"
    SLIDE_DECK  = "slide_deck"      # for pitch decks


# ============================================================================
# DOCUMENT DATA STRUCTURES
# ============================================================================

@dataclass
class DocumentRequest:
    """
    A request to generate one document.
    Assembles all inputs before calling the generation engine.
    """
    request_id:         str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id:         str = ""
    user_id:            str = ""
    document_type:      DocumentType = DocumentType.EXECUTIVE_SUMMARY
    style:              DocumentStyle = DocumentStyle.STANDARD
    audience:           DocumentAudience = DocumentAudience.INVESTORS
    export_format:      ExportFormat = ExportFormat.PDF
    investor_mode:      bool = False    # adds risk scoring + recommendation page
    startup_data:       Dict[str, Any] = field(default_factory=dict)
    analysis_results:   Dict[str, Any] = field(default_factory=dict)
    created_at:         datetime = field(default_factory=datetime.utcnow)


@dataclass
class GeneratedDocument:
    """
    The output of a successful document generation.
    Stored in generated_documents DB table.
    """
    document_id:        str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id:         str = ""
    user_id:            str = ""
    document_type:      DocumentType = DocumentType.EXECUTIVE_SUMMARY
    style:              DocumentStyle = DocumentStyle.STANDARD
    audience:           DocumentAudience = DocumentAudience.INVESTORS
    title:              str = ""
    content:            str = ""         # full AI-generated document text
    structured_output:  Dict[str, Any] = field(default_factory=dict)  # parsed sections
    word_count:         int = 0
    page_estimate:      int = 0
    investor_mode:      bool = False
    export_urls:        Dict[str, str] = field(default_factory=dict)  # format -> url
    shareable_link:     Optional[str] = None
    credits_consumed:   int = 0
    model_used:         str = ""
    generated_at:       datetime = field(default_factory=datetime.utcnow)


@dataclass
class DocumentTemplate:
    """
    A versioned document template stored in document_templates DB table.
    Templates define the structure and prompt for each document type.
    """
    template_id:        str = field(default_factory=lambda: str(uuid.uuid4()))
    document_type:      DocumentType = DocumentType.EXECUTIVE_SUMMARY
    audience:           DocumentAudience = DocumentAudience.INVESTORS
    style:              DocumentStyle = DocumentStyle.STANDARD
    version:            int = 1
    system_prompt:      str = ""
    section_schema:     List[str] = field(default_factory=list)
    estimated_pages:    Dict[str, int] = field(default_factory=dict)  # style -> pages
    is_active:          bool = True
    created_at:         datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# MASTER DOCUMENT GENERATION PROMPT ENGINE
# ============================================================================

class DocumentPromptEngine:
    """
    Manages all document generation prompts as versioned assets.

    Every document type has:
      - A system prompt defining the AI's role
      - A section schema defining required sections
      - Style modifiers (concise / standard / detailed)
      - Audience modifiers (founder / investor / accelerator)

    The Master Prompt is assembled from:
      1. System role definition
      2. Startup data injection
      3. Analysis results injection
      4. Document type template
      5. Style modifier
      6. Audience modifier
      7. Format specification
    """

    # ── SYSTEM ROLE ────────────────────────────────────────────────────────

    MASTER_SYSTEM_PROMPT = """You are the TechIT Document Generation Engine.

Your role is to convert startup analysis into structured, professional,
investor-grade documents.

INPUTS AVAILABLE:
  - Structured startup data (name, problem, solution, market, team, traction)
  - Unicorn analysis results (10 drivers, UPS score, classification)
  - Strategy outputs (GTM, pricing, growth path)
  - Market insights (TAM/SAM/SOM, competition)
  - Financial signals (MRR, revenue model, unit economics)
  - User-selected document type, target audience, and level of detail

GENERAL RULES:
  - Output must be clear, structured, and professional
  - Use headings and numbered sections
  - Avoid fluff -- focus on clarity and density
  - Adapt tone to target audience
  - Use bullet points where they aid clarity
  - Ensure logical flow from problem -> solution -> market -> execution
  - Every claim must be grounded in the input data provided
  - Do not invent metrics not present in the inputs
  - Use quantitative language wherever possible
"""

    # ── DOCUMENT TYPE PROMPTS ──────────────────────────────────────────────

    TYPE_PROMPTS: Dict[DocumentType, str] = {

        DocumentType.EXECUTIVE_SUMMARY: """
DOCUMENT TYPE: Executive Summary (1–2 pages)

Generate a concise, high-density executive summary covering:

1. COMPANY OVERVIEW
   Company name, one-line description, founding stage

2. THE PROBLEM
   What problem exists? Who suffers? How severe? Current failed solutions?

3. THE SOLUTION
   What does the product/service do? Core value proposition.

4. MARKET OPPORTUNITY
   TAM / SAM / SOM with clear assumptions. Why now?

5. BUSINESS MODEL
   How does revenue work? Key revenue streams. Unit economics summary.

6. COMPETITIVE ADVANTAGE
   What makes this defensible? Moat, unique insight, timing.

7. TRACTION (if available)
   Users, revenue, partnerships, pilot results.

8. VISION
   Where is this in 5 years? Market position target.

Tone: Authoritative, data-dense, zero fluff.
Length: 1 page (Concise), 1.5 pages (Standard), 2 pages (Detailed).
""",

        DocumentType.BUSINESS_PLAN: """
DOCUMENT TYPE: Full Business Plan (10–25 pages)

Generate a comprehensive business plan with these sections:

1. COMPANY OVERVIEW
   Vision, mission, founding story, legal entity, location.

2. PROBLEM STATEMENT
   Problem depth analysis, root causes, who is affected, evidence of the problem.

3. SOLUTION
   Product/service description, how it works, key features, IP/technology.

4. MARKET ANALYSIS
   Industry overview, TAM/SAM/SOM breakdown with sources, market trends,
   customer segmentation, target demographic profiles.

5. COMPETITIVE LANDSCAPE
   Direct and indirect competitors, competitive matrix, differentiators, moat.

6. PRODUCT STRATEGY
   Product roadmap, feature prioritisation, development methodology.

7. BUSINESS MODEL
   Revenue streams, pricing strategy, unit economics (CAC, LTV, payback period),
   gross margin targets.

8. GO-TO-MARKET STRATEGY
   Acquisition channels, marketing strategy, sales process, partnerships.

9. FINANCIAL PROJECTIONS
   Year 1–3 revenue forecast, cost structure, break-even analysis,
   key financial assumptions.

10. OPERATIONS PLAN
    Team structure, hiring plan, key processes, technology stack.

11. GROWTH STRATEGY
    Expansion phases, geographic markets, product line extensions.

12. RISK ANALYSIS
    Top 5 risks with mitigation strategies.

13. FUNDING ASK (if applicable)
    Amount sought, use of funds breakdown, milestones unlocked.

Format: Numbered sections, professional tone, data-backed assertions.
Length: 10 pages (Concise), 18 pages (Standard), 25 pages (Detailed).
""",

        DocumentType.PITCH_DECK: """
DOCUMENT TYPE: Pitch Deck (Slide Structure)

Format the output as a structured slide-by-slide outline.
Each slide should have: TITLE, KEY POINTS (3–5 bullets), VISUALS SUGGESTED.

SLIDE 1 -- COVER
  Company name, tagline, presenter, date

SLIDE 2 -- PROBLEM
  Pain point, who suffers, scale, failed alternatives

SLIDE 3 -- SOLUTION
  Product/service, how it works, core value prop

SLIDE 4 -- MARKET OPPORTUNITY
  TAM/SAM/SOM, why the timing is right

SLIDE 5 -- PRODUCT
  Key features, demo screenshot description, tech differentiator

SLIDE 6 -- TRACTION
  Users, revenue, growth rate, key milestones, retention

SLIDE 7 -- BUSINESS MODEL
  Revenue streams, pricing, unit economics

SLIDE 8 -- GO-TO-MARKET
  Acquisition strategy, channels, early partnerships

SLIDE 9 -- COMPETITION
  Competitive matrix, our position, unfair advantage

SLIDE 10 -- TEAM
  Founders and key hires, relevant expertise, advisors

SLIDE 11 -- FINANCIAL PROJECTIONS
  3-year revenue forecast, key assumptions, path to profitability

SLIDE 12 -- THE ASK
  Funding amount, use of funds, milestones to next round, vision

Output format:
--- SLIDE N: [TITLE] ---
HEADLINE: [one compelling sentence]
KEY POINTS:
  • ...
VISUAL: [suggested chart/image type]
""",

        DocumentType.INVESTOR_REPORT: """
DOCUMENT TYPE: Investor Report (Deep Analysis)

Generate an institutional-grade investor analysis report:

1. EXECUTIVE BRIEF
   One-page investment thesis summary.

2. UNICORN POTENTIAL ASSESSMENT
   Unicorn score breakdown (all 10 drivers), classification tier,
   benchmark comparison, probability commentary.

3. MARKET OPPORTUNITY ANALYSIS
   TAM/SAM/SOM with sizing methodology. Market growth rate.
   Timing and macro tailwinds. Customer demand evidence.

4. COMPETITIVE MOAT ANALYSIS
   Differentiation depth, switching costs, network effects, IP.

5. EXECUTION VELOCITY ASSESSMENT
   EVI-I signal interpretation: MDR, iteration speed, team responsiveness,
   revenue traction, user growth, capital efficiency.

6. RISK ANALYSIS
   Market risk, technical risk, team risk, regulatory risk, competitive risk.
   Each rated Low / Medium / High with mitigation commentary.

7. FINANCIAL SIGNAL ANALYSIS
   Revenue trajectory, burn rate, runway, unit economics quality,
   capital efficiency score.

8. INVESTMENT SIGNALS
   Bull case, bear case, key assumptions, deal breakers.

9. INVESTMENT RECOMMENDATION
   Proceed / Watch / Pass -- with rationale.
   Suggested valuation range (if data permits).
   Key diligence questions.

Tone: Institutional, objective, evidence-based.
""",

        DocumentType.UNICORN_ANALYSIS_REPORT: """
DOCUMENT TYPE: Unicorn Analysis Report (TechIT Proprietary)

Generate the full TechIT Unicorn Probability Report:

1. UNICORN PROBABILITY SCORE (UPS)
   Overall score (0–100%) with classification tier.
   Tier: Unicorn Candidate / High Potential / Early Traction / Pre-Aha / Idea Stage.

2. THE 10 UNICORN DRIVER BREAKDOWN
   For each of the 10 drivers, provide:
   -- Driver name and weight
   -- Score (0–10) with explanation
   -- What would improve this score
   Drivers:
   1. Market Size (15%)           6. Network Effects (10%)
   2. Problem Severity (12%)      7. Revenue Model Strength (10%)
   3. Founder Advantage (10%)     8. Market Timing (8%)
   4. Technological Moat (12%)    9. Competition Landscape (6%)
   5. Scalability (12%)          10. Capital Efficiency (5%)

3. DILEEP RAO BENCHMARK ANALYSIS
   4-dimension RAG assessment:
   -- Market scale (Red / Amber / Green)
   -- Founder skill (Red / Amber / Green)
   -- Financing (Red / Amber / Green)
   -- Venture stage (Red / Amber / Green)

4. COMPARATIVE BENCHMARKING
   How does this venture compare to typical companies at this stage?
   Notable patterns or anomalies.

5. STRATEGIC INSIGHTS
   Top 3 strengths to leverage.
   Top 3 gaps to close.
   Priority actions for next 90 days.

6. PATH TO UNICORN
   What would need to be true for this to reach $1B valuation?
   Key inflection points and milestones.
""",

        DocumentType.PRODUCT_ROADMAP: """
DOCUMENT TYPE: Product Roadmap Document

Generate a structured product roadmap:

1. PRODUCT VISION
   Where the product is going in 3 years. North Star metric.

2. CURRENT STATE
   What exists today. What users can do. Known limitations.

3. PHASE 1 -- MVP (Month 1–3)
   Core features to validate the hypothesis.
   Success criteria. Key milestones.

4. PHASE 2 -- BETA (Month 3–6)
   Feature extensions based on user feedback.
   Performance improvements. Onboarding optimisation.
   Success criteria.

5. PHASE 3 -- LAUNCH (Month 6–12)
   Public launch features. Scale infrastructure.
   Monetisation activation. Key partnerships.
   Success criteria.

6. PHASE 4 -- SCALE (Month 12–24)
   Expansion features. New markets. Enterprise tier.
   Platform / ecosystem plays.
   Success criteria.

7. TECHNICAL MILESTONES
   Key engineering deliverables aligned to phases.

8. RESOURCE REQUIREMENTS
   Team, budget, and external dependencies per phase.

Format: Timeline-oriented, milestone-anchored.
""",

        DocumentType.FINANCIAL_PROJECTION: """
DOCUMENT TYPE: Financial Projection Document

Generate a structured financial projection:

1. REVENUE MODEL OVERVIEW
   Revenue streams, pricing tiers, billing frequency.
   Key assumptions driving projections.

2. YEAR 1 PROJECTION (Monthly)
   Month-by-month: Users, Revenue, COGS, Gross Profit, Operating Costs, Net.
   Highlight: break-even month if applicable.

3. YEAR 2–3 PROJECTION (Quarterly)
   Quarterly summary: Revenue, Growth Rate, Headcount, Burn.

4. UNIT ECONOMICS
   CAC by channel, LTV, LTV:CAC ratio, payback period, gross margin.

5. COST STRUCTURE
   Fixed vs variable costs. Team costs (hiring plan).
   Technology + infrastructure costs. Marketing budget.

6. FUNDING REQUIREMENTS
   Total capital required, by phase.
   What each funding round unlocks.
   Milestones required to raise next round.

7. SENSITIVITY ANALYSIS
   Bull / Base / Bear case revenue scenarios.
   Key variables and their impact.

8. PATH TO PROFITABILITY
   When does the business reach gross margin positive?
   When does it reach EBITDA positive?

Note all projections are forward-looking estimates based on stated assumptions.
""",

        DocumentType.MARKET_RESEARCH_REPORT: """
DOCUMENT TYPE: Market Research Report

Generate a comprehensive market research document:

1. INDUSTRY OVERVIEW
   Industry description, history, current state.
   Key players and market dynamics.

2. MARKET SIZE
   TAM (Total Addressable Market) -- global potential.
   SAM (Serviceable Addressable Market) -- realistic reach.
   SOM (Serviceable Obtainable Market) -- achievable in 3 years.
   Methodology and data sources.

3. MARKET TRENDS
   Top 5 macro trends shaping the market.
   Emerging technologies. Regulatory changes. Social shifts.

4. CUSTOMER SEGMENTATION
   Primary customer segments with profiles.
   Segment size, willingness to pay, acquisition difficulty.
   Unmet needs per segment.

5. COMPETITOR LANDSCAPE
   Direct competitors -- features, pricing, market share.
   Indirect competitors -- alternative solutions.
   Competitive matrix (feature comparison).
   Our differentiation and positioning.

6. MARKET TIMING ANALYSIS
   Why now? What has changed in the last 2 years?
   Catalysts and tailwinds.

7. GEOGRAPHIC ANALYSIS
   Primary market. Expansion markets. Global opportunity map.

8. ENTRY BARRIERS & RISKS
   What makes this market hard to enter?
   What could go wrong?

Format: Data-first, citation-conscious, visual-suggestion included.
""",
    }

    # ── STYLE MODIFIERS ────────────────────────────────────────────────────

    STYLE_MODIFIERS: Dict[DocumentStyle, str] = {
        DocumentStyle.CONCISE:  "\nSTYLE: CONCISE -- Be maximally dense. Cut every non-essential sentence. Prioritise data over narrative.",
        DocumentStyle.STANDARD: "\nSTYLE: STANDARD -- Balance depth with readability. Use clear structure. One key insight per section.",
        DocumentStyle.DETAILED: "\nSTYLE: DETAILED -- Maximum depth. Expand all analysis. Include sub-sections. Support every claim with reasoning.",
    }

    # ── AUDIENCE MODIFIERS ─────────────────────────────────────────────────

    AUDIENCE_MODIFIERS: Dict[DocumentAudience, str] = {
        DocumentAudience.FOUNDER_USE:   "\nAUDIENCE: FOUNDER -- Internal operations focus. Be direct and actionable. Highlight risks honestly.",
        DocumentAudience.INVESTORS:     "\nAUDIENCE: INVESTORS -- Lead with market size and defensibility. Quantify everything. Anticipate due diligence questions.",
        DocumentAudience.ACCELERATORS:  "\nAUDIENCE: ACCELERATORS -- Emphasise founder capability, learning velocity, and traction quality.",
    }

    # ── INVESTOR MODE ADDITION ─────────────────────────────────────────────

    INVESTOR_MODE_ADDITION = """
INVESTOR MODE ENABLED -- Add these sections at the end:

INVESTOR SUMMARY PAGE:
  • Investment opportunity in one sentence
  • Risk rating: Low / Medium / High
  • Recommended diligence areas
  • Key questions to ask the founder

RISK SCORING:
  Rate each risk area 1–5:
  • Market risk:        [score] -- [rationale]
  • Execution risk:     [score] -- [rationale]
  • Technical risk:     [score] -- [rationale]
  • Competitive risk:   [score] -- [rationale]
  • Regulatory risk:    [score] -- [rationale]

RECOMMENDATION:
  Proceed / Watch / Pass -- with one paragraph rationale.
"""

    def build_prompt(
        self,
        request:         DocumentRequest,
        startup_context: str,
    ) -> str:
        """
        Assemble the full generation prompt for one document request.

        Components:
          1. Master system role
          2. Document type template
          3. Style modifier
          4. Audience modifier
          5. Startup data injection
          6. Investor mode addition (optional)
          7. Format specification
        """
        type_prompt     = self.TYPE_PROMPTS.get(request.document_type, "")
        style_mod       = self.STYLE_MODIFIERS.get(request.style, "")
        audience_mod    = self.AUDIENCE_MODIFIERS.get(request.audience, "")
        investor_add    = self.INVESTOR_MODE_ADDITION if request.investor_mode else ""

        return (
            f"{self.MASTER_SYSTEM_PROMPT}\n"
            f"{type_prompt}\n"
            f"{style_mod}\n"
            f"{audience_mod}\n"
            f"{investor_add}\n"
            f"STARTUP DATA:\n{startup_context}\n\n"
            f"ANALYSIS RESULTS:\n{str(request.analysis_results)[:3000]}\n\n"
            f"OUTPUT: Generate the {request.document_type.value.replace('_', ' ').title()} now. "
            f"Use professional formatting. Ensure all sections are complete and data-grounded."
        )

    def get_section_schema(self, doc_type: DocumentType) -> List[str]:
        """Return the expected sections for a document type (for structured parsing)."""
        schema_map = {
            DocumentType.EXECUTIVE_SUMMARY:       ["company_overview","problem","solution","market_opportunity","business_model","competitive_advantage","traction","vision"],
            DocumentType.BUSINESS_PLAN:           ["company_overview","problem","solution","market_analysis","competitive_landscape","product_strategy","business_model","go_to_market","financial_projections","operations","growth_strategy","risk_analysis","funding_ask"],
            DocumentType.PITCH_DECK:              ["cover","problem","solution","market","product","traction","business_model","go_to_market","competition","team","financials","ask"],
            DocumentType.INVESTOR_REPORT:         ["executive_brief","unicorn_assessment","market_analysis","competitive_moat","execution_velocity","risk_analysis","financial_signals","investment_signals","recommendation"],
            DocumentType.UNICORN_ANALYSIS_REPORT: ["ups_score","driver_breakdown","dileep_rao_benchmark","benchmarking","strategic_insights","path_to_unicorn"],
            DocumentType.PRODUCT_ROADMAP:         ["vision","current_state","phase_1_mvp","phase_2_beta","phase_3_launch","phase_4_scale","technical_milestones","resources"],
            DocumentType.FINANCIAL_PROJECTION:    ["revenue_model","year_1_monthly","year_2_3_quarterly","unit_economics","cost_structure","funding_requirements","sensitivity","path_to_profitability"],
            DocumentType.MARKET_RESEARCH_REPORT:  ["industry_overview","market_size","trends","customer_segmentation","competitor_landscape","timing","geography","entry_barriers"],
        }
        return schema_map.get(doc_type, [])

    def estimate_pages(self, doc_type: DocumentType, style: DocumentStyle) -> int:
        """Estimate page count for a document by type and style."""
        page_map = {
            DocumentType.EXECUTIVE_SUMMARY:       {DocumentStyle.CONCISE: 1, DocumentStyle.STANDARD: 2, DocumentStyle.DETAILED: 2},
            DocumentType.BUSINESS_PLAN:           {DocumentStyle.CONCISE: 10, DocumentStyle.STANDARD: 18, DocumentStyle.DETAILED: 25},
            DocumentType.PITCH_DECK:              {DocumentStyle.CONCISE: 10, DocumentStyle.STANDARD: 12, DocumentStyle.DETAILED: 15},
            DocumentType.INVESTOR_REPORT:         {DocumentStyle.CONCISE: 5, DocumentStyle.STANDARD: 8, DocumentStyle.DETAILED: 12},
            DocumentType.UNICORN_ANALYSIS_REPORT: {DocumentStyle.CONCISE: 4, DocumentStyle.STANDARD: 7, DocumentStyle.DETAILED: 10},
            DocumentType.PRODUCT_ROADMAP:         {DocumentStyle.CONCISE: 3, DocumentStyle.STANDARD: 5, DocumentStyle.DETAILED: 8},
            DocumentType.FINANCIAL_PROJECTION:    {DocumentStyle.CONCISE: 3, DocumentStyle.STANDARD: 5, DocumentStyle.DETAILED: 8},
            DocumentType.MARKET_RESEARCH_REPORT:  {DocumentStyle.CONCISE: 5, DocumentStyle.STANDARD: 8, DocumentStyle.DETAILED: 12},
        }
        return page_map.get(doc_type, {}).get(style, 5)


# ============================================================================
# EXPORT SERVICE
# ============================================================================

class ExportService:
    """
    Handles all export and sharing operations for generated documents.

    Export Options:
      - PDF (via WeasyPrint or reportlab in production)
      - Notion Doc (via Notion API)
      - Google Doc (via Google Drive API)
      - Slide Deck (for pitch decks, via python-pptx)

    Share Options:
      - Shareable link (public URL with optional expiry)
      - "Edit with AI" button (re-opens in generation interface)

    Investor Mode:
      When enabled, adds:
        • Investor summary page
        • Risk scoring table
        • Recommendation section
    """

    def generate_shareable_link(
        self, document_id: str, expiry_days: Optional[int] = 30
    ) -> str:
        """
        Generate a time-limited shareable link for a document.
        Production: store in document_exports table with signed URL.
        """
        return f"https://app.techit.io/documents/share/{document_id}?expires={expiry_days}d"

    def export_to_pdf(
        self, document: GeneratedDocument
    ) -> Dict[str, Any]:
        """
        Convert document content to PDF.
        Production: use WeasyPrint or reportlab with TechIT brand template.
        Returns S3 URL of the generated PDF.
        """
        # Production: convert document.content -> PDF -> upload to S3
        pdf_url = f"https://cdn.techit.io/documents/{document.document_id}/export.pdf"
        return {
            "format":       "pdf",
            "url":          pdf_url,
            "file_size_kb": round(document.word_count * 0.008, 1),  # rough estimate
            "pages":        document.page_estimate,
            "ready":        True,
        }

    def export_to_notion(
        self, document: GeneratedDocument, notion_token: str
    ) -> Dict[str, Any]:
        """
        Create a Notion page from the generated document.
        Production: call Notion API pages.create endpoint.
        """
        notion_url = f"https://notion.so/techit-documents/{document.document_id}"
        return {
            "format":     "notion_doc",
            "url":        notion_url,
            "page_id":    document.document_id,
            "ready":      True,
        }

    def export_to_google_doc(
        self, document: GeneratedDocument, google_token: str
    ) -> Dict[str, Any]:
        """
        Create a Google Doc from the generated document.
        Production: call Google Drive API documents.create endpoint.
        """
        gdoc_url = f"https://docs.google.com/document/d/{document.document_id}/edit"
        return {
            "format": "google_doc",
            "url":    gdoc_url,
            "ready":  True,
        }

    def export_pitch_deck(
        self, document: GeneratedDocument
    ) -> Dict[str, Any]:
        """
        Convert pitch deck structure to PowerPoint / Google Slides.
        Production: use python-pptx with TechIT brand template.
        """
        deck_url = f"https://cdn.techit.io/documents/{document.document_id}/pitch_deck.pptx"
        return {
            "format": "slide_deck",
            "url":    deck_url,
            "slides": document.structured_output.get("slide_count", 12),
            "ready":  True,
        }

    def build_export_manifest(
        self,
        document:       GeneratedDocument,
        requested_format: ExportFormat,
        notion_token:   Optional[str] = None,
        google_token:   Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build the complete export result for a document.
        Returns all available export URLs and the shareable link.
        """
        share_link = self.generate_shareable_link(document.document_id)
        exports: Dict[str, Any] = {"shareable_link": share_link}

        if requested_format == ExportFormat.PDF or document.document_type != DocumentType.PITCH_DECK:
            exports["pdf"] = self.export_to_pdf(document)

        if requested_format == ExportFormat.SLIDE_DECK and document.document_type == DocumentType.PITCH_DECK:
            exports["slide_deck"] = self.export_pitch_deck(document)

        if requested_format == ExportFormat.NOTION_DOC and notion_token:
            exports["notion"] = self.export_to_notion(document, notion_token)

        if requested_format == ExportFormat.GOOGLE_DOC and google_token:
            exports["google_doc"] = self.export_to_google_doc(document, google_token)

        exports["edit_with_ai_url"] = f"https://app.techit.io/documents/{document.document_id}/edit"

        return exports


# ============================================================================
# DOCUMENT GENERATION ENGINE
# ============================================================================

class DocumentGenerationEngine:
    """
    Master orchestrator for all document generation.

    Flow:
      1. Pull startup data from project record
      2. Pull analysis results (unicorn eval, market intel, strategy)
      3. Select document template
      4. Assemble master prompt
      5. Call AI (via ai_router_core.AICommandLayer)
      6. Parse structured output
      7. Count words and estimate pages
      8. Generate exports
      9. Store in generated_documents table
     10. Return preview + download options
    """

    def __init__(self) -> None:
        self.prompt_engine = DocumentPromptEngine()
        self.export_service = ExportService()

    def build_startup_context(
        self, startup_data: Dict[str, Any], analysis_results: Dict[str, Any]
    ) -> str:
        """
        Assemble startup data and analysis results into a clean context string.
        This is the core data injection for every document.
        """
        lines = ["=== STARTUP DATA ==="]

        # Core identity
        for key in ["startup_name","industry","problem","solution","target_customers",
                    "revenue_model","market_size","traction","tech_stack","location"]:
            if startup_data.get(key):
                lines.append(f"{key.upper()}: {startup_data[key]}")

        # Team
        if startup_data.get("team"):
            lines.append(f"TEAM: {startup_data['team']}")

        lines.append("\n=== ANALYSIS RESULTS ===")

        # Unicorn / scoring
        if analysis_results.get("unicorn_potential_score"):
            lines.append(f"UNICORN POTENTIAL SCORE: {analysis_results['unicorn_potential_score']}%")
        if analysis_results.get("unicorn_classification"):
            lines.append(f"UNICORN CLASSIFICATION: {analysis_results['unicorn_classification']}")
        if analysis_results.get("gsis_score"):
            lines.append(f"GSIS SCORE: {analysis_results['gsis_score']}")
        if analysis_results.get("evi_i_adjusted"):
            lines.append(f"EVI-I INVESTOR SIGNAL: {analysis_results['evi_i_adjusted']}")
        if analysis_results.get("investment_score"):
            lines.append(f"INVESTMENT SCORE: {analysis_results['investment_score']}")

        # Market
        if analysis_results.get("tam"):
            lines.append(f"TAM: {analysis_results['tam']}")
        if analysis_results.get("market_analysis"):
            lines.append(f"MARKET INSIGHTS: {str(analysis_results['market_analysis'])[:500]}")

        # Strategy
        if analysis_results.get("startup_strategy"):
            lines.append(f"STRATEGY: {str(analysis_results['startup_strategy'])[:500]}")

        # Financials
        if analysis_results.get("mrr"):
            lines.append(f"MRR: ${analysis_results['mrr']:,.0f}")
        if analysis_results.get("burn_rate"):
            lines.append(f"MONTHLY BURN: ${analysis_results['burn_rate']:,.0f}")

        return "\n".join(lines)

    def parse_structured_output(
        self, content: str, doc_type: DocumentType
    ) -> Dict[str, Any]:
        """
        Parse the raw AI output into a structured dict keyed by section names.
        Production: use more sophisticated section detection.
        """
        schema    = self.prompt_engine.get_section_schema(doc_type)
        sections: Dict[str, str] = {}
        current   = "intro"
        buffer    = []

        for line in content.split("\n"):
            matched = False
            for section in schema:
                label = section.replace("_", " ").upper()
                if label in line.upper():
                    if buffer:
                        sections[current] = "\n".join(buffer).strip()
                    current = section
                    buffer  = [line]
                    matched = True
                    break
            if not matched:
                buffer.append(line)

        if buffer:
            sections[current] = "\n".join(buffer).strip()

        return {
            "sections":    sections,
            "section_count": len(sections),
            "slide_count": len([k for k in sections if k.startswith("slide_")]) or 12,
        }

    def estimate_word_count(self, content: str) -> int:
        return len(content.split())


# ============================================================================
# DOCUMENT GENERATION SERVICE (INTEGRATION LAYER)
# ============================================================================

class DocumentGenerationService:
    """
    Service layer connecting the Document Generation Engine to the TechIT platform.
    Integrates with TechITAIBrain for all AI calls.

    AI calls use TaskTypes from ai_router_core.py:
      DOCUMENT_EXECUTIVE_SUMMARY   DOCUMENT_BUSINESS_PLAN
      DOCUMENT_PITCH_DECK          DOCUMENT_INVESTOR_REPORT
      DOCUMENT_UNICORN_REPORT      DOCUMENT_PRODUCT_ROADMAP
      DOCUMENT_FINANCIAL_PROJECTION DOCUMENT_MARKET_RESEARCH

    Credit costs per document type:
      Executive Summary          -> 2 credits   (Builder+)
      Full Business Plan         -> 4 credits   (Investor+)
      Pitch Deck                 -> 3 credits   (Founder Pro+)
      Investor Report            -> 3 credits   (Investor+)
      Unicorn Analysis Report    -> 2 credits   (Builder+)
      Product Roadmap            -> 2 credits   (Founder Pro+)
      Financial Projection       -> 2 credits   (Founder Pro+)
      Market Research Report     -> 3 credits   (Founder Pro+)

    API Endpoints served
    ─────────────────────
      POST /api/v1/documents/generate                3–4 credits  Founder Pro+
      GET  /api/v1/documents/{document_id}           0 credits    Free+
      GET  /api/v1/documents/project/{project_id}    0 credits    Free+
      POST /api/v1/documents/{document_id}/export    0 credits    Free+
      GET  /api/v1/documents/{document_id}/preview   0 credits    Free+
      POST /api/v1/documents/{document_id}/edit      2 credits    Builder+
      DELETE /api/v1/documents/{document_id}         0 credits    Free+
      GET  /api/v1/documents/templates               0 credits    Free+
      POST /api/v1/documents/batch                   8 credits    Investor+
      POST /api/v1/documents/{document_id}/share     0 credits    Free+
    """

    # Map DocumentType -> TaskType string (resolved in ai_router_core.py)
    TASK_TYPE_MAP: Dict[DocumentType, str] = {
        DocumentType.EXECUTIVE_SUMMARY:       "document_executive_summary",
        DocumentType.BUSINESS_PLAN:           "document_business_plan",
        DocumentType.PITCH_DECK:              "document_pitch_deck",
        DocumentType.INVESTOR_REPORT:         "document_investor_report",
        DocumentType.UNICORN_ANALYSIS_REPORT: "document_unicorn_report",
        DocumentType.PRODUCT_ROADMAP:         "document_product_roadmap",
        DocumentType.FINANCIAL_PROJECTION:    "document_financial_projection",
        DocumentType.MARKET_RESEARCH_REPORT:  "document_market_research",
    }

    CREDIT_COSTS: Dict[DocumentType, int] = {
        DocumentType.EXECUTIVE_SUMMARY:       2,
        DocumentType.BUSINESS_PLAN:           4,
        DocumentType.PITCH_DECK:              3,
        DocumentType.INVESTOR_REPORT:         3,
        DocumentType.UNICORN_ANALYSIS_REPORT: 2,
        DocumentType.PRODUCT_ROADMAP:         2,
        DocumentType.FINANCIAL_PROJECTION:    2,
        DocumentType.MARKET_RESEARCH_REPORT:  3,
    }

    def __init__(self, brain) -> None:
        self.brain         = brain
        self.gen_engine    = DocumentGenerationEngine()
        self.export_svc    = ExportService()

    async def generate_document(
        self,
        user_context,
        project_id:       str,
        document_type:    str,
        style:            str            = "standard",
        audience:         str            = "investors",
        export_format:    str            = "pdf",
        investor_mode:    bool           = False,
        startup_data:     Optional[Dict] = None,
        analysis_results: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/documents/generate

        Master generation endpoint.
        Pulls startup data and analysis, generates the document,
        and returns a preview + all export options.
        """
        from ai_router_core import AIRequest, TaskType

        dt  = DocumentType(document_type) if document_type in [e.value for e in DocumentType] else DocumentType.EXECUTIVE_SUMMARY
        sty = DocumentStyle(style) if style in [e.value for e in DocumentStyle] else DocumentStyle.STANDARD
        aud = DocumentAudience(audience) if audience in [e.value for e in DocumentAudience] else DocumentAudience.INVESTORS
        ef  = ExportFormat(export_format) if export_format in [e.value for e in ExportFormat] else ExportFormat.PDF

        startup  = startup_data or {}
        analysis = analysis_results or {}

        # Build context and prompt
        context = self.gen_engine.build_startup_context(startup, analysis)
        req     = DocumentRequest(
            project_id=project_id, user_id=user_context.user_id,
            document_type=dt, style=sty, audience=aud,
            export_format=ef, investor_mode=investor_mode,
            startup_data=startup, analysis_results=analysis,
        )
        prompt  = self.gen_engine.prompt_engine.build_prompt(req, context)

        # Resolve TaskType from ai_router_core
        task_type_str = self.TASK_TYPE_MAP.get(dt, "document_executive_summary")
        task_type     = TaskType[task_type_str.upper().replace("-", "_")] if hasattr(TaskType, task_type_str.upper().replace("-", "_")) else TaskType.EXECUTIVE_SUMMARY

        # AI call -- long-form generation uses Claude Sonnet
        max_tokens_map = {
            DocumentType.EXECUTIVE_SUMMARY:       2000,
            DocumentType.BUSINESS_PLAN:           8000,
            DocumentType.PITCH_DECK:              5000,
            DocumentType.INVESTOR_REPORT:         5000,
            DocumentType.UNICORN_ANALYSIS_REPORT: 4000,
            DocumentType.PRODUCT_ROADMAP:         4000,
            DocumentType.FINANCIAL_PROJECTION:    4000,
            DocumentType.MARKET_RESEARCH_REPORT:  5000,
        }

        ai_resp = await self.brain.process(AIRequest(
            task_type=task_type,
            user_context=user_context,
            input_data={"startup_context": context, "prompt_override": prompt,
                        "document_type": document_type, "style": style,
                        "audience": audience, "investor_mode": investor_mode},
            max_tokens=max_tokens_map.get(dt, 4000),
            ip_protected=True,
        ))

        # Build document object
        word_count = self.gen_engine.estimate_word_count(ai_resp.output)
        pages      = self.gen_engine.prompt_engine.estimate_pages(dt, sty)
        structured = self.gen_engine.parse_structured_output(ai_resp.output, dt)

        doc = GeneratedDocument(
            project_id=project_id, user_id=user_context.user_id,
            document_type=dt, style=sty, audience=aud,
            title=f"{startup.get('startup_name', 'TechIT')} -- {dt.value.replace('_', ' ').title()}",
            content=ai_resp.output,
            structured_output=structured,
            word_count=word_count, page_estimate=pages,
            investor_mode=investor_mode,
            credits_consumed=ai_resp.credits_consumed,
            model_used=ai_resp.model_used,
        )

        # Build exports
        exports = self.export_svc.build_export_manifest(doc, ef)
        doc.export_urls    = {k: v.get("url", "") for k, v in exports.items() if isinstance(v, dict)}
        doc.shareable_link = exports.get("shareable_link", "")

        preview = ai_resp.output[:1500] + ("..." if len(ai_resp.output) > 1500 else "")

        return {
            "document_id":       doc.document_id,
            "title":             doc.title,
            "document_type":     dt.value,
            "style":             sty.value,
            "audience":          aud.value,
            "word_count":        word_count,
            "page_estimate":     pages,
            "preview":           preview,
            "content":           ai_resp.output,
            "sections":          structured["sections"],
            "exports":           exports,
            "shareable_link":    doc.shareable_link,
            "edit_with_ai_url":  exports.get("edit_with_ai_url", ""),
            "credits_consumed":  ai_resp.credits_consumed,
            "model_used":        ai_resp.model_used,
            "investor_mode":     investor_mode,
            "generated_at":      doc.generated_at.isoformat(),
        }

    async def generate_batch(
        self,
        user_context,
        project_id:       str,
        document_types:   List[str],
        style:            str = "standard",
        audience:         str = "investors",
        startup_data:     Optional[Dict] = None,
        analysis_results: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/documents/batch -- 8 credits, Investor+

        Generate multiple documents in one call.
        Useful for investor pack preparation (exec summary + pitch deck + financials).
        """
        results = []
        total_credits = 0
        for doc_type in document_types:
            result = await self.generate_document(
                user_context=user_context, project_id=project_id,
                document_type=doc_type, style=style, audience=audience,
                startup_data=startup_data, analysis_results=analysis_results,
            )
            results.append(result)
            total_credits += result.get("credits_consumed", 0)

        return {
            "batch_id":        str(uuid.uuid4()),
            "document_count":  len(results),
            "documents":       results,
            "total_credits":   total_credits,
            "investor_pack_url": f"https://app.techit.io/documents/pack/{project_id}",
        }

    async def edit_with_ai(
        self, user_context, document_id: str,
        current_content: str, edit_instruction: str,
        section: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/documents/{document_id}/edit -- 2 credits, Builder+

        AI-powered in-document editing.
        User highlights a section and gives an instruction:
          "Make this more concise"
          "Add more financial detail here"
          "Rewrite for a US investor audience"
        """
        from ai_router_core import AIRequest, TaskType

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.DOCUMENT_EXECUTIVE_SUMMARY,  # reuse lightweight task
            user_context=user_context,
            input_data={
                "mode":            "edit",
                "edit_instruction": edit_instruction,
                "section":         section or "full document",
                "current_content": current_content[:4000],
            },
            max_tokens=3000,
        ))

        return {
            "document_id":   document_id,
            "edited_content": resp.output,
            "section":       section or "full document",
            "instruction":   edit_instruction,
        }

    def get_available_templates(self) -> List[Dict[str, Any]]:
        """
        GET /api/v1/documents/templates -- 0 credits, Free+

        Return all available document types with metadata for the UI card grid.
        """
        return [
            {
                "document_type": dt.value,
                "display_name":  dt.value.replace("_", " ").title(),
                "icon":          icon,
                "description":   desc,
                "credit_cost":   self.CREDIT_COSTS[dt],
                "estimated_pages": {
                    "concise":  self.gen_engine.prompt_engine.estimate_pages(dt, DocumentStyle.CONCISE),
                    "standard": self.gen_engine.prompt_engine.estimate_pages(dt, DocumentStyle.STANDARD),
                    "detailed": self.gen_engine.prompt_engine.estimate_pages(dt, DocumentStyle.DETAILED),
                },
                "export_formats":  [ef.value for ef in ExportFormat],
                "investor_mode_supported": dt in [
                    DocumentType.INVESTOR_REPORT, DocumentType.BUSINESS_PLAN,
                    DocumentType.PITCH_DECK, DocumentType.UNICORN_ANALYSIS_REPORT,
                ],
            }
            for dt, icon, desc in [
                (DocumentType.EXECUTIVE_SUMMARY,       "🧾", "Concise 1–2 page investor-facing summary"),
                (DocumentType.BUSINESS_PLAN,           "📊", "Comprehensive 10–25 page business plan"),
                (DocumentType.PITCH_DECK,              "🎯", "Slide-by-slide pitch deck structure"),
                (DocumentType.INVESTOR_REPORT,         "📈", "Deep analysis with EVI-I and signals"),
                (DocumentType.UNICORN_ANALYSIS_REPORT, "🧠", "Full 10-driver unicorn breakdown"),
                (DocumentType.PRODUCT_ROADMAP,         "🛠", "MVP -> Beta -> Launch -> Scale timeline"),
                (DocumentType.FINANCIAL_PROJECTION,    "💰", "Revenue model, costs, and forecast"),
                (DocumentType.MARKET_RESEARCH_REPORT,  "🧪", "TAM/SAM/SOM, trends, competition"),
            ]
        ]

    async def share_document(
        self, user_context, document_id: str,
        expiry_days: Optional[int] = 30
    ) -> Dict[str, Any]:
        """
        POST /api/v1/documents/{document_id}/share -- 0 credits, Free+
        """
        link = self.export_svc.generate_shareable_link(document_id, expiry_days)
        return {
            "document_id":    document_id,
            "shareable_link": link,
            "expiry_days":    expiry_days,
            "can_edit":       False,
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def example_document_generation() -> None:
    """Demonstrates all 8 document types and the export system."""

    engine   = DocumentGenerationEngine()
    prompt_e = DocumentPromptEngine()
    export   = ExportService()

    startup = {
        "startup_name":    "MediConnect Africa",
        "industry":        "Healthtech",
        "problem":         "Rural patients in Sub-Saharan Africa cannot access specialist doctors",
        "solution":        "AI-powered telemedicine with real-time triage and remote diagnostics",
        "revenue_model":   "B2B SaaS -- hospitals pay per consultation minute",
        "market_size":     "$4.5B African digital health market by 2027",
        "team":            "CEO (former WHO), CTO (ex-Google Health), COO (Safaricom)",
        "traction":        "47 paying hospitals, $12,500 MRR, 820 active users",
        "mrr":             12500,
    }
    analysis = {
        "unicorn_potential_score": 81,
        "unicorn_classification":  "High Potential Startup",
        "gsis_score":              72.4,
        "evi_i_adjusted":          81.24,
        "investment_score":        78.5,
    }

    print("=" * 65)
    print("TECHIT -- DOCUMENT GENERATION ENGINE DEMO")
    print("=" * 65)

    templates = DocumentGenerationService.__new__(DocumentGenerationService)
    templates.gen_engine = engine
    available = [
        {
            "type":   dt.value,
            "pages":  prompt_e.estimate_pages(dt, DocumentStyle.STANDARD),
            "credits": {"executive_summary":2,"business_plan":4,"pitch_deck":3,
                         "investor_report":3,"unicorn_analysis_report":2,
                         "product_roadmap":2,"financial_projection":2,
                         "market_research_report":3}.get(dt.value, 2),
        }
        for dt in DocumentType
    ]

    for t in available:
        print(f"   📄 {t['type']:35s}  {t['pages']:2d} pages  {t['credits']} credits")

    # Test prompt assembly
    req = DocumentRequest(
        project_id="proj_001", user_id="founder_001",
        document_type=DocumentType.PITCH_DECK,
        style=DocumentStyle.STANDARD,
        audience=DocumentAudience.INVESTORS,
        investor_mode=True,
        startup_data=startup, analysis_results=analysis,
    )
    context = engine.build_startup_context(startup, analysis)
    prompt  = prompt_e.build_prompt(req, context)
    sections = prompt_e.get_section_schema(DocumentType.PITCH_DECK)
    pages    = prompt_e.estimate_pages(DocumentType.PITCH_DECK, DocumentStyle.STANDARD)

    print(f"\n📋 Pitch Deck (Standard, Investor Mode)")
    print(f"   Sections: {sections}")
    print(f"   Estimated: {pages} slides/pages")
    print(f"   Context length: {len(context)} chars")
    print(f"   Prompt length:  {len(prompt)} chars")

    # Shareable link
    link = export.generate_shareable_link("doc_001")
    print(f"\n🔗 Shareable link: {link}")

    print("\n" + "=" * 65)
    print("✅ Document Generation Engine demo complete")
    print("   8 document types  |  3 styles  |  3 audiences  |  4 export formats")
    print("=" * 65)


if __name__ == "__main__":
    example_document_generation()
