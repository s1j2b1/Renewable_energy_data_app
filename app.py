import os
import csv
import io
import requests  # ضروري لجلب بيانات الطقس
from flask import Flask, render_template, request, Response, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

# تحميل المفاتيح من ملف .env (إذا وجد)
load_dotenv()

app = Flask(__name__)

# --- إعدادات قاعدة البيانات ---
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(base_dir, 'energy_data.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# كلمة المرور للإدارة (يمكنك تغييرها)
ADMIN_PASSWORD = "my_secret_password" 

# --- تصميم جدول البيانات ---
class EnergyRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    city = db.Column(db.String(100))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    temp = db.Column(db.Float)
    wind_speed = db.Column(db.Float)
    clouds = db.Column(db.Float)
    solar_pred = db.Column(db.Float)
    wind_pred = db.Column(db.Float)
    total_power = db.Column(db.Float)

# إنشاء الجداول
with app.app_context():
    db.create_all()

# جلب مفتاح الطقس من إعدادات Render
MY_API_KEY = os.environ.get('WEATHER_API_KEY')

# --- دالة جلب الطقس ---
def get_weather_data(lat, lon, api_key):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=ar"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get("cod") == "200":
            forecast = data['list'][0]
            return {
                "city": data['city']['name'],
                "temp": forecast['main']['temp'],
                "wind_speed": forecast['wind']['speed'],
                "clouds": forecast['clouds']['all']
            }
    except:
        return None

# --- دالة الحساب ---
def predict_power(temp, wind_speed_api, cloud_pct, ac_status):
    solar_base = 1.0
    cloud_factor = (100 - (cloud_pct * 0.8)) / 100
    temp_factor = 1.0 if temp < 40 else 0.8
    predicted_solar = round(solar_base * cloud_factor * temp_factor, 3)

    wind_base = 1.6
    if ac_status:
        predicted_wind = wind_base * 0.7 if wind_speed_api > 15 else wind_base * 1.0
    else:
        predicted_wind = (wind_speed_api / 20) * wind_base
    
    predicted_wind = round(predicted_wind, 3)
    total_power = round(predicted_solar + predicted_wind, 3)
    return total_power, predicted_solar, predicted_wind

# --- المسارات (Routes) ---

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    if request.method == 'POST':
        lat = request.form.get('lat')
        lon = request.form.get('lon')
        ac_on = 'ac_status' in request.form
        weather = get_weather_data(lat, lon, MY_API_KEY)
        if weather:
            total, solar, wind = predict_power(weather['temp'], weather['wind_speed'], weather['clouds'], ac_on)
            new_record = EnergyRecord(
                city=weather['city'], lat=float(lat), lon=float(lon),
                temp=weather['temp'], wind_speed=weather['wind_speed'],
                clouds=weather['clouds'], solar_pred=solar, 
                wind_pred=wind, total_power=total
            )
            db.session.add(new_record)
            db.session.commit()
            results = {"weather": weather, "solar": solar, "wind": wind, "total": total, "ac_status": "شغال" if ac_on else "مطفأ"}
    return render_template('index.html', results=results)

@app.route('/history')
def history():
    pwd = request.args.get('password')
    if pwd != ADMIN_PASSWORD:
        return "<h3>خطأ: كلمة المرور غير صحيحة.</h3>", 403
    
    records = EnergyRecord.query.order_by(EnergyRecord.timestamp.desc()).all()
    return render_template('history.html', records=records)

@app.route('/download')
def download_csv():
    pwd = request.args.get('password')
    if pwd != ADMIN_PASSWORD:
        return "خطأ في الصلاحية", 403
    
    records = EnergyRecord.query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'City', 'Solar', 'Wind', 'Total'])
    for r in records:
        writer.writerow([r.id, r.city, r.solar_pred, r.wind_pred, r.total_power])
    
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-disposition": "attachment; filename=data.csv"})

if __name__ == '__main__':
    app.run(debug=True)
