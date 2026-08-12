let rawData = null;
let selectedAccountId = null;
let currentFilter = 'all';

document.addEventListener('DOMContentLoaded', () => {
    initEvents();
    fetchData();
});

function initEvents() {
    document.getElementById('btnRefresh').addEventListener('click', () => {
        fetchData(null, true);
    });
    
    document.getElementById('periodSelect').addEventListener('change', (e) => {
        fetchData(e.target.value);
    });

    document.getElementById('gestorSelect').addEventListener('change', () => {
        renderKPIs();
        renderSidebar(document.getElementById('searchInput').value.toLowerCase());
    });

    document.getElementById('searchInput').addEventListener('input', (e) => {
        renderSidebar(e.target.value.toLowerCase());
    });

    document.querySelectorAll('.filter-chips .chip').forEach(chip => {
        chip.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.getAttribute('data-filter');
            renderSidebar(document.getElementById('searchInput').value.toLowerCase());
        });
    });
}

let pollCount = 0;

function getFilteredAccounts() {
    if (!rawData || !rawData.contas) return [];
    const gestorVal = document.getElementById('gestorSelect').value;
    if (gestorVal === 'todos') {
        return rawData.contas;
    }
    return rawData.contas.filter(c => c.gestor === gestorVal);
}

async function fetchData(preset = null, force = false) {
    if (typeof preset !== 'string' || !preset) {
        preset = document.getElementById('periodSelect').value;
    }

    const btnRefresh = document.getElementById('btnRefresh');
    btnRefresh.disabled = true;
    btnRefresh.innerHTML = `<span class="btn-icon">⏳</span> Carregando...`;

    try {
        const url = `/api/metricas?date_preset=${preset}${force ? '&force=true' : ''}`;
        const res = await fetch(url);
        rawData = await res.json();

        if (rawData.loading) {
            document.getElementById('accountList').innerHTML = `<li class="loading-state">⏳ Buscando dados do Meta Ads para este período...</li>`;
            document.getElementById('detailPanel').innerHTML = `
                <div class="placeholder-state" style="margin-top: 40px;">
                    <div class="placeholder-icon">⏳</div>
                    <h3>Buscando métricas do período no Meta Ads...</h3>
                    <p>O servidor está processando os dados na nuvem. Clique em <strong>🔄 Sincronizar API</strong> em instantes.</p>
                </div>
            `;
            return;
        }

        renderKPIs();
        renderSidebar();

        const baseContas = getFilteredAccounts();
        if (baseContas.length > 0) {
            if (!selectedAccountId || !baseContas.find(c => c.account_id === selectedAccountId)) {
                selectedAccountId = baseContas[0].account_id;
            }
            renderDetail(selectedAccountId);
        }
    } catch (err) {
        console.error("Erro ao buscar métricas:", err);
        document.getElementById('accountList').innerHTML = `<li class="loading-state">❌ Erro ao carregar dados da API.</li>`;
    } finally {
        btnRefresh.disabled = false;
        btnRefresh.innerHTML = `<span class="btn-icon">🔄</span> Sincronizar API`;
    }
}

function formatBRL(val) {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0);
}

function formatNum(val) {
    return new Intl.NumberFormat('pt-BR').format(val || 0);
}

function renderKPIs() {
    if (!rawData || !rawData.contas) return;
    const baseContas = getFilteredAccounts();

    let invest = 0;
    let alcance = 0;
    let vendas = 0;
    let pedidos = 0;
    let conversas = 0;
    let ativas = 0;
    let inativas = 0;

    baseContas.forEach(c => {
        if (c.is_ativa) {
            ativas++;
            if (c.metricas) {
                invest += c.metricas.spend || 0;
                alcance += c.metricas.reach || 0;
                vendas += c.metricas.total_vendas || 0;
                pedidos += c.metricas.total_pedidos || 0;
                conversas += c.metricas.conversas_iniciadas || 0;
            }
        } else {
            inativas++;
        }
    });

    document.getElementById('kpiInvestimento').innerText = formatBRL(invest);
    document.getElementById('kpiAlcance').innerText = formatNum(alcance);
    document.getElementById('kpiVendas').innerText = formatBRL(vendas);
    document.getElementById('kpiPedidos').innerText = `${formatNum(pedidos)} pedidos realizados`;
    document.getElementById('kpiConversas').innerText = formatNum(conversas);
    document.getElementById('kpiContas').innerText = `${baseContas.length} Locais`;
    document.getElementById('kpiStatusCount').innerText = `${ativas} Ativas / ${inativas} Inativas`;

    document.getElementById('accountCountBadge').innerText = baseContas.length;
}

function renderSidebar(searchQuery = '') {
    const listEl = document.getElementById('accountList');
    if (!rawData || !rawData.contas) return;

    const baseContas = getFilteredAccounts();

    let filtered = baseContas.filter(c => {
        const matchesSearch = c.nome.toLowerCase().includes(searchQuery) || c.account_id.includes(searchQuery);
        
        if (!matchesSearch) return false;

        if (currentFilter === 'vendas') {
            return c.metricas && c.metricas.tipo_foco === 'vendas';
        }
        if (currentFilter === 'mensagens') {
            return c.metricas && c.metricas.tipo_foco === 'mensagens';
        }
        if (currentFilter === 'inativas') {
            return !c.is_ativa;
        }

        return true;
    });

    if (filtered.length === 0) {
        listEl.innerHTML = `<li class="loading-state">Nenhum local encontrado com o filtro atual.</li>`;
        return;
    }

    if (!selectedAccountId || !filtered.find(c => c.account_id === selectedAccountId)) {
        selectedAccountId = filtered[0].account_id;
        renderDetail(selectedAccountId);
    }

    listEl.innerHTML = filtered.map(c => {
        const isSelected = (c.account_id === selectedAccountId) ? 'active' : '';
        
        let statusText = '🟢 Ativa';
        let statusClass = 'active';
        if (c.status_num === 2 || c.status_num === 3) {
            statusText = '🟡 Sem Saldo';
            statusClass = 'active';
        } else if (!c.is_ativa) {
            statusText = '🔴 Inativa';
            statusClass = 'inactive';
        }

        let tagGoal = 'ℹ️ Sem dados';
        if (c.metricas) {
            tagGoal = c.metricas.tipo_foco === 'vendas' ? '🛒 Vendas' : '💬 Mensagens';
        }

        const spendStr = c.metricas ? formatBRL(c.metricas.spend) : 'R$ 0,00';

        return `
            <li class="account-item ${isSelected}" onclick="selectAccount('${c.account_id}')">
                <div class="item-top">
                    <span class="item-name" title="${c.nome}">${c.nome}</span>
                    <span class="status-dot ${statusClass}">${statusText}</span>
                </div>
                <div class="item-bottom">
                    <span class="tag-goal">${tagGoal}</span>
                    <span class="item-spend">${spendStr}</span>
                </div>
            </li>
        `;
    }).join('');
}

const ALL_METRIC_KEYS = [
    { key: 'spend', label: '💰 Investimento' },
    { key: 'reach', label: '📢 Alcance' },
    { key: 'impressions', label: '👁️ Impressões' },
    { key: 'frequency', label: '🔄 Frequência' },
    { key: 'ctr', label: '⚡ CTR (Cliques %)' },
    { key: 'cliques_link', label: '🖱️ Cliques no Link' },
    { key: 'cpc', label: '🎯 CPC (Custo/Clique)' },
    { key: 'cpm', label: '📊 CPM (Custo 1k Impr.)' },
    { key: 'total_pedidos', label: '🛵 Total Pedidos' },
    { key: 'total_vendas', label: '📈 Total Vendas' },
    { key: 'roas', label: '🤑 ROAS' },
    { key: 'visitas_perfil', label: '👤 Visitas Perfil' },
    { key: 'conversas_iniciadas', label: '💬 Conversas' },
    { key: 'custo_por_conversa', label: '📊 Custo/Conversa' },
    { key: 'carrinhos', label: '🛒 Carrinhos' },
    { key: 'checkouts', label: '💳 Checkouts' },
    { key: 'leads', label: '📋 Leads' }
];

let isFilterExpanded = false;

function toggleMetricFilterPanel() {
    isFilterExpanded = !isFilterExpanded;
    const box = document.getElementById('metricFilterBox');
    const chevron = document.getElementById('filterChevron');
    if (box) {
        box.classList.toggle('hidden', !isFilterExpanded);
    }
    if (chevron) {
        chevron.classList.toggle('open', isFilterExpanded);
    }
}

function getActiveMetrics() {
    const saved = localStorage.getItem('active_metrics_filter');
    if (saved) {
        try {
            return JSON.parse(saved);
        } catch (e) {}
    }
    // Por padrão exibe as métricas principais
    return ['spend', 'reach', 'total_pedidos', 'total_vendas', 'roas', 'visitas_perfil', 'conversas_iniciadas', 'custo_por_conversa'];
}

function isMetricVisible(key) {
    const active = getActiveMetrics();
    return active.includes(key);
}

function toggleMetricFilter(key) {
    let active = getActiveMetrics();
    if (active.includes(key)) {
        active = active.filter(k => k !== key);
    } else {
        active.push(key);
    }
    localStorage.setItem('active_metrics_filter', JSON.stringify(active));
    if (selectedAccountId) {
        renderDetail(selectedAccountId);
    }
}

function setAllMetricsFilter(selectAll) {
    const active = selectAll ? ALL_METRIC_KEYS.map(m => m.key) : [];
    localStorage.setItem('active_metrics_filter', JSON.stringify(active));
    if (selectedAccountId) {
        renderDetail(selectedAccountId);
    }
}

function setPresetMetricsFilter(preset) {
    let active = [];
    if (preset === 'vendas') {
        active = ['spend', 'reach', 'impressions', 'total_pedidos', 'total_vendas', 'roas', 'carrinhos', 'checkouts'];
    } else if (preset === 'mensagens') {
        active = ['spend', 'reach', 'impressions', 'visitas_perfil', 'conversas_iniciadas', 'custo_por_conversa', 'ctr', 'cliques_link', 'cpc', 'cpm'];
    }
    localStorage.setItem('active_metrics_filter', JSON.stringify(active));
    if (selectedAccountId) {
        renderDetail(selectedAccountId);
    }
}

function selectAccount(id) {
    selectedAccountId = id;
    renderSidebar(document.getElementById('searchInput').value.toLowerCase());
    renderDetail(id);
}

function renderDetail(id) {
    const detailPanel = document.getElementById('detailPanel');
    if (!rawData || !rawData.contas) return;

    const conta = rawData.contas.find(c => c.account_id === id);
    if (!conta) return;

    let statusBadge = `<span class="status-badge active">🟢 Conta Ativa</span>`;
    if (conta.status_num === 2 || conta.status_num === 3) {
        statusBadge = `<span class="status-badge active" style="background: rgba(245, 158, 11, 0.2); color: var(--accent-gold); border-color: rgba(245, 158, 11, 0.4);">🟡 Sem Saldo / Pausada (Métricas Ativas)</span>`;
    } else if (!conta.is_ativa) {
        statusBadge = `<span class="status-badge inactive">🔴 Inativa / Bloqueada</span>`;
    }

    const activeKeys = getActiveMetrics();

    let contentHTML = `
        <div class="detail-header">
            <div class="detail-title">
                <h2>${conta.nome}</h2>
                <div class="account-meta">
                    <span>ID da Conta: <code>act_${conta.account_id}</code></span>
                    <span>Moeda: <strong>${conta.moeda}</strong></span>
                </div>
            </div>
            ${statusBadge}
        </div>

        <div class="metric-filter-bar">
            <button class="btn-filter-toggle" onclick="toggleMetricFilterPanel()">
                <span>⚙️ Personalizar Métricas Exibidas</span>
                <span class="chevron ${isFilterExpanded ? 'open' : ''}" id="filterChevron">▼</span>
            </button>
            <span class="filter-count-badge" id="filterCountBadge">${activeKeys.length} de ${ALL_METRIC_KEYS.length} ativas</span>
        </div>

        <div class="metric-filter-box glass ${isFilterExpanded ? '' : 'hidden'}" id="metricFilterBox">
            <div class="metric-filter-header">
                <div class="metric-filter-title">
                    <span>⚙️ Escolha as métricas que deseja visualizar no relatório:</span>
                </div>
                <div class="metric-filter-actions">
                    <button class="btn-chip-sm" onclick="setAllMetricsFilter(true)">✨ Marcar Todas</button>
                    <button class="btn-chip-sm" onclick="setPresetMetricsFilter('vendas')">🛒 Foco Vendas</button>
                    <button class="btn-chip-sm" onclick="setPresetMetricsFilter('mensagens')">💬 Foco Mensagens</button>
                    <button class="btn-chip-sm" onclick="setAllMetricsFilter(false)">🧹 Limpar</button>
                </div>
            </div>
            <div class="metric-checkboxes">
                ${ALL_METRIC_KEYS.map(m => `
                    <label class="metric-chip-toggle ${activeKeys.includes(m.key) ? 'active' : ''}">
                        <input type="checkbox" ${activeKeys.includes(m.key) ? 'checked' : ''} onchange="toggleMetricFilter('${m.key}')">
                        <span>${m.label}</span>
                    </label>
                `).join('')}
            </div>
        </div>
    `;

    if (!conta.is_ativa || !conta.metricas) {
        contentHTML += `
            <div class="placeholder-state" style="margin-top: 20px;">
                <div class="placeholder-icon">ℹ️</div>
                <h3>${conta.erro || 'Sem dados de desempenho para o período.'}</h3>
                <p>Esta conta de anúncio não gerou dados no período selecionado ou está com restrição no Meta.</p>
            </div>
        `;
    } else {
        const m = conta.metricas;
        const isVendas = m.tipo_foco === 'vendas';

        contentHTML += `
            <div class="metrics-section-title">
                <span>${isVendas ? '🛒 Relatório de Vendas & Conversão' : '💬 Relatório de Mensagens & Engajamento'}</span>
            </div>

            <div class="detail-metrics-grid">
        `;

        if (isMetricVisible('spend')) {
            contentHTML += `
                <div class="metric-box" data-metric="spend">
                    <span class="label">💰 Investimento</span>
                    <span class="val">${formatBRL(m.spend)}</span>
                </div>
            `;
        }

        if (isMetricVisible('reach')) {
            contentHTML += `
                <div class="metric-box" data-metric="reach">
                    <span class="label">📢 Alcance (Pessoas)</span>
                    <span class="val">${formatNum(m.reach)}</span>
                </div>
            `;
        }

        if (isMetricVisible('impressions')) {
            contentHTML += `
                <div class="metric-box" data-metric="impressions">
                    <span class="label">👁️ Impressões</span>
                    <span class="val">${formatNum(m.impressions)}</span>
                </div>
            `;
        }

        if (isMetricVisible('frequency')) {
            const freqStr = (m.frequency || 0).toFixed(2).replace('.', ',');
            contentHTML += `
                <div class="metric-box" data-metric="frequency">
                    <span class="label">🔄 Frequência Média</span>
                    <span class="val">${freqStr}x</span>
                </div>
            `;
        }

        if (isMetricVisible('ctr')) {
            const ctrStr = (m.ctr || 0).toFixed(2).replace('.', ',');
            contentHTML += `
                <div class="metric-box" data-metric="ctr">
                    <span class="label">⚡ CTR (Cliques %)</span>
                    <span class="val">${ctrStr}%</span>
                </div>
            `;
        }

        if (isMetricVisible('cliques_link')) {
            contentHTML += `
                <div class="metric-box" data-metric="cliques_link">
                    <span class="label">🖱️ Cliques no Link</span>
                    <span class="val">${formatNum(m.cliques_link)}</span>
                </div>
            `;
        }

        if (isMetricVisible('cpc')) {
            contentHTML += `
                <div class="metric-box" data-metric="cpc">
                    <span class="label">🎯 CPC (Custo por Clique)</span>
                    <span class="val">${formatBRL(m.cpc)}</span>
                </div>
            `;
        }

        if (isMetricVisible('cpm')) {
            contentHTML += `
                <div class="metric-box" data-metric="cpm">
                    <span class="label">📊 CPM (Custo 1k Impr.)</span>
                    <span class="val">${formatBRL(m.cpm)}</span>
                </div>
            `;
        }

        if (isVendas) {
            if (isMetricVisible('total_pedidos')) {
                contentHTML += `
                    <div class="metric-box highlight" data-metric="total_pedidos">
                        <span class="label">🛵 Total de Pedidos</span>
                        <span class="val">${formatNum(m.total_pedidos)}</span>
                    </div>
                `;
            }
            if (isMetricVisible('total_vendas')) {
                contentHTML += `
                    <div class="metric-box highlight" data-metric="total_vendas">
                        <span class="label">📈 Total em Vendas</span>
                        <span class="val">${formatBRL(m.total_vendas)}</span>
                    </div>
                `;
            }
            if (isMetricVisible('carrinhos')) {
                contentHTML += `
                    <div class="metric-box highlight" data-metric="carrinhos">
                        <span class="label">🛒 Adições ao Carrinho</span>
                        <span class="val">${formatNum(m.carrinhos)}</span>
                    </div>
                `;
            }
            if (isMetricVisible('checkouts')) {
                contentHTML += `
                    <div class="metric-box highlight" data-metric="checkouts">
                        <span class="label">💳 Checkouts Iniciados</span>
                        <span class="val">${formatNum(m.checkouts)}</span>
                    </div>
                `;
            }
        } else {
            if (isMetricVisible('visitas_perfil')) {
                contentHTML += `
                    <div class="metric-box purple-glow" data-metric="visitas_perfil">
                        <span class="label">👤 Visitas ao Perfil</span>
                        <span class="val">${formatNum(m.visitas_perfil)}</span>
                    </div>
                `;
            }
            if (isMetricVisible('conversas_iniciadas')) {
                contentHTML += `
                    <div class="metric-box purple-glow" data-metric="conversas_iniciadas">
                        <span class="label">💬 Conversas Iniciadas</span>
                        <span class="val">${formatNum(m.conversas_iniciadas)}</span>
                    </div>
                `;
            }
            if (isMetricVisible('custo_por_conversa')) {
                contentHTML += `
                    <div class="metric-box" data-metric="custo_por_conversa">
                        <span class="label">📊 Custo por Conversa</span>
                        <span class="val">${formatBRL(m.custo_por_conversa)}</span>
                    </div>
                `;
            }
        }

        if (isMetricVisible('leads')) {
            contentHTML += `
                <div class="metric-box highlight" data-metric="leads">
                    <span class="label">📋 Leads Gerados</span>
                    <span class="val">${formatNum(m.leads)}</span>
                </div>
            `;
        }

        contentHTML += `</div>`; // fecha detail-metrics-grid

        if (isVendas && isMetricVisible('roas')) {
            const roasVal = (m.roas || 0).toFixed(2).replace('.', ',');
            contentHTML += `
                <div class="roas-banner" style="margin-top: 16px;" data-metric="roas">
                    <div class="roas-text">
                        <h4>🤑 ROAS Geral da Conta (Média Consolidada)</h4>
                        <p>Total em Vendas da Conta dividido pelo Investimento Total da Conta.</p>
                    </div>
                    <div class="roas-value">${roasVal}x</div>
                </div>
            `;
        }

        // Exibe o detalhamento por Campanha (ROAS e métricas exatas por campanha)
        if (m.campanhas && m.campanhas.length > 0) {
            contentHTML += `
                <div class="campaigns-section" style="margin-top: 28px;">
                    <div class="metrics-section-title">
                        <span>🎯 Campanhas da Conta (ROAS e Métricas Exatas por Campanha)</span>
                    </div>

                    <div class="campaigns-grid" style="display: flex; flex-direction: column; gap: 12px;">
            `;

            m.campanhas.forEach(camp => {
                const isCampVendas = camp.tipo_foco === 'vendas';
                const hasConversas = camp.conversas_iniciadas > 0;
                const campRoasStr = (camp.roas || 0).toFixed(2).replace('.', ',');

                let tagGoal = '📢 Alcance / Reconhecimento';
                if (isCampVendas) {
                    tagGoal = '🛒 Vendas';
                } else if (hasConversas) {
                    tagGoal = '💬 Mensagens';
                }

                contentHTML += `
                    <div class="campaign-card glass" style="padding: 16px; border-radius: var(--radius-md); background: rgba(255, 255, 255, 0.02); border: 1px solid var(--border-glass);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <h4 style="font-size: 15px; font-weight: 600; color: #fff;">📌 ${camp.nome}</h4>
                            <span class="tag-goal">${tagGoal}</span>
                        </div>

                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; font-size: 13px;">
                `;

                if (isMetricVisible('spend')) {
                    contentHTML += `
                        <div>
                            <span style="color: var(--text-muted);">💰 Investimento:</span>
                            <div style="font-weight: 700; color: #fff;">${formatBRL(camp.spend)}</div>
                        </div>
                    `;
                }

                if (isMetricVisible('reach')) {
                    contentHTML += `
                        <div>
                            <span style="color: var(--text-muted);">📢 Alcance:</span>
                            <div style="font-weight: 700; color: #fff;">${formatNum(camp.reach)}</div>
                        </div>
                    `;
                }

                if (isMetricVisible('impressions')) {
                    contentHTML += `
                        <div>
                            <span style="color: var(--text-muted);">👁️ Impressões:</span>
                            <div style="font-weight: 700; color: #fff;">${formatNum(camp.impressions)}</div>
                        </div>
                    `;
                }

                if (isMetricVisible('ctr')) {
                    contentHTML += `
                        <div>
                            <span style="color: var(--text-muted);">⚡ CTR:</span>
                            <div style="font-weight: 700; color: #fff;">${(camp.ctr || 0).toFixed(2).replace('.', ',')}%</div>
                        </div>
                    `;
                }

                if (isMetricVisible('cpc')) {
                    contentHTML += `
                        <div>
                            <span style="color: var(--text-muted);">🎯 CPC:</span>
                            <div style="font-weight: 700; color: #fff;">${formatBRL(camp.cpc)}</div>
                        </div>
                    `;
                }

                if (isCampVendas) {
                    const roasDisplay = (camp.spend > 0) ? `${campRoasStr}x` : 'Atribuição Tardia (Sem gasto no período)';
                    const roasFontSize = (camp.spend > 0) ? '16px' : '12px';

                    if (isMetricVisible('total_pedidos')) {
                        contentHTML += `
                            <div>
                                <span style="color: var(--text-muted);">🛵 Pedidos:</span>
                                <div style="font-weight: 700; color: var(--accent-green);">${formatNum(camp.total_pedidos)}</div>
                            </div>
                        `;
                    }

                    if (isMetricVisible('total_vendas')) {
                        contentHTML += `
                            <div>
                                <span style="color: var(--text-muted);">📈 Total em Vendas:</span>
                                <div style="font-weight: 700; color: var(--accent-green);">${formatBRL(camp.total_vendas)}</div>
                            </div>
                        `;
                    }

                    if (isMetricVisible('carrinhos')) {
                        contentHTML += `
                            <div>
                                <span style="color: var(--text-muted);">🛒 Carrinhos:</span>
                                <div style="font-weight: 700; color: var(--accent-green);">${formatNum(camp.carrinhos)}</div>
                            </div>
                        `;
                    }

                    if (isMetricVisible('checkouts')) {
                        contentHTML += `
                            <div>
                                <span style="color: var(--text-muted);">💳 Checkouts:</span>
                                <div style="font-weight: 700; color: var(--accent-green);">${formatNum(camp.checkouts)}</div>
                            </div>
                        `;
                    }

                    if (isMetricVisible('roas')) {
                        contentHTML += `
                            <div style="background: rgba(245, 158, 11, 0.1); padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(245, 158, 11, 0.2);">
                                <span style="color: var(--accent-gold); font-size: 12px; font-weight: 600;">🤑 ROAS da Campanha:</span>
                                <div style="font-weight: 800; font-size: ${roasFontSize}; color: var(--accent-gold);">${roasDisplay}</div>
                            </div>
                        `;
                    }
                } else if (hasConversas) {
                    if (isMetricVisible('visitas_perfil')) {
                        contentHTML += `
                            <div>
                                <span style="color: var(--text-muted);">👤 Visitas Perfil:</span>
                                <div style="font-weight: 700; color: #fff;">${formatNum(camp.visitas_perfil)}</div>
                            </div>
                        `;
                    }

                    if (isMetricVisible('conversas_iniciadas')) {
                        contentHTML += `
                            <div>
                                <span style="color: var(--text-muted);">💬 Conversas:</span>
                                <div style="font-weight: 700; color: var(--accent-purple);">${formatNum(camp.conversas_iniciadas)}</div>
                            </div>
                        `;
                    }

                    if (isMetricVisible('custo_por_conversa')) {
                        contentHTML += `
                            <div style="background: rgba(139, 92, 246, 0.1); padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(139, 92, 246, 0.2);">
                                <span style="color: var(--accent-purple); font-size: 12px; font-weight: 600;">📊 Custo/Conversa:</span>
                                <div style="font-weight: 800; font-size: 16px; color: var(--accent-purple);">${formatBRL(camp.custo_por_conversa)}</div>
                            </div>
                        `;
                    }
                } else {
                    if (isMetricVisible('visitas_perfil')) {
                        contentHTML += `
                            <div>
                                <span style="color: var(--text-muted);">👤 Visitas Perfil:</span>
                                <div style="font-weight: 700; color: #fff;">${formatNum(camp.visitas_perfil)}</div>
                            </div>
                        `;
                    }
                    contentHTML += `
                        <div style="grid-column: span 2;">
                            <span style="color: var(--text-dim); font-size: 12px;">ℹ️ Campanha focada apenas em Alcance/Engajamento.</span>
                        </div>
                    `;
                }

                contentHTML += `
                        </div>
                    </div>
                `;
            });

            contentHTML += `
                    </div>
                </div>
            `;
        }
    }

    detailPanel.innerHTML = contentHTML;
}
