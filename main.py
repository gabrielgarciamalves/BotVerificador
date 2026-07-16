import requests
from bs4 import BeautifulSoup
import json
import os
import urllib3
import re
from datetime import datetime

# Oculta os avisos de segurança no console
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WEBHOOK_URL = os.environ.get("WEBHOOK_DISCORD")
ARQUIVO_HISTORICO = "historico.json"

# CONSTANTE DE DATA DE CORTE (Formato DD/MM/AAAA)
DATA_CORTE_STR = "01/07/2026"
DATA_CORTE = datetime.strptime(DATA_CORTE_STR, "%d/%m/%Y")

def carregar_historico():
    """Carrega o histórico e garante que a estrutura de chaves esteja correta."""
    padrao = {"STN": [], "TCE-SP": [], "TCE-MG": []}
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            with open(ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                for chave in padrao:
                    if chave not in dados:
                        dados[chave] = []
                return dados
        except json.JSONDecodeError:
            pass
    return padrao

def salvar_historico(historico):
    """Salva o histórico atualizado, garantindo que resquícios de órgãos antigos não permaneçam."""
    historico_limpo = {k: v for k, v in historico.items() if k in ["STN", "TCE-SP", "TCE-MG"]}
    with open(ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f:
        json.dump(historico_limpo, f, ensure_ascii=False, indent=4)

def enviar_resumo_discord(novidades):
    """Envia o resumo contínuo com um único título principal."""
    # Verifica se existe pelo menos um item novo em qualquer órgão antes de iniciar
    if not any(novidades.values()):
        return
        
    # Adiciona o título principal apenas uma vez
    linhas_msg = ["🚨 **Atualização Detectada!**\n\n"]
    
    for orgao, itens in novidades.items():
        if not itens:
            continue
            
        linhas_msg.append(f"**Órgão:** {orgao}\n\n")
        
        for item in itens:
            adicao = (
                f"**Documento:** {item['documento']}\n"
                f"**Data/Versão:** {item['info']}\n"
                f"**Link:** {item['link']}\n\n"
            )
            
            # Controle do limite de caracteres
            if len("".join(linhas_msg)) + len(adicao) > 1900:
                resposta = requests.post(WEBHOOK_URL, json={"content": "".join(linhas_msg).strip()})
                if resposta.status_code in (200, 204):
                    print(f"[{orgao}] Bloco enviado ao Discord com sucesso.")
                else:
                    print(f"[{orgao}] Erro no Discord: {resposta.status_code} - {resposta.text}")
                
                linhas_msg = [f"\n🚨 **Continuação - {orgao}**\n\n"]
            
            linhas_msg.append(adicao)
            
    # Envia o que sobrou na lista (se houver mais que apenas o título)
    if len("".join(linhas_msg).strip()) > 35: 
        resposta = requests.post(WEBHOOK_URL, json={"content": "".join(linhas_msg).strip()})
        if resposta.status_code in (200, 204):
            print("Envio finalizado com sucesso.")
        else:
            print(f"Erro no Discord: {resposta.status_code} - {resposta.text}")

def verificar_stn(historico, novidades):
    """Verifica atualizações no site do STN validando qualquer data no bloco do documento."""
    url = "https://siconfi.tesouro.gov.br/siconfi/pages/public/conteudo/conteudo.jsf?id=12503"
    print("Verificando STN...")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resposta = requests.get(url, headers=headers, verify=False)
        resposta.raise_for_status()
        soup = BeautifulSoup(resposta.text, 'html.parser')
        
        links = soup.find_all('a')
        
        for tag in links:
            nome_arquivo = tag.get_text(strip=True)
            if not nome_arquivo:
                continue
                
            bloco_pai = tag.find_parent(['tr', 'li', 'p', 'div', 'td'])
            texto_bloco = bloco_pai.get_text(" ", strip=True) if bloco_pai else tag.parent.get_text(" ", strip=True)
            
            datas_encontradas = re.findall(r'\b(\d{2}/\d{2}/\d{4})\b', texto_bloco)
            data_valida = False
            maior_data_str = "Data não localizada"
            
            if datas_encontradas:
                for d_str in datas_encontradas:
                    try:
                        d_obj = datetime.strptime(d_str, "%d/%m/%Y")
                        if d_obj >= DATA_CORTE:
                            data_valida = True
                            maior_data_str = d_str
                    except ValueError:
                        continue
            
            if data_valida:
                if nome_arquivo not in historico["STN"]:
                    link_doc = tag.get('href', '')
                    if link_doc.startswith('/'):
                        link_doc = "https://siconfi.tesouro.gov.br" + link_doc
                    elif not link_doc.startswith('http'):
                        link_doc = "https://siconfi.tesouro.gov.br/" + link_doc
                        
                    novidades["STN"].append({
                        "documento": nome_arquivo,
                        "info": maior_data_str,
                        "link": link_doc
                    })
                    historico["STN"].append(nome_arquivo)
                    print(f"Novo documento STN notificado: {nome_arquivo} ({maior_data_str})")
                    
    except Exception as e:
        print(f"Erro ao verificar STN: {e}")

def verificar_tce_sp(historico, novidades):
    """Verifica atualizações no site do TCE-SP agrupando os arquivos e sem exibir versão."""
    url_base = "https://www.tce.sp.gov.br"
    url_principal = f"{url_base}/audesp/documentacao"
    print("Verificando TCE-SP...")
    termos_alvo = ["plano de contas", "demonstrativos"]
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resposta = requests.get(url_principal, headers=headers, verify=False)
        resposta.raise_for_status()
        soup = BeautifulSoup(resposta.text, 'html.parser')
        
        linhas = soup.find_all('tr')
        ano_contexto = 2026
        subpaginas = []
        
        for linha in linhas:
            texto_linha = linha.get_text(strip=True).lower()
            
            anos_linha = re.findall(r'\b(20\d{2})\b', texto_linha)
            if anos_linha:
                ano_contexto = max([int(a) for a in anos_linha])
            
            if ano_contexto < 2026:
                continue
            
            if any(termo in texto_linha for termo in termos_alvo):
                link_tag = linha.find('a')
                if link_tag:
                    titulo_categoria = link_tag.get_text(strip=True)
                    href = link_tag.get('href', '')
                    if href.startswith('/'):
                        href = url_base + href
                    subpaginas.append({"titulo": titulo_categoria, "url": href})
        
        for sub in subpaginas:
            resp_sub = requests.get(sub["url"], headers=headers, verify=False)
            soup_sub = BeautifulSoup(resp_sub.text, 'html.parser')
            
            links_arquivos = soup_sub.find_all('a')
            arquivos_novos = []
            
            for tag in links_arquivos:
                nome_arquivo = tag.get_text(strip=True)
                if not nome_arquivo:
                    continue
                
                # Identifica se é um arquivo do Audesp pela versão e agrupa
                match_v = re.search(r'v[_\-\.\s]*(\d+)', nome_arquivo, re.IGNORECASE)
                
                if match_v:
                    if nome_arquivo not in historico["TCE-SP"]:
                        arquivos_novos.append(nome_arquivo)
                        historico["TCE-SP"].append(nome_arquivo)
            
            if arquivos_novos:
                qtd = len(arquivos_novos)
                
                novidades["TCE-SP"].append({
                    "documento": sub['titulo'],
                    "info": f"{qtd} arquivo(s) atualizado(s)",
                    "link": sub["url"]
                })
                print(f"TCE-SP: {qtd} novos arquivos em '{sub['titulo']}'")
                        
    except Exception as e:
        print(f"Erro ao verificar TCE-SP: {e}")

def verificar_tce_mg(historico, novidades):
    """Verifica atualizações isolando estritamente por siglas na URL e versão mais recente."""
    url_base = "https://portalsicom1.tce.mg.gov.br/leiautes/"
    print("Verificando TCE-MG...")
    
    termos_alvo = [
        "contábeis", "cadastro básico", "acompanhamento mensal",
        "balancete", "inclusão de programas", "instrumentos de planejamento"
    ]
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        session = requests.Session()
        session.verify = False 
        
        pagina_atual = 1
        limite_paginas = 10
        texto_pagina_anterior = ""
        
        documentos_recentes = {}
        
        while pagina_atual <= limite_paginas:
            url_pagina = url_base if pagina_atual == 1 else f"{url_base}page/{pagina_atual}/"
            
            resposta = session.get(url_pagina, headers=headers)
            
            if resposta.status_code != 200 or "Página não encontrada" in resposta.text:
                break
                
            soup = BeautifulSoup(resposta.text, 'html.parser')
            
            texto_pagina_atual = soup.get_text(" ", strip=True)
            if texto_pagina_atual == texto_pagina_anterior:
                break
            texto_pagina_anterior = texto_pagina_atual
            
            links = soup.find_all('a')
            
            for tag in links:
                href = tag.get('href', '')
                if not href or href.startswith('#') or 'javascript' in href:
                    continue
                
                nome_link = tag.get_text(strip=True)
                nome_lower = nome_link.lower()
                texto_pai_imediato = tag.parent.get_text(" ", strip=True).lower() if tag.parent else ""
                
                # Isola o contexto do arquivo para ele mesmo e a sua URL
                texto_base = f"{nome_lower} {texto_pai_imediato} {href.lower()}"
                
                if "consolidado" not in texto_base:
                    continue
                
                # Dicionário conversor de siglas das URLs e arquivos do TCE-MG para termos pesquisáveis
                texto_expandido = texto_base
                substituicoes_mg = {
                    "-am-": " acompanhamento mensal ",
                    " am ": " acompanhamento mensal ",
                    "-ip-": " instrumentos de planejamento ",
                    " ip ": " instrumentos de planejamento ",
                    "-aip-": " inclusão de programas ",
                    " aip ": " inclusão de programas ",
                    "cadastro-basico": " cadastro básico ",
                    "contabeis": " contábeis "
                }
                
                for sigla, termo_completo in substituicoes_mg.items():
                    if sigla in texto_expandido:
                        texto_expandido += termo_completo
                
                # Bloqueio rígido: Só aprova se a categoria estiver validada dentro do nome ou da URL
                termo_encontrado = next((t for t in termos_alvo if t in texto_expandido), None)
                if not termo_encontrado:
                    continue
                
                anos_base = re.findall(r'\b(20\d{2})\b', texto_expandido)
                if not anos_base:
                    continue
                    
                ano_encontrado = max([int(a) for a in anos_base])
                if ano_encontrado < 2026:
                    continue
                
                match_v = re.search(r'(?:vers[ãa]o|v)\s*([\d\.]+)', texto_base)
                versao_str = match_v.group(1) if match_v else "0"
                versao_doc = f"Versão {versao_str}" if match_v else "Versão não identificada"
                
                try:
                    versao_tupla = tuple(map(int, versao_str.split('.')))
                except ValueError:
                    versao_tupla = (0,)
                
                data_doc = "Data não identificada"
                match_data = re.search(r'atualizado em.*?(\d{2}/\d{2}/\d{4})', texto_base)
                if match_data:
                    data_doc = match_data.group(1)
                else:
                    textos_anteriores = [t.strip().lower() for t in tag.find_all_previous(string=True) if t.strip()]
                    for txt in textos_anteriores[:15]:
                        match_data = re.search(r'atualizado em.*?(\d{2}/\d{2}/\d{4})', txt)
                        if match_data:
                            data_doc = match_data.group(1)
                            break
                
                if not nome_link:
                    nome_link = "Documento Consolidado"
                    
                nome_exibicao = nome_link
                if len(nome_link) < 25 and termo_encontrado not in nome_lower:
                    nome_exibicao = f"{termo_encontrado.title()} - {nome_link}"
                
                link_doc = href
                if link_doc.startswith('/'):
                    link_doc = "https://portalsicom1.tce.mg.gov.br" + link_doc
                elif not link_doc.startswith('http'):
                    link_doc = f"https://portalsicom1.tce.mg.gov.br/leiautes/{link_doc}"
                    
                info_completa = f"{versao_doc} | {data_doc}"
                identificador_historico = f"{nome_exibicao} | {info_completa} | {link_doc}"
                
                nome_base = re.sub(r'(?i)[-\s]*(?:vers[ãa]o|v)\s*[\d\.]+', '', nome_exibicao).strip()
                
                item_atual = {
                    "documento": nome_exibicao,
                    "info": info_completa,
                    "link": link_doc,
                    "identificador_historico": identificador_historico,
                    "versao_tupla": versao_tupla
                }
                
                # Agrupamento para listar apenas a maior versão
                if nome_base in documentos_recentes:
                    if versao_tupla > documentos_recentes[nome_base]["versao_tupla"]:
                        documentos_recentes[nome_base] = item_atual
                else:
                    documentos_recentes[nome_base] = item_atual
            
            pagina_atual += 1
            
        # Gravação e disparo
        for item in documentos_recentes.values():
            if item["identificador_historico"] not in historico["TCE-MG"]:
                novidades["TCE-MG"].append({
                    "documento": item["documento"],
                    "info": item["info"],
                    "link": item["link"]
                })
                historico["TCE-MG"].append(item["identificador_historico"])
                print(f"Novo documento TCE-MG notificado: {item['documento']} ({item['info']})")
                
    except Exception as e:
        print(f"Erro ao verificar TCE-MG: {e}")

if __name__ == "__main__":
    historico_atual = carregar_historico()
    
    novidades_atuais = {"STN": [], "TCE-SP": [], "TCE-MG": []}
    
    # Execução das rotinas
    verificar_stn(historico_atual, novidades_atuais)
    verificar_tce_sp(historico_atual, novidades_atuais)
    verificar_tce_mg(historico_atual, novidades_atuais)
    
    enviar_resumo_discord(novidades_atuais)
    
    salvar_historico(historico_atual)
    print("Execução finalizada.")
