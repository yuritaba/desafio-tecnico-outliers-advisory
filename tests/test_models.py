"""
Testes unitários para o módulo de modelos de dados.
"""
import pytest
from datetime import datetime

from src.models import (
    Utterance,
    Participant,
    EpisodeMetadata,
    TranscriptOutput,
    ProcessingNote
)


class TestUtterance:
    """Testes para o modelo Utterance"""
    
    def test_valid_utterance(self):
        """Testa criação de utterance válido"""
        utterance = Utterance(
            speaker_role="HOST",
            start_time=0.0,
            end_time=5.0,
            text="Teste de fala"
        )
        
        assert utterance.speaker_role == "HOST"
        assert utterance.start_time == 0.0
        assert utterance.end_time == 5.0
        assert utterance.text == "Teste de fala"
    
    def test_utterance_duration(self):
        """Testa cálculo de duração"""
        utterance = Utterance(
            speaker_role="HOST",
            start_time=10.0,
            end_time=15.5,
            text="Teste"
        )
        
        assert utterance.duration() == 5.5
    
    def test_invalid_time_range(self):
        """Testa que end_time deve ser maior que start_time"""
        with pytest.raises(ValueError):
            Utterance(
                speaker_role="HOST",
                start_time=10.0,
                end_time=5.0,  # Inválido
                text="Teste"
            )
    
    def test_timestamp_formatting(self):
        """Testa formatação de timestamps"""
        utterance = Utterance(
            speaker_role="HOST",
            start_time=3665.0,  # 1h 1min 5s
            end_time=3670.0,
            text="Teste"
        )
        
        formatted = utterance.format_timestamp(3665.0)
        assert formatted == "01:01:05"


class TestParticipant:
    """Testes para o modelo Participant"""
    
    def test_valid_participant(self):
        """Testa criação de participant válido"""
        participant = Participant(
            role="HOST",
            name="João Silva",
            speaker_id="SPK_0"
        )
        
        assert participant.role == "HOST"
        assert participant.name == "João Silva"
        assert participant.speaker_id == "SPK_0"
    
    def test_participant_without_name(self):
        """Testa participant sem nome (opcional)"""
        participant = Participant(
            role="GUEST_1",
            speaker_id="SPK_1"
        )
        
        assert participant.role == "GUEST_1"
        assert participant.name is None


class TestEpisodeMetadata:
    """Testes para o modelo EpisodeMetadata"""
    
    def test_minimal_metadata(self):
        """Testa metadados mínimos"""
        metadata = EpisodeMetadata()
        
        assert metadata.language == "pt-BR"
        assert metadata.participants == []
    
    def test_full_metadata(self):
        """Testa metadados completos"""
        metadata = EpisodeMetadata(
            episode_id="001",
            title="Episódio de Teste",
            date="2024-01-15",
            duration_seconds=3600.0,
            original_link="https://example.com",
            language="pt-BR",
            participants=[
                Participant(role="HOST", name="João")
            ]
        )
        
        assert metadata.episode_id == "001"
        assert metadata.title == "Episódio de Teste"
        assert len(metadata.participants) == 1


class TestTranscriptOutput:
    """Testes para o modelo TranscriptOutput"""
    
    def test_minimal_output(self):
        """Testa output mínimo válido"""
        output = TranscriptOutput(
            episode_metadata=EpisodeMetadata(),
            utterances=[]
        )
        
        assert output.version == "1.0"
        assert len(output.utterances) == 0
        assert len(output.processing_notes) == 0
    
    def test_utterances_order_validation(self):
        """Testa que utterances devem estar em ordem cronológica"""
        with pytest.raises(ValueError):
            TranscriptOutput(
                episode_metadata=EpisodeMetadata(),
                utterances=[
                    Utterance(
                        speaker_role="HOST",
                        start_time=10.0,
                        end_time=15.0,
                        text="Segunda fala"
                    ),
                    Utterance(
                        speaker_role="GUEST_1",
                        start_time=5.0,  # Antes da anterior - inválido!
                        end_time=9.0,
                        text="Primeira fala"
                    )
                ]
            )
    
    def test_get_speaker_stats(self):
        """Testa cálculo de estatísticas por speaker"""
        output = TranscriptOutput(
            episode_metadata=EpisodeMetadata(),
            utterances=[
                Utterance(
                    speaker_role="HOST",
                    start_time=0.0,
                    end_time=10.0,
                    text="Fala 1"
                ),
                Utterance(
                    speaker_role="HOST",
                    start_time=10.0,
                    end_time=15.0,
                    text="Fala 2"
                ),
                Utterance(
                    speaker_role="GUEST_1",
                    start_time=15.0,
                    end_time=25.0,
                    text="Fala 3"
                )
            ]
        )
        
        stats = output.get_speaker_stats()
        
        assert "HOST" in stats
        assert "GUEST_1" in stats
        assert stats["HOST"]["utterance_count"] == 2
        assert stats["HOST"]["total_time"] == 15.0
        assert stats["GUEST_1"]["utterance_count"] == 1
        assert stats["GUEST_1"]["total_time"] == 10.0
    
    def test_add_note(self):
        """Testa adição de notas de processamento"""
        output = TranscriptOutput(
            episode_metadata=EpisodeMetadata(),
            utterances=[]
        )
        
        output.add_note("INFO", "Teste de nota", "test_component")
        
        assert len(output.processing_notes) == 1
        assert output.processing_notes[0].level == "INFO"
        assert output.processing_notes[0].message == "Teste de nota"
    
    def test_json_serialization(self):
        """Testa serialização para JSON"""
        output = TranscriptOutput(
            episode_metadata=EpisodeMetadata(
                episode_id="001",
                title="Teste"
            ),
            utterances=[
                Utterance(
                    speaker_role="HOST",
                    start_time=0.0,
                    end_time=5.0,
                    text="Teste"
                )
            ]
        )
        
        json_str = output.to_json()
        
        assert isinstance(json_str, str)
        assert '"episode_id": "001"' in json_str
        assert '"text": "Teste"' in json_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
