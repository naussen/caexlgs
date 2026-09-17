"""
Interface Streamlit para o módulo de Fontes Abertas & Redes Sociais (OSINT).
Implementação desacoplada, sem vínculo obrigatório com CNPJ ou CPF.
"""
import os
import streamlit as st
from datetime import datetime
from . import (
    coletar_instagram,
    capturar_url_forense,
    pesquisar_mencoes,
    listar_perfis_salvos,
    obter_perfil,
    listar_evidencias_salvas,
    excluir_perfil,
    excluir_evidencia,
    gerar_pacote_zip,
    gerar_dossie_pdf_evidencia,
    sanitizar_username,
    gerar_dorks_investigativas,
    EvidenciaForense
)


def render_osint_screen():
    """Renderiza a tela completa de Fontes Abertas e Redes Sociais."""
    st.markdown("""
        <div style="margin-bottom: 20px;">
            <h1 style="color: #1a237e; margin-bottom: 4px;">🌐 Fontes Abertas & Redes Sociais (OSINT)</h1>
            <p style="color: #546e7a; font-size: 15px; margin-top: 0;">
                Ferramentas Open Source Autohospedadas • Coleta de Perfis Públicos, Raspagem Multi-Redes e Captura Forense Headless
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.info(
        "🔒 **Módulo Autônomo & Sigiloso:** As coletas são salvas exclusivamente no disco desta máquina "
        "com selo criptográfico SHA-256. Nenhuma consulta é transmitida para terceiros nem vinculada "
        "compulsoriamente a CNPJs ou CPFs nesta fase."
    )

    tab_insta, tab_forense, tab_dorks, tab_mencoes, tab_cofre = st.tabs([
        "📸 Instagram (Instaloader & Playwright)",
        "🖥️ Captura Forense de URL (Playwright)",
        "🌐 LinkedIn & Facebook (X-Ray OSINT)",
        "🕸️ Fóruns & Telegram (snscrape)",
        "📂 Cofre de Evidências & Histórico"
    ])

    # ==========================================================
    # ABA 1: INSTAGRAM (INSTALOADER & PLAYWRIGHT)
    # ==========================================================
    with tab_insta:
        st.subheader("📸 Coleta de Perfil & Publicações do Instagram")
        st.caption("Extrai dados cadastrais de perfil, contagem de seguidores, mídias e posts com integridade SHA-256.")

        with st.expander("🔑 Autenticação de Auditoria & Perfis Fechados (Guia Pericial)", expanded=False):
            st.markdown("""
            **Como contornar o Bloqueio 401 da Meta (Login Required):**
            A Meta bloqueou consultas anônimas via API. Para permitir que o Instaloader baixe publicações e fotos em lote:
            1. No seu navegador, faça login em uma conta de pesquisa/auditoria no Instagram.
            2. Pressione `F12` > aba **Application** (ou **Armazenamento**) > **Cookies** > `https://www.instagram.com`.
            3. Copie o valor do cookie **`sessionid`** e cole abaixo.
            
            **Perfis Fechados (Privados):**
            - Por segurança e criptografia no servidor da Meta, contas fechadas **não entregam dados para quem não é seguidor aprovado**.
            - Se a sua conta de auditoria for seguidora aceita pelo investigado, o `sessionid` permitirá baixar **100% dos posts e carrosséis**.
            - Para perfis fechados sem autorização, acesse a aba **"🌐 LinkedIn & Facebook (X-Ray OSINT)"** para pesquisar **menções e tags indiretas (@alvo)** em postagens abertas de terceiros.
            """)
            insta_sid_input = st.text_input(
                "Cookie sessionid do Instagram (Opcional - evita bloqueio 401 da Meta e acessa perfis autorizados):",
                type="password",
                placeholder="Cole seu sessionid aqui...",
                key="input_insta_sid",
                value=st.session_state.get("insta_sessionid_saved", "")
            )
            if insta_sid_input:
                st.session_state.insta_sessionid_saved = insta_sid_input

        col_in1, col_in2, col_in3 = st.columns([3, 1.5, 1.5])
        with col_in1:
            insta_target = st.text_input(
                "Nome de Usuário (@username) ou URL:",
                placeholder="Ex: @alvo_investigado ou https://www.instagram.com/usuario/",
                key="input_insta_target"
            )
        with col_in2:
            max_posts = st.number_input("Limite de Posts:", min_value=1, max_value=24, value=6, step=1, key="input_insta_max")
        with col_in3:
            st.write("")
            st.write("")
            btn_insta = st.button("🚀 Iniciar Coleta", key="btn_coleta_insta", use_container_width=True)

        download_media = st.checkbox("Baixar imagens e miniaturas localmente para custódia", value=True, key="chk_insta_media")

        if btn_insta and insta_target:
            with st.spinner(f"Consultando perfil '{insta_target}'..."):
                perfil, erro = coletar_instagram(
                    insta_target,
                    max_posts=int(max_posts),
                    download_midias=download_media,
                    sessionid=st.session_state.get("insta_sessionid_saved")
                )

            if erro and not perfil:
                st.error(erro)
                # Oferece alternativa imediata via Playwright
                clean_u = sanitizar_username(insta_target)
                insta_url = f"https://www.instagram.com/{clean_u}/"
                st.info("💡 **Alternativa de Captura:** Deseja capturar a página deste perfil pelo navegador real (Playwright)? O navegador renderiza a tela completa com fotos e gera a certidão com hash SHA-256.")
                if st.button(f"📸 Capturar '@{clean_u}' via Navegador Headless", key=f"btn_play_fallback_{clean_u}"):
                    with st.spinner(f"Renderizando {insta_url} no navegador headless..."):
                        ev_insta, err_instaplay = capturar_url_forense(insta_url, wait_seconds=3, observacoes=f"Captura do perfil @{clean_u}")
                        if ev_insta:
                            st.success("Captura forense realizada com sucesso!")
                            st.session_state.ultima_evidencia_id = ev_insta.id
                            st.rerun()
                        else:
                            st.error(err_instaplay)
            elif perfil:
                if erro:
                    st.warning(f"Aviso da coleta: {erro}")
                st.success(f"Perfil de @{perfil.username} coletado com sucesso!")
                st.session_state.ultimo_perfil_insta = perfil.id
                st.rerun()

        # Exibição do perfil coletado recentemente
        perfil_ativo_id = st.session_state.get("ultimo_perfil_insta")
        if perfil_ativo_id:
            perfil_ativo = obter_perfil(perfil_ativo_id)
            if perfil_ativo:
                st.divider()
                # Card do Perfil
                col_av, col_det = st.columns([1, 4])
                with col_av:
                    if perfil_ativo.avatar_local and os.path.exists(perfil_ativo.avatar_local):
                        st.image(perfil_ativo.avatar_local, width=130)
                    elif perfil_ativo.url_avatar:
                        st.image(perfil_ativo.url_avatar, width=130)
                    else:
                        st.markdown("👤 *Sem foto de perfil*")
                with col_det:
                    selo = " ✓ [Verificado]" if perfil_ativo.verificado else ""
                    st.markdown(f"### {perfil_ativo.nome_exibicao or perfil_ativo.username} `{selo}`")
                    st.markdown(f"**@{perfil_ativo.username}** • [Abrir no Instagram ↗]({perfil_ativo.url_perfil})")
                    if perfil_ativo.bio_descricao:
                        st.markdown(f"> *{perfil_ativo.bio_descricao}*")
                    if perfil_ativo.links_externos:
                        st.caption(f"🔗 Links na Bio: {', '.join(perfil_ativo.links_externos)}")

                # Métricas
                c_m1, c_m2, c_m3, c_m4 = st.columns(4)
                c_m1.metric("Seguidores", f"{perfil_ativo.num_seguidores:,}")
                c_m2.metric("Seguindo", f"{perfil_ativo.num_seguindo:,}")
                c_m3.metric("Total de Posts", f"{perfil_ativo.num_posts:,}")
                c_m4.metric("Coletados Agora", len(perfil_ativo.posts_recentes))

                # Botão de Exportar ZIP
                zip_path = gerar_pacote_zip(perfil_ativo.id)
                if zip_path and os.path.exists(zip_path):
                    with open(zip_path, "rb") as fz:
                        st.download_button(
                            "📦 Baixar Pacote de Prova Digital (.ZIP com fotos e metadados)",
                            data=fz.read(),
                            file_name=os.path.basename(zip_path),
                            mime="application/zip",
                            key="btn_dl_zip_insta"
                        )

                # Galeria de Posts
                if perfil_ativo.posts_recentes:
                    st.write("#### 📸 Publicações Coletadas")
                    cols = st.columns(3)
                    for idx, post in enumerate(perfil_ativo.posts_recentes):
                        col_curr = cols[idx % 3]
                        with col_curr:
                            with st.container(border=True):
                                # Mostra primeira mídia se houver
                                if post.midias and post.midias[0].caminho_local and os.path.exists(post.midias[0].caminho_local):
                                    st.image(post.midias[0].caminho_local, use_container_width=True)
                                
                                st.caption(f"📅 {post.data_postagem or 'Data não informada'}")
                                st.write(f"❤️ **{post.num_likes}** likes • 💬 **{post.num_comentarios}** comentários")
                                
                                if post.conteudo_texto:
                                    resumo_legenda = post.conteudo_texto[:140] + ("..." if len(post.conteudo_texto) > 140 else "")
                                    st.write(resumo_legenda)
                                    with st.expander("Ver Legenda Completa"):
                                        st.text(post.conteudo_texto)
                                
                                if post.url_post:
                                    st.link_button("↗ Post Original", post.url_post)

    # ==========================================================
    # ABA 2: CAPTURA FORENSE DE URL (PLAYWRIGHT HEADLESS)
    # ==========================================================
    with tab_forense:
        st.subheader("🖥️ Captura Forense de URL via Navegador Headless (Playwright)")
        st.caption("Renderiza qualquer página web pública, post de rede social ou notícia. Registra print em alta resolução com Hash SHA-256 e Laudo PDF.")

        col_u1, col_u2 = st.columns([4, 1])
        with col_u1:
            target_url = st.text_input(
                "Cole a URL pública do alvo:",
                placeholder="Ex: https://noticias.exemplo.com/materia ou post público",
                key="input_playwright_url"
            )
        with col_u2:
            st.write("")
            st.write("")
            btn_capturar = st.button("📸 Capturar Evidência", key="btn_exec_playwright", use_container_width=True)

        col_opt1, col_opt2, col_opt3 = st.columns([1.5, 1.5, 3])
        with col_opt1:
            opt_full_page = st.checkbox("Capturar Página Inteira (Full-page)", value=True, key="chk_opt_fullpage")
        with col_opt2:
            opt_wait = st.slider("Espera de renderização (seg):", min_value=1, max_value=8, value=2, key="sld_wait_time")
        with col_opt3:
            obs_forense = st.text_input("Observação / Objetivo da Captura:", placeholder="Ex: Prova de vinculação em postagem", key="input_obs_forense")

        if btn_capturar and target_url:
            with st.spinner("Lançando navegador headless, renderizando DOM e extraindo prova..."):
                evidencia, err_play = capturar_url_forense(
                    target_url,
                    full_page=opt_full_page,
                    wait_seconds=int(opt_wait),
                    observacoes=obs_forense
                )

            if err_play and not evidencia:
                st.error(err_play)
            elif evidencia:
                st.success("Captura forense realizada com sucesso!")
                st.session_state.ultima_evidencia_id = evidencia.id
                st.rerun()

        # Visualização da captura recente
        evid_ativa_id = st.session_state.get("ultima_evidencia_id")
        if evid_ativa_id:
            evidencias_todas = listar_evidencias_salvas(limite=10)
            evid_match = next((e for e in evidencias_todas if e["id"] == evid_ativa_id), None)
            if evid_match:
                st.divider()
                st.markdown("#### 🛡️ Laudo de Captura Digital")
                
                # Selo de Integridade
                st.markdown(
                    f"""
                    <div style="background:#f1f8e9; border:1px solid #c5e1a5; padding:12px; border-radius:8px; margin-bottom:15px;">
                        <h4 style="color:#2e7d32; margin:0 0 6px 0;">✓ Registro Forense Autenticado</h4>
                        <div style="font-size:12px; color:#33691e;"><b>Data/Hora da Captura:</b> {evid_match['data_captura']}</div>
                        <div style="font-size:12px; color:#33691e;"><b>URL Alvo:</b> {evid_match['url_alvo']}</div>
                        <div style="font-size:11px; font-family:monospace; color:#bf360c; margin-top:4px;"><b>SHA-256:</b> {evid_match['hash_sha256']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Botões de Ação
                c_btn_pdf, c_btn_view = st.columns([2, 2])
                with c_btn_pdf:
                    # Gera objeto EvidenciaForense rápido para PDF
                    ev_obj = EvidenciaForense(
                        id=evid_match['id'],
                        url_alvo=evid_match['url_alvo'],
                        titulo_pagina=evid_match['titulo_pagina'],
                        texto_extraido=evid_match['texto_extraido'],
                        screenshot_path=evid_match['screenshot_path'],
                        hash_sha256=evid_match['hash_sha256'],
                        data_captura=evid_match['data_captura'],
                        observacoes=evid_match['observacoes'] or ""
                    )
                    pdf_path = gerar_dossie_pdf_evidencia(ev_obj)
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as fpdf:
                            st.download_button(
                                "📑 Baixar Laudo Forense Consolidado (PDF)",
                                data=fpdf.read(),
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf",
                                key="btn_dl_pdf_evid"
                            )

                # Exibição do Screenshot e Conteúdo
                c_sc1, c_sc2 = st.columns([3, 2])
                with c_sc1:
                    st.write("**Print Digital Capturado:**")
                    if evid_match['screenshot_path'] and os.path.exists(evid_match['screenshot_path']):
                        st.image(evid_match['screenshot_path'], use_container_width=True)
                    else:
                        st.warning("Arquivo de print não encontrado em disco.")
                with c_sc2:
                    st.write(f"**Título da Página:** {evid_match['titulo_pagina']}")
                    if evid_match['texto_extraido']:
                        st.write("**Texto Extraído do DOM:**")
                        st.text_area("Texto:", evid_match['texto_extraido'][:2500], height=350, key="txt_extraido_view")

    # ==========================================================
    # ABA 3: LINKEDIN & FACEBOOK (X-RAY OSINT & MENÇÕES CRUZADAS)
    # ==========================================================
    with tab_dorks:
        st.subheader("🌐 Investigação em Redes: LinkedIn, Facebook e Menções Cruzadas")
        st.caption("Gera consultas X-Ray de alta precisão para localizar perfis profissionais, páginas comerciais, sócios e menções a contas fechadas sem bloqueio de login.")

        c_d1, c_d2 = st.columns(2)
        with c_d1:
            dork_nome = st.text_input("Nome da Pessoa / Sócio:", placeholder="Ex: Fulano de Tal", key="dork_input_nome")
            dork_empresa = st.text_input("Nome da Empresa / Razão Social:", placeholder="Ex: Alfa Empreendimentos", key="dork_input_empresa")
        with c_d2:
            dork_cnpj = st.text_input("CNPJ (opcional):", placeholder="Ex: 12.345.678/0001-90", key="dork_input_cnpj")
            c_cid, c_uf = st.columns([3, 1])
            with c_cid:
                dork_cidade = st.text_input("Cidade (opcional):", placeholder="Ex: São Paulo", key="dork_input_cidade")
            with c_uf:
                dork_uf = st.text_input("UF:", placeholder="SP", key="dork_input_uf")

        if dork_nome or dork_empresa or dork_cnpj:
            catalogo = gerar_dorks_investigativas(
                nome_alvo=dork_nome,
                empresa=dork_empresa,
                cnpj=dork_cnpj,
                cidade=dork_cidade,
                uf=dork_uf
            )

            sub_lk, sub_fb, sub_ig, sub_jur = st.tabs([
                "👔 LinkedIn (Profissional & Societário)",
                "👥 Facebook (Empresas & Perfis)",
                "📸 Instagram Cruzado (Perfis Fechados & Tags)",
                "⚖️ Diários Oficiais & Bases Jurídicas"
            ])

            with sub_lk:
                st.markdown("#### 👔 Consultas Direcionadas no LinkedIn")
                st.caption("Identifique cargos atuais, histórico profissional, empresas anteriores e página corporativa oficial.")
                for item in catalogo.get("linkedin", []):
                    with st.container(border=True):
                        st.markdown(f"**{item['titulo']}**")
                        st.caption(item["descricao"])
                        st.code(item["query"], language="text")
                        c_link1, c_link2 = st.columns(2)
                        with c_link1:
                            st.link_button("↗ Abrir Consulta no Google", item["google_url"], use_container_width=True)
                        with c_link2:
                            st.link_button("↗ Abrir Consulta no Bing", item["bing_url"], use_container_width=True)

            with sub_fb:
                st.markdown("#### 👥 Consultas Direcionadas no Facebook")
                st.caption("Localize páginas de estabelecimentos, denúncias de consumidores e menções diretas ao CNPJ.")
                for item in catalogo.get("facebook", []):
                    with st.container(border=True):
                        st.markdown(f"**{item['titulo']}**")
                        st.caption(item["descricao"])
                        st.code(item["query"], language="text")
                        c_link1, c_link2 = st.columns(2)
                        with c_link1:
                            st.link_button("↗ Abrir Consulta no Google", item["google_url"], use_container_width=True)
                        with c_link2:
                            st.link_button("↗ Abrir Consulta no Bing", item["bing_url"], use_container_width=True)

            with sub_ig:
                st.markdown("#### 📸 Técnica de OSINT Cruzado para Instagram")
                st.markdown("""
                > **Estratégia para Perfis Fechados:** Quando a conta do investigado for privada, pesquise as **menções em perfis abertos** (`@nome_do_alvo`) e postagens de terceiros, sócios, eventos ou parceiros comerciais que o marcaram publicamente.
                """)
                for item in catalogo.get("instagram_cruzado", []):
                    with st.container(border=True):
                        st.markdown(f"**{item['titulo']}**")
                        st.caption(item["descricao"])
                        st.code(item["query"], language="text")
                        c_link1, c_link2 = st.columns(2)
                        with c_link1:
                            st.link_button("↗ Abrir Consulta no Google", item["google_url"], use_container_width=True)
                        with c_link2:
                            st.link_button("↗ Abrir Consulta no Bing", item["bing_url"], use_container_width=True)

            with sub_jur:
                st.markdown("#### ⚖️ Consulta em Diários Oficiais & Bases Jurídicas")
                for item in catalogo.get("juridico_oficial", []):
                    with st.container(border=True):
                        st.markdown(f"**{item['titulo']}**")
                        st.caption(item["descricao"])
                        st.code(item["query"], language="text")
                        c_link1, c_link2 = st.columns(2)
                        with c_link1:
                            st.link_button("↗ Abrir Consulta no Google", item["google_url"], use_container_width=True)
                        with c_link2:
                            st.link_button("↗ Abrir Consulta no Bing", item["bing_url"], use_container_width=True)

            st.divider()
            st.write("#### 📸 Encontrou uma URL relevante? Capture com Fé Pública Digital:")
            st.caption("O Playwright renderiza a página web, extrai o conteúdo do DOM, gera o print e calcula o Hash SHA-256 com Laudo PDF.")
            c_url_c, c_url_b = st.columns([4, 1.5])
            with c_url_c:
                url_descoberta = st.text_input("Cole a URL do perfil do LinkedIn, post do Facebook ou Instagram:", placeholder="https://...", key="input_url_dork_capture")
            with c_url_b:
                st.write("")
                st.write("")
                btn_capt_dork = st.button("📸 Capturar com Playwright", key="btn_exec_dork_play", use_container_width=True)

            if btn_capt_dork and url_descoberta:
                with st.spinner("Lançando navegador, renderizando página e gerando custódia SHA-256..."):
                    ev_d, err_d = capturar_url_forense(url_descoberta, wait_seconds=3, observacoes=f"Evidência de rede social: {url_descoberta}")
                    if ev_d:
                        st.success(f"Captura realizada com sucesso! ID: {ev_d.id}")
                        st.session_state.ultima_evidencia_id = ev_d.id
                        st.rerun()
                    else:
                        st.error(err_d)
        else:
            st.info("💡 Preencha o nome do sócio ou da empresa acima para gerar as consultas X-Ray de inteligência.")

    # ==========================================================
    # ABA 4: RASPAGEM EM REDES E FÓRUNS (SNSCRAPE)
    # ==========================================================
    with tab_mencoes:
        st.subheader("🕸️ Raspagem de Menções Públicas e Fóruns (snscrape)")
        st.caption("Pesquisa termos, nomes, tópicos ou palavras-chave em discussões públicas e canais abertos.")

        col_sn1, col_sn2, col_sn3, col_sn4 = st.columns([3, 1.5, 1, 1.5])
        with col_sn1:
            query_sn = st.text_input("Termo de Busca / Palavra-chave:", placeholder="Ex: nome de empresa, alvo, tópico", key="input_sn_query")
        with col_sn2:
            plat_sn = st.selectbox("Plataforma:", ["todas", "reddit", "telegram"], key="sel_sn_plat")
        with col_sn3:
            limite_sn = st.number_input("Limite:", min_value=5, max_value=50, value=15, step=5, key="num_sn_lim")
        with col_sn4:
            st.write("")
            st.write("")
            btn_sn = st.button("🔍 Pesquisar", key="btn_exec_sn", use_container_width=True)

        if btn_sn and query_sn:
            with st.spinner(f"Buscando menções de '{query_sn}' em fontes abertas..."):
                posts_sn, err_sn = pesquisar_mencoes(query_sn, limite=int(limite_sn), plataforma=plat_sn)

            if err_sn and not posts_sn:
                st.warning(f"Aviso de busca: {err_sn}")
            elif posts_sn:
                st.success(f"Foram encontradas {len(posts_sn)} publicações/menções!")
                for p_sn in posts_sn:
                    with st.container(border=True):
                        c_h1, c_h2 = st.columns([3, 1])
                        with c_h1:
                            st.markdown(f"**[{p_sn.plataforma.upper()}] Autor: @{p_sn.autor_username}**")
                        with c_h2:
                            st.caption(f"📅 {p_sn.data_postagem}")

                        st.write(p_sn.conteudo_texto)
                        if p_sn.url_post:
                            st.link_button("↗ Acessar Publicação", p_sn.url_post)
            else:
                st.info("Nenhuma menção pública encontrada para este termo.")

    # ==========================================================
    # ABA 4: COFRE DE EVIDÊNCIAS & HISTÓRICO
    # ==========================================================
    with tab_cofre:
        st.subheader("📂 Cofre de Evidências & Histórico Local")
        st.caption("Todos os dados, perfis e capturas salvas na máquina. Gerencie, exporte laudos ou exclua registros.")

        sub_c1, sub_c2 = st.tabs(["📸 Perfis Salvos (Instagram)", "🖥️ Capturas de URL & Prints"])

        with sub_c1:
            perfis_salvos = listar_perfis_salvos(limite=50)
            if not perfis_salvos:
                st.info("Nenhum perfil de rede social salvo até o momento.")
            else:
                for p_item in perfis_salvos:
                    with st.container(border=True):
                        c_p1, c_p2, c_p3, c_p4 = st.columns([1, 3, 1.5, 1])
                        with c_p1:
                            if p_item.get("avatar_local") and os.path.exists(p_item["avatar_local"]):
                                st.image(p_item["avatar_local"], width=70)
                            else:
                                st.markdown("👤")
                        with c_p2:
                            st.markdown(f"**@{p_item['username']}** — {p_item.get('nome_exibicao', '')}")
                            st.caption(f"Coletado em: {p_item['data_coleta']} • Seguidores: {p_item.get('num_seguidores', 0):,}")
                        with c_p3:
                            if st.button("Visualizar Perfil", key=f"btn_vis_p_{p_item['id']}"):
                                st.session_state.ultimo_perfil_insta = p_item['id']
                                st.rerun()
                        with c_p4:
                            if st.button("🗑️ Excluir", key=f"btn_del_p_{p_item['id']}"):
                                excluir_perfil(p_item['id'])
                                if st.session_state.get("ultimo_perfil_insta") == p_item['id']:
                                    st.session_state.ultimo_perfil_insta = None
                                st.success("Perfil excluído com sucesso.")
                                st.rerun()

        with sub_c2:
            evidencias_salvas = listar_evidencias_salvas(limite=50)
            if not evidencias_salvas:
                st.info("Nenhuma captura de URL forense salva até o momento.")
            else:
                for ev_item in evidencias_salvas:
                    with st.container(border=True):
                        c_e1, c_e2, c_e3 = st.columns([3, 1.5, 1])
                        with c_e1:
                            st.markdown(f"**{ev_item.get('titulo_pagina') or 'Sem título'}**")
                            st.caption(f"🔗 {ev_item['url_alvo']}")
                            st.caption(f"📅 {ev_item['data_captura']} | SHA-256: `{ev_item['hash_sha256'][:16]}...`")
                        with c_e2:
                            if st.button("Abrir Laudo", key=f"btn_open_ev_{ev_item['id']}"):
                                st.session_state.ultima_evidencia_id = ev_item['id']
                                st.rerun()
                        with c_e3:
                            if st.button("🗑️ Excluir", key=f"btn_del_ev_{ev_item['id']}"):
                                excluir_evidencia(ev_item['id'])
                                if st.session_state.get("ultima_evidencia_id") == ev_item['id']:
                                    st.session_state.ultima_evidencia_id = None
                                st.success("Evidência excluída com sucesso.")
                                st.rerun()
