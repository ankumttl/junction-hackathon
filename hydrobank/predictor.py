import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime

# Real NEA data: month -> average generation MW
MONTHLY_GENERATION = {
    1: 1100, 2: 1050, 3: 1200, 4: 1500,
    5: 1900, 6: 2600, 7: 3200, 8: 3400,
    9: 3100, 10: 2400, 11: 1400, 12: 1150
}

AVERAGE_DEMAND = 1380  # MW (relatively stable year round)

def train_model():
    """Train a simple linear regression on monthly generation data"""
    X = np.array(list(MONTHLY_GENERATION.keys())).reshape(-1, 1)
    y = np.array(list(MONTHLY_GENERATION.values()))
    model = LinearRegression()
    model.fit(X, y)
    return model

model = train_model()

def predict_surplus(month: int) -> dict:
    """Predict surplus/deficit for a given month"""
    predicted_generation = model.predict([[month]])[0]
    surplus = predicted_generation - AVERAGE_DEMAND

    if surplus > 300:
        status = "HIGH_SURPLUS"
        recommendation = "surplus"
        message = f"High surplus expected: {surplus:.0f} MW extra. Offer discounts to customers."
    elif surplus > 0:
        status = "LOW_SURPLUS"
        recommendation = "surplus"
        message = f"Mild surplus expected: {surplus:.0f} MW extra. Encourage industrial use."
    elif surplus > -200:
        status = "BALANCED"
        recommendation = "balanced"
        message = f"Demand roughly matches supply. Normal tariff rates."
    else:
        status = "DEFICIT"
        recommendation = "shortage"
        message = f"Deficit expected: {abs(surplus):.0f} MW short. Request load reduction."

    return {
        "month": month,
        "predicted_generation_mw": round(predicted_generation, 1),
        "average_demand_mw": AVERAGE_DEMAND,
        "surplus_mw": round(surplus, 1),
        "status": status,
        "recommendation": recommendation,
        "message": message
    }

def get_7_day_forecast() -> list:
    """Get forecast for next 7 days based on current month"""
    current_month = datetime.now().month
    forecasts = []

    for i in range(7):
        # Slightly vary daily prediction for realism
        month_to_predict = ((current_month - 1 + i // 30) % 12) + 1
        forecast = predict_surplus(month_to_predict)
        forecast["day"] = i + 1

        # Add small daily variation (+/- 5%)
        variation = np.random.uniform(-0.05, 0.05)
        forecast["predicted_generation_mw"] *= (1 + variation)
        forecast["surplus_mw"] = round(forecast["predicted_generation_mw"] - AVERAGE_DEMAND, 1)
        forecasts.append(forecast)

    return forecasts

def calculate_dynamic_tariff(surplus_mw: float) -> dict:
    """Calculate electricity tariff based on surplus"""
    base_rate = 12.0  # Rs per kWh normal rate

    if surplus_mw > 1500:
        discount = 45
    elif surplus_mw > 800:
        discount = 35
    elif surplus_mw > 300:
        discount = 20
    elif surplus_mw > 0:
        discount = 10
    elif surplus_mw > -200:
        discount = 0
    else:
        # Shortage - no discount, penalty for heavy use
        discount = -10  # 10% premium during shortage

    current_rate = base_rate * (1 - discount / 100)

    return {
        "base_rate_rs": base_rate,
        "discount_percent": discount,
        "current_rate_rs": round(current_rate, 2),
        "surplus_mw": surplus_mw
    }