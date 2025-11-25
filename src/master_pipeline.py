"""
Orquestrador principal: YouTube → Transcrição → Análise → Marketing
Pipeline completo para processar playlists de podcasts financeiros.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime

from .youtube_extractor import YouTubePlaylistExtractor
from .pipeline import PodcastPipeline
from .investment_agent import InvestmentAnalysisAgent
from .marketing_agent import MarketingAgent
from .models import TranscriptOutput


class MasterPipeline:
    """Pipeline completo: YouTube → Transcrição → Análise → Marketing."""
    
    def __init__(
        self,
        data_dir: str = "data",
        output_dir: str = "output",
        transcripts_dir: str = "output/transcripts",
        analyses_dir: str = "output/analyses",
        marketing_dir: str = "output/marketing"
    ):
        """
        Inicializa o pipeline mestre.
        
        Args:
            data_dir: Diretório para áudios baixados
            output_dir: Diretório base de saída
            transcripts_dir: Subdiretório para transcrições
            analyses_dir: Subdiretório para análises
            marketing_dir: Subdiretório para conteúdo de marketing
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.transcripts_dir = Path(transcripts_dir)
        self.analyses_dir = Path(analyses_dir)
        self.marketing_dir = Path(marketing_dir)
        
        # Criar diretórios
        for dir_path in [
            self.data_dir,
            self.output_dir,
            self.transcripts_dir,
            self.analyses_dir,
            self.marketing_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger('podcast_pipeline.master')
        
        # Inicializar componentes
        self.youtube_extractor = YouTubePlaylistExtractor(
            output_dir=str(self.data_dir)
        )
        
        self.transcription_pipeline = PodcastPipeline()
        self.investment_agent = InvestmentAnalysisAgent()
        self.marketing_agent = MarketingAgent()
    
    def process_playlist(
        self,
        playlist_url: str,
        max_videos: Optional[int] = None,
        marketing_tone: Literal["technical", "didactic"] = "didactic",
        skip_download: bool = False,
        skip_transcription: bool = False,
        skip_analysis: bool = False,
        skip_marketing: bool = False
    ) -> Dict[str, Any]:
        """
        Processa uma playlist completa do YouTube.
        
        Args:
            playlist_url: URL da playlist
            max_videos: Máximo de vídeos a processar
            marketing_tone: Tom do conteúdo de marketing
            skip_download: Pular download (usar áudios existentes)
            skip_transcription: Pular transcrição (usar JSONs existentes)
            skip_analysis: Pular análise
            skip_marketing: Pular geração de marketing
            
        Returns:
            Dict com estatísticas e resultados
        """
        self.logger.info("=" * 80)
        self.logger.info("INICIANDO PIPELINE COMPLETO")
        self.logger.info("=" * 80)
        
        results = {
            'playlist_url': playlist_url,
            'started_at': datetime.now().isoformat(),
            'downloads': [],
            'transcriptions': [],
            'analyses': [],
            'marketing': [],
            'errors': []
        }
        
        # ETAPA 1: Download do YouTube
        if not skip_download:
            self.logger.info("\n[1/4] DOWNLOAD DO YOUTUBE")
            try:
                downloads = self.youtube_extractor.download_playlist(
                    playlist_url,
                    max_videos=max_videos
                )
                results['downloads'] = downloads
                
                success_count = sum(1 for d in downloads if d.get('success'))
                self.logger.info(
                    f"✓ Download completo: {success_count}/{len(downloads)} sucessos"
                )
            except Exception as e:
                self.logger.error(f"✗ Erro no download: {e}")
                results['errors'].append({
                    'stage': 'download',
                    'error': str(e)
                })
                return results
        else:
            self.logger.info("\n[1/4] DOWNLOAD - PULADO")
        
        # ETAPA 2: Transcrição
        if not skip_transcription:
            self.logger.info("\n[2/4] TRANSCRIÇÃO E DIARIZAÇÃO")
            
            # Encontrar áudios
            audio_files = list(self.data_dir.glob("*.mp3")) + \
                         list(self.data_dir.glob("*.wav"))
            
            if max_videos:
                audio_files = audio_files[:max_videos]
            
            self.logger.info(f"Encontrados {len(audio_files)} áudios para transcrever")
            
            for i, audio_path in enumerate(audio_files, 1):
                try:
                    self.logger.info(f"[{i}/{len(audio_files)}] {audio_path.name}")
                    
                    episode_id = audio_path.stem
                    output_path = self.transcripts_dir / f"{episode_id}.json"
                    
                    # Processar
                    transcript = self.transcription_pipeline.process(
                        audio_path=str(audio_path),
                        episode_id=episode_id,
                        output_path=str(output_path)
                    )
                    
                    results['transcriptions'].append({
                        'episode_id': episode_id,
                        'audio_path': str(audio_path),
                        'transcript_path': str(output_path),
                        'success': True
                    })
                    
                except Exception as e:
                    self.logger.error(f"✗ Erro na transcrição: {e}")
                    results['errors'].append({
                        'stage': 'transcription',
                        'episode_id': audio_path.stem,
                        'error': str(e)
                    })
            
            self.logger.info(
                f"✓ Transcrição completa: "
                f"{len(results['transcriptions'])}/{len(audio_files)} sucessos"
            )
        else:
            self.logger.info("\n[2/4] TRANSCRIÇÃO - PULADA")
        
        # ETAPA 3: Análise de Investimento
        if not skip_analysis:
            self.logger.info("\n[3/4] ANÁLISE DE INVESTIMENTO")
            
            # Encontrar transcrições
            transcript_files = list(self.transcripts_dir.glob("*.json"))
            
            if max_videos:
                transcript_files = transcript_files[:max_videos]
            
            self.logger.info(f"Encontradas {len(transcript_files)} transcrições para analisar")
            
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
                    episode_id = transcript_path.stem
                    output_path = self.analyses_dir / f"{episode_id}_analysis.json"
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(analysis, f, indent=2, ensure_ascii=False)
                    
                    results['analyses'].append({
                        'episode_id': episode_id,
                        'analysis_path': str(output_path),
                        'success': True
                    })
                    
                except Exception as e:
                    self.logger.error(f"✗ Erro na análise: {e}")
                    results['errors'].append({
                        'stage': 'analysis',
                        'episode_id': transcript_path.stem,
                        'error': str(e)
                    })
            
            self.logger.info(
                f"✓ Análise completa: "
                f"{len(results['analyses'])}/{len(transcript_files)} sucessos"
            )
        else:
            self.logger.info("\n[3/4] ANÁLISE - PULADA")
        
        # ETAPA 4: Geração de Marketing
        if not skip_marketing:
            self.logger.info("\n[4/4] GERAÇÃO DE CONTEÚDO DE MARKETING")
            
            # Encontrar análises
            analysis_files = list(self.analyses_dir.glob("*_analysis.json"))
            
            if max_videos:
                analysis_files = analysis_files[:max_videos]
            
            self.logger.info(f"Encontradas {len(analysis_files)} análises para marketing")
            
            for i, analysis_path in enumerate(analysis_files, 1):
                try:
                    self.logger.info(f"[{i}/{len(analysis_files)}] {analysis_path.name}")
                    
                    # Carregar análise
                    with open(analysis_path) as f:
                        analysis = json.load(f)
                    
                    # Carregar transcrição correspondente
                    episode_id = analysis_path.stem.replace('_analysis', '')
                    transcript_path = self.transcripts_dir / f"{episode_id}.json"
                    
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
                    output_path = self.marketing_dir / f"{episode_id}_marketing.json"
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(marketing_package, f, indent=2, ensure_ascii=False)
                    
                    results['marketing'].append({
                        'episode_id': episode_id,
                        'marketing_path': str(output_path),
                        'success': True
                    })
                    
                except Exception as e:
                    self.logger.error(f"✗ Erro no marketing: {e}")
                    results['errors'].append({
                        'stage': 'marketing',
                        'episode_id': analysis_path.stem.replace('_analysis', ''),
                        'error': str(e)
                    })
            
            self.logger.info(
                f"✓ Marketing completo: "
                f"{len(results['marketing'])}/{len(analysis_files)} sucessos"
            )
        else:
            self.logger.info("\n[4/4] MARKETING - PULADO")
        
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
        self.logger.info(f"Sumário salvo em: {summary_path}")
        self.logger.info("=" * 80)
        
        return results


def process_outliers_playlist(
    max_videos: Optional[int] = None,
    marketing_tone: Literal["technical", "didactic"] = "didactic"
) -> Dict[str, Any]:
    """
    Helper function para processar a playlist da Outliers Advisory.
    
    Args:
        max_videos: Máximo de vídeos (None = todos)
        marketing_tone: Tom do marketing
        
    Returns:
        Resultados do pipeline
    """
    pipeline = MasterPipeline()
    
    return pipeline.process_playlist(
        playlist_url="https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
        max_videos=max_videos,
        marketing_tone=marketing_tone
    )
