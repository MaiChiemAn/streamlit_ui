import sqlite3
import random

def create_and_populate_db():
    # 1. Kết nối đến database (nếu chưa có sẽ tự tạo)
    conn = sqlite3.connect('your_database.db')
    cursor = conn.cursor()

    # 2. Tạo 10 bảng (mỗi bảng chỉ 1 hàng, id cố định để ghi đè như conversation id)
    for i in range(1, 11):
        table_name = f'Team_{i}'
        
        # Xóa bảng cũ nếu đã tồn tại để tránh lỗi trùng lặp khi chạy lại
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        # Tạo bảng mới với id cố định và 1 cột value
        cursor.execute(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, value INTEGER)")
        
        # Chèn / ghi đè giá trị mẫu duy nhất với id=1
        sample_value = random.randint(10, 100)
        cursor.execute(f"INSERT OR REPLACE INTO {table_name} (id, value) VALUES (1, ?)", (sample_value,))
        
        print(f"Đã tạo {table_name} với giá trị: {sample_value}")

    # 3. Lưu thay đổi và đóng kết nối
    conn.commit()
    conn.close()
    print("\nDatabase 'your_database.db' đã được tạo thành công!")

if __name__ == "__main__":
    create_and_populate_db()
