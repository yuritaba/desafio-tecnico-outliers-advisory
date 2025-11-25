"""
Módulo para limpeza e normalização de texto transcrito.
Corrige erros comuns de STT mantendo fidelidade ao conteúdo.
"""
import re
import logging
from typing import List, Optional, Dict, Set

from .models import AlignedSegment


class TextCleaner:
    """
    Classe para limpeza e normalização de texto transcrito.
    """
    
    # Muletas comuns em português para remover/reduzir
    FILLER_WORDS = {
        'né', 'tipo', 'então', 'assim', 'tá', 'ééé', 'aaa', 'ééh',
        'ahh', 'hmm', 'uhm', 'ééée', 'éééh'
    }
    
    # Termos financeiros comuns que frequentemente são mal transcritos
    FINANCIAL_TERMS = {
        'valuation': ['valuação', 'valiueição'],
        'hedge': ['edge', 'hêdge'],
        'private equity': ['prívate equity', 'prívate équiti'],
        'venture capital': ['venchur capital', 'venchur cápital'],
        'M&A': ['emmi and ei', 'eme e a'],
        'IPO': ['ai pi ou', 'aipío'],
        'EBITDA': ['ebitda', 'ibítida'],
        'ROE': ['erre ou i', 'rói'],
        'ROI': ['erre ou ai', 'rói'],
        'CEO': ['ci i ou', 'síio'],
        'CFO': ['ci éfe ou', 'sífio'],
        'CAPEX': ['cápex', 'capéx'],
        'OPEX': ['ópex', 'opéx']
    }
    
    def __init__(
        self,
        remove_fillers: bool = True,
        fix_financial_terms: bool = True,
        fix_punctuation: bool = True,
        preserve_style: bool = True,
        aggressive_cleaning: bool = False
    ):
        """
        Inicializa o text cleaner.
        
        Args:
            remove_fillers: Remove muletas de fala
            fix_financial_terms: Corrige termos financeiros
            fix_punctuation: Corrige pontuação
            preserve_style: Preserva estilo oral
            aggressive_cleaning: Limpeza mais agressiva (perde naturalidade)
        """
        self.remove_fillers = remove_fillers
        self.fix_financial_terms = fix_financial_terms
        self.fix_punctuation = fix_punctuation
        self.preserve_style = preserve_style
        self.aggressive_cleaning = aggressive_cleaning
        self.logger = logging.getLogger('podcast_pipeline.text_cleaner')
        
        # Compila regex patterns
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compila padrões regex para limpeza"""
        # Múltiplos espaços
        self.multi_space_pattern = re.compile(r'\s+')
        
        # Repetições excessivas de caracteres (ééééé -> é)
        self.excessive_repeat_pattern = re.compile(r'(.)\1{3,}')
        
        # Números mal formatados
        self.number_pattern = re.compile(r'(\d)\s+(\d)')
        
        # Pontuação duplicada
        self.duplicate_punct_pattern = re.compile(r'([.,!?])\1+')
    
    def clean(self, text: str) -> str:
        """
        Limpa e normaliza um texto.
        
        Args:
            text: Texto bruto a limpar
        
        Returns:
            Texto limpo
        """
        if not text:
            return text
        
        original_text = text
        
        # Pipeline de limpeza
        text = self._remove_excessive_repetitions(text)
        text = self._fix_spacing(text)
        
        if self.fix_financial_terms:
            text = self._fix_financial_terms(text)
        
        if self.remove_fillers:
            text = self._remove_filler_words(text)
        
        if self.fix_punctuation:
            text = self._fix_punctuation(text)
        
        if self.aggressive_cleaning:
            text = self._aggressive_clean(text)
        
        # Normalização final
        text = text.strip()
        
        # Log se mudança significativa
        if len(text) < len(original_text) * 0.7:
            self.logger.debug(
                f"Limpeza removeu {len(original_text) - len(text)} caracteres: "
                f"{original_text[:50]}... -> {text[:50]}..."
            )
        
        return text
    
    def clean_segments(
        self,
        segments: List[AlignedSegment]
    ) -> List[AlignedSegment]:
        """
        Limpa uma lista de segmentos.
        
        Args:
            segments: Lista de segmentos a limpar
        
        Returns:
            Lista de segmentos com texto limpo
        """
        self.logger.info(f"Limpando {len(segments)} segmentos")
        
        cleaned = []
        for seg in segments:
            cleaned_text = self.clean(seg.text)
            
            # Só adiciona se o texto não ficou vazio
            if cleaned_text:
                cleaned.append(AlignedSegment(
                    start=seg.start,
                    end=seg.end,
                    text=cleaned_text,
                    speaker=seg.speaker,
                    confidence=seg.confidence
                ))
        
        if len(cleaned) < len(segments):
            self.logger.warning(
                f"Removidos {len(segments) - len(cleaned)} segmentos vazios após limpeza"
            )
        
        return cleaned
    
    def _remove_excessive_repetitions(self, text: str) -> str:
        """Remove repetições excessivas de caracteres"""
        # ééééé -> é (mas mantém até 2 repetições para naturalidade)
        return self.excessive_repeat_pattern.sub(r'\1\1', text)
    
    def _fix_spacing(self, text: str) -> str:
        """Corrige espaçamento"""
        # Múltiplos espaços -> espaço único
        text = self.multi_space_pattern.sub(' ', text)
        
        # Números separados por espaço
        text = self.number_pattern.sub(r'\1\2', text)
        
        # Espaços antes de pontuação
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        # Falta de espaço após pontuação
        text = re.sub(r'([.,!?;:])([A-Za-zÀ-ÿ])', r'\1 \2', text)
        
        return text
    
    def _fix_financial_terms(self, text: str) -> str:
        """Corrige termos financeiros mal transcritos"""
        text_lower = text.lower()
        
        for correct, alternatives in self.FINANCIAL_TERMS.items():
            for alt in alternatives:
                if alt.lower() in text_lower:
                    # Substitui mantendo case
                    pattern = re.compile(re.escape(alt), re.IGNORECASE)
                    text = pattern.sub(correct, text)
        
        return text
    
    def _remove_filler_words(self, text: str) -> str:
        """Remove ou reduz muletas de fala"""
        if self.aggressive_cleaning:
            # Remove completamente
            words = text.split()
            filtered = [
                w for w in words
                if w.lower() not in self.FILLER_WORDS
            ]
            return ' '.join(filtered)
        else:
            # Remove apenas repetições excessivas de muletas
            # Mantém algumas para naturalidade
            words = text.split()
            result = []
            prev_filler_count = 0
            
            for word in words:
                if word.lower() in self.FILLER_WORDS:
                    prev_filler_count += 1
                    # Permite até 1 muleta seguida
                    if prev_filler_count <= 1:
                        result.append(word)
                else:
                    prev_filler_count = 0
                    result.append(word)
            
            return ' '.join(result)
    
    def _fix_punctuation(self, text: str) -> str:
        """Corrige pontuação"""
        # Remove pontuação duplicada
        text = self.duplicate_punct_pattern.sub(r'\1', text)
        
        # Garante espaço após ponto final
        text = re.sub(r'\.([A-Z])', r'. \1', text)
        
        # Capitaliza após ponto final
        sentences = re.split(r'([.!?]+\s+)', text)
        result = []
        for i, part in enumerate(sentences):
            if i == 0 or re.match(r'[.!?]+\s+', sentences[i-1]):
                # Capitaliza primeira letra
                part = part[:1].upper() + part[1:] if part else part
            result.append(part)
        text = ''.join(result)
        
        # Capitaliza primeira letra do texto
        if text:
            text = text[0].upper() + text[1:]
        
        return text
    
    def _aggressive_clean(self, text: str) -> str:
        """
        Limpeza agressiva - remove mais elementos mas perde naturalidade.
        Use apenas se necessário.
        """
        # Remove interjeições
        interjections = ['ah', 'oh', 'uh', 'eh']
        words = text.split()
        filtered = [
            w for w in words
            if w.lower() not in interjections
        ]
        
        text = ' '.join(filtered)
        
        # Remove reticências
        text = text.replace('...', '')
        
        return text
    
    def get_cleaning_stats(
        self,
        original_segments: List[AlignedSegment],
        cleaned_segments: List[AlignedSegment]
    ) -> Dict:
        """
        Calcula estatísticas da limpeza.
        
        Returns:
            Dict com estatísticas
        """
        original_chars = sum(len(s.text) for s in original_segments)
        cleaned_chars = sum(len(s.text) for s in cleaned_segments)
        
        original_words = sum(len(s.text.split()) for s in original_segments)
        cleaned_words = sum(len(s.text.split()) for s in cleaned_segments)
        
        return {
            "original_segments": len(original_segments),
            "cleaned_segments": len(cleaned_segments),
            "removed_segments": len(original_segments) - len(cleaned_segments),
            "original_chars": original_chars,
            "cleaned_chars": cleaned_chars,
            "chars_removed": original_chars - cleaned_chars,
            "chars_reduction_pct": ((original_chars - cleaned_chars) / original_chars * 100)
                if original_chars > 0 else 0,
            "original_words": original_words,
            "cleaned_words": cleaned_words,
            "words_removed": original_words - cleaned_words
        }


def clean_transcription(
    segments: List[AlignedSegment],
    remove_fillers: bool = True,
    fix_financial_terms: bool = True,
    aggressive: bool = False
) -> List[AlignedSegment]:
    """
    Função helper para limpeza de transcrição.
    
    Args:
        segments: Segmentos a limpar
        remove_fillers: Remove muletas
        fix_financial_terms: Corrige termos financeiros
        aggressive: Limpeza agressiva
    
    Returns:
        Segmentos limpos
    """
    cleaner = TextCleaner(
        remove_fillers=remove_fillers,
        fix_financial_terms=fix_financial_terms,
        aggressive_cleaning=aggressive
    )
    return cleaner.clean_segments(segments)
