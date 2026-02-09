// ========== 指定單品鎖定功能 (優先級 3) ==========
const AnchorItemUI = {
    selectedItems: [],  // [{ id, name, category, color }]
    wardrobeItems: [],  // 快取衣櫥列表
    isOpen: false,

    init() {
        this.bindEvents();
        this.loadStoredSelection();  // ✅ 初始化時載入已儲存的選擇
    },

    loadStoredSelection() {
        const stored = localStorage.getItem('anchorItems');
        if (stored) {
            try {
                this.selectedItems = JSON.parse(stored);
                this.updateAnchorDisplay();
            } catch (e) {
                this.selectedItems = [];
            }
        }
    },

    bindEvents() {
        // 綁定「指定單品」按鈕
        const anchorBtn = document.getElementById('anchor-item-btn');
        if (anchorBtn) {
            anchorBtn.addEventListener('click', () => this.openModal());
        }

        // 關閉 Modal
        const closeBtn = document.querySelector('.anchor-modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }

        // 確認選擇
        const confirmBtn = document.getElementById('anchor-confirm-btn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.confirmSelection());
        }

        // 點擊 Modal 外部也關閉
        const modal = document.getElementById('anchor-modal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal();
                }
            });
        }
    },

    async openModal() {
        // 載入用戶的衣櫥
        try {
            const result = await API.getWardrobe();
            if (result.success && result.items) {
                this.wardrobeItems = result.items;
                this.renderWardrobeList(result.items);
                this.showModal();
            } else {
                if (typeof Toast !== 'undefined') {
                    Toast.error('無法載入衣櫥');
                }
            }
        } catch (error) {
            if (typeof Toast !== 'undefined') {
                Toast.error('載入衣櫥失敗: ' + error.message);
            }
        }
    },

    renderWardrobeList(items) {
        const container = document.getElementById('anchor-wardrobe-list');
        if (!container) return;

        container.innerHTML = '';

        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state">衣櫥是空的，請先上傳衣物</div>';
            return;
        }

        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'anchor-item-card';
            
            const isSelected = this.selectedItems.some(s => s.id === item.id);
            if (isSelected) {
                div.classList.add('selected');
            }

            const imgSrc = item.image_data ? `data:image/jpeg;base64,${item.image_data}` : 'static/images/placeholder.jpg';

            div.innerHTML = `
                <img src="${imgSrc}" alt="${item.name}">
                <div class="anchor-item-info">
                    <strong>${item.name}</strong>
                    <div class="anchor-item-meta">
                        <span class="tag">${item.category}</span>
                        <span class="tag">${item.color}</span>
                    </div>
                </div>
            `;

            div.addEventListener('click', () => this.toggleItemSelection(item, div));
            container.appendChild(div);
        });
    },

    toggleItemSelection(item, cardElement) {
        const index = this.selectedItems.findIndex(s => s.id === item.id);
        if (index >= 0) {
            this.selectedItems.splice(index, 1);
            cardElement.classList.remove('selected');
        } else {
            // ✅ 限制最多選擇 3 件
            if (this.selectedItems.length < 3) {
                this.selectedItems.push({
                    id: item.id,
                    name: item.name,
                    category: item.category,
                    color: item.color
                });
                cardElement.classList.add('selected');
            } else {
                if (typeof Toast !== 'undefined') {
                    Toast.warning('最多只能選擇 3 件單品');
                }
            }
        }
    },

    confirmSelection() {
        // 儲存選擇的單品
        localStorage.setItem('anchorItems', JSON.stringify(this.selectedItems));
        
        const count = this.selectedItems.length;
        if (typeof Toast !== 'undefined') {
            Toast.success(`✅ 已指定 ${count} 件單品`);
        }
        
        this.closeModal();
        this.updateAnchorDisplay();
    },

    updateAnchorDisplay() {
        const badge = document.getElementById('anchor-count-badge');
        if (badge) {
            badge.textContent = this.selectedItems.length;
            badge.style.display = this.selectedItems.length > 0 ? 'inline-flex' : 'none';
        }
    },

    showModal() {
        const modal = document.getElementById('anchor-modal');
        if (modal) {
            modal.style.display = 'flex';
            this.isOpen = true;
        }
    },

    closeModal() {
        const modal = document.getElementById('anchor-modal');
        if (modal) {
            modal.style.display = 'none';
            this.isOpen = false;
        }
    }
};

// ========== 導購連結功能 (優先級 3) ==========
const ShoppingLinkUI = {
    /**
     * 生成購物連結
     * @param {string} itemName - 推薦的單品名稱 (e.g., "米色寬褲")
     * @returns {object} { shopee, google, uniqlo }
     */
    generateShoppingLinks(itemName) {
        if (!itemName) return null;

        // ✅ 動態生成各平台的搜尋連結
        const encodedName = encodeURIComponent(itemName);
        
        return {
            shopee: `https://shopee.tw/search?keyword=${encodedName}`,
            google: `https://www.google.com/shopping/search?q=${encodedName}`,
            uniqlo: `https://www.uniqlo.com/tw/zh_TW/search?q=${encodedName}`,
            momo: `https://www.momoshop.com.tw/search/searchShop.jsp?searchKeyword=${encodedName}`,
            pchome: `https://ecshop.pchome.com.tw/search/${encodedName}`
        };
    },

    /**
     * 在推薦詳情中顯示導購按鈕
     */
    renderShoppingButtons(itemName, container) {
        const links = this.generateShoppingLinks(itemName);
        if (!links) return;

        const shoppingDiv = document.createElement('div');
        shoppingDiv.className = 'shopping-links';
        shoppingDiv.innerHTML = `
            <p>🛍️ 缺件導購</p>
            <div class="shopping-buttons">
                <a href="${links.shopee}" target="_blank" class="shop-btn shopee">蝦皮</a>
                <a href="${links.momo}" target="_blank" class="shop-btn momo">momo</a>
                <a href="${links.google}" target="_blank" class="shop-btn google">Google購物</a>
                <a href="${links.uniqlo}" target="_blank" class="shop-btn uniqlo">UNIQLO</a>
            </div>
        `;

        if (container) {
            container.appendChild(shoppingDiv);
        }

        return shoppingDiv;
    }
};

// ========== 初始化 ==========
window.addEventListener('load', () => {
    if (typeof AnchorItemUI !== 'undefined') {
        AnchorItemUI.init();
    }
});

