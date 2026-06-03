from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import math
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart 
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import atexit
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///domain.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "check_same_thread": False
    }
}

db = SQLAlchemy(app)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '请先登录'})
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    
    def __repr__(self):
        return f'<User {self.username}>'

# 域名模型
class Domain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    registrar = db.Column(db.String(255))
    registration_date = db.Column(db.DateTime)
    expiration_date = db.Column(db.DateTime, nullable=False)
    renewal_period = db.Column(db.String(50))
    renewal_price = db.Column(db.String(255))
    renewal_url = db.Column(db.String(500))
    renewal_date = db.Column(db.DateTime)  # 续费日期
    currency = db.Column(db.String(10), default='USD')
    warning_threshold = db.Column(db.Integer, default=30)
    danger_threshold = db.Column(db.Integer, default=7)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # 邮件发送状态
    warning_sent = db.Column(db.Boolean, default=False)
    danger_sent = db.Column(db.Boolean, default=False)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    # 是否需要续期（永久域名不需要续期）
    needs_renewal = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<Domain {self.name}>'
    
    def days_remaining(self):
        if not self.needs_renewal:
            # 永久域名返回一个很大的数字
            return 999999
        if self.expiration_date:
            return (self.expiration_date.date() - datetime.utcnow().date()).days
        return 0

    def remaining_text(self):
        """返回页面展示用的到期时间文案。"""
        days = self.days_remaining()
        if days < 0:
            return f'已过期 {abs(days)} 天'
        if days == 0:
            return '今天到期'
        return f'剩余 {days} 天'
    
    def status(self):
        if not self.needs_renewal:
            return 'info'  # 永久域名使用info状态
        days = self.days_remaining()
        if days <= self.danger_threshold:
            return 'danger'
        elif days <= self.warning_threshold:
            return 'warning'
        else:
            return 'success'
    
    def progress_percentage(self):
        """计算域名有效期的进度百分比"""
        if self.renewal_date and self.expiration_date:
            # 使用续费日期作为起始点计算进度
            total_days = (self.expiration_date - self.renewal_date).days
            remaining_days = self.days_remaining()
            if total_days > 0:
                percentage = (remaining_days / total_days) * 100
                return round(max(0, min(100, percentage)), 1)
        return 0

# SMTP配置模型
class SMTPConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mail_server = db.Column(db.String(255), nullable=False, default='smtp.gmail.com')
    mail_port = db.Column(db.Integer, nullable=False, default=587)
    mail_use_tls = db.Column(db.Boolean, nullable=False, default=True)
    mail_username = db.Column(db.String(255), nullable=False)
    mail_password = db.Column(db.String(255), nullable=False)
    mail_default_sender = db.Column(db.String(255), nullable=False)
    admin_email = db.Column(db.String(255), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    
    def __repr__(self):
        return f'<SMTPConfig {self.mail_server}>'

# 初始化SMTP配置
def init_smtp_config():
    with app.app_context():
        if not SMTPConfig.query.first():
            default_config = SMTPConfig(
                mail_server='smtp.gmail.com',
                mail_port=587,
                mail_use_tls=True,
                mail_username='',
                mail_password='',
                mail_default_sender='',
                admin_email='',
                enabled=False
            )
            db.session.add(default_config)
            db.session.commit()
            print("默认SMTP配置已创建")

# 创建美化的邮件模板
def create_email_template(domain, days_remaining, alert_level):
    """创建美化的邮件模板
    
    Args:
        domain: 域名对象
        days_remaining: 剩余天数
        alert_level: 警告级别 ('danger' 或 'warning')
    
    Returns:
        str: 美化后的HTML邮件内容
    """
    
    time_text = domain.remaining_text()

    # 根据警告级别设置颜色和标题
    if alert_level == 'danger':
        primary_color = "#dc3545"  # 红色
        title = "【紧急】域名过期提醒" if days_remaining < 0 else "【紧急】域名即将过期"
        urgency_text = "已过期" if days_remaining < 0 else "即将过期"
        action_text = "请立即续费"
        icon = "⚠️"
    else:
        primary_color = "#ffc107"  # 黄色
        title = "【提醒】域名即将过期"
        urgency_text = "即将过期"
        action_text = "请考虑续费"
        icon = "ℹ️"
    
    # 格式化日期
    expiration_date = domain.expiration_date.strftime('%Y年%m月%d日')
    renewal_date = domain.renewal_date.strftime('%Y年%m月%d日') if domain.renewal_date else "未知"
    current_date = datetime.now().strftime('%Y年%m月%d日 %H:%M')
    
    # 创建续费链接
    renewal_link = domain.renewal_url or "#"
    renewal_text = "立即续费" if domain.renewal_url else "暂无续费链接"
    
    html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f6f6f6;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background: linear-gradient(135deg, {primary_color}, #ffffff);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            padding: 30px;
        }}
        .domain-info {{
            background-color: #f8f9fa;
            border-left: 4px solid {primary_color};
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .domain-name {{
            font-size: 22px;
            font-weight: bold;
            color: {primary_color};
            margin-bottom: 10px;
        }}
        .days-remaining {{
            font-size: 36px;
            font-weight: bold;
            color: {primary_color};
            text-align: center;
            margin: 20px 0;
        }}
        .details {{
            display: flex;
            justify-content: space-between;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .detail-item {{
            flex: 1;
            min-width: 200px;
            margin: 10px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 6px;
            text-align: center;
        }}
        .detail-label {{
            font-size: 14px;
            color: #666;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 16px;
            font-weight: bold;
        }}
        .action-button {{
            display: inline-block;
            background-color: {primary_color};
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            margin: 20px 0;
            text-align: center;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #e9ecef;
        }}
        .alert-icon {{
            font-size: 48px;
            margin-bottom: 20px;
        }}
        @media (max-width: 600px) {{
            .details {{
                flex-direction: column;
            }}
            .detail-item {{
                min-width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="alert-icon">{icon}</div>
            <h1>{title}</h1>
        </div>
        
        <div class="content">
            <p>尊敬的用户，您好：</p>
            <p>系统检测到您监控的域名<strong>{domain.name}</strong>{urgency_text}，为避免服务中断，{action_text}。</p>
            
            <div class="domain-info">
                <div class="domain-name">{domain.name}</div>
                <div class="days-remaining">{time_text}</div>
            </div>
            
            <div class="details">
                <div class="detail-item">
                    <div class="detail-label">注册商</div>
                    <div class="detail-value">{domain.registrar or '未知'}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">续费日期</div>
                    <div class="detail-value">{renewal_date}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">到期日期</div>
                    <div class="detail-value">{expiration_date}</div>
                </div>
            </div>
            
            {f'<div style="text-align: center;"><a href="{renewal_link}" class="action-button">{renewal_text}</a></div>' if renewal_link != "#" else ''}
            
            <p style="color: #666; font-size: 14px; margin-top: 30px;">
                <strong>温馨提示：</strong><br>
                域名过期后将无法正常访问，可能导致业务中断、数据丢失和品牌损失。<br>
                建议您提前完成续费操作，确保业务连续性。
            </p>
        </div>
        
        <div class="footer">
            <p>此邮件由 <strong>域名监控系统</strong> 自动发送</p>
            <p>发送时间：{current_date}</p>
            <p>如果您有任何疑问，请查看系统设置或联系管理员</p>
            <p style="margin-top: 10px; font-size: 10px; color: #999;">
                此为系统自动发送的邮件，请勿直接回复
            </p>
        </div>
    </div>
</body>
</html>
"""
    return html_template

# 邮件发送函数
def send_email_async(subject, recipient, body):
    """异步发送邮件"""
    def send_email(app, subject, recipient, body):
        # 在新线程中创建应用上下文
        with app.app_context():
            try:
                config = SMTPConfig.query.first()
                if not config or not config.enabled:
                    print("❌ SMTP未启用或未配置")
                    return False
                
                print(f"📧 开始发送邮件到: {recipient}")
                print(f"📨 主题: {subject}")
                print(f"🔧 使用服务器: {config.mail_server}:{config.mail_port}")
                print(f"👤 用户名: {config.mail_username}")
                
                msg = MIMEMultipart()
                msg['From'] = config.mail_default_sender
                msg['To'] = recipient
                msg['Subject'] = subject
                
                msg.attach(MIMEText(body, 'html'))
                
                # 根据端口选择连接方式
                if config.mail_port == 465:
                    # 端口465使用SSL连接
                    print(f"🔐 使用SSL连接 (端口465)")
                    server = smtplib.SMTP_SSL(config.mail_server, config.mail_port)
                else:
                    # 其他端口使用普通连接，可能需要TLS
                    print(f"🔐 使用普通连接，TLS: {config.mail_use_tls}")
                    server = smtplib.SMTP(config.mail_server, config.mail_port)
                    if config.mail_use_tls:
                        server.starttls()
                        print("🔐 TLS已启用")
                
                print("🔑 正在登录...")
                server.login(config.mail_username, config.mail_password)
                print("✅ 登录成功")
                
                print("📤 正在发送邮件...")
                server.send_message(msg)
                server.quit()
                print(f"✅ 邮件已成功发送至 {recipient}")
                return True
            except Exception as e:
                print(f"❌ 发送邮件失败: {str(e)}")
                import traceback
                traceback.print_exc()
                return False
    
    # 在新线程中发送邮件，避免阻塞主程序
    # 传递app实例和其他参数
    thread = Thread(target=send_email, args=(app, subject, recipient, body))
    thread.start()
    print(f"🧵 邮件发送任务已在后台线程启动")

# 测试邮件发送函数
def send_test_email(config, subject, recipient, body):
    """同步发送测试邮件"""
    try:
        msg = MIMEMultipart()
        msg['From'] = config.mail_default_sender
        msg['To'] = recipient
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        print(f"🔧 测试邮件 - 使用服务器: {config.mail_server}:{config.mail_port}")
        
        # 根据端口选择连接方式
        if config.mail_port == 465:
            # 端口465使用SSL连接
            print(f"🔐 测试邮件 - 使用SSL连接 (端口465)")
            server = smtplib.SMTP_SSL(config.mail_server, config.mail_port)
        else:
            # 其他端口使用普通连接，可能需要TLS
            print(f"🔐 测试邮件 - 使用普通连接，TLS: {config.mail_use_tls}")
            server = smtplib.SMTP(config.mail_server, config.mail_port)
            if config.mail_use_tls:
                server.starttls()
                print("🔐 测试邮件 - TLS已启用")
        
        print("🔑 测试邮件 - 正在登录...")
        server.login(config.mail_username, config.mail_password)
        print("✅ 测试邮件 - 登录成功")
        
        print("📤 测试邮件 - 正在发送...")
        server.send_message(msg)
        server.quit()
        print(f"✅ 测试邮件已发送至 {recipient}")
        return True
    except Exception as e:
        print(f"❌ 发送测试邮件失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def should_send_domain_reminder(domain, days_remaining, today=None):
    """根据当前剩余天数和上次提醒时间判断是否发送邮件。"""
    today = today or datetime.utcnow().date()
    last_reminder_date = domain.last_checked.date() if domain.last_checked else None
    sent_today = last_reminder_date == today

    if days_remaining < 0:
        overdue_days = abs(days_remaining)
        should_send = (
            not sent_today and (
                not domain.danger_sent or
                overdue_days == 1 or
                last_reminder_date is None or
                (today - last_reminder_date).days >= 7
            )
        )
        return should_send, 'danger'

    if days_remaining <= domain.danger_threshold:
        return (not domain.danger_sent or not sent_today), 'danger'

    if days_remaining <= domain.warning_threshold:
        return (not domain.warning_sent), 'warning'

    return False, None

def create_reminder_subject(domain, days_remaining, alert_level):
    """创建提醒邮件标题。"""
    if days_remaining < 0:
        return f"【紧急】域名 {domain.name} 已过期 {abs(days_remaining)} 天"

    time_text = domain.remaining_text()
    if alert_level == 'danger':
        return f"【紧急】域名 {domain.name} 即将过期！{time_text}"

    return f"【提醒】域名 {domain.name} 即将过期，{time_text}"

# 修复域名检查函数
def check_domain_expiry():
    """检查所有域名的到期状态并发送提醒"""
    with app.app_context():
        print("=" * 60)
        print("🔍 开始执行域名检查任务...")
        
        # 检查SMTP是否启用
        config = SMTPConfig.query.first()
        if not config:
            print("❌ SMTP配置不存在，跳过域名检查")
            return
            
        if not config.enabled:
            print("❌ SMTP未启用，跳过域名检查")
            return
            
        print(f"✅ SMTP配置正常: {config.mail_server}:{config.mail_port}")
        print(f"📧 管理员邮箱: {config.admin_email}")
        print(f"🔐 发件人: {config.mail_default_sender}")
        
        domains = Domain.query.all()
        print(f"🌐 发现 {len(domains)} 个域名需要检查")
        
        if len(domains) == 0:
            print("ℹ️ 没有域名需要检查")
            return
        
        sent_count = 0
        for domain in domains:
            try:
                # 跳过永久域名
                if not domain.needs_renewal:
                    print(f"\n📋 检查域名: {domain.name}")
                    print(f"  ℹ️ 永久域名，跳过检查")
                    continue
                
                days_remaining = domain.days_remaining()
                print(f"\n📋 检查域名: {domain.name}")
                print(f"  剩余天数: {days_remaining}")
                print(f"  危险阈值: {domain.danger_threshold}")
                print(f"  警告阈值: {domain.warning_threshold}")
                print(f"  危险邮件已发送: {domain.danger_sent}")
                print(f"  警告邮件已发送: {domain.warning_sent}")
                print(f"  续费日期: {domain.renewal_date}")
                print(f"  到期日期: {domain.expiration_date}")
                
                should_send, alert_level = should_send_domain_reminder(domain, days_remaining)

                if should_send:
                    print(f"  ⚠️ 域名 {domain.name} 达到提醒条件，需要发送邮件")
                    subject = create_reminder_subject(domain, days_remaining, alert_level)
                    body = create_email_template(domain, days_remaining, alert_level)
                    
                    print(f"  📤 准备发送提醒邮件到: {config.admin_email}")
                    send_email_async(subject, config.admin_email, body)
                    
                    if alert_level == 'warning':
                        domain.warning_sent = True
                    elif alert_level == 'danger':
                        domain.danger_sent = True
                    domain.last_checked = datetime.utcnow()
                    db.session.commit()

                    sent_count += 1
                    print(f"  ✅ 提醒邮件已安排发送 - 域名: {domain.name}, 类型: {alert_level}")
                elif alert_level:
                    print(f"  ℹ️ 域名 {domain.name} 今天或当前周期已提醒过，跳过")
                else:
                    print(f"  ✅ 域名 {domain.name} 状态正常")
                        
            except Exception as e:
                print(f"  ❌ 处理域名 {domain.name} 时出错: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n📊 域名检查完成，共安排发送 {sent_count} 封提醒邮件")
        print("=" * 60)

# 路由：首页
@app.route('/')
def index():
    domains = (
        Domain.query
        .order_by(
            Domain.needs_renewal.desc(),   # ✅
            Domain.expiration_date.asc(),  # ✅
            Domain.id.asc()
        )
        .all()
    )
    return render_template('index.html', domains=domains, now=datetime.now())

# 路由：登录页
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('登录成功！', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误！', 'danger')
    
    return render_template('login.html')

# 路由：登出
@app.route('/logout')
def logout():
    session.clear()
    flash('您已成功登出。', 'info')
    return redirect(url_for('index'))

# 路由：仪表盘
@app.route('/dashboard')
@login_required
def dashboard():
    domains = (
        Domain.query
        .order_by(
            Domain.needs_renewal.desc(),   # ✅
            Domain.expiration_date.asc(),  # ✅
            Domain.id.asc()
        )
        .all()
    )
    return render_template('dashboard.html', domains=domains, now=datetime.now())


# 路由：SMTP配置页面
@app.route('/smtp_config')
@login_required
def smtp_config():
    # 只有管理员可以访问SMTP配置
    if session.get('username') != 'admin':
        flash('只有管理员可以访问SMTP配置', 'danger')
        return redirect(url_for('dashboard'))
    
    config = SMTPConfig.query.first()
    return render_template('smtp_config.html', config=config)

# 路由：更新SMTP配置
@app.route('/update_smtp_config', methods=['POST'])
@login_required
def update_smtp_config():
    # 只有管理员可以更新SMTP配置
    if session.get('username') != 'admin':
        return jsonify({'success': False, 'message': '只有管理员可以更新SMTP配置'})
    
    try:
        config = SMTPConfig.query.first()
        if not config:
            config = SMTPConfig()
        
        config.mail_server = request.form.get('mail_server')
        config.mail_port = int(request.form.get('mail_port'))
        config.mail_use_tls = request.form.get('mail_use_tls') == 'true'
        config.mail_username = request.form.get('mail_username')
        config.mail_password = request.form.get('mail_password')
        config.mail_default_sender = request.form.get('mail_default_sender')
        config.admin_email = request.form.get('admin_email')
        config.enabled = request.form.get('enabled') == 'true'
        
        db.session.add(config)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'SMTP配置更新成功！'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})

# 路由：测试SMTP配置
@app.route('/test_smtp_config', methods=['POST'])
@login_required
def test_smtp_config():
    # 只有管理员可以测试SMTP配置
    if session.get('username') != 'admin':
        return jsonify({'success': False, 'message': '只有管理员可以测试SMTP配置'})
    
    try:
        config = SMTPConfig.query.first()
        if not config:
            return jsonify({'success': False, 'message': '请先配置SMTP设置'})
        
        # 测试邮件发送
        subject = "域名监控系统 - SMTP配置测试成功"
        body = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMTP配置测试</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f6f6f6;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #007bff, #ffffff);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            padding: 30px;
        }}
        .success-icon {{
            font-size: 48px;
            margin-bottom: 20px;
            color: #28a745;
        }}
        .details {{
            background-color: #f8f9fa;
            border-left: 4px solid #007bff;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #e9ecef;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">✅</div>
            <h1>SMTP配置测试成功</h1>
        </div>
        
        <div class="content">
            <p>恭喜！您的域名监控系统SMTP配置测试成功。</p>
            
            <div class="details">
                <p><strong>测试详情：</strong></p>
                <p>📧 收件人：{config.admin_email}</p>
                <p>🔧 邮件服务器：{config.mail_server}:{config.mail_port}</p>
                <p>⏰ 发送时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
            </div>
            
            <p>如果您收到了这封邮件，说明您的SMTP配置已经正确设置，系统可以正常发送域名到期提醒邮件。</p>
            
            <p style="color: #666; font-size: 14px; margin-top: 30px;">
                <strong>下一步：</strong><br>
                请确保在系统中添加您要监控的域名，并设置合适的提醒阈值。<br>
                系统将自动监控域名到期状态并及时发送提醒。
            </p>
        </div>
        
        <div class="footer">
            <p>此邮件由 <strong>域名监控系统</strong> 自动发送</p>
            <p>发送时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
            <p style="margin-top: 10px; font-size: 10px; color: #999;">
                此为系统自动发送的测试邮件，请勿直接回复
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        result = send_test_email(config, subject, config.admin_email, body)
        
        if result:
            return jsonify({'success': True, 'message': '测试邮件已发送，请检查您的邮箱。'})
        else:
            return jsonify({'success': False, 'message': '发送测试邮件失败，请检查SMTP配置。'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'测试失败: {str(e)}'})

# 路由：添加域名
@app.route('/add_domain', methods=['POST'])
@login_required
def add_domain():
    try:
        # 获取表单数据
        name = request.form.get('name')
        registrar = request.form.get('registrar')
        
        registration_date_str = request.form.get('registration_date')
        expiration_date_str = request.form.get('expiration_date')
        
        registration_date = datetime.strptime(registration_date_str, '%Y-%m-%d') if registration_date_str else None
        # 永久域名可以不填到期日期，使用一个很远的日期
        if expiration_date_str:
            expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        else:
            # 如果没有填写到期日期，设置为一个很远的日期（100年后）
            expiration_date = datetime.utcnow() + timedelta(days=36500)
        
        renewal_period = request.form.get('renewal_period')
        renewal_price = request.form.get('renewal_price')
        renewal_url = request.form.get('renewal_url')
        currency = request.form.get('currency', 'USD')
        # 获取是否需要续期（默认为True）
        needs_renewal = request.form.get('needs_renewal') == 'true' or request.form.get('needs_renewal') == 'on'

        # 创建新域名
        new_domain = Domain(
            name=name,
            registrar=registrar,
            registration_date=registration_date,
            expiration_date=expiration_date,
            renewal_period=renewal_period,
            renewal_price=renewal_price,
            renewal_url=renewal_url,
            currency=currency,
            user_id=session['user_id'],
            needs_renewal=needs_renewal,
            # 设置续费日期为注册日期
            renewal_date=registration_date if registration_date else datetime.utcnow()
        )
        
        db.session.add(new_domain)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '域名添加成功！'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})

# 路由：更新域名
@app.route('/update_domain/<int:domain_id>', methods=['POST'])
@login_required
def update_domain(domain_id):
    try:
        domain = Domain.query.get_or_404(domain_id)
        
        # 验证用户权限
        if domain.user_id != session['user_id']:
            return jsonify({'success': False, 'message': '无权操作'})
        
        # 记录旧的注册日期，用于比较
        old_registration_date = domain.registration_date
        
        # 更新域名信息
        domain.name = request.form.get('name')
        domain.registrar = request.form.get('registrar')
        
        registration_date_str = request.form.get('registration_date')
        expiration_date_str = request.form.get('expiration_date')
        
        domain.registration_date = datetime.strptime(registration_date_str, '%Y-%m-%d') if registration_date_str else None
        # 永久域名可以不填到期日期，使用一个很远的日期
        if expiration_date_str:
            domain.expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        else:
            # 如果没有填写到期日期，设置为一个很远的日期（100年后）
            domain.expiration_date = datetime.utcnow() + timedelta(days=36500)
        
        domain.renewal_period = request.form.get('renewal_period')
        domain.renewal_price = request.form.get('renewal_price')
        domain.renewal_url = request.form.get('renewal_url')
        domain.currency = request.form.get('currency', 'USD')
        domain.warning_threshold = int(request.form.get('warning_threshold', 30))
        domain.danger_threshold = int(request.form.get('danger_threshold', 7))
        # 更新是否需要续期
        domain.needs_renewal = request.form.get('needs_renewal') == 'true' or request.form.get('needs_renewal') == 'on'
        
        # 只有当注册日期确实发生变化时，才更新续费日期
        if registration_date_str:
            new_registration_date = datetime.strptime(registration_date_str, '%Y-%m-%d')
            # 只有当新的注册日期与旧的注册日期不同时，才更新 renewal_date
            if old_registration_date != new_registration_date:
                domain.renewal_date = new_registration_date
                print(f"注册日期发生变化，更新 renewal_date 为: {domain.renewal_date}")
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '域名更新成功！'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})

# 路由：删除域名
@app.route('/delete_domain/<int:domain_id>', methods=['POST'])
@login_required
def delete_domain(domain_id):
    try:
        domain = Domain.query.get_or_404(domain_id)
        
        # 验证用户权限
        if domain.user_id != session['user_id']:
            return jsonify({'success': False, 'message': '无权操作'})
        
        db.session.delete(domain)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '域名删除成功！'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

# 路由：获取域名数据（用于编辑）
@app.route('/domain_data/<int:domain_id>')
@login_required
def domain_data(domain_id):
    try:
        domain = Domain.query.get(domain_id)
        if not domain:
            return jsonify({'success': False, 'message': '域名不存在'})
        
        # 验证用户权限
        if domain.user_id != session['user_id']:
            return jsonify({'success': False, 'message': '无权操作'})
        
        return jsonify({
            'success': True,
            'domain': {
                'id': domain.id,
                'name': domain.name,
                'registrar': domain.registrar,
                'registration_date': domain.registration_date.strftime('%Y-%m-%d') if domain.registration_date else '',
                'expiration_date': domain.expiration_date.strftime('%Y-%m-%d'),
                'renewal_period': domain.renewal_period,
                'renewal_price': domain.renewal_price,
                'renewal_url': domain.renewal_url,
                'currency': domain.currency,
                'warning_threshold': domain.warning_threshold,
                'danger_threshold': domain.danger_threshold,
                'renewal_date': domain.renewal_date.strftime('%Y-%m-%d') if domain.renewal_date else '',
                'needs_renewal': domain.needs_renewal
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取数据失败: {str(e)}'})

# 路由：续费域名
@app.route('/renew_domain/<int:domain_id>', methods=['POST'])
@login_required
def renew_domain(domain_id):
    """处理域名续费请求"""
    try:
        domain = Domain.query.get_or_404(domain_id)
        data = request.get_json()
        
        if not data or 'new_expiration_date' not in data:
            return jsonify({'success': False, 'message': '无效的请求数据'})
        
        # 验证用户权限
        if domain.user_id != session['user_id']:
            return jsonify({'success': False, 'message': '无权操作此域名'})
        
        # 解析新的到期日期
        new_expiration_str = data['new_expiration_date']
        try:
            new_expiration = datetime.strptime(new_expiration_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': '无效的日期格式'})
        
        # 记录旧的到期日期和续费日期
        old_expiration = domain.expiration_date
        old_renewal_date = domain.renewal_date
        
        # 更新到期日期和续费日期
        domain.expiration_date = new_expiration
        domain.renewal_date = datetime.utcnow()  # 续费日期设置为当前日期
        
        # 重置邮件发送状态
        if hasattr(domain, 'warning_sent'):
            domain.warning_sent = False
        if hasattr(domain, 'danger_sent'):
            domain.danger_sent = False
        if hasattr(domain, 'last_checked'):
            domain.last_checked = datetime.utcnow()
        
        db.session.commit()
        
        # 记录续费操作日志
        logger.info(f"域名续费成功 - 域名: {domain.name}, 旧到期日: {old_expiration.strftime('%Y-%m-%d')}, 新到期日: {new_expiration.strftime('%Y-%m-%d')}, 旧续费日: {old_renewal_date.strftime('%Y-%m-%d') if old_renewal_date else '无'}, 新续费日: {domain.renewal_date.strftime('%Y-%m-%d')}, 操作人: {session.get('username')}")
        
        return jsonify({
            'success': True, 
            'message': '续费成功',
            'domain': {
                'name': domain.name,
                'old_expiration': old_expiration.strftime('%Y-%m-%d'),
                'new_expiration': new_expiration.strftime('%Y-%m-%d'),
                'renewal_date': domain.renewal_date.strftime('%Y-%m-%d')
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"域名续费失败 - 域名ID: {domain_id}, 错误: {str(e)}")
        return jsonify({'success': False, 'message': f'续费失败: {str(e)}'})

# 路由：手动触发域名检查
@app.route('/trigger_domain_check', methods=['POST'])
@login_required
def trigger_domain_check():
    """手动触发域名检查"""
    try:
        print("=" * 50)
        print("手动触发域名检查...")
        
        # 检查SMTP配置
        config = SMTPConfig.query.first()
        if not config:
            print("❌ SMTP配置不存在")
            return jsonify({'success': False, 'message': 'SMTP配置不存在'})
        
        if not config.enabled:
            print("❌ SMTP未启用")
            return jsonify({'success': False, 'message': 'SMTP未启用'})
        
        print(f"✅ SMTP配置状态: 已启用")
        print(f"📧 管理员邮箱: {config.admin_email}")
        print(f"🔧 邮件服务器: {config.mail_server}:{config.mail_port}")
        
        # 检查域名数据
        domains = Domain.query.all()
        print(f"🌐 域名数量: {len(domains)}")
        
        for domain in domains:
            days_remaining = domain.days_remaining()
            print(f"  域名: {domain.name}, 剩余天数: {days_remaining}, 续费日期: {domain.renewal_date}, 到期日期: {domain.expiration_date}")
        
        # 执行检查
        check_domain_expiry()
        
        return jsonify({'success': True, 'message': '域名检查已完成，请查看控制台输出'})
    except Exception as e:
        print(f"❌ 手动触发失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'检查失败: {str(e)}'})

# 路由：立即发送测试邮件
@app.route('/send_test_now', methods=['POST'])
@login_required
def send_test_now():
    """立即发送测试邮件"""
    try:
        print("🚀 立即发送测试邮件...")
        
        config = SMTPConfig.query.first()
        if not config or not config.enabled:
            return jsonify({'success': False, 'message': 'SMTP未启用或未配置'})
        
        subject = "域名监控系统 - 立即测试邮件"
        body = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>立即测试邮件</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f6f6f6;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #007bff, #ffffff);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            padding: 30px;
        }}
        .success-icon {{
            font-size: 48px;
            margin-bottom: 20px;
            color: #28a745;
        }}
        .details {{
            background-color: #f8f9fa;
            border-left: 4px solid #007bff;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #e9ecef;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">✅</div>
            <h1>立即测试邮件</h1>
        </div>
        
        <div class="content">
            <p>这是一封立即测试邮件，用于验证邮件发送功能是否正常。</p>
            
            <div class="details">
                <p><strong>测试详情：</strong></p>
                <p>📧 收件人：{config.admin_email}</p>
                <p>🔧 邮件服务器：{config.mail_server}:{config.mail_port}</p>
                <p>⏰ 发送时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
            </div>
            
            <p>如果您收到了这封邮件，说明邮件发送功能正常工作。</p>
        </div>
        
        <div class="footer">
            <p>此邮件由 <strong>域名监控系统</strong> 自动发送</p>
            <p>发送时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
            <p style="margin-top: 10px; font-size: 10px; color: #999;">
                此为系统自动发送的测试邮件，请勿直接回复
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        # 使用异步发送
        send_email_async(subject, config.admin_email, body)
        
        return jsonify({'success': True, 'message': '测试邮件已发送，请查看控制台输出和邮箱'})
        
    except Exception as e:
        print(f"❌ 立即测试失败: {str(e)}")
        return jsonify({'success': False, 'message': f'测试失败: {str(e)}'})

# 路由：重置域名邮件发送状态
@app.route('/reset_domain_flags/<int:domain_id>', methods=['POST'])
@login_required
def reset_domain_flags(domain_id):
    """重置域名的邮件发送标志"""
    try:
        domain = Domain.query.get_or_404(domain_id)
        
        # 验证用户权限
        if domain.user_id != session['user_id']:
            return jsonify({'success': False, 'message': '无权操作'})
        
        # 重置邮件发送状态
        domain.warning_sent = False
        domain.danger_sent = False
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'域名 {domain.name} 的邮件发送状态已重置'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置失败: {str(e)}'})

# 路由：批量重置所有域名的邮件发送状态
@app.route('/reset_all_domain_flags', methods=['POST'])
@login_required
def reset_all_domain_flags():
    """重置所有域名的邮件发送标志"""
    try:
        domains = Domain.query.filter_by(user_id=session['user_id']).all()
        
        reset_count = 0
        for domain in domains:
            if domain.warning_sent or domain.danger_sent:
                domain.warning_sent = False
                domain.danger_sent = False
                reset_count += 1
        
        if reset_count > 0:
            db.session.commit()
            return jsonify({
                'success': True, 
                'message': f'已重置 {reset_count} 个域名的邮件发送状态'
            })
        else:
            return jsonify({
                'success': True, 
                'message': '没有需要重置的域名'
            })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置失败: {str(e)}'})

def setup_scheduler():
    """设置定时任务调度器"""
    try:
        # 创建调度器
        scheduler = BackgroundScheduler()
        
        # 设置时区
        beijing_tz = pytz.timezone('Asia/Shanghai')
        
        # 添加域名检查任务 - 每天上午8:30执行
        scheduler.add_job(
            func=check_domain_expiry,
            trigger=CronTrigger(hour=8, minute=30, timezone=beijing_tz),
            id='domain_daily_check',
            name='域名到期每日检查',
            replace_existing=True
        )
        
        # 添加快速测试任务 - 每10分钟执行一次（用于测试）
        scheduler.add_job(
            func=check_domain_expiry,
            trigger=CronTrigger(minute='*/10'),  # 每10分钟
            id='domain_test_check',
            name='域名到期测试检查',
            replace_existing=True
        )
        
        # 启动调度器
        scheduler.start()
        
        # 注册关闭钩子
        atexit.register(lambda: scheduler.shutdown())
        
        print("=" * 60)
        print("🚀 定时任务调度器已启动")
        print("📅 每日检查: 上午8:30 (北京时间)")
        print("🧪 测试检查: 每10分钟一次")
        
        # 检查SMTP状态
        with app.app_context():
            config = SMTPConfig.query.first()
            if config and config.enabled:
                print(f"✅ SMTP状态: 已启用 - {config.mail_server}:{config.mail_port}")
                print(f"📧 管理员邮箱: {config.admin_email}")
            else:
                print("❌ SMTP状态: 未启用或未配置")
        
        print("=" * 60)
        
        return scheduler
        
    except Exception as e:
        print(f"❌ 调度器启动失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    from init_db import init_database

    # 初始化数据库
    if not os.path.exists('domain.db'):
        init_database()
    else:
        # 检查是否需要迁移
        try:
            with app.app_context():
                inspector = db.inspect(db.engine)
                columns = [col['name'] for col in inspector.get_columns('domain')]
                if 'needs_renewal' not in columns:
                    print("\n" + "=" * 60)
                    print("⚠️  检测到数据库需要迁移！")
                    print("=" * 60)
                    print("请先运行以下命令进行数据库迁移：")
                    print("  python migrate.py")
                    print("=" * 60)
                    print("迁移完成后，再运行 app.py 启动应用")
                    print("=" * 60 + "\n")
                    exit(1)
        except Exception as e:
            print(f"⚠️  检查数据库结构时出错: {e}")
            print("如果这是首次运行，请删除 domain.db 后重新运行")
            exit(1)
    
    # 设置定时任务
    scheduler = setup_scheduler()

    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
