"""
Teste para verificar se o LLM está detectando corretamente
o início de conversas que NÃO têm "bom dia/boa tarde".
"""
from src.podcast_start_detector import PodcastStartDetector
from src.models import AlignedSegment

def test_llm_detection_without_greeting():
    """Testar caso onde não tem saudação mas tem início claro de conversa."""
    
    print("\n" + "="*80)
    print("TESTE: Detecção por LLM quando não há 'bom dia/boa tarde'")
    print("="*80)
    
    detector = PodcastStartDetector()
    
    # Simular os primeiros segmentos do episódio IZ1LX8yJ6Fk
    segments = [
        AlignedSegment(
            start=0.0,
            end=30.0,
            text="Propaganda comercial aqui no início do podcast.",
            speaker="A"
        ),
        AlignedSegment(
            start=30.0,
            end=60.0,
            text="Mais propaganda sobre algum produto patrocinador.",
            speaker="A"
        ),
        AlignedSegment(
            start=60.0,
            end=90.0,
            text="Bom, Ale, obrigado por aceitar falar aqui com a gente. É um prazer ter você aqui no podcast.",
            speaker="B"
        ),
        AlignedSegment(
            start=90.0,
            end=120.0,
            text="Obrigado pelo convite, Samuel. Vamos começar?",
            speaker="A"
        ),
        AlignedSegment(
            start=120.0,
            end=150.0,
            text="Sim, queria conversar sobre investimentos em ativos estressados.",
            speaker="B"
        ),
    ]
    
    print(f"\n📊 ENTRADA: {len(segments)} segmentos")
    for idx, seg in enumerate(segments):
        print(f"   [{idx}] {seg.start}s-{seg.end}s: '{seg.text[:60]}...'")
    
    # Rodar detecção
    result = detector.detect_podcast_start(segments, blocks_to_check=10)
    
    print(f"\n📊 RESULTADO:")
    print(f"   Segmentos removidos: {len(segments) - len(result)}")
    print(f"   Primeiro segmento após detecção:")
    print(f"   - Start: {result[0].start}s")
    print(f"   - Text: '{result[0].text[:80]}...'")
    
    # Verificação
    expected_start = "Bom, Ale, obrigado"
    if result[0].text.startswith(expected_start):
        print("\n✅ TESTE PASSOU! LLM detectou corretamente.")
        return True
    else:
        print(f"\n❌ TESTE FALHOU!")
        print(f"   Esperado: Começar com '{expected_start}'")
        print(f"   Obtido: '{result[0].text[:80]}'")
        return False

def test_conversation_markers():
    """Testar detecção de marcadores de início de conversa."""
    
    print("\n" + "="*80)
    print("TESTE 2: Detecção de marcadores de conversa (obrigado, bem-vindo, etc)")
    print("="*80)
    
    detector = PodcastStartDetector()
    
    segments = [
        AlignedSegment(
            start=0.0,
            end=20.0,
            text="Propaganda inicial sobre nosso patrocinador XYZ.",
            speaker="A"
        ),
        AlignedSegment(
            start=20.0,
            end=50.0,
            text="Obrigado por estar aqui conosco hoje. É um prazer receber você neste episódio.",
            speaker="B"
        ),
        AlignedSegment(
            start=50.0,
            end=80.0,
            text="Prazer estar aqui. Vamos falar sobre mercado financeiro?",
            speaker="A"
        ),
    ]
    
    print(f"\n📊 ENTRADA: {len(segments)} segmentos")
    for idx, seg in enumerate(segments):
        print(f"   [{idx}] {seg.start}s: '{seg.text[:60]}...'")
    
    result = detector.detect_podcast_start(segments, blocks_to_check=10)
    
    print(f"\n📊 RESULTADO:")
    print(f"   Segmentos removidos: {len(segments) - len(result)}")
    print(f"   Primeiro: '{result[0].text[:60]}...'")
    
    if "Obrigado" in result[0].text:
        print("\n✅ TESTE PASSOU!")
        return True
    else:
        print("\n❌ TESTE FALHOU!")
        return False

if __name__ == "__main__":
    test1 = test_llm_detection_without_greeting()
    test2 = test_conversation_markers()
    
    print("\n" + "="*80)
    if test1 and test2:
        print("🎉 TODOS OS TESTES PASSARAM!")
    else:
        print("⚠️ ALGUNS TESTES FALHARAM - Necessário ajustar detector")
    print("="*80)
