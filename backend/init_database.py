"""
数据库初始化和示例数据填充脚本
"""
from app import create_app, db
from app.utils.database import seed_sample_data

if __name__ == "__main__":
    app = create_app()
    
    with app.app_context():
        # 创建所有数据库表
        print("正在创建数据库表...")
        db.create_all()
        print("✅ 数据库表创建完成！")
        
        # 填充示例数据
        print("\n正在填充示例数据...")
        seed_sample_data(app)
        print("✅ 示例数据填充完成！")
        
        print("\n🎉 数据库初始化全部完成！")
