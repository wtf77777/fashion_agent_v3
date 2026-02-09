// ========== 推薦頁面 UI 邏輯 - 智能推薦版 ==========
const RecommendationUI = {
    // 數據結構
    // currentRecommendation: { vive: "...", recommendations: [{ items: [], score: 80, reasons: [] }, ...] }
    aiResult: null,
    currentSetIndex: 0,      // 目前在第幾套推薦 (Set 1, 2, 3)
    currentItemIndex: 0,     // 目前在該套的第幾件單品 (Top, Bottom, Shoes...)

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    },

    getReasonLines(currentSet) {
        const setReasons = Array.isArray(currentSet?.reasons) ? currentSet.reasons.filter(Boolean) : [];
        if (setReasons.length > 0) {
            return setReasons;
        }

        return this.parseReasonText(this.aiResult?.detailed_reasons);
    },

    parseReasonText(text) {
        if (!text || typeof text !== 'string') return [];
        const cleaned = text.replace(/\r/g, '').trim();
        if (!cleaned) return [];

        const lines = cleaned
            .split(/\n+/)
            .map(line => line.trim())
            .filter(Boolean);

        return lines.length > 0 ? lines : [cleaned];
    },

    init() {
        this.bindEvents();
    },

    bindEvents() {
        // 獲取推薦按鈕
        const getRecommendBtn = document.getElementById('get-recommendation-btn');
        if (getRecommendBtn) {
            getRecommendBtn.addEventListener('click', () => {
                this.handleGetRecommendation();
            });
        }

        // 城市選擇變更時更新天氣
        const citySelect = document.getElementById('city-select');
        if (citySelect) {
            citySelect.addEventListener('change', () => {
                if (typeof Weather !== 'undefined') Weather.loadWeather();
            });
        }
    },

    async handleGetRecommendation() {
        const city = document.getElementById('city-select').value;
        const style = document.getElementById('style-input').value.trim();
        const occasion = document.getElementById('occasion-input').value.trim();

        // ✅ 優先級 3：從 localStorage 讀取指定單品
        const anchorItems = JSON.parse(localStorage.getItem('anchorItems') || '[]');
        const lockedItemIds = anchorItems.map(item => item.id);

        if (typeof AppState !== 'undefined') AppState.setLoading(true);

        try {
            const result = await API.getRecommendation(city, style, occasion, lockedItemIds);

            if (result.success && result.recommendation) {
                // 儲存後端回傳的結構化推薦
                this.aiResult = result.recommendation;
                this.currentSetIndex = 0;
                this.currentItemIndex = 0;

                this.renderAll();
                if (typeof Toast !== 'undefined') Toast.success('✨ 智能穿搭方案已生成！');
            } else {
                if (typeof Toast !== 'undefined') Toast.error(result.message || '獲取推薦失敗');
            }
        } catch (error) {
            console.error('推薦錯誤:', error);
            if (typeof Toast !== 'undefined') Toast.error('獲取推薦失敗: ' + error.message);
        } finally {
            if (typeof AppState !== 'undefined') AppState.setLoading(false);
        }
    },

    renderAll() {
        const resultContainer = document.getElementById('recommendation-result');
        const textContainer = document.getElementById('recommendation-text');

        if (!resultContainer || !textContainer) {
            console.warn('⚠️ 推薦結果容器不存在');
            if (typeof Toast !== 'undefined') Toast.error('頁面元素加載失敗');
            return;
        }

        // 1. 顯示主容器
        resultContainer.style.display = 'block';

        // 2. 顯示 AI 描述
        const vibeText = this.escapeHtml(this.aiResult?.vibe || '');
        textContainer.innerHTML = `<div class="vibe-box"><i class="fas fa-magic"></i> ${vibeText}</div>`;

        // 3. 渲染主推薦區塊 (包含 Tabs 和 Carousel)
        this.renderRecommendationSets();

        // 4. 滾動到結果
        resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    renderRecommendationSets() {
        const container = document.getElementById('recommendation-items');
        
        if (!container) {
            console.warn('⚠️ recommendation-items 容器不存在');
            return;
        }
        
        const sets = this.aiResult.recommendations; // 這是 [ 套裝1, 套裝2, 套裝3 ]

        if (!sets || sets.length === 0) {
            container.innerHTML = `<div class="no-items">💡 沒有找到適合的穿搭組合，建議增加衣櫥收藏！</div>`;
            return;
        }

        // 上方 Tabs
        let tabsHtml = `<div class="recommendation-tabs">`;
        sets.forEach((set, idx) => {
            tabsHtml += `
                <button class="tab-btn ${idx === this.currentSetIndex ? 'active' : ''}" 
                        onclick="RecommendationUI.switchSet(${idx})">
                    推薦方案 ${idx + 1}
                </button>
            `;
        });
        tabsHtml += `</div>`;

        // 中間 Carousel
        const currentSet = sets[this.currentSetIndex];
        const currentItems = currentSet.items;
        const currentItem = currentItems[this.currentItemIndex];

        // ✅ 修復問題 8: 檢查是否需要購物連結容器
        let shoppingHtml = '';
        if (!currentItem.id || currentItem.id === 'ai_suggested' || !currentItem.image_data) {
            shoppingHtml = `<div id="shopping-container-${this.currentSetIndex}-${this.currentItemIndex}"></div>`;
        }

        const reasonLines = this.getReasonLines(currentSet);
        const reasonsHtml = reasonLines.length > 0
            ? reasonLines.map(r => `<li>${this.escapeHtml(r)}</li>`).join('')
            : `<li>暫無推薦原因說明。</li>`;

        let carouselHtml = `
            <div class="carousel-container">
                <button class="carousel-btn prev" onclick="RecommendationUI.prevItem()">◀</button>
                
                <div class="carousel-main">
                    <div class="carousel-indicator">
                        ${currentItems[this.currentItemIndex].category} (${this.currentItemIndex + 1}/${currentItems.length})
                    </div>
                    
                    <div class="carousel-item-display">
                        ${this.renderClothingItem(currentItems[this.currentItemIndex])}
                    </div>
                </div>
                
                <button class="carousel-btn next" onclick="RecommendationUI.nextItem()">▶</button>
            </div>
            
            <div class="outfit-reasons">
                <h4>✨ 推薦原因</h4>
                <ul>
                    ${reasonsHtml}
                </ul>
            </div>
            ${shoppingHtml}
        `;

        container.innerHTML = tabsHtml + carouselHtml;
        
        // ✅ 修復問題 8：在渲染後立即添加購物連結（使用動態 ID）
        if (shoppingHtml && typeof ShoppingLinkUI !== 'undefined') {
            setTimeout(() => {
                const shoppingContainer = document.getElementById(`shopping-container-${this.currentSetIndex}-${this.currentItemIndex}`);
                if (shoppingContainer) {
                    ShoppingLinkUI.renderShoppingButtons(currentItem.name, shoppingContainer);
                }
            }, 0);
        }
    },

    renderClothingItem(item) {
        // 處理圖片
        const imgSrc = item.image_data ? `data:image/jpeg;base64,${item.image_data}` : 'static/images/placeholder.jpg';

        return `
            <div class="recommended-item animate-fade-in">
                <div class="recommended-item-image">
                    <img src="${imgSrc}" alt="${item.name}">
                </div>
                <div class="recommended-item-info">
                    <h3>${item.name}</h3>
                    <div class="item-tag-cloud">
                        <span class="tag color">${item.color}</span>
                        <span class="tag style">${item.style || '經典'}</span>
                        <span class="tag warmth">保暖 ${'🔥'.repeat(item.warmth)}</span>
                    </div>
                </div>
            </div>
        `;
    },

    // 控制邏輯
    switchSet(index) {
        this.currentSetIndex = index;
        this.currentItemIndex = 0; // 重置到第一件
        this.renderRecommendationSets();
    },

    prevItem() {
        const items = this.aiResult.recommendations[this.currentSetIndex].items;
        if (this.currentItemIndex > 0) {
            this.currentItemIndex--;
            this.renderRecommendationSets();
        }
    },

    nextItem() {
        const items = this.aiResult.recommendations[this.currentSetIndex].items;
        if (this.currentItemIndex < items.length - 1) {
            this.currentItemIndex++;
            this.renderRecommendationSets();
        }
    }
};
