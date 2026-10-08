# ==============================================================================
# FaceID Biometric Recognition & Role-Based Access Control System
# Copyright (c) 2026 Saitharun Cherukuri. All rights reserved.
# Author: Saitharun Cherukuri
# ==============================================================================

import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime
from database import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), unique=True, index=True, nullable=False)  # Badge ID or Employee ID
    full_name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True)
    department = Column(String(64), nullable=True)
    role_title = Column(String(64), nullable=True)
    photo_path = Column(String(256), nullable=False)  # Path to saved cropped face image
    embedding_json = Column(Text, nullable=False)     # 128-dimensional float list serialized as JSON
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_embedding(self):
        return json.loads(self.embedding_json)

    def set_embedding(self, emb_list):
        self.embedding_json = json.dumps(emb_list)

    def to_dict(self, include_embedding=False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department,
            "role_title": self.role_title,
            "photo_path": self.photo_path,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_embedding:
            data["embedding"] = self.get_embedding()
        return data


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=True)       # Matched user's user_id or None
    user_name = Column(String(128), nullable=True)    # Matched user's name
    status = Column(String(32), nullable=False)       # 'VERIFIED', 'UNRECOGNIZED', 'NO_FACE'
    accuracy_percent = Column(Float, nullable=False)  # 0.0 to 100.0%
    similarity_score = Column(Float, nullable=False)  # raw cosine score
    snapshot_path = Column(String(256), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "status": self.status,
            "accuracy_percent": round(self.accuracy_percent, 2),
            "similarity_score": round(self.similarity_score, 4),
            "snapshot_path": self.snapshot_path,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None,
        }


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True)
    value = Column(String(256), nullable=False)
