// static/js/script.js
// 初始化进度圈
document.addEventListener('DOMContentLoaded', function() {
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
