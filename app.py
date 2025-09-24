from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import math
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart  # 添加这行导入
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///domain.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    currency = db.Column(db.String(10), default='USD')
    warning_threshold = db.Column(db.Integer, default=30)
    danger_threshold = db.Column(db.Integer, default=7)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<Domain {self.name}>'
    
    def days_remaining(self):
        if self.expiration_date:
            remaining = (self.expiration_date - datetime.now()).days
            return max(0, remaining)
        return 0
    
    def status(self):
        days = self.days_remaining()
        if days < self.danger_threshold:
            return 'danger'
        elif days < self.warning_threshold:
            return 'warning'
        else:
            return 'success'
    
    def progress_percentage(self):
        if self.registration_date and self.expiration_date:
            total_days = (self.expiration_date - self.registration_date).days
            remaining_days = self.days_remaining()
            if total_days > 0:
                return round((remaining_days / total_days) * 100, 1)
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

# 路由：SMTP配置页面
@app.route('/smtp_config')
def smtp_config():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 只有管理员可以访问SMTP配置
    if session.get('username') != 'admin':
        flash('只有管理员可以访问SMTP配置', 'danger')
        return redirect(url_for('dashboard'))
    
    config = SMTPConfig.query.first()
    return render_template('smtp_config.html', config=config)

# 路由：更新SMTP配置
@app.route('/update_smtp_config', methods=['POST'])
def update_smtp_config():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
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
        
        # 更新应用配置
        app.config['MAIL_SERVER'] = config.mail_server
        app.config['MAIL_PORT'] = config.mail_port
        app.config['MAIL_USE_TLS'] = config.mail_use_tls
        app.config['MAIL_USERNAME'] = config.mail_username
        app.config['MAIL_PASSWORD'] = config.mail_password
        app.config['MAIL_DEFAULT_SENDER'] = config.mail_default_sender
        app.config['ADMIN_EMAIL'] = config.admin_email
        
        return jsonify({'success': True, 'message': 'SMTP配置更新成功！'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})

# 路由：测试SMTP配置
@app.route('/test_smtp_config', methods=['POST'])
def test_smtp_config():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    # 只有管理员可以测试SMTP配置
    if session.get('username') != 'admin':
        return jsonify({'success': False, 'message': '只有管理员可以测试SMTP配置'})
    
    try:
        config = SMTPConfig.query.first()
        if not config:
            return jsonify({'success': False, 'message': '请先配置SMTP设置'})
        
        # 测试邮件发送
        subject = "域名监控系统 - SMTP配置测试"
        body = """
        <html>
        <body>
            <h2>SMTP配置测试</h2>
            <p>这是一封测试邮件，用于验证域名监控系统的SMTP配置是否正确。</p>
            <p>如果您收到了这封邮件，说明SMTP配置已经正确设置。</p>
            <hr>
            <p><small>此邮件由域名监控系统自动发送，请勿回复。</small></p>
        </body>
        </html>
        """
        
        # 使用新的邮件发送函数（稍后定义）
        result = send_test_email(config, subject, config.admin_email, body)
        
        if result:
            return jsonify({'success': True, 'message': '测试邮件已发送，请检查您的邮箱。'})
        else:
            return jsonify({'success': False, 'message': '发送测试邮件失败，请检查SMTP配置。'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'测试失败: {str(e)}'})


# 邮件发送函数
def send_email_async(subject, recipient, body):
    """异步发送邮件"""
    def send_email():
        try:
            config = SMTPConfig.query.first()
            if not config or not config.enabled:
                print("SMTP未启用或未配置")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = config.mail_default_sender
            msg['To'] = recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html'))
            
            # 根据端口选择连接方式
            if config.mail_port == 465:
                # 端口465使用SSL连接
                server = smtplib.SMTP_SSL(config.mail_server, config.mail_port)
                # SSL连接不需要调用starttls()
            else:
                # 其他端口使用普通连接，可能需要TLS
                server = smtplib.SMTP(config.mail_server, config.mail_port)
                if config.mail_use_tls:
                    server.starttls()
            
            server.login(config.mail_username, config.mail_password)
            server.send_message(msg)
            server.quit()
            print(f"邮件已发送至 {recipient}")
            return True
        except Exception as e:
            print(f"发送邮件失败: {str(e)}")
            return False
    
    # 在新线程中发送邮件，避免阻塞主程序
    thread = Thread(target=send_email)
    thread.start()

# 测试邮件发送函数
def send_test_email(config, subject, recipient, body):
    """同步发送测试邮件"""
    try:
        msg = MIMEMultipart()
        msg['From'] = config.mail_default_sender
        msg['To'] = recipient
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        # 根据端口选择连接方式
        if config.mail_port == 465:
            # 端口465使用SSL连接
            server = smtplib.SMTP_SSL(config.mail_server, config.mail_port)
            # SSL连接不需要调用starttls()
        else:
            # 其他端口使用普通连接，可能需要TLS
            server = smtplib.SMTP(config.mail_server, config.mail_port)
            if config.mail_use_tls:
                server.starttls()
        
        server.login(config.mail_username, config.mail_password)
        server.send_message(msg)
        server.quit()
        print(f"测试邮件已发送至 {recipient}")
        return True
    except Exception as e:
        print(f"发送测试邮件失败: {str(e)}")
        return False

# 域名检查函数
def check_domain_expiry():
    """检查所有域名的到期状态并发送提醒"""
    with app.app_context():
        # 检查SMTP是否启用
        config = SMTPConfig.query.first()
        if not config or not config.enabled:
            print("SMTP未启用，跳过域名检查")
            return
            
        domains = Domain.query.all()
        for domain in domains:
            days_remaining = domain.days_remaining()
            
            # 检查是否需要发送提醒
            if days_remaining <= domain.danger_threshold and not domain.danger_sent:
                # 发送危险级别提醒
                subject = f"【紧急】域名 {domain.name} 即将过期！"
                body = f"""
                <html>
                <body>
                    <h2>域名过期提醒</h2>
                    <p>您的域名 <strong>{domain.name}</strong> 即将在 <strong>{days_remaining}</strong> 天后过期！</p>
                    <p>到期日期: {domain.expiration_date.strftime('%Y-%m-%d')}</p>
                    <p>请及时续费以避免服务中断。</p>
                    <p>续费链接: <a href="{domain.renewal_url or '#'}">{domain.renewal_url or '暂无'}</a></p>
                    <hr>
                    <p><small>此邮件由域名监控系统自动发送，请勿回复。</small></p>
                </body>
                </html>
                """
                send_email_async(subject, config.admin_email, body)
                
                # 标记已发送提醒
                domain.danger_sent = True
                db.session.commit()
                
            elif days_remaining <= domain.warning_threshold and not domain.warning_sent:
                # 发送警告级别提醒
                subject = f"【提醒】域名 {domain.name} 即将过期"
                body = f"""
                <html>
                <body>
                    <h2>域名过期提醒</h2>
                    <p>您的域名 <strong>{domain.name}</strong> 将在 <strong>{days_remaining}</strong> 天后过期。</p>
                    <p>到期日期: {domain.expiration_date.strftime('%Y-%m-%d')}</p>
                    <p>请考虑及时续费。</p>
                    <p>续费链接: <a href="{domain.renewal_url or '#'}">{domain.renewal_url or '暂无'}</a></p>
                    <hr>
                    <p><small>此邮件由域名监控系统自动发送，请勿回复。</small></p>
                </body>
                </html>
                """
                send_email_async(subject, config.admin_email, body)
                
                # 标记已发送提醒
                domain.warning_sent = True
                db.session.commit()

# 初始化数据库
def init_db():
    with app.app_context():
        db.create_all()
        # 创建默认用户（如果没有的话）
        if not User.query.filter_by(username='admin').first():
            default_user = User(
                username='admin', 
                password=generate_password_hash('admin123')
            )
            db.session.add(default_user)
            db.session.commit()
            print("默认用户已创建: admin/admin123")
        
        # 初始化SMTP配置
        init_smtp_config()

# 路由：首页
@app.route('/')
def index():
    domains = Domain.query.all()
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
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    domains = Domain.query.filter_by(user_id=session['user_id']).all()
    return render_template('dashboard.html', domains=domains, now=datetime.now())

# 路由：添加域名
@app.route('/add_domain', methods=['POST'])
def add_domain():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    try:
        # 获取表单数据
        name = request.form.get('name')
        registrar = request.form.get('registrar')
        registration_date = datetime.strptime(request.form.get('registration_date'), '%Y-%m-%d')
        expiration_date = datetime.strptime(request.form.get('expiration_date'), '%Y-%m-%d')
        renewal_period = request.form.get('renewal_period')
        renewal_price = request.form.get('renewal_price')
        renewal_url = request.form.get('renewal_url')
        currency = request.form.get('currency', 'USD')

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
            user_id=session['user_id']
        )
        
        db.session.add(new_domain)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '域名添加成功！'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})

# 路由：更新域名
@app.route('/update_domain/<int:domain_id>', methods=['POST'])
def update_domain(domain_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    try:
        domain = Domain.query.get_or_404(domain_id)
        
        # 验证用户权限
        if domain.user_id != session['user_id']:
            return jsonify({'success': False, 'message': '无权操作'})
        
        # 更新域名信息
        domain.name = request.form.get('name')
        domain.registrar = request.form.get('registrar')
        domain.registration_date = datetime.strptime(request.form.get('registration_date'), '%Y-%m-%d')
        domain.expiration_date = datetime.strptime(request.form.get('expiration_date'), '%Y-%m-%d')
        domain.renewal_period = request.form.get('renewal_period')
        domain.renewal_price = request.form.get('renewal_price')
        domain.renewal_url = request.form.get('renewal_url')
        domain.currency = request.form.get('currency', 'USD')
        domain.warning_threshold = int(request.form.get('warning_threshold', 30))
        domain.danger_threshold = int(request.form.get('danger_threshold', 7))
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '域名更新成功！'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})

# 路由：删除域名
@app.route('/delete_domain/<int:domain_id>', methods=['POST'])
def delete_domain(domain_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
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
def domain_data(domain_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
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
                'danger_threshold': domain.danger_threshold
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取数据失败: {str(e)}'})

if __name__ == '__main__':
    # 初始化数据库
    if not os.path.exists('domain.db'):
        init_db()
    
    app.run(host="0.0.0.0", port=8000, debug=True)
