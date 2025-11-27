"""
Orquestrador principal: YouTube → Transcrição (API AssemblyAI) → Análise → Marketing
Pipeline completo SEM download local - tudo via APIs.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime

from openai import OpenAI

from .youtube_transcriber_assemblyai import YouTubeTranscriberAssemblyAI
from .investment_agent import InvestmentAnalysisAgent
from .marketing_agent import MarketingAgent
from .models import TranscriptOutput, EpisodeMetadata, Utterance, Participant, AlignedSegment
from .podcast_start_detector import PodcastStartDetector


class MasterPipelineAPI:
    """
    Pipeline completo via APIs - agora com AssemblyAI.
    YouTube URL → AssemblyAI → Análise → Marketing
    """
    
    def __init__(
        self,
        output_dir: str = "output",
        transcripts_dir: str = "output/transcripts",
        analyses_dir: str = "output/analyses",
        marketing_dir: str = "output/marketing"
    ):
        """
        Inicializa o pipeline mestre (versão API AssemblyAI).
        
        Args:
            output_dir: Diretório base de saída
            transcripts_dir: Subdiretório para transcrições
            analyses_dir: Subdiretório para análises
            marketing_dir: Subdiretório para conteúdo de marketing
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
        
        # Inicializar componentes (AssemblyAI)
        self.youtube_transcriber = YouTubeTranscriberAssemblyAI()
        self.investment_agent = InvestmentAnalysisAgent()
        self.marketing_agent = MarketingAgent()
        self.podcast_start_detector = PodcastStartDetector()
        
        # Inicializar OpenAI para extração de nomes
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def _extract_guest_name(self, description: str) -> str:
        """
        Extrai o nome do convidado da descrição do vídeo usando OpenAI.
        
        Args:
            description: Descrição do vídeo do YouTube
            
        Returns:
            Nome completo do convidado (ex: "João Silva")
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um assistente que extrai nomes de convidados de descrições de vídeos de podcast. Responda SOMENTE o nome e sobrenome do convidado, nada mais."
                    },
                    {
                        "role": "user",
                        "content": f"Quem é o entrevistado/convidado neste vídeo? Responda SOMENTE o nome e sobrenome:\n\n{description[:1000]}"
                    }
                ],
                temperature=0,
                max_tokens=50
            )
            
            guest_name = response.choices[0].message.content.strip()
            self.logger.info(f"Convidado identificado via OpenAI: {guest_name}")
            return guest_name
            
        except Exception as e:
            self.logger.warning(f"Erro ao extrair nome do convidado: {e}. Usando 'Convidado'")
            return "Convidado"
    
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
                # ✅ OBTER LISTA DE VÍDEOS DA PLAYLIST
                playlist_info = self.youtube_transcriber._get_playlist_info(playlist_url)
                all_videos = playlist_info['entries']
                
                self.logger.info(f"Playlist: {playlist_info['title']} - {len(all_videos)} vídeos no total")
                
                # ✅ FILTRAR VÍDEOS JÁ TRANSCRITOS (ANTES de aplicar max_videos)
                videos_to_transcribe = []
                skipped_count = 0
                
                for video in all_videos:
                    video_id = video['id']
                    output_path = self.transcripts_dir / f"{video_id}.json"
                    
                    if output_path.exists():
                        skipped_count += 1
                        self.logger.debug(f"⏭  {video['title']} - JÁ TRANSCRITO, pulando...")
                    else:
                        videos_to_transcribe.append(video)
                
                self.logger.info(f"📊 Status: {skipped_count} já transcritos, {len(videos_to_transcribe)} restantes")
                
                # ✅ APLICAR max_videos APENAS NOS VÍDEOS NÃO TRANSCRITOS
                if max_videos and len(videos_to_transcribe) > max_videos:
                    self.logger.info(f"🎯 Limitando a {max_videos} vídeos novos")
                    videos_to_transcribe = videos_to_transcribe[:max_videos]
                
                # ✅ TRANSCREVER APENAS OS NOVOS
                if not videos_to_transcribe:
                    self.logger.info("✓ Todos os vídeos já foram transcritos!")
                else:
                    self.logger.info(f"\n📝 Transcrevendo {len(videos_to_transcribe)} vídeos novos...")
                    
                    for i, video in enumerate(videos_to_transcribe, 1):
                        video_url = f"https://www.youtube.com/watch?v={video['id']}"
                        self.logger.info(f"\n[{i}/{len(videos_to_transcribe)}] {video['title']}")
                        
                        try:
                            # Transcrever APENAS este vídeo
                            trans_raw = self.youtube_transcriber.transcribe_youtube_url(
                                video_url,
                                language="pt"  # AssemblyAI usa "pt" em vez de "pt-BR"
                            )
                            
                            # Converter e salvar
                            video_id = trans_raw['video_id']
                            output_path = self.transcripts_dir / f"{video_id}.json"
                            
                            transcript = self._convert_to_transcript_output(trans_raw)
                            
                            with open(output_path, 'w', encoding='utf-8') as f:
                                json.dump(transcript.model_dump(), f, indent=2, ensure_ascii=False)
                            
                            results['transcriptions'].append({
                                'video_id': video_id,
                                'title': trans_raw['title'],
                                'transcript_path': str(output_path),
                                'success': True,
                                'skipped': False
                            })
                            
                            self.logger.info(f"✓ Salvo: {output_path}")
                            
                        except Exception as e:
                            self.logger.error(f"Erro ao transcrever: {e}")
                            results['errors'].append({
                                'stage': 'transcription',
                                'video_id': video['id'],
                                'error': str(e)
                            })
                
                total_processed = len(results['transcriptions'])
                self.logger.info(f"\n✓ Transcrição completa: {total_processed} vídeos processados")
                
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
            
            # Encontrar transcrições (processar TODAS, não limitar por max_videos)
            transcript_files = list(self.transcripts_dir.glob("*.json"))
            
            self.logger.info(f"Encontradas {len(transcript_files)} transcrições")
            
            # Filtrar apenas as que NÃO têm análise
            files_to_analyze = []
            for transcript_path in transcript_files:
                video_id = transcript_path.stem
                analysis_path = self.analyses_dir / f"{video_id}_analysis.json"
                
                if not analysis_path.exists():
                    files_to_analyze.append(transcript_path)
                else:
                    self.logger.debug(f"⏭  {video_id} - análise já existe, pulando...")
            
            if files_to_analyze:
                self.logger.info(f"📊 {len(files_to_analyze)} novas análises a fazer")
            else:
                self.logger.info("✓ Todas as transcrições já foram analisadas!")
            
            for i, transcript_path in enumerate(files_to_analyze, 1):
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
                f"{len(results['analyses'])}/{len(files_to_analyze)} sucessos"
            )
        else:
            self.logger.info("\n[2/3] ANÁLISE - PULADA")
        
        # ETAPA 3: Geração de Marketing
        if not skip_marketing:
            self.logger.info("\n[3/3] GERAÇÃO DE MARKETING")
            
            # Encontrar análises (processar TODAS, não limitar por max_videos)
            analysis_files = list(self.analyses_dir.glob("*_analysis.json"))
            
            self.logger.info(f"Encontradas {len(analysis_files)} análises")
            
            # Filtrar apenas as que NÃO têm marketing
            files_to_market = []
            for analysis_path in analysis_files:
                video_id = analysis_path.stem.replace('_analysis', '')
                marketing_path = self.marketing_dir / f"{video_id}_marketing.json"
                
                if not marketing_path.exists():
                    files_to_market.append(analysis_path)
                else:
                    self.logger.debug(f"⏭  {video_id} - marketing já existe, pulando...")
            
            if files_to_market:
                self.logger.info(f"📊 {len(files_to_market)} novos materiais de marketing a gerar")
            else:
                self.logger.info("✓ Todas as análises já têm marketing gerado!")
            
            for i, analysis_path in enumerate(files_to_market, 1):
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
                        f"{u.speaker or u.speaker_raw_id or 'Unknown'}: {u.text}"
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
                f"{len(results['marketing'])}/{len(files_to_market)} sucessos"
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
        Converte resultado da API AssemblyAI para TranscriptOutput estruturado.
        Extrai nome do convidado via OpenAI e mapeia speakers corretamente.
        
        Args:
            transcription_raw: Dict da API do YouTubeTranscriberAssemblyAI
            
        Returns:
            TranscriptOutput completo
        """
        # 1. Extrair nome do convidado da descrição via OpenAI
        description = transcription_raw.get('description', '')
        guest_name = self._extract_guest_name(description)
        
        self.logger.info(f"🎙️ Speakers identificados: Samuel Ponsoni + {guest_name}")
        self.logger.info(f"✨ CONVIDADO EXTRAÍDO VIA LLM: {guest_name}")
        
        # 2. Preparar dados do AssemblyAI
        # AssemblyAI retorna utterances diretamente com speakers "A", "B", etc.
        utterances_raw = transcription_raw.get('utterances', [])
        
        # 2.5. DETECTAR INÍCIO DO PODCAST E REMOVER PROPAGANDA/INTRO
        self.logger.info("🎯 Detectando início do podcast (removendo propaganda/intro)...")
        original_count = len(utterances_raw)
        
        if utterances_raw:
            # Converter utterances do AssemblyAI para AlignedSegments
            aligned_segments_original = []
            for utt in utterances_raw:
                segment = AlignedSegment(
                    start=utt.get('start', 0.0),
                    end=utt.get('end', 0.0),
                    text=utt.get('text', ''),
                    speaker=utt.get('speaker', 'A')
                )
                aligned_segments_original.append(segment)
            
            # Detectar início (verifica primeiros 10 blocos)
            filtered_segments = self.podcast_start_detector.detect_podcast_start(
                aligned_segments_original,
                blocks_to_check=10
            )
            
            # Converter de volta para formato AssemblyAI
            utterances_raw = []
            for seg in filtered_segments:
                utterances_raw.append({
                    'start': seg.start,
                    'end': seg.end,
                    'text': seg.text,
                    'speaker': seg.speaker
                })
            
            # Log da remoção
            removed_count = original_count - len(utterances_raw)
            if removed_count > 0:
                removed_duration = self.podcast_start_detector.get_removed_duration(
                    aligned_segments_original,
                    filtered_segments
                )
                self.logger.info(f"✅ Removidos {removed_count} segmentos de propaganda/intro ({removed_duration:.1f}s)")
                self.logger.info(f"📍 Podcast inicia em: {utterances_raw[0]['start']:.1f}s")
            else:
                self.logger.info("ℹ️ Nenhuma propaganda/intro detectada")
        
        # 3. Identificar speakers únicos
        unique_speakers = sorted(set(utt['speaker'] for utt in utterances_raw))
        
        # 4. Criar mapeamento: speaker_label -> nome completo
        # REGRA: O PRIMEIRO SPEAKER A FALAR (após remover intro) é Samuel Ponsoni
        speaker_names = {}
        if len(unique_speakers) >= 2 and utterances_raw:
            # Identificar quem fala primeiro
            first_speaker = utterances_raw[0]['speaker']
            
            # Primeiro a falar = Samuel Ponsoni (HOST)
            speaker_names[first_speaker] = "Samuel Ponsoni"
            
            # Próximo speaker diferente = Convidado
            for spk in unique_speakers:
                if spk != first_speaker:
                    speaker_names[spk] = guest_name
                    break
            
            # Se houver mais speakers, marcar como GUEST_2, GUEST_3...
            guest_counter = 2
            for spk in unique_speakers:
                if spk not in speaker_names:
                    speaker_names[spk] = f"Convidado {guest_counter}"
                    guest_counter += 1
                    
        elif len(unique_speakers) == 1:
            # Apenas 1 speaker (provavelmente erro, mas processar mesmo assim)
            speaker_names[unique_speakers[0]] = "Samuel Ponsoni"
        
        # 5. Criar utterances COM nomes completos
        utterances = []
        
        if not utterances_raw:
            # Fallback: texto completo
            full_text = transcription_raw.get('text', '')
            if full_text.strip():
                utterances.append(Utterance(
                    start_time=0.0,
                    end_time=transcription_raw.get('duration', 0),
                    text=full_text,
                    speaker_raw_id="A",
                    speaker="Samuel Ponsoni"
                ))
        else:
            # Processar cada utterance do AssemblyAI
            for utt_raw in utterances_raw:
                text = utt_raw.get('text', '').strip()
                if not text:
                    continue  # Ignorar vazios
                
                speaker_label = utt_raw.get('speaker', 'A')
                speaker_name = speaker_names.get(speaker_label, "Samuel Ponsoni")
                
                utterances.append(Utterance(
                    start_time=utt_raw.get('start', 0.0),
                    end_time=utt_raw.get('end', 0.0),
                    text=text,
                    speaker_raw_id=speaker_label,
                    speaker=speaker_name
                ))
        
        # 6. Calcular tempo de fala por participante
        speaking_times = {}
        for utt in utterances:
            duration = utt.end_time - utt.start_time
            speaking_times[utt.speaker] = speaking_times.get(utt.speaker, 0) + duration
        
        # 6. Criar participantes COM nomes completos
        participants = [
            Participant(
                role="HOST",
                name="Samuel Ponsoni",
                speaker_id="0",
                total_speaking_time=speaking_times.get("Samuel Ponsoni", 0)
            ),
            Participant(
                role="GUEST_1",
                name=guest_name,
                speaker_id="1",
                total_speaking_time=speaking_times.get(guest_name, 0)
            )
        ]
        
        # 7. Criar metadados
        metadata = EpisodeMetadata(
            episode_id=transcription_raw['video_id'],
            title=transcription_raw['title'],
            description=description,
            date=transcription_raw.get('upload_date'),
            duration_seconds=transcription_raw.get('duration', 0),
            original_link=transcription_raw['video_url'],
            processing_date=datetime.now(),
            language=transcription_raw.get('language', 'pt-BR'),
            participants=participants
        )
        
        # Criar TranscriptOutput
        return TranscriptOutput(
            version="2.0.0",
            episode_metadata=metadata,
            utterances=utterances,
            processing_notes=[]
        )


def process_outliers_playlist_api(
    max_videos: Optional[int] = None,
    marketing_tone: Literal["technical", "didactic"] = "didactic"
) -> Dict[str, Any]:
    """
    Helper function para processar a playlist da Outliers via Google Cloud.
    SEM DOWNLOAD LOCAL!
    
    Args:
        max_videos: Máximo de vídeos (None = todos)
        marketing_tone: Tom do marketing
        
    Returns:
        Resultados do pipeline
    """
    pipeline = MasterPipelineAPI()
    
    return pipeline.process_playlist(
        playlist_url="https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
        max_videos=max_videos,
        marketing_tone=marketing_tone,
        language="pt-BR"
    )
