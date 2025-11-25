#!/usr/bin/env python3
"""
Script de teste para validar a nova funcionalidade de transcrição via API.
Execute este script para verificar se tudo está funcionando corretamente.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

def check_environment():
    """Verifica se o ambiente está configurado corretamente."""
    print("🔍 Verificando ambiente...\n")
    
    issues = []
    
    # 1. Verificar OPENAI_API_KEY
    if not os.getenv("OPENAI_API_KEY"):
        issues.append("❌ OPENAI_API_KEY não encontrado no .env")
    else:
        key = os.getenv("OPENAI_API_KEY")
        print(f"✅ OPENAI_API_KEY configurado (início: {key[:15]}...)")
    
    # 2. Verificar HF_TOKEN (opcional)
    if not os.getenv("HF_TOKEN"):
        print("⚠️  HF_TOKEN não encontrado (opcional - só necessário para diarização)")
    else:
        print("✅ HF_TOKEN configurado")
    
    # 3. Verificar imports
    print("\n🔍 Verificando imports...\n")
    
    try:
        from src.youtube_transcriber import YouTubeTranscriber
        print("✅ youtube_transcriber.py importado")
    except ImportError as e:
        issues.append(f"❌ Erro ao importar youtube_transcriber: {e}")
    
    try:
        from src.master_pipeline_api import MasterPipelineAPI
        print("✅ master_pipeline_api.py importado")
    except ImportError as e:
        issues.append(f"❌ Erro ao importar master_pipeline_api: {e}")
    
    try:
        from src.investment_agent import InvestmentAnalysisAgent
        print("✅ investment_agent.py importado")
    except ImportError as e:
        issues.append(f"❌ Erro ao importar investment_agent: {e}")
    
    try:
        from src.marketing_agent import MarketingAgent
        print("✅ marketing_agent.py importado")
    except ImportError as e:
        issues.append(f"❌ Erro ao importar marketing_agent: {e}")
    
    # 4. Verificar diretórios de saída
    print("\n🔍 Verificando diretórios...\n")
    
    output_dir = Path("output")
    if output_dir.exists():
        print(f"✅ Diretório output/ existe")
    else:
        print(f"⚠️  Diretório output/ não existe (será criado automaticamente)")
    
    return issues

def test_youtube_transcriber():
    """Testa a classe YouTubeTranscriber (import apenas)."""
    print("\n🧪 Testando YouTubeTranscriber...\n")
    
    try:
        from src.youtube_transcriber import YouTubeTranscriber
        
        # Apenas verificar se a classe pode ser instanciada
        transcriber = YouTubeTranscriber(api_provider="openai")
        print("✅ YouTubeTranscriber instanciado com sucesso")
        print(f"   - API Provider: {transcriber.api_provider}")
        print(f"   - Client configurado: {transcriber.client is not None}")
        
        return True
    except Exception as e:
        print(f"❌ Erro ao testar YouTubeTranscriber: {e}")
        return False

def test_master_pipeline_api():
    """Testa a classe MasterPipelineAPI (import apenas)."""
    print("\n🧪 Testando MasterPipelineAPI...\n")
    
    try:
        from src.master_pipeline_api import MasterPipelineAPI
        
        # Apenas verificar se a classe pode ser instanciada
        pipeline = MasterPipelineAPI(
            output_dir="output",
            api_provider="openai"
        )
        print("✅ MasterPipelineAPI instanciado com sucesso")
        print(f"   - Output dir: {pipeline.output_dir}")
        print(f"   - Transcripts dir: {pipeline.transcripts_dir}")
        print(f"   - Analyses dir: {pipeline.analyses_dir}")
        print(f"   - Marketing dir: {pipeline.marketing_dir}")
        
        return True
    except Exception as e:
        print(f"❌ Erro ao testar MasterPipelineAPI: {e}")
        return False

def test_cli_commands():
    """Verifica se os comandos CLI foram adicionados."""
    print("\n🧪 Testando comandos CLI...\n")
    
    import subprocess
    
    try:
        result = subprocess.run(
            ["python", "main.py", "--help"],
            capture_output=True,
            text=True,
            check=True
        )
        
        output = result.stdout
        
        if "outliers-api" in output:
            print("✅ Comando 'outliers-api' disponível")
        else:
            print("❌ Comando 'outliers-api' NÃO encontrado")
            return False
        
        if "process-playlist-api" in output:
            print("✅ Comando 'process-playlist-api' disponível")
        else:
            print("❌ Comando 'process-playlist-api' NÃO encontrado")
            return False
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar main.py --help: {e}")
        return False

def main():
    """Executa todos os testes."""
    print("=" * 80)
    print("🚀 VALIDAÇÃO DA FUNCIONALIDADE API")
    print("=" * 80)
    print()
    
    # 1. Verificar ambiente
    issues = check_environment()
    
    # 2. Testar YouTubeTranscriber
    youtube_ok = test_youtube_transcriber()
    
    # 3. Testar MasterPipelineAPI
    pipeline_ok = test_master_pipeline_api()
    
    # 4. Testar comandos CLI
    cli_ok = test_cli_commands()
    
    # Resumo
    print("\n" + "=" * 80)
    print("📊 RESUMO DOS TESTES")
    print("=" * 80)
    print()
    
    all_ok = (
        len(issues) == 0 and
        youtube_ok and
        pipeline_ok and
        cli_ok
    )
    
    if all_ok:
        print("✅ TODOS OS TESTES PASSARAM!")
        print()
        print("🎉 A funcionalidade API está pronta para uso!")
        print()
        print("📝 Próximos passos:")
        print("   1. Teste com 1 vídeo:")
        print("      python main.py outliers-api --max-videos 1")
        print()
        print("   2. Processar múltiplos vídeos:")
        print("      python main.py outliers-api --max-videos 5")
        print()
        print("   3. Revise os outputs em:")
        print("      - output/transcripts/")
        print("      - output/analyses/")
        print("      - output/marketing/")
        print()
        return 0
    else:
        print("❌ ALGUNS TESTES FALHARAM")
        print()
        if issues:
            print("🔧 Problemas encontrados:")
            for issue in issues:
                print(f"   {issue}")
        print()
        print("📖 Consulte API_MODE_GUIDE.md para ajuda")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
