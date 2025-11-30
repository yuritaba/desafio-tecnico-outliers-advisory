"""
Teste real do LLM com API key do .env
"""
import os
from dotenv import load_dotenv
from src.podcast_start_detector import PodcastStartDetector
from src.models import AlignedSegment

# Carregar .env
load_dotenv()

def test_with_real_llm():
    """Testar com LLM real (precisa de API key)."""
    
    print("\n" + "="*80)
    print("TESTE REAL: LLM detectando início sem saudação tradicional")
    print("="*80)
    
    if not os.getenv('OPENAI_API_KEY'):
        print("\n❌ ERRO: OPENAI_API_KEY não encontrada no .env")
        return False
    
    detector = PodcastStartDetector()
    
    # Caso do episódio IZ1LX8yJ6Fk
    segments = [
        AlignedSegment(
            start=0.0,
            end=30.0,
            text="Chegou o Credit Guide, a primeira ferramenta completa de informações e análises de crédito privado do Brasil.",
            speaker="A"
        ),
        AlignedSegment(
            start=30.0,
            end=60.0,
            text="Com a ajuda do Credit Guide, isso é simples. O futuro do crédito agora tem guia.",
            speaker="A"
        ),
        AlignedSegment(
            start=60.0,
            end=90.0,
            text="Bom, Ale, obrigado por aceitar falar aqui com a gente. É um prazer ter você neste episódio do podcast.",
            speaker="B"
        ),
        AlignedSegment(
            start=90.0,
            end=120.0,
            text="Obrigado pelo convite, Samuel. É sempre um prazer estar aqui.",
            speaker="A"
        ),
        AlignedSegment(
            start=120.0,
            end=150.0,
            text="Então, hoje vamos falar sobre investimentos em ativos estressados no Brasil.",
            speaker="B"
        ),
    ]
    
    print(f"\n📊 ENTRADA: {len(segments)} segmentos")
    for idx, seg in enumerate(segments):
        print(f"   [{idx}] {seg.start}s: '{seg.text[:70]}...'")
    
    print("\n🤖 Chamando LLM para detectar início...")
    result = detector.detect_podcast_start(segments, blocks_to_check=10)
    
    print(f"\n📊 RESULTADO:")
    print(f"   Segmentos removidos: {len(segments) - len(result)}")
    print(f"   Primeiro segmento após detecção:")
    print(f"   - Start: {result[0].start}s")
    print(f"   - Text: '{result[0].text[:100]}...'")
    
    # Verificação
    if result[0].text.startswith("Bom, Ale") or "obrigado por aceitar" in result[0].text.lower():
        print("\n✅ TESTE PASSOU! LLM detectou corretamente o início da conversa.")
        return True
    else:
        print(f"\n❌ TESTE FALHOU!")
        print(f"   Esperado: Começar com 'Bom, Ale, obrigado' ou contendo 'obrigado por aceitar'")
        print(f"   Obtido: '{result[0].text[:100]}'")
        return False

if __name__ == "__main__":
    success = test_with_real_llm()
    print("\n" + "="*80)
    if success:
        print("🎉 LLM FUNCIONANDO CORRETAMENTE!")
        print("✅ PRONTO PARA IMPLEMENTAR NO PIPELINE")
    else:
        print("⚠️ LLM precisa de ajustes")
    print("="*80)
