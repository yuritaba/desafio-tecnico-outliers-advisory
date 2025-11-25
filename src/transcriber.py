"""
Módulo de Speech-to-Text para transcrição de áudio.
Suporta Whisper local, OpenAI API e WhisperX.
"""
import os
import logging
from typing import List, Literal, Optional, Dict, Any
from pathlib import Path

from .models import RawTranscriptionSegment
from .utils import validate_audio_file, load_env_var


class Transcriber:
    """
    Classe para transcrição de áudio usando diferentes backends.
    """
    
    def __init__(
        self,
        backend: Literal["local", "openai", "whisperx"] = "local",
        model: str = "large-v3",
        language: str = "pt",
        device: Optional[str] = None
    ):
        """
        Inicializa o transcriber.
        
        Args:
            backend: Backend a usar (local, openai, whisperx)
            model: Modelo Whisper a usar
            language: Código do idioma (pt, en, etc)
            device: Device para computação (cuda, cpu, ou None para auto)
        """
        self.backend = backend
        self.model_name = model
        self.language = language
        self.device = device
        self.logger = logging.getLogger('podcast_pipeline.transcriber')
        
        self._model = None
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Inicializa o backend escolhido"""
        self.logger.info(f"Inicializando backend de transcrição: {self.backend}")
        
        if self.backend == "local":
            self._initialize_local_whisper()
        elif self.backend == "openai":
            self._initialize_openai_whisper()
        elif self.backend == "whisperx":
            self._initialize_whisperx()
        else:
            raise ValueError(f"Backend não suportado: {self.backend}")
    
    def _initialize_local_whisper(self):
        """Inicializa Whisper local"""
        try:
            import whisper
            import torch
            
            # Determina device
            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            
            self.logger.info(f"Carregando modelo Whisper '{self.model_name}' em {self.device}")
            self._model = whisper.load_model(self.model_name, device=self.device)
            self.logger.info("Modelo Whisper carregado com sucesso")
            
        except ImportError:
            raise ImportError(
                "openai-whisper não está instalado. "
                "Instale com: pip install openai-whisper"
            )
    
    def _initialize_openai_whisper(self):
        """Inicializa cliente OpenAI"""
        try:
            from openai import OpenAI
            
            api_key = load_env_var("OPENAI_API_KEY", required=True)
            self._model = OpenAI(api_key=api_key)
            self.logger.info("Cliente OpenAI inicializado")
            
        except ImportError:
            raise ImportError(
                "openai não está instalado. "
                "Instale com: pip install openai"
            )
    
    def _initialize_whisperx(self):
        """Inicializa WhisperX"""
        try:
            import whisperx
            import torch
            
            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            
            self.logger.info(f"Carregando WhisperX '{self.model_name}' em {self.device}")
            self._model = whisperx.load_model(
                self.model_name,
                device=self.device,
                language=self.language
            )
            self.logger.info("WhisperX carregado com sucesso")
            
        except ImportError:
            raise ImportError(
                "whisperx não está instalado. "
                "Instale com: pip install whisperx"
            )
    
    def transcribe(self, audio_path: str) -> List[RawTranscriptionSegment]:
        """
        Transcreve um arquivo de áudio.
        
        Args:
            audio_path: Caminho para o arquivo de áudio
        
        Returns:
            Lista de segmentos transcritos com timestamps
        
        Raises:
            FileNotFoundError: Se o arquivo não existe
            ValueError: Se o formato não é suportado
        """
        if not validate_audio_file(audio_path):
            raise ValueError(f"Arquivo de áudio inválido: {audio_path}")
        
        self.logger.info(f"Iniciando transcrição de: {audio_path}")
        
        if self.backend == "local":
            return self._transcribe_local(audio_path)
        elif self.backend == "openai":
            return self._transcribe_openai(audio_path)
        elif self.backend == "whisperx":
            return self._transcribe_whisperx(audio_path)
        else:
            raise ValueError(f"Backend não implementado: {self.backend}")
    
    def _transcribe_local(self, audio_path: str) -> List[RawTranscriptionSegment]:
        """Transcreve usando Whisper local"""
        import whisper
        
        # Transcreve com word-level timestamps
        result = self._model.transcribe(
            audio_path,
            language=self.language,
            task="transcribe",
            verbose=False,
            word_timestamps=True
        )
        
        segments = []
        for segment in result.get("segments", []):
            segments.append(RawTranscriptionSegment(
                start=segment["start"],
                end=segment["end"],
                text=segment["text"].strip(),
                confidence=segment.get("confidence")
            ))
        
        self.logger.info(f"Transcrição completa: {len(segments)} segmentos")
        return segments
    
    def _transcribe_openai(self, audio_path: str) -> List[RawTranscriptionSegment]:
        """Transcreve usando API OpenAI"""
        # OpenAI API não retorna timestamps detalhados no response padrão
        # Precisamos usar o formato verbose_json
        
        with open(audio_path, "rb") as audio_file:
            response = self._model.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=self.language,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        
        segments = []
        
        # Se temos acesso aos segments
        if hasattr(response, 'segments'):
            for segment in response.segments:
                segments.append(RawTranscriptionSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                    confidence=None  # API OpenAI não retorna confidence
                ))
        else:
            # Fallback: cria um único segmento
            self.logger.warning(
                "OpenAI API não retornou segmentos detalhados. "
                "Criando um único segmento."
            )
            segments.append(RawTranscriptionSegment(
                start=0.0,
                end=0.0,  # Será necessário obter duração por outro meio
                text=response.text,
                confidence=None
            ))
        
        self.logger.info(f"Transcrição completa: {len(segments)} segmentos")
        return segments
    
    def _transcribe_whisperx(self, audio_path: str) -> List[RawTranscriptionSegment]:
        """Transcreve usando WhisperX"""
        import whisperx
        
        # Carrega áudio
        audio = whisperx.load_audio(audio_path)
        
        # Transcreve
        result = self._model.transcribe(audio, batch_size=16)
        
        # WhisperX retorna formato similar ao Whisper
        segments = []
        for segment in result.get("segments", []):
            segments.append(RawTranscriptionSegment(
                start=segment["start"],
                end=segment["end"],
                text=segment["text"].strip(),
                confidence=segment.get("confidence")
            ))
        
        self.logger.info(f"Transcrição completa: {len(segments)} segmentos")
        return segments
    
    def transcribe_with_metadata(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcreve e retorna metadata adicional.
        
        Args:
            audio_path: Caminho para o arquivo de áudio
        
        Returns:
            Dict com 'segments', 'language', 'duration', etc
        """
        from .utils import get_audio_duration
        
        segments = self.transcribe(audio_path)
        
        return {
            "segments": segments,
            "language": self.language,
            "model": self.model_name,
            "backend": self.backend,
            "duration": get_audio_duration(audio_path),
            "segment_count": len(segments)
        }


def create_transcriber_from_config(config: Optional[Dict] = None) -> Transcriber:
    """
    Factory function para criar transcriber a partir de configuração.
    
    Args:
        config: Dict com configurações. Se None, usa variáveis de ambiente.
    
    Returns:
        Instância configurada de Transcriber
    """
    if config is None:
        config = {
            "backend": os.getenv("WHISPER_BACKEND", "local"),
            "model": os.getenv("WHISPER_MODEL", "large-v3"),
            "language": os.getenv("LANGUAGE", "pt")
        }
    
    return Transcriber(
        backend=config.get("backend", "local"),
        model=config.get("model", "large-v3"),
        language=config.get("language", "pt"),
        device=config.get("device")
    )
