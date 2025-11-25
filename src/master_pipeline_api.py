"""
Orquestrador principal: YouTube → Transcrição (API direta) → Análise → Marketing
Pipeline completo SEM download local - tudo via APIs.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime

from .youtube_transcriber import YouTubeTranscriber
from .investment_agent import InvestmentAnalysisAgent
from .marketing_agent import MarketingAgent
from .models import TranscriptOutput, EpisodeMetadata, Utterance, Participant


class MasterPipelineAPI:
    """
    Pipeline completo via APIs (SEM download local).
    YouTube URL → OpenAI Whisper API → Análise → Marketing
    """
    
    def __init__(
        self,
        output_dir: str = "output",
        transcripts_dir: str = "output/transcripts",
        analyses_dir: str = "output/analyses",
        marketing_dir: str = "output/marketing",
        api_provider: Literal["openai", "google"] = "openai"
    ):
        """
        Inicializa o pipeline mestre (versão API).
        
        Args:
            output_dir: Diretório base de saída
            transcripts_dir: Subdiretório para transcrições
            analyses_dir: Subdiretório para análises
            marketing_dir: Subdiretório para conteúdo de marketing
            api_provider: Provedor da API de transcrição
        """
        self.output_dir = Path(output_dir)
        self.transcripts_dir = Path(transcripts_dir)
        self.analyses_dir = Path(analyses_dir)
        self.marketing_dir = Path(marketing_dir)
        
        # Criar diretórios
        for dir_path in [
            self.output_dir,
            self.transcripts_dir,
            self.analyses_dir,
            self.marketing_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger('podcast_pipeline.master_api')
        
        # Inicializar componentes (SEM youtube_extractor local)
        self.youtube_transcriber = YouTubeTranscriber(api_provider=api_provider)
        self.investment_agent = InvestmentAnalysisAgent()
        self.marketing_agent = MarketingAgent()
    
    def process_playlist(
        self,
        playlist_url: str,
        max_videos: Optional[int] = None,
        marketing_tone: Literal["technical", "didactic"] = "didactic",
        language: str = "pt",
        skip_transcription: bool = False,
        skip_analysis: bool = False,
        skip_marketing: bool = False
    ) -> Dict[str, Any]:
        """
        Processa uma playlist completa do YouTube (via APIs).
        
        Args:
            playlist_url: URL da playlist
            max_videos: Máximo de vídeos a processar
            marketing_tone: Tom do conteúdo de marketing
            language: Idioma da transcrição
            skip_transcription: Pular transcrição (usar JSONs existentes)
            skip_analysis: Pular análise
            skip_marketing: Pular geração de marketing
            
        Returns:
            Dict com estatísticas e resultados
        """
        self.logger.info("=" * 80)
        self.logger.info("PIPELINE COMPLETO (VIA APIs - SEM DOWNLOAD)")
        self.logger.info("=" * 80)
        
        results = {
            'playlist_url': playlist_url,
            'started_at': datetime.now().isoformat(),
            'transcriptions': [],
            'analyses': [],
            'marketing': [],
            'errors': []
        }
        
        # ETAPA 1: Transcrição via API (direto da URL)
        if not skip_transcription:
            self.logger.info("\n[1/3] TRANSCRIÇÃO VIA API")
            
            try:
                # Transcrever playlist inteira via API
                transcriptions_raw = self.youtube_transcriber.transcribe_playlist(
                    playlist_url,
                    max_videos=max_videos,
                    language=language
                )
                
                # Converter para formato estruturado e salvar
                for i, trans_raw in enumerate(transcriptions_raw, 1):
                    if not trans_raw.get('success'):
                        self.logger.warning(f"[{i}] Falha: {trans_raw.get('error')}")
                        results['errors'].append({
                            'stage': 'transcription',
                            'video_id': trans_raw.get('video_id'),
                            'error': trans_raw.get('error')
                        })
                        continue
                    
                    try:
                        # Converter para TranscriptOutput
                        transcript = self._convert_to_transcript_output(trans_raw)
                        
                        # Salvar
                        video_id = trans_raw['video_id']
                        output_path = self.transcripts_dir / f"{video_id}.json"
                        
                        with open(output_path, 'w', encoding='utf-8') as f:
                            json.dump(transcript.model_dump(), f, indent=2, ensure_ascii=False)
                        
                        results['transcriptions'].append({
                            'video_id': video_id,
                            'title': trans_raw['title'],
                            'transcript_path': str(output_path),
                            'success': True
                        })
                        
                        self.logger.info(f"✓ [{i}] {trans_raw['title']}")
                        
                    except Exception as e:
                        self.logger.error(f"Erro ao processar transcrição: {e}")
                        results['errors'].append({
                            'stage': 'transcription_processing',
                            'video_id': trans_raw.get('video_id'),
                            'error': str(e)
                        })
                
                self.logger.info(
                    f"✓ Transcrição completa: "
                    f"{len(results['transcriptions'])}/{len(transcriptions_raw)} sucessos"
                )
                
            except Exception as e:
                self.logger.error(f"✗ Erro na transcrição: {e}")
                results['errors'].append({
                    'stage': 'transcription_api',
                    'error': str(e)
                })
                return results
        else:
            self.logger.info("\n[1/3] TRANSCRIÇÃO - PULADA")
        
        # ETAPA 2: Análise de Investimento
        if not skip_analysis:
            self.logger.info("\n[2/3] ANÁLISE DE INVESTIMENTO")
            
            # Encontrar transcrições
            transcript_files = list(self.transcripts_dir.glob("*.json"))
            
            if max_videos:
                transcript_files = transcript_files[:max_videos]
            
            self.logger.info(f"Encontradas {len(transcript_files)} transcrições")
            
            for i, transcript_path in enumerate(transcript_files, 1):
                try:
                    self.logger.info(f"[{i}/{len(transcript_files)}] {transcript_path.name}")
                    
                    # Carregar transcrição
                    with open(transcript_path) as f:
                        transcript_data = json.load(f)
                        transcript = TranscriptOutput(**transcript_data)
                    
                    # Analisar
                    analysis = self.investment_agent.analyze_transcript(
                        transcript,
                        use_rag=True
                    )
                    
                    # Salvar
                    video_id = transcript_path.stem
                    output_path = self.analyses_dir / f"{video_id}_analysis.json"
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(analysis, f, indent=2, ensure_ascii=False)
                    
                    results['analyses'].append({
                        'video_id': video_id,
                        'analysis_path': str(output_path),
                        'success': True
                    })
                    
                except Exception as e:
                    self.logger.error(f"✗ Erro na análise: {e}")
                    results['errors'].append({
                        'stage': 'analysis',
                        'video_id': transcript_path.stem,
                        'error': str(e)
                    })
            
            self.logger.info(
                f"✓ Análise completa: "
                f"{len(results['analyses'])}/{len(transcript_files)} sucessos"
            )
        else:
            self.logger.info("\n[2/3] ANÁLISE - PULADA")
        
        # ETAPA 3: Geração de Marketing
        if not skip_marketing:
            self.logger.info("\n[3/3] GERAÇÃO DE MARKETING")
            
            # Encontrar análises
            analysis_files = list(self.analyses_dir.glob("*_analysis.json"))
            
            if max_videos:
                analysis_files = analysis_files[:max_videos]
            
            self.logger.info(f"Encontradas {len(analysis_files)} análises")
            
            for i, analysis_path in enumerate(analysis_files, 1):
                try:
                    self.logger.info(f"[{i}/{len(analysis_files)}] {analysis_path.name}")
                    
                    # Carregar análise
                    with open(analysis_path) as f:
                        analysis = json.load(f)
                    
                    # Carregar transcrição correspondente
                    video_id = analysis_path.stem.replace('_analysis', '')
                    transcript_path = self.transcripts_dir / f"{video_id}.json"
                    
                    with open(transcript_path) as f:
                        transcript_data = json.load(f)
                        transcript = TranscriptOutput(**transcript_data)
                    
                    # Preparar texto da transcrição
                    transcript_text = "\n".join([
                        f"{u.speaker_name or u.speaker_id}: {u.text}"
                        for u in transcript.utterances
                    ])
                    
                    # Gerar marketing
                    marketing_package = self.marketing_agent.generate_full_marketing_package(
                        analysis,
                        transcript_text,
                        tone=marketing_tone
                    )
                    
                    # Salvar
                    output_path = self.marketing_dir / f"{video_id}_marketing.json"
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(marketing_package, f, indent=2, ensure_ascii=False)
                    
                    results['marketing'].append({
                        'video_id': video_id,
                        'marketing_path': str(output_path),
                        'success': True
                    })
                    
                except Exception as e:
                    self.logger.error(f"✗ Erro no marketing: {e}")
                    results['errors'].append({
                        'stage': 'marketing',
                        'video_id': analysis_path.stem.replace('_analysis', ''),
                        'error': str(e)
                    })
            
            self.logger.info(
                f"✓ Marketing completo: "
                f"{len(results['marketing'])}/{len(analysis_files)} sucessos"
            )
        else:
            self.logger.info("\n[3/3] MARKETING - PULADO")
        
        # Finalizar
        results['completed_at'] = datetime.now().isoformat()
        
        # Salvar sumário
        summary_path = self.output_dir / f"pipeline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info("PIPELINE COMPLETO")
        self.logger.info(f"Transcrições: {len(results['transcriptions'])}")
        self.logger.info(f"Análises: {len(results['analyses'])}")
        self.logger.info(f"Marketing: {len(results['marketing'])}")
        self.logger.info(f"Erros: {len(results['errors'])}")
        self.logger.info(f"Sumário: {summary_path}")
        self.logger.info("=" * 80)
        
        return results
    
    def _convert_to_transcript_output(
        self,
        transcription_raw: Dict[str, Any]
    ) -> TranscriptOutput:
        """
        Converte resultado da API para TranscriptOutput estruturado.
        
        Args:
            transcription_raw: Dict da API do YouTubeTranscriber
            
        Returns:
            TranscriptOutput completo
        """
        # Criar metadados
        metadata = EpisodeMetadata(
            episode_id=transcription_raw['video_id'],
            title=transcription_raw['title'],
            description=transcription_raw.get('description', ''),
            date=transcription_raw.get('upload_date'),
            duration_seconds=transcription_raw.get('duration', 0),
            original_link=transcription_raw['video_url'],
            processing_date=datetime.now(),
            language=transcription_raw.get('language', 'pt'),
            participants=[]  # Será preenchido depois
        )
        
        # Criar utterances dos segmentos
        utterances = []
        transcription = transcription_raw.get('transcription', {})
        segments = transcription.get('segments', [])
        
        if not segments:
            # Se não tiver segmentos, criar um único utterance com texto completo
            full_text = transcription.get('text', '')
            utterances.append(Utterance(
                start_time=0.0,
                end_time=transcription_raw.get('duration', 0),
                text=full_text,
                speaker_id="UNKNOWN",
                speaker_role="UNKNOWN"
            ))
        else:
            # Criar utterance para cada segmento
            for seg in segments:
                utterances.append(Utterance(
                    start_time=seg.get('start', 0.0),
                    end_time=seg.get('end', 0.0),
                    text=seg.get('text', ''),
                    speaker_id="UNKNOWN",  # API não faz diarização
                    speaker_role="UNKNOWN"
                ))
        
        # Criar participantes (genérico, pois API não identifica)
        participants = [
            Participant(
                role="UNKNOWN",
                name="Speaker",
                total_speaking_time=transcription_raw.get('duration', 0)
            )
        ]
        
        # Criar TranscriptOutput
        return TranscriptOutput(
            version="2.0.0",
            episode_metadata=metadata,
            utterances=utterances,
            processing_notes=[]
        )


def process_outliers_playlist_api(
    max_videos: Optional[int] = None,
    marketing_tone: Literal["technical", "didactic"] = "didactic",
    api_provider: Literal["openai", "google"] = "openai"
) -> Dict[str, Any]:
    """
    Helper function para processar a playlist da Outliers via APIs.
    SEM DOWNLOAD LOCAL!
    
    Args:
        max_videos: Máximo de vídeos (None = todos)
        marketing_tone: Tom do marketing
        api_provider: Provedor da API
        
    Returns:
        Resultados do pipeline
    """
    pipeline = MasterPipelineAPI(api_provider=api_provider)
    
    return pipeline.process_playlist(
        playlist_url="https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
        max_videos=max_videos,
        marketing_tone=marketing_tone
    )
