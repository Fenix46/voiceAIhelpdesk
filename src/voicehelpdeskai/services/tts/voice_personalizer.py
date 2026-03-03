"""Advanced Voice Personalizer for adaptive speech synthesis based on context and user preferences."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta

from loguru import logger

from .piper_service import ProsodySettings, VoiceGender
from .tts_processor import EmotionType, EmotionSettings
from voicehelpdeskai.services.nlu import IntentPrediction, ITCategory, UrgencyLevel
from voicehelpdeskai.config.manager import get_config_manager


class PersonalityType(Enum):
    """Voice personality types for consistent character."""
    PROFESSIONAL = "professional"      # Formal, clear, authoritative
    FRIENDLY = "friendly"              # Warm, approachable, helpful
    TECHNICAL = "technical"            # Precise, detailed, methodical
    EMPATHETIC = "empathetic"          # Caring, understanding, supportive
    EFFICIENT = "efficient"            # Quick, direct, to-the-point
    EDUCATIONAL = "educational"        # Patient, explanatory, encouraging


class CulturalStyle(Enum):
    """Cultural adaptation styles."""
    ITALIAN_FORMAL = "italian_formal"      # Formal Italian business style
    ITALIAN_CASUAL = "italian_casual"      # Casual Italian conversation
    INTERNATIONAL = "international"        # Neutral international style
    REGIONAL_NORTH = "regional_north"      # Northern Italian style
    REGIONAL_SOUTH = "regional_south"      # Southern Italian style


class SpeechStyle(Enum):
    """Speech delivery styles."""
    CONVERSATIONAL = "conversational"      # Natural conversation pace
    PRESENTATION = "presentation"          # Clear presentation style
    INSTRUCTION = "instruction"            # Step-by-step instruction style
    ANNOUNCEMENT = "announcement"          # Public announcement style
    STORYTELLING = "storytelling"          # Narrative storytelling style


@dataclass
class UserPreferences:
    """User voice preferences and history."""
    user_id: str
    preferred_gender: Optional[VoiceGender] = None
    preferred_speed: float = 1.0
    preferred_pitch: float = 1.0
    preferred_volume: float = 1.0
    preferred_personality: PersonalityType = PersonalityType.PROFESSIONAL
    cultural_style: CulturalStyle = CulturalStyle.ITALIAN_FORMAL
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    feedback_scores: List[float] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ContextAdaptation:
    """Context-based voice adaptation parameters."""
    urgency_level: UrgencyLevel
    problem_category: ITCategory
    user_emotion: Optional[EmotionType]
    conversation_stage: str  # greeting, problem_solving, closing, etc.
    time_of_day: str  # morning, afternoon, evening
    interaction_count: int  # Number of interactions in session
    
    # Calculated adaptations
    speed_modifier: float = 1.0
    pitch_modifier: float = 1.0
    volume_modifier: float = 1.0
    emphasis_strength: float = 1.0
    pause_frequency: float = 1.0


@dataclass 
class PersonalizationProfile:
    """Complete personalization profile for voice synthesis."""
    base_prosody: ProsodySettings
    emotion_settings: EmotionSettings
    personality: PersonalityType
    cultural_style: CulturalStyle
    speech_style: SpeechStyle
    context_adaptations: ContextAdaptation
    confidence_score: float = 0.5  # Confidence in personalization accuracy


class VoicePersonalizer:
    """Advanced voice personalizer for adaptive speech synthesis."""
    
    def __init__(self,
                 enable_user_learning: bool = True,
                 enable_context_adaptation: bool = True,
                 enable_cultural_adaptation: bool = True,
                 adaptation_strength: float = 0.7):
        """Initialize voice personalizer.
        
        Args:
            enable_user_learning: Enable learning from user feedback
            enable_context_adaptation: Enable context-based adaptations
            enable_cultural_adaptation: Enable cultural style adaptations
            adaptation_strength: Strength of personalization (0.0-1.0)
        """
        self.config = get_config_manager().get_config()
        self.enable_user_learning = enable_user_learning
        self.enable_context_adaptation = enable_context_adaptation
        self.enable_cultural_adaptation = enable_cultural_adaptation
        self.adaptation_strength = adaptation_strength
        
        # User preferences storage
        self.user_preferences: Dict[str, UserPreferences] = {}
        
        # Personality templates
        self.personality_templates = self._initialize_personality_templates()
        
        # Cultural style templates
        self.cultural_templates = self._initialize_cultural_templates()
        
        # Context adaptation rules
        self.adaptation_rules = self._initialize_adaptation_rules()
        
        # Performance tracking
        self.stats = {
            'total_personalizations': 0,
            'user_profiles_created': 0,
            'context_adaptations_applied': 0,
            'cultural_adaptations_applied': 0,
            'feedback_received': 0,
            'average_satisfaction': 0.0,
            'learning_updates': 0,
        }
        
        logger.info("VoicePersonalizer initialized")
    
    async def personalize_voice(self,
                               text: str,
                               user_id: Optional[str] = None,
                               intent: Optional[IntentPrediction] = None,
                               conversation_context: Optional[Dict[str, Any]] = None,
                               target_emotion: Optional[EmotionType] = None) -> PersonalizationProfile:
        """Create personalized voice profile for synthesis.
        
        Args:
            text: Text to be synthesized
            user_id: User identifier for personalization
            intent: Intent prediction from NLU
            conversation_context: Current conversation context
            target_emotion: Override emotion for synthesis
            
        Returns:
            Complete personalization profile
        """
        start_time = time.time()
        
        try:
            # Get or create user preferences
            user_prefs = await self._get_user_preferences(user_id) if user_id else None
            
            # Analyze context
            context = await self._analyze_context(intent, conversation_context)
            
            # Determine personality
            personality = await self._determine_personality(text, intent, user_prefs)
            
            # Determine cultural style
            cultural_style = await self._determine_cultural_style(user_prefs, context)
            
            # Determine speech style
            speech_style = await self._determine_speech_style(text, intent, context)
            
            # Create base prosody settings
            base_prosody = await self._create_base_prosody(
                personality, cultural_style, speech_style, user_prefs
            )
            
            # Determine emotion settings
            emotion_settings = await self._determine_emotion_settings(
                text, intent, target_emotion, context
            )
            
            # Apply context adaptations
            if self.enable_context_adaptation:
                context.speed_modifier = await self._calculate_speed_adaptation(intent, context)
                context.pitch_modifier = await self._calculate_pitch_adaptation(intent, context)
                context.volume_modifier = await self._calculate_volume_adaptation(intent, context)
                context.emphasis_strength = await self._calculate_emphasis_adaptation(intent, context)
                self.stats['context_adaptations_applied'] += 1
            
            # Calculate confidence score
            confidence = await self._calculate_personalization_confidence(
                user_prefs, context, intent
            )
            
            # Create personalization profile
            profile = PersonalizationProfile(
                base_prosody=base_prosody,
                emotion_settings=emotion_settings,
                personality=personality,
                cultural_style=cultural_style,
                speech_style=speech_style,
                context_adaptations=context,
                confidence_score=confidence
            )
            
            # Update statistics
            self.stats['total_personalizations'] += 1
            processing_time = time.time() - start_time
            
            # Store interaction for learning
            if user_id and self.enable_user_learning:
                await self._record_interaction(user_id, text, profile, intent)
            
            logger.debug(f"Created personalization profile in {processing_time:.3f}s: "
                        f"personality={personality.value}, confidence={confidence:.3f}")
            
            return profile
            
        except Exception as e:
            logger.error(f"Voice personalization failed: {e}")
            # Return default profile
            return PersonalizationProfile(
                base_prosody=ProsodySettings(),
                emotion_settings=EmotionSettings(),
                personality=PersonalityType.PROFESSIONAL,
                cultural_style=CulturalStyle.ITALIAN_FORMAL,
                speech_style=SpeechStyle.CONVERSATIONAL,
                context_adaptations=ContextAdaptation(
                    urgency_level=UrgencyLevel.MEDIO,
                    problem_category=ITCategory.GENERAL,
                    user_emotion=None,
                    conversation_stage="unknown",
                    time_of_day="unknown",
                    interaction_count=0
                ),
                confidence_score=0.1
            )
    
    async def _get_user_preferences(self, user_id: str) -> UserPreferences:
        """Get or create user preferences."""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreferences(user_id=user_id)
            self.stats['user_profiles_created'] += 1
            
        return self.user_preferences[user_id]
    
    async def _analyze_context(self,
                              intent: Optional[IntentPrediction],
                              conversation_context: Optional[Dict[str, Any]]) -> ContextAdaptation:
        """Analyze context for voice adaptation."""
        
        # Extract context information
        urgency = intent.urgency if intent else UrgencyLevel.MEDIO
        category = intent.category if intent else ITCategory.GENERAL
        
        # Determine conversation stage
        stage = "unknown"
        if conversation_context:
            stage = conversation_context.get('conversation_stage', 'unknown')
        
        # Determine time of day
        current_hour = datetime.now().hour
        if 6 <= current_hour < 12:
            time_of_day = "morning"
        elif 12 <= current_hour < 18:
            time_of_day = "afternoon"
        else:
            time_of_day = "evening"
        
        # Get interaction count
        interaction_count = 0
        if conversation_context:
            interaction_count = conversation_context.get('interaction_count', 0)
        
        return ContextAdaptation(
            urgency_level=urgency,
            problem_category=category,
            user_emotion=None,  # Will be determined later
            conversation_stage=stage,
            time_of_day=time_of_day,
            interaction_count=interaction_count
        )
    
    async def _determine_personality(self,
                                   text: str,
                                   intent: Optional[IntentPrediction],
                                   user_prefs: Optional[UserPreferences]) -> PersonalityType:
        """Determine appropriate personality for synthesis."""
        
        # Use user preference if available
        if user_prefs and user_prefs.preferred_personality:
            return user_prefs.preferred_personality
        
        # Determine based on intent and text
        if intent:
            if intent.intent.value in ["information_request", "installation_request"]:
                return PersonalityType.EDUCATIONAL
            elif intent.urgency == UrgencyLevel.CRITICO:
                return PersonalityType.EFFICIENT
            elif intent.category in [ITCategory.SECURITY, ITCategory.HARDWARE]:
                return PersonalityType.TECHNICAL
        
        # Analyze text for personality cues
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["aiuto", "supporto", "problema", "difficoltà"]):
            return PersonalityType.EMPATHETIC
        elif any(word in text_lower for word in ["veloce", "rapido", "urgente", "subito"]):
            return PersonalityType.EFFICIENT  
        elif any(word in text_lower for word in ["spiegare", "come", "tutorial", "guida"]):
            return PersonalityType.EDUCATIONAL
        
        # Default to professional
        return PersonalityType.PROFESSIONAL
    
    async def _determine_cultural_style(self,
                                       user_prefs: Optional[UserPreferences],
                                       context: ContextAdaptation) -> CulturalStyle:
        """Determine appropriate cultural style."""
        
        # Use user preference if available
        if user_prefs and user_prefs.cultural_style:
            return user_prefs.cultural_style
        
        # Adapt based on context
        if context.conversation_stage == "greeting":
            return CulturalStyle.ITALIAN_FORMAL
        elif context.urgency_level == UrgencyLevel.CRITICO:
            return CulturalStyle.INTERNATIONAL  # More direct
        elif context.interaction_count > 3:
            return CulturalStyle.ITALIAN_CASUAL  # More relaxed after multiple interactions
        
        return CulturalStyle.ITALIAN_FORMAL
    
    async def _determine_speech_style(self,
                                     text: str,
                                     intent: Optional[IntentPrediction],
                                     context: ContextAdaptation) -> SpeechStyle:
        """Determine appropriate speech style."""
        
        # Determine based on intent
        if intent:
            if intent.intent.value == "information_request":
                return SpeechStyle.INSTRUCTION
            elif intent.urgency == UrgencyLevel.CRITICO:
                return SpeechStyle.ANNOUNCEMENT
        
        # Analyze text content
        if len(text.split()) > 50:  # Long text
            return SpeechStyle.PRESENTATION
        elif "passo" in text.lower() or "prima" in text.lower():  # Step-by-step
            return SpeechStyle.INSTRUCTION
        
        return SpeechStyle.CONVERSATIONAL
    
    async def _create_base_prosody(self,
                                  personality: PersonalityType,
                                  cultural_style: CulturalStyle,
                                  speech_style: SpeechStyle,
                                  user_prefs: Optional[UserPreferences]) -> ProsodySettings:
        """Create base prosody settings."""
        
        # Start with personality template
        template = self.personality_templates.get(personality, {})
        
        prosody = ProsodySettings(
            speed=template.get('speed', 1.0),
            pitch=template.get('pitch', 1.0),
            volume=template.get('volume', 1.0),
            emphasis_strength=template.get('emphasis_strength', 1.2)
        )
        
        # Apply cultural style modifications
        cultural_mods = self.cultural_templates.get(cultural_style, {})
        prosody.speed *= cultural_mods.get('speed_modifier', 1.0)
        prosody.pitch *= cultural_mods.get('pitch_modifier', 1.0)
        prosody.volume *= cultural_mods.get('volume_modifier', 1.0)
        
        # Apply speech style modifications
        if speech_style == SpeechStyle.PRESENTATION:
            prosody.speed *= 0.95  # Slightly slower
            prosody.volume *= 1.1  # Slightly louder
        elif speech_style == SpeechStyle.INSTRUCTION:
            prosody.speed *= 0.9   # Slower for clarity
            prosody.emphasis_strength *= 1.3
        elif speech_style == SpeechStyle.ANNOUNCEMENT:
            prosody.volume *= 1.2  # Louder
            prosody.emphasis_strength *= 1.4
        
        # Apply user preferences
        if user_prefs:
            prosody.speed *= user_prefs.preferred_speed
            prosody.pitch *= user_prefs.preferred_pitch
            prosody.volume *= user_prefs.preferred_volume
        
        return prosody
    
    async def _determine_emotion_settings(self,
                                        text: str,
                                        intent: Optional[IntentPrediction],
                                        target_emotion: Optional[EmotionType],
                                        context: ContextAdaptation) -> EmotionSettings:
        """Determine emotion settings for synthesis."""
        
        if target_emotion:
            primary_emotion = target_emotion
            intensity = 0.7
        else:
            # Detect emotion from context
            if context.urgency_level == UrgencyLevel.CRITICO:
                primary_emotion = EmotionType.CONCERNED
                intensity = 0.8
            elif intent and intent.intent.value == "problem_report":
                primary_emotion = EmotionType.EMPATHETIC
                intensity = 0.6
            elif context.conversation_stage == "greeting":
                primary_emotion = EmotionType.FRIENDLY
                intensity = 0.5
            else:
                primary_emotion = EmotionType.PROFESSIONAL
                intensity = 0.4
        
        return EmotionSettings(
            primary_emotion=primary_emotion,
            intensity=intensity
        )
    
    async def _calculate_speed_adaptation(self,
                                        intent: Optional[IntentPrediction],
                                        context: ContextAdaptation) -> float:
        """Calculate speed modification based on context."""
        
        base_speed = 1.0
        
        # Urgency-based adaptation
        if context.urgency_level == UrgencyLevel.CRITICO:
            base_speed *= 1.15  # Faster for critical issues
        elif context.urgency_level == UrgencyLevel.BASSO:
            base_speed *= 0.95  # Slower for low urgency
        
        # Category-based adaptation
        if context.problem_category == ITCategory.SECURITY:
            base_speed *= 0.9   # Slower for security (important details)
        elif context.problem_category == ITCategory.GENERAL:
            base_speed *= 1.05  # Slightly faster for general queries
        
        # Time of day adaptation
        if context.time_of_day == "morning":
            base_speed *= 1.05  # Slightly faster in morning
        elif context.time_of_day == "evening":
            base_speed *= 0.95  # Slower in evening
        
        return base_speed * self.adaptation_strength + (1.0 - self.adaptation_strength)
    
    async def _calculate_pitch_adaptation(self,
                                        intent: Optional[IntentPrediction],
                                        context: ContextAdaptation) -> float:
        """Calculate pitch modification based on context."""
        
        base_pitch = 1.0
        
        # Urgency-based adaptation
        if context.urgency_level == UrgencyLevel.CRITICO:
            base_pitch *= 1.1   # Higher pitch for urgency
        elif context.urgency_level == UrgencyLevel.BASSO:
            base_pitch *= 0.95  # Lower pitch for calm situations
        
        # Emotional adaptation
        if context.user_emotion == EmotionType.ANGRY:
            base_pitch *= 0.9   # Lower pitch for angry users
        elif context.user_emotion == EmotionType.HAPPY:
            base_pitch *= 1.05  # Higher pitch for positive interactions
        
        return base_pitch * self.adaptation_strength + (1.0 - self.adaptation_strength)
    
    async def _calculate_volume_adaptation(self,
                                         intent: Optional[IntentPrediction],
                                         context: ContextAdaptation) -> float:
        """Calculate volume modification based on context."""
        
        base_volume = 1.0
        
        # Urgency-based adaptation
        if context.urgency_level == UrgencyLevel.CRITICO:
            base_volume *= 1.1  # Louder for critical issues
        
        # Conversation stage adaptation
        if context.conversation_stage == "greeting":
            base_volume *= 1.05  # Slightly louder for greetings
        elif context.conversation_stage == "closing":
            base_volume *= 0.95  # Softer for closings
        
        return base_volume * self.adaptation_strength + (1.0 - self.adaptation_strength)
    
    async def _calculate_emphasis_adaptation(self,
                                           intent: Optional[IntentPrediction],
                                           context: ContextAdaptation) -> float:
        """Calculate emphasis strength based on context."""
        
        base_emphasis = 1.2
        
        # Category-based adaptation
        if context.problem_category in [ITCategory.SECURITY, ITCategory.HARDWARE]:
            base_emphasis *= 1.3  # Stronger emphasis for critical categories
        elif context.problem_category == ITCategory.GENERAL:
            base_emphasis *= 0.9  # Less emphasis for general queries
        
        # Urgency-based adaptation
        if context.urgency_level == UrgencyLevel.CRITICO:
            base_emphasis *= 1.4  # Strong emphasis for critical issues
        
        return base_emphasis * self.adaptation_strength + (1.2 * (1.0 - self.adaptation_strength))
    
    async def _calculate_personalization_confidence(self,
                                                   user_prefs: Optional[UserPreferences],
                                                   context: ContextAdaptation,
                                                   intent: Optional[IntentPrediction]) -> float:
        """Calculate confidence in personalization accuracy."""
        
        confidence = 0.5  # Base confidence
        
        # User preferences available
        if user_prefs:
            confidence += 0.2
            # Interaction history
            if len(user_prefs.interaction_history) > 5:
                confidence += 0.1
            # Feedback scores
            if user_prefs.feedback_scores:
                avg_feedback = sum(user_prefs.feedback_scores) / len(user_prefs.feedback_scores)
                confidence += (avg_feedback - 3.0) * 0.1  # Assuming 1-5 scale
        
        # Context clarity
        if intent and intent.confidence > 0.8:
            confidence += 0.1
        
        # Context completeness
        if context.conversation_stage != "unknown":
            confidence += 0.05
        if context.urgency_level != UrgencyLevel.MEDIO:
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    async def _record_interaction(self,
                                user_id: str,
                                text: str,
                                profile: PersonalizationProfile,
                                intent: Optional[IntentPrediction]) -> None:
        """Record interaction for user learning."""
        
        if user_id not in self.user_preferences:
            return
        
        interaction_record = {
            'timestamp': datetime.now().isoformat(),
            'text_length': len(text),
            'personality': profile.personality.value,
            'cultural_style': profile.cultural_style.value,
            'speech_style': profile.speech_style.value,
            'confidence': profile.confidence_score,
            'intent': intent.intent.value if intent else None,
            'urgency': intent.urgency.value if intent else None,
        }
        
        user_prefs = self.user_preferences[user_id]
        user_prefs.interaction_history.append(interaction_record)
        user_prefs.last_updated = datetime.now()
        
        # Limit history size
        if len(user_prefs.interaction_history) > 100:
            user_prefs.interaction_history = user_prefs.interaction_history[-50:]
    
    async def record_user_feedback(self,
                                  user_id: str,
                                  satisfaction_score: float,
                                  feedback_details: Optional[Dict[str, Any]] = None) -> None:
        """Record user feedback for learning.
        
        Args:
            user_id: User identifier
            satisfaction_score: Satisfaction score (1.0-5.0)
            feedback_details: Optional detailed feedback
        """
        if user_id not in self.user_preferences:
            return
        
        user_prefs = self.user_preferences[user_id]
        user_prefs.feedback_scores.append(satisfaction_score)
        user_prefs.last_updated = datetime.now()
        
        # Limit feedback history
        if len(user_prefs.feedback_scores) > 50:
            user_prefs.feedback_scores = user_prefs.feedback_scores[-25:]
        
        # Update learning based on feedback
        if self.enable_user_learning:
            await self._update_preferences_from_feedback(user_id, satisfaction_score, feedback_details)
        
        self.stats['feedback_received'] += 1
        self.stats['average_satisfaction'] = (
            (self.stats['average_satisfaction'] * (self.stats['feedback_received'] - 1) + satisfaction_score) /
            self.stats['feedback_received']
        )
        
        logger.info(f"Recorded feedback for user {user_id}: {satisfaction_score}/5.0")
    
    async def _update_preferences_from_feedback(self,
                                              user_id: str,
                                              satisfaction_score: float,
                                              feedback_details: Optional[Dict[str, Any]]) -> None:
        """Update user preferences based on feedback."""
        
        user_prefs = self.user_preferences[user_id]
        
        # Adaptive learning rate based on feedback confidence
        learning_rate = 0.1 if satisfaction_score >= 4.0 else 0.05
        
        if feedback_details:
            # Adjust preferences based on specific feedback
            if 'speed' in feedback_details:
                speed_feedback = feedback_details['speed']  # "too_fast", "too_slow", "good"
                if speed_feedback == "too_fast":
                    user_prefs.preferred_speed = max(user_prefs.preferred_speed - learning_rate, 0.7)
                elif speed_feedback == "too_slow":
                    user_prefs.preferred_speed = min(user_prefs.preferred_speed + learning_rate, 1.3)
            
            if 'pitch' in feedback_details:
                pitch_feedback = feedback_details['pitch']
                if pitch_feedback == "too_high":
                    user_prefs.preferred_pitch = max(user_prefs.preferred_pitch - learning_rate, 0.7)
                elif pitch_feedback == "too_low":
                    user_prefs.preferred_pitch = min(user_prefs.preferred_pitch + learning_rate, 1.3)
            
            if 'volume' in feedback_details:
                volume_feedback = feedback_details['volume']
                if volume_feedback == "too_loud":
                    user_prefs.preferred_volume = max(user_prefs.preferred_volume - learning_rate, 0.5)
                elif volume_feedback == "too_quiet":
                    user_prefs.preferred_volume = min(user_prefs.preferred_volume + learning_rate, 1.5)
        
        self.stats['learning_updates'] += 1
    
    def _initialize_personality_templates(self) -> Dict[PersonalityType, Dict[str, float]]:
        """Initialize personality-based voice templates."""
        return {
            PersonalityType.PROFESSIONAL: {
                'speed': 1.0,
                'pitch': 1.0,
                'volume': 1.0,
                'emphasis_strength': 1.1
            },
            PersonalityType.FRIENDLY: {
                'speed': 1.05,
                'pitch': 1.05,
                'volume': 1.05,
                'emphasis_strength': 1.2
            },
            PersonalityType.TECHNICAL: {
                'speed': 0.95,
                'pitch': 0.98,
                'volume': 1.0,
                'emphasis_strength': 1.3
            },
            PersonalityType.EMPATHETIC: {
                'speed': 0.9,
                'pitch': 0.95,
                'volume': 0.95,
                'emphasis_strength': 1.1
            },
            PersonalityType.EFFICIENT: {
                'speed': 1.15,
                'pitch': 1.02,
                'volume': 1.05,
                'emphasis_strength': 1.4
            },
            PersonalityType.EDUCATIONAL: {
                'speed': 0.9,
                'pitch': 1.0,
                'volume': 1.0,
                'emphasis_strength': 1.25
            }
        }
    
    def _initialize_cultural_templates(self) -> Dict[CulturalStyle, Dict[str, float]]:
        """Initialize cultural style templates."""
        return {
            CulturalStyle.ITALIAN_FORMAL: {
                'speed_modifier': 0.98,
                'pitch_modifier': 1.0,
                'volume_modifier': 1.0
            },
            CulturalStyle.ITALIAN_CASUAL: {
                'speed_modifier': 1.05,
                'pitch_modifier': 1.02,
                'volume_modifier': 1.02
            },
            CulturalStyle.INTERNATIONAL: {
                'speed_modifier': 1.0,
                'pitch_modifier': 1.0,
                'volume_modifier': 1.0
            },
            CulturalStyle.REGIONAL_NORTH: {
                'speed_modifier': 0.95,
                'pitch_modifier': 0.98,
                'volume_modifier': 0.98
            },
            CulturalStyle.REGIONAL_SOUTH: {
                'speed_modifier': 1.08,
                'pitch_modifier': 1.05,
                'volume_modifier': 1.05
            }
        }
    
    def _initialize_adaptation_rules(self) -> Dict[str, Any]:
        """Initialize context adaptation rules."""
        return {
            'urgency_multipliers': {
                UrgencyLevel.CRITICO: {'speed': 1.15, 'pitch': 1.1, 'volume': 1.1},
                UrgencyLevel.ALTO: {'speed': 1.05, 'pitch': 1.02, 'volume': 1.02},
                UrgencyLevel.MEDIO: {'speed': 1.0, 'pitch': 1.0, 'volume': 1.0},
                UrgencyLevel.BASSO: {'speed': 0.95, 'pitch': 0.98, 'volume': 0.98}
            },
            'category_multipliers': {
                ITCategory.SECURITY: {'speed': 0.9, 'emphasis': 1.4},
                ITCategory.HARDWARE: {'speed': 0.95, 'emphasis': 1.3},
                ITCategory.SOFTWARE: {'speed': 1.0, 'emphasis': 1.2},
                ITCategory.NETWORK: {'speed': 0.98, 'emphasis': 1.25},
                ITCategory.GENERAL: {'speed': 1.05, 'emphasis': 1.1}
            }
        }
    
    def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Get user preferences for external access."""
        return self.user_preferences.get(user_id)
    
    async def update_user_preferences(self,
                                    user_id: str,
                                    preferences: Dict[str, Any]) -> None:
        """Update user preferences manually."""
        
        user_prefs = await self._get_user_preferences(user_id)
        
        if 'preferred_gender' in preferences:
            user_prefs.preferred_gender = VoiceGender(preferences['preferred_gender'])
        if 'preferred_speed' in preferences:
            user_prefs.preferred_speed = preferences['preferred_speed']
        if 'preferred_pitch' in preferences:
            user_prefs.preferred_pitch = preferences['preferred_pitch']
        if 'preferred_volume' in preferences:
            user_prefs.preferred_volume = preferences['preferred_volume']
        if 'preferred_personality' in preferences:
            user_prefs.preferred_personality = PersonalityType(preferences['preferred_personality'])
        if 'cultural_style' in preferences:
            user_prefs.cultural_style = CulturalStyle(preferences['cultural_style'])
        
        user_prefs.last_updated = datetime.now()
        
        logger.info(f"Updated preferences for user {user_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get personalization statistics."""
        stats = self.stats.copy()
        
        stats.update({
            'active_user_profiles': len(self.user_preferences),
            'personality_templates': len(self.personality_templates),
            'cultural_templates': len(self.cultural_templates),
            'adaptation_strength': self.adaptation_strength,
            'features_enabled': {
                'user_learning': self.enable_user_learning,
                'context_adaptation': self.enable_context_adaptation,
                'cultural_adaptation': self.enable_cultural_adaptation,
            }
        })
        
        if stats['total_personalizations'] > 0:
            stats['context_adaptation_rate'] = (stats['context_adaptations_applied'] / stats['total_personalizations']) * 100
            stats['cultural_adaptation_rate'] = (stats['cultural_adaptations_applied'] / stats['total_personalizations']) * 100
        
        if self.user_preferences:
            # Calculate user engagement metrics
            active_users = sum(1 for prefs in self.user_preferences.values() 
                             if (datetime.now() - prefs.last_updated).days <= 7)
            stats['active_users_7d'] = active_users
            
            avg_interactions = sum(len(prefs.interaction_history) for prefs in self.user_preferences.values()) / len(self.user_preferences)
            stats['avg_interactions_per_user'] = avg_interactions
        
        return stats