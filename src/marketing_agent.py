"""
Agente de Marketing para gerar conteúdo a partir de análises de investimento.
Gera posts LinkedIn, carrosséis, e citações atribuídas.
"""
import logging
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

try:
    from langchain_openai import ChatOpenAI
    from langchain.prompts import PromptTemplate
except ImportError:
    raise ImportError(
        "LangChain não instalado. Execute: "
        "pip install langchain langchain-openai"
    )


class MarketingAgent:
    """Agente que gera conteúdo de marketing a partir de análises."""
    
    # Prompt para post LinkedIn
    LINKEDIN_POST_PROMPT = """Você é um copywriter especializado em conteúdo financeiro para LinkedIn.

Crie um post para LinkedIn baseado na seguinte análise de investimento. O post deve ser:
- Engajador e profissional
- Usar storytelling quando apropriado
- Incluir 3-5 hashtags relevantes
- Tom: {tone} (técnico para profissionais ou didático para público geral)
- Entre 150-300 palavras

Informações do episódio:
- Título: {title}
- Participantes: {participants}

Análise:
{analysis}

Post para LinkedIn:"""

    # Prompt para carrossel
    CAROUSEL_PROMPT = """Você é um designer de conteúdo educacional para redes sociais.

Crie {num_slides} slides para um carrossel no LinkedIn/Instagram sobre esta análise de investimento.

Cada slide deve ter:
- Título curto e impactante (máx 50 caracteres)
- 3-5 bullets concisos (máx 80 caracteres cada)
- Um slide deve ser introdução, um deve ser conclusão/CTA

Tom: {tone}

Informações:
{analysis}

Formato esperado:
SLIDE 1
Título: [título]
• Bullet 1
• Bullet 2
• Bullet 3

SLIDE 2
...

Carrossel:"""

    # Prompt para extrair citações
    QUOTES_PROMPT = """Você é um editor de conteúdo que identifica as melhores citações.

Analise a transcrição abaixo e extraia as 5 melhores citações para usar em marketing.

Critérios:
- Citações impactantes e memoráveis
- Que transmitam insights de investimento
- Atribuir ao speaker correto (HOST ou GUEST)
- Entre 15-40 palavras

Transcrição:
{transcript}

Participantes:
{participants}

Formato:
1. "Citação aqui" - Nome do Speaker (ROLE)
2. ...

Citações:"""

    # Prompt para sumário executivo marketing
    EXECUTIVE_SUMMARY_PROMPT = """Você é um analista que cria sumários executivos para equipes de marketing.

Crie um sumário executivo estruturado desta análise para ser usado pela equipe de marketing.

Deve incluir:
1. RESUMO (1 parágrafo)
2. PRINCIPAIS INSIGHTS (3-5 tópicos)
3. PÚBLICO-ALVO (quem deveria ler/ouvir isso)
4. ÂNGULOS DE MARKETING (3-4 formas de promover este conteúdo)
5. CALLS-TO-ACTION sugeridos

Análise:
{analysis}

Sumário Executivo:"""
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model_name: str = "gpt-4",
        temperature: float = 0.7
    ):
        """
        Inicializa o agente de marketing.
        
        Args:
            openai_api_key: Chave da API OpenAI
            model_name: Modelo a usar
            temperature: Temperatura (0.7 para mais criatividade)
        """
        self.logger = logging.getLogger('podcast_pipeline.marketing')
        
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            openai_api_key=openai_api_key
        )
    
    def generate_linkedin_post(
        self,
        analysis: Dict[str, Any],
        tone: Literal["technical", "didactic"] = "didactic"
    ) -> str:
        """
        Gera um post para LinkedIn.
        
        Args:
            analysis: Análise de investimento
            tone: Tom do post (technical ou didactic)
            
        Returns:
            Texto do post
        """
        self.logger.info(f"Gerando post LinkedIn (tom: {tone})")
        
        participants_str = ", ".join([
            f"{p['name']} ({p['role']})"
            for p in analysis.get('participants', [])
        ])
        
        prompt = self.LINKEDIN_POST_PROMPT.format(
            title=analysis.get('title', 'Episódio'),
            participants=participants_str,
            analysis=analysis.get('analysis', ''),
            tone="técnico para profissionais de mercado" if tone == "technical"
                 else "didático e acessível para público geral"
        )
        
        return self.llm.predict(prompt)
    
    def generate_carousel(
        self,
        analysis: Dict[str, Any],
        num_slides: int = 5,
        tone: Literal["technical", "didactic"] = "didactic"
    ) -> List[Dict[str, Any]]:
        """
        Gera slides de carrossel.
        
        Args:
            analysis: Análise de investimento
            num_slides: Número de slides (3-7)
            tone: Tom do conteúdo
            
        Returns:
            Lista de slides com título e bullets
        """
        self.logger.info(f"Gerando carrossel com {num_slides} slides")
        
        prompt = self.CAROUSEL_PROMPT.format(
            num_slides=num_slides,
            analysis=analysis.get('analysis', ''),
            tone="técnico" if tone == "technical" else "didático"
        )
        
        result = self.llm.predict(prompt)
        
        # Parse resultado
        slides = self._parse_carousel_output(result)
        return slides
    
    def extract_quotes(
        self,
        transcript_text: str,
        participants: List[Dict[str, str]],
        num_quotes: int = 5
    ) -> List[Dict[str, str]]:
        """
        Extrai citações impactantes da transcrição.
        
        Args:
            transcript_text: Texto completo da transcrição
            participants: Lista de participantes
            num_quotes: Número de citações
            
        Returns:
            Lista de dicts com quote, speaker_name, speaker_role
        """
        self.logger.info(f"Extraindo {num_quotes} citações")
        
        participants_str = ", ".join([
            f"{p['name']} ({p['role']})" for p in participants
        ])
        
        # Limitar texto para não estourar tokens
        max_chars = 12000
        if len(transcript_text) > max_chars:
            transcript_text = transcript_text[:max_chars] + "..."
        
        prompt = self.QUOTES_PROMPT.format(
            transcript=transcript_text,
            participants=participants_str
        )
        
        result = self.llm.predict(prompt)
        
        # Parse resultado
        quotes = self._parse_quotes_output(result)
        return quotes[:num_quotes]
    
    def generate_executive_summary(
        self,
        analysis: Dict[str, Any]
    ) -> str:
        """
        Gera sumário executivo para equipe de marketing.
        
        Args:
            analysis: Análise de investimento
            
        Returns:
            Sumário executivo formatado
        """
        self.logger.info("Gerando sumário executivo para marketing")
        
        prompt = self.EXECUTIVE_SUMMARY_PROMPT.format(
            analysis=analysis.get('analysis', '')
        )
        
        return self.llm.predict(prompt)
    
    def generate_full_marketing_package(
        self,
        analysis: Dict[str, Any],
        transcript_text: str,
        tone: Literal["technical", "didactic"] = "didactic"
    ) -> Dict[str, Any]:
        """
        Gera pacote completo de marketing.
        
        Args:
            analysis: Análise de investimento
            transcript_text: Texto da transcrição
            tone: Tom do conteúdo
            
        Returns:
            Dict com todos os materiais de marketing
        """
        self.logger.info("Gerando pacote completo de marketing")
        
        return {
            'episode_id': analysis.get('episode_id'),
            'title': analysis.get('title'),
            'generated_at': datetime.now().isoformat(),
            'tone': tone,
            'linkedin_post': self.generate_linkedin_post(analysis, tone),
            'carousel_slides': self.generate_carousel(analysis, num_slides=5, tone=tone),
            'quotes': self.extract_quotes(
                transcript_text,
                analysis.get('participants', []),
                num_quotes=5
            ),
            'executive_summary': self.generate_executive_summary(analysis),
            'metadata': {
                'model': self.llm.model_name,
                'temperature': self.llm.temperature
            }
        }
    
    def _parse_carousel_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse da saída do carrossel."""
        slides = []
        current_slide = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            if line.startswith('SLIDE'):
                if current_slide:
                    slides.append(current_slide)
                current_slide = {'title': '', 'bullets': []}
            
            elif line.startswith('Título:') or line.startswith('Title:'):
                if current_slide is not None:
                    current_slide['title'] = line.split(':', 1)[1].strip()
            
            elif line.startswith('•') or line.startswith('-'):
                if current_slide is not None:
                    bullet = line.lstrip('•-').strip()
                    if bullet:
                        current_slide['bullets'].append(bullet)
        
        if current_slide:
            slides.append(current_slide)
        
        return slides
    
    def _parse_quotes_output(self, output: str) -> List[Dict[str, str]]:
        """Parse da saída das citações."""
        quotes = []
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Formato: 1. "Quote" - Name (ROLE)
            if line and (line[0].isdigit() or line.startswith('"')):
                try:
                    # Remover numeração
                    if line[0].isdigit():
                        line = line.split('.', 1)[1].strip()
                    
                    # Extrair quote e atribuição
                    if '"' in line and '-' in line:
                        quote_part = line.split('-', 1)[0].strip().strip('"')
                        attribution = line.split('-', 1)[1].strip()
                        
                        # Extrair nome e role
                        if '(' in attribution:
                            name = attribution.split('(')[0].strip()
                            role = attribution.split('(')[1].strip(')')
                        else:
                            name = attribution
                            role = "Unknown"
                        
                        quotes.append({
                            'quote': quote_part,
                            'speaker_name': name,
                            'speaker_role': role
                        })
                except:
                    continue
        
        return quotes


def generate_marketing_from_analysis(
    analysis_path: str,
    transcript_path: str,
    output_path: str,
    tone: Literal["technical", "didactic"] = "didactic"
) -> Dict[str, Any]:
    """
    Helper function para gerar marketing a partir de arquivos.
    
    Args:
        analysis_path: Caminho do JSON de análise
        transcript_path: Caminho do JSON de transcrição
        output_path: Caminho para salvar resultado
        tone: Tom do conteúdo
        
    Returns:
        Pacote de marketing
    """
    import json
    from .models import TranscriptOutput
    
    # Carregar análise
    with open(analysis_path) as f:
        analysis = json.load(f)
    
    # Carregar transcrição
    with open(transcript_path) as f:
        transcript_data = json.load(f)
        transcript = TranscriptOutput(**transcript_data)
    
    # Preparar texto
    transcript_text = "\n".join([
        f"{u.speaker or u.speaker_raw_id or 'Unknown'}: {u.text}"
        for u in transcript.utterances
    ])
    
    # Gerar marketing
    agent = MarketingAgent()
    package = agent.generate_full_marketing_package(
        analysis,
        transcript_text,
        tone=tone
    )
    
    # Salvar
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(package, f, indent=2, ensure_ascii=False)
    
    return package
