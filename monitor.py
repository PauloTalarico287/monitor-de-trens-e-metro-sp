# ============================================================
# Monitor de Status - Metro e Trem de SP  (v7)
# Cole este codigo numa celula do Google Colab e execute!
# ============================================================

import subprocess
subprocess.run(["pip", "install", "requests", "beautifulsoup4", "-q"])

import requests
import urllib3
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime
import json, time, re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Mapeamento cor -> numero + operadora real
MAPA_LINHAS = {
    "AZUL":      {"numero": 1,  "operadora": "Metro SP",      "nome_completo": "Linha 1-Azul"},
    "VERDE":     {"numero": 2,  "operadora": "Metro SP",       "nome_completo": "Linha 2-Verde"},
    "VERMELHA":  {"numero": 3,  "operadora": "Metro SP",       "nome_completo": "Linha 3-Vermelha"},
    "AMARELA":   {"numero": 4,  "operadora": "Motiva",         "nome_completo": "Linha 4-Amarela"},
    "LILAS":     {"numero": 5,  "operadora": "ViaMobilidade",  "nome_completo": "Linha 5-Lilas"},
    "RUBI":      {"numero": 7,  "operadora": "TIC Trens",      "nome_completo": "Linha 7-Rubi"},
    "DIAMANTE":  {"numero": 8,  "operadora": "ViaMobilidade",  "nome_completo": "Linha 8-Diamante"},
    "ESMERALDA": {"numero": 9,  "operadora": "ViaMobilidade",  "nome_completo": "Linha 9-Esmeralda"},
    "TURQUESA":  {"numero": 10, "operadora": "CPTM",           "nome_completo": "Linha 10-Turquesa"},
    "CORAL":     {"numero": 11, "operadora": "CPTM",           "nome_completo": "Linha 11-Coral"},
    "SAFIRA":    {"numero": 12, "operadora": "CPTM",           "nome_completo": "Linha 12-Safira"},
    "JADE":      {"numero": 13, "operadora": "CPTM",           "nome_completo": "Linha 13-Jade"},
    "PRATA":     {"numero": 15, "operadora": "Metro SP",       "nome_completo": "Linha 15-Prata"},
    "OURO":      {"numero": 17, "operadora": "ViaMobilidade",  "nome_completo": "Linha 17-Ouro"},
}

# Mapeamento território -> linhas que atendem a região
# Uma linha pode atender mais de um território (ex: Linha 9 → Osasco e Grajaú)
TERRITORIOS = {
    "Suzano":         ["CORAL"],
    "Maua":           ["TURQUESA"],
    "Osasco":         ["DIAMANTE", "ESMERALDA"],
    "Guarulhos":      ["JADE"],
    "Capao Redondo":  ["LILAS"],
    "Itaim Paulista": ["SAFIRA"],
    "Graja":          ["ESMERALDA"],
    "Sao Mateus":     ["PRATA"],
    "Jacana":         ["AZUL"],
    "Paraisopolis":   ["AMARELA"],
}

def territorios_afetados(linha_cor):
    """Retorna lista de territórios afetados por uma linha com problema."""
    return [t for t, linhas in TERRITORIOS.items() if linha_cor in linhas]

PALAVRAS_PROBLEMA = [
    "reducida", "reduzida", "velocidade", "intervalo", "intervalos",
    "via unica", "parcial", "interrompida", "paralisada", "encerrada",
    "suspensa", "falha", "defeito", "manutencao", "manutencao",
    "programada", "obras", "problema", "ocorrencia", "ocorrencia",
    "atencao", "atencao", "lentidao", "lentidao", "atraso", "impedimento",
]

def sem_acento(texto):
    """Remove acentos e retorna uppercase."""
    nfkd = unicodedata.normalize("NFD", texto.upper())
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")

def normalizar_cor(cor):
    return sem_acento(cor.strip())

def get_emoji(texto):
    t = sem_acento(texto)
    for p in PALAVRAS_PROBLEMA:
        if p in t:
            if any(x in t for x in ["INTERROMPIDA", "PARALISADA", "ENCERRADA", "SUSPENSA"]):
                return "🔴"
            return "🟡"
    if "NORMAL" in t:
        return "🟢"
    return "⚪"

def tem_problema(reg):
    t = sem_acento(reg.get("status", "") + " " + reg.get("raw", ""))
    return any(p in t for p in PALAVRAS_PROBLEMA)

def extrair_campo(obj, *chaves):
    for chave in chaves:
        if chave in obj and obj[chave] is not None:
            val = str(obj[chave]).strip()
            if val:
                return val
    return None


# ============================================================
# FONTE PRINCIPAL - API central (todas as linhas metropolitanas)
# ============================================================

# Flag global: indica se a API ficou totalmente indisponível
API_INDISPONIVEL = False

def scrape_api_central():
    global API_INDISPONIVEL
    api_url = "http://apps.cptm.sp.gov.br:8080/AppMobileService/api/LinhasMetropolitanas"
    results = []
    MAX_TENTATIVAS = 3

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            r = requests.get(api_url, timeout=12, verify=False)
            if r.status_code != 200:
                print(f"  [API central] HTTP {r.status_code} (tentativa {tentativa})")
                continue

            data = r.json()
            linhas_raw = data if isinstance(data, list) else data.get(
                "linhas", data.get("Linhas", data.get("Resultado", [])))

            print(f"  [API central] {len(linhas_raw)} itens recebidos.")

            for l in linhas_raw:
                cor_raw = extrair_campo(l, "Nome", "nome") or "?"
                cor_key = normalizar_cor(cor_raw)

                status = extrair_campo(l,
                    "Descricao", "descricao",
                    "StatusDescricao", "statusDescricao",
                    "Status", "status",
                ) or "Operacao Normal"

                info = MAPA_LINHAS.get(cor_key, {})
                results.append({
                    "linha_cor":    cor_key,
                    "linha_numero": info.get("numero", 99),
                    "linha_nome":   info.get("nome_completo", cor_raw),
                    "operadora":    info.get("operadora", "?"),
                    "status":       status,
                    "emoji":        get_emoji(status),
                    "fonte":        "API central",
                })
            return results  # sucesso — sai do loop

        except Exception as e:
            print(f"  [API central] Tentativa {tentativa}/{MAX_TENTATIVAS} falhou: {type(e).__name__}")
            if tentativa < MAX_TENTATIVAS:
                time.sleep(5)  # aguarda 5s antes de tentar de novo

    # Todas as tentativas falharam
    print("  [API central] Indisponível após 3 tentativas.")
    API_INDISPONIVEL = True
    return results


# ============================================================
# COMPLEMENTO - linhas ausentes na API
# ============================================================

def scrape_tic_trens():
    """Linha 7-Rubi via site da TIC Trens."""
    url = "https://www.tictrens.com.br/"
    IGNORAR = ["apple", "android", "ver video", "conheca", "saiba mais", "outras companhias", "somos"]
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all(class_=re.compile(r"linha|status|operac|line|situacao", re.I))
        melhor = None
        for item in items:
            texto = item.get_text(" ", strip=True)
            if not texto or len(texto) < 4:
                continue
            if any(ig in sem_acento(texto) for ig in [sem_acento(x) for x in IGNORAR]):
                continue
            if any(p in sem_acento(texto) for p in ["RUBI", "LINHA 7", "OPERACAO", "NORMAL", "INTERROMPIDA"]):
                if melhor is None or len(texto) > len(melhor):
                    melhor = texto
        if melhor:
            return [{
                "linha_cor": "RUBI", "linha_numero": 7,
                "linha_nome": "Linha 7-Rubi", "operadora": "TIC Trens",
                "status": melhor[:200], "emoji": get_emoji(melhor),
                "fonte": "site TIC Trens",
            }]
    except Exception as e:
        print(f"  [TIC Trens] {e}")
    return []

def linhas_fixas_ausentes(cores_presentes):
    """
    Se a API respondeu mas omitiu algumas linhas → provavelmente normal.
    Se a API ficou totalmente indisponível → marca como indisponível.
    """
    ausentes = []
    for cor, info in MAPA_LINHAS.items():
        if cor not in cores_presentes:
            if API_INDISPONIVEL:
                status = "API indisponivel nesta execucao"
                emoji  = "⚪"
            else:
                status = "Nao retornado pela API (provavelmente normal)"
                emoji  = "🟢"
            ausentes.append({
                "linha_cor":    cor,
                "linha_numero": info["numero"],
                "linha_nome":   info["nome_completo"],
                "operadora":    info["operadora"],
                "status":       status,
                "emoji":        emoji,
                "fonte":        "inferido",
            })
    return ausentes


# ============================================================
# EXECUCAO PRINCIPAL
# ============================================================

print("=" * 55)
print(f"Monitor Metro e Trem SP  (v6) - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
print("=" * 55)
print()

todos = scrape_api_central()

if API_INDISPONIVEL:
    print("  ⚠️  API indisponível — dados desta execução não são confiáveis.")
    print("  ⚠️  Nenhuma gravação será feita no Google Sheets.")

# Complemento: linhas ausentes
cores = {r["linha_cor"] for r in todos if "erro" not in r}

if "RUBI" not in cores:
    tic = scrape_tic_trens()
    todos.extend(tic)

ausentes = linhas_fixas_ausentes(cores)
if ausentes:
    nomes = [a["linha_nome"] for a in ausentes]
    print(f"  Linhas ausentes na API: {nomes}")
    todos.extend(ausentes)

# Separar
problemas = [r for r in todos if tem_problema(r) and "erro" not in r]
normais   = [r for r in todos if not tem_problema(r) and "erro" not in r and "aviso" not in r]
erros     = [r for r in todos if "erro" in r or "aviso" in r]

# Cruzar problemas com territórios do Mural Local
alertas_territorios = []
for p in problemas:
    territorios = territorios_afetados(p["linha_cor"])
    if territorios:
        for t in territorios:
            alertas_territorios.append({
                "territorio":  t,
                "linha_nome":  p["linha_nome"],
                "linha_cor":   p["linha_cor"],
                "operadora":   p["operadora"],
                "status":      p["status"],
                "emoji":       p["emoji"],
            })

problemas.sort(key=lambda r: r.get("linha_numero", 99))
normais.sort(key=lambda r: r.get("linha_numero", 99))

print("\n" + "=" * 55)
print(f"LINHAS COM PROBLEMA: {len(problemas)}")
for p in problemas:
    territorios = territorios_afetados(p["linha_cor"])
    aviso_t = f" → alerta para: {', '.join(territorios)}" if territorios else ""
    print(f"  {p['emoji']} {p['linha_nome']} ({p['operadora']}){aviso_t}")
    print(f"     {p['status'][:120]}")

if alertas_territorios:
    print(f"\nALERTAS POR TERRITORIO ({len(alertas_territorios)}):")
    for a in alertas_territorios:
        print(f"  📍 {a['territorio']}: {a['emoji']} {a['linha_nome']} com problema")

print(f"\nLinhas em operacao normal: {len(normais)}")
for n in normais:
    print(f"  🟢 {n['linha_nome']} ({n['operadora']}): {n['status'][:60]}")

if erros:
    print(f"\nAvisos/Erros: {len(erros)}")
    for e in erros:
        print(f"  ⚠️  {e.get('operadora','?')}: {e.get('erro', e.get('aviso',''))[:80]}")

print("=" * 55)

resultado = {
    "coletado_em": datetime.now().isoformat(),
    "resumo": {
        "total_com_problema":      len(problemas),
        "total_normal":            len(normais),
        "total_ausente_api":       len(ausentes),
        "territorios_com_alerta":  len(alertas_territorios),
    },
    "problemas":           problemas,
    "alertas_territorios": alertas_territorios,
    "normais":             normais,
    "erros":               erros,
    "ausentes_api":        ausentes,
}

if API_INDISPONIVEL:
    print("\n⚠️  Execução ignorada — API indisponível. JSON não atualizado.")
else:
    # Salva localmente (Colab) e em data/ (GitHub Actions)
    import os
    os.makedirs("data", exist_ok=True)
    for path in ["status_metro_sp.json", "data/status.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
    print("\nSalvo em status_metro_sp.json e data/status.json")
