"""
Action Recovery - Retry and Recovery Strategies
=================================================
Handles failures with intelligent recovery.

Sprint 2: Autonomous Action
"""

import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum


class RecoveryStrategy(Enum):
    """Available recovery strategies."""
    RETRY = "retry"                     # Simple retry
    RESCAN_UI = "rescan_ui"            # Rescan UI tree and retry
    ALTERNATE_SELECTOR = "alt_selector" # Try alternate selector
    OCR_FALLBACK = "ocr_fallback"      # Use OCR to find element
    ABORT = "abort"                     # Give up


@dataclass
class RecoveryResult:
    """Result of recovery attempt."""
    strategy: RecoveryStrategy
    success: bool
    attempts: int
    error: Optional[str] = None
    new_element: Any = None


class ActionRecovery:
    """
    Handles action failures with recovery strategies.
    
    Recovery order:
    1. Simple retry (with delay)
    2. Rescan UI tree
    3. Try alternate selector
    4. OCR fallback
    5. Abort
    """
    
    DEFAULT_MAX_RETRIES = 3
    RETRY_DELAYS = [0.5, 1.0, 2.0]  # Backoff delays
    
    def __init__(self, ui_inspector=None, selector_resolver=None):
        self.ui_inspector = ui_inspector
        self.selector_resolver = selector_resolver
    
    def recover(self, 
                action_fn: Callable,
                original_error: str,
                strategy: RecoveryStrategy = RecoveryStrategy.RETRY,
                max_attempts: int = 3) -> RecoveryResult:
        """
        Attempt recovery from failed action.
        
        Args:
            action_fn: Function to retry
            original_error: Error message from failed attempt
            strategy: Recovery strategy to use
            max_attempts: Maximum retry attempts
            
        Returns:
            RecoveryResult
        """
        if strategy == RecoveryStrategy.RETRY:
            return self._retry_with_backoff(action_fn, max_attempts)
        elif strategy == RecoveryStrategy.RESCAN_UI:
            return self._rescan_and_retry(action_fn, max_attempts)
        elif strategy == RecoveryStrategy.ABORT:
            return RecoveryResult(
                strategy=RecoveryStrategy.ABORT,
                success=False,
                attempts=0,
                error="Aborted"
            )
        
        return RecoveryResult(
            strategy=strategy,
            success=False,
            attempts=0,
            error=f"Strategy {strategy.value} not implemented"
        )
    
    def _retry_with_backoff(self, action_fn: Callable, max_attempts: int) -> RecoveryResult:
        """Retry with exponential backoff."""
        for attempt in range(max_attempts):
            delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
            time.sleep(delay)
            
            try:
                result = action_fn()
                if result and (getattr(result, 'ok', False) or result.get('ok', False) if isinstance(result, dict) else False):
                    return RecoveryResult(
                        strategy=RecoveryStrategy.RETRY,
                        success=True,
                        attempts=attempt + 1
                    )
            except Exception as e:
                if attempt == max_attempts - 1:
                    return RecoveryResult(
                        strategy=RecoveryStrategy.RETRY,
                        success=False,
                        attempts=attempt + 1,
                        error=str(e)
                    )
        
        return RecoveryResult(
            strategy=RecoveryStrategy.RETRY,
            success=False,
            attempts=max_attempts,
            error="Max retries exceeded"
        )
    
    def _rescan_and_retry(self, action_fn: Callable, max_attempts: int) -> RecoveryResult:
        """Rescan UI tree and retry."""
        if not self.ui_inspector:
            return RecoveryResult(
                strategy=RecoveryStrategy.RESCAN_UI,
                success=False,
                attempts=0,
                error="UI inspector not available"
            )
        
        for attempt in range(max_attempts):
            # Rescan UI
            try:
                new_tree = self.ui_inspector.get_active_window_tree()
                if new_tree:
                    result = action_fn()
                    if result and getattr(result, 'ok', False):
                        return RecoveryResult(
                            strategy=RecoveryStrategy.RESCAN_UI,
                            success=True,
                            attempts=attempt + 1
                        )
            except Exception as e:
                pass
            
            time.sleep(0.5)
        
        return RecoveryResult(
            strategy=RecoveryStrategy.RESCAN_UI,
            success=False,
            attempts=max_attempts,
            error="Rescan recovery failed"
        )
    
    def suggest_strategy(self, error: str, action_type: str) -> RecoveryStrategy:
        """
        Suggest recovery strategy based on error type.
        
        Args:
            error: Error message
            action_type: Type of action that failed
            
        Returns:
            Recommended RecoveryStrategy
        """
        error_lower = error.lower()
        
        # Element not found -> rescan
        if "not found" in error_lower or "no element" in error_lower:
            return RecoveryStrategy.RESCAN_UI
        
        # Timeout -> retry
        if "timeout" in error_lower:
            return RecoveryStrategy.RETRY
        
        # Permission -> abort
        if "permission" in error_lower or "access denied" in error_lower:
            return RecoveryStrategy.ABORT
        
        # Default -> retry
        return RecoveryStrategy.RETRY
