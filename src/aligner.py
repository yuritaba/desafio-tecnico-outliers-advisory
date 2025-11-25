"""
Módulo para alinhamento entre transcrição e diarização.
Combina segmentos de texto com identificação de speakers.
"""
import logging
from typing import List, Tuple, Optional
from collections import defaultdict

from .models import (
    RawTranscriptionSegment,
    DiarizationSegment,
    AlignedSegment
)
from .utils import calculate_overlap, calculate_iou


class Aligner:
    """
    Classe para alinhar transcrição com diarização baseada em timestamps.
    """
    
    def __init__(
        self,
        min_overlap: float = 0.3,
        merge_threshold: float = 0.5
    ):
        """
        Inicializa o aligner.
        
        Args:
            min_overlap: Overlap mínimo (IoU) para considerar match válido
            merge_threshold: Gap máximo em segundos para merge de segmentos adjacentes
        """
        self.min_overlap = min_overlap
        self.merge_threshold = merge_threshold
        self.logger = logging.getLogger('podcast_pipeline.aligner')
    
    def align(
        self,
        transcription: List[RawTranscriptionSegment],
        diarization: List[DiarizationSegment]
    ) -> List[AlignedSegment]:
        """
        Alinha transcrição com diarização.
        
        Args:
            transcription: Segmentos de transcrição com texto e timestamps
            diarization: Segmentos de diarização com speakers e timestamps
        
        Returns:
            Lista de segmentos alinhados (texto + speaker)
        """
        self.logger.info(
            f"Alinhando {len(transcription)} segmentos de transcrição "
            f"com {len(diarization)} segmentos de diarização"
        )
        
        if not transcription:
            self.logger.warning("Transcrição vazia")
            return []
        
        if not diarization:
            self.logger.warning(
                "Diarização vazia. Todos os segmentos serão marcados como UNKNOWN"
            )
            return self._create_unknown_alignment(transcription)
        
        # Cria índice de diarização por tempo para busca eficiente
        diarization_index = self._build_time_index(diarization)
        
        aligned = []
        unmatched_count = 0
        
        for trans_seg in transcription:
            # Encontra o melhor match de speaker para este segmento
            speaker, confidence = self._find_best_speaker_match(
                trans_seg,
                diarization_index
            )
            
            if speaker is None:
                speaker = "UNKNOWN"
                unmatched_count += 1
                self.logger.debug(
                    f"Segmento sem match [{trans_seg.start:.2f}-{trans_seg.end:.2f}]: "
                    f"{trans_seg.text[:50]}..."
                )
            
            aligned.append(AlignedSegment(
                start=trans_seg.start,
                end=trans_seg.end,
                text=trans_seg.text,
                speaker=speaker,
                confidence=trans_seg.confidence
            ))
        
        if unmatched_count > 0:
            self.logger.warning(
                f"{unmatched_count}/{len(transcription)} segmentos "
                f"não puderam ser atribuídos a um speaker"
            )
        
        # Merge de segmentos adjacentes do mesmo speaker
        aligned = self._merge_adjacent_segments(aligned)
        
        self.logger.info(
            f"Alinhamento completo: {len(aligned)} segmentos finais"
        )
        
        return aligned
    
    def _build_time_index(
        self,
        diarization: List[DiarizationSegment]
    ) -> dict:
        """
        Constrói índice temporal para busca eficiente.
        
        Returns:
            Dict mapeando intervalos de tempo para segmentos
        """
        # Agrupa por buckets de 1 segundo para busca rápida
        index = defaultdict(list)
        
        for seg in diarization:
            start_bucket = int(seg.start)
            end_bucket = int(seg.end) + 1
            
            for bucket in range(start_bucket, end_bucket):
                index[bucket].append(seg)
        
        return index
    
    def _find_best_speaker_match(
        self,
        trans_seg: RawTranscriptionSegment,
        diarization_index: dict
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        Encontra o melhor match de speaker para um segmento de transcrição.
        
        Returns:
            Tupla (speaker_id, confidence)
        """
        # Busca candidatos no índice
        candidates = set()
        start_bucket = int(trans_seg.start)
        end_bucket = int(trans_seg.end) + 1
        
        for bucket in range(start_bucket, end_bucket):
            candidates.update(diarization_index.get(bucket, []))
        
        if not candidates:
            return None, None
        
        # Calcula IoU com cada candidato
        best_speaker = None
        best_iou = 0.0
        
        for diar_seg in candidates:
            iou = calculate_iou(
                trans_seg.start, trans_seg.end,
                diar_seg.start, diar_seg.end
            )
            
            if iou > best_iou:
                best_iou = iou
                best_speaker = diar_seg.speaker
        
        # Verifica threshold mínimo
        if best_iou < self.min_overlap:
            return None, None
        
        return best_speaker, best_iou
    
    def _merge_adjacent_segments(
        self,
        segments: List[AlignedSegment]
    ) -> List[AlignedSegment]:
        """
        Mescla segmentos adjacentes do mesmo speaker.
        """
        if not segments:
            return []
        
        merged = [segments[0]]
        
        for current in segments[1:]:
            last = merged[-1]
            
            gap = current.start - last.end
            same_speaker = current.speaker == last.speaker
            
            if gap <= self.merge_threshold and same_speaker:
                # Mescla
                merged[-1] = AlignedSegment(
                    start=last.start,
                    end=current.end,
                    text=last.text.strip() + ' ' + current.text.strip(),
                    speaker=last.speaker,
                    confidence=min(last.confidence, current.confidence)
                    if last.confidence and current.confidence else None
                )
            else:
                merged.append(current)
        
        if len(merged) < len(segments):
            self.logger.info(
                f"Merged {len(segments) - len(merged)} segmentos adjacentes"
            )
        
        return merged
    
    def _create_unknown_alignment(
        self,
        transcription: List[RawTranscriptionSegment]
    ) -> List[AlignedSegment]:
        """
        Cria alinhamento com speaker UNKNOWN quando não há diarização.
        """
        return [
            AlignedSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                speaker="UNKNOWN",
                confidence=seg.confidence
            )
            for seg in transcription
        ]
    
    def get_alignment_quality_metrics(
        self,
        aligned: List[AlignedSegment]
    ) -> dict:
        """
        Calcula métricas de qualidade do alinhamento.
        
        Args:
            aligned: Segmentos alinhados
        
        Returns:
            Dict com métricas
        """
        if not aligned:
            return {
                "total_segments": 0,
                "unknown_segments": 0,
                "unknown_percentage": 0.0,
                "speakers_count": 0
            }
        
        unknown_count = sum(1 for seg in aligned if seg.speaker == "UNKNOWN")
        speakers = set(seg.speaker for seg in aligned if seg.speaker != "UNKNOWN")
        
        total_time = sum(seg.end - seg.start for seg in aligned)
        unknown_time = sum(
            seg.end - seg.start
            for seg in aligned
            if seg.speaker == "UNKNOWN"
        )
        
        return {
            "total_segments": len(aligned),
            "unknown_segments": unknown_count,
            "unknown_percentage": (unknown_count / len(aligned)) * 100,
            "speakers_count": len(speakers),
            "speakers": list(speakers),
            "total_time": total_time,
            "unknown_time": unknown_time,
            "unknown_time_percentage": (unknown_time / total_time * 100) if total_time > 0 else 0
        }


def align_transcription_and_diarization(
    transcription: List[RawTranscriptionSegment],
    diarization: List[DiarizationSegment],
    min_overlap: float = 0.3,
    merge_threshold: float = 0.5
) -> List[AlignedSegment]:
    """
    Função helper para alinhamento.
    
    Args:
        transcription: Segmentos de transcrição
        diarization: Segmentos de diarização
        min_overlap: IoU mínimo para match
        merge_threshold: Gap máximo para merge
    
    Returns:
        Segmentos alinhados
    """
    aligner = Aligner(
        min_overlap=min_overlap,
        merge_threshold=merge_threshold
    )
    return aligner.align(transcription, diarization)
