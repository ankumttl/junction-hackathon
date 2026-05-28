File 1: database.py
This creates your database tables automatically.

It creates 4 tables:
customers — stores everyone who signs up (name, email, password, business type, credits)
alerts — stores alerts NEA sends (surplus/shortage messages)
customer_responses — stores who accepted/declined each alert
nea_data — stores real NEA historical electricity data (pre-filled automatically)

File 2: predictor.py
It:
Has real NEA data built in (monsoon = 3400 MW, dry season = 1100 MW)
Predicts whether current month has surplus or deficit
Calculates dynamic electricity rate (cheaper during surplus, normal during shortage)
Generates a 7-day forecast

File 3: main.py
It connects everything together and creates all the API routes:
POST /customer/register      Customer signs up
POST /customer/login         Customer logs in
GET /alerts/active           Get all active alerts
POST /alerts/create          NEA sends an alert
POST /alerts/respond         Customer accepts/declines
GET /forecast/current        Current surplus prediction
GET /forecast/7days          7-day forecast
GET /nea/stats               Dashboard statistics

index.html — Customer Portal
This is what a brick kiln owner, factory, EV station sees.
Before login:
See current electricity rate
See if today is surplus or shortage
Sign up / Login buttons

After login:
Their profile with credit balance
Active alerts from NEA ("Cheap electricity 6–11 PM tonight!")
Accept button → enter how much load they'll shift → earn credits
Decline button
Full history of all their responses and credits earned

dashboard.html — NEA Admin Panel
This is what the NEA operator sees. It has 4 sections:
Overview:
Total customers enrolled
Total load being managed (kW)
Active alerts count
Current surplus/deficit MW
Bar chart of monthly generation vs demand

Forecast:
7-day surplus/deficit prediction cards
Line chart showing the trend

Alerts:
Send a surplus alert (with discount %, time window, message)
Send a shortage alert
See all active alerts
Deactivate any alert

Customers:
Table of all registered customers
Their business type, load, credits, join date
