from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    # --- CÁC CỘT MỚI THÊM CHO TRANG PROFILE ---
    full_name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    avatar = db.Column(db.String(200), nullable=True) # Lưu tên file ảnh
    last_password_change = db.Column(db.DateTime, nullable=True) # Lưu ngày đổi pass
    
    # [THÊM MỚI] Cột phân loại tài khoản: FREE, PRO, PREMIUM
    tier = db.Column(db.String(20), default="FREE")
    
    stations = db.relationship('Station', backref='owner', lazy=True)


class Station(db.Model):
    __tablename__ = 'stations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    
    p_max = db.Column(db.Float, default=100.0)
    area = db.Column(db.Float, default=1.0)
    elec_price = db.Column(db.Float, default=3015.0)

    devices = db.relationship('Device', backref='station', lazy=True)

class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    
    mac_address = db.Column(db.String(50), unique=True, nullable=False) 
    status = db.Column(db.String(20), default="active")
    #Thêm mới 
    mode = db.Column(db.String(20), default="MANUAL") # MANUAL, AUTO, SMART_ECO
    is_auto_running = db.Column(db.Boolean, default=False)
    last_auto_start = db.Column(db.Float, default=0.0)

    sensor_data = db.relationship('SensorData', backref='device', lazy=True)

class SensorData(db.Model):
    __tablename__ = 'sensor_data'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Các thông số cơ bản
    temp_panel = db.Column(db.Float)
    temp_env = db.Column(db.Float)
    humidity = db.Column(db.Float)
    lux = db.Column(db.Float)
    power = db.Column(db.Float)
    pump_status = db.Column(db.Integer)
    
    # Các thông số nâng cao (giống sensor_history cũ của bạn)
    current = db.Column(db.Float, nullable=True)
    voltage = db.Column(db.Float, nullable=True)
    health_score = db.Column(db.Float, nullable=True)
    profit = db.Column(db.Float, nullable=True)
    delta_e = db.Column(db.Float, nullable=True)

# Bảng thay thế cho bảng `history` cũ của bạn
class CommandHistory(db.Model):
    __tablename__ = 'command_history'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(50))
    command = db.Column(db.String(50))
    action_type = db.Column(db.String(50))
    source = db.Column(db.String(50))