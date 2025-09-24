# Domain Monitor System

一个基于 **Flask + SQLite** 的域名监控与管理系统，支持域名到期监控、管理员后台管理以及 SMTP 邮件告警。

---

## ✨ 功能特性

- **主页展示**  
  展示已添加的域名及其注册商、到期时间等基础信息。

- **管理员登录**  
  提供后台登录入口，确保管理操作安全。

- **域名管理**  
  - 新增域名  
  - 删除域名  
  - 编辑域名信息  
  - 快速跳转至续费链接  

- **邮件告警**  
  支持配置 SMTP，当域名距离到期小于阈值时，自动发送预警邮件。

---

## 📂 项目结构

```
domain_monitor_system/
├─ app.py               # Flask 主程序
├─ init_db.py           # 初始化数据库脚本
├─ requirements.txt     # 所需依赖
├─ instance/
│  └─ domain.db         # SQLite 数据库 (首次运行自动生成)
├─ templates/
│  ├─ index.html        # 展示页面
│  ├─ login.html        # 登录页面
│  ├─ dashboard.html    # 仪表盘页面
│  └─ smtp_config.html  # SMTP 配置页面
├─ static/
│  ├─ css/
│  │  └─ style.css      # 样式文件
│  ├─ img/              # 图片均可替换，保留文件名
│  │  ├─ logo.svg 
│  │  ├─ pc.jpg
│  │  └─ pe.jpg
│  ├─ js/
│  │  ├─ dashboard.js   # 仪表盘脚本
│  │  └─ script.js      # 全局脚本
```

---

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/yourusername/domain-monitor-system.git
cd domain-monitor-system
````

### 2. 修改关键内容

在`app.py`中修改`SECRET_KEY`值和默认`port`值（按需）
```python
app.config['SECRET_KEY'] = 'your-secret-key-here'

app.run(host="0.0.0.0", port=8000, debug=True)
```

在`init_db.py`中，可以修改`password`,修改为你想要的密码，因为自用为主，没有预留在网页上修改的功能
```python
password=generate_password_hash('admin123')
```

### 3. 创建虚拟环境并安装依赖

```bash
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
python init_db.py
```

### 5. 运行项目

```bash
python app.py
```

访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)。

推荐结合 **Nginx 反向代理** 实现**HTTPS** 访问。

---

## ⚙️ SMTP 配置

在 **后台管理 → SMTP 设置** 中填写：

* SMTP 服务器地址
* SMTP端口（TLS加密）
* SMTp用户名
* 授权码/密码
* 收件人邮箱
* 接收邮箱

配置完成后，系统会根据域名到期时间自动发送提醒邮件。

---

## 🖼️ 页面示例

* 首页展示
<img width="1920" height="910" alt="image" src="https://github.com/user-attachments/assets/97079f3b-b2ec-4a51-b001-491c742f8cc0" />

* Login页面
<img width="1920" height="911" alt="image" src="https://github.com/user-attachments/assets/7a4a7edb-e51b-4c56-9470-9d8263e8c8fe" />

* 管理员页面
<img width="1920" height="910" alt="image" src="https://github.com/user-attachments/assets/73edee6e-19de-4e28-8448-857a1af08f5c" />

* SMTP设置
<img width="1920" height="911" alt="image" src="https://github.com/user-attachments/assets/db2c909d-f781-493d-94ca-4b559dbcc365" />

---

##  📷 Demo

**演示站点**：https://domain.aimeisoul.serv00.net

（demo用户名：admin）
（demo密码：YKiI-Jx*{5）

---

## 📜 License

本项目采用 MIT License。
