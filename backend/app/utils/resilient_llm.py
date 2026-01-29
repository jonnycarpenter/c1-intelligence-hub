"""Resilient LLM wrapper with automatic fallback support.

This module provides two resilient wrapper patterns:
1. ResilientChatAnthropic - For LangChain-based code (agents, workflows)
2. ResilientAsyncClient - For raw SDK code (ingestion, services)

Both support cross-provider fallback: Anthropic (primary) -> OpenAI (fallback)
to protect against credit outages.
"""

import os
import time
from typing import Any, List, Optional, Sequence, Literal, Dict
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableConfig

# Raw SDK imports for async resilient client
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Model Mapping: Anthropic -> OpenAI equivalents
# =============================================================================

ANTHROPIC_TO_OPENAI_MODEL_MAP = {
    "claude-sonnet-4-5": "gpt-4o",
    "claude-3-5-sonnet-20241022": "gpt-4o",
    "claude-opus-4-5": "gpt-4o",  # Opus -> GPT-4o (best available)
    "claude-haiku-4-5": "gpt-4o-mini",  # Haiku alias
    "claude-3-5-haiku-20241022": "gpt-4o-mini",  # Legacy haiku
}


class ResilientChatAnthropic(BaseChatModel):
    """
    A resilient LLM wrapper that automatically falls back to a secondary model if primary fails.
    
    Supports both Anthropic and OpenAI models for cross-provider failover.
    
    Usage:
        # Anthropic primary -> OpenAI fallback (recommended for credit safety)
        llm = ResilientChatAnthropic(
            primary_model="claude-sonnet-4-5",
            fallback_model="gpt-4o",
            fallback_provider="openai",
            api_key=settings.anthropic_api_key,
            fallback_api_key=settings.openai_api_key,
        )
        
        # Anthropic primary -> Anthropic fallback (same provider)
        llm = ResilientChatAnthropic(
            primary_model="claude-sonnet-4-5",
            fallback_model="claude-3-5-haiku-20241022",
            api_key=settings.anthropic_api_key,
        )
    """
    
    primary_model: str
    fallback_model: Optional[str] = None
    fallback_provider: Literal["anthropic", "openai"] = "anthropic"
    api_key: str
    fallback_api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 45.0  # Reduced from 120s - should fail fast, let fallback handle slow requests
    max_retries: int = 1   # Reduced from 2 - faster failure, let asyncio timeout handle retries
    
    # Internal clients (not part of pydantic model)
    _primary_client: Optional[ChatAnthropic] = None
    _fallback_client: Optional[Any] = None  # Can be ChatAnthropic or ChatOpenAI
    _tools: List[Any] = []
    
    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
    
    def __init__(self, **kwargs):
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
            if self.fallback_provider == "openai":
                # OpenAI fallback - use fallback_api_key or environment variable
                openai_key = self.fallback_api_key or os.getenv("OPENAI_API_KEY")
                if not openai_key:
                    logger.warning("OpenAI fallback model specified but no API key available. Skipping fallback.")
                    return
                    
                self._fallback_client = ChatOpenAI(
                    model=self.fallback_model,
                    api_key=openai_key,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
                logger.info(f"Initialized resilient LLM: {self.primary_model} (Anthropic) -> {self.fallback_model} (OpenAI)")
            else:
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
            logger.warning(f"Primary model ({self.primary_model}) failed: {primary_error}")
            
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
                logger.error(f"Fallback model ({self.fallback_model}) also failed: {fallback_error}")
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
            return result
            
        except Exception as primary_error:
            logger.warning(f"Primary model ({self.primary_model}) failed: {primary_error}")
            
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
                return result
                
            except Exception as fallback_error:
                logger.error(f"Fallback model ({self.fallback_model}) also failed: {fallback_error}")
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
            return result
            
        except Exception as primary_error:
            logger.warning(f"Primary model ({self.primary_model}) failed: {primary_error}")
            
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
                return result
                
            except Exception as fallback_error:
                logger.error(f"Fallback model ({self.fallback_model}) also failed: {fallback_error}")
                raise primary_error from fallback_error


# =============================================================================
# Helper Functions for LangChain Usage
# =============================================================================

def create_resilient_llm_with_openai_fallback(
    primary_model: str,
    anthropic_api_key: str,
    openai_api_key: str,
    fallback_model: str = "gpt-4o",
    **kwargs
) -> ResilientChatAnthropic:
    """
    Create a resilient LLM with OpenAI as fallback provider.
    
    This is the recommended pattern to protect against Anthropic credit outages.
    
    Args:
        primary_model: Anthropic model name (e.g., "claude-sonnet-4-5")
        anthropic_api_key: Your Anthropic API key
        openai_api_key: Your OpenAI API key (fallback)
        fallback_model: OpenAI model to use as fallback (default: "gpt-4o")
        **kwargs: Additional parameters (temperature, max_tokens, etc.)
    
    Returns:
        ResilientChatAnthropic instance with OpenAI fallback
        
    Example:
        from app.config.settings import settings
        
        llm = create_resilient_llm_with_openai_fallback(
            primary_model="claude-sonnet-4-5",
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=settings.openai_api_key,
            fallback_model="gpt-4o",
            temperature=0.3,
        )
    """
    return ResilientChatAnthropic(
        primary_model=primary_model,
        fallback_model=fallback_model,
        fallback_provider="openai",
        api_key=anthropic_api_key,
        fallback_api_key=openai_api_key,
        **kwargs
    )


# =============================================================================
# Resilient Async Client (for raw SDK usage in ingestion/services)
# =============================================================================

class ResilientAsyncClient:
    """
    Resilient async client that wraps Anthropic SDK with OpenAI fallback.
    
    For use in ingestion pipelines, services, and other async code that 
    uses the raw Anthropic SDK (not LangChain).
    
    Usage:
        client = ResilientAsyncClient(
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=settings.openai_api_key,
        )
        
        response = await client.messages_create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": "Hello"}],
        )
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        openai_api_key: Optional[str] = None,
    ):
        self.anthropic_client = AsyncAnthropic(api_key=anthropic_api_key)
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self._openai_client: Optional[AsyncOpenAI] = None
        
    @property
    def openai_client(self) -> Optional[AsyncOpenAI]:
        """Lazy init OpenAI client only when needed."""
        if self._openai_client is None and self.openai_api_key:
            self._openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        return self._openai_client
    
    def _get_openai_model(self, anthropic_model: str) -> str:
        """Map Anthropic model to equivalent OpenAI model."""
        return ANTHROPIC_TO_OPENAI_MODEL_MAP.get(anthropic_model, "gpt-4o")
    
    def _convert_messages_for_openai(
        self, 
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Convert Anthropic message format to OpenAI format."""
        openai_messages = []
        
        # Add system message if provided
        if system:
            openai_messages.append({"role": "system", "content": system})
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Handle complex content (e.g., with images)
            if isinstance(content, list):
                # For now, extract text only (OpenAI has different image format)
                text_parts = [
                    part.get("text", "") 
                    for part in content 
                    if part.get("type") == "text"
                ]
                content = "\n".join(text_parts) if text_parts else str(content)
            
            openai_messages.append({"role": role, "content": content})
        
        return openai_messages
    
    async def messages_create(
        self,
        model: str,
        max_tokens: int,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        temperature: float = 0.3,
        thinking: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Create a message with automatic OpenAI fallback.
        
        Args:
            model: The model to use (e.g., "claude-sonnet-4-5")
            max_tokens: Maximum tokens in response
            messages: List of message dictionaries
            system: Optional system prompt
            temperature: Sampling temperature (ignored when thinking is enabled)
            thinking: Optional extended thinking config, e.g. {"type": "enabled", "budget_tokens": 10000}
                     See: https://platform.claude.com/docs/en/build-with-claude/extended-thinking
        
        Returns an Anthropic-style response object (or OpenAI response adapted).
        The response may include 'thinking' content blocks when thinking is enabled.
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
            # For thinking responses, check for text blocks specifically
            text_content = [b for b in response.content if getattr(b, 'type', None) == 'text']
            if not response.content or (not thinking_enabled and len(response.content) == 0):
                logger.warning(f"Anthropic ({model}) returned empty content, falling back to OpenAI")
                raise ValueError("Anthropic returned empty response")
            if thinking_enabled and not text_content:
                logger.warning(f"Anthropic ({model}) returned only thinking blocks, no text output")
                # Still return - thinking-only responses can be valid
            
            return response
            
        except Exception as anthropic_error:
            logger.warning(f"Anthropic ({model}) failed: {anthropic_error}")
            
            # Try OpenAI fallback
            if not self.openai_client:
                logger.error("No OpenAI API key configured for fallback")
                raise anthropic_error
            
            try:
                openai_model = self._get_openai_model(model)
                openai_messages = self._convert_messages_for_openai(messages, system)
                
                logger.info(f"Falling back to OpenAI ({openai_model})")
                start = time.time()
                
                openai_response = await self.openai_client.chat.completions.create(
                    model=openai_model,
                    max_tokens=max_tokens,
                    messages=openai_messages,
                    temperature=temperature,
                )
                elapsed = time.time() - start
                logger.info(f"OpenAI fallback ({openai_model}) succeeded in {elapsed:.2f}s")
                
                # Wrap OpenAI response in Anthropic-like structure
                return OpenAIResponseAdapter(openai_response)
                
            except Exception as openai_error:
                logger.error(f"OpenAI fallback also failed: {openai_error}")
                raise anthropic_error from openai_error


class OpenAIResponseAdapter:
    """
    Adapter to make OpenAI responses look like Anthropic responses.
    
    This allows existing code using Anthropic response structure to work
    with OpenAI fallback responses without modification.
    """
    
    def __init__(self, openai_response):
        self._openai_response = openai_response
        
        # Create content list like Anthropic
        choice = openai_response.choices[0] if openai_response.choices else None
        text = choice.message.content if choice else ""
        
        self.content = [ContentBlock(text=text)]
        self.stop_reason = choice.finish_reason if choice else "end_turn"
        self.model = openai_response.model
        self.usage = UsageAdapter(openai_response.usage)


class ContentBlock:
    """Mimics Anthropic's ContentBlock."""
    def __init__(self, text: str, type: str = "text"):
        self.text = text
        self.type = type


class UsageAdapter:
    """Mimics Anthropic's Usage object."""
    def __init__(self, openai_usage):
        self.input_tokens = openai_usage.prompt_tokens if openai_usage else 0
        self.output_tokens = openai_usage.completion_tokens if openai_usage else 0


def get_resilient_async_client(
    anthropic_api_key: str,
    openai_api_key: Optional[str] = None,
) -> ResilientAsyncClient:
    """
    Get a resilient async client with OpenAI fallback.
    
    Example:
        from app.config.settings import settings
        from app.utils.resilient_llm import get_resilient_async_client
        
        client = get_resilient_async_client(
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=settings.openai_api_key,
        )
        
        response = await client.messages_create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(response.content[0].text)
    """
    return ResilientAsyncClient(
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
    )
