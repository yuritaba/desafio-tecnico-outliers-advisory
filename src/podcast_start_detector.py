"""
Módulo para detectar o início real do podcast.
Remove intros, propagandas, vinhetas e outros conteúdos pré-podcast.
"""
import logging
import re
from typing import List, Optional
from openai import OpenAI
import os

from .models import AlignedSegment


class PodcastStartDetector:
    """
    Detecta onde o podcast realmente começa, removendo conteúdo introdutório.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Inicializa o detector de início de podcast.
        
        Args:
            openai_api_key: Chave da API OpenAI (usa variável de ambiente se não fornecida)
        """
        self.logger = logging.getLogger('podcast_pipeline.podcast_start_detector')
        api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        
        # API key é opcional - se não tiver, usa apenas keywords
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
            self.logger.warning("OpenAI API key não encontrada - usando apenas detecção por keywords")
        
        # Palavras-chave para PRIORIDADE 3 (saudações genéricas)
        # NÃO incluir cumprimentos tradicionais (já estão na PRIORIDADE 1)
        self.greeting_keywords = [
            # Boas-vindas explícitas
            r'\bsejam bem[- ]vindos\b',
            
            # Olá direto ao público
            r'\bolá pessoal\b',
            r'\be aí pessoal\b',
            r'\bfala galera\b',
        ]
        
        # Padrões que indicam INÍCIO REAL da conversa (PRIORIDADE 2)
        self.conversation_start_patterns = [
            r'\b\w+,?\s+é uma (verdadeira\s+)?honra',  # "Nome, é uma honra", "Nome, é uma verdadeira honra"
            r'\b\w+,\s+obrigad[oa]',  # "Nome, obrigado"
            r'\b\w+,\s+seja bem[- ]vind[oa]',  # "Nome, seja bem-vindo"
            r'\b\w+,\s+prazer',  # "Nome, prazer"
        ]
    
    def detect_podcast_start(
        self,
        segments: List[AlignedSegment],
        blocks_to_check: int = 10
    ) -> List[AlignedSegment]:
        """
        Detecta onde o podcast começa e remove conteúdo anterior.
        
        Args:
            segments: Lista de segmentos alinhados
            blocks_to_check: Quantos blocos iniciais verificar (padrão: 10 para cobrir intros longas)
        
        Returns:
            Lista de segmentos a partir do início real do podcast
        """
        if not segments:
            self.logger.warning("Lista de segmentos vazia")
            return segments
        
        self.logger.info(f"Detectando início do podcast em {len(segments)} segmentos")
        self.logger.info(f"📊 Primeiro segmento: start={segments[0].start:.1f}s, text='{segments[0].text[:60]}...'")
        self.logger.info(f"📊 Segundo segmento: start={segments[1].start if len(segments) > 1 else 'N/A'}s, text='{segments[1].text[:60] if len(segments) > 1 else 'N/A'}...'")
        
        # Primeiro: tenta encontrar por palavras-chave
        keyword_start_idx = self._find_start_by_keywords(segments, blocks_to_check)
        
        if keyword_start_idx is not None:
            self.logger.info(
                f"✓ Início detectado por palavra-chave no segmento {keyword_start_idx} "
                f"({segments[keyword_start_idx].start:.1f}s)"
            )
            self.logger.info(
                f"📊 REMOÇÃO: {keyword_start_idx} segmentos serão removidos"
            )
            self.logger.info(
                f"📊 ANTES: {len(segments)} segmentos | DEPOIS: {len(segments[keyword_start_idx:])} segmentos"
            )
            return segments[keyword_start_idx:]
        
        # Segundo: usa LLM para identificar o início
        self.logger.info("Palavra-chave não encontrada, usando GPT-3.5 para detecção")
        llm_start_idx = self._find_start_by_llm(segments, blocks_to_check)
        
        if llm_start_idx is not None:
            self.logger.info(
                f"✓ Início detectado por LLM no segmento {llm_start_idx} "
                f"({segments[llm_start_idx].start:.1f}s)"
            )
            return segments[llm_start_idx:]
        
        # Se não encontrou, retorna original
        self.logger.warning(
            "⚠ Não foi possível detectar início do podcast, "
            "mantendo todos os segmentos"
        )
        return segments
    
    def _find_start_by_keywords(
        self,
        segments: List[AlignedSegment],
        blocks_to_check: int
    ) -> Optional[int]:
        """
        Busca o início do podcast por palavras-chave.
        
        PRIORIDADE 1: Cumprimentos tradicionais (bom dia, boa tarde, boa noite)
        PRIORIDADE 2: Chamadas diretas ao convidado (Nome, é uma honra...)
        PRIORIDADE 3: Outras saudações genéricas
        
        Returns:
            Índice do segmento onde o podcast começa, ou None se não encontrado
        """
        # Verifica apenas os primeiros blocos
        segments_to_check = segments[:min(blocks_to_check, len(segments))]
        
        # PRIORIDADE 1: Cumprimentos tradicionais (bom dia, boa tarde, boa noite)
        traditional_greetings = [
            r'\bbom dia\b',
            r'\bboa tarde\b',
            r'\bboa noite\b',
        ]
        
        for idx, segment in enumerate(segments_to_check):
            text = segment.text
            text_lower = text.lower()
            
            for pattern in traditional_greetings:
                match = re.search(pattern, text_lower)
                if match:
                    # Encontrou cumprimento tradicional!
                    start_pos = match.start()
                    
                    self.logger.info(
                        f"🎯 CUMPRIMENTO TRADICIONAL detectado no segmento {idx}: '{text[start_pos:start_pos+80]}...'"
                    )
                    
                    # Se há propaganda antes do cumprimento, cortar
                    if start_pos > 0:
                        # Pegar texto original (case-sensitive) a partir do match
                        match_original = re.search(pattern, text, re.IGNORECASE)
                        if match_original:
                            cut_text = text[match_original.start():].strip()
                            self.logger.info(f"✂️ Cortando propaganda antes do cumprimento")
                            self.logger.info(f"❌ ANTES: '{text[:100]}...'")
                            self.logger.info(f"✅ DEPOIS: '{cut_text[:100]}...'")
                            segment.text = cut_text
                    
                    return idx
        
        # PRIORIDADE 2: Chamadas diretas ao convidado (Nome, é uma honra...)
        self.logger.info("⚠️ Não encontrou cumprimentos tradicionais, buscando chamadas diretas...")
        
        for idx, segment in enumerate(segments_to_check):
            text = segment.text
            
            for pattern in self.conversation_start_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    start_pos = match.start()
                    
                    self.logger.info(
                        f"🎯 CHAMADA DIRETA detectada no segmento {idx}: '{text[start_pos:start_pos+80]}...'"
                    )
                    
                    if start_pos > 0:
                        cut_text = text[start_pos:].strip()
                        self.logger.info(f"✂️ Cortando propaganda antes da chamada")
                        self.logger.info(f"❌ ANTES: '{text[:100]}...'")
                        self.logger.info(f"✅ DEPOIS: '{cut_text[:100]}...'")
                        segment.text = cut_text
                    
                    return idx
        
        # PRIORIDADE 3: Outras saudações genéricas
        self.logger.info("⚠️ Não encontrou chamadas diretas, buscando saudações genéricas...")
        
        all_matches = []
        
        for idx, segment in enumerate(segments_to_check):
            text_lower = segment.text.lower()
            
            # Verifica cada palavra-chave
            for pattern in self.greeting_keywords:
                match = re.search(pattern, text_lower)
                if match:
                    all_matches.append({
                        'idx': idx,
                        'pattern': pattern,
                        'match': match,
                        'segment': segment
                    })
        
        # Se não encontrou nenhuma palavra-chave
        if not all_matches:
            return None
        
        # Escolher o PRIMEIRO match (menor índice de segmento)
        first_match = min(all_matches, key=lambda x: x['idx'])
        idx = first_match['idx']
        segment = first_match['segment']
        match = first_match['match']
        pattern = first_match['pattern']
        
        # Encontrou! Vamos cortar o texto a partir da palavra-chave
        start_pos = match.start()
        
        # Se a palavra-chave está no meio do texto (há propaganda antes)
        if start_pos > 0:
            # Cortar o texto original a partir da palavra-chave
            text_original = segment.text
            # Encontrar a posição no texto original (case-insensitive)
            match_original = re.search(pattern, text_original, re.IGNORECASE)
            if match_original:
                cut_text = text_original[match_original.start():].strip()
                
                self.logger.info(
                    f"🎯 Palavra-chave encontrada no MEIO do segmento {idx}"
                )
                self.logger.info(f"❌ ANTES (com propaganda): '{segment.text[:100]}...'")
                self.logger.info(f"✅ DEPOIS (cortado): '{cut_text[:100]}...'")
                
                # Atualizar o segmento para conter apenas a parte após a palavra-chave
                segment.text = cut_text
                
                self.logger.info(
                    f"✂️ Propaganda removida DENTRO do segmento {idx}"
                )
        else:
            # Palavra-chave está no início, sem propaganda antes
            self.logger.info(
                f"✅ Palavra-chave encontrada no INÍCIO do segmento {idx}: "
                f"'{segment.text[:80]}...'"
            )
        
        return idx
        
        return None
    
    def _find_start_by_llm(
        self,
        segments: List[AlignedSegment],
        blocks_to_check: int
    ) -> Optional[int]:
        """
        Usa GPT-3.5 para identificar onde o podcast começa.
        
        Returns:
            Índice do segmento onde o podcast começa, ou None se não encontrado
        """
        # Se não tem client configurado, não pode usar LLM
        if not self.client:
            self.logger.warning("Cliente OpenAI não configurado - pulando detecção por LLM")
            return None
        
        # Pega os primeiros blocos
        segments_to_check = segments[:min(blocks_to_check, len(segments))]
        
        # Formata os segmentos para o LLM
        segments_text = ""
        for idx, seg in enumerate(segments_to_check):
            segments_text += f"[SEGMENTO {idx}] {seg.text}\n\n"
        
        # Prompt para o LLM
        prompt = f"""Você é um especialista em análise de podcasts. Abaixo estão os primeiros segmentos de um episódio.

Sua tarefa é identificar EXATAMENTE onde o podcast REALMENTE começa (excluindo propagandas, vinhetas, intros, comerciais e cortes que vêm ANTES da conversa começar).

O podcast COMEÇA quando:
- O apresentador DIRETAMENTE chama o convidado pelo nome ("Howard, é uma honra...", "Fulano, obrigado por estar aqui") OU
- O apresentador cumprimenta E já está na conversa (bom dia + pergunta) OU
- O apresentador agradece/recebe o convidado DE FORMA PESSOAL ("obrigado por aceitar", "prazer ter você aqui") OU
- Inicia-se uma PERGUNTA ou DIÁLOGO entre apresentador e convidado

O podcast NÃO COMEÇOU se:
- É "bem-vindo ao episódio número X" (intro formal genérica)
- É propaganda de patrocinador ou da própria empresa
- É vinheta/música de abertura
- São cortes ou trechos antecipados do episódio
- É apenas narração institucional/descritiva sem interação pessoal
- Está falando SOBRE o convidado, mas não COM o convidado ainda

EXEMPLO DE INTRO FORMAL (NÃO é o início):
"bem-vindo ao episódio número 4 do podcast... [propaganda da empresa]... Howard, é uma verdadeira honra..."
INÍCIO REAL: Quando diz "Howard, é uma verdadeira honra..." (chamou o convidado diretamente)

Segmentos:
{segments_text}

INSTRUÇÕES CRÍTICAS:
1. Identifique o NÚMERO do segmento onde a CONVERSA REAL DO PODCAST começa
2. Procure pelo momento em que o host CHAMA O CONVIDADO PELO NOME ou faz a PRIMEIRA PERGUNTA
3. Ignore intros formais como "bem-vindo ao episódio X" - procure pela CONVERSA
4. Responda APENAS com o número do segmento (exemplo: "2")
5. NÃO adicione explicações, NÃO adicione texto extra
6. Se o podcast já começa no segmento 0 COM CONVERSA REAL, responda "0"

Resposta (apenas o número):"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um assistente que responde APENAS com números."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,
                max_tokens=10
            )
            
            answer = response.choices[0].message.content.strip()
            self.logger.info(f"Resposta do LLM: '{answer}'")
            
            # Extrai o número da resposta
            match = re.search(r'\d+', answer)
            if match:
                segment_idx = int(match.group())
                
                # Valida o índice
                if 0 <= segment_idx < len(segments_to_check):
                    self.logger.info(
                        f"LLM identificou início no segmento {segment_idx}: "
                        f"'{segments_to_check[segment_idx].text[:80]}...'"
                    )
                    return segment_idx
                else:
                    self.logger.warning(
                        f"LLM retornou índice inválido: {segment_idx}"
                    )
            else:
                self.logger.warning(f"Não foi possível extrair número da resposta do LLM")
                
        except Exception as e:
            self.logger.error(f"Erro ao chamar LLM: {e}")
        
        return None
    
    def get_removed_duration(
        self,
        original_segments: List[AlignedSegment],
        filtered_segments: List[AlignedSegment]
    ) -> float:
        """
        Calcula quanto tempo foi removido do início.
        
        Returns:
            Duração em segundos do conteúdo removido
        """
        if not filtered_segments or not original_segments:
            return 0.0
        
        return filtered_segments[0].start - original_segments[0].start
