"""Resilient LLM wrapper with automatic fallback support."""

import time
from typing import Any, List, Optional, Sequence
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableConfig

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResilientChatAnthropic(BaseChatModel):
    """
    A resilient ChatAnthropic wrapper that automatically falls back to
    a secondary model if the primary model fails.
    
    Usage:
        llm = ResilientChatAnthropic(
            primary_model="claude-sonnet-4-5",
            fallback_model="claude-sonnet-4-5",
            api_key=settings.anthropic_api_key,
        )
    """
    
    primary_model: str
    fallback_model: Optional[str] = None
    api_key: str
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 120.0
    max_retries: int = 2
    
    # Internal clients (not part of pydantic model)
    _primary_client: Optional[ChatAnthropic] = None
    _fallback_client: Optional[ChatAnthropic] = None
    _tools: List[Any] = []
    
    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize primary and fallback clients."""
        self._primary_client = ChatAnthropic(
            model=self.primary_model,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        
        if self.fallback_model:
            self._fallback_client = ChatAnthropic(
                model=self.fallback_model,
                api_key=self.api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
            logger.info(f"Initialized resilient LLM: {self.primary_model} -> {self.fallback_model}")
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
            logger.debug(f"Async invoking primary model: {self.primary_model}")
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
