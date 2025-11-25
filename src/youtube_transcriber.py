"""
Módulo para transcrever vídeos do YouTube diretamente via API (sem download).
Usa OpenAI Whisper API ou Google Cloud Speech-to-Text.
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
    from openai import OpenAI
except ImportError:
    raise ImportError(
        "Dependências não instaladas. Execute: "
        "pip install yt-dlp openai ffmpeg-python"
    )


class YouTubeTranscriber:
    """
    Transcreve vídeos do YouTube diretamente via API (sem salvar localmente).
    Suporta OpenAI Whisper API e Google Cloud Speech-to-Text.
    """
    
    def __init__(
        self,
        api_provider: Literal["openai", "google"] = "openai",
        openai_api_key: Optional[str] = None,
        temp_dir: Optional[str] = None
    ):
        """
        Inicializa o transcriber.
        
        Args:
            api_provider: Provedor da API ('openai' ou 'google')
            openai_api_key: Chave da API OpenAI (se None, usa env var)
            temp_dir: Diretório temporário (se None, usa sistema)
        """
        self.logger = logging.getLogger('podcast_pipeline.youtube_transcriber')
        self.api_provider = api_provider
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
        if api_provider == "openai":
            self.client = OpenAI(api_key=openai_api_key or os.getenv('OPENAI_API_KEY'))
        elif api_provider == "google":
            # TODO: Implementar Google Cloud Speech-to-Text
            raise NotImplementedError("Google Cloud ainda não implementado")
        else:
            raise ValueError(f"Provedor inválido: {api_provider}")
    
    def transcribe_youtube_url(
        self,
        youtube_url: str,
        language: str = "pt",
        prompt: Optional[str] = None,
        chunk_duration: int = 600  # 10 minutos por chunk
    ) -> Dict[str, Any]:
        """
        Transcreve um vídeo do YouTube diretamente pela URL.
        Para vídeos longos, divide em chunks para respeitar o limite de 25MB da API.
        
        Args:
            youtube_url: URL do vídeo do YouTube
            language: Código do idioma (pt, en, etc)
            prompt: Prompt opcional para guiar a transcrição
            chunk_duration: Duração de cada chunk em segundos (padrão: 600 = 10min)
            
        Returns:
            Dict com transcrição e metadados
        """
        self.logger.info(f"Transcrevendo: {youtube_url}")
        
        # 1. Extrair metadados do vídeo (sem baixar)
        metadata = self._get_video_metadata(youtube_url)
        duration_sec = metadata['duration']
        self.logger.info(f"Vídeo: {metadata['title']} ({duration_sec}s = {duration_sec/60:.1f}min)")
        
        # 2. Decidir estratégia: chunk ou completo
        # Estimativa: ~1.5MB por minuto em MP3 64kbps
        estimated_size_mb = (duration_sec / 60) * 1.5
        
        if estimated_size_mb > 23:  # Margem de segurança (limite é 25MB)
            self.logger.info(
                f"Vídeo longo ({estimated_size_mb:.1f}MB estimado). "
                f"Dividindo em chunks de {chunk_duration}s..."
            )
            transcription = self._transcribe_in_chunks(
                youtube_url, 
                duration_sec, 
                chunk_duration, 
                language, 
                prompt
            )
        else:
            self.logger.info("Vídeo curto. Transcrevendo de uma vez...")
            # 2. Baixar áudio em memória (temporário)
            audio_data = self._extract_audio_stream(youtube_url)
            self.logger.info(f"Áudio extraído: {len(audio_data) / 1024 / 1024:.1f} MB")
            
            # 3. Transcrever via API
            if self.api_provider == "openai":
                transcription = self._transcribe_openai(audio_data, language, prompt)
            else:
                raise NotImplementedError(f"Provedor {self.api_provider} não implementado")
        
        # 4. Retornar resultado completo
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
            'language': language,
            'api_provider': self.api_provider
        }
    
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
    
    def _transcribe_openai(
        self,
        audio_data: bytes,
        language: str,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcreve áudio usando OpenAI Whisper API.
        
        Args:
            audio_data: Bytes do áudio
            language: Código do idioma
            prompt: Prompt opcional
            
        Returns:
            Dict com texto e timestamps (se disponível)
        """
        self.logger.info("Enviando para OpenAI Whisper API...")
        
        # Criar arquivo em memória
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.mp3"  # OpenAI precisa do nome do arquivo
        
        # Preparar prompt padrão para podcasts financeiros
        default_prompt = (
            "Este é um podcast sobre investimentos e mercado financeiro. "
            "Os participantes discutem teses de investimento, análise de ações, "
            "fundos, economia e estratégias de alocação."
        )
        
        try:
            # Chamar API
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
                prompt=prompt or default_prompt,
                response_format="verbose_json",  # Inclui timestamps
                temperature=0.0
            )
            
            # Parsear resposta
            result = {
                'text': response.text,
                'language': response.language,
                'duration': response.duration if hasattr(response, 'duration') else None,
                'segments': []
            }
            
            # Adicionar segmentos se disponíveis
            if hasattr(response, 'segments'):
                result['segments'] = [
                    {
                        'start': seg.start if hasattr(seg, 'start') else seg['start'],
                        'end': seg.end if hasattr(seg, 'end') else seg['end'],
                        'text': seg.text if hasattr(seg, 'text') else seg['text']
                    }
                    for seg in response.segments
                ]
            
            self.logger.info(f"✓ Transcrição completa: {len(result['text'])} caracteres")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erro na API OpenAI: {e}")
            raise


def transcribe_outliers_playlist(
    playlist_url: str = "https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
    max_videos: Optional[int] = None,
    language: str = "pt",
    api_provider: Literal["openai", "google"] = "openai"
) -> List[Dict[str, Any]]:
    """
    Helper function para transcrever a playlist da Outliers.
    
    Args:
        playlist_url: URL da playlist
        max_videos: Máximo de vídeos
        language: Idioma
        api_provider: Provedor da API
        
    Returns:
        Lista de transcrições
    """
    transcriber = YouTubeTranscriber(api_provider=api_provider)
    return transcriber.transcribe_playlist(
        playlist_url,
        max_videos=max_videos,
        language=language
    )
