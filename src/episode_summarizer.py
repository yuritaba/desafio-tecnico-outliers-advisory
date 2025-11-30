"""
Gerador de resumos de episódios para indexação no Pinecone.
Cria resumos baseados nas descrições dos vídeos do YouTube.
"""
import os
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from pinecone import Pinecone


class EpisodeSummarizer:
    """
    Gera resumos de episódios e armazena no Pinecone em namespace separado.
    """
    
    def __init__(self):
        """Inicializa o gerador de resumos."""
        self.logger = logging.getLogger('podcast_pipeline.episode_summarizer')
        
        # Inicializar OpenAI
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            raise ValueError("OPENAI_API_KEY não encontrada")
        self.openai_client = OpenAI(api_key=openai_key)
        
        # Inicializar Pinecone
        pinecone_key = os.getenv('PINECONE_API_KEY')
        if not pinecone_key:
            raise ValueError("PINECONE_API_KEY não encontrada")
        
        pc = Pinecone(api_key=pinecone_key)
        self.index = pc.Index("outliers-case")
        
        self.logger.info("✓ EpisodeSummarizer inicializado")
    
    def generate_summary_from_description(
        self,
        episode_id: str,
        episode_number: Optional[int],
        title: str,
        description: str,
        guest_name: Optional[str] = None
    ) -> str:
        """
        Gera um resumo do episódio baseado na descrição.
        
        Args:
            episode_id: ID do vídeo no YouTube
            episode_number: Número do episódio (extraído do título)
            title: Título do episódio
            description: Descrição do vídeo do YouTube
            guest_name: Nome do convidado (opcional)
        
        Returns:
            Resumo formatado do episódio
        """
        # Extrair número do episódio do título se não foi fornecido
        if episode_number is None:
            import re
            match = re.search(r'#(\d+)', title)
            episode_number = int(match.group(1)) if match else None
        
        # Criar prompt para o LLM
        episode_info = f"Episódio #{episode_number}" if episode_number else "Episódio"
        guest_info = f" com {guest_name}" if guest_name else ""
        
        prompt = f"""Você é um especialista em criar resumos concisos e informativos de episódios de podcast.

EPISÓDIO: {title}
CONVIDADO: {guest_name or "Não especificado"}
DESCRIÇÃO DO VÍDEO:
{description[:2000]}

Crie um resumo objetivo e completo deste episódio do Second Level Podcast que inclua:
1. Quem é o convidado e sua expertise/background
2. Principais temas discutidos
3. Insights ou conclusões importantes
4. Público-alvo ou relevância do conteúdo

O resumo deve ter entre 3-5 parágrafos e ser escrito de forma clara e profissional.
NÃO comece com "Neste episódio..." - vá direto ao ponto.

RESUMO:"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um especialista em criar resumos profissionais e informativos de podcasts sobre investimentos e mercado financeiro."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            summary_content = response.choices[0].message.content.strip()
            
            # Formatar resumo final
            header = f"RESUMO DO EPISÓDIO {episode_number if episode_number else ''} DO SECOND LEVEL PODCAST{guest_info}".strip()
            full_summary = f"{header}:\n\n{summary_content}"
            
            self.logger.info(f"✓ Resumo gerado para episódio {episode_id}")
            return full_summary
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar resumo: {e}")
            raise
    
    def create_summary_embedding(self, summary_text: str) -> list:
        """
        Cria embedding do resumo usando OpenAI.
        
        Args:
            summary_text: Texto do resumo
        
        Returns:
            Lista com valores do embedding (1536 dimensões)
        """
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=summary_text
            )
            
            embedding = response.data[0].embedding
            self.logger.debug(f"✓ Embedding criado ({len(embedding)} dimensões)")
            return embedding
            
        except Exception as e:
            self.logger.error(f"Erro ao criar embedding: {e}")
            raise
    
    def store_summary_in_pinecone(
        self,
        episode_id: str,
        summary_text: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Armazena resumo no Pinecone em namespace 'resumos'.
        
        Args:
            episode_id: ID do vídeo no YouTube
            summary_text: Texto completo do resumo
            metadata: Metadados adicionais (título, número do episódio, etc)
        
        Returns:
            True se armazenado com sucesso
        """
        try:
            # Criar embedding
            embedding = self.create_summary_embedding(summary_text)
            
            # ID único para o resumo
            vector_id = f"resumo_{episode_id}"
            
            # Preparar metadados
            vector_metadata = {
                "type": "resumo",
                "episode_id": episode_id,
                "text": summary_text,
                **metadata
            }
            
            # Armazenar no Pinecone (namespace: resumos)
            self.index.upsert(
                vectors=[
                    {
                        "id": vector_id,
                        "values": embedding,
                        "metadata": vector_metadata
                    }
                ],
                namespace="resumos"
            )
            
            self.logger.info(f"✓ Resumo armazenado no Pinecone (namespace: resumos): {vector_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao armazenar no Pinecone: {e}")
            return False
    
    def process_episode(
        self,
        episode_id: str,
        title: str,
        description: str,
        episode_number: Optional[int] = None,
        guest_name: Optional[str] = None,
        youtube_url: Optional[str] = None
    ) -> bool:
        """
        Processa um episódio completo: gera resumo e armazena no Pinecone.
        
        Args:
            episode_id: ID do vídeo no YouTube
            title: Título do episódio
            description: Descrição do vídeo
            episode_number: Número do episódio (opcional)
            guest_name: Nome do convidado (opcional)
            youtube_url: URL do vídeo (opcional)
        
        Returns:
            True se processado com sucesso
        """
        self.logger.info(f"📝 Processando resumo para episódio: {title}")
        
        try:
            # Gerar resumo
            summary = self.generate_summary_from_description(
                episode_id=episode_id,
                episode_number=episode_number,
                title=title,
                description=description,
                guest_name=guest_name
            )
            
            self.logger.info(f"📄 Resumo gerado ({len(summary)} caracteres)")
            
            # Preparar metadados
            metadata = {
                "title": title,
                "episode_number": episode_number,
                "guest_name": guest_name or "Desconhecido",
            }
            
            if youtube_url:
                metadata["youtube_url"] = youtube_url
            
            # Armazenar no Pinecone
            success = self.store_summary_in_pinecone(
                episode_id=episode_id,
                summary_text=summary,
                metadata=metadata
            )
            
            if success:
                self.logger.info(f"✅ Episódio {episode_id} processado com sucesso")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao processar episódio {episode_id}: {e}")
            return False
