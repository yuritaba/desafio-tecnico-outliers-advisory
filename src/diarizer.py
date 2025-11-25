"""
Módulo de diarização para identificação de speakers.
Suporta pyannote.audio e integração com WhisperX.
"""
import os
import logging
from typing import List, Optional, Dict, Any, Literal
from pathlib import Path

from .models import DiarizationSegment
from .utils import validate_audio_file, load_env_var


class Diarizer:
    """
    Classe para diarização de áudio (identificação de quem está falando).
    """
    
    def __init__(
        self,
        backend: Literal["pyannote", "whisperx"] = "pyannote",
        model_name: Optional[str] = None,
        num_speakers: Optional[int] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        device: Optional[str] = None
    ):
        """
        Inicializa o diarizer.
        
        Args:
            backend: Backend a usar (pyannote, whisperx)
            model_name: Nome do modelo (ex: pyannote/speaker-diarization-3.1)
            num_speakers: Número exato de speakers (se conhecido)
            min_speakers: Número mínimo de speakers
            max_speakers: Número máximo de speakers
            device: Device para computação (cuda, cpu, ou None para auto)
        """
        self.backend = backend
        self.model_name = model_name or os.getenv(
            "PYANNOTE_MODEL",
            "pyannote/speaker-diarization-3.1"
        )
        self.num_speakers = num_speakers
        self.min_speakers = min_speakers or 1
        self.max_speakers = max_speakers or int(os.getenv("MAX_SPEAKERS", "2"))
        self.device = device
        self.logger = logging.getLogger('podcast_pipeline.diarizer')
        
        self._pipeline = None
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Inicializa o backend de diarização"""
        self.logger.info(f"Inicializando backend de diarização: {self.backend}")
        
        if self.backend == "pyannote":
            self._initialize_pyannote()
        elif self.backend == "whisperx":
            self._initialize_whisperx()
        else:
            raise ValueError(f"Backend não suportado: {self.backend}")
    
    def _initialize_pyannote(self):
        """Inicializa pyannote.audio"""
        try:
            from pyannote.audio import Pipeline
            import torch
            
            # Determina device
            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Carrega token do HuggingFace
            hf_token = load_env_var("HF_TOKEN", required=True)
            
            self.logger.info(
                f"Carregando pipeline pyannote '{self.model_name}' em {self.device}"
            )
            
            self._pipeline = Pipeline.from_pretrained(
                self.model_name,
                use_auth_token=hf_token
            )
            
            # Move para device
            self._pipeline.to(torch.device(self.device))
            
            self.logger.info("Pipeline pyannote carregado com sucesso")
            
        except ImportError:
            raise ImportError(
                "pyannote.audio não está instalado. "
                "Instale com: pip install pyannote.audio"
            )
        except Exception as e:
            self.logger.error(f"Erro ao carregar pyannote: {e}")
            raise
    
    def _initialize_whisperx(self):
        """Inicializa diarização do WhisperX"""
        try:
            import whisperx
            import torch
            
            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # WhisperX usa pyannote internamente, então precisa do token
            hf_token = load_env_var("HF_TOKEN", required=True)
            
            self.logger.info("Inicializando diarização WhisperX")
            
            # WhisperX carrega o modelo on-demand, então só guardamos o token
            self._hf_token = hf_token
            
            self.logger.info("WhisperX diarização inicializado")
            
        except ImportError:
            raise ImportError(
                "whisperx não está instalado. "
                "Instale com: pip install whisperx"
            )
    
    def diarize(self, audio_path: str) -> List[DiarizationSegment]:
        """
        Realiza diarização de um arquivo de áudio.
        
        Args:
            audio_path: Caminho para o arquivo de áudio
        
        Returns:
            Lista de segmentos com identificação de speaker
        
        Raises:
            FileNotFoundError: Se o arquivo não existe
            ValueError: Se o formato não é suportado
        """
        if not validate_audio_file(audio_path):
            raise ValueError(f"Arquivo de áudio inválido: {audio_path}")
        
        self.logger.info(f"Iniciando diarização de: {audio_path}")
        
        if self.backend == "pyannote":
            return self._diarize_pyannote(audio_path)
        elif self.backend == "whisperx":
            return self._diarize_whisperx(audio_path)
        else:
            raise ValueError(f"Backend não implementado: {self.backend}")
    
    def _diarize_pyannote(self, audio_path: str) -> List[DiarizationSegment]:
        """Realiza diarização usando pyannote"""
        # Prepara parâmetros
        params = {}
        
        if self.num_speakers is not None:
            params["num_speakers"] = self.num_speakers
        else:
            params["min_speakers"] = self.min_speakers
            params["max_speakers"] = self.max_speakers
        
        # Executa diarização
        self.logger.info(f"Executando diarização com parâmetros: {params}")
        diarization = self._pipeline(audio_path, **params)
        
        # Converte para nosso formato
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(DiarizationSegment(
                start=turn.start,
                end=turn.end,
                speaker=speaker
            ))
        
        self.logger.info(
            f"Diarização completa: {len(segments)} segmentos, "
            f"{len(set(s.speaker for s in segments))} speakers únicos"
        )
        
        return segments
    
    def _diarize_whisperx(self, audio_path: str) -> List[DiarizationSegment]:
        """Realiza diarização usando WhisperX"""
        import whisperx
        
        # Carrega áudio
        audio = whisperx.load_audio(audio_path)
        
        # Carrega modelo de diarização
        diarize_model = whisperx.DiarizationPipeline(
            use_auth_token=self._hf_token,
            device=self.device
        )
        
        # Executa diarização
        params = {}
        if self.num_speakers is not None:
            params["num_speakers"] = self.num_speakers
        else:
            params["min_speakers"] = self.min_speakers
            params["max_speakers"] = self.max_speakers
        
        self.logger.info(f"Executando diarização WhisperX com parâmetros: {params}")
        diarization = diarize_model(audio, **params)
        
        # Converte para nosso formato
        segments = []
        for segment in diarization:
            segments.append(DiarizationSegment(
                start=segment["start"],
                end=segment["end"],
                speaker=segment["speaker"]
            ))
        
        self.logger.info(
            f"Diarização completa: {len(segments)} segmentos, "
            f"{len(set(s.speaker for s in segments))} speakers únicos"
        )
        
        return segments
    
    def diarize_with_stats(self, audio_path: str) -> Dict[str, Any]:
        """
        Realiza diarização e retorna estatísticas.
        
        Args:
            audio_path: Caminho para o arquivo de áudio
        
        Returns:
            Dict com 'segments', 'speakers', 'speaker_stats', etc
        """
        segments = self.diarize(audio_path)
        
        # Calcula estatísticas por speaker
        speaker_stats = {}
        for segment in segments:
            if segment.speaker not in speaker_stats:
                speaker_stats[segment.speaker] = {
                    "total_time": 0.0,
                    "segment_count": 0,
                    "speaker_id": segment.speaker
                }
            
            duration = segment.end - segment.start
            speaker_stats[segment.speaker]["total_time"] += duration
            speaker_stats[segment.speaker]["segment_count"] += 1
        
        # Ordena speakers por tempo de fala
        sorted_speakers = sorted(
            speaker_stats.values(),
            key=lambda x: x["total_time"],
            reverse=True
        )
        
        return {
            "segments": segments,
            "num_speakers": len(speaker_stats),
            "speakers": list(speaker_stats.keys()),
            "speaker_stats": sorted_speakers,
            "backend": self.backend,
            "model": self.model_name
        }


def create_diarizer_from_config(config: Optional[Dict] = None) -> Diarizer:
    """
    Factory function para criar diarizer a partir de configuração.
    
    Args:
        config: Dict com configurações. Se None, usa variáveis de ambiente.
    
    Returns:
        Instância configurada de Diarizer
    """
    if config is None:
        config = {
            "backend": os.getenv("DIARIZATION_BACKEND", "pyannote"),
            "model_name": os.getenv("PYANNOTE_MODEL"),
            "max_speakers": int(os.getenv("MAX_SPEAKERS", "2"))
        }
    
    return Diarizer(
        backend=config.get("backend", "pyannote"),
        model_name=config.get("model_name"),
        num_speakers=config.get("num_speakers"),
        min_speakers=config.get("min_speakers"),
        max_speakers=config.get("max_speakers", 2),
        device=config.get("device")
    )
