from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import os

from database import get_db, init_db, Customer, Alert, CustomerResponse, NEAData
from predictor import predict_surplus, get_7_day_forecast, calculate_dynamic_tariff

app = FastAPI(title="HydroBank API")

# Serve frontend files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.on_event("startup")
def startup():
    init_db()

# ─── PYDANTIC SCHEMAS ───────────────────────────────────────────

class CustomerCreate(BaseModel):
    name: str
    email: str
    password: str
    business_type: str
    load_kw: float

class CustomerLogin(BaseModel):
    email: str
    password: str

class AlertCreate(BaseModel):
    alert_type: str        # "surplus" or "shortage"
    message: str
    discount_percent: float
    start_time: str
    end_time: str

class RespondToAlert(BaseModel):
    customer_id: int
    alert_id: int
    accepted: bool
    load_shifted_kw: Optional[float] = 0.0

# ─── FRONTEND ROUTES ────────────────────────────────────────────

@app.get("/")
def serve_customer():
    return FileResponse("frontend/index.html")

@app.get("/nea")
def serve_nea():
    return FileResponse("frontend/dashboard.html")

# ─── CUSTOMER ROUTES ────────────────────────────────────────────

@app.post("/customer/register")
def register_customer(data: CustomerCreate, db: Session = Depends(get_db)):
    existing = db.query(Customer).filter(Customer.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    customer = Customer(
        name=data.name,
        email=data.email,
        password=data.password,  # in real app: hash this!
        business_type=data.business_type,
        load_kw=data.load_kw,
        credits=0.0
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return {"message": "Registered successfully!", "customer_id": customer.id, "name": customer.name}

@app.post("/customer/login")
def login_customer(data: CustomerLogin, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(
        Customer.email == data.email,
        Customer.password == data.password
    ).first()
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "business_type": customer.business_type,
        "load_kw": customer.load_kw,
        "credits": customer.credits
    }

@app.get("/customer/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "business_type": customer.business_type,
        "load_kw": customer.load_kw,
        "credits": round(customer.credits, 2)
    }

@app.get("/customer/{customer_id}/history")
def get_customer_history(customer_id: int, db: Session = Depends(get_db)):
    responses = db.query(CustomerResponse).filter(
        CustomerResponse.customer_id == customer_id
    ).all()
    result = []
    for r in responses:
        alert = db.query(Alert).filter(Alert.id == r.alert_id).first()
        result.append({
            "alert_type": alert.alert_type if alert else "unknown",
            "accepted": r.accepted,
            "load_shifted_kw": r.load_shifted_kw,
            "credits_earned": r.credits_earned,
            "date": r.responded_at.strftime("%Y-%m-%d %H:%M")
        })
    return result

# ─── ALERT ROUTES ───────────────────────────────────────────────

@app.get("/alerts/active")
def get_active_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).filter(Alert.is_active == True).all()
    return [{
        "id": a.id,
        "alert_type": a.alert_type,
        "message": a.message,
        "discount_percent": a.discount_percent,
        "start_time": a.start_time,
        "end_time": a.end_time,
        "created_at": a.created_at.strftime("%Y-%m-%d %H:%M")
    } for a in alerts]

@app.post("/alerts/create")
def create_alert(data: AlertCreate, db: Session = Depends(get_db)):
    alert = Alert(
        alert_type=data.alert_type,
        message=data.message,
        discount_percent=data.discount_percent,
        start_time=data.start_time,
        end_time=data.end_time
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return {"message": "Alert created!", "alert_id": alert.id}

@app.post("/alerts/respond")
def respond_to_alert(data: RespondToAlert, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    alert = db.query(Alert).filter(Alert.id == data.alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    credits_earned = 0.0
    if data.accepted:
        # Calculate credits based on load shifted and alert type
        if alert.alert_type == "surplus":
            # Customer uses cheap electricity - earns credits for participation
            credits_earned = data.load_shifted_kw * 0.5  # Rs 0.5 per kW as loyalty credit
        elif alert.alert_type == "shortage":
            # Customer reduces load - earns more credits for helping
            credits_earned = data.load_shifted_kw * 2.0  # Rs 2 per kW saved

        customer.credits += credits_earned
        db.commit()

    response = CustomerResponse(
        customer_id=data.customer_id,
        alert_id=data.alert_id,
        accepted=data.accepted,
        load_shifted_kw=data.load_shifted_kw,
        credits_earned=credits_earned
    )
    db.add(response)
    db.commit()

    return {
        "message": "Response recorded!",
        "accepted": data.accepted,
        "credits_earned": credits_earned,
        "total_credits": round(customer.credits, 2)
    }

@app.delete("/alerts/{alert_id}/deactivate")
def deactivate_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_active = False
    db.commit()
    return {"message": "Alert deactivated"}

# ─── PREDICTION ROUTES ──────────────────────────────────────────

@app.get("/forecast/current")
def current_forecast():
    month = datetime.now().month
    forecast = predict_surplus(month)
    tariff = calculate_dynamic_tariff(forecast["surplus_mw"])
    return {**forecast, **tariff}

@app.get("/forecast/7days")
def seven_day_forecast():
    return get_7_day_forecast()

@app.get("/tariff/current")
def current_tariff():
    month = datetime.now().month
    forecast = predict_surplus(month)
    return calculate_dynamic_tariff(forecast["surplus_mw"])

# ─── NEA DASHBOARD ROUTES ───────────────────────────────────────

@app.get("/nea/stats")
def nea_stats(db: Session = Depends(get_db)):
    total_customers = db.query(Customer).count()
    total_alerts = db.query(Alert).filter(Alert.is_active == True).count()

    # Total load enrolled
    customers = db.query(Customer).all()
    total_load_kw = sum(c.load_kw for c in customers)

    # Total responses accepted
    accepted = db.query(CustomerResponse).filter(CustomerResponse.accepted == True).count()
    total_responses = db.query(CustomerResponse).count()

    # Current forecast
    month = datetime.now().month
    forecast = predict_surplus(month)

    return {
        "total_customers": total_customers,
        "active_alerts": total_alerts,
        "total_enrolled_load_kw": round(total_load_kw, 1),
        "total_responses": total_responses,
        "accepted_responses": accepted,
        "current_surplus_mw": forecast["surplus_mw"],
        "current_status": forecast["status"],
        "current_month_name": datetime.now().strftime("%B")
    }

@app.get("/nea/customers")
def list_customers(db: Session = Depends(get_db)):
    customers = db.query(Customer).all()
    return [{
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "business_type": c.business_type,
        "load_kw": c.load_kw,
        "credits": round(c.credits, 2),
        "joined": c.joined_at.strftime("%Y-%m-%d")
    } for c in customers]

@app.get("/nea/monthly-data")
def monthly_data(db: Session = Depends(get_db)):
    data = db.query(NEAData).order_by(NEAData.month).all()
    return [{
        "month": d.month,
        "generation_mw": d.generation_mw,
        "demand_mw": d.demand_mw,
        "surplus_mw": d.surplus_mw
    } for d in data]