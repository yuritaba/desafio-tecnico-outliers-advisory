"""
Módulo para identificação de papéis dos speakers (HOST vs GUEST).
Usa heurísticas baseadas em tempo de fala e padrões de diálogo.
"""
import logging
from typing import List, Dict, Optional, Tuple
from collections import defaultdict, Counter

from .models import AlignedSegment, Participant


class SpeakerIdentifier:
    """
    Classe para identificar papéis dos speakers.
    """
    
    def __init__(
        self,
        host_name: Optional[str] = None,
        guest_names: Optional[List[str]] = None,
        use_time_heuristic: bool = True,
        use_question_heuristic: bool = True
    ):
        """
        Inicializa o identificador de speakers.
        
        Args:
            host_name: Nome do host (se conhecido)
            guest_names: Lista de nomes dos convidados (se conhecidos)
            use_time_heuristic: Usar heurística de tempo de fala
            use_question_heuristic: Usar heurística de perguntas
        """
        self.host_name = host_name
        self.guest_names = guest_names or []
        self.use_time_heuristic = use_time_heuristic
        self.use_question_heuristic = use_question_heuristic
        self.logger = logging.getLogger('podcast_pipeline.speaker_identifier')
    
    def identify_speakers(
        self,
        segments: List[AlignedSegment]
    ) -> Tuple[Dict[str, str], List[Participant]]:
        """
        Identifica papéis dos speakers.
        
        Args:
            segments: Segmentos alinhados com speakers
        
        Returns:
            Tupla (mapeamento speaker_raw_id -> role, lista de Participants)
        """
        self.logger.info("Identificando papéis dos speakers")
        
        # Coleta estatísticas dos speakers
        speaker_stats = self._calculate_speaker_stats(segments)
        
        # Se temos nomes explícitos, usa eles
        if self.host_name or self.guest_names:
            return self._identify_with_names(speaker_stats)
        
        # Senão, usa heurísticas
        return self._identify_with_heuristics(segments, speaker_stats)
    
    def _calculate_speaker_stats(
        self,
        segments: List[AlignedSegment]
    ) -> Dict[str, dict]:
        """
        Calcula estatísticas detalhadas por speaker.
        """
        stats = defaultdict(lambda: {
            "total_time": 0.0,
            "segment_count": 0,
            "words": 0,
            "questions": 0,
            "first_appearance": float('inf'),
            "last_appearance": 0.0
        })
        
        for seg in segments:
            if seg.speaker == "UNKNOWN":
                continue
            
            speaker = seg.speaker
            duration = seg.end - seg.start
            
            stats[speaker]["total_time"] += duration
            stats[speaker]["segment_count"] += 1
            stats[speaker]["words"] += len(seg.text.split())
            stats[speaker]["first_appearance"] = min(
                stats[speaker]["first_appearance"],
                seg.start
            )
            stats[speaker]["last_appearance"] = max(
                stats[speaker]["last_appearance"],
                seg.end
            )
            
            # Conta perguntas (heurística simples)
            if self.use_question_heuristic:
                stats[speaker]["questions"] += self._count_questions(seg.text)
        
        # Calcula métricas derivadas
        for speaker in stats:
            if stats[speaker]["segment_count"] > 0:
                stats[speaker]["avg_segment_duration"] = (
                    stats[speaker]["total_time"] / stats[speaker]["segment_count"]
                )
                stats[speaker]["words_per_segment"] = (
                    stats[speaker]["words"] / stats[speaker]["segment_count"]
                )
        
        return dict(stats)
    
    def _count_questions(self, text: str) -> int:
        """
        Conta perguntas no texto (heurística simples).
        """
        # Conta pontos de interrogação
        question_marks = text.count('?')
        
        # Busca por palavras interrogativas comuns em PT-BR
        question_words = [
            'como', 'quando', 'onde', 'quem', 'qual', 'quais',
            'por que', 'porque', 'quanto', 'quantos', 'quantas',
            'o que', 'que'
        ]
        
        text_lower = text.lower()
        word_questions = sum(
            1 for word in question_words
            if f' {word} ' in f' {text_lower} '
        )
        
        return question_marks + (word_questions // 2)  # Desconta duplicatas
    
    def _identify_with_names(
        self,
        speaker_stats: Dict[str, dict]
    ) -> Tuple[Dict[str, str], List[Participant]]:
        """
        Identificação quando nomes são fornecidos.
        """
        # Se temos apenas 1 speaker conhecido + convidado, é simples
        speakers = sorted(
            speaker_stats.keys(),
            key=lambda s: speaker_stats[s]["total_time"],
            reverse=True
        )
        
        role_mapping = {}
        participants = []
        
        # Atribui papéis baseado em ordem de tempo de fala
        if self.host_name:
            # Host geralmente fala mais (mas não sempre)
            host_id = speakers[0] if len(speakers) > 0 else None
            if host_id:
                role_mapping[host_id] = "HOST"
                participants.append(Participant(
                    role="HOST",
                    name=self.host_name,
                    speaker_id=host_id
                ))
        
        # Atribui guests
        guest_idx = 1 if self.host_name else 0
        for i, guest_name in enumerate(self.guest_names):
            if guest_idx + i < len(speakers):
                speaker_id = speakers[guest_idx + i]
                role = f"GUEST_{i + 1}"
                role_mapping[speaker_id] = role
                participants.append(Participant(
                    role=role,
                    name=guest_name,
                    speaker_id=speaker_id
                ))
        
        self.logger.info(f"Identificados {len(role_mapping)} speakers com nomes fornecidos")
        return role_mapping, participants
    
    def _identify_with_heuristics(
        self,
        segments: List[AlignedSegment],
        speaker_stats: Dict[str, dict]
    ) -> Tuple[Dict[str, str], List[Participant]]:
        """
        Identificação usando heurísticas.
        """
        if not speaker_stats:
            return {}, []
        
        # Ordena speakers por diferentes critérios
        speakers_by_time = sorted(
            speaker_stats.keys(),
            key=lambda s: speaker_stats[s]["total_time"],
            reverse=True
        )
        
        role_mapping = {}
        participants = []
        
        if len(speakers_by_time) == 1:
            # Apenas 1 speaker - marca como UNKNOWN
            speaker_id = speakers_by_time[0]
            role_mapping[speaker_id] = "UNKNOWN"
            participants.append(Participant(
                role="UNKNOWN",
                speaker_id=speaker_id
            ))
            self.logger.warning("Apenas 1 speaker detectado")
            
        elif len(speakers_by_time) == 2:
            # 2 speakers - cenário típico de podcast
            role_mapping, participants = self._identify_two_speakers(
                speakers_by_time,
                speaker_stats,
                segments
            )
            
        else:
            # 3+ speakers - atribui sequencialmente
            self.logger.warning(
                f"{len(speakers_by_time)} speakers detectados. "
                "Atribuindo papéis sequencialmente."
            )
            
            role_mapping[speakers_by_time[0]] = "HOST"
            participants.append(Participant(
                role="HOST",
                speaker_id=speakers_by_time[0]
            ))
            
            for i, speaker_id in enumerate(speakers_by_time[1:], 1):
                role = f"GUEST_{i}"
                role_mapping[speaker_id] = role
                participants.append(Participant(
                    role=role,
                    speaker_id=speaker_id
                ))
        
        return role_mapping, participants
    
    def _identify_two_speakers(
        self,
        speakers: List[str],
        speaker_stats: Dict[str, dict],
        segments: List[AlignedSegment]
    ) -> Tuple[Dict[str, str], List[Participant]]:
        """
        Identificação específica para 2 speakers (caso mais comum).
        """
        spk1, spk2 = speakers
        stats1 = speaker_stats[spk1]
        stats2 = speaker_stats[spk2]
        
        # Scores para cada heurística
        host_score = {spk1: 0, spk2: 0}
        
        # Heurística 1: Tempo de fala
        # Em podcasts financeiros, host geralmente fala mais
        if self.use_time_heuristic:
            if stats1["total_time"] > stats2["total_time"]:
                host_score[spk1] += 2
            else:
                host_score[spk2] += 2
        
        # Heurística 2: Perguntas
        # Host geralmente faz mais perguntas
        if self.use_question_heuristic:
            if stats1["questions"] > stats2["questions"]:
                host_score[spk1] += 1
            elif stats2["questions"] > stats1["questions"]:
                host_score[spk2] += 1
        
        # Heurística 3: Primeira aparição
        # Host geralmente fala primeiro (introduz o programa)
        if stats1["first_appearance"] < stats2["first_appearance"]:
            host_score[spk1] += 1
        else:
            host_score[spk2] += 1
        
        # Heurística 4: Padrão de alternância
        # Analisa quem inicia mais trocas de fala
        initiator_score = self._analyze_turn_taking(segments, [spk1, spk2])
        if initiator_score[spk1] > initiator_score[spk2]:
            host_score[spk1] += 1
        else:
            host_score[spk2] += 1
        
        # Decide baseado nos scores
        host_id = spk1 if host_score[spk1] >= host_score[spk2] else spk2
        guest_id = spk2 if host_id == spk1 else spk1
        
        role_mapping = {
            host_id: "HOST",
            guest_id: "GUEST_1"
        }
        
        participants = [
            Participant(role="HOST", speaker_id=host_id),
            Participant(role="GUEST_1", speaker_id=guest_id)
        ]
        
        self.logger.info(
            f"Identificados: HOST={host_id} (score={host_score[host_id]}), "
            f"GUEST={guest_id} (score={host_score[guest_id]})"
        )
        
        return role_mapping, participants
    
    def _analyze_turn_taking(
        self,
        segments: List[AlignedSegment],
        speakers: List[str]
    ) -> Dict[str, int]:
        """
        Analisa padrão de alternância de turnos.
        Retorna quantas vezes cada speaker inicia uma nova sequência.
        """
        initiator_count = {spk: 0 for spk in speakers}
        
        prev_speaker = None
        for seg in segments:
            if seg.speaker in speakers:
                if prev_speaker and prev_speaker != seg.speaker:
                    # Novo turno
                    initiator_count[seg.speaker] += 1
                prev_speaker = seg.speaker
        
        return initiator_count


def identify_speaker_roles(
    segments: List[AlignedSegment],
    host_name: Optional[str] = None,
    guest_names: Optional[List[str]] = None
) -> Tuple[Dict[str, str], List[Participant]]:
    """
    Função helper para identificação de speakers.
    
    Args:
        segments: Segmentos alinhados
        host_name: Nome do host (opcional)
        guest_names: Nomes dos convidados (opcional)
    
    Returns:
        Tupla (mapeamento, participants)
    """
    identifier = SpeakerIdentifier(
        host_name=host_name,
        guest_names=guest_names
    )
    return identifier.identify_speakers(segments)
