"""
Teste rápido com YouTube Short para debug do pipeline.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env
load_dotenv()

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.youtube_transcriber_assemblyai import YouTubeTranscriberAssemblyAI
from src.pipeline import PodcastPipeline

def test_short_video():
    """Testa com um YouTube Short"""
    
    short_url = "https://www.youtube.com/shorts/BFUt_Q-5nZI"
    video_id = "cZ8M2OoPTts"
    
    print("=" * 60)
    print("TESTE: YouTube Short - Debug Pipeline")
    print("=" * 60)
    print(f"URL: {short_url}")
    print(f"Video ID: {video_id}")
    
    # Verifica API keys
    assemblyai_key = os.getenv('ASSEMBLYAI_KEY') or os.getenv('ASSEMBLYAI_API_KEY')
    if not assemblyai_key:
        print("❌ ASSEMBLYAI_KEY não encontrada!")
        return
    
    print(f"\n✓ AssemblyAI API key: {assemblyai_key[:10]}...")
    
    try:
        # Step 1: Transcrição completa via AssemblyAI
        print("\n" + "=" * 60)
        print("STEP 1: Transcrição via AssemblyAI (com diarização)")
        print("=" * 60)
        
        transcriber = YouTubeTranscriberAssemblyAI(api_key=assemblyai_key)
        
        print(f"\n� Transcrevendo {short_url}...")
        print(f"   (Isso inclui: download, transcrição e diarização)")
        
        result = transcriber.transcribe_youtube_url(short_url)
        
        print(f"\n✅ Transcrição completa!")
        print(f"   - Vídeo: {result.get('title', 'N/A')}")
        print(f"   - Duração: {result.get('duration', 'N/A')}s")
        print(f"   - Canal: {result.get('channel', 'N/A')}")
        
        # Pega utterances diretamente do resultado
        utterances = result.get('utterances', [])
        print(f"   - {len(utterances)} utterances")
        
        # Mostra primeiras utterances
        print(f"\n📊 Primeiras 5 utterances (RAW - antes do pipeline):")
        for i, utt in enumerate(utterances[:5]):
            speaker = utt.get('speaker', 'UNKNOWN')
            text = utt.get('text', '')
            start = utt.get('start_time', 0)
            print(f"   [{i}] {start:.1f}s - {speaker}: {text[:80]}...")
            
            # Detecta propaganda
            if any(word in text.lower() for word in ['credit', 'patrocinador', 'anúncio', 'parceiro', 'patrocínio']):
                print(f"        ⚠️  PROPAGANDA/ANÚNCIO DETECTADO!")
            
            # Detecta saudação
            if any(word in text.lower() for word in ['bom dia', 'boa tarde', 'boa noite', 'bem-vindos', 'olá pessoal']):
                print(f"        ✅ SAUDAÇÃO - POSSÍVEL INÍCIO DO PODCAST!")
        
        # Análise: verifica se precisa remover intro
        first_text = utterances[0].get('text', '').lower()
        has_intro = any(word in first_text for word in ['credit', 'patrocinador', 'anúncio', 'parceiro'])
        
        if has_intro:
            print(f"\n⚠️  ATENÇÃO: Primeira utterance parece ser propaganda/intro!")
            print(f"   O detector de início deveria remover isso.")
        else:
            print(f"\n✅ Primeira utterance parece ser conteúdo real do podcast.")
        
        print("\n" + "=" * 60)
        print("✅ TESTE COMPLETO!")
        print("=" * 60)
        print(f"\nVídeo: {result.get('title', 'N/A')}")
        print(f"URL: {short_url}")
        print(f"\nAnálise:")
        print(f"  1. Tem propaganda/intro? {'SIM' if has_intro else 'NÃO'}")
        print(f"  2. Total de utterances: {len(utterances)}")
        print(f"  3. Primeira utterance começa em: {utterances[0].get('start', 0) if utterances else 'N/A'}s")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_short_video()
