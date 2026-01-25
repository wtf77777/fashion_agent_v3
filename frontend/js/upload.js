// ========== 上傳頁面 UI 邏輯 - 佇列上傳版本 ==========
const UploadUI = {
    tempFiles: [], // 目前選取但尚未確認的原始 File 物件
    queue: [],     // 已確認厚度，準備批量上傳的項目
    maxFiles: 20,

    init() {
        this.cacheDOM();
        this.bindEvents();
    },

    cacheDOM() {
        this.uploadZone = document.getElementById('upload-zone');
        this.fileInput = document.getElementById('file-input');
        this.selectBtn = document.getElementById('select-btn');
        this.confirmBtn = document.getElementById('add-to-queue-btn');
        this.warmthSelect = document.getElementById('batch-warmth-select');
        this.queueGrid = document.getElementById('queue-grid');
        this.queueCount = document.getElementById('queue-count');
        this.batchArea = document.getElementById('batch-action-area');
        this.batchUploadBtn = document.getElementById('batch-upload-btn');
    },

    bindEvents() {
        // 觸發檔案選取
        [this.uploadZone, this.selectBtn].forEach(el => {
            if (el) {
                el.addEventListener('click', (e) => {
                    if (e.target === this.fileInput) return;
                    this.fileInput.click();
                });
            }
        });

        // 處理檔案選取
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelect(e.target.files);
            }
        });

        // 拖曳上傳
        this.uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadZone.classList.add('drag-over');
        });

        this.uploadZone.addEventListener('dragleave', () => {
            this.uploadZone.classList.remove('drag-over');
        });

        this.uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadZone.classList.remove('drag-over');
            this.handleFileSelect(e.dataTransfer.files);
        });

        // 按下「確認」按鈕
        this.confirmBtn.addEventListener('click', () => this.pushToQueue());

        // 按下「開始批量辨識並上傳全部」
        this.batchUploadBtn.addEventListener('click', () => this.handleBatchUpload());
    },

    handleFileSelect(files) {
        const fileArray = Array.from(files);

        // 簡單驗證
        const validFiles = fileArray.filter(file => {
            try {
                return ImageUtils.validateImageFile(file);
            } catch (e) {
                console.warn(e.message);
                return false;
            }
        });

        if (validFiles.length === 0) return;

        this.tempFiles = validFiles;

        // 視覺回饋
        this.selectBtn.textContent = `已選取 ${this.tempFiles.length} 張`;
        this.selectBtn.style.background = "#e3f2fd";
        Toast.info(`已載入 ${this.tempFiles.length} 張照片，請選擇厚度後按確認`);
    },

    /**
     * 將暫存的圖檔正式加入「待上傳隊列」
     */
    async pushToQueue() {
        if (this.tempFiles.length === 0) {
            Toast.warning("請先上傳或選取照片");
            return;
        }

        const warmth = this.warmthSelect.value;
        if (!warmth) {
            Toast.warning("請選擇這批衣服的厚薄程度");
            return;
        }

        AppState.setLoading(true);

        try {
            for (const file of this.tempFiles) {
                // 為了即時顯示，先做一個預覽 URL
                const previewUrl = URL.createObjectURL(file);

                const item = {
                    id: Math.random().toString(36).substr(2, 9),
                    file: file,
                    previewUrl: previewUrl,
                    warmth: warmth,
                    isEditing: false
                };

                this.queue.push(item);
            }

            // 重置上方控制項
            this.tempFiles = [];
            this.fileInput.value = '';
            this.selectBtn.textContent = '上傳照片';
            this.selectBtn.style.background = '';
            this.warmthSelect.selectedIndex = 0;

            this.renderQueue();
            Toast.success("已加入待上傳隊列");
        } catch (error) {
            console.error(error);
            Toast.error("加入隊列失敗");
        } finally {
            AppState.setLoading(false);
        }
    },

    /**
     * 渲染下方的隊列列表
     */
    renderQueue() {
        this.queueGrid.innerHTML = '';
        this.queueCount.textContent = this.queue.length;

        if (this.queue.length === 0) {
            this.queueGrid.innerHTML = '<div class="queue-empty-msg">目前沒有等待上傳的衣服</div>';
            this.batchArea.style.display = 'none';
            return;
        }

        this.batchArea.style.display = 'block';

        this.queue.forEach(item => {
            const el = document.createElement('div');
            el.className = 'queue-item';

            if (item.isEditing) {
                el.innerHTML = `
                    <div class="item-left">
                        <img class="item-thumbnail" src="${item.previewUrl}">
                        <div class="item-meta">
                            <span class="item-name">${item.file.name}</span>
                            <select class="warmth-select-small" onchange="UploadUI.updateItemWarmth('${item.id}', this.value)">
                                <option value="薄" ${item.warmth === '薄' ? 'selected' : ''}>極薄</option>
                                <option value="適中" ${item.warmth === '適中' ? 'selected' : ''}>中等</option>
                                <option value="厚" ${item.warmth === '厚' ? 'selected' : ''}>極厚</option>
                            </select>
                        </div>
                    </div>
                    <div class="item-actions">
                        <button class="btn-text-save" onclick="UploadUI.toggleEdit('${item.id}')">儲存</button>
                    </div>
                `;
            } else {
                el.innerHTML = `
                    <div class="item-left">
                        <img class="item-thumbnail" src="${item.previewUrl}">
                        <div class="item-meta">
                            <span class="item-name">${item.file.name}</span>
                            <span class="item-tag warmth-tag-${item.warmth}">極${item.warmth}</span>
                        </div>
                    </div>
                    <div class="item-actions">
                        <button class="btn-icon" onclick="UploadUI.toggleEdit('${item.id}')" title="編輯厚度">✎</button>
                        <button class="btn-icon" onclick="UploadUI.removeFromQueue('${item.id}')" title="刪除">✕</button>
                    </div>
                `;
            }
            this.queueGrid.appendChild(el);
        });
    },

    toggleEdit(id) {
        const item = this.queue.find(i => i.id === id);
        if (item) {
            item.isEditing = !item.isEditing;
            this.renderQueue();
        }
    },

    updateItemWarmth(id, value) {
        const item = this.queue.find(i => i.id === id);
        if (item) item.warmth = value;
    },

    removeFromQueue(id) {
        const index = this.queue.findIndex(i => i.id === id);
        if (index > -1) {
            // 釋放記憶體
            URL.revokeObjectURL(this.queue[index].previewUrl);
            this.queue.splice(index, 1);
            this.renderQueue();
        }
    },

    /**
     * 執行最後的上傳 (呼叫後端 API)
     */
    async handleBatchUpload() {
        if (this.queue.length === 0) return;

        AppState.setLoading(true);
        const startTime = Date.now();

        try {
            // 由於 API 目前設計是一次上傳一批並帶入一個 warmth 值，
            // 為了支援「每件衣服不同厚度」，我們需要分組上傳，或者修改後端。
            // 這裡採用「分組上傳」策略，將相同厚度的衣服打包在一起發送，以減少 API 呼叫次數（Gemini 批次）。

            const groups = {
                '薄': this.queue.filter(i => i.warmth === '薄'),
                '適中': this.queue.filter(i => i.warmth === '適中'),
                '厚': this.queue.filter(i => i.warmth === '厚')
            };

            let totalSuccess = 0;
            let totalFail = 0;
            const allItems = [];

            for (const [warmthKey, items] of Object.entries(groups)) {
                if (items.length === 0) continue;

                Toast.info(`正在處理「極${warmthKey}」類別 (${items.length} 件)...`);

                // 1. 圖片壓縮
                const compressedFiles = await Promise.all(
                    items.map(item => ImageUtils.compressImage(item.file))
                );

                // 2. 上傳到後端
                const result = await API.uploadImages(compressedFiles, warmthKey);

                if (result.success) {
                    totalSuccess += (result.success_count || 0);
                    totalFail += (result.fail_count || 0);
                    if (result.items) allItems.push(...result.items);
                } else {
                    totalFail += items.length;
                    console.error(`類別 ${warmthKey} 上傳失敗:`, result.message);
                }
            }

            // 清空隊列
            this.queue.forEach(i => URL.revokeObjectURL(i.previewUrl));
            this.queue = [];
            this.renderQueue();

            // 顯示最終結果
            const duration = ((Date.now() - startTime) / 1000).toFixed(1);
            Toast.success(`🎉 任務完成！成功: ${totalSuccess}, 失敗: ${totalFail} (耗時 ${duration}s)`);

            if (allItems.length > 0) {
                this.showUploadResults(allItems);
            }

        } catch (error) {
            console.error('上傳過程出錯:', error);
            Toast.error('上傳失敗: ' + error.message);
        } finally {
            AppState.setLoading(false);
        }
    },

    showUploadResults(items) {
        // 重用原本的呈現邏輯，但增加動畫
        const resultsHTML = `
            <div class="upload-results" style="margin-top: 20px; border-left: 4px solid var(--success); background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <h3 style="margin-bottom: 15px;">✅ 剛加入衣櫥的衣服</h3>
                <div class="results-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px;">
                    ${items.map(item => `
                        <div class="result-item" style="background: #f9f9f9; padding: 10px; border-radius: 8px; border: 1px solid #eee;">
                            <p style="font-weight: 600; font-size: 0.9rem; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${item.name}</p>
                            <p style="font-size: 0.8rem; color: #666;">${item.category} | ${item.color}</p>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        const stagingSection = document.querySelector('.queue-section');
        const existingResults = document.querySelector('.upload-results');
        if (existingResults) existingResults.remove();

        const div = document.createElement('div');
        div.innerHTML = resultsHTML;
        stagingSection.after(div.firstElementChild);

        setTimeout(() => {
            const res = document.querySelector('.upload-results');
            if (res) {
                res.style.transition = 'opacity 1s';
                res.style.opacity = '0';
                setTimeout(() => res.remove(), 1000);
            }
        }, 8000);
    }
};
