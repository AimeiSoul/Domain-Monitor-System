#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移脚本
用于将老版本数据库迁移到新版本，添加缺失的字段
运行方式: python migrate.py
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
import os

# 创建Flask应用实例用于迁移
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///domain.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 定义Domain模型（仅用于迁移）
class Domain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    registrar = db.Column(db.String(255))
    registration_date = db.Column(db.DateTime)
    expiration_date = db.Column(db.DateTime, nullable=False)
    renewal_period = db.Column(db.String(50))
    renewal_price = db.Column(db.String(255))
    renewal_url = db.Column(db.String(500))
    renewal_date = db.Column(db.DateTime)
    currency = db.Column(db.String(10), default='USD')
    warning_threshold = db.Column(db.Integer, default=30)
    danger_threshold = db.Column(db.Integer, default=7)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    warning_sent = db.Column(db.Boolean, default=False)
    danger_sent = db.Column(db.Boolean, default=False)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    needs_renewal = db.Column(db.Boolean, default=True)

def migrate_database():
    """迁移数据库，添加缺失的字段"""
    with app.app_context():
        try:
            # 检查数据库文件是否存在
            if not os.path.exists('domain.db'):
                print("=" * 60)
                print("❌ 数据库文件 domain.db 不存在")
                print("=" * 60)
                print("请先运行 app.py 初始化数据库")
                return False
            
            print("=" * 60)
            print("🚀 开始数据库迁移...")
            print("=" * 60)
            
            # 检查表结构
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('domain')]
            print(f"\n📋 当前domain表的列: {columns}")
            
            migration_needed = False
            
            # 添加缺失的字段
            if 'warning_sent' not in columns:
                print("\n➕ 添加 warning_sent 字段...")
                db.session.execute(text('ALTER TABLE domain ADD COLUMN warning_sent BOOLEAN DEFAULT FALSE'))
                db.session.commit()
                print("✅ warning_sent 字段添加成功")
                migration_needed = True
            
            if 'danger_sent' not in columns:
                print("\n➕ 添加 danger_sent 字段...")
                db.session.execute(text('ALTER TABLE domain ADD COLUMN danger_sent BOOLEAN DEFAULT FALSE'))
                db.session.commit()
                print("✅ danger_sent 字段添加成功")
                migration_needed = True
                
            if 'last_checked' not in columns:
                print("\n➕ 添加 last_checked 字段...")
                db.session.execute(text('ALTER TABLE domain ADD COLUMN last_checked DATETIME'))
                db.session.commit()
                print("✅ last_checked 字段添加成功")
                migration_needed = True
            
            if 'needs_renewal' not in columns:
                print("\n➕ 添加 needs_renewal 字段...")
                db.session.execute(text('ALTER TABLE domain ADD COLUMN needs_renewal BOOLEAN DEFAULT TRUE'))
                db.session.commit()
                print("✅ needs_renewal 字段添加成功")
                migration_needed = True
            
            if not migration_needed:
                print("\n✅ 数据库已是最新版本，无需迁移")
                return True
            
            # 为现有域名设置renewal_date
            domains = Domain.query.all()
            renewal_date_count = 0
            for domain in domains:
                if not domain.renewal_date:
                    # 如果renewal_date为空，设置为registration_date或当前日期
                    domain.renewal_date = domain.registration_date if domain.registration_date else datetime.utcnow()
                    renewal_date_count += 1
                    print(f"📝 设置域名 {domain.name} 的renewal_date为: {domain.renewal_date}")
            
            if renewal_date_count > 0:
                db.session.commit()
                print(f"\n✅ 已为 {renewal_date_count} 个域名设置 renewal_date")
            
            # 验证迁移结果
            inspector = db.inspect(db.engine)
            new_columns = [col['name'] for col in inspector.get_columns('domain')]
            print(f"\n📋 迁移后domain表的列: {new_columns}")
            
            print("\n" + "=" * 60)
            print("✅ 数据库迁移完成!")
            print("=" * 60)
            return True
            
        except Exception as e:
            print("\n" + "=" * 60)
            print(f"❌ 数据库迁移失败: {e}")
            print("=" * 60)
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("📦 数据库迁移工具")
    print("=" * 60)
    print("此脚本将为老版本数据库添加缺失的字段")
    print("迁移完成后，请运行 app.py 启动应用")
    print("=" * 60 + "\n")
    
    success = migrate_database()
    
    if success:
        print("\n✅ 迁移成功！现在可以运行 app.py 启动应用了")
    else:
        print("\n❌ 迁移失败，请检查错误信息")
    
    print("\n按 Enter 键退出...")
    try:
        input()
    except:
        pass

