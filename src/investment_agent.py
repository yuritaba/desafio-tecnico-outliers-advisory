"""
Agente de Inteligência e Análise de Investimentos.
Extrai teses de investimento usando RAG e LLMs com LangChain.
"""
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain.chains import RetrievalQA
    from langchain.prompts import PromptTemplate
    from langchain.docstore.document import Document
except ImportError:
    raise ImportError(
        "LangChain não instalado. Execute: "
        "pip install langchain langchain-openai langchain-community faiss-cpu tiktoken"
    )

from .models import TranscriptOutput


class InvestmentAnalysisAgent:
    """Agente que analisa transcrições para extrair teses de investimento."""
    
    ANALYSIS_PROMPT = """Você é um analista financeiro especializado em identificar teses de investimento em podcasts.

Analise a seguinte transcrição de podcast financeiro e extraia:

1. TESE PRINCIPAL DE INVESTIMENTO
   - Qual a principal recomendação ou visão de investimento apresentada?
   - Qual o raciocínio fundamental por trás dessa tese?

2. ATIVOS/SETORES MENCIONADOS
   - Quais ações, fundos, classes de ativos ou setores foram discutidos?
   - Qual a visão sobre cada um (positiva/negativa/neutra)?

3. CONTEXTO MACROECONÔMICO
   - Quais fatores econômicos foram mencionados (juros, inflação, câmbio)?
   - Qual o impacto desses fatores na tese?

4. HORIZONTE E RISCOS
   - Qual o horizonte temporal da tese?
   - Quais riscos foram mencionados?

5. FRASES-CHAVE
   - Identifique 3-5 citações diretas mais relevantes com o nome do speaker

Contexto da transcrição:
- Título: {title}
- Participantes: {participants}
- Duração: {duration} segundos

Transcrição:
{context}

Forneça uma análise estruturada e objetiva."""

    SUMMARY_PROMPT = """Com base nas análises anteriores, crie um SUMÁRIO EXECUTIVO sobre as teses de investimento discutidas neste episódio.

O sumário deve ter:
- 1 parágrafo introdutório (contexto do episódio)
- Principais teses em tópicos
- Conclusão com recomendação geral

Análises:
{analyses}

Sumário Executivo:"""
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model_name: str = "gpt-4",
        temperature: float = 0.3,
        chunk_size: int = 2000,
        chunk_overlap: int = 200
    ):
        """
        Inicializa o agente de análise.
        
        Args:
            openai_api_key: Chave da API OpenAI
            model_name: Modelo a usar (gpt-4, gpt-3.5-turbo)
            temperature: Temperatura para geração
            chunk_size: Tamanho dos chunks para RAG
            chunk_overlap: Overlap entre chunks
        """
        self.logger = logging.getLogger('podcast_pipeline.investment')
        
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            openai_api_key=openai_api_key
        )
        
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
    def analyze_transcript(
        self,
        transcript: TranscriptOutput,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Analisa uma transcrição para extrair teses de investimento.
        
        Args:
            transcript: Transcrição processada
            use_rag: Se True, usa RAG para análise contextual
            
        Returns:
            Dict com análise estruturada
        """
        self.logger.info(f"Analisando: {transcript.metadata.title}")
        
        # Preparar contexto
        full_text = self._prepare_transcript_text(transcript)
        
        if use_rag and len(full_text) > 8000:
            # Para transcrições longas, usar RAG
            analysis = self._analyze_with_rag(transcript, full_text)
        else:
            # Para transcrições curtas, análise direta
            analysis = self._analyze_direct(transcript, full_text)
        
        return {
            'episode_id': transcript.metadata.episode_id,
            'title': transcript.metadata.title,
            'duration_seconds': transcript.metadata.duration_seconds,
            'participants': [
                {'role': p.role, 'name': p.name}
                for p in transcript.participants
            ],
            'analysis': analysis,
            'metadata': {
                'model': self.llm.model_name,
                'method': 'rag' if use_rag and len(full_text) > 8000 else 'direct',
                'text_length': len(full_text)
            }
        }
    
    def _prepare_transcript_text(self, transcript: TranscriptOutput) -> str:
        """Prepara texto da transcrição para análise."""
        lines = []
        for utterance in transcript.utterances:
            speaker_name = utterance.speaker_name or utterance.speaker_id
            lines.append(f"{speaker_name}: {utterance.text}")
        return "\n".join(lines)
    
    def _analyze_with_rag(
        self,
        transcript: TranscriptOutput,
        full_text: str
    ) -> str:
        """Analisa usando RAG (para transcrições longas)."""
        self.logger.info("Usando RAG para análise contextual")
        
        # Criar documentos
        docs = [
            Document(
                page_content=chunk,
                metadata={'source': transcript.metadata.episode_id}
            )
            for chunk in self.text_splitter.split_text(full_text)
        ]
        
        # Criar vector store
        vectorstore = FAISS.from_documents(docs, self.embeddings)
        
        # Criar chain de QA
        prompt = PromptTemplate(
            template=self.ANALYSIS_PROMPT,
            input_variables=["context", "title", "participants", "duration"]
        )
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
            chain_type_kwargs={"prompt": prompt}
        )
        
        # Executar análise
        participants_str = ", ".join([
            f"{p.name} ({p.role})" for p in transcript.participants
        ])
        
        result = qa_chain.run({
            "title": transcript.metadata.title,
            "participants": participants_str,
            "duration": transcript.metadata.duration_seconds,
            "context": full_text[:10000]  # Limitar contexto inicial
        })
        
        return result
    
    def _analyze_direct(
        self,
        transcript: TranscriptOutput,
        full_text: str
    ) -> str:
        """Análise direta sem RAG (para transcrições curtas)."""
        self.logger.info("Análise direta (sem RAG)")
        
        participants_str = ", ".join([
            f"{p.name} ({p.role})" for p in transcript.participants
        ])
        
        prompt = self.ANALYSIS_PROMPT.format(
            title=transcript.metadata.title,
            participants=participants_str,
            duration=transcript.metadata.duration_seconds,
            context=full_text[:12000]  # Limitar para não estourar tokens
        )
        
        result = self.llm.predict(prompt)
        return result
    
    def analyze_batch(
        self,
        transcripts: List[TranscriptOutput],
        use_rag: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Analisa múltiplas transcrições em batch.
        
        Args:
            transcripts: Lista de transcrições
            use_rag: Usar RAG
            
        Returns:
            Lista de análises
        """
        analyses = []
        for i, transcript in enumerate(transcripts, 1):
            self.logger.info(f"[{i}/{len(transcripts)}] Analisando...")
            analysis = self.analyze_transcript(transcript, use_rag=use_rag)
            analyses.append(analysis)
        
        return analyses
    
    def create_executive_summary(
        self,
        analyses: List[Dict[str, Any]]
    ) -> str:
        """
        Cria sumário executivo consolidando múltiplas análises.
        
        Args:
            analyses: Lista de análises
            
        Returns:
            Sumário executivo em texto
        """
        if not analyses:
            return "Nenhuma análise disponível."
        
        # Consolidar análises
        analyses_text = "\n\n---\n\n".join([
            f"Episódio: {a['title']}\n{a['analysis']}"
            for a in analyses
        ])
        
        prompt = self.SUMMARY_PROMPT.format(analyses=analyses_text)
        summary = self.llm.predict(prompt)
        
        return summary


def analyze_transcripts_from_files(
    transcript_paths: List[str],
    output_path: Optional[str] = None,
    use_rag: bool = True
) -> List[Dict[str, Any]]:
    """
    Helper function para analisar múltiplos arquivos de transcrição.
    
    Args:
        transcript_paths: Caminhos dos JSONs de transcrição
        output_path: Caminho para salvar análises (opcional)
        use_rag: Usar RAG
        
    Returns:
        Lista de análises
    """
    import json
    
    agent = InvestmentAnalysisAgent()
    
    transcripts = []
    for path in transcript_paths:
        with open(path) as f:
            data = json.load(f)
            transcripts.append(TranscriptOutput(**data))
    
    analyses = agent.analyze_batch(transcripts, use_rag=use_rag)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analyses, f, indent=2, ensure_ascii=False)
    
    return analyses
