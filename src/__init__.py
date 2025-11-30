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

# Pipeline API (AssemblyAI)
from .master_pipeline_api import MasterPipelineAPI, process_outliers_playlist_api
from .youtube_transcriber_assemblyai import YouTubeTranscriberAssemblyAI

# Agents
from .investment_agent import InvestmentAnalysisAgent
from .marketing_agent import MarketingAgent

# Utilities
from .podcast_start_detector import PodcastStartDetector
from .utils import validate_audio_file

__all__ = [
    # Models
    'TranscriptOutput',
    'EpisodeMetadata',
    'Utterance',
    'Participant',
    'ProcessingNote',
    
    # Pipeline
    'MasterPipelineAPI',
    'process_outliers_playlist_api',
    'YouTubeTranscriberAssemblyAI',
    
    # Agents
    'InvestmentAnalysisAgent',
    'MarketingAgent',
    
    # Utilities
    'PodcastStartDetector',
    'validate_audio_file',
]
