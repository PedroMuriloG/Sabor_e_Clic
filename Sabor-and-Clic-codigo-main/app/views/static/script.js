// Configuração dos Menus e Páginas por Perfil de Utilizador
const roleConfig = {
    cliente: [
    { id: 'client-catalog', label: '🍎 Catálogo de Pratos' },
    { id: 'client-cart', label: '🛒 Meu Carrinho & Histórico' },
    { id: 'client-space', label: '🏢 Reservar Bancada' },
    { id: 'client-login', label: '🔑 Área de Login' }
    ],
    cozinheiro: [
    { id: 'chef-kds', label: '🍳 Pedidos da Cozinha (KDS)' },
    { id: 'chef-recipe', label: '📜 Fichas Técnicas' }
    ],
    admin: [
    { id: 'admin-dashboard', label: '📊 Relatórios & Atrasos' },
    { id: 'admin-management', label: '⚙️ Gestão de Chefs e Bancadas' }
    ]
};

let cart = [];

function changeRole(role) {
    const tabsNav = document.getElementById('tabsNav');
    tabsNav.innerHTML = '';

    // Ocultar todas as páginas
    document.querySelectorAll('.page-content').forEach(page => {
    page.classList.remove('active');
    });

    // Construir novas abas para o perfil selecionado
    const tabs = roleConfig[role];
    tabs.forEach((tab, index) => {
    const btn = document.createElement('button');
    btn.className = `tab-btn ${index === 0 ? 'active' : ''}`;
    btn.innerText = tab.label;
    btn.onclick = () => switchTab(tab.id, btn);
    tabsNav.appendChild(btn);
    });

    // Exibir a primeira página do perfil
    if (tabs.length > 0) {
    document.getElementById(tabs[0].id).classList.add('active');
    }
}

function switchTab(pageId, btnElement) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.page-content').forEach(page => page.classList.remove('active'));

    btnElement.classList.add('active');
    document.getElementById(pageId).classList.add('active');
}

function addToCart(itemName, price) {
    cart.push({ itemName, price });
    updateCartUI();
    alert(`"${itemName}" adicionado ao carrinho!`);
}

function updateCartUI() {
    const cartItemsEl = document.getElementById('cartItems');
    if (cart.length === 0) {
    cartItemsEl.innerHTML = '<li>Nenhum item adicionado ainda.</li>';
    return;
    }
    cartItemsEl.innerHTML = cart.map(item => `<li>${item.itemName} - R$ ${item.price.toFixed(2)}</li>`).join('');
}

function checkout() {
    if (cart.length === 0) {
    alert('O seu carrinho está vazio!');
    return;
    }
    alert('Pedido realizado com sucesso e enviado para o painel do Cozinheiro!');
    cart = [];
    updateCartUI();
}

// Inicialização por defeito com o perfil 'cliente'
changeRole('cliente');