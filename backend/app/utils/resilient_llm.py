"""Resilient LLM wrapper with automatic fallback support.

This module provides two resilient wrapper patterns:
1. ResilientChatAnthropic - For LangChain-based code (agents, workflows)
2. ResilientAsyncClient - For raw SDK code (ingestion, services)

Both support cross-provider fallback: Anthropic (primary) -> Google Gemini (fallback)
to protect against credit outages.

Fallback notes:
- Gemini does NOT support extended thinking, so thinking params are dropped on fallback
- max_tokens is clamped to Gemini's model limit (65536 for gemini-2.5-pro)
- Messages are converted from Anthropic format to Gemini/OpenAI-compatible format
"""

import os
import time
from typing import Any, List, Optional, Sequence, Literal, Dict
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableConfig

# Raw SDK imports for async resilient client
from anthropic import AsyncAnthropic

# Google Gemini imports (lazy-loaded for fallback)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    HAS_LANGCHAIN_GEMINI = True
except ImportError:
    HAS_LANGCHAIN_GEMINI = False

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _track_tokens(model: str, result: Any, provider: str = "anthropic", caller: str = "unknown") -> None:
    """Record token usage from an LLM response. Fails silently."""
    try:
        from app.evals.token_tracker import token_tracker

        input_tokens = 0
        output_tokens = 0

        if provider == "anthropic" and hasattr(result, "response_metadata"):
            # LangChain ChatAnthropic response
            usage = result.response_metadata.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
        elif provider == "anthropic" and hasattr(result, "usage"):
            # Raw Anthropic SDK response
            input_tokens = getattr(result.usage, "input_tokens", 0)
            output_tokens = getattr(result.usage, "output_tokens", 0)
        elif provider == "openai" and hasattr(result, "usage"):
            input_tokens = getattr(result.usage, "input_tokens", 0)
            output_tokens = getattr(result.usage, "output_tokens", 0)

        if input_tokens or output_tokens:
            token_tracker.record(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                caller=caller,
            )
    except Exception:
        pass  # Token tracking must never break LLM calls


# =============================================================================
# Model Mapping: Anthropic -> Google Gemini equivalents
# =============================================================================

ANTHROPIC_TO_GEMINI_MODEL_MAP = {
    "claude-sonnet-4-6": "gemini-2.5-pro",
    "claude-3-5-sonnet-20241022": "gemini-2.5-pro",
    "claude-opus-4-6": "gemini-2.5-pro",
    "claude-opus-4-5": "gemini-2.5-pro",  # Legacy alias
    "claude-haiku-4-5": "gemini-2.5-flash",  # Haiku -> Flash (fast + cheap)
}

# Gemini model output token limits (for clamping)
GEMINI_MAX_OUTPUT_TOKENS = {
    "gemini-2.5-pro": 65536,
    "gemini-2.5-flash": 65536,
    "gemini-3-pro": 65536,
    "gemini-2.0-flash": 8192,  # Deprecated March 2026
}
DEFAULT_GEMINI_MAX_OUTPUT = 8192  # Safe default if model not in map


def _clamp_max_tokens_for_gemini(max_tokens: int, gemini_model: str) -> int:
    """Clamp max_tokens to the Gemini model's output limit to prevent 400 errors."""
    model_limit = GEMINI_MAX_OUTPUT_TOKENS.get(gemini_model, DEFAULT_GEMINI_MAX_OUTPUT)
    if max_tokens > model_limit:
        logger.info(f"Clamping max_tokens from {max_tokens} to {model_limit} for {gemini_model}")
        return model_limit
    return max_tokens


def _get_default_timeout_for_model(model: str) -> float:
    """Return appropriate HTTP timeout based on model class.

    Opus-class models are significantly slower than Haiku/Sonnet,
    especially with large context windows and complex prompts.
    """
    model_lower = model.lower()
    if "opus" in model_lower:
        return 180.0  # 3 minutes for Opus (large prompts, complex reasoning)
    elif "sonnet" in model_lower:
        return 90.0   # 90 seconds for Sonnet
    elif "haiku" in model_lower:
        return 45.0   # 45 seconds for Haiku (fast model)
    else:
        return 120.0  # Safe default for unknown models


class ResilientChatAnthropic(BaseChatModel):
    """
    A resilient LLM wrapper that automatically falls back to a secondary model if primary fails.
    
    Supports Anthropic primary with Google Gemini or Anthropic fallback.
    
    Usage:
        # Anthropic primary -> Gemini fallback (recommended for credit safety)
        llm = ResilientChatAnthropic(
            primary_model="claude-sonnet-4-6",
            fallback_model="gemini-2.5-pro",
            fallback_provider="gemini",
            api_key=settings.anthropic_api_key,
            fallback_api_key=settings.gemini_api_key,
        )
        
        # Anthropic primary -> Anthropic fallback (same provider)
        llm = ResilientChatAnthropic(
            primary_model="claude-sonnet-4-6",
            fallback_model="claude-haiku-4-5",
            api_key=settings.anthropic_api_key,
        )
    """
    
    primary_model: str
    fallback_model: Optional[str] = None
    fallback_provider: Literal["anthropic", "gemini"] = "anthropic"
    api_key: str
    fallback_api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 120.0  # Model-aware default applied in __init__; see _get_default_timeout_for_model()
    max_retries: int = 2
    
    # Internal clients (not part of pydantic model)
    _primary_client: Optional[ChatAnthropic] = None
    _fallback_client: Optional[Any] = None  # Can be ChatAnthropic or ChatGoogleGenerativeAI
    _tools: List[Any] = []
    
    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
    
    def __init__(self, **kwargs):
        # Apply model-aware timeout if caller didn't set an explicit one
        if "timeout" not in kwargs:
            model = kwargs.get("primary_model", "")
            kwargs["timeout"] = _get_default_timeout_for_model(model)
        super().__init__(**kwargs)
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize primary and fallback clients."""
        # Primary is always Anthropic
        self._primary_client = ChatAnthropic(
            model=self.primary_model,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        
        if self.fallback_model:
            if self.fallback_provider == "gemini":
                # Google Gemini fallback
                gemini_key = self.fallback_api_key or os.getenv("GEMINI_API_KEY")
                if not gemini_key:
                    logger.warning("Gemini fallback model specified but no API key available. Skipping fallback.")
                    return
                if not HAS_LANGCHAIN_GEMINI:
                    logger.warning("langchain-google-genai not installed. Skipping Gemini fallback.")
                    return
                
                # Clamp max_tokens for Gemini
                clamped_tokens = _clamp_max_tokens_for_gemini(self.max_tokens, self.fallback_model)
                
                self._fallback_client = ChatGoogleGenerativeAI(
                    model=self.fallback_model,
                    google_api_key=gemini_key,
                    temperature=self.temperature,
                    max_output_tokens=clamped_tokens,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
                logger.info(f"Initialized resilient LLM: {self.primary_model} (Anthropic) -> {self.fallback_model} (Gemini, max_tokens={clamped_tokens})")
            elif self.fallback_provider == "anthropic":
                # Anthropic fallback
                self._fallback_client = ChatAnthropic(
                    model=self.fallback_model,
                    api_key=self.api_key,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
                logger.info(f"Initialized resilient LLM: {self.primary_model} -> {self.fallback_model} (both Anthropic)")
        else:
            logger.info(f"Initialized LLM (no fallback): {self.primary_model}")
    
    def bind_tools(self, tools: List[Any], **kwargs) -> "ResilientChatAnthropic":
        """Bind tools to the LLM, returns self for chaining."""
        self._tools = tools
        if self._primary_client:
            self._primary_client = self._primary_client.bind_tools(tools, **kwargs)
        if self._fallback_client:
            self._fallback_client = self._fallback_client.bind_tools(tools, **kwargs)
        return self
    
    @property
    def _llm_type(self) -> str:
        return "resilient-anthropic"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs,
    ) -> ChatResult:
        """Generate with fallback support."""
        return self._invoke_with_fallback(messages, stop=stop, **kwargs)
    
    def _invoke_with_fallback(
        self,
        messages: List[BaseMessage],
        **kwargs,
    ) -> ChatResult:
        """Try primary model, fall back to secondary on failure."""
        
        # Try primary model
        try:
            logger.debug(f"Invoking primary model: {self.primary_model}")
            start = time.time()
            result = self._primary_client._generate(messages, **kwargs)
            elapsed = time.time() - start
            logger.info(f"Primary model ({self.primary_model}) succeeded in {elapsed:.2f}s")
            return result
            
        except Exception as primary_error:
            logger.warning(
                f"Primary model ({self.primary_model}) failed: [{type(primary_error).__name__}] {primary_error}",
                exc_info=True,
            )

            # If no fallback configured, re-raise
            if not self._fallback_client:
                logger.error("No fallback model configured, re-raising error")
                raise

            # Try fallback model
            try:
                logger.info(f"Falling back to: {self.fallback_model}")
                start = time.time()
                result = self._fallback_client._generate(messages, **kwargs)
                elapsed = time.time() - start
                logger.info(f"Fallback model ({self.fallback_model}) succeeded in {elapsed:.2f}s")
                return result

            except Exception as fallback_error:
                logger.error(
                    f"Fallback model ({self.fallback_model}) also failed: [{type(fallback_error).__name__}] {fallback_error}",
                    exc_info=True,
                )
                # Raise the original error (more informative)
                raise primary_error from fallback_error

    def invoke(
        self,
        input: Sequence[BaseMessage],
        config: Optional[RunnableConfig] = None,
        **kwargs,
    ) -> BaseMessage:
        """Invoke with fallback support - returns single message."""
        
        messages = list(input) if not isinstance(input, list) else input
        
        # Try primary model
        try:
            logger.debug(f"Invoking primary model: {self.primary_model}")
            start = time.time()
            result = self._primary_client.invoke(messages, config=config, **kwargs)
            elapsed = time.time() - start
            logger.info(f"Primary model ({self.primary_model}) succeeded in {elapsed:.2f}s")
            _track_tokens(self.primary_model, result, "anthropic")
            return result

        except Exception as primary_error:
            logger.warning(
                f"Primary model ({self.primary_model}) failed: [{type(primary_error).__name__}] {primary_error}",
                exc_info=True,
            )

            # If no fallback configured, re-raise
            if not self._fallback_client:
                logger.error("No fallback model configured, re-raising error")
                raise

            # Try fallback model
            try:
                logger.info(f"Falling back to: {self.fallback_model}")
                start = time.time()
                result = self._fallback_client.invoke(messages, config=config, **kwargs)
                elapsed = time.time() - start
                logger.info(f"Fallback model ({self.fallback_model}) succeeded in {elapsed:.2f}s")
                fb_provider = "gemini" if self.fallback_provider == "gemini" else "anthropic"
                _track_tokens(self.fallback_model, result, fb_provider)
                return result

            except Exception as fallback_error:
                logger.error(
                    f"Fallback model ({self.fallback_model}) also failed: [{type(fallback_error).__name__}] {fallback_error}",
                    exc_info=True,
                )
                # Raise the original error (more informative)
                raise primary_error from fallback_error

    async def ainvoke(
        self,
        input: Sequence[BaseMessage],
        config: Optional[RunnableConfig] = None,
        **kwargs,
    ) -> BaseMessage:
        """Async invoke with fallback support."""
        
        messages = list(input) if not isinstance(input, list) else input
        
        # Try primary model
        try:
            logger.info(f"Async invoking primary model: {self.primary_model} (message count: {len(messages)})")
            start = time.time()
            result = await self._primary_client.ainvoke(messages, config=config, **kwargs)
            elapsed = time.time() - start
            logger.info(f"Primary model ({self.primary_model}) succeeded in {elapsed:.2f}s")
            _track_tokens(self.primary_model, result, "anthropic")
            return result

        except Exception as primary_error:
            logger.warning(
                f"Primary model ({self.primary_model}) failed: [{type(primary_error).__name__}] {primary_error}",
                exc_info=True,
            )

            # If no fallback configured, re-raise
            if not self._fallback_client:
                logger.error("No fallback model configured, re-raising error")
                raise

            # Try fallback model
            try:
                logger.info(f"Falling back to: {self.fallback_model}")
                start = time.time()
                result = await self._fallback_client.ainvoke(messages, config=config, **kwargs)
                elapsed = time.time() - start
                logger.info(f"Fallback model ({self.fallback_model}) succeeded in {elapsed:.2f}s")
                fb_provider = "gemini" if self.fallback_provider == "gemini" else "anthropic"
                _track_tokens(self.fallback_model, result, fb_provider)
                return result

            except Exception as fallback_error:
                logger.error(
                    f"Fallback model ({self.fallback_model}) also failed: [{type(fallback_error).__name__}] {fallback_error}",
                    exc_info=True,
                )
                raise primary_error from fallback_error


# =============================================================================
# Helper Functions for LangChain Usage
# =============================================================================

def create_resilient_llm_with_gemini_fallback(
    primary_model: str,
    anthropic_api_key: str,
    gemini_api_key: str,
    fallback_model: Optional[str] = None,
    **kwargs
) -> ResilientChatAnthropic:
    """
    Create a resilient LLM with Google Gemini as fallback provider.
    
    This is the recommended pattern to protect against Anthropic credit outages.
    Gemini does NOT support extended thinking - thinking params are dropped on fallback.
    max_tokens is automatically clamped to the Gemini model's limit.
    
    Args:
        primary_model: Anthropic model name (e.g., "claude-sonnet-4-6")
        anthropic_api_key: Your Anthropic API key
        gemini_api_key: Your Google Gemini API key (fallback)
        fallback_model: Gemini model to use as fallback (auto-mapped if None)
        **kwargs: Additional parameters (temperature, max_tokens, etc.)
    
    Returns:
        ResilientChatAnthropic instance with Gemini fallback
        
    Example:
        from app.config.settings import settings
        
        llm = create_resilient_llm_with_gemini_fallback(
            primary_model="claude-sonnet-4-6",
            anthropic_api_key=settings.anthropic_api_key,
            gemini_api_key=settings.gemini_api_key,
            temperature=0.3,
        )
    """
    if not fallback_model:
        fallback_model = ANTHROPIC_TO_GEMINI_MODEL_MAP.get(primary_model, "gemini-2.5-pro")
    
    return ResilientChatAnthropic(
        primary_model=primary_model,
        fallback_model=fallback_model,
        fallback_provider="gemini",
        api_key=anthropic_api_key,
        fallback_api_key=gemini_api_key,
        **kwargs
    )


# Backward-compatible alias (callers use this name)
def create_resilient_llm_with_openai_fallback(
    primary_model: str,
    anthropic_api_key: str,
    openai_api_key: str,  # This param name is kept for backward compat but now expects Gemini key
    fallback_model: Optional[str] = None,
    **kwargs
) -> ResilientChatAnthropic:
    """
    DEPRECATED: Use create_resilient_llm_with_gemini_fallback() instead.
    
    This function exists for backward compatibility. It routes to the Gemini fallback.
    The openai_api_key parameter now accepts a Gemini API key.
    """
    return create_resilient_llm_with_gemini_fallback(
        primary_model=primary_model,
        anthropic_api_key=anthropic_api_key,
        gemini_api_key=openai_api_key,
        fallback_model=fallback_model,
        **kwargs
    )


# =============================================================================
# Resilient Async Client (for raw SDK usage in ingestion/services)
# =============================================================================

class ResilientAsyncClient:
    """
    Resilient async client that wraps Anthropic SDK with Google Gemini fallback.
    
    For use in ingestion pipelines, services, and other async code that 
    uses the raw Anthropic SDK (not LangChain).
    
    Gemini fallback notes:
    - Extended thinking params are dropped (Gemini doesn't support them)
    - max_tokens is clamped to the Gemini model's output limit
    - Response is adapted to Anthropic-like structure for seamless caller compat
    
    Usage:
        client = ResilientAsyncClient(
            anthropic_api_key=settings.anthropic_api_key,
            gemini_api_key=settings.gemini_api_key,
        )
        
        response = await client.messages_create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": "Hello"}],
        )
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,  # Kept for backward compat, treated as gemini key
        timeout: float = 180.0,  # HTTP timeout for Anthropic SDK calls (generous for Opus + thinking)
    ):
        self.anthropic_client = AsyncAnthropic(api_key=anthropic_api_key, timeout=timeout)
        self.timeout = timeout
        # Accept gemini_api_key directly, or fall back to openai_api_key param (backward compat),
        # or check env var
        self.gemini_api_key = gemini_api_key or openai_api_key or os.getenv("GEMINI_API_KEY")
        self._gemini_client = None
        
    @property
    def gemini_client(self):
        """Lazy init Google Gemini client only when needed."""
        if self._gemini_client is None and self.gemini_api_key and HAS_GOOGLE_GENAI:
            self._gemini_client = genai.Client(api_key=self.gemini_api_key)
        return self._gemini_client
    
    def _get_gemini_model(self, anthropic_model: str) -> str:
        """Map Anthropic model to equivalent Gemini model."""
        return ANTHROPIC_TO_GEMINI_MODEL_MAP.get(anthropic_model, "gemini-2.5-pro")
    
    def _build_gemini_contents(
        self, 
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
    ) -> tuple:
        """Convert Anthropic message format to Gemini format.
        
        Returns (system_instruction, contents) tuple.
        """
        contents = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Map Anthropic role -> Gemini role
            gemini_role = "user" if role == "user" else "model"
            
            # Handle complex content (e.g., with images)
            if isinstance(content, list):
                text_parts = [
                    part.get("text", "") 
                    for part in content 
                    if part.get("type") == "text"
                ]
                content = "\n".join(text_parts) if text_parts else str(content)
            
            contents.append(genai_types.Content(
                role=gemini_role,
                parts=[genai_types.Part(text=content)],
            ))
        
        return system, contents
    
    async def messages_create(
        self,
        model: str,
        max_tokens: int,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        temperature: float = 0.3,
        thinking: Optional[Dict[str, Any]] = None,
        _caller: str = "unknown",
        **kwargs,
    ) -> Any:
        """
        Create a message with automatic Gemini fallback.
        
        Args:
            model: The model to use (e.g., "claude-sonnet-4-6")
            max_tokens: Maximum tokens in response
            messages: List of message dictionaries
            system: Optional system prompt
            temperature: Sampling temperature (ignored when thinking is enabled)
            thinking: Optional extended thinking config, e.g. {"type": "enabled", "budget_tokens": 10000}
                     Note: Thinking is NOT supported by Gemini and will be dropped on fallback.
        
        Returns an Anthropic-style response object (or Gemini response adapted).
        The response may include 'thinking' content blocks when thinking is enabled (Anthropic only).
        """
        # Try Anthropic first
        try:
            start = time.time()
            thinking_enabled = thinking and thinking.get("type") == "enabled"
            logger.info(f"Async invoking primary model: {model} (thinking={'enabled' if thinking_enabled else 'disabled'})")
            
            # Build params dict - only include system if provided (SDK 0.75.0+ requires this)
            anthropic_params = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
                **kwargs,
            }
            
            # Extended thinking configuration
            # Note: temperature/top_k not compatible with extended thinking
            if thinking_enabled:
                anthropic_params["thinking"] = thinking
                # Don't set temperature when thinking is enabled (API requirement)
                # Safety: max_tokens MUST be > thinking.budget_tokens
                budget = thinking.get("budget_tokens", 0)
                if budget and max_tokens <= budget:
                    fixed_max = budget + 16000
                    logger.warning(f"max_tokens ({max_tokens}) must be > thinking.budget_tokens ({budget}). Auto-fixing to {fixed_max}")
                    anthropic_params["max_tokens"] = fixed_max
            else:
                anthropic_params["temperature"] = temperature
            
            if system:
                anthropic_params["system"] = system
            
            response = await self.anthropic_client.messages.create(**anthropic_params)
            elapsed = time.time() - start
            
            # Log thinking usage if present
            if thinking_enabled:
                thinking_blocks = [b for b in response.content if getattr(b, 'type', None) == 'thinking']
                text_blocks = [b for b in response.content if getattr(b, 'type', None) == 'text']
                logger.info(f"Anthropic ({model}) succeeded in {elapsed:.2f}s - thinking_blocks: {len(thinking_blocks)}, text_blocks: {len(text_blocks)}")
            else:
                logger.info(f"Anthropic ({model}) succeeded in {elapsed:.2f}s")
            
            # Check for empty response (API succeeded but returned nothing)
            text_content = [b for b in response.content if getattr(b, 'type', None) == 'text']
            if not response.content or (not thinking_enabled and len(response.content) == 0):
                logger.warning(f"Anthropic ({model}) returned empty content, falling back to Gemini")
                raise ValueError("Anthropic returned empty response")
            if thinking_enabled and not text_content:
                logger.warning(f"Anthropic ({model}) returned only thinking blocks, no text output")
                # Still return - thinking-only responses can be valid

            _track_tokens(model, response, "anthropic", _caller)
            return response
            
        except Exception as anthropic_error:
            logger.warning(
                f"Anthropic ({model}) failed: [{type(anthropic_error).__name__}] {anthropic_error}",
                exc_info=True,
            )

            # Try Gemini fallback
            if not self.gemini_client:
                if not HAS_GOOGLE_GENAI:
                    logger.error("google-genai not installed for Gemini fallback")
                else:
                    logger.error("No Gemini API key configured for fallback")
                raise anthropic_error
            
            try:
                gemini_model = self._get_gemini_model(model)
                system_instruction, contents = self._build_gemini_contents(messages, system)
                
                # Clamp max_tokens for Gemini model limits
                clamped_tokens = _clamp_max_tokens_for_gemini(max_tokens, gemini_model)
                
                # Note: Gemini does NOT support extended thinking.
                # We drop thinking params and use higher max_tokens instead.
                if thinking and thinking.get("type") == "enabled":
                    logger.info(f"Dropping extended thinking for Gemini fallback (not supported). Using max_tokens={clamped_tokens}")
                
                logger.info(f"Falling back to Gemini ({gemini_model}, max_tokens={clamped_tokens})")
                start = time.time()
                
                gemini_config = genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=clamped_tokens,
                )
                
                gemini_response = await self.gemini_client.aio.models.generate_content(
                    model=gemini_model,
                    contents=contents,
                    config=gemini_config,
                )
                elapsed = time.time() - start
                logger.info(f"Gemini fallback ({gemini_model}) succeeded in {elapsed:.2f}s")

                # Wrap Gemini response in Anthropic-like structure
                adapted = GeminiResponseAdapter(gemini_response, gemini_model)
                _track_tokens(gemini_model, adapted, "gemini", _caller)
                return adapted
                
            except Exception as gemini_error:
                logger.error(
                    f"Gemini fallback also failed: [{type(gemini_error).__name__}] {gemini_error}",
                    exc_info=True,
                )
                raise anthropic_error from gemini_error


class GeminiResponseAdapter:
    """
    Adapter to make Gemini responses look like Anthropic responses.
    
    This allows existing code using Anthropic response structure to work
    with Gemini fallback responses without modification.
    """
    
    def __init__(self, gemini_response, model: str = "gemini-2.5-pro"):
        self._gemini_response = gemini_response
        
        # Extract text from Gemini response
        text = ""
        if gemini_response.candidates:
            candidate = gemini_response.candidates[0]
            if candidate.content and candidate.content.parts:
                text_parts = [p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text]
                text = "\n".join(text_parts)
        
        self.content = [ContentBlock(text=text)]
        self.stop_reason = "end_turn"
        self.model = model
        
        # Build usage adapter from Gemini usage metadata
        self.usage = GeminiUsageAdapter(gemini_response)


class ContentBlock:
    """Mimics Anthropic's ContentBlock."""
    def __init__(self, text: str, type: str = "text"):
        self.text = text
        self.type = type


class GeminiUsageAdapter:
    """Mimics Anthropic's Usage object from Gemini usage metadata."""
    def __init__(self, gemini_response):
        usage = getattr(gemini_response, 'usage_metadata', None)
        self.input_tokens = getattr(usage, 'prompt_token_count', 0) if usage else 0
        self.output_tokens = getattr(usage, 'candidates_token_count', 0) if usage else 0


def get_resilient_async_client(
    anthropic_api_key: str,
    openai_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    timeout: float = 180.0,
) -> ResilientAsyncClient:
    """
    Get a resilient async client with Gemini fallback.

    Args:
        anthropic_api_key: Your Anthropic API key
        openai_api_key: DEPRECATED - kept for backward compat, treated as gemini_api_key
        gemini_api_key: Your Google Gemini API key (preferred)
        timeout: HTTP timeout in seconds (default 180s, generous for Opus + thinking)

    Example:
        from app.config.settings import settings
        from app.utils.resilient_llm import get_resilient_async_client

        client = get_resilient_async_client(
            anthropic_api_key=settings.anthropic_api_key,
            gemini_api_key=settings.gemini_api_key,
        )

        response = await client.messages_create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(response.content[0].text)
    """
    return ResilientAsyncClient(
        anthropic_api_key=anthropic_api_key,
        gemini_api_key=gemini_api_key or openai_api_key,
        timeout=timeout,
    )
