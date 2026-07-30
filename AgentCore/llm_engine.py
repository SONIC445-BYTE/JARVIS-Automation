"""
LLM Engine - Local Language Model Interface
=============================================
Ollama integration for offline, free LLM inference.

Sprint 6: Conversational Intelligence
"""

import os
import json
import time
import subprocess
from typing import Optional, Dict, Generator, List
from dataclasses import dataclass, field
from threading import Thread, Event


@dataclass
class LLMResponse:
    """Response from LLM."""
    text: str
    tokens_used: int = 0
    duration_ms: float = 0
    model: str = ""
    truncated: bool = False


class LLMEngine:
    """
    Local LLM via Ollama (CPU-optimized).
    
    Models (in order of preference for Intel UHD):
    1. phi3:mini (3.8B, fast, good quality)
    2. tinyllama (1.1B, very fast, lower quality)
    3. gemma:2b (2B, balanced)
    
    Fallback: Rule-based responses if Ollama unavailable.
    """
    
    # CPU-friendly models (smallest first)
    PREFERRED_MODELS = [
        "tinyllama", 
        "phi3:mini", 
        "gemma:2b", 
        "mistral:7b",
        "llama3:latest",
        "llama3",
        "llama2"
    ]
    DEFAULT_MODEL = "tinyllama"
    
    # Token limits for CPU safety
    MAX_TOKENS = 256
    MAX_CONTEXT = 2048
    
    def __init__(self, model: str = None, warm_up: bool = False):
        self.model = model or self.DEFAULT_MODEL
        self._ollama_available = False
        self._check_ollama()

        print(f"[LLMEngine] Initialized with model: {self.model}")
        print(f"[LLMEngine] Ollama available: {self._ollama_available}")

        # S0-E9: real cold-load penalty confirmed live before building this
        # -- a cold Ollama call for this model measured ~10.4s vs ~2.8s once
        # loaded, a ~7.6s tax on whatever request happens to arrive first.
        # Defaults to False deliberately: dozens of call sites construct
        # LLMEngine() throughout this codebase (tests, code_engine,
        # level6, one-off CLI utilities), and warming up on every single
        # one would add a real blocking network call to all of them, not
        # just the live conversational path this is actually meant to
        # help. The real fix is jarvis.py's live service startup calling
        # warm_up() explicitly, once, at boot -- see jarvis.py where
        # self._llm is constructed.
        if warm_up and self._ollama_available:
            self.warm_up()

    def warm_up(self) -> None:
        """
        Force the model into memory now, so the first real user-facing
        request doesn't pay the cold-load penalty. Fire-and-forget: a
        warm-up failure must never block startup or be mistaken for the
        engine being unavailable -- is_available() is unaffected either
        way.
        """
        try:
            import requests
            requests.post(
                "http://localhost:11434/api/generate",
                json={"model": self.model, "prompt": "", "keep_alive": "10m"},
                timeout=30,
            )
            print(f"[LLMEngine] Warm-up complete for {self.model}")
        except Exception as e:
            print(f"[LLMEngine] Warm-up failed (non-fatal): {e}")
    
    def _check_ollama(self):
        """Check if Ollama is running and model is available."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                self._ollama_available = True
                
                # Check if preferred model is available
                available_models = result.stdout.lower()
                found = False
                for model in self.PREFERRED_MODELS:
                    if model.split(":")[0] in available_models:
                        self.model = model
                        found = True
                        break
                
                # If no preferred model found, pick first available
                if not found:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1: # Header + 1 model
                        first_model = lines[1].split()[0]
                        print(f"[LLMEngine] Preferred model not found. Using: {first_model}")
                        self.model = first_model
                        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._ollama_available = False
    
    def is_available(self) -> bool:
        """Check if LLM is ready."""
        return self._ollama_available
    
    def generate(self, prompt: str, system: str = None, 
                max_tokens: int = None) -> LLMResponse:
        """
        Generate response from LLM.
        
        Args:
            prompt: User prompt
            system: System prompt (personality)
            max_tokens: Max tokens to generate
            
        Returns:
            LLMResponse
        """
        if not self._ollama_available:
            return self._fallback_response(prompt)
        
        max_tokens = min(max_tokens or self.MAX_TOKENS, self.MAX_TOKENS)
        
        start_time = time.time()
        
        try:
            # Build request
            request = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "num_ctx": self.MAX_CONTEXT,
                    "temperature": 0.7
                }
            }
            
            if system:
                request["system"] = system
            
            # Call Ollama API. D6: was subprocess(["curl", ...]) --
            # shells out to a separate process per call and depends on
            # curl being on PATH, for no benefit over the requests
            # library already used by generate_stream()/chat_stream()
            # in this same file.
            import requests
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json=request,
                timeout=60,
            )

            if resp.status_code == 200:
                data = resp.json()

                return LLMResponse(
                    text=data.get("response", "").strip(),
                    tokens_used=data.get("eval_count", 0),
                    duration_ms=(time.time() - start_time) * 1000,
                    model=self.model
                )

        except Exception as e:
            print(f"[LLMEngine] Error: {e}")

        return self._fallback_response(prompt)
    
    def generate_stream(self, prompt: str, system: str = None,
                       max_tokens: int = None) -> Generator[str, None, None]:
        """
        Stream response from LLM.
        
        Yields:
            Text chunks as they're generated
        """
        if not self._ollama_available:
            yield self._fallback_response(prompt).text
            return
        
        max_tokens = min(max_tokens or self.MAX_TOKENS, self.MAX_TOKENS)
        
        try:
            import requests
            
            request = {
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict": max_tokens,
                    "num_ctx": self.MAX_CONTEXT
                }
            }
            
            if system:
                request["system"] = system
            
            response = requests.post(
                "http://localhost:11434/api/generate",
                json=request,
                stream=True,
                timeout=60
            )
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                    if data.get("done"):
                        break
                        
        except Exception as e:
            print(f"[LLMEngine] Stream error: {e}")
            yield self._fallback_response(prompt).text

    def chat_stream(self, messages: List[Dict], system: str = None,
                     max_tokens: int = None) -> Generator[str, None, None]:
        """
        Streaming counterpart to chat() -- generate_stream() only wraps
        /api/generate (single prompt), but jarvis.py's real conversation
        loop calls chat() (multi-turn message history via /api/chat), so
        generate_stream() alone couldn't reach the actual live path.
        Built to close that gap (S0-E9). Live-verified: first chunk
        arrived at ~2.3s vs ~23.7s for the full response on a real
        3-sentence answer.

        Yields:
            Text chunks as they're generated
        """
        if not self._ollama_available:
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            yield self._fallback_response(last_user).text
            return

        max_tokens = min(max_tokens or self.MAX_TOKENS, self.MAX_TOKENS)

        try:
            import requests

            payload_messages = messages
            if system:
                payload_messages = [{"role": "system", "content": system}] + messages

            request = {
                "model": self.model,
                "messages": payload_messages,
                "stream": True,
                "options": {
                    "num_predict": max_tokens,
                    "num_ctx": self.MAX_CONTEXT
                }
            }

            response = requests.post(
                "http://localhost:11434/api/chat",
                json=request,
                stream=True,
                timeout=60
            )

            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content")
                    if content:
                        yield content
                    if data.get("done"):
                        break

        except Exception as e:
            print(f"[LLMEngine] Chat stream error: {e}")
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            yield self._fallback_response(last_user).text


    def _fallback_response(self, prompt: str) -> LLMResponse:
        """Rule-based fallback when LLM unavailable."""
        prompt_lower = prompt.lower()
        
        # Simple rule-based responses
        if "explain" in prompt_lower or "what is" in prompt_lower:
            text = "I apologize, but I cannot provide detailed explanations without my language model. Please try again when Ollama is running."
        elif "help" in prompt_lower:
            text = "I can help with commands like: open apps, search the web, send messages, and more. What would you like me to do?"
        elif "hello" in prompt_lower or "hi" in prompt_lower:
            text = "Hello! How can I assist you?"
        else:
            text = "I understand. I'll do my best to help with that command."
        
        return LLMResponse(
            text=text,
            model="fallback",
            duration_ms=0
        )
    
    def chat(self, messages: List[Dict], system: str = None, max_tokens: int = None) -> LLMResponse:
        """
        Multi-turn chat with message history.

        Args:
            messages: List of {"role": "user"|"assistant", "content": str}
            system: System prompt
            max_tokens: Max tokens to generate. Previously hardcoded to
                self.MAX_TOKENS with no per-call override -- generate()
                already had this (callers vary 50-200), chat() didn't,
                which meant the main jarvis.py conversation loop (chat()'s
                only real caller) could never ask for a shorter budget on
                a task that didn't need 256 tokens (S0-E9).

        Returns:
            LLMResponse
        """
        if not self._ollama_available:
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return self._fallback_response(last_user)

        start_time = time.time()
        max_tokens = min(max_tokens or self.MAX_TOKENS, self.MAX_TOKENS)

        try:
            request = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "num_ctx": self.MAX_CONTEXT
                }
            }

            if system:
                request["messages"] = [{"role": "system", "content": system}] + messages
            
            import requests
            resp = requests.post(
                "http://localhost:11434/api/chat",
                json=request,
                timeout=60,
            )

            if resp.status_code == 200:
                data = resp.json()

                return LLMResponse(
                    text=data.get("message", {}).get("content", "").strip(),
                    tokens_used=data.get("eval_count", 0),
                    duration_ms=(time.time() - start_time) * 1000,
                    model=self.model
                )

        except Exception as e:
            print(f"[LLMEngine] Chat error: {e}")
        
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return self._fallback_response(last_user)


def test_llm_engine():
    """Test LLM engine."""
    print("LLM Engine Test")
    print("=" * 50)
    
    engine = LLMEngine()
    
    print(f"Model: {engine.model}")
    print(f"Available: {engine.is_available()}")
    
    if engine.is_available():
        # Test generation
        response = engine.generate("What is 2+2? Answer briefly.")
        print(f"\nResponse: {response.text}")
        print(f"Tokens: {response.tokens_used}")
        print(f"Duration: {response.duration_ms:.0f}ms")
    else:
        print("\nOllama not available. Testing fallback...")
        response = engine.generate("Hello, how are you?")
        print(f"Fallback: {response.text}")


if __name__ == "__main__":
    test_llm_engine()
