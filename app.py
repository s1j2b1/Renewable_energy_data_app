
""" كود الـ Flask المطور (مع SQLite)
سنستخدم مكتبة Flask-SQLAlchemy لأنها تجعل التعامل مع قاعدة البيانات سهلاً جداً وتسمح لك بالانتقال من SQLite إلى PostgreSQL بضغطة زر
"""


# --- 1. استيراد المكتبات (الأدوات التي سنستخدمها) ---
import os # مكتبة للتعامل مع نظام التشغيل (مثل قراءة روابط قواعد البيانات)
from flask import Flask, render_template, request # مكتبة فلاسك لبناء موقع الويب
from flask_sqlalchemy import SQLAlchemy # مكتبة للتعامل مع قاعدة البيانات بسهولة
from datetime import datetime # مكتبة للتعامل مع الوقت والتاريخ
import requests # مكتبة لإرسال طلبات للإنترنت (مثل جلب الطقس)

# --- 2. إعداد تطبيق فلاسك ---
app = Flask(__name__) # إنشاء نسخة من تطبيق فلاسك

# --- 3. إعداد قاعدة البيانات (المخزن) ---
# السطر القادم يحدد مكان تخزين البيانات
# إذا كان التطبيق على الإنترنت (Render) سيستخدم PostgreSQL
# إذا كان على جهازك الشخصي سيقوم بإنشاء ملف صغير اسمه energy_data.db
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(base_dir, 'energy_data.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # إيقاف ميزة إضافية لا نحتاجها لتوفير الذاكرة

db = SQLAlchemy(app) # ربط قاعدة البيانات بتطبيق فلاسك

# --- 4. تصميم "الجدول" داخل قاعدة البيانات ---
# هنا نحدد ما هي المعلومات التي نريد حفظها للأبد
class EnergyRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True) # رقم تسلسلي تلقائي لكل عملية (1, 2, 3...)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow) # وقت وتاريخ الحساب
    city = db.Column(db.String(100)) # اسم المدينة
    lat = db.Column(db.Float) # خط العرض
    lon = db.Column(db.Float) # خط الطول
    temp = db.Column(db.Float) # درجة الحرارة التي جلبناها
    wind_speed = db.Column(db.Float) # سرعة الرياح
    clouds = db.Column(db.Float) # نسبة الغيوم
    solar_pred = db.Column(db.Float) # مقدار الطاقة الشمسية المتوقع
    wind_pred = db.Column(db.Float) # مقدار طاقة الرياح المتوقع
    total_power = db.Column(db.Float) # المجموع الكلي للطاقة

# أمر لإنشاء ملف قاعدة البيانات فور تشغيل الكود لأول مرة
with app.app_context():
    db.create_all()

# --- 5. إعدادات جلب البيانات من الإنترنت ---
MY_API_KEY = "2124779a58cd2a8e54e3326eb592337e" # مفتاحك الخاص لموقع OpenWeatherMap

def get_weather_data(lat, lon, api_key):
    """دالة تذهب للإنترنت وتجلب حالة الطقس الحالية للإحداثيات المعطاة"""
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=ar"
    try:
        response = requests.get(url) # إرسال الطلب للموقع
        data = response.json() # تحويل الرد إلى شكل يمكن لبايثون فهمه (قاموس)
        if data.get("cod") == "200": # إذا كان الاتصال ناجحاً
            forecast = data['list'][0] # خذ أول توقع متاح الآن
            return {
                "city": data['city']['name'],
                "temp": forecast['main']['temp'],
                "wind_speed": forecast['wind']['speed'],
                "clouds": forecast['clouds']['all']
            }
    except Exception as e:
        print(f"خطأ في الاتصال: {e}")
    return None

# --- 6. دالة التوقع (الذكاء الاصطناعي البسيط) ---
def predict_power(temp, wind_speed_api, cloud_pct, ac_status):
    """دالة تحسب كمية الطاقة بناءً على الأرقام التي شرحناها سابقاً"""
    
    # حساب الطاقة الشمسية
    solar_base = 1.0 # نفترض أن أقصى إنتاج للوح هو 1 أمبير
    cloud_factor = (100 - (cloud_pct * 0.8)) / 100 # الغيوم تقلل الإنتاج لكن لا تنهيه
    temp_factor = 1.0 if temp < 40 else 0.8 # إذا كانت الحرارة فوق 40، الكفاءة تقل
    predicted_solar = round(solar_base * cloud_factor * temp_factor, 3)

    # حساب طاقة الرياح
    wind_base = 1.6 # أقصى إنتاج للتوربين هو 1.6 أمبير
    if ac_status: # إذا كان المستخدم مشغل المكيف (رياح صناعية)
        predicted_wind = wind_base * 0.7 if wind_speed_api > 15 else wind_base * 1.0
    else: # إذا كان يعتمد على رياح الطبيعة فقط
        predicted_wind = (wind_speed_api / 20) * wind_base
    
    predicted_wind = round(predicted_wind, 3)
    total_power = round(predicted_solar + predicted_wind, 3)
    
    return total_power, predicted_solar, predicted_wind

# --- 7. مسارات الموقع (الصفحات التي يراها المستخدم) ---

@app.route('/', methods=['GET', 'POST']) # الصفحة الرئيسية للموقع
def index():
    results = None
    if request.method == 'POST': # إذا قام المستخدم بضغط زر "حساب"
        # 1. قراءة البيانات التي أدخلها المستخدم في المربعات
        lat = request.form.get('lat')
        lon = request.form.get('lon')
        ac_on = 'ac_status' in request.form # تفقد هل علامة "المكيف" مفعلة
        
        # 2. استدعاء دالة الطقس
        weather = get_weather_data(lat, lon, MY_API_KEY)
        
        if weather:
            # 3. حساب الطاقة المتوقعة بناءً على الطقس
            total, solar, wind = predict_power(weather['temp'], weather['wind_speed'], weather['clouds'], ac_on)
            
            # 4. حفظ هذه العملية في "المخزن" (قاعدة البيانات)
            new_record = EnergyRecord(
                city=weather['city'], lat=float(lat), lon=float(lon),
                temp=weather['temp'], wind_speed=weather['wind_speed'],
                clouds=weather['clouds'], solar_pred=solar, 
                wind_pred=wind, total_power=total
            )
            db.session.add(new_record) # إضافة السجل
            db.session.commit() # تأكيد الحفظ نهائياً
            
            # تجهيز النتائج لعرضها في الصفحة
            results = {
                "weather": weather,
                "solar": solar,
                "wind": wind,
                "total": total,
                "ac_status": "شغال" if ac_on else "مطفأ"
            }
            
    return render_template('index.html', results=results) # عرض صفحة index.html


# --- 8. تشغيل التطبيق ---
if __name__ == '__main__':
    app.run(debug=True) # تشغيل الموقع في وضع التطوير (Debug) لسهولة اكتشاف الأخطاء


