# ============================================================
# sheets_writer.py — Grava alertas no Google Sheets
# - Aba "Todas as Linhas": só grava linhas com problema
# - Uma aba por território: só grava quando há problema
# ============================================================

import subprocess
subprocess.run(["pip", "install", "gspread", "google-auth", "-q"])

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json

# ============================================================
# CONFIGURAÇÃO — preencha antes de rodar
# ============================================================

import os

# No GitHub Actions, vêm de Secrets. No Colab, preencha manualmente.
SPREADSHEET_ID   = os.environ.get("SPREADSHEET_ID", "COLE_AQUI_O_ID_DA_SUA_PLANILHA")
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE", "credentials.json")

# ============================================================
# CABEÇALHOS
# ============================================================

# Aba "Todas as Linhas" — registra tudo, sempre
CABECALHOS_HISTORICO = [
    "Data",
    "Hora",
    "Linha",
    "Número",
    "Operadora",
    "Status",
    "Com Problema?",
    "Fonte",
]

# Abas de território — registra só quando há problema
CABECALHOS_TERRITORIO = [
    "Data",
    "Hora",
    "Linha",
    "Operadora",
    "Status",
    "Duração estimada",
    "Fonte",
]

NOMES_TERRITORIOS = [
    "Suzano",
    "Maua",
    "Osasco",
    "Guarulhos",
    "Capao Redondo",
    "Itaim Paulista",
    "Graja",
    "Sao Mateus",
    "Jacana",
    "Paraisopolis",
]

ABA_HISTORICO = "Todas as Linhas"

# ============================================================
# FUNÇÕES
# ============================================================

def conectar_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)

def garantir_abas(planilha):
    """Cria abas que não existem ainda — histórico geral + territórios."""
    abas_existentes = [ws.title for ws in planilha.worksheets()]

    # Aba de histórico geral
    if ABA_HISTORICO not in abas_existentes:
        ws = planilha.add_worksheet(title=ABA_HISTORICO, rows=10000, cols=len(CABECALHOS_HISTORICO))
        ws.append_row(CABECALHOS_HISTORICO)
        print(f"  ✅ Aba criada: {ABA_HISTORICO}")
    else:
        print(f"  ✓  Aba já existe: {ABA_HISTORICO}")

    # Abas de territórios
    for territorio in NOMES_TERRITORIOS:
        if territorio not in abas_existentes:
            ws = planilha.add_worksheet(title=territorio, rows=1000, cols=len(CABECALHOS_TERRITORIO))
            ws.append_row(CABECALHOS_TERRITORIO)
            print(f"  ✅ Aba criada: {territorio}")
        else:
            print(f"  ✓  Aba já existe: {territorio}")

def gravar_historico(planilha, todas_linhas):
    """Grava apenas as linhas com problema no histórico geral."""
    ws = planilha.worksheet(ABA_HISTORICO)
    agora = datetime.now()
    data_str = agora.strftime("%d/%m/%Y")
    hora_str = agora.strftime("%H:%M")
    gravados = 0

    linhas_com_problema = [l for l in todas_linhas if l.get("emoji") in ["🟡", "🔴"]]

    if not linhas_com_problema:
        return 0

    for linha in linhas_com_problema:
        status = linha.get("status", "")
        registro = [
            data_str,
            hora_str,
            linha.get("linha_nome", linha.get("linha_cor", "")),
            str(linha.get("linha_numero", "")),
            linha.get("operadora", ""),
            status[:200],
            "SIM",
            linha.get("fonte", "API central"),
        ]
        ws.append_row(registro)
        gravados += 1

    return gravados

def gravar_alertas_territorios(planilha, alertas_territorios):
    """
    Grava na aba do território quando há problema na linha correspondente.
    """
    if not alertas_territorios:
        return 0

    agora = datetime.now()
    data_str = agora.strftime("%d/%m/%Y")
    hora_str = agora.strftime("%H:%M")
    gravados = 0

    for alerta in alertas_territorios:
        territorio = alerta.get("territorio", "")
        if territorio not in NOMES_TERRITORIOS:
            print(f"  ⚠️  Território '{territorio}' não mapeado — pulando.")
            continue
        try:
            ws = planilha.worksheet(territorio)
            linha = [
                data_str,
                hora_str,
                alerta.get("linha_nome", ""),
                alerta.get("operadora", ""),
                alerta.get("status", "")[:200],
                "",  # duração estimada
                alerta.get("fonte", "API central"),
            ]
            ws.append_row(linha)
            print(f"  📍 {territorio}: {alerta.get('linha_nome')} | {alerta.get('status','')[:55]}")
            gravados += 1
        except Exception as e:
            print(f"  ❌ Erro em '{territorio}': {e}")

    return gravados


# ============================================================
# EXECUÇÃO
# ============================================================

print("=" * 55)
print("Gravando no Google Sheets...")
print("=" * 55)

# Carregar JSON do monitor.py
try:
    caminho = "data/status.json" if os.path.exists("data/status.json") else "status_metro_sp.json"
    with open(caminho, "r", encoding="utf-8") as f:
        resultado = json.load(f)
    print(f"  Lendo: {caminho}")
except FileNotFoundError:
    print("❌ Arquivo de status não encontrado. Execute o monitor.py primeiro.")
    exit(1)

# Montar lista completa de todas as linhas (problemas + normais + ausentes)
todas_linhas = (
    resultado.get("problemas", []) +
    resultado.get("normais", []) +
    resultado.get("ausentes_api", [])
)
alertas = resultado.get("alertas_territorios", [])

print(f"\nLinhas coletadas:      {len(todas_linhas)}")
print(f"Territórios com alerta: {len(alertas)}")

# Conectar
print("\nConectando ao Google Sheets...")
try:
    SPREADSHEET_ID = SPREADSHEET_ID.strip().replace("\u200b", "").replace("\ufeff", "")
    cliente = conectar_sheets()
    planilha = cliente.open_by_key(SPREADSHEET_ID)
    print(f"✅ Conectado: '{planilha.title}'")

    print("\nVerificando abas...")
    garantir_abas(planilha)

    # 1. Histórico geral — só grava se houver problema
    print(f"\nGravando histórico em '{ABA_HISTORICO}'...")
    total_historico = gravar_historico(planilha, todas_linhas)
    print(f"  ✅ {total_historico} linha(s) gravada(s)")

    # 2. Alertas por território — só grava se houver problema
    if alertas:
        print(f"\nGravando alertas por território...")
        total_alertas = gravar_alertas_territorios(planilha, alertas)
        print(f"  ✅ {total_alertas} alerta(s) gravado(s)")
    else:
        print("\nNenhum território afetado no momento.")

    print(f"\n✅ Concluído!")
    print(f"Planilha: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")

except FileNotFoundError:
    print(f"❌ Arquivo '{CREDENTIALS_FILE}' não encontrado.")
except Exception as e:
    print(f"❌ Erro de conexão: {e}")
