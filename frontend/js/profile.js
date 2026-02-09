// ========== 風格定義 ==========
const STYLE_DEFINITIONS = {
    "Minimalist": "黑白灰素色、剪裁俐落、冷淡風",
    "Japanese Cityboy": "寬鬆Oversized、多層次、大地色、自然舒適",
    "Korean Chic": "修身剪裁、顯高顯瘦、都會精緻、流行元素",
    "American Vintage": "牛仔、格紋、大學T、古著感",
    "Streetwear": "大Logo、強烈配色、工裝、球鞋文化",
    "Formal": "西裝、襯衫、適合職場",
    "Athleisure": "瑜珈褲、防風材質、機能舒適",
    "French Chic": "條紋、針織、隨性優雅",
    "Y2K": "元氣亮色、短版上衣、低腰褲、科技復古",
    "Old Money": "質感針織、Polo衫、低調奢華",
    "Bohemian": "碎花、流蘇、圖騰、民族風",
    "Grunge": "破損、鉚釘、全黑層次、個性叛逆",
    "Techwear": "全黑、多口袋、扣環織帶、未來感",
    "Coquette": "蝴蝶結、蕾絲、粉嫩、可愛夢幻",
    "Gorpcore": "登山機能、大地撞色、露營感"
};

// ========== 個人設定 UI 邏輯 ==========
const ProfileUI = {
    favoriteStyles: [],
    currentUser: null,

    init() {
        this.cacheDOM();
        this.bindEvents();
        this.loadProfile();
    },

    cacheDOM() {
        this.tabButtons = document.querySelectorAll('.profile-tab-btn');
        this.tabPages = document.querySelectorAll('.tab-page');
        this.genderSelect = document.getElementById('gender');
        this.heightInput = document.getElementById('height');
        this.weightInput = document.getElementById('weight');
        this.thermalRadios = document.querySelectorAll('input[name="thermal"]');
        this.styleSelect = document.getElementById('style-select');
        this.styleDesc = document.getElementById('style-desc');
        this.favoriteStylesList = document.getElementById('favorite-styles-list');
        this.dislikesTextarea = document.getElementById('dislikes');
        this.customDescTextarea = document.getElementById('custom-desc');
        this.historyList = document.getElementById('history-list');
    },

    bindEvents() {
        this.tabButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });
    },

    switchTab(tabName) {
        // 更新按鈕狀態
        this.tabButtons.forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 顯示對應的 tab 內容
        this.tabPages.forEach(page => {
            if (page.id === tabName) {
                page.classList.add('active');
                // 如果切換到歷史頁面，則載入歷史
                if (tabName === 'history') {
                    this.loadHistory();
                }
            } else {
                page.classList.remove('active');
            }
        });
    },

    async loadProfile() {
        const user = AppState.getUser();

        if (!user) {
            console.warn('⚠️ loadProfile: AppState.getUser() 回傳 null, 無法載入');
            return;
        }

        this.currentUser = user;
        const userId = this.currentUser.id;
        console.log('🚀 [Debug] 開始載入個人資料, UserID:', userId);

        try {
            const result = await API.getProfile(userId);
            console.log('📦 [Debug] API 回傳結果:', result);

            if (result.success && result.profile) {
                const profile = result.profile;
                console.log('📄 [Debug] Profile 資料內容:', profile);

                // 填充表單
                if (this.genderSelect) this.genderSelect.value = profile.gender || '';
                if (this.heightInput) this.heightInput.value = profile.height || '';
                if (this.weightInput) this.weightInput.value = profile.weight || '';
                if (this.dislikesTextarea) this.dislikesTextarea.value = profile.dislikes || '';
                if (this.customDescTextarea) this.customDescTextarea.value = profile.custom_style_desc || '';

                // 設定體感偏好
                const thermalValue = profile.thermal_preference || 'normal';
                const thermalRadio = document.querySelector(`input[name="thermal"][value="${thermalValue}"]`);
                if (thermalRadio) {
                    thermalRadio.checked = true;
                }

                // 載入喜好風格
                this.favoriteStyles = profile.favorite_styles || [];
                this.renderFavoriteStyles();

                console.log('✅ [Debug] 個人資料載入流程完成');
            } else {
                console.warn('⚠️ [Debug] API 回傳成功但無 profile 資料', result);
            }
        } catch (error) {
            console.error('❌ [Debug] 載入個人資料發生錯誤:', error);
        }
    },

    showStyleDescription() {
        const selectedStyle = this.styleSelect.value;
        if (selectedStyle && STYLE_DEFINITIONS[selectedStyle]) {
            this.styleDesc.textContent = STYLE_DEFINITIONS[selectedStyle];
        } else {
            this.styleDesc.textContent = '選擇一個風格查看詳細描述';
        }
    },

    addStyle() {
        const selectedStyle = this.styleSelect.value;
        if (!selectedStyle) {
            alert('請先選擇風格');
            return;
        }

        if (this.favoriteStyles.includes(selectedStyle)) {
            alert('此風格已在列表中');
            return;
        }

        this.favoriteStyles.push(selectedStyle);
        this.renderFavoriteStyles();
        this.styleSelect.value = '';
        this.styleDesc.textContent = '選擇一個風格查看詳細描述';
    },

    renderFavoriteStyles() {
        this.favoriteStylesList.innerHTML = '';

        if (this.favoriteStyles.length === 0) {
            this.favoriteStylesList.innerHTML = '<div style="color: #999; font-size: 12px;">未選擇任何風格</div>';
            return;
        }

        this.favoriteStyles.forEach(style => {
            const tag = document.createElement('div');
            tag.className = 'style-tag';
            tag.innerHTML = `
                <span>${style}</span>
                <button onclick="ProfileUI.removeStyle('${style}')">×</button>
            `;
            this.favoriteStylesList.appendChild(tag);
        });
    },

    removeStyle(style) {
        this.favoriteStyles = this.favoriteStyles.filter(s => s !== style);
        this.renderFavoriteStyles();
    },

    async savePersonalInfo() {
        const user = AppState.getUser();
        if (!user) return;

        try {
            const result = await API.updateProfile(
                user.id,
                this.genderSelect.value,
                this.heightInput.value,
                this.weightInput.value,
                null,
                null,
                document.querySelector('input[name="thermal"]:checked').value,
                null
            );

            if (result.success) {
                alert('✅ 個人資料已儲存');
            } else {
                alert('❌ 儲存失敗: ' + result.message);
            }
        } catch (error) {
            alert('❌ 儲存失敗: ' + error.message);
        }
    },

    async savePreferences() {
        const user = AppState.getUser();
        if (!user) return;

        try {
            const result = await API.updateProfile(
                user.id,
                null,
                null,
                null,
                JSON.stringify(this.favoriteStyles),
                this.dislikesTextarea.value,
                null,
                this.customDescTextarea.value
            );

            if (result.success) {
                alert('✅ 偏好設定已儲存');
            } else {
                alert('❌ 儲存失敗: ' + result.message);
            }
        } catch (error) {
            alert('❌ 儲存失敗: ' + error.message);
        }
    },

    async loadHistory() {
        const user = AppState.getUser();
        if (!user) return;

        try {
            const result = await API.getHistory(user.id);

            if (result.success && result.history) {
                if (result.history.length === 0) {
                    this.historyList.innerHTML = `<div class="empty-state"><p>暫無推薦記錄</p></div>`;
                    return;
                }

                this.historyList.innerHTML = '';
                result.history.forEach((item, index) => {
                    const date = new Date(item.created_at).toLocaleString('zh-TW');
                    const historyHTML = `
                        <div class="history-item">
                            <div class="history-info">
                                <strong>${index + 1}. ${item.city} - ${item.occasion}</strong>
                                <div class="history-detail">風格: ${item.style}</div>
                                <div class="history-date">📅 ${date}</div>
                            </div>
                            <button class="history-button" onclick="ProfileUI.deleteHistory(${item.id})">刪除</button>
                        </div>
                    `;
                    this.historyList.innerHTML += historyHTML;
                });
            }
        } catch (error) {
            console.error('載入歷史失敗:', error);
            this.historyList.innerHTML = `<div class="empty-state"><p>載入失敗</p></div>`;
        }
    },

    async deleteHistory(historyId) {
        if (!confirm('確定要刪除此推薦記錄嗎？')) {
            return;
        }

        const user = AppState.getUser();
        if (!user) return;

        try {
            const result = await API.deleteHistory(user.id, historyId);

            if (result.success) {
                alert('✅ 記錄已刪除');
                this.loadHistory();
            } else {
                alert('❌ 刪除失敗: ' + result.message);
            }
        } catch (error) {
            alert('❌ 刪除失敗: ' + error.message);
        }
    }
};

// ========== API 擴充 (在 api.js 中新增) ==========
// 以下方法應該新增到 API 物件中

API.getProfile = async function (user_id) {
    const response = await fetch(`${API_BASE_URL}/api/profile?user_id=${encodeURIComponent(user_id)}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
};

API.updateProfile = async function (
    user_id,
    gender,
    height,
    weight,
    favorite_styles,
    dislikes,
    thermal_preference,
    custom_style_desc
) {
    const formData = new FormData();
    formData.append('user_id', user_id);
    if (gender) formData.append('gender', gender);
    if (height) formData.append('height', height);
    if (weight) formData.append('weight', weight);
    if (favorite_styles) formData.append('favorite_styles', favorite_styles);
    if (dislikes) formData.append('dislikes', dislikes);
    if (thermal_preference) formData.append('thermal_preference', thermal_preference);
    if (custom_style_desc) formData.append('custom_style_desc', custom_style_desc);

    const response = await fetch(`${API_BASE_URL}/api/profile`, {
        method: 'POST',
        body: formData
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
};

API.getHistory = async function (user_id, limit = 20) {
    const response = await fetch(
        `${API_BASE_URL}/api/history?user_id=${encodeURIComponent(user_id)}&limit=${limit}`
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
};

API.deleteHistory = async function (user_id, history_id) {
    const formData = new FormData();
    formData.append('user_id', user_id);
    formData.append('history_id', history_id);

    const response = await fetch(`${API_BASE_URL}/api/history/delete`, {
        method: 'POST',
        body: formData
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
};

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    ProfileUI.init();
});
