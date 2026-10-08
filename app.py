# ==============================================================================
# FaceID Biometric Recognition & Role-Based Access Control System
# Copyright (c) 2026 Saitharun Cherukuri. All rights reserved.
# Author: Saitharun Cherukuri
# ==============================================================================

import os
import csv
import io
import time
from datetime import datetime, date
from typing import Optional, List
from pathlib import Path

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    Request,
    Response,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import cv2
import numpy as np

from config import (
    BASE_DIR,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_COSINE_THRESHOLD,
    UPLOAD_DIR_FACES,
    UPLOAD_DIR_SNAPSHOTS,
)
from database import engine, Base, get_db, SessionLocal
from models import Admin, User, ScanLog, SystemSetting
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_admin,
    get_token_from_request,
)
from face_engine import face_engine

# Initialize database schema
Base.metadata.create_all(bind=engine)

# Initialize application
app = FastAPI(title="Facial Recognition & Access Management System", version="2.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# Database Initialization: Seed default admin and settings if not present
def initialize_system():
    db = SessionLocal()
    try:
        # Check default admin
        admin_count = db.query(Admin).count()
        if admin_count == 0:
            default_admin = Admin(
                username=DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            )
            db.add(default_admin)
            print(f"[Init] Created default admin account: '{DEFAULT_ADMIN_USERNAME}'")

        # Check default settings
        thresh_setting = db.query(SystemSetting).filter(SystemSetting.key == "cosine_threshold").first()
        if not thresh_setting:
            db.add(SystemSetting(key="cosine_threshold", value=str(DEFAULT_COSINE_THRESHOLD)))

        db.commit()
    finally:
        db.close()


initialize_system()


def get_system_threshold(db: Session) -> float:
    """Helper to fetch currently configured recognition threshold."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == "cosine_threshold").first()
    if setting:
        try:
            return float(setting.value)
        except ValueError:
            pass
    return DEFAULT_COSINE_THRESHOLD


# Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class SettingUpdateRequest(BaseModel):
    cosine_threshold: float


class FaceScanRequest(BaseModel):
    image: str  # Base64 string from client webcam


class UserUpdateRequest(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role_title: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


# ==========================================
# PUBLIC / KIOSK ENDPOINTS (ZERO DATA LEAK)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def kiosk_terminal_page(request: Request):
    """
    Kiosk / Scanner Terminal: The public camera scanning interface.
    No registered users data is sent or available to this view.
    """
    return templates.TemplateResponse(request=request, name="kiosk.html", context={})


@app.get("/scan", response_class=HTMLResponse)
async def kiosk_scan_redirect(request: Request):
    return templates.TemplateResponse(request=request, name="kiosk.html", context={})


@app.post("/api/scan-face")
async def scan_face_endpoint(scan_req: FaceScanRequest, db: Session = Depends(get_db)):
    """
    Public face scanning endpoint for the biometric camera terminal.
    Evaluates the camera frame against registered embeddings.
    If verified, returns ONLY the recognized user's verified details.
    Does NOT expose other users or database records.
    """
    threshold = get_system_threshold(db)

    # Fetch active registered users from database (only embeddings & metadata needed for matching)
    active_users = db.query(User).filter(User.is_active == True).all()
    user_candidates = []
    for u in active_users:
        try:
            user_candidates.append({
                "id": u.id,
                "user_id": u.user_id,
                "full_name": u.full_name,
                "email": u.email,
                "phone": u.phone,
                "department": u.department,
                "role_title": u.role_title,
                "photo_path": u.photo_path,
                "embedding": u.get_embedding()
            })
        except Exception:
            continue

    # Execute biometric identification
    result = face_engine.identify_face(scan_req.image, user_candidates, threshold=threshold)

    # Save live snapshot for audit trail
    snapshot_filename = None
    try:
        img_np = face_engine.decode_image(scan_req.image)
        if img_np is not None:
            ts = int(time.time() * 1000)
            snapshot_filename = f"snap_{ts}.jpg"
            save_path = UPLOAD_DIR_SNAPSHOTS / snapshot_filename
            # Resize snapshot to save space
            h, w = img_np.shape[:2]
            scale = min(1.0, 480 / max(h, w))
            if scale < 1.0:
                img_np = cv2.resize(img_np, (int(w * scale), int(h * scale)))
            cv2.imwrite(str(save_path), img_np)
    except Exception as e:
        print(f"[Audit] Failed to save snapshot: {e}")

    # Record scan log in database
    matched_user = result.get("user")
    log_entry = ScanLog(
        user_id=matched_user["user_id"] if matched_user else None,
        user_name=matched_user["full_name"] if matched_user else None,
        status=result["status"],
        accuracy_percent=result["accuracy_percent"],
        similarity_score=result["similarity_score"],
        snapshot_path=f"/static/uploads/snapshots/{snapshot_filename}" if snapshot_filename else None,
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()

    # Add snapshot path to response
    result["snapshot_url"] = log_entry.snapshot_path
    result["timestamp"] = log_entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    return JSONResponse(content=result)


# ==========================================
# ADMIN AUTHENTICATION ENDPOINTS
# ==========================================

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin Login UI."""
    return templates.TemplateResponse(request=request, name="login.html", context={})


@app.post("/api/admin/login")
async def admin_login(creds: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate Admin and issue JWT token."""
    admin = db.query(Admin).filter(Admin.username == creds.username).first()
    if not admin or not verify_password(creds.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    token = create_access_token(data={"sub": admin.username})

    # Set cookie for web browsing
    response.set_cookie(
        key="faceid_token",
        value=token,
        httponly=False,
        max_age=3600 * 24,
        path="/",
        samesite="lax",
    )

    return {"access_token": token, "token_type": "bearer", "username": admin.username}


@app.get("/admin/logout")
async def admin_logout(response: Response):
    """Log out admin and clear session cookie."""
    resp = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(key="faceid_token", path="/")
    return resp


# ==========================================
# ADMIN PORTAL PAGES (RESTRICTED)
# ==========================================

def admin_page_guard(request: Request, db: Session) -> Admin:
    """Helper to protect HTML admin pages."""
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        from jose import jwt
        from config import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        admin = db.query(Admin).filter(Admin.username == username).first()
        if not admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return admin
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request, db: Session = Depends(get_db)):
    """Admin Dashboard Page."""
    try:
        admin = admin_page_guard(request, db)
    except HTTPException:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    threshold = get_system_threshold(db)
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={"admin": admin, "threshold": threshold}
    )


@app.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs_page(request: Request, db: Session = Depends(get_db)):
    """Admin Scan Logs & Attendance Page."""
    try:
        admin = admin_page_guard(request, db)
    except HTTPException:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="admin_logs.html",
        context={"admin": admin}
    )


# ==========================================
# ADMIN SECURE APIS (ONLY ADMIN CAN ACCESS)
# ==========================================

@app.get("/api/admin/stats")
async def get_admin_stats(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Return overview metrics for admin dashboard."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()

    today_start = datetime.combine(date.today(), datetime.min.time())
    total_scans_today = db.query(ScanLog).filter(ScanLog.timestamp >= today_start).count()
    verified_scans_today = db.query(ScanLog).filter(
        ScanLog.timestamp >= today_start,
        ScanLog.status == "VERIFIED"
    ).count()

    # Calculate average accuracy of verified scans today
    avg_accuracy_row = db.query(func.avg(ScanLog.accuracy_percent)).filter(
        ScanLog.timestamp >= today_start,
        ScanLog.status == "VERIFIED"
    ).scalar()
    avg_accuracy = round(float(avg_accuracy_row), 1) if avg_accuracy_row else 0.0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "scans_today": total_scans_today,
        "verified_today": verified_scans_today,
        "avg_accuracy_today": avg_accuracy,
    }


@app.get("/api/admin/users")
async def get_all_users(
    search: Optional[str] = None,
    department: Optional[str] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    STRICTLY ADMIN ONLY: Fetch all registered users.
    Embeddings are excluded from regular listing for performance and security.
    """
    query = db.query(User)
    if search:
        s = f"%{search}%"
        query = query.filter((User.full_name.ilike(s)) | (User.user_id.ilike(s)) | (User.email.ilike(s)))
    if department:
        query = query.filter(User.department == department)

    users = query.order_by(desc(User.created_at)).all()
    return [u.to_dict(include_embedding=False) for u in users]


@app.get("/api/admin/users/{user_id}")
async def get_user_by_id(
    user_id: str,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Get details of a single user."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict(include_embedding=False)


@app.post("/api/admin/users")
async def register_new_user(
    user_id: str = Form(...),
    full_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    role_title: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    face_image_base64: Optional[str] = Form(None),
    face_image_file: Optional[UploadFile] = File(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    STRICTLY ADMIN ONLY: Register a new user with face photo and biometric embedding.
    Accepts either webcam base64 capture or uploaded image file.
    """
    # Check if user_id already exists
    existing = db.query(User).filter(User.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"User ID '{user_id}' is already registered.")

    # Get image data
    image_data = None
    if face_image_base64 and face_image_base64.strip():
        image_data = face_image_base64.strip()
    elif face_image_file:
        image_data = await face_image_file.read()
    else:
        raise HTTPException(status_code=400, detail="A face photo (via webcam capture or file upload) is required.")

    # Process face registration
    success, msg, cropped_img, embedding, meta = face_engine.process_face_registration(image_data)
    if not success:
        raise HTTPException(status_code=400, detail=f"Face registration failed: {msg}")

    # Save cropped face photo
    filename = f"{user_id}_{int(time.time())}.jpg"
    photo_file_path = UPLOAD_DIR_FACES / filename
    cv2.imwrite(str(photo_file_path), cropped_img)
    relative_photo_url = f"/static/uploads/faces/{filename}"

    # Create new user record
    new_user = User(
        user_id=user_id,
        full_name=full_name,
        email=email,
        phone=phone,
        department=department,
        role_title=role_title,
        notes=notes,
        photo_path=relative_photo_url,
        is_active=True
    )
    new_user.set_embedding(embedding)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "success": True,
        "message": f"User {full_name} ({user_id}) registered successfully!",
        "user": new_user.to_dict(include_embedding=False),
        "detection_meta": meta
    }


@app.put("/api/admin/users/{user_id}")
async def update_user(
    user_id: str,
    update_data: UserUpdateRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Update existing user information."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.full_name = update_data.full_name
    user.email = update_data.email
    user.phone = update_data.phone
    user.department = update_data.department
    user.role_title = update_data.role_title
    user.notes = update_data.notes
    user.is_active = update_data.is_active

    db.commit()
    db.refresh(user)
    return {"success": True, "message": "User updated successfully", "user": user.to_dict()}


@app.post("/api/admin/users/{user_id}/update-face")
async def update_user_face(
    user_id: str,
    face_image_base64: Optional[str] = Form(None),
    face_image_file: Optional[UploadFile] = File(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Re-register / update a user's biometric face model."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    image_data = None
    if face_image_base64 and face_image_base64.strip():
        image_data = face_image_base64.strip()
    elif face_image_file:
        image_data = await face_image_file.read()
    else:
        raise HTTPException(status_code=400, detail="Face image data required")

    success, msg, cropped_img, embedding, meta = face_engine.process_face_registration(image_data)
    if not success:
        raise HTTPException(status_code=400, detail=f"Face update failed: {msg}")

    # Save new cropped photo
    filename = f"{user_id}_{int(time.time())}.jpg"
    photo_file_path = UPLOAD_DIR_FACES / filename
    cv2.imwrite(str(photo_file_path), cropped_img)

    user.photo_path = f"/static/uploads/faces/{filename}"
    user.set_embedding(embedding)
    db.commit()

    return {"success": True, "message": "Biometric face data updated successfully", "photo_path": user.photo_path}


@app.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Delete user from database."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Optionally remove photo file
    try:
        if user.photo_path and user.photo_path.startswith("/static/"):
            file_on_disk = BASE_DIR / user.photo_path.lstrip("/")
            if file_on_disk.exists():
                file_on_disk.unlink()
    except Exception:
        pass

    db.delete(user)
    db.commit()
    return {"success": True, "message": f"User '{user_id}' deleted successfully."}


@app.get("/api/admin/logs")
async def get_scan_logs(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    user_id_filter: Optional[str] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: View audit and attendance face scan logs."""
    query = db.query(ScanLog)
    if status_filter:
        query = query.filter(ScanLog.status == status_filter)
    if user_id_filter:
        query = query.filter(ScanLog.user_id.ilike(f"%{user_id_filter}%"))

    total = query.count()
    logs = query.order_by(desc(ScanLog.timestamp)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "logs": [log.to_dict() for log in logs]
    }


@app.delete("/api/admin/logs")
async def clear_scan_logs(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Clear all scan logs."""
    db.query(ScanLog).delete()
    db.commit()
    return {"success": True, "message": "All scan logs cleared"}


@app.get("/api/admin/logs/export")
async def export_scan_logs_csv(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Export scan history to CSV file."""
    logs = db.query(ScanLog).order_by(desc(ScanLog.timestamp)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "User ID", "User Name", "Status", "Accuracy (%)", "Similarity Score", "Snapshot"])

    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "",
            log.user_id or "N/A",
            log.user_name or "N/A",
            log.status,
            f"{log.accuracy_percent:.2f}%",
            f"{log.similarity_score:.4f}",
            log.snapshot_path or ""
        ])

    output.seek(0)
    filename = f"faceid_scan_logs_{date.today().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/admin/settings")
async def get_settings(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Get system configuration."""
    threshold = get_system_threshold(db)
    return {
        "cosine_threshold": threshold,
        "default_threshold": DEFAULT_COSINE_THRESHOLD,
    }


@app.post("/api/admin/settings")
async def update_settings(
    settings: SettingUpdateRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Update system configuration."""
    row = db.query(SystemSetting).filter(SystemSetting.key == "cosine_threshold").first()
    if not row:
        row = SystemSetting(key="cosine_threshold", value=str(settings.cosine_threshold))
        db.add(row)
    else:
        row.value = str(settings.cosine_threshold)
    db.commit()
    return {"success": True, "message": "Settings updated", "cosine_threshold": settings.cosine_threshold}


@app.post("/api/admin/change-password")
async def change_admin_password(
    pwd_req: ChangePasswordRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """STRICTLY ADMIN ONLY: Change admin password."""
    if not verify_password(pwd_req.old_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(pwd_req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    admin.password_hash = hash_password(pwd_req.new_password)
    db.commit()
    return {"success": True, "message": "Password changed successfully"}
