// 检测屏幕尺寸并相应调整导航栏
function adjustNavbar() {
    const navbar = document.querySelector('.navbar');
    const isLoggedIn = document.querySelector('.navbar-text') !== null;
    
    if (window.innerWidth <= 991) {
        // 手机端
        if (isLoggedIn) {
            navbar.classList.add('navbar-expanded');
        } else {
            navbar.classList.remove('navbar-expanded');
        }
    } else {
        // PC端
        navbar.classList.remove('navbar-expanded');
    }
}

// 初始化导航栏功能
function initNavbar() {
    // 初始调整
    adjustNavbar();
    
    // 窗口大小改变时调整
    window.addEventListener('resize', adjustNavbar);
    
    // 修复汉堡菜单点击事件 - 使用事件委托确保动态元素也能工作
    document.addEventListener('click', function(e) {
        // 检查点击的是否是汉堡菜单按钮
        const navbarToggler = e.target.closest('.navbar-toggler');
        if (navbarToggler) {
            const navbarCollapse = document.getElementById('navbarCollapse');
            if (navbarCollapse) {
                // 使用Bootstrap的Collapse组件来切换状态
                const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse) || 
                                  new bootstrap.Collapse(navbarCollapse, {toggle: true});
            }
        }
        
        // 检查点击的是否是导航链接（手机端自动关闭菜单）
        const navLink = e.target.closest('.nav-link');
        if (navLink && window.innerWidth <= 991) {
            const navbarCollapse = document.getElementById('navbarCollapse');
            
            if (navbarCollapse && navbarCollapse.classList.contains('show')) {
                const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse);
                if (bsCollapse) {
                    bsCollapse.hide();
                } else {
                    new bootstrap.Collapse(navbarCollapse, {hide: true});
                }
            }
        }
    });
}

// 通用功能初始化
function initCommonFeatures() {
    // 初始化进度圈
    const progressCircles = document.querySelectorAll('.progress-circle');
    progressCircles.forEach(circle => {
        const percent = circle.getAttribute('data-percent');
        const status = circle.getAttribute('data-status');

        if (percent && status) {
            circle.style.setProperty('--percent', percent);

            let statusColor;
            switch(status) {
                case 'success':
                    statusColor = '#198754';
                    break;
                case 'warning':
                    statusColor = '#ffc107';
                    break;
                case 'danger':
                    statusColor = '#dc3545';
                    break;
                default:
                    statusColor = '#0d6efd';
            }
            circle.style.setProperty('--status-color', statusColor);
        }
    });

    // 处理详情切换按钮
    const toggleButtons = document.querySelectorAll('.details-toggle');
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const icon = this.querySelector('i');
            if (icon) {
                if (icon.classList.contains('bi-chevron-down')) {
                    icon.classList.replace('bi-chevron-down', 'bi-chevron-up');
                    this.innerHTML = '隐藏详细信息 <i class="bi bi-chevron-up"></i>';
                } else {
                    icon.classList.replace('bi-chevron-up', 'bi-chevron-down');
                    this.innerHTML = '显示详细信息 <i class="bi bi-chevron-down"></i>';
                }
            }
        });
    });
}

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initNavbar();
    initCommonFeatures();
});