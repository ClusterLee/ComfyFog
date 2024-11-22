import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// 导入ComfyUI的核心模块
// app: ComfyUI的主应用对象，提供扩展注册功能
// api: ComfyUI的API调用工具，用于与后端通信

// 手动加载CSS
// 创建link元素加载CSS
function loadCSS() {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.href = './extensions/ComfyFog/web/fog_panel.css';
    document.head.appendChild(link);
}

// 注册ComfyUI扩展
// ComfyUI启动时会自动加载web/js目录下的所有js文件
// 并调用registerExtension注册扩展
app.registerExtension({
    // 扩展名称，必须唯一，推荐使用命名空间格式
    name: "ComfyFog.Control",
    
    // setup方法在ComfyUI初始化时被调用
    // 用于设置扩展的初始状态和UI
    async setup() {
        // 加载CSS
        loadCSS();
        
        // 1. 创建菜单入口
        await this.createMenu();
        
        // 2. 创建控制面板
        await this.createPanel();
        
        // 3. 绑定事件处理器
        this.bindEvents();
        
        // 4. 启动状态更新循环
        this.startUpdates();
        
        // 5. 记录扩展已加载
        console.log("Fog Control Panel loaded");
    },
    
    // 创建菜单入口
    // 在ComfyUI的主菜单中添加一个按钮来打开控制面板
    createMenu() {
        // 创建菜单项容器
        const menuEntry = document.createElement('div');
        menuEntry.classList.add('comfy-menu-entry');
        menuEntry.innerHTML = `
            <label>Fog Control</label>
            <button id="fog-panel-btn">Open Panel</button>
        `;
        
        // 添加到ComfyUI的菜单中
        // .comfy-menu 是ComfyUI的主菜单容器
        const menuContainer = document.querySelector('.comfy-menu');
        menuContainer.appendChild(menuEntry);
    },
    
    // 创建控制面板
    // 面板默认隐藏，点击菜单按钮时显示
    createPanel() {
        const panel = document.createElement('div');
        panel.id = 'fog-control-panel';
        panel.style.display = 'none';  // 初始隐藏
        panel.classList.add('comfy-modal');  // 使用ComfyUI的模态框样式
        
        // 面板内容模板
        panel.innerHTML = `
            <div class="comfy-modal-content">
                <!-- 状态显示区域 -->
                <div class="fog-status">
                    <h4>Status</h4>
                    <div>Running: <span id="fog-running-status">No</span></div>
                    <div>Current Task: <span id="fog-current-task">None</span></div>
                </div>
                
                <!-- 控制开关区域 -->
                <div class="fog-controls">
                    <h4>Controls</h4>
                    <label class="fog-switch">
                        <input type="checkbox" id="fog-enabled"/>
                        <span>Enable Fog Computing</span>
                    </label>
                </div>
                
                <!-- 调度时间设置区域 -->
                <div class="fog-schedule">
                    <h4>Schedule</h4>
                    <div id="fog-schedule-list"></div>
                    <button id="add-schedule" class="comfy-btn">Add Time Slot</button>
                </div>
                
                <!-- 历史记录显示区域 -->
                <div class="fog-history">
                    <h4>Recent Tasks</h4>
                    <div id="fog-task-history"></div>
                </div>
            </div>
        `;
        
        // 添加到页面
        document.body.appendChild(panel);
    },
    
    // 绑定事件处理器
    // 处理所有的用户交互
    bindEvents() {
        // 1. 面板显示/隐藏控制
        const panelBtn = document.getElementById('fog-panel-btn');
        const panel = document.getElementById('fog-control-panel');
        
        panelBtn.addEventListener('click', () => {
            const isVisible = panel.style.display !== 'none';
            panel.style.display = isVisible ? 'none' : 'block';
            
            // 显示面板时更新状态
            if (!isVisible) {
                this.updateStatus();
            }
        });
        
        // 2. 启用/禁用开关处理
        const enabledSwitch = document.getElementById('fog-enabled');
        enabledSwitch.addEventListener('change', async (e) => {
            try {
                // 发送配置更新请求
                await this.updateConfig({ enabled: e.target.checked });
                // 更新显示状态
                await this.updateStatus();
            } catch (error) {
                console.error('Failed to update config:', error);
                // 更新失败时恢复开关状态
                e.target.checked = !e.target.checked;
            }
        });
        
        // 3. 添加时间段按钮处理
        document.getElementById('add-schedule').addEventListener('click', 
            () => this.addScheduleSlot());
    },
    
    // 更新状态显示
    // 从后端获取最新状态并更新UI
    async updateStatus() {
        try {
            const response = await api.fetchApi('/fog/status');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            updateUI(data);
        } catch (error) {
            console.error('Error updating status:', error);
            // 显示错误信息给用户
            showError('Failed to update status');
        }
    },
    
    // 启动定期更新
    // 只在面板可见时更新状态
    startUpdates() {
        this.updateInterval = setInterval(() => {
            const panel = document.getElementById('fog-control-panel');
            if (panel.style.display !== 'none') {
                this.updateStatus();
            }
        }, 5000);  // 每5秒更新一次
    },
    
    // 更新配置
    // 向后端发送配置更新请求
    async updateConfig(config) {
        const response = await api.fetchApi('/fog/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        return response.json();
    },
    
    // 添加调度时间段
    addScheduleSlot() {
        const scheduleList = document.getElementById('fog-schedule-list');
        const slot = document.createElement('div');
        slot.classList.add('schedule-slot');
        
        // 时间段输入模板
        slot.innerHTML = `
            <input type="time" class="start-time" />
            <span>to</span>
            <input type="time" class="end-time" />
            <button class="remove-slot">×</button>
        `;
        
        // 绑定删除和更改事件
        slot.querySelector('.remove-slot').onclick = () => {
            slot.remove();
            this.saveSchedule();
        };
        
        // 时间改变时保存
        slot.querySelectorAll('input[type="time"]').forEach(input => {
            input.onchange = () => this.saveSchedule();
        });
        
        scheduleList.appendChild(slot);
    },
    
    // 保存调度时间设置
    async saveSchedule() {
        const scheduleList = document.getElementById('fog-schedule-list');
        const schedule = Array.from(scheduleList.children).map(slot => ({
            start: slot.querySelector('.start-time').value,
            end: slot.querySelector('.end-time').value
        }));
        
        await this.updateConfig({ schedule });
    }
});

function showError(message) {
    // 添加错误提示UI
    const errorDiv = document.createElement('div');
    errorDiv.className = 'fog-error';
    errorDiv.textContent = message;
    // ... 显示错误信息的逻辑
}
