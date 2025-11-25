"""
Pipeline principal para processamento de episódios de podcast.
Orquestra todos os módulos para gerar transcrição estruturada.
"""
import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from .models import (
    TranscriptOutput,
    EpisodeMetadata,
    Utterance,
    ProcessingNote
)
from .transcriber import Transcriber, create_transcriber_from_config
from .diarizer import Diarizer, create_diarizer_from_config
from .aligner import Aligner
from .speaker_identifier import SpeakerIdentifier
from .text_cleaner import TextCleaner
from .utils import (
    setup_logging,
    get_audio_duration,
    ProgressTracker,
    validate_audio_file
)


class PodcastPipeline:
    """
    Pipeline completo para processamento de episódios de podcast.
    """
    
    def __init__(
        self,
        transcriber_config: Optional[Dict] = None,
        diarizer_config: Optional[Dict] = None,
        aligner_config: Optional[Dict] = None,
        cleaner_config: Optional[Dict] = None,
        log_level: str = "INFO"
    ):
        """
        Inicializa o pipeline.
        
        Args:
            transcriber_config: Config para transcrição
            diarizer_config: Config para diarização
            aligner_config: Config para alinhamento
            cleaner_config: Config para limpeza de texto
            log_level: Nível de log
        """
        self.logger = setup_logging(log_level)
        self.logger.info("Inicializando Podcast Pipeline")
        
        # Inicializa componentes
        self.transcriber = create_transcriber_from_config(transcriber_config)
        self.diarizer = create_diarizer_from_config(diarizer_config)
        
        self.aligner = Aligner(**(aligner_config or {}))
        self.cleaner = TextCleaner(**(cleaner_config or {}))
        self.speaker_identifier = SpeakerIdentifier()
        
        self.logger.info("Pipeline inicializado com sucesso")
    
    def process(
        self,
        audio_path: str,
        episode_metadata: Optional[Dict] = None,
        host_name: Optional[str] = None,
        guest_names: Optional[List[str]] = None
    ) -> TranscriptOutput:
        """
        Processa um episódio de podcast completo.
        
        Args:
            audio_path: Caminho para arquivo de áudio
            episode_metadata: Metadados do episódio (opcional)
            host_name: Nome do host (opcional)
            guest_names: Nomes dos convidados (opcional)
        
        Returns:
            TranscriptOutput estruturado e validado
        
        Raises:
            ValueError: Se arquivo inválido ou erro no processamento
        """
        self.logger.info(f"Iniciando processamento de: {audio_path}")
        
        # Valida arquivo
        if not validate_audio_file(audio_path):
            raise ValueError(f"Arquivo de áudio inválido: {audio_path}")
        
        # Cria tracker de progresso
        progress = ProgressTracker(7, "Processamento do episódio")
        
        # Cria estrutura de output
        output = TranscriptOutput(
            episode_metadata=self._build_metadata(audio_path, episode_metadata),
            utterances=[]
        )
        
        try:
            # Passo 1: Transcrição
            progress.update("Transcrevendo áudio")
            transcription = self.transcriber.transcribe(audio_path)
            output.add_note(
                "INFO",
                f"Transcrição completa: {len(transcription)} segmentos",
                "transcription"
            )
            
            # Passo 2: Diarização
            progress.update("Identificando speakers")
            diarization = self.diarizer.diarize(audio_path)
            output.add_note(
                "INFO",
                f"Diarização completa: {len(diarization)} segmentos, "
                f"{len(set(d.speaker for d in diarization))} speakers",
                "diarization"
            )
            
            # Passo 3: Alinhamento
            progress.update("Alinhando transcrição com diarização")
            aligned = self.aligner.align(transcription, diarization)
            
            # Verifica qualidade do alinhamento
            alignment_metrics = self.aligner.get_alignment_quality_metrics(aligned)
            if alignment_metrics["unknown_percentage"] > 20:
                output.add_note(
                    "WARNING",
                    f"{alignment_metrics['unknown_percentage']:.1f}% dos segmentos "
                    f"não puderam ser atribuídos a um speaker",
                    "alignment"
                )
            
            # Passo 4: Identificação de speakers
            progress.update("Identificando papéis (HOST/GUEST)")
            self.speaker_identifier.host_name = host_name
            self.speaker_identifier.guest_names = guest_names or []
            
            speaker_mapping, participants = self.speaker_identifier.identify_speakers(aligned)
            
            # Atualiza metadados com participantes
            output.episode_metadata.participants = participants
            output.add_note(
                "INFO",
                f"Speakers identificados: {', '.join(p.role for p in participants)}",
                "speaker_identification"
            )
            
            # Passo 5: Aplica mapeamento de speakers
            progress.update("Aplicando mapeamento de speakers")
            aligned_with_roles = self._apply_speaker_mapping(aligned, speaker_mapping)
            
            # Passo 6: Limpeza de texto
            progress.update("Limpando e normalizando texto")
            cleaned = self.cleaner.clean_segments(aligned_with_roles)
            
            cleaning_stats = self.cleaner.get_cleaning_stats(
                aligned_with_roles,
                cleaned
            )
            if cleaning_stats["removed_segments"] > 0:
                output.add_note(
                    "INFO",
                    f"Removidos {cleaning_stats['removed_segments']} segmentos vazios "
                    f"após limpeza",
                    "text_cleaning"
                )
            
            # Passo 7: Converte para Utterances finais
            progress.update("Finalizando estrutura de dados")
            output.utterances = self._convert_to_utterances(cleaned)
            
            # Finaliza
            progress.complete()
            
            # Adiciona estatísticas finais
            speaker_stats = output.get_speaker_stats()
            self.logger.info(
                f"Processamento completo! "
                f"Total: {len(output.utterances)} falas, "
                f"{output.get_total_duration():.1f}s de áudio"
            )
            
            for role, stats in speaker_stats.items():
                self.logger.info(
                    f"  {role}: {stats['utterance_count']} falas, "
                    f"{stats['total_time']:.1f}s "
                    f"({stats['total_time']/output.get_total_duration()*100:.1f}%)"
                )
            
            return output
            
        except Exception as e:
            self.logger.error(f"Erro no processamento: {e}", exc_info=True)
            output.add_note(
                "ERROR",
                f"Erro fatal no processamento: {str(e)}",
                "pipeline"
            )
            raise
    
    def process_from_metadata(
        self,
        audio_path: str,
        metadata_dict: Dict[str, Any]
    ) -> TranscriptOutput:
        """
        Processa episódio a partir de dict de metadados completo.
        
        Args:
            audio_path: Caminho para áudio
            metadata_dict: Dict com todos os metadados
        
        Returns:
            TranscriptOutput
        """
        # Extrai informações do metadata
        episode_meta = metadata_dict.get("episode", {})
        host_name = metadata_dict.get("host_name")
        guest_names = metadata_dict.get("guest_names", [])
        
        return self.process(
            audio_path=audio_path,
            episode_metadata=episode_meta,
            host_name=host_name,
            guest_names=guest_names
        )
    
    def _build_metadata(
        self,
        audio_path: str,
        provided_metadata: Optional[Dict]
    ) -> EpisodeMetadata:
        """Constrói metadados do episódio"""
        metadata = provided_metadata or {}
        
        # Obtém duração do áudio
        duration = get_audio_duration(audio_path)
        
        return EpisodeMetadata(
            episode_id=metadata.get("episode_id"),
            title=metadata.get("title"),
            date=metadata.get("date"),
            duration_seconds=duration or metadata.get("duration_seconds"),
            original_link=metadata.get("original_link"),
            participants=[],  # Será preenchido depois
            language=metadata.get("language", "pt-BR")
        )
    
    def _apply_speaker_mapping(
        self,
        segments: List,
        mapping: Dict[str, str]
    ) -> List:
        """Aplica mapeamento de speaker_raw_id para roles"""
        result = []
        for seg in segments:
            role = mapping.get(seg.speaker, "UNKNOWN")
            
            # Cria novo segmento com role atualizado
            result.append(type(seg)(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                speaker=role,
                confidence=seg.confidence
            ))
        
        return result
    
    def _convert_to_utterances(self, segments: List) -> List[Utterance]:
        """Converte AlignedSegments para Utterances"""
        utterances = []
        
        for seg in segments:
            utterances.append(Utterance(
                speaker_role=seg.speaker,
                speaker_raw_id=None,  # Já foi mapeado
                start_time=seg.start,
                end_time=seg.end,
                text=seg.text,
                confidence=seg.confidence
            ))
        
        return utterances
    
    def save_output(
        self,
        output: TranscriptOutput,
        output_path: str,
        pretty: bool = True
    ):
        """
        Salva output em arquivo JSON.
        
        Args:
            output: TranscriptOutput a salvar
            output_path: Caminho do arquivo de saída
            pretty: Se True, formata JSON com indentação
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if pretty:
                f.write(output.to_json())
            else:
                f.write(output.model_dump_json())
        
        self.logger.info(f"Output salvo em: {output_path}")


def process_podcast_episode(
    audio_path: str,
    output_path: Optional[str] = None,
    episode_metadata: Optional[Dict] = None,
    host_name: Optional[str] = None,
    guest_names: Optional[List[str]] = None,
    config: Optional[Dict] = None
) -> TranscriptOutput:
    """
    Função helper para processar um episódio.
    
    Args:
        audio_path: Caminho do áudio
        output_path: Caminho para salvar JSON (opcional)
        episode_metadata: Metadados do episódio
        host_name: Nome do host
        guest_names: Nomes dos convidados
        config: Configuração customizada
    
    Returns:
        TranscriptOutput processado
    """
    # Cria pipeline
    pipeline = PodcastPipeline(**(config or {}))
    
    # Processa
    result = pipeline.process(
        audio_path=audio_path,
        episode_metadata=episode_metadata,
        host_name=host_name,
        guest_names=guest_names
    )
    
    # Salva se output_path fornecido
    if output_path:
        pipeline.save_output(result, output_path)
    
    return result
