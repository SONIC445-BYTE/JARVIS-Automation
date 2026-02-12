"""
Voice ID - Local Voice Authentication
=======================================
Voice embedding and matching for identity verification.

Sprint 5: Trust & Identity
"""

import os
import json
import time
import hashlib
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import numpy as np


@dataclass
class VoiceProfile:
    """Stored voice profile."""
    profile_id: str
    name: str
    embeddings: List[List[float]]  # Multiple enrollment samples
    created_at: float = field(default_factory=time.time)
    last_verified: Optional[float] = None
    verification_count: int = 0
    
    def get_centroid(self) -> List[float]:
        """Get average embedding for matching."""
        if not self.embeddings:
            return []
        return [sum(e[i] for e in self.embeddings) / len(self.embeddings) 
               for i in range(len(self.embeddings[0]))]


class VoiceID:
    """
    Local voice identification.
    
    Uses simple spectral features for voice matching.
    NOT a security feature - for convenience only.
    
    For critical actions, combine with PIN/confirmation.
    """
    
    SIMILARITY_THRESHOLD = 0.75  # Minimum cosine similarity
    MIN_ENROLLMENT_SAMPLES = 3
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        if profiles_dir is None:
            profiles_dir = Path(__file__).parent.parent / "data" / "voice_profiles"
        
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        self._profiles: Dict[str, VoiceProfile] = {}
        self._active_profile: Optional[str] = None
        
        self._load_profiles()
    
    def _load_profiles(self):
        """Load saved voice profiles."""
        for profile_file in self.profiles_dir.glob("*.json"):
            try:
                with open(profile_file, 'r') as f:
                    data = json.load(f)
                profile = VoiceProfile(**data)
                self._profiles[profile.profile_id] = profile
            except Exception as e:
                print(f"[VoiceID] Error loading profile: {e}")
    
    def _save_profile(self, profile: VoiceProfile):
        """Save a profile to disk."""
        profile_file = self.profiles_dir / f"{profile.profile_id}.json"
        with open(profile_file, 'w') as f:
            json.dump(asdict(profile), f)
    
    def create_profile(self, name: str) -> VoiceProfile:
        """
        Create a new voice profile.
        
        Args:
            name: Display name for profile
            
        Returns:
            Created profile (needs enrollment)
        """
        profile_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()[:8]
        
        profile = VoiceProfile(
            profile_id=profile_id,
            name=name,
            embeddings=[]
        )
        
        self._profiles[profile_id] = profile
        self._save_profile(profile)
        
        print(f"[VoiceID] Created profile: {name} ({profile_id})")
        return profile
    
    def enroll_sample(self, profile_id: str, audio_data: bytes) -> bool:
        """
        Add enrollment sample to profile.
        
        Args:
            profile_id: Profile to enroll
            audio_data: Audio sample bytes
            
        Returns:
            True if successful, False otherwise
        """
        profile = self._profiles.get(profile_id)
        if not profile:
            return False
        
        # Extract embedding
        embedding = self._extract_embedding(audio_data)
        if embedding:
            profile.embeddings.append(embedding)
            self._save_profile(profile)
            return True
        
        return False
    
    def _extract_embedding(self, audio_data: bytes) -> Optional[List[float]]:
        """
        Extract voice embedding from audio.
        
        Simple spectral features (MFCC-like).
        In production, use proper speaker embedding model.
        """
        try:
            import numpy as np
            
            # Convert bytes to numpy (assume 16-bit PCM)
            audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            if len(audio) < 160:
                return None
            
            # Normalize
            audio = audio / (np.abs(audio).max() + 1e-6)
            
            # Simple features: mean, std, energy per segment
            num_segments = 16
            segment_size = len(audio) // num_segments
            
            features = []
            for i in range(num_segments):
                segment = audio[i * segment_size:(i + 1) * segment_size]
                features.extend([
                    float(np.mean(segment)),
                    float(np.std(segment)),
                    float(np.mean(segment ** 2))  # Energy
                ])
            
            return features
            
        except Exception as e:
            print(f"[VoiceID] Embedding error: {e}")
            return None
    
    def verify(self, audio_data: bytes, profile_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Verify speaker against profile(s).
        
        Args:
            audio_data: Audio sample to verify
            profile_id: Specific profile to match (None = match any)
            
        Returns:
            (matched, profile_id or None)
        """
        embedding = self._extract_embedding(audio_data)
        if not embedding:
            return (False, None)
        
        profiles_to_check = (
            [self._profiles.get(profile_id)] if profile_id 
            else self._profiles.values()
        )
        
        best_match = None
        best_score = 0.0
        
        for profile in profiles_to_check:
            if not profile or len(profile.embeddings) < self.MIN_ENROLLMENT_SAMPLES:
                continue
            
            centroid = profile.get_centroid()
            if not centroid:
                continue
            
            score = self._cosine_similarity(embedding, centroid)
            
            if score > best_score and score >= self.SIMILARITY_THRESHOLD:
                best_score = score
                best_match = profile
        
        if best_match:
            best_match.last_verified = time.time()
            best_match.verification_count += 1
            self._active_profile = best_match.profile_id
            self._save_profile(best_match)
            return (True, best_match.profile_id)
        
        return (False, None)
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between embeddings."""
        import numpy as np
        
        a = np.array(a)
        b = np.array(b)
        
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot / (norm_a * norm_b))
    
    def get_active_profile(self) -> Optional[VoiceProfile]:
        """Get currently active (verified) profile."""
        if self._active_profile:
            return self._profiles.get(self._active_profile)
        return None
    
    def clear_active(self):
        """Clear active profile (log out)."""
        self._active_profile = None
    
    def delete_profile(self, profile_id: str) -> bool:
        """Delete a voice profile."""
        if profile_id not in self._profiles:
            return False
        
        del self._profiles[profile_id]
        
        profile_file = self.profiles_dir / f"{profile_id}.json"
        if profile_file.exists():
            profile_file.unlink()
        
        if self._active_profile == profile_id:
            self._active_profile = None
        
        return True
    
    def list_profiles(self) -> List[Dict]:
        """List all profiles."""
        return [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "enrolled_samples": len(p.embeddings),
                "is_enrolled": len(p.embeddings) >= self.MIN_ENROLLMENT_SAMPLES,
                "verification_count": p.verification_count
            }
            for p in self._profiles.values()
        ]


def test_voice_id():
    """Test voice ID."""
    print("Voice ID Test")
    print("=" * 50)
    
    vid = VoiceID()
    
    # Create profile
    profile = vid.create_profile("Test User")
    print(f"Created: {profile.name}")
    
    # List profiles
    profiles = vid.list_profiles()
    print(f"Profiles: {profiles}")


if __name__ == "__main__":
    test_voice_id()
