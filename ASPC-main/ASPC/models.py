from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True) # Đánh index để login siêu nhanh
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    avatar = db.Column(db.String(200), nullable=True) 
    last_password_change = db.Column(db.DateTime, nullable=True) 
    
    tier = db.Column(db.String(20), default="FREE")
    
    # Thêm cascade để nếu xóa User thì tự động xóa sạch trạm của họ (không để lại rác)
    stations = db.relationship('Station', backref='owner', lazy=True, cascade="all, delete-orphan")


class Station(db.Model):
    __tablename__ = 'stations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    
    p_max = db.Column(db.Float, default=100.0)
    area = db.Column(db.Float, default=1.0)
    elec_price = db.Column(db.Float, default=3015.0)

    devices = db.relationship('Device', backref='station', lazy=True, cascade="all, delete-orphan")


class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False, index=True)
    
    mac_address = db.Column(db.String(50), unique=True, nullable=False, index=True) 
    status = db.Column(db.String(20), default="active")
    
    mode = db.Column(db.String(20), default="MANUAL") 
    is_auto_running = db.Column(db.Boolean, default=False)
    last_auto_start = db.Column(db.Float, default=0.0)

    sensor_data = db.relationship('SensorData', backref='device', lazy=True, cascade="all, delete-orphan")


class SensorData(db.Model):
    __tablename__ = 'sensor_data'
    id = db.Column(db.Integer, primary_key=True)
    # INDEX TỐI QUAN TRỌNG: Giúp load biểu đồ IoT triệu dòng chỉ mất 0.1 giây!
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    temp_panel = db.Column(db.Float)
    temp_env = db.Column(db.Float)
    humidity = db.Column(db.Float)
    lux = db.Column(db.Float)
    power = db.Column(db.Float)
    pump_status = db.Column(db.Integer)
    
    current = db.Column(db.Float, nullable=True)
    voltage = db.Column(db.Float, nullable=True)
    health_score = db.Column(db.Float, nullable=True)
    profit = db.Column(db.Float, nullable=True)
    delta_e = db.Column(db.Float, nullable=True)


class CommandHistory(db.Model):
    __tablename__ = 'command_history'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True) # Thêm index
    user_id = db.Column(db.String(50), index=True) # Thêm index
    command = db.Column(db.String(50))
    action_type = db.Column(db.String(50))
    source = db.Column(db.String(50))


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False, index=True) # Thêm index
    message = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(20), default='info') 
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True) # Thêm index