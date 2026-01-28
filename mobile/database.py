# Copyright (C) [2026] [晨曦微光]
# 此软件受著作权法保护。未经明确书面许可，任何单位或个人不得复制、分发、修改或用于商业用途。
# APP名称：[晨曦智能打卡]
# 版本号：1.0.0

# database.py

import sqlite3
import os
import base64
import hashlib
from datetime import datetime


class Database:
    def __init__(self, db_name='attendance.db'):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.init_db()

    def connect(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()

    def init_db(self):
        self.connect()
        # 创建用户表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 创建打卡记录表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date DATE NOT NULL,
                check_in_time TIMESTAMP,
                check_out_time TIMESTAMP,
                status TEXT, -- 'success', 'fail', '补录'
                location TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        # 创建打卡设置表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                check_in_start TIME,
                check_in_end TIME,
                check_out_start TIME,
                check_out_end TIME,
                location_lat REAL,
                location_lon REAL,
                location_radius REAL, -- 半径，单位米
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        self.conn.commit()
        self.close()

    def _hash_password(self, password, salt=None, iterations=120000):
        salt_bytes = salt or os.urandom(16)
        derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, iterations)
        return f"pbkdf2${iterations}${base64.b64encode(salt_bytes).decode()}${base64.b64encode(derived).decode()}"

    # 用户相关操作
    def add_user(self, username, password, is_admin=0):

        self.connect()
        try:
            hashed_password = self._hash_password(password)
            self.cursor.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                                (username, hashed_password, is_admin))

            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            self.close()

    def get_user(self, username):
        self.connect()
        self.cursor.execute('SELECT * FROM users WHERE username=?', (username,))
        user = self.cursor.fetchone()
        self.close()
        return user

    # 打卡记录相关操作
    def add_attendance(self, user_id, date, check_in_time, status, location):
        self.connect()
        self.cursor.execute('''
            INSERT INTO attendance (user_id, date, check_in_time, status, location)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, date, check_in_time, status, location))
        self.conn.commit()
        self.close()

    def get_attendance_by_user(self, user_id):
        self.connect()
        self.cursor.execute('SELECT * FROM attendance WHERE user_id=? ORDER BY date DESC', (user_id,))
        records = self.cursor.fetchall()
        self.close()
        return records

    # 设置相关操作
    def update_settings(self, user_id, check_in_start, check_in_end, location_lat, location_lon, location_radius):
        self.connect()
        # 先检查是否存在
        self.cursor.execute('SELECT * FROM settings WHERE user_id=?', (user_id,))
        if self.cursor.fetchone():
            self.cursor.execute('''
                UPDATE settings SET check_in_start=?, check_in_end=?, location_lat=?, location_lon=?, location_radius=?
                WHERE user_id=?
            ''', (check_in_start, check_in_end, location_lat, location_lon, location_radius, user_id))
        else:
            self.cursor.execute('''
                INSERT INTO settings (user_id, check_in_start, check_in_end, location_lat, location_lon, location_radius)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, check_in_start, check_in_end, location_lat, location_lon, location_radius))
        self.conn.commit()
        self.close()

    def get_settings(self, user_id):
        self.connect()
        self.cursor.execute('SELECT * FROM settings WHERE user_id=?', (user_id,))
        settings = self.cursor.fetchone()
        self.close()
        return settings

    # 管理员补录
    def update_attendance_status(self, record_id, status):
        self.connect()
        self.cursor.execute('UPDATE attendance SET status=? WHERE id=?', (status, record_id))
        self.conn.commit()
        self.close()

    # 获取所有打卡记录（管理员用）
    def get_all_attendance(self):
        self.connect()
        self.cursor.execute('SELECT * FROM attendance ORDER BY date DESC')
        records = self.cursor.fetchall()
        self.close()
        return records

# 创建一个全局的数据库实例
db = Database()