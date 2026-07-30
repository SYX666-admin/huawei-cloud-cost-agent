from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Enum, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'app.db')}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,
    max_overflow=20,
    pool_timeout=60
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Bill(Base):
    __tablename__ = "bills"
    
    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(String(64), unique=True, nullable=False, comment="账单唯一标识")
    file_name = Column(String(255), nullable=False, comment="上传的文件名")
    upload_time = Column(DateTime, default=datetime.now, comment="上传时间")
    record_count = Column(Integer, default=0, comment="解析到的记录数")
    total_amount = Column(Numeric(12, 2), default=0.0, comment="总费用")
    status = Column(Enum('pending', 'completed', 'failed'), default='pending', comment="处理状态")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    def to_dict(self):
        return {
            "id": self.id,
            "bill_id": self.bill_id,
            "file_name": self.file_name,
            "upload_time": self.upload_time.isoformat() if self.upload_time else None,
            "record_count": self.record_count,
            "total_amount": float(self.total_amount) if self.total_amount else 0.0,
            "status": self.status,
            "error_message": self.error_message
        }

class Resource(Base):
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(String(64), nullable=False, comment="关联的账单ID")
    resource_id = Column(String(128), nullable=False, comment="资源唯一标识")
    product_type = Column(String(64), nullable=False, comment="产品类型（ECS/EIP/EVS/VPC等）")
    product_name = Column(String(255), nullable=True, comment="产品名称（原始名称）")
    spec = Column(String(128), nullable=True, comment="实例规格")
    region = Column(String(64), nullable=True, comment="区域")
    bill_date = Column(String(10), nullable=True, comment="账单日期")
    cost = Column(Numeric(12, 2), default=0.0, comment="费用")
    usage = Column(Float, default=0.0, comment="用量")
    usage_unit = Column(String(32), nullable=True, comment="用量单位")
    billing_mode = Column(Enum('on_demand', 'monthly', 'yearly'), nullable=True, comment="计费模式")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    def to_dict(self):
        return {
            "id": self.id,
            "bill_id": self.bill_id,
            "resource_id": self.resource_id,
            "product_type": self.product_type,
            "product_name": self.product_name,
            "spec": self.spec,
            "region": self.region,
            "bill_date": self.bill_date,
            "cost": float(self.cost) if self.cost else 0.0,
            "usage": float(self.usage) if self.usage else 0.0,
            "usage_unit": self.usage_unit,
            "billing_mode": self.billing_mode,
            "create_time": self.create_time.isoformat() if self.create_time else None
        }

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(String(64), nullable=False, comment="关联的账单ID")
    resource_id = Column(String(128), nullable=False, comment="资源ID")
    product_type = Column(String(64), nullable=False, comment="产品类型")
    issue_description = Column(Text, nullable=False, comment="问题描述")
    recommendation = Column(Text, nullable=False, comment="操作建议")
    estimated_savings = Column(Numeric(12, 2), default=0.0, comment="预计节省金额")
    billing_mode = Column(Enum('on_demand', 'monthly', 'yearly'), nullable=True, comment="计费模式")
    risk_level = Column(Enum('low', 'medium', 'high'), default='low', comment="风险等级")
    risk_warning = Column(Text, nullable=True, comment="风险提示文字")
    category = Column(Enum('release', 'downsize', 'rightsize', 'other'), nullable=True, comment="建议类型")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    def to_dict(self):
        return {
            "id": self.id,
            "bill_id": self.bill_id,
            "resource_id": self.resource_id,
            "product_type": self.product_type,
            "issue_description": self.issue_description,
            "recommendation": self.recommendation,
            "estimated_savings": float(self.estimated_savings) if self.estimated_savings else 0.0,
            "billing_mode": self.billing_mode,
            "risk_level": self.risk_level,
            "risk_warning": self.risk_warning,
            "category": self.category,
            "create_time": self.create_time.isoformat() if self.create_time else None
        }

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()