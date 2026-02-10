"""
Intelligence Hub Guide - AI Agent
==================================

Sales-focused AI agent that helps prospective users understand the platform.
Designed to showcase value without revealing technical implementation details.
"""

import logging
from typing import Optional
from anthropic import AsyncAnthropic

from app.config.settings import settings
from .guide_knowledge import get_full_knowledge_base

logger = logging.getLogger(__name__)

# =============================================================================
# SYSTEM PROMPT
# =============================================================================

GUIDE_SYSTEM_PROMPT = """You are the Intelligence Hub Guide, an AI assistant designed to help prospective users understand the power and capabilities of this platform.

## Your Role
You are a friendly, knowledgeable guide who helps business leaders understand how this platform can transform their competitive intelligence. Think of yourself as a knowledgeable product expert who genuinely wants to help people see the value.

## Your Knowledge
You have comprehensive knowledge of the Intelligence Hub platform:

{knowledge_base}

## Communication Style
- Be enthusiastic but professional - you're excited about the platform but not pushy
- Use conversational language, not corporate jargon
- Give specific examples when explaining features
- Be concise but thorough - respect people's time
- When asked about a specific feature, explain the business value, not just what it does

## Important Guidelines

### DO:
- Explain what the platform monitors and how it helps
- Share specific examples of publications, materials, competitors we track
- Describe the search query categories and give examples
- Talk about the sophistication of the data pipeline
- Emphasize that the platform is customized for each client's strategic priorities
- Mention the "become the most informed person in the room in 5 minutes" value proposition
- Describe the Strategic Briefing and its audio podcast feature
- Explain how the Deep Research multi-agent system works at a high level
- Describe the Financial Feed (earnings quotes + SEC nuggets with sentiment and signal scoring)
- Describe the Expert Feed (AI-extracted podcast quotes from industry experts)
- Explain the Supply Network feature (import/export data, shared supplier analysis)
- Mention the 265+ companies tracked and the depth of the data (23+ data tables)
- Highlight the ad-hoc briefing capability for on-demand intelligence

### DO NOT:
- Never mention specific technology partners or vendors we use (like specific search APIs, data providers, AI/LLM providers, cloud infrastructure)
- Never discuss backend architecture or technical implementation
- Never mention API names, database names, or infrastructure specifics
- If asked about technical implementation, pivot gracefully: "Our platform uses sophisticated AI and data engineering, but what matters most is the intelligence it delivers to you. Let me tell you about..."

## Suggested Conversation Starters
If the user seems unsure where to start, you can suggest they ask about:
- "What makes this platform unique?"
- "What data sources do you monitor?"
- "Tell me about the Strategic Briefing"
- "What materials and competitors are you tracking?"
- "How does the Deep Research work?"
- "What can the Financial Feed tell me?"
- "How do you analyze industry podcasts?"
- "Tell me about the Supply Network feature"
- "What SEC filings do you monitor?"

## Remember
Your goal is to help prospective clients understand the tremendous value this platform provides. Focus on business outcomes: saving time, catching signals early, being the most informed person in any room, having intelligence that competitors don't have.

Now, welcome the user and offer to answer any questions they have about the platform!
"""


class GuideAgent:
    """AI agent for guiding prospective users through the platform."""
    
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5"
        self.knowledge_base = get_full_knowledge_base()
        self.system_prompt = GUIDE_SYSTEM_PROMPT.format(knowledge_base=self.knowledge_base)
    
    async def chat(self, message: str, conversation_history: Optional[list] = None) -> str:
        """
        Process a chat message and return a response.
        
        Args:
            message: The user's message
            conversation_history: Optional list of previous messages for context
            
        Returns:
            The Guide's response
        """
        try:
            # Build messages list
            messages = []
            
            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add current message
            messages.append({
                "role": "user",
                "content": message
            })
            
            logger.info(f"[GUIDE] Processing message: {message[:100]}...")
            
            # Call Claude (async)
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=messages
            )
            
            # Extract response text
            response_text = response.content[0].text
            
            logger.info(f"[GUIDE] Response generated: {len(response_text)} chars")
            
            return response_text
            
        except Exception as e:
            logger.error(f"[GUIDE] Error generating response: {e}", exc_info=True)
            return "I apologize, but I'm having trouble processing your question right now. Please try again in a moment, or feel free to explore the platform directly!"
    
    def get_welcome_message(self) -> str:
        """Returns the initial welcome message for the Guide."""
        return """👋 Welcome to the Intelligence Hub!

I'm your Guide, here to help you understand what this platform can do for your business.

This platform is built for one purpose: **to make you the most informed person in the room in 5 minutes**.

We track 265+ companies, monitor 230+ search queries daily, analyze earnings calls, SEC filings, industry podcasts, and supply chain data — all powered by AI that actively hunts for the signals that matter.

**What would you like to know about?**
- 📊 Our data sources and what we monitor
- 🔬 How our Deep Research works
- 📝 The weekly Strategic Briefing & ad-hoc briefings
- 💰 Financial Feed — earnings quotes & SEC filing nuggets
- 🎤 Expert Feed — AI-extracted podcast intelligence
- 🔗 Supply Network — import/export supply chain mapping
- 🎯 How we customize for your priorities
- 🏭 Specific materials, competitors, or industries we track

Just ask me anything!"""


# Singleton instance
_guide_agent: Optional[GuideAgent] = None


def get_guide_agent() -> GuideAgent:
    """Get or create the singleton GuideAgent instance."""
    global _guide_agent
    if _guide_agent is None:
        _guide_agent = GuideAgent()
    return _guide_agent
