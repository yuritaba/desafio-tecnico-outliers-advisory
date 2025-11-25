"""
Modelos de dados para estruturação da transcrição de podcasts.
Usa Pydantic para validação e serialização.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class Participant(BaseModel):
    """Representa um participante do podcast"""
    role: Literal["HOST", "GUEST_1", "GUEST_2", "UNKNOWN"] = Field(
        ...,
        description="Papel do participante no episódio"
    )
    name: Optional[str] = Field(
        None,
        description="Nome real do participante (se fornecido)"
    )
    speaker_id: Optional[str] = Field(
        None,
        description="ID do speaker retornado pela diarização (ex: SPK_0)"
    )


class Utterance(BaseModel):
    """Representa uma fala individual no episódio"""
    speaker_role: Literal["HOST", "GUEST_1", "GUEST_2", "UNKNOWN"] = Field(
        ...,
        description="Papel de quem está falando"
    )
    speaker_raw_id: Optional[str] = Field(
        None,
        description="ID bruto retornado pela ferramenta de diarização"
    )
    start_time: float = Field(
        ...,
        description="Tempo de início em segundos",
        ge=0
    )
    end_time: float = Field(
        ...,
        description="Tempo de fim em segundos",
        ge=0
    )
    text: str = Field(
        ...,
        description="Texto transcrito e limpo da fala",
        min_length=1
    )
    confidence: Optional[float] = Field(
        None,
        description="Confiança da transcrição (0-1)",
        ge=0,
        le=1
    )

    @field_validator('end_time')
    @classmethod
    def validate_time_range(cls, v, info):
        """Valida que end_time > start_time"""
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('end_time deve ser maior que start_time')
        return v

    def duration(self) -> float:
        """Retorna a duração da fala em segundos"""
        return self.end_time - self.start_time

    def format_timestamp(self, time_seconds: float) -> str:
        """Formata segundos para HH:MM:SS"""
        hours = int(time_seconds // 3600)
        minutes = int((time_seconds % 3600) // 60)
        seconds = int(time_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_timestamp_range(self) -> str:
        """Retorna o range de timestamp formatado"""
        return f"{self.format_timestamp(self.start_time)} - {self.format_timestamp(self.end_time)}"


class EpisodeMetadata(BaseModel):
    """Metadados do episódio"""
    episode_id: Optional[str] = Field(
        None,
        description="Identificador único do episódio"
    )
    title: Optional[str] = Field(
        None,
        description="Título do episódio"
    )
    date: Optional[str] = Field(
        None,
        description="Data de publicação (ISO 8601)"
    )
    duration_seconds: Optional[float] = Field(
        None,
        description="Duração total do episódio em segundos",
        ge=0
    )
    original_link: Optional[str] = Field(
        None,
        description="Link original do episódio"
    )
    participants: List[Participant] = Field(
        default_factory=list,
        description="Lista de participantes identificados"
    )
    language: str = Field(
        default="pt-BR",
        description="Idioma do episódio"
    )


class ProcessingNote(BaseModel):
    """Nota sobre o processamento (avisos, problemas, etc)"""
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Timestamp da nota"
    )
    level: Literal["INFO", "WARNING", "ERROR"] = Field(
        ...,
        description="Nível de severidade"
    )
    message: str = Field(
        ...,
        description="Mensagem da nota"
    )
    component: Optional[str] = Field(
        None,
        description="Componente que gerou a nota (ex: diarization, transcription)"
    )


class TranscriptOutput(BaseModel):
    """Estrutura completa do output da transcrição"""
    episode_metadata: EpisodeMetadata = Field(
        ...,
        description="Metadados do episódio"
    )
    utterances: List[Utterance] = Field(
        ...,
        description="Lista ordenada de falas"
    )
    processing_notes: List[ProcessingNote] = Field(
        default_factory=list,
        description="Notas sobre o processamento"
    )
    version: str = Field(
        default="1.0",
        description="Versão do formato de output"
    )
    processed_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Timestamp do processamento"
    )

    @field_validator('utterances')
    @classmethod
    def validate_utterances_order(cls, v):
        """Valida que as falas estão em ordem cronológica"""
        if len(v) < 2:
            return v
        
        for i in range(1, len(v)):
            if v[i].start_time < v[i-1].start_time:
                raise ValueError(
                    f"Utterances devem estar em ordem cronológica. "
                    f"Utterance {i} começa em {v[i].start_time}s mas a anterior termina em {v[i-1].end_time}s"
                )
        return v

    def get_total_duration(self) -> float:
        """Retorna a duração total baseada nas utterances"""
        if not self.utterances:
            return 0.0
        return max(u.end_time for u in self.utterances)

    def get_speaker_stats(self) -> dict:
        """Retorna estatísticas por speaker"""
        stats = {}
        for utterance in self.utterances:
            role = utterance.speaker_role
            if role not in stats:
                stats[role] = {
                    "total_time": 0.0,
                    "utterance_count": 0,
                    "avg_utterance_duration": 0.0
                }
            
            duration = utterance.duration()
            stats[role]["total_time"] += duration
            stats[role]["utterance_count"] += 1
        
        # Calcula médias
        for role in stats:
            if stats[role]["utterance_count"] > 0:
                stats[role]["avg_utterance_duration"] = (
                    stats[role]["total_time"] / stats[role]["utterance_count"]
                )
        
        return stats

    def add_note(self, level: str, message: str, component: Optional[str] = None):
        """Adiciona uma nota de processamento"""
        note = ProcessingNote(
            level=level,
            message=message,
            component=component
        )
        self.processing_notes.append(note)

    def to_json(self, **kwargs) -> str:
        """Serializa para JSON com configurações padrão"""
        return self.model_dump_json(indent=2, exclude_none=False, **kwargs)


# Modelos intermediários para processamento interno

class RawTranscriptionSegment(BaseModel):
    """Segmento bruto retornado pelo STT"""
    start: float
    end: float
    text: str
    confidence: Optional[float] = None


class DiarizationSegment(BaseModel):
    """Segmento retornado pela diarização"""
    start: float
    end: float
    speaker: str  # ex: SPK_0, SPK_1


class AlignedSegment(BaseModel):
    """Segmento após alinhamento de transcrição + diarização"""
    start: float
    end: float
    text: str
    speaker: str
    confidence: Optional[float] = None
