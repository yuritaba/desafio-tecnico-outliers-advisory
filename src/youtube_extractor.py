"""
Módulo para extrair áudio de playlists do YouTube.
Usa yt-dlp para download e conversão automática.
"""
import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import yt_dlp
except ImportError:
    raise ImportError("yt-dlp não instalado. Execute: pip install yt-dlp")


class YouTubePlaylistExtractor:
    """Extrai áudio de playlists do YouTube para processamento."""
    
    def __init__(
        self,
        output_dir: str = "data",
        audio_format: str = "mp3",
        audio_quality: str = "192"
    ):
        """
        Inicializa o extrator.
        
        Args:
            output_dir: Diretório para salvar áudios
            audio_format: Formato de áudio (mp3, wav)
            audio_quality: Qualidade em kbps
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audio_format = audio_format
        self.audio_quality = audio_quality
        self.logger = logging.getLogger('podcast_pipeline.youtube')
    
    def get_playlist_info(self, playlist_url: str) -> Dict[str, Any]:
        """
        Obtém informações da playlist sem baixar.
        
        Args:
            playlist_url: URL da playlist do YouTube
            
        Returns:
            Dict com informações da playlist
        """
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': False
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            
            return {
                'title': info.get('title'),
                'uploader': info.get('uploader'),
                'video_count': len(info.get('entries', [])),
                'videos': [
                    {
                        'video_id': entry.get('id'),
                        'title': entry.get('title'),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                        'duration': entry.get('duration')
                    }
                    for entry in info.get('entries', [])
                    if entry  # Filtrar None
                ]
            }
    
    def download_video_audio(
        self,
        video_url: str,
        episode_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Baixa o áudio de um vídeo específico.
        
        Args:
            video_url: URL do vídeo
            episode_id: ID do episódio (opcional)
            
        Returns:
            Dict com caminho do arquivo e metadados
        """
        # Extrair video_id da URL
        video_id = self._extract_video_id(video_url)
        if episode_id is None:
            episode_id = video_id
        
        output_template = str(self.output_dir / f"{episode_id}")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.audio_format,
                'preferredquality': self.audio_quality,
            }],
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.logger.info(f"Baixando: {video_url}")
                info = ydl.extract_info(video_url, download=True)
                
                audio_path = f"{output_template}.{self.audio_format}"
                
                return {
                    'success': True,
                    'audio_path': audio_path,
                    'episode_id': episode_id,
                    'video_id': video_id,
                    'title': info.get('title'),
                    'description': info.get('description', ''),
                    'duration': info.get('duration'),
                    'upload_date': info.get('upload_date'),
                    'uploader': info.get('uploader'),
                    'channel': info.get('channel')
                }
                
        except Exception as e:
            self.logger.error(f"Erro ao baixar {video_url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'video_url': video_url
            }
    
    def download_playlist(
        self,
        playlist_url: str,
        max_videos: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Baixa todos os áudios de uma playlist.
        
        Args:
            playlist_url: URL da playlist
            max_videos: Número máximo de vídeos (None = todos)
            
        Returns:
            Lista de resultados de download
        """
        self.logger.info(f"Obtendo informações da playlist: {playlist_url}")
        
        playlist_info = self.get_playlist_info(playlist_url)
        videos = playlist_info['videos']
        
        if max_videos:
            videos = videos[:max_videos]
        
        self.logger.info(
            f"Playlist: {playlist_info['title']} - "
            f"{len(videos)} vídeos para baixar"
        )
        
        results = []
        for i, video in enumerate(videos, 1):
            self.logger.info(f"[{i}/{len(videos)}] {video['title']}")
            
            result = self.download_video_audio(
                video['url'],
                episode_id=f"ep_{i:03d}_{video['video_id']}"
            )
            results.append(result)
        
        # Sumário
        success_count = sum(1 for r in results if r.get('success'))
        self.logger.info(
            f"\nDownload completo: {success_count}/{len(videos)} sucessos"
        )
        
        return results
    
    def _extract_video_id(self, url: str) -> str:
        """Extrai video_id da URL do YouTube"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return url  # Fallback


def download_outliers_playlist(
    playlist_url: str = "https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
    output_dir: str = "data",
    max_videos: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Helper function para baixar a playlist da Outliers.
    
    Args:
        playlist_url: URL da playlist
        output_dir: Diretório de saída
        max_videos: Máximo de vídeos (None = todos)
        
    Returns:
        Lista de resultados
    """
    extractor = YouTubePlaylistExtractor(output_dir=output_dir)
    return extractor.download_playlist(playlist_url, max_videos=max_videos)
