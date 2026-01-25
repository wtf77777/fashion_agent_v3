// ========== 推薦頁面 UI 邏輯 - 智能推薦版 ==========
const RecommendationUI = {
    // 數據結構
    // currentRecommendation: { vive: "...", recommendations: [{ items: [], score: 80, reasons: [] }, ...] }
    aiResult: null,
    currentSetIndex: 0,      // 目前在第幾套推薦 (Set 1, 2, 3)
    currentItemIndex: 0,     // 目前在該套的第幾件單品 (Top, Bottom, Shoes...)

    init() {
        this.bindEvents();
    },

    bindEvents() {
        // 獲取推薦按鈕
        document.getElementById('get-recommendation-btn').addEventListener('click', () => {
            this.handleGetRecommendation();
        });

        // 城市選擇變更時更新天氣
        document.getElementById('city-select').addEventListener('change', () => {
            if (typeof Weather !== 'undefined') Weather.loadWeather();
        });
    },

    async handleGetRecommendation() {
        const city = document.getElementById('city-select').value;
        const style = document.getElementById('style-input').value.trim();
        const occasion = document.getElementById('occasion-input').value.trim();

        if (typeof AppState !== 'undefined') AppState.setLoading(true);

        try {
            const result = await API.getRecommendation(city, style, occasion);

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

        // 1. 顯示主容器
        resultContainer.style.display = 'block';

        // 2. 顯示 AI 描述
        textContainer.innerHTML = `<div class="vibe-box"><i class="fas fa-magic"></i> ${this.aiResult.vibe}</div>`;

        // 3. 渲染主推薦區塊 (包含 Tabs 和 Carousel)
        this.renderRecommendationSets();

        // 4. 滾動到結果
        resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    renderRecommendationSets() {
        const container = document.getElementById('recommendation-items');
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
                    ${currentSet.reasons.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>
        `;

        container.innerHTML = tabsHtml + carouselHtml;
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
