"""
Exemplo simples de uso do Podcast Pipeline.

Este script demonstra como usar o pipeline de forma programática.
"""
import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import process_podcast_episode
from dotenv import load_dotenv


def main():
    # Carrega variáveis de ambiente
    load_dotenv()
    
    # Verifica se HF_TOKEN está configurado
    if not os.getenv("HF_TOKEN"):
        print("⚠️  ATENÇÃO: HF_TOKEN não configurado no .env")
        print("Configure-o para usar pyannote.audio")
        print()
    
    # Caminho do áudio (ajuste conforme necessário)
    audio_path = "data/podcast_exemplo.mp3"
    
    # Verifica se arquivo existe
    if not Path(audio_path).exists():
        print(f"❌ Arquivo não encontrado: {audio_path}")
        print(f"\nColoque um arquivo de áudio em: {Path(audio_path).absolute()}")
        return
    
    print("🎙️  Podcast Pipeline - Exemplo de Uso")
    print("=" * 60)
    print(f"Processando: {audio_path}")
    print()
    
    # Processa o podcast
    try:
        result = process_podcast_episode(
            audio_path=audio_path,
            output_path="output/exemplo_transcript.json",
            episode_metadata={
                "episode_id": "EXEMPLO_001",
                "title": "Episódio de Exemplo",
                "date": "2024-01-15"
            },
            host_name="João Silva",
            guest_names=["Maria Santos"]
        )
        
        print()
        print("✅ Processamento concluído com sucesso!")
        print("=" * 60)
        print(f"📊 Estatísticas:")
        print(f"   • Total de falas: {len(result.utterances)}")
        print(f"   • Duração: {result.get_total_duration():.1f}s")
        print()
        
        # Exibe estatísticas por speaker
        stats = result.get_speaker_stats()
        for role, data in stats.items():
            pct = (data['total_time'] / result.get_total_duration() * 100)
            print(f"   • {role}:")
            print(f"     - Falas: {data['utterance_count']}")
            print(f"     - Tempo: {data['total_time']:.1f}s ({pct:.1f}%)")
            print(f"     - Média por fala: {data['avg_utterance_duration']:.1f}s")
        
        print()
        print(f"💾 Output salvo em: output/exemplo_transcript.json")
        print()
        
        # Exibe algumas falas de exemplo
        print("📝 Primeiras 3 falas:")
        print("-" * 60)
        for i, utterance in enumerate(result.utterances[:3], 1):
            print(f"\n[{i}] {utterance.speaker_role} "
                  f"({utterance.start_time:.1f}s - {utterance.end_time:.1f}s)")
            print(f"    {utterance.text}")
        
        if len(result.utterances) > 3:
            print(f"\n... e mais {len(result.utterances) - 3} falas")
        
        print()
        
    except Exception as e:
        print(f"❌ Erro no processamento: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
