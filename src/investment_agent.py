"""
Agente de Inteligência e Análise de Investimentos.
Extrai teses de investimento usando RAG e LLMs com LangChain.
Integração com Pinecone para armazenamento vetorial persistente.
"""
import os
import logging
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_pinecone import PineconeVectorStore
    from langchain.chains import RetrievalQA
    from langchain.prompts import PromptTemplate
    from langchain.docstore.document import Document
    from pinecone import Pinecone, ServerlessSpec
except ImportError:
    raise ImportError(
        "LangChain não instalado. Execute: "
        "pip install langchain langchain-openai langchain-community langchain-pinecone "
        "pinecone-client faiss-cpu tiktoken"
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
        chunk_overlap: int = 200,
        use_pinecone: bool = True,
        pinecone_api_key: Optional[str] = None,
        pinecone_index_name: Optional[str] = None
    ):
        """
        Inicializa o agente de análise.
        
        Args:
            openai_api_key: Chave da API OpenAI
            model_name: Modelo a usar (gpt-4, gpt-3.5-turbo)
            temperature: Temperatura para geração
            chunk_size: Tamanho dos chunks para RAG
            chunk_overlap: Overlap entre chunks
            use_pinecone: Se True, usa Pinecone para armazenamento persistente
            pinecone_api_key: Chave da API Pinecone (se None, busca em .env)
            pinecone_index_name: Nome do índice Pinecone (se None, busca em .env)
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
        
        # Configurar Pinecone
        self.use_pinecone = use_pinecone
        self.pinecone_client = None
        self.pinecone_index_name = pinecone_index_name or os.getenv("PINECONE_INDEX_NAME")
        
        if self.use_pinecone:
            try:
                # Inicializar cliente Pinecone
                api_key = pinecone_api_key or os.getenv("PINECONE_API_KEY")
                if not api_key:
                    self.logger.warning("⚠️ PINECONE_API_KEY não encontrada, usando apenas FAISS temporário")
                    self.use_pinecone = False
                else:
                    self.pinecone_client = Pinecone(api_key=api_key)
                    
                    # Verificar se índice existe
                    existing_indexes = [idx.name for idx in self.pinecone_client.list_indexes()]
                    
                    if self.pinecone_index_name not in existing_indexes:
                        self.logger.info(f"📝 Criando índice Pinecone: {self.pinecone_index_name}")
                        self.pinecone_client.create_index(
                            name=self.pinecone_index_name,
                            dimension=1536,  # OpenAI text-embedding-ada-002
                            metric="cosine",
                            spec=ServerlessSpec(
                                cloud="aws",
                                region=os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
                            )
                        )
                        # Aguardar índice estar pronto
                        time.sleep(5)
                    
                    self.logger.info(f"✓ Pinecone conectado: {self.pinecone_index_name}")
                    
            except Exception as e:
                self.logger.error(f"✗ Erro ao conectar Pinecone: {e}")
                self.logger.warning("⚠️ Continuando apenas com FAISS temporário")
                self.use_pinecone = False
    
    def _create_documents_with_rich_metadata(
        self,
        transcript: TranscriptOutput
    ) -> List[Document]:
        """
        Cria documentos com metadados ricos para cada utterance.
        Resolve o problema de speakers em chunks mistos.
        
        Estratégia:
        1. Cada utterance vira um documento (não chunk arbitrário)
        2. Metadados: speaker, start, end, episode_id, title
        3. Texto inclui speaker no início para contexto
        
        Args:
            transcript: Transcrição completa
            
        Returns:
            Lista de Documents com metadados ricos
        """
        documents = []
        episode_id = transcript.episode_metadata.episode_id
        title = transcript.episode_metadata.title
        
        for utt in transcript.utterances:
            # Texto com speaker embutido (para busca semântica)
            text_with_speaker = f"{utt.speaker}: {utt.text}"
            
            # Metadados ricos
            metadata = {
                "episode_id": episode_id,
                "episode_title": title,
                "speaker": utt.speaker or "Unknown",
                "speaker_raw_id": utt.speaker_raw_id or "unknown",
                "start_time": utt.start_time,
                "end_time": utt.end_time,
                "duration": utt.end_time - utt.start_time,
                "text_length": len(utt.text),
                "timestamp": datetime.now().isoformat(),
                "source": "utterance"  # Indica que é utterance completa, não chunk
            }
            
            doc = Document(
                page_content=text_with_speaker,
                metadata=metadata
            )
            documents.append(doc)
        
        self.logger.info(f"📄 Criados {len(documents)} documentos com metadados (1 por utterance)")
        return documents
        
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
        self.logger.info(f"Analisando: {transcript.episode_metadata.title}")
        
        # Preparar contexto
        full_text = self._prepare_transcript_text(transcript)
        
        if use_rag and len(full_text) > 8000:
            # Para transcrições longas, usar RAG
            analysis = self._analyze_with_rag(transcript, full_text)
        else:
            # Para transcrições curtas, análise direta
            analysis = self._analyze_direct(transcript, full_text)
        
        return {
            'episode_id': transcript.episode_metadata.episode_id,
            'title': transcript.episode_metadata.title,
            'duration_seconds': transcript.episode_metadata.duration_seconds,
            'participants': [
                {'role': p.role, 'name': p.name}
                for p in transcript.episode_metadata.participants
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
            speaker_name = utterance.speaker or utterance.speaker_raw_id or "Unknown"
            lines.append(f"{speaker_name}: {utterance.text}")
        return "\n".join(lines)
    
    def _analyze_with_rag(
        self,
        transcript: TranscriptOutput,
        full_text: str
    ) -> str:
        """Analisa usando RAG (para transcrições longas)."""
        self.logger.info("Usando RAG para análise contextual")
        
        episode_id = transcript.episode_metadata.episode_id
        
        # 1. Criar documentos com metadados ricos (1 por utterance)
        rich_docs = self._create_documents_with_rich_metadata(transcript)
        
        # 2. Armazenar no Pinecone (persistente) se habilitado
        pinecone_vectorstore = None
        if self.use_pinecone and self.pinecone_client:
            try:
                self.logger.info("💾 Armazenando embeddings no Pinecone...")
                
                # Criar namespace único por episódio
                namespace = f"episode_{episode_id}"
                
                # Criar vector store Pinecone
                pinecone_vectorstore = PineconeVectorStore.from_documents(
                    documents=rich_docs,
                    embedding=self.embeddings,
                    index_name=self.pinecone_index_name,
                    namespace=namespace
                )
                
                self.logger.info(f"✓ {len(rich_docs)} utterances salvas no Pinecone (namespace: {namespace})")
                
            except Exception as e:
                self.logger.error(f"✗ Erro ao salvar no Pinecone: {e}")
                self.logger.warning("⚠️ Continuando com FAISS temporário")
        
        # 3. SEMPRE criar FAISS temporário para busca rápida
        self.logger.info("🔍 Criando índice FAISS temporário...")
        faiss_vectorstore = FAISS.from_documents(rich_docs, self.embeddings)
        
        # 4. Buscar documentos relevantes (usa FAISS ou Pinecone)
        vectorstore = pinecone_vectorstore if pinecone_vectorstore else faiss_vectorstore
        
        # Executar análise usando o retriever
        participants_str = ", ".join([
            f"{p.name} ({p.role})" for p in transcript.episode_metadata.participants
        ])
        
        # Buscar utterances relevantes (não chunks arbitrários!)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 10})  # Top 10 utterances
        relevant_docs = retriever.invoke("tese de investimento ativos setores riscos oportunidades")
        
        # Combinar contexto dos documentos com metadados
        context_parts = []
        for doc in relevant_docs:
            speaker = doc.metadata.get("speaker", "Unknown")
            text = doc.page_content
            # Já inclui speaker no text, mas garantir formato
            if not text.startswith(f"{speaker}:"):
                text = f"{speaker}: {text}"
            context_parts.append(text)
        
        context = "\n\n".join(context_parts)
        
        self.logger.info(f"📊 Usando {len(relevant_docs)} utterances relevantes para análise")
        
        # Criar prompt com variáveis preenchidas
        prompt_text = self.ANALYSIS_PROMPT.format(
            title=transcript.episode_metadata.title,
            participants=participants_str,
            duration=transcript.episode_metadata.duration_seconds,
            context=context
        )
        
        # Executar análise
        result = self.llm.invoke(prompt_text)
        
        # Extrair texto da resposta
        if hasattr(result, 'content'):
            return result.content
        return str(result)
    
    def _analyze_direct(
        self,
        transcript: TranscriptOutput,
        full_text: str
    ) -> str:
        """Análise direta sem RAG (para transcrições curtas)."""
        self.logger.info("Análise direta (sem RAG)")
        
        participants_str = ", ".join([
            f"{p.name} ({p.role})" for p in transcript.episode_metadata.participants
        ])
        
        prompt = self.ANALYSIS_PROMPT.format(
            title=transcript.episode_metadata.title,
            participants=participants_str,
            duration=transcript.episode_metadata.duration_seconds,
            context=full_text[:12000]  # Limitar para não estourar tokens
        )
        
        result = self.llm.predict(prompt)
        return result
    
    def query_episode_in_pinecone(
        self,
        episode_id: str,
        query: str,
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Consulta utterances de um episódio específico no Pinecone.
        
        Args:
            episode_id: ID do episódio
            query: Query de busca
            k: Número de resultados
            
        Returns:
            Lista de dicts com utterances e metadados
        """
        if not self.use_pinecone or not self.pinecone_client:
            self.logger.warning("⚠️ Pinecone não está habilitado")
            return []
        
        try:
            namespace = f"episode_{episode_id}"
            
            # Conectar ao vector store existente
            vectorstore = PineconeVectorStore(
                index_name=self.pinecone_index_name,
                embedding=self.embeddings,
                namespace=namespace
            )
            
            # Buscar similaridade
            results = vectorstore.similarity_search_with_score(query, k=k)
            
            # Formatar resultados
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "text": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata
                })
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"✗ Erro ao consultar Pinecone: {e}")
            return []
    
    def get_episode_stats_from_pinecone(self, episode_id: str) -> Dict[str, Any]:
        """
        Obtém estatísticas de um episódio no Pinecone.
        
        Args:
            episode_id: ID do episódio
            
        Returns:
            Dict com estatísticas (total utterances, speakers, etc.)
        """
        if not self.use_pinecone or not self.pinecone_client:
            return {"error": "Pinecone não habilitado"}
        
        try:
            namespace = f"episode_{episode_id}"
            index = self.pinecone_client.Index(self.pinecone_index_name)
            
            # Obter stats do namespace
            stats = index.describe_index_stats()
            namespace_stats = stats.namespaces.get(namespace, {})
            
            return {
                "episode_id": episode_id,
                "namespace": namespace,
                "total_vectors": namespace_stats.get("vector_count", 0),
                "index_name": self.pinecone_index_name
            }
            
        except Exception as e:
            self.logger.error(f"✗ Erro ao obter stats: {e}")
            return {"error": str(e)}
    
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
