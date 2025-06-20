import pandas as pd
import os
import asyncio
import sys
import logging
from tqdm import tqdm
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import json 

# Configura encoding e logging
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

Fipe = []

# Cria json se não houver Log de Marcas
if not os.path.exists("marcas_processadas.json"):
    with open("marcas_processadas.json", "w") as f:
        json.dump([], f)

# Carrega as Marcas do Json
def carregar_marcas_processadas():
    try:
        with open("marcas_processadas.json", "r") as f:
            return set(json.load(f))
    except Exception as e:
        logging.warning(f"Não foi possivel carregar as marcas processadas {e}")
        return set()

# Salva as marcas no json
def salvar_marcas_processadas(marcas_processadas):
    with open("marcas_processadas.json", "w") as f:
        json.dump(list(marcas_processadas),f)

# Abre a seleção/Dropdown e espera
async def abrir_dropdown_e_esperar(page, container_id):
    logging.info(f"Abrindo dropdown: {container_id}")
    await page.focus(f'div.chosen-container#{container_id} > a')
    await page.click(f'div.chosen-container#{container_id} > a')
    await asyncio.sleep(2)
    await page.wait_for_selector(f'div.chosen-container#{container_id} ul.chosen-results > li', state='attached', timeout=20000)

# Feito para selecionar a Marca atravez do nome
async def selecionar_item_por_nome(page, container_id, nome_desejado):
    await abrir_dropdown_e_esperar(page, container_id)
    await page.focus(f'div.chosen-container#{container_id} > a')
    await asyncio.sleep(0.3)

    itens = await page.query_selector_all(f'div.chosen-container#{container_id} ul.chosen-results > li')
    for i, item in enumerate(itens):
        texto = (await item.text_content()).strip()
        if texto.lower() == nome_desejado.lower():
            logging.info(f"Selecionando por nome '{texto}' no dropdown {container_id}")
            await item.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)
            await page.keyboard.press("Home")
            await asyncio.sleep(0.1)
            for _ in range(i):
                await page.keyboard.press("ArrowDown")
                await asyncio.sleep(0.2)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)
            return
    
    logging.warning(f"[NOME NÃO ENCONTRADO] '{nome_desejado}' não está disponível no dropdown {container_id}")

async def selecionar_item_por_index(page, container_id, index, use_arrow=False):
    logging.info(f"Selecionando item {index+1} no dropdown {container_id}")
    await abrir_dropdown_e_esperar(page, container_id)
    await page.focus(f'div.chosen-container#{container_id} > a')
    await asyncio.sleep(0.5)

    if use_arrow:
        
        # Sempre garante o item 0 como selecionado antes de navegar
        #await page.keyboard.press("Home")
        #await asyncio.sleep(0.3)
        #await page.keyboard.press("Enter")  # Seleciona o primeiro item real
        #await asyncio.sleep(1)

        # Fecha qualquer dropdown aberto
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.6)
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.6)
        
        # Reabre o dropdown para navegação ao índice desejado
        await abrir_dropdown_e_esperar(page, container_id)
        await page.focus(f'div.chosen-container#{container_id} > a')
        await asyncio.sleep(0.3)
        
        ultimo_texto = ""
        tentativas = 0
        max_tentativas = 30
        
        while tentativas < max_tentativas:
            itens = await page.query_selector_all(f'div.chosen-container#{container_id} ul.chosen-results > li.highlighted')
            if itens:
                texto_atual = await itens[0].text_content()
                texto_atual = texto_atual.strip() if texto_atual else ""
                if texto_atual == ultimo_texto:
                    break
                ultimo_texto = texto_atual
            
            await page.keyboard.press("ArrowUp")
            await asyncio.sleep(0.05)
            tentativas += 1  
        
        # Usa a seta para cima para voltar para o topo da lista
        #for _ in range(150):
        #    await page.keyboard.press("ArrowUp")
        #    await asyncio.sleep(0.05)
        
        # Navega até o indice que eu quero
        for _ in range(index):
            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(0.3)
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)
    else:
        items = await page.query_selector_all(f'div.chosen-container#{container_id} ul.chosen-results > li')
        if not items:
            logging.warning(f"Dropdown {container_id} não carregou itens!")
            return
        if index >= len(items):
            logging.warning(f"Index {index} fora do range no dropdown {container_id} (total: {len(items)})")
            return
        await items[index].scroll_into_view_if_needed()
        await asyncio.sleep(0.3)
        item_text = await items[index].text_content()
        logging.info(f"Clicando no item '{item_text.strip()}'")
        await items[index].click()
        await asyncio.sleep(1)

async def selecionar_primeiro_item_teclado(page, container_id):
    logging.info(f"Selecionando primeiro item via teclado no dropdown {container_id}")
    try:
        await page.focus(f'div.chosen-container#{container_id} input.chosen-search-input')
    except:
        await page.focus(f'div.chosen-container#{container_id} > a')

    items = await page.query_selector_all(f'div.chosen-container#{container_id} ul.chosen-results > li')
    if items and len(items) > 0:
        first_item_text = await items[0].text_content()
        current_selection = await page.eval_on_selector(f'div.chosen-container#{container_id} a span', 'el => el.innerText')
        if current_selection and first_item_text.strip() in current_selection:
            logging.info(f"Primeiro item '{first_item_text.strip()}' já está selecionado, pressionando Enter diretamente.")
            await page.keyboard.press("Enter")
        else:
            await asyncio.sleep(0.5)
            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
        await asyncio.sleep(1)

async def limpar_pesquisa(page):
    try:
        await page.wait_for_selector('#buttonLimparPesquisarcarro a.text', state='visible', timeout=5000)
        limpar_link = page.locator('#buttonLimparPesquisarcarro a.text')
        await limpar_link.scroll_into_view_if_needed()
        await limpar_link.click()
        logging.info(">>> Pesquisa limpa com sucesso.")
        await asyncio.sleep(2)

        await page.wait_for_function(
            """() => {
                const span = document.querySelector('#selectMarcacarro_chosen a span');
                return span && span.textContent.toLowerCase().includes('selecione');
            }""",
            timeout=10000
        )
        logging.info(">>> Confirmação visual: dropdown de Marca resetado.")
    except Exception as e:
        logging.warning(f"[ERRO ao tentar limpar pesquisa]: {e}")

async def fechar_todos_dropdowns(page):
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.3)
    await page.evaluate("document.activeElement.blur();")
    await asyncio.sleep(0.3)

async def run(max_marcas=None, max_modelos=None, max_anos=None):
    marcas_processadas = carregar_marcas_processadas()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            logging.info("Acessando o site da FIPE...")
            await page.goto('https://veiculos.fipe.org.br/', timeout=120000)

            logging.info("Clicando em 'Consulta de Carros e Utilitários Pequenos'...")
            await page.wait_for_selector('li:has-text("Carros e utilitários pequenos")', state='visible', timeout=30000)
            await page.click('li:has-text("Carros e utilitários pequenos")')

            logging.info("Selecionando Tabela de Referência...")
            await abrir_dropdown_e_esperar(page, "selectTabelaReferenciacarro_chosen")
            await selecionar_primeiro_item_teclado(page, "selectTabelaReferenciacarro_chosen")

            logging.info("Aguardando carregamento de Marcas...")
            await abrir_dropdown_e_esperar(page, "selectMarcacarro_chosen")
            marcas = await page.query_selector_all('div.chosen-container#selectMarcacarro_chosen ul.chosen-results > li')
            max_marcas = len(marcas) if max_marcas is None else min(max_marcas, len(marcas))

            for marca_index in tqdm(range(max_marcas), desc="Marcas"):
                
                nome_marcas = await marcas[marca_index].text_content()
                
                if nome_marcas.strip() in marcas_processadas:
                    logging.warning(f"[SKIP] Marca {marca_index+1} já processada. Pulando.")
                    continue
                
                try:
                    nome_marca = await marcas[marca_index].text_content()
                    logging.info(f"Processando Marca [{marca_index+1}]: {nome_marca.strip()}")

                    await abrir_dropdown_e_esperar(page, "selectMarcacarro_chosen")
                    await selecionar_item_por_nome(page, "selectMarcacarro_chosen", nome_marca.strip())

                    logging.info("Aguardando carregamento de Modelos...")
                    await abrir_dropdown_e_esperar(page, "selectAnoModelocarro_chosen")
                    modelos = await page.query_selector_all('div.chosen-container#selectAnoModelocarro_chosen ul.chosen-results > li')
                    max_modelos_loop = len(modelos) if max_modelos is None else min(max_modelos, len(modelos))

                    for modelo_index in range(max_modelos_loop):
                        try:
                            nome_modelo = await modelos[modelo_index].text_content()
                            logging.info(f"  Modelo [{modelo_index+1}]: {nome_modelo.strip()}")

                            await abrir_dropdown_e_esperar(page, "selectAnoModelocarro_chosen")
                            await selecionar_item_por_index(page, "selectAnoModelocarro_chosen", modelo_index, use_arrow=True)

                            await abrir_dropdown_e_esperar(page, "selectAnocarro_chosen")
                            anos = await page.query_selector_all('div.chosen-container#selectAnocarro_chosen ul.chosen-results > li')
                            max_anos_loop = len(anos) if max_anos is None else min(max_anos, len(anos))

                            primeiro_ano_para_modelo = True

                            for ano_index in range(max_anos_loop):
                                try:
                                    await limpar_pesquisa(page)
                                    await asyncio.sleep(1.5)

                                     # Só reabre Marca e Modelo se não for a primeira vez (ano_index > 0)
                                    if ano_index > 0:
                                        await abrir_dropdown_e_esperar(page, "selectMarcacarro_chosen")
                                        await selecionar_item_por_index(page, "selectMarcacarro_chosen", marca_index, use_arrow=True)
                                        await page.keyboard.press("Escape")
                                        await asyncio.sleep(0.3)

                                        await abrir_dropdown_e_esperar(page, "selectAnoModelocarro_chosen")
                                        await selecionar_item_por_index(page, "selectAnoModelocarro_chosen", modelo_index, use_arrow=True)
                                        await page.keyboard.press("Escape")
                                        await asyncio.sleep(0.3)

                                    nome_ano = await anos[ano_index].text_content()
                                    logging.info(f"    Ano [{ano_index+1}]: {nome_ano.strip()}")

                                    await abrir_dropdown_e_esperar(page, "selectAnocarro_chosen")
                                    await selecionar_item_por_index(page, "selectAnocarro_chosen", ano_index, use_arrow=True)

                                    logging.info("    Realizando busca...")
                                    botao_pesquisar = page.locator('#buttonPesquisarcarro')
                                    await botao_pesquisar.scroll_into_view_if_needed()
                                    await botao_pesquisar.click(force=True)

                                    await asyncio.sleep(5)
                                    await page.wait_for_selector('div#resultadoConsultacarroFiltros', state='visible', timeout=30000)

                                    codigo_fipe_elements = await page.locator('td:has-text("Código Fipe") + td p').all_text_contents()
                                    preco_medio_elements = await page.locator('td:has-text("Preço Médio") + td p').all_text_contents()

                                    codigo_fipe = next((x.strip() for x in codigo_fipe_elements if x.strip() and not x.strip().startswith('{')), "")
                                    preco_medio = next((x.strip().replace('R$', '').replace('.', '').replace(',', '.') for x in preco_medio_elements if x.strip() and not x.strip().startswith('{')), "")

                                    logging.info(f"    Código Fipe extraído: {codigo_fipe}")
                                    logging.info(f"    Preço Médio extraído: {preco_medio}")

                                    linhas = await page.query_selector_all('table#resultadoConsultacarroFiltros tr')
                                    dados_tabela = {}
                                    ultima_label = None

                                    for linha in linhas:
                                        tds = await linha.query_selector_all('td')
                                        if len(tds) == 2:
                                            nome_element = await tds[0].query_selector('p, strong')
                                            valor_element = await tds[1].query_selector('p, strong')
                                            nome_coluna = (await nome_element.inner_text()).strip() if nome_element else (await tds[0].inner_text()).strip()
                                            valor_coluna = (await valor_element.inner_text()).strip() if valor_element else (await tds[1].inner_text()).strip()
                                            dados_tabela[nome_coluna] = valor_coluna
                                            ultima_label = nome_coluna
                                        elif len(tds) == 1:
                                            valor_element = await tds[0].query_selector('p, strong')
                                            valor_coluna = (await valor_element.inner_text()).strip() if valor_element else (await tds[0].inner_text()).strip()
                                            if ultima_label and 'noborder' in (await tds[0].get_attribute('class') or ''):
                                                dados_tabela[ultima_label] = valor_coluna

                                    dados = {
                                        "MarcaSelecionada": nome_marca.strip(),
                                        "ModeloSelecionado": nome_modelo.strip(),
                                        "AnoSelecionado": nome_ano.strip(),
                                        "CodigoFipe": codigo_fipe,
                                        "PrecoMedio": preco_medio,
                                        **dados_tabela
                                    }

                                    Fipe.append(dados)
                                    logging.info(f"    Dados salvos no Fipe: {dados}")
                                    pd.DataFrame(Fipe).to_excel("Fipe_temp.xlsx", index=False)

                                except Exception as e:
                                    logging.warning(f"[ERRO] Ano [{ano_index+1}] do Modelo [{nome_modelo.strip()}]: {e}")
                                    await asyncio.sleep(2)

                        finally:
                            await limpar_pesquisa(page)
                            await abrir_dropdown_e_esperar(page, "selectMarcacarro_chosen")
                            await selecionar_item_por_index(page, "selectMarcacarro_chosen", marca_index, use_arrow=True)
                            
                            marcas_processadas.add(nome_marcas.strip())
                            salvar_marcas_processadas(marcas_processadas)

                except Exception as e:
                    logging.warning(f"[ERRO] Marca [{marca_index+1}]: {e}")

        except Exception as e:
            logging.error(f"[ERRO GERAL]: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run(max_marcas=None, max_modelos=None, max_anos=None))

    Fipe_df = pd.DataFrame(Fipe)
    print("\n\nDADOS FINAIS COLETADOS")
    print(Fipe_df)
    Fipe_df.to_excel("Fipe.xlsx", index=False)
