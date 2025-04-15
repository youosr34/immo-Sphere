from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField
from wtforms.validators import DataRequired
import sqlite3
from datetime import datetime
from PIL import Image, ImageEnhance
import os

def init_db():
    with sqlite3.connect('crm.db') as conn:
        curseur = conn.cursor()
        curseur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        curseur.execute('''
            CREATE TABLE IF NOT EXISTS pige (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                nom_contact TEXT,
                adresse TEXT,
                prix REAL,
                date_ajout TEXT,
                photo_path TEXT,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        curseur.execute('INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)', ('admin', 'admin123'))
        conn.commit()

app = Flask(__name__) 
init_db()
app.secret_key = os.environ.get('SECRET_KEY', 'ma_cle_secrete_123')
app.config['UPLOAD_FOLDER'] = 'static/images'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect('crm.db') as conn:
        curseur = conn.cursor()
        curseur.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
        user = curseur.fetchone()
        if user:
            return User(user[0], user[1])
        return None

class PhotoForm(FlaskForm):
    photo = FileField('Uploader une photo', validators=[DataRequired()])
    submit = SubmitField('Traiter la photo')

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        with sqlite3.connect('crm.db') as conn:
            curseur = conn.cursor()
            curseur.execute('SELECT id, username FROM users WHERE username = ? AND password = ?', 
                            (username, password))
        user = curseur.fetchone()
        conn.close()
        if user:
            user_obj = User(user[0], user[1])
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        flash('Nom d’utilisateur ou mot de passe incorrect')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=current_user.username)

@app.route('/pige', methods=['GET', 'POST'])
@login_required
def pige():
    with sqlite3.connect('crm.db') as conn:
        curseur = conn.cursor()
    
    if request.method == 'POST':
        source = request.form.get('source', '')
        nom_contact = request.form.get('nom_contact', '')
        adresse = request.form.get('adresse', '')
        prix = float(request.form.get('prix', 0))
        curseur.execute('INSERT INTO pige (source, nom_contact, adresse, prix, date_ajout, user_id) VALUES (?, ?, ?, ?, ?, ?)',
                        (source, nom_contact, adresse, prix, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), current_user.id))
        conn.commit()
        flash('Lead ajouté avec succès')

    curseur.execute('SELECT * FROM pige WHERE user_id = ?', (current_user.id,))
    leads = curseur.fetchall()
    conn.close()
    return render_template('pige.html', leads=leads)

@app.route('/photo_staging', methods=['GET', 'POST'])
@login_required
def photo_staging():
    form = PhotoForm()
    processed_image = None
    
    if form.validate_on_submit():
        photo = form.photo.data
        filename = f"{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        photo.save(filepath)
        
        img = Image.open(filepath)
        img_enhanced = ImageEnhance.Brightness(img).enhance(1.2)
        img_enhanced = ImageEnhance.Contrast(img_enhanced).enhance(1.3)
        img_enhanced = ImageEnhance.Sharpness(img_enhanced).enhance(1.5)
        
        processed_filename = f"enhanced_{filename}"
        processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
        img_enhanced.save(processed_filepath)
        
        with sqlite3.connect('crm.db') as conn:
            curseur = conn.cursor()
        curseur.execute('UPDATE pige SET photo_path = ? WHERE id = (SELECT MAX(id) FROM pige WHERE user_id = ?)',
                        (processed_filename, current_user.id))
        conn.commit()
        conn.close()
        
        processed_image = processed_filename
        flash('Photo améliorée avec succès !')

    return render_template('photo_staging.html', form=form, processed_image=processed_image)

@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)