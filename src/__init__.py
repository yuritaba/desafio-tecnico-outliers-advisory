"""
Pipeline completo de processamento de podcasts financeiros.
YouTube → Transcrição → Análise → Marketing
"""

__version__ = "2.0.0"

# Core models
from .models import (
    TranscriptOutput,
    EpisodeMetadata,
    Utterance,
    Participant,
    ProcessingNote
)

# Transcription pipeline
from .pipeline import PodcastPipeline
from .transcriber import Transcriber
from .diarizer import Diarizer
from .aligner import Aligner
from .speaker_identifier import SpeakerIdentifier
from .text_cleaner import TextCleaner

# Extended pipeline
from .youtube_extractor import YouTubePlaylistExtractor
from .investment_agent import InvestmentAnalysisAgent
from .marketing_agent import MarketingAgent
from .master_pipeline import MasterPipeline, process_outliers_playlist

__all__ = [
    # Models
    'TranscriptOutput',
    'EpisodeMetadata',
    'Utterance',
    'Participant',
    'ProcessingNote',
    
    # Transcription
    'PodcastPipeline',
    'Transcriber',
    'Diarizer',
    'Aligner',
    'SpeakerIdentifier',
    'TextCleaner',
    
    # Extended pipeline
    'YouTubePlaylistExtractor',
    'InvestmentAnalysisAgent',
    'MarketingAgent',
    'MasterPipeline',
    'process_outliers_playlist',
]
