import asyncio
from config import settings
from database.mongo import MongoDB, get_db

async def reset_database():
    print("⏳ Đang kết nối tới MongoDB...")
    await MongoDB.connect(url=settings.MONGODB_URL, db_name="medical_ai")
    db = get_db()
    
    print("🗑️ Đang xoá toàn bộ dữ liệu Users...")
    users_result = await db["users"].delete_many({})
    print(f"✅ Đã xoá {users_result.deleted_count} users cũ.")
    
    print("🗑️ Đang xoá toàn bộ dữ liệu Chat Sessions...")
    sessions_result = await db["sessions"].delete_many({})
    print(f"✅ Đã xoá {sessions_result.deleted_count} lịch sử hội thoại.")

    await MongoDB.close()
    print("\n🎉 RESET HOÀN TẤT! Toàn bộ Database đã trở lại như mới.")
    print("Bây giờ bạn có thể F5 lại trình duyệt, dùng bất kỳ tài khoản nào đăng nhập cũng sẽ được tính là NEW USER và nhận được Mail Chào Mừng!")

if __name__ == "__main__":
    asyncio.run(reset_database())
