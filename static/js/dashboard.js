// 仪表盘特定功能
document.addEventListener('DOMContentLoaded', function() {
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

    // 续费功能
    const renewButtons = document.querySelectorAll('.renew-domain');
    const renewConfirmModal = new bootstrap.Modal(document.getElementById('renewConfirmModal'));
    const confirmRenewalBtn = document.getElementById('confirmRenewalBtn');
    const renewalConfirmedCheckbox = document.getElementById('renewalConfirmed');
    
    // 续费按钮点击事件
    renewButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault(); // 阻止默认的链接跳转
            
            const domainId = this.getAttribute('data-domain-id');
            const domainName = this.getAttribute('data-domain-name');
            const renewalPeriod = this.getAttribute('data-renewal-period');
            const currentExpiration = this.getAttribute('data-current-expiration');
            
            // 打开续费网址在新标签页
            window.open(this.href, '_blank');
            
            // 填充模态框数据
            document.getElementById('renew_domain_id').value = domainId;
            document.getElementById('renew_domain_name').value = domainName;
            document.getElementById('renew_renewal_period').value = renewalPeriod;
            document.getElementById('renew_current_expiration').value = currentExpiration;
            
            // 显示域名信息
            document.getElementById('renew_domain_name_display').textContent = domainName;
            document.getElementById('renew_renewal_period_display').textContent = renewalPeriod;
            document.getElementById('renew_current_expiration_display').textContent = currentExpiration;
            
            // 计算并显示新的到期日期
            const newExpiration = calculateNewExpirationDate(currentExpiration, renewalPeriod);
            document.getElementById('renew_new_expiration_display').textContent = newExpiration;
            
            // 重置确认状态
            renewalConfirmedCheckbox.checked = false;
            confirmRenewalBtn.disabled = true;
            
            // 显示确认模态框
            renewConfirmModal.show();
        });
    });
    
    // 确认复选框状态改变事件
    renewalConfirmedCheckbox.addEventListener('change', function() {
        confirmRenewalBtn.disabled = !this.checked;
    });
    
    // 确认续费按钮点击事件
    confirmRenewalBtn.addEventListener('click', function() {
        const domainId = document.getElementById('renew_domain_id').value;
        const domainName = document.getElementById('renew_domain_name').value;
        const renewalPeriod = document.getElementById('renew_renewal_period').value;
        const currentExpiration = document.getElementById('renew_current_expiration').value;
        const newExpiration = calculateNewExpirationDate(currentExpiration, renewalPeriod);
        
        if (confirm(`确定要更新域名 ${domainName} 的到期日期为 ${newExpiration} 吗？`)) {
            // 发送续费请求
            fetch(`/renew_domain/${domainId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    new_expiration_date: newExpiration
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('域名续费成功！到期日期已更新。');
                    renewConfirmModal.hide();
                    window.location.reload(); // 刷新页面显示新日期
                } else {
                    alert('续费失败: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('续费失败，请重试');
            });
        }
    });
    
    // 计算新的到期日期函数
    function calculateNewExpirationDate(currentDate, renewalPeriod) {
        const current = new Date(currentDate);
        let yearsToAdd = 1; // 默认1年
        
        // 从续费周期中提取年数
        if (renewalPeriod) {
            const match = renewalPeriod.match(/(\d+)/);
            if (match) {
                yearsToAdd = parseInt(match[1]);
            }
        }
        
        // 添加年数
        const newDate = new Date(current);
        newDate.setFullYear(current.getFullYear() + yearsToAdd);
        
        // 格式化为 YYYY-MM-DD
        return newDate.toISOString().split('T')[0];
    }

});