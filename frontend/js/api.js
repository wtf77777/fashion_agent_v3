// ========== API 配置 ==========
const API_BASE_URL = window.location.origin;

// ========== API 請求封裝 ==========
const API = {
    // ========== 認證 API ==========
    async login(username, password) {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${API_BASE_URL}/api/login`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    },

    async register(username, password) {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${API_BASE_URL}/api/register`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    },

    // ========== 天氣 API ==========
    async getWeather(city) {
        const response = await fetch(
            `${API_BASE_URL}/api/weather?city=${encodeURIComponent(city)}`
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    },

    // ========== 上傳 API ==========
    async uploadImages(files, warmth = '薄') {
        const formData = new FormData();

        files.forEach(file => {
            formData.append('files', file);
        });

        const user = AppState.getUser();
        // ✅ 改這裡：傳送 UUID 而不是 BIGINT
        formData.append('user_id', user.id);
        formData.append('warmth', warmth);

        console.log(`[INFO] 上傳: user_id=${user.id}, 預設厚度=${warmth}`);

        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`上傳失敗: ${response.statusText}`);
        }

        return response.json();
    },

    // ========== 衣櫥 API ==========
    async getWardrobe() {
        const user = AppState.getUser();

        // ✅ 改這裡：驗證 user_id 存在
        if (!user || !user.id) {
            throw new Error('未登入或 user_id 無效');
        }

        console.log(`[INFO] 查詢衣櫥: user_id=${user.id}`);

        const response = await fetch(
            `${API_BASE_URL}/api/wardrobe?user_id=${encodeURIComponent(user.id)}`  // ✅ encodeURIComponent
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    },

    async deleteItem(itemId) {
        const user = AppState.getUser();
        const formData = new FormData();
        formData.append('user_id', user.id);
        formData.append('item_id', itemId);

        const response = await fetch(`${API_BASE_URL}/api/wardrobe/delete`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    },

    async batchDeleteItems(itemIds) {
        const user = AppState.getUser();
        const formData = new FormData();
        formData.append('user_id', user.id);

        // ✅ 改這裡：正確的陣列格式
        itemIds.forEach(id => {
            formData.append('item_ids', id);
        });

        const response = await fetch(`${API_BASE_URL}/api/wardrobe/batch-delete`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    },

    // ========== 推薦 API ==========
    async getRecommendation(city, style, occasion) {
        const user = AppState.getUser();

        // ✅ 改這裡：驗證 user_id
        if (!user || !user.id) {
            throw new Error('未登入');
        }

        const formData = new FormData();
        formData.append('user_id', user.id);
        formData.append('city', city);
        formData.append('style', style || '不限定風格');
        formData.append('occasion', occasion || '外出遊玩');

        const response = await fetch(`${API_BASE_URL}/api/recommendation`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    },

    async updateItem(itemId, data) {
        const user = AppState.getUser();
        const formData = new FormData();
        formData.append('user_id', user.id);
        formData.append('item_id', itemId);
        formData.append('name', data.name);
        formData.append('category', data.category);
        formData.append('color', data.color);
        formData.append('style', data.style);
        formData.append('warmth', data.warmth);

        const response = await fetch(`${API_BASE_URL}/api/wardrobe/update`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    }
};

// ========== 圖片處理工具 ==========
const ImageUtils = {
    // 壓縮圖片: 模擬「截圖邏輯」，先處理格式相容性，再強制縮小解析度
    async compressImage(file, maxWidth = 800, maxHeight = 800, quality = 0.6) {
        return new Promise(async (resolve, reject) => {
            let currentFile = file;
            const originalSize = file.size;

            // 1. 處理 iPhone HEIC 格式轉換 (虛擬截圖的第一步：格式轉正)
            const fileName = file.name.toLowerCase();
            const isHeic = fileName.endsWith('.heic') || fileName.endsWith('.heif') || file.type === 'image/heic';

            if (isHeic && typeof heic2any === 'function') {
                try {
                    console.log(`[HEIC 轉換] 偵測到手機特有格式: ${file.name}，正在進行相容性轉換...`);
                    const blob = await heic2any({
                        blob: file,
                        toType: "image/jpeg",
                        quality: 0.8
                    });

                    // 轉成 JPG File 物件
                    currentFile = new File([blob], file.name.replace(/\.(heic|heif)$/i, '.jpg'), {
                        type: "image/jpeg",
                        lastModified: Date.now()
                    });
                    console.log(`[HEIC 轉換] 轉換完成: ${Utils.formatFileSize(currentFile.size)}`);
                } catch (err) {
                    console.warn("HEIC 轉換失敗，嘗試直接讀取:", err);
                }
            }

            // 2. 執行「截圖式縮圖」邏輯 (透過 Canvas 強制降解析度)
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();

                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let width = img.width;
                    let height = img.height;

                    if (width > height) {
                        if (width > maxWidth) {
                            height = height * (maxWidth / width);
                            width = maxWidth;
                        }
                    } else {
                        if (height > maxHeight) {
                            width = width * (maxHeight / height);
                            height = maxHeight;
                        }
                    }

                    canvas.width = width;
                    canvas.height = height;

                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    canvas.toBlob((blob) => {
                        if (!blob) {
                            alert(`圖片處理失敗: ${currentFile.name}`);
                            reject(new Error("Canvas toBlob failed"));
                            return;
                        }

                        const finalFile = new File([blob], currentFile.name, {
                            type: 'image/jpeg',
                            lastModified: Date.now()
                        });

                        const finalSize = finalFile.size;
                        const reduction = ((originalSize - finalSize) / originalSize * 100).toFixed(1);
                        console.log(`[截圖壓縮完成] ${file.name}: ${Utils.formatFileSize(originalSize)} -> ${Utils.formatFileSize(finalSize)} (縮減率: ${reduction}%)`);

                        resolve(finalFile);
                    }, 'image/jpeg', quality);
                };

                img.onerror = (e) => {
                    alert(`圖片載入失敗: ${file.name}。請嘗試手動截圖後再上傳。`);
                    reject(new Error("Image load failed"));
                };
                img.src = e.target.result;
            };

            reader.onerror = (e) => {
                alert(`檔案讀取失敗: ${file.name}`);
                reject(new Error("FileReader failed"));
            };
            reader.readAsDataURL(currentFile);
        });
    },

    // 生成預覽 URL
    createPreviewURL(file) {
        return URL.createObjectURL(file);
    },

    // 清理預覽 URL
    revokePreviewURL(url) {
        URL.revokeObjectURL(url);
    },

    // 驗證圖片文件
    validateImageFile(file) {
        // 放寬檢查: 只要是 image 開頭，或是常見圖片副檔名
        const validTypes = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp', 'image/heic', 'image/heif'];
        const maxSize = 15 * 1024 * 1024; // 放寬到 15MB

        console.log(`[驗證] 檔名: ${file.name}, 類型: ${file.type}, 大小: ${file.size}`);

        // 某些手機瀏覽器 file.type 可能是空的，這裡做個容錯
        if (file.type && !file.type.startsWith('image/')) {
            // 如果 type 不是 image 開頭，再檢查副檔名
            const ext = file.name.split('.').pop().toLowerCase();
            if (!['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'].includes(ext)) {
                alert(`不支援的檔案格式: ${file.type || '未知'} (${file.name})`);
                throw new Error(`不支援的檔案類型: ${file.type}`);
            }
        }

        if (file.size > maxSize) {
            alert(`檔案過大: ${(file.size / 1024 / 1024).toFixed(2)}MB (最大 15MB)`);
            throw new Error(`檔案過大: ${(file.size / 1024 / 1024).toFixed(2)}MB`);
        }

        return true;
    }
};

// ========== 本地儲存工具 ==========
const Storage = {
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.error('儲存失敗:', error);
        }
    },

    get(key) {
        try {
            const value = localStorage.getItem(key);
            return value ? JSON.parse(value) : null;
        } catch (error) {
            console.error('讀取失敗:', error);
            return null;
        }
    },

    remove(key) {
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.error('刪除失敗:', error);
        }
    },

    clear() {
        try {
            localStorage.clear();
        } catch (error) {
            console.error('清空失敗:', error);
        }
    }
};

// ========== 防抖和節流工具 ==========
const Utils = {
    // 防抖
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // 節流
    throttle(func, limit) {
        let inThrottle;
        return function (...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    // 格式化日期
    formatDate(date) {
        return new Date(date).toLocaleDateString('zh-TW', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    },

    // 格式化檔案大小
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }
};
