from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, make_response
from pymongo import MongoClient
from tensorflow.keras.models import load_model
from itsdangerous import URLSafeTimedSerializer
from PIL import Image
import numpy as np
import os
from datetime import datetime
from flask_mail import Mail, Message


# Flask Uygulaması
app = Flask(__name__)
# Çevresel değişkeni kullanır
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Token Serializer Tanımlaması
s = URLSafeTimedSerializer(app.secret_key)
  
# Flask-Mail Ayarları
from flask_mail import Mail, Message

app.config['MAIL_DEFAULT_SENDER'] = ('MammoDetectAI', 'ayssenurkurt@gmail.com')

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'ayssenurkurt@gmail.com'  # Gmail adresiniz
app.config['MAIL_PASSWORD'] = 'leko amgq clrb rhes'      # Gmail uygulama şifresi


mail = Mail(app)  # Burada mail nesnesini oluşturun

# MongoDB Bağlantısı
client = MongoClient("mongodb+srv://ayssenurkurt:Guclusifre123.@memekansericluster.e8xvl.mongodb.net/?retryWrites=true&w=majority")
db = client['meme_kanseri_db']  # Veritabanı adı
collection = db['analiz_sonuclari']  # Koleksiyon adı
users_collection = db['kullanicilar']



# Modeli Yükle
model = load_model('/Users/nur/Desktop/breastcancerproject/yüzde82dogruluk.keras')

# Yükleme Klasörü Ayarı
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Uygulama başlatıldığında uploads klasörünü oluştur
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Görsel İşleme Fonksiyonu
def process_image(file_path):
    img = Image.open(file_path).resize((224, 224)).convert("RGB")  # Görseli uygun boyuta getir
    img_array = np.expand_dims(np.array(img) / 255.0, axis=0)  # Normalize et ve batch boyutu ekle
    return img_array



# Ana Sayfa: index.html'i Render Et

@app.route('/')
def home():
   # Blogları MongoDB'den çek
    blogs = list(db['blogs'].find({"is_published": True}))
    for blog in blogs:
        blog["_id"] = str(blog["_id"])

    # Oturum açık mı kontrol et
    if 'username' in session:
        return render_template('index.html', logged_in=True, username=session.get('username'), blogs=blogs)
    else:
        username = request.cookies.get('rememberMe')
        if username:
            session['username'] = username
             # 🔹 Rolü de session'a ekle
            user = users_collection.find_one({"username": username})
            if user:
                session['role'] = user.get('role', 'user')
            return render_template('index.html', logged_in=True, username=username, blogs=blogs)
        else:
            return render_template('index.html', logged_in=False, blogs=blogs)


from bson import ObjectId

@app.route('/blog/<blog_id>')
def blog_detail(blog_id):
    from bson import ObjectId
    blog = db['blogs'].find_one({"_id": ObjectId(blog_id)})
    if blog:
        blog["_id"] = str(blog["_id"])
        return render_template('blog_detail.html', blog=blog)
    return "Blog bulunamadı", 404



@app.route('/logout')
def logout():
    session.pop('username', None)  # Oturumu temizle
    response = make_response(redirect(url_for('home')))
    response.delete_cookie('rememberMe')  # Çerezi temizle
    return response


#Hesabım Sayfası
@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'username' in session:
        # Kullanıcı bilgilerini getir
        user = users_collection.find_one({"username": session['username']}, {"_id": 0})
        # 🔽 Rol bilgisi eksikse session'a ekle
        if 'role' not in session:
            session['role'] = user.get('role', 'user')

        user_results = list(collection.find({"kullanici": session['username']}, {"_id": 0}))

        if request.method == 'POST':
            # Formdan gelen bilgileri al
            updated_data = {
                "email": request.form['email'],
                "yas": request.form['yas'],
                "cinsiyet": request.form['cinsiyet'],
                "kilo": request.form['kilo'],
                "boy": request.form['boy']
            }
            users_collection.update_one({"username": session['username']}, {"$set": updated_data})

            # Profil fotoğrafını kontrol et
            if 'profile_pic' in request.files and request.files['profile_pic'].filename != '':
                profile_pic = request.files['profile_pic']
                profile_pic_path = f"static/profile_pics/{session['username']}.jpg"
                profile_pic.save(profile_pic_path)
                updated_foto = f"profile_pics/{session['username']}.jpg"
            else:
                updated_foto = user.get('foto')  # Mevcut fotoğrafı koru

            # Fotoğrafı veritabanına kaydet
            users_collection.update_one(
                {"username": session['username']},
                {"$set": {"foto": updated_foto}}
            )

            flash("Bilgileriniz başarıyla güncellendi!", "success")
            return redirect(url_for('account'))

        return render_template('account.html', user=user, results=user_results)
    else:
        return redirect(url_for('login'))


@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    if 'username' in session:
        user = users_collection.find_one({"username": session['username']})
        if user and user.get('foto'):
            photo_path = os.path.join('static', user['foto'])

            # Dosya sisteminden fotoğrafı sil
            if os.path.exists(photo_path):
                os.remove(photo_path)

            # Veritabanından fotoğraf bilgisini kaldır
            users_collection.update_one(
                {"username": session['username']},
                {"$unset": {"foto": ""}}  # 'foto' alanını kaldırır
            )
            flash("Profil fotoğrafınız kaldırıldı!", "success")
        else:
            flash("Zaten profil fotoğrafınız yok.", "info")

    return redirect(url_for('account'))

#Tarama Sayfası
@app.route('/scan')
def scan():
    # Giriş yapmış kullanıcıya seçenek göstermeden tarama ekranını aç
    if 'username' in session:
        return render_template('scan.html', logged_in=True)  # Giriş yapmış kullanıcı
    else:
        return render_template('scan.html', logged_in=False)  # Misafir kullanıcı

# Hesabım Güncelleme Rotası
@app.route('/update-field', methods=['POST'])
def update_field():
    if 'username' in session:
        data = request.json
        field = data.get('field')
        value = data.get('value')

        if field and value:
            # Veritabanındaki ilgili alanı güncelle
            users_collection.update_one(
                {"username": session['username']}, 
                {"$set": {field: value}}
            )
            return jsonify({"value": value}), 200
    return jsonify({"error": "Yetkisiz işlem"}), 403


@app.route('/muayene-takvimi')
def muayene_takvimi():
    return render_template('muayene-takvimi.html')

#Fotoğraf Güncelleme rotası
@app.route('/upload-photo', methods=['POST'])
def upload_photo():
    if 'username' in session and 'profile_pic' in request.files:
        profile_pic = request.files['profile_pic']
        profile_pic_path = f"static/profile_pics/{session['username']}.jpg"
        profile_pic.save(profile_pic_path)  # Fotoğrafı kaydet

        # Veritabanındaki kullanıcı fotoğrafını güncelle
        users_collection.update_one(
            {"username": session['username']},
            {"$set": {"foto": f"profile_pics/{session['username']}.jpg"}}
        )

        return jsonify({"message": "Fotoğraf başarıyla güncellendi!"}), 200
    return jsonify({"error": "Yükleme başarısız!"}), 403


import tempfile

@app.route('/upload', methods=['POST'])
def upload_images():
    print("Upload rotasına istek geldi!")
    try:
        files = request.files.getlist("images")  # Çoklu görselleri al
        results = []

        for file in files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            print(f"Görsel kaydedildi: {file_path}")

            # Görsel işleme
            img_array = process_image(file_path)
            prediction = model.predict(img_array)
            predicted_class = np.argmax(prediction, axis=1)[0]

            # Tahmin edilen sınıfı belirle
            if predicted_class == 0:
                result = "İyi huylu"
            elif predicted_class == 1:
                result = "Kötü huylu"
            else:
                result = "Takip edilmeli"

            # Veritabanına kayıt
            if 'username' in session:
                try:
                    collection.insert_one({
                        "kullanici": session['username'],  # Kullanıcı adı
                        "goruntu": file.filename,
                        "sonuc": result,
                        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    print("Veritabanına kayıt yapıldı!")
                except Exception as e:
                    print("Veritabanına kayıt hatası:", e)

            results.append({"image": file.filename, "prediction": result})

        return jsonify({"results": results}) , 200 # JSON formatında yanıt döndür
    except Exception as e:
        print("Hata:", str(e))
        return jsonify({"error": str(e)}), 500


   
# Kayıt Ol Sayfası
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Formdan gelen veriyi al
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Veritabanına kaydet
        user = {
            "username": username,
            "email": email,
            "password": password , # Şifreleme önerilir
            "role": "user"  # 🔹 Varsayılan rol ekle

        }
        users_collection.insert_one(user)
        return render_template('success.html', message="Kayıt başarılı!")
    return render_template('register.html')

#Kullanıcı Giriş Sayfası
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')  # Kullanıcı adı veya e-posta
        password = request.form.get('password')
        remember_me = request.form.get('rememberMe')  # Checkbox değeri
        print(f"Beni Hatırla Değeri: {remember_me}")


        # Kullanıcıyı veritabanından çek
        user = users_collection.find_one({"$or": [{"email": identifier}, {"username": identifier}]})

        if user and user['password'] == password:
            session['username'] = user['username']  # Oturumu başlat
            session['role'] = user.get('role', 'user') 
            response = make_response(redirect(url_for('home')))  # Ana sayfaya yönlendir

            # "Beni Hatırla" seçildiyse çerez oluştur
            if remember_me:
                response.set_cookie('rememberMe', user['username'], max_age=30*24*60*60, secure=False, httponly=True)
            return response
        else:
            return render_template('login.html', error="E-posta veya şifre hatalı!")
    else:
        return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        print(f"📨 E-posta alındı: {email}")

        user = users_collection.find_one({"email": email})
        print(f"🔍 Veritabanında kullanıcı bulundu mu: {bool(user)}")

        if user:
            try:
                token = s.dumps(email, salt='password-reset-salt')
                reset_url = f'http://127.0.0.1:5003/reset-password/{token}'
                print(f"🔗 Token üretildi. Reset URL: {reset_url}")

                msg = Message('Şifre Sıfırlama Talebi', recipients=[email])
                msg.body = f"Lütfen aşağıdaki bağlantıyı kullanarak şifrenizi sıfırlayın:\n\n{reset_url}"
                print("📤 Mail oluşturuldu. Gönderiliyor...")

                mail.send(msg)
                print("✅ Mail gönderildi!")

                return render_template('forgot-password.html', success="Şifre sıfırlama bağlantısı e-posta adresinize gönderildi!")
            except Exception as e:
                print(f"❌ Mail gönderiminde hata: {e}")
                return render_template('forgot-password.html', error="Mail gönderilirken bir hata oluştu.")
        else:
            print("⚠️ Kullanıcı bulunamadı, mail gönderilmedi.")
            return render_template('forgot-password.html', error="Bu e-posta adresi sistemimizde kayıtlı değil!")

    print("🟡 [GET] Şifre sıfırlama formu gösteriliyor.")
    return render_template('forgot-password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception as e:
        return "Token geçersiz veya süresi dolmuş!"

    if request.method == 'POST':
        new_password = request.form.get('password')
        users_collection.update_one({"email": email}, {"$set": {"password": new_password}})
        return redirect('/login')

    return '''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Şifreyi Güncelle</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {
                    background: linear-gradient(120deg, #1c1c1e, #343434); 
                    color: #fff;
                    font-family: 'Roboto', sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .reset-container {
                    background: rgba(255, 255, 255, 0.1);
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
                    width: 100%;
                    max-width: 400px;
                    text-align: center;
                }
                .form-control {
                    background: rgba(255, 255, 255, 0.2);
                    border: none;
                    color: #fff;
                    margin-bottom: 15px;
                }
                .btn-primary {
                    background-color: #5dcc85;
                    border: none;
                    width: 100%;
                }
            </style>
        </head>
        <body>
            <div class="reset-container">
                <h2>Şifreyi Güncelle</h2>
                <form method="POST">
                    <input type="password" name="password" class="form-control" placeholder="Yeni Şifre" required />
                    <button type="submit" class="btn btn-primary">Şifreyi Güncelle</button>
                </form>
            </div>
        </body>
        </html>
    '''





# Veri Ekleme
@app.route('/add', methods=['POST'])
def add_data():
    try:
        # İstekten gelen JSON veriyi al
        data = request.json
        collection.insert_one(data)  # Veriyi MongoDB'ye ekle
        return jsonify({"message": "Veri başarıyla eklendi!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Veri Okuma
@app.route('/read', methods=['GET'])
def read_data():
    try:
        data = list(collection.find({}, {"_id": 0}))  # Tüm verileri al
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#Blogs Sayfası
@app.route('/blogs', methods=['GET'])
def list_blogs():
    # Blogları MongoDB'den çek ve şablona gönder
    blogs = list(db['blogs'].find({"is_published": True}))
    return render_template('blogs.html', blogs=blogs)

#Blog Yazma Sayfası
import base64

@app.route('/write-blog', methods=['GET', 'POST'])
def write_blog():
    if request.method == 'POST':
        # Görsel dosyasını kontrol et
        image_base64 = None
        if 'image' in request.files:
            image_file = request.files['image']
            # Görseli Base64'e dönüştür
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        # Blog detaylarını al
        new_blog = {
            "title": request.form['title'],
            "content": request.form['content'],
            "image": image_base64,  # Görseli Base64 olarak sakla
            "author": session.get('username', 'Anonymous'),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "is_published": True
        }

        # MongoDB'ye blog ekle
        db['blogs'].insert_one(new_blog)
        flash("Blog başarıyla eklendi!", "success")
        return redirect('/#blog-section')

    return render_template('blogwrite.html')


@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')  # Formdan gelen 'name' alanı
    email = request.form.get('email')  # Formdan gelen 'email' alanı
    message = request.form.get('message')  # Formdan gelen 'message' alanı

    # Form verilerinin eksikliğini kontrol et
    if not name or not email or not message:
        flash('Lütfen tüm alanları doldurun!', 'error')
        return redirect('/')

    # MongoDB'ye verileri kaydet
    contact_data = {
        'name': name,
        'email': email,
        'message': message,
        'created_at': datetime.utcnow()  # Mesajın kaydedildiği zamanı ekle
    }

    try:
        iletisim_collection = db['iletisim_formu']  # Yeni koleksiyon
        iletisim_collection.insert_one(contact_data)  # Veritabanına ekle
        flash('Mesajınız başarıyla kaydedildi!', 'success')
    except Exception as e:
        print(f"Veritabanı hatası: {e}")
        flash('Mesaj kaydedilirken bir hata oluştu.', 'error')

    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True, port=5003)  # 5001 portunu kullan

