"""
Testes para o módulo de utilidades.
"""
import pytest
from pathlib import Path

from src.utils import (
    seconds_to_timestamp,
    timestamp_to_seconds,
    calculate_overlap,
    calculate_iou,
    merge_adjacent_segments
)


class TestTimeConversion:
    """Testes para conversão de tempo"""
    
    def test_seconds_to_timestamp(self):
        """Testa conversão de segundos para timestamp"""
        assert seconds_to_timestamp(0) == "00:00:00"
        assert seconds_to_timestamp(65) == "00:01:05"
        assert seconds_to_timestamp(3665) == "01:01:05"
    
    def test_timestamp_to_seconds(self):
        """Testa conversão de timestamp para segundos"""
        assert timestamp_to_seconds("00:00:00") == 0
        assert timestamp_to_seconds("00:01:05") == 65
        assert timestamp_to_seconds("01:01:05") == 3665
        assert timestamp_to_seconds("01:05") == 65  # Formato MM:SS


class TestOverlapCalculation:
    """Testes para cálculo de overlap"""
    
    def test_no_overlap(self):
        """Testa segmentos sem overlap"""
        overlap = calculate_overlap(0, 10, 20, 30)
        assert overlap == 0
    
    def test_full_overlap(self):
        """Testa overlap completo"""
        overlap = calculate_overlap(0, 10, 0, 10)
        assert overlap == 10
    
    def test_partial_overlap(self):
        """Testa overlap parcial"""
        overlap = calculate_overlap(0, 10, 5, 15)
        assert overlap == 5
    
    def test_contained(self):
        """Testa segmento contido em outro"""
        overlap = calculate_overlap(0, 20, 5, 10)
        assert overlap == 5


class TestIoU:
    """Testes para Intersection over Union"""
    
    def test_no_overlap(self):
        """Testa IoU sem overlap"""
        iou = calculate_iou(0, 10, 20, 30)
        assert iou == 0.0
    
    def test_perfect_overlap(self):
        """Testa IoU perfeito"""
        iou = calculate_iou(0, 10, 0, 10)
        assert iou == 1.0
    
    def test_partial_overlap(self):
        """Testa IoU parcial"""
        iou = calculate_iou(0, 10, 5, 15)
        # Intersection: 5, Union: 15
        assert abs(iou - 0.333) < 0.01


class TestSegmentMerging:
    """Testes para merge de segmentos"""
    
    def test_merge_adjacent_same_speaker(self):
        """Testa merge de segmentos adjacentes do mesmo speaker"""
        segments = [
            {'start': 0, 'end': 5, 'speaker': 'A', 'text': 'Olá'},
            {'start': 5.2, 'end': 10, 'speaker': 'A', 'text': 'mundo'}
        ]
        
        merged = merge_adjacent_segments(segments, max_gap=0.5)
        
        assert len(merged) == 1
        assert merged[0]['text'] == 'Olá mundo'
    
    def test_no_merge_different_speakers(self):
        """Testa que não mescla speakers diferentes"""
        segments = [
            {'start': 0, 'end': 5, 'speaker': 'A', 'text': 'Olá'},
            {'start': 5.2, 'end': 10, 'speaker': 'B', 'text': 'mundo'}
        ]
        
        merged = merge_adjacent_segments(segments, max_gap=0.5, same_speaker=True)
        
        assert len(merged) == 2
    
    def test_no_merge_large_gap(self):
        """Testa que não mescla com gap grande"""
        segments = [
            {'start': 0, 'end': 5, 'speaker': 'A', 'text': 'Olá'},
            {'start': 10, 'end': 15, 'speaker': 'A', 'text': 'mundo'}
        ]
        
        merged = merge_adjacent_segments(segments, max_gap=0.5)
        
        assert len(merged) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
