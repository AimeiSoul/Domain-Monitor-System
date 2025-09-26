// static/js/dashboard.js
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

    // 初始化进度圈
    const progressCircles = document.querySelectorAll('.progress-circle');
    progressCircles.forEach(circle => {
        const percent = circle.getAttribute('data-percent');
        const status = circle.getAttribute('data-status');

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

    // 添加域名表单提交
    const addDomainForm = document.getElementById('addDomainForm');
    if (addDomainForm) {
        addDomainForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // 处理续费周期 - 如果只输入数字，自动添加"年"
            const renewalPeriodInput = document.getElementById('renewal_period');
            if (renewalPeriodInput && renewalPeriodInput.value && /^\d+$/.test(renewalPeriodInput.value)) {
                renewalPeriodInput.value = renewalPeriodInput.value + '年';
            }

            const formData = new FormData(this);

            fetch('/add_domain', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('网络响应不正常');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert('域名添加成功！');
                    window.location.reload();
                } else {
                    alert('添加失败: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('添加失败，请重试');
            });
        });
    }

    // 编辑域名按钮点击事件
    const editButtons = document.querySelectorAll('.edit-domain');
    editButtons.forEach(button => {
        button.addEventListener('click', function() {
            const domainId = this.getAttribute('data-domain-id');
            console.log('Editing domain ID:', domainId);

            // 获取域名数据并填充表单
            fetch(`/domain_data/${domainId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('网络响应不正常');
                }
                return response.json();
            })
            .then(data => {
                console.log('Response data:', data);
                if (data.success) {
                    const domain = data.domain;
                    
                    // 安全地设置表单字段值
                    setFormValue('edit_domain_id', domain.id);
                    setFormValue('edit_name', domain.name);
                    setFormValue('edit_registrar', domain.registrar || '');
                    setFormValue('edit_registration_date', domain.registration_date || '');
                    setFormValue('edit_expiration_date', domain.expiration_date || '');
                    
                    // 处理续费周期 - 去掉"年"字只显示数字
                    let renewalPeriod = domain.renewal_period || '';
                    if (renewalPeriod.endsWith('年')) {
                        renewalPeriod = renewalPeriod.slice(0, -1);
                    }
                    setFormValue('edit_renewal_period', renewalPeriod);
                    
                    setFormValue('edit_renewal_price', domain.renewal_price || '');
                    setFormValue('edit_currency', domain.currency || 'USD');
                    setFormValue('edit_renewal_url', domain.renewal_url || '');
                    setFormValue('edit_warning_threshold', domain.warning_threshold);
                    setFormValue('edit_danger_threshold', domain.danger_threshold);
                } else {
                    alert('获取域名数据失败: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('获取域名数据失败，请检查网络连接或刷新页面重试');
            });
        });
    });

    // 编辑域名表单提交
    const editDomainForm = document.getElementById('editDomainForm');
    if (editDomainForm) {
        editDomainForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // 处理续费周期 - 如果只输入数字，自动添加"年"
            const renewalPeriodInput = document.getElementById('edit_renewal_period');
            if (renewalPeriodInput && renewalPeriodInput.value && /^\d+$/.test(renewalPeriodInput.value)) {
                renewalPeriodInput.value = renewalPeriodInput.value + '年';
            }

            const formData = new FormData(this);
            const domainId = document.getElementById('edit_domain_id').value;

            fetch(`/update_domain/${domainId}`, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('域名更新成功！');
                    window.location.reload();
                } else {
                    alert('更新失败: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('更新失败，请重试');
            });
        });
    }

    // 删除域名按钮点击事件
    const deleteButtons = document.querySelectorAll('.delete-domain');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const domainId = this.getAttribute('data-domain-id');

            if (confirm('确定要删除这个域名吗？此操作不可恢复。')) {
                fetch(`/delete_domain/${domainId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('域名删除成功！');
                        window.location.reload();
                    } else {
                        alert('删除失败: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('删除失败，请重试');
                });
            }
        });
    });

    // 辅助函数：安全地设置表单字段值
    function setFormValue(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.value = value;
        } else {
            console.warn(`Element with ID '${elementId}' not found`);
        }
    }
});
