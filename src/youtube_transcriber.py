"""
Módulo para transcrever vídeos do YouTube via Google Cloud Speech-to-Text.
Inclui diarização para identificar speakers (Samuel e Convidado).
"""
import os
import io
import logging
from typing import Dict, Any, List, Optional, Literal
from pathlib import Path
import tempfile
import subprocess
import ffmpeg

try:
    import yt_dlp
    from google.cloud import speech_v1p1beta1 as speech
    from google.cloud import storage
    from google.oauth2 import service_account
except ImportError:
    raise ImportError(
        "Dependências não instaladas. Execute: "
        "pip install yt-dlp google-cloud-speech google-cloud-storage ffmpeg-python"
    )


class YouTubeTranscriber:
    """
    Transcreve vídeos do YouTube via Google Cloud Speech-to-Text.
    Inclui diarização para identificar speakers (Samuel e Convidado).
    """
    
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        gcs_bucket: Optional[str] = None,
        temp_dir: Optional[str] = None
    ):
        """
        Inicializa o transcriber com Google Cloud.
        
        Args:
            credentials_path: Caminho para JSON de credenciais (se None, usa keys/desafio-outliers-*.json)
            gcs_bucket: Nome do bucket GCS (se None, usa desafio-outliers-audio-temp)
            temp_dir: Diretório temporário (se None, usa sistema)
        """
        self.logger = logging.getLogger('podcast_pipeline.youtube_transcriber')
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
        # Configurar credenciais
        if credentials_path is None:
            keys_dir = Path(__file__).parent.parent / 'keys'
            cred_files = list(keys_dir.glob('desafio-outliers-*.json'))
            if not cred_files:
                raise FileNotFoundError(f"Credenciais Google Cloud não encontradas em {keys_dir}")
            credentials_path = str(cred_files[0])
            self.logger.info(f"Usando credenciais: {credentials_path}")
        
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path
        )
        
        # Inicializar clientes
        self.speech_client = speech.SpeechClient(credentials=self.credentials)
        self.storage_client = storage.Client(credentials=self.credentials)
        
        # Configurar bucket GCS
        self.gcs_bucket = gcs_bucket or "desafio-outliers-audio-temp"
        self.logger.info(f"Usando bucket GCS: {self.gcs_bucket}")
    
    def transcribe_youtube_url(
        self,
        youtube_url: str,
        language: str = "pt-BR"
    ) -> Dict[str, Any]:
        """
        Transcreve um vídeo do YouTube via Google Cloud Speech-to-Text.
        Usa upload para GCS + long-running recognition com diarização.
        
        Args:
            youtube_url: URL do vídeo do YouTube
            language: Código do idioma (pt-BR, en-US, etc)
            
        Returns:
            Dict com transcrição, metadados e speakers identificados
        """
        self.logger.info(f"Transcrevendo: {youtube_url}")
        
        # 1. Extrair metadados do vídeo (sem baixar)
        metadata = self._get_video_metadata(youtube_url)
        duration_sec = metadata['duration']
        self.logger.info(f"Vídeo: {metadata['title']} ({duration_sec}s = {duration_sec/60:.1f}min)")
        
        # 2. Baixar áudio em formato adequado para Google Cloud (FLAC ou WAV)
        self.logger.info("Baixando áudio...")
        audio_path = self._download_audio_for_gcs(youtube_url)
        
        try:
            # 3. Upload para GCS
            gcs_uri = self._upload_to_gcs(audio_path, metadata['id'])
            self.logger.info(f"Áudio enviado para GCS: {gcs_uri}")
            
            # 4. Transcrever com diarização (long-running operation)
            transcription = self._transcribe_google_cloud(gcs_uri, language, duration_sec)
            
            # 5. Deletar do GCS
            self._delete_from_gcs(gcs_uri)
            
            # 6. Retornar resultado completo
            return {
                'success': True,
                'video_url': youtube_url,
                'video_id': metadata['id'],
                'title': metadata['title'],
                'description': metadata.get('description', ''),
                'duration': metadata['duration'],
                'upload_date': metadata.get('upload_date'),
                'uploader': metadata.get('uploader'),
                'channel': metadata.get('channel'),
                'transcription': transcription,
                'language': language
            }
        
        finally:
            # Limpar arquivo local
            try:
                os.unlink(audio_path)
            except:
                pass
    
    def transcribe_playlist(
        self,
        playlist_url: str,
        max_videos: Optional[int] = None,
        language: str = "pt"
    ) -> List[Dict[str, Any]]:
        """
        Transcreve todos os vídeos de uma playlist.
        
        Args:
            playlist_url: URL da playlist
            max_videos: Máximo de vídeos (None = todos)
            language: Idioma
            
        Returns:
            Lista de resultados
        """
        self.logger.info(f"Transcrevendo playlist: {playlist_url}")
        
        # Obter lista de vídeos
        playlist_info = self._get_playlist_info(playlist_url)
        videos = playlist_info['entries']
        
        if max_videos:
            videos = videos[:max_videos]
        
        self.logger.info(f"Playlist: {playlist_info['title']} - {len(videos)} vídeos")
        
        results = []
        for i, video in enumerate(videos, 1):
            video_url = f"https://www.youtube.com/watch?v={video['id']}"
            self.logger.info(f"\n[{i}/{len(videos)}] {video['title']}")
            
            try:
                result = self.transcribe_youtube_url(video_url, language=language)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Erro ao transcrever {video_url}: {e}")
                results.append({
                    'success': False,
                    'video_url': video_url,
                    'video_id': video['id'],
                    'error': str(e)
                })
        
        success_count = sum(1 for r in results if r.get('success'))
        self.logger.info(f"\n✓ Playlist completa: {success_count}/{len(videos)} sucessos")
        
        return results
    
    def _transcribe_in_chunks(
        self,
        youtube_url: str,
        total_duration: int,
        chunk_duration: int,
        language: str,
        prompt: Optional[str]
    ) -> Dict[str, Any]:
        """
        Transcreve vídeo dividindo em chunks (para vídeos longos > 25MB).
        Estratégia: baixa o áudio completo uma vez, depois divide localmente.
        
        Args:
            youtube_url: URL do vídeo
            total_duration: Duração total em segundos
            chunk_duration: Duração de cada chunk em segundos
            language: Idioma
            prompt: Prompt opcional
            
        Returns:
            Dict com transcrição completa (segmentos concatenados)
        """
        import math
        
        num_chunks = math.ceil(total_duration / chunk_duration)
        self.logger.info(f"Dividindo em {num_chunks} chunks de ~{chunk_duration}s")
        
        # 1. Baixar áudio completo uma vez
        self.logger.info("Baixando áudio completo...")
        full_audio_path = self._download_full_audio(youtube_url)
        
        try:
            all_segments = []
            full_text = ""
            
            # 2. Dividir e transcrever cada chunk
            for i in range(num_chunks):
                start_time = i * chunk_duration
                end_time = min((i + 1) * chunk_duration, total_duration)
                
                self.logger.info(f"Chunk {i+1}/{num_chunks}: {start_time}s - {end_time}s")
                
                # Extrair chunk do áudio completo
                audio_chunk = self._extract_chunk_from_file(
                    full_audio_path, 
                    start_time, 
                    end_time - start_time
                )
                self.logger.info(f"  Chunk extraído: {len(audio_chunk) / 1024 / 1024:.1f} MB")
                
                # Transcrever chunk
                chunk_transcription = self._transcribe_openai(audio_chunk, language, prompt)
                
                # Ajustar timestamps dos segmentos
                if 'segments' in chunk_transcription:
                    for seg in chunk_transcription['segments']:
                        seg['start'] += start_time
                        seg['end'] += start_time
                    all_segments.extend(chunk_transcription['segments'])
                
                # Concatenar texto
                full_text += chunk_transcription.get('text', '') + " "
            
            # Retornar transcrição completa
            return {
                'text': full_text.strip(),
                'segments': all_segments,
                'language': language
            }
        
        finally:
            # Limpar áudio completo
            try:
                os.unlink(full_audio_path)
            except:
                pass
    
    def _download_full_audio(self, youtube_url: str) -> str:
        """
        Baixa o áudio completo do vídeo e retorna o caminho do arquivo.
        
        Args:
            youtube_url: URL do vídeo
            
        Returns:
            Caminho para o arquivo de áudio temporário
        """
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Encontrar ffmpeg
        ffmpeg_location = self._find_ffmpeg()
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '64',
            }],
            'outtmpl': temp_path.replace('.mp3', ''),
            'quiet': True,
            'no_warnings': True,
            # Opções avançadas para contornar bloqueios do YouTube
            'cookiefile': None,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                    'skip': ['dash', 'hls']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        }
        
        # Adicionar localização do ffmpeg se necessário
        if ffmpeg_location and '/' in ffmpeg_location:
            ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_location)
            # Adicionar ao PATH temporariamente
            os.environ['PATH'] = f"{os.path.dirname(ffmpeg_location)}:{os.environ.get('PATH', '')}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        
        return temp_path
    
    def _extract_chunk_from_file(
        self,
        audio_path: str,
        start_time: int,
        duration: int
    ) -> bytes:
        """
        Extrai um trecho do arquivo de áudio usando ffmpeg-python.
        
        Args:
            audio_path: Caminho do arquivo de áudio
            start_time: Tempo de início em segundos
            duration: Duração do chunk em segundos
            
        Returns:
            Bytes do chunk de áudio
        """
        # Criar arquivo temporário para o chunk
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            chunk_path = temp_file.name
        
        try:
            # Usar ffmpeg-python para extrair o chunk
            (
                ffmpeg
                .input(audio_path, ss=start_time, t=duration)
                .output(chunk_path, acodec='libmp3lame', ab='64k')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, quiet=True)
            )
            
            # Ler chunk
            with open(chunk_path, 'rb') as f:
                chunk_data = f.read()
            
            return chunk_data
        
        finally:
            # Limpar arquivo temporário
            try:
                os.unlink(chunk_path)
            except:
                pass
    
    def _get_video_metadata(self, youtube_url: str) -> Dict[str, Any]:
        """Extrai metadados do vídeo sem baixar."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            
            return {
                'id': info.get('id'),
                'title': info.get('title'),
                'description': info.get('description', ''),
                'duration': info.get('duration'),
                'upload_date': info.get('upload_date'),
                'uploader': info.get('uploader'),
                'channel': info.get('channel'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
            }
    
    def _get_playlist_info(self, playlist_url: str) -> Dict[str, Any]:
        """Obtém informações da playlist."""
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            
            return {
                'title': info.get('title'),
                'uploader': info.get('uploader'),
                'entries': [
                    {
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'duration': entry.get('duration')
                    }
                    for entry in info.get('entries', [])
                    if entry  # Filtrar None
                ]
            }
    
    def _find_ffmpeg(self) -> Optional[str]:
        """
        Encontra o executável do ffmpeg no sistema.
        
        Returns:
            Caminho para ffmpeg ou None se não encontrado
        """
        # Tentar localizações comuns
        common_paths = [
            '/opt/homebrew/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/usr/bin/ffmpeg',
            'ffmpeg'  # PATH do sistema
        ]
        
        for path in common_paths:
            try:
                result = subprocess.run(
                    [path, '-version'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return path
            except:
                continue
        
        return None
    
    def _extract_audio_stream(self, youtube_url: str) -> bytes:
        """
        Extrai áudio do vídeo em memória (sem salvar no disco).
        Retorna bytes do áudio em formato MP3 compatível com Whisper API.
        Requer ffmpeg instalado no sistema.
        """
        # Criar arquivo temporário para o áudio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Localizar ffmpeg
            ffmpeg_location = self._find_ffmpeg()
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '64',  # Qualidade mais baixa para reduzir tamanho (64kbps)
                }],
                'outtmpl': temp_path.replace('.mp3', ''),
                'quiet': True,
                'no_warnings': True,
                # Opções avançadas para contornar bloqueios do YouTube
                'cookiefile': None,
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': 'https://www.youtube.com/',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage', 'configs'],
                        'skip': ['dash', 'hls']
                    }
                },
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            }
            
            # Adicionar localização do ffmpeg se encontrado
            if ffmpeg_location and '/' in ffmpeg_location:
                ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_location)
                # Adicionar ao PATH temporariamente
                os.environ['PATH'] = f"{os.path.dirname(ffmpeg_location)}:{os.environ.get('PATH', '')}"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
            
            # Ler arquivo temporário para memória
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
            
            # Verificar tamanho (OpenAI limita a 25MB)
            size_mb = len(audio_data) / 1024 / 1024
            if size_mb > 25:
                self.logger.warning(
                    f"Áudio muito grande ({size_mb:.1f}MB). "
                    f"OpenAI Whisper API limita a 25MB. "
                    f"Considerando comprimir mais ou usar modo tradicional."
                )
            
            return audio_data
        
        finally:
            # Limpar arquivo temporário
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _transcribe_google_cloud(
        self,
        gcs_uri: str,
        language: str,
        duration_sec: int
    ) -> Dict[str, Any]:
        """
        Transcreve áudio usando Google Cloud Speech-to-Text com diarização.
        
        Args:
            gcs_uri: URI do áudio no GCS (gs://bucket/file)
            language: Código do idioma (pt-BR, en-US, etc)
            duration_sec: Duração do áudio em segundos
            
        Returns:
            Dict com texto, timestamps e speakers identificados
        """
        self.logger.info("Enviando para Google Cloud Speech-to-Text...")
        
        # Configurar reconhecimento com diarização
        diarization_config = speech.SpeakerDiarizationConfig(
            enable_speaker_diarization=True,
            min_speaker_count=2,
            max_speaker_count=2  # Sempre 2 speakers: Samuel e Convidado
        )
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,  # WAV 16kHz mono
            sample_rate_hertz=16000,  # 16kHz (ótimo para fala)
            audio_channel_count=1,    # Mono
            language_code=language,
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,
            diarization_config=diarization_config,
            model="latest_long",  # Modelo otimizado para áudios longos
            use_enhanced=True  # Modelo melhorado (mais preciso)
        )
        
        self.logger.info(f"DEBUG - Configuração da diarização: enable={diarization_config.enable_speaker_diarization}, min={diarization_config.min_speaker_count}, max={diarization_config.max_speaker_count}")
        
        audio = speech.RecognitionAudio(uri=gcs_uri)
        
        # Iniciar operação long-running
        operation = self.speech_client.long_running_recognize(
            config=config,
            audio=audio
        )
        
        self.logger.info(f"Aguardando transcrição (pode levar ~{duration_sec/60:.0f}min)...")
        response = operation.result(timeout=duration_sec * 2)  # Timeout generoso
        
        # Processar resultado com diarização por palavras
        # IMPORTANTE: Seguindo o padrão oficial do Google Cloud Speech-to-Text:
        # "The words list within an alternative includes all the words from all the results.
        #  Thus, to get all the words with speaker tags, you only have to take the 
        #  words list from the LAST result"
        # Fonte: https://cloud.google.com/speech-to-text/docs/speaker-diarization
        
        all_words = []
        
        self.logger.info(f"DEBUG - Total de results: {len(response.results)}")
        
        if not response.results:
            self.logger.error("❌ Nenhum resultado retornado pela API!")
            raise Exception("API não retornou nenhum resultado")
        
        # Usar APENAS o último result (padrão oficial)
        result = response.results[-1]
        self.logger.info(f"DEBUG - Usando o ÚLTIMO result (índice {len(response.results)-1}) como especificado no exemplo oficial")
        
        if not result.alternatives:
            self.logger.error("❌ Nenhuma alternativa no último result!")
            raise Exception("Último result não tem alternativas")
        
        alternative = result.alternatives[0]
        
        if not alternative.words:
            self.logger.warning("⚠️ Nenhuma palavra no último result!")
        
        # Processar todas as palavras do último result
        for word_info in alternative.words:
            all_words.append({
                'word': word_info.word,
                'start': word_info.start_time.total_seconds(),
                'end': word_info.end_time.total_seconds(),
                'speaker_tag': word_info.speaker_tag
            })
        
        self.logger.info(f"✓ Palavras transcritas: {len(all_words)} palavras")
        
        # Debug: Contar speaker tags
        if len(all_words) > 0:
            speaker_counts = {}
            for w in all_words:
                tag = w['speaker_tag']
                speaker_counts[tag] = speaker_counts.get(tag, 0) + 1
            self.logger.info(f"DEBUG - Distribuição de speaker tags: {speaker_counts}")
            
            # Mostrar primeiras 20 palavras com speaker tags
            sample_words = [(w['word'], w['speaker_tag'], round(w['start'], 1)) for w in all_words[:20]]
            self.logger.info(f"DEBUG - Primeiras 20 palavras: {sample_words}")
            
            # Mostrar mudanças de speaker
            speaker_changes = []
            if all_words:
                prev_tag = all_words[0]['speaker_tag']
                for i, w in enumerate(all_words[1:], 1):
                    if w['speaker_tag'] != prev_tag:
                        speaker_changes.append((i, prev_tag, w['speaker_tag'], w['start']))
                        prev_tag = w['speaker_tag']
                self.logger.info(f"DEBUG - Mudanças de speaker: {len(speaker_changes)} mudanças")
                if speaker_changes:
                    for idx, from_spk, to_spk, time in speaker_changes[:10]:
                        self.logger.info(f"  Palavra {idx}: Speaker {from_spk} → {to_spk} em {time:.1f}s")
        
        # Agrupar palavras em segmentos (quebra por mudança de speaker OU pausa longa)
        segments = []
        speaker_mapping = {}
        MAX_SEGMENT_DURATION = 30.0  # Máximo 30s por segmento
        MAX_PAUSE = 2.0  # Pausa de 2s quebra segmento
        
        if all_words:
            current_segment = {
                'speaker_tag': all_words[0]['speaker_tag'],
                'words': [all_words[0]],
                'start': all_words[0]['start']
            }
            
            for word_info in all_words[1:]:
                current_duration = word_info['end'] - current_segment['start']
                pause_duration = word_info['start'] - current_segment['words'][-1]['end']
                
                # Quebrar segmento se:
                # 1. Mudou de speaker
                # 2. Pausa muito longa (>2s)
                # 3. Segmento muito longo (>30s)
                should_break = (
                    word_info['speaker_tag'] != current_segment['speaker_tag'] or
                    pause_duration > MAX_PAUSE or
                    current_duration > MAX_SEGMENT_DURATION
                )
                
                if should_break:
                    # Finaliza segmento atual
                    current_segment['end'] = current_segment['words'][-1]['end']
                    current_segment['text'] = ' '.join(w['word'] for w in current_segment['words'])
                    segments.append(current_segment)
                    
                    # Inicia novo segmento
                    current_segment = {
                        'speaker_tag': word_info['speaker_tag'],
                        'words': [word_info],
                        'start': word_info['start']
                    }
                else:
                    # Continua no mesmo segmento
                    current_segment['words'].append(word_info)
            
            # Adiciona último segmento
            if current_segment['words']:
                current_segment['end'] = current_segment['words'][-1]['end']
                current_segment['text'] = ' '.join(w['word'] for w in current_segment['words'])
                segments.append(current_segment)
        
        # Mapear speaker tags para nomes (0 = Samuel, 1 = Convidado)
        unique_speakers = sorted(set(seg['speaker_tag'] for seg in segments))
        for i, speaker_tag in enumerate(unique_speakers):
            speaker_mapping[speaker_tag] = "Samuel" if i == 0 else "Convidado"
        
        # Adicionar speaker_name aos segmentos
        for seg in segments:
            seg['speaker_name'] = speaker_mapping[seg['speaker_tag']]
            del seg['words']  # Remove lista de palavras (não precisa mais)
        
        full_text = ' '.join(seg['text'] for seg in segments)
        
        self.logger.info(f"✓ Transcrição completa: {len(segments)} segmentos, {len(full_text)} caracteres")
        self.logger.info(f"✓ Speakers identificados: {speaker_mapping}")
        
        return {
            'text': full_text.strip(),
            'segments': segments,
            'language': language,
            'speaker_mapping': speaker_mapping
        }
    
    def _download_audio_for_gcs(self, youtube_url: str) -> str:
        """
        Baixa áudio do YouTube em formato WAV LINEAR16 (melhor para Google Cloud).
        
        Args:
            youtube_url: URL do vídeo
            
        Returns:
            Caminho para o arquivo de áudio temporário
        """
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Encontrar ffmpeg
        ffmpeg_location = self._find_ffmpeg()
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',  # WAV LINEAR16 para melhor compatibilidade
            }],
            'outtmpl': temp_path.replace('.wav', ''),
            'quiet': True,
            'no_warnings': True,
            'postprocessor_args': [
                '-ar', '16000',  # Sample rate 16kHz (ótimo para fala)
                '-ac', '1',      # Mono (reduz tamanho)
            ],
            # Opções avançadas para contornar bloqueios do YouTube
            'cookiefile': None,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'referer': 'https://www.youtube.com/',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            }
        }
        
        # Adicionar localização do ffmpeg se necessário
        if ffmpeg_location and '/' in ffmpeg_location:
            ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_location)
            os.environ['PATH'] = f"{os.path.dirname(ffmpeg_location)}:{os.environ.get('PATH', '')}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        
        return temp_path
    
    def _upload_to_gcs(self, audio_path: str, video_id: str) -> str:
        """
        Faz upload do áudio para Google Cloud Storage.
        
        Args:
            audio_path: Caminho do arquivo local
            video_id: ID do vídeo (usado como nome do blob)
            
        Returns:
            URI do GCS (gs://bucket/file)
        """
        bucket = self.storage_client.bucket(self.gcs_bucket)
        
        # Detectar extensão do arquivo
        ext = '.wav' if audio_path.endswith('.wav') else '.mp3'
        blob_name = f"transcribe-temp/{video_id}{ext}"
        blob = bucket.blob(blob_name)
        
        # Upload com timeout maior
        blob.upload_from_filename(audio_path, timeout=600)  # 10 minutos
        
        return f"gs://{self.gcs_bucket}/{blob_name}"
    
    def _delete_from_gcs(self, gcs_uri: str):
        """
        Deleta arquivo do GCS após transcrição.
        
        Args:
            gcs_uri: URI do GCS (gs://bucket/file)
        """
        try:
            # Parsear URI
            parts = gcs_uri.replace('gs://', '').split('/', 1)
            bucket_name = parts[0]
            blob_name = parts[1]
            
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
            
            self.logger.info(f"Arquivo deletado do GCS: {gcs_uri}")
        except Exception as e:
            self.logger.warning(f"Erro ao deletar do GCS: {e}")


def transcribe_outliers_playlist(
    playlist_url: str = "https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
    max_videos: Optional[int] = None,
    language: str = "pt-BR"
) -> List[Dict[str, Any]]:
    """
    Helper function para transcrever a playlist da Outliers via Google Cloud.
    
    Args:
        playlist_url: URL da playlist
        max_videos: Máximo de vídeos
        language: Idioma (pt-BR, en-US, etc)
        
    Returns:
        Lista de transcrições
    """
    transcriber = YouTubeTranscriber()
    return transcriber.transcribe_playlist(
        playlist_url,
        max_videos=max_videos,
        language=language
    )
