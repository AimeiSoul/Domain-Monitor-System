// static/js/script.js
// 导航栏优化脚本
document.addEventListener('DOMContentLoaded', function() {
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
    
    // 初始调整
    adjustNavbar();
    
    // 窗口大小改变时调整
    window.addEventListener('resize', adjustNavbar);
    
    // 处理导航栏折叠菜单的显示/隐藏
    const navbarToggler = document.querySelector('.navbar-toggler');
    if (navbarToggler) {
        navbarToggler.addEventListener('click', function() {
            const navbarCollapse = document.getElementById('navbarCollapse');
            navbarCollapse.classList.toggle('show');
        });
    }
    
    // 点击导航链接后自动折叠菜单（手机端）
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function() {
            if (window.innerWidth <= 991) {
                const navbarCollapse = document.getElementById('navbarCollapse');
                if (navbarCollapse.classList.contains('show')) {
                    // 使用Bootstrap的折叠方法
                    const bsCollapse = new bootstrap.Collapse(navbarCollapse);
                    bsCollapse.hide();
                }
            }
        });
    });

    // 设置进度圈
    const progressCircles = document.querySelectorAll('.progress-circle');
    progressCircles.forEach(circle => {
        const percent = circle.getAttribute('data-percent');
        const status = circle.getAttribute('data-status');
        
        // 设置CSS变量
        circle.style.setProperty('--percent', percent);
        
        // 根据状态设置颜色
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
    });
    
    // 处理详情切换按钮
    const toggleButtons = document.querySelectorAll('.details-toggle');
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const icon = this.querySelector('i');
            if (icon.classList.contains('bi-chevron-down')) {
                icon.classList.replace('bi-chevron-down', 'bi-chevron-up');
                this.textContent = '隐藏详细信息 ';
            } else {
                icon.classList.replace('bi-chevron-up', 'bi-chevron-down');
                this.textContent = '显示详细信息 ';
            }
            this.appendChild(icon);
        });
    });
});
