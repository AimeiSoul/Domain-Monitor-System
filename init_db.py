from app import app, db, User, init_smtp_config
from werkzeug.security import generate_password_hash

def init_database():
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
            print("默认用户已创建")

        # 初始化SMTP配置
        init_smtp_config()
        print("数据库初始化完成！")

if __name__ == '__main__':
    init_database()
