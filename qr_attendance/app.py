import os
import base64
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import qrcode
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SendGridMail, Email, To, Content, Attachment, FileContent, FileName, FileType
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Configuración de Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.urandom(24)

# Obtener la API KEY desde el archivo .env
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

# Inicializar SQLAlchemy
db = SQLAlchemy(app)

# Modelos
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    lastname = db.Column(db.String(50))
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    qr_code = db.Column(db.String(200))
    attended = db.Column(db.Boolean, default=False)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    attended = db.Column(db.Boolean, default=False)

# Ruta de inicio
@app.route('/')
def index():
    return render_template('index.html')

# Registro de usuario
@app.route('/register_user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        name = request.form['name']
        lastname = request.form['lastname']
        email = request.form['email']
        phone = request.form['phone']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Este correo electrónico ya está registrado. Por favor, utiliza otro.', 'danger')
            return redirect(url_for('register_user'))

        new_user = User(name=name, lastname=lastname, email=email, phone=phone)

        # Generar QR
        qr = qrcode.make(f"{name} {lastname} {email}")
        qr_code_path = os.path.join('static/qr_codes', f"{email}.png")
        os.makedirs(os.path.dirname(qr_code_path), exist_ok=True)
        qr.save(qr_code_path)
        new_user.qr_code = qr_code_path

        db.session.add(new_user)
        db.session.commit()

        # Enviar correo con el QR adjunto
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            from_email = Email("wazaaquispe40@gmail.com")  # Correo verificado de SendGrid
            to_email = To(email)
            subject = "QR de Registro"
            
            # Mensaje con emojis
            content = Content("text/plain", f"Hola {name}, 😊\n\nEspero que tengas un excelente día. 🌞\n\nTe comparto tu QR para asistir al evento. 📲 ¡Nos vemos pronto! 🎉")
            
            mail = SendGridMail(from_email, to_email, subject, content)

            # Adjuntar el código QR al correo
            with open(qr_code_path, 'rb') as qr_file:
                file_data = qr_file.read()
                encoded_file_data = base64.b64encode(file_data).decode()
                attachment = Attachment()
                attachment.file_content = FileContent(encoded_file_data)
                attachment.file_name = FileName(f"{email}.png")
                attachment.file_type = FileType("image/png")
                mail.add_attachment(attachment)

            response = sg.send(mail)
            print("Correo enviado:", response.status_code)

        except Exception as e:
            print("Error al enviar correo:", str(e))
            flash('Error al enviar el correo. Revisa la configuración de SendGrid.', 'danger')

        return render_template('qr_page.html', qr_code_path=qr_code_path)

    return render_template('register_user.html')

# Registro de administradores
@app.route('/register_root', methods=['GET', 'POST'])
def register_root():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        new_admin = Admin(email=email, password=password)
        db.session.add(new_admin)
        db.session.commit()

        flash('Registro exitoso', 'success')
        return redirect(url_for('login_root'))

    return render_template('register_root.html')

# Login root
@app.route('/login_root', methods=['GET', 'POST'])
def login_root():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Verificar si las credenciales son correctas
        admin = Admin.query.filter_by(email=email, password=password).first()
        
        if admin:
            # Si las credenciales son correctas, redirigir a login_root_success.html
            return redirect(url_for('login_root_success'))
        else:
            flash('Credenciales incorrectas. Intenta nuevamente.', 'danger')

    return render_template('login_root.html')

# Ruta para la página de éxito después de un inicio de sesión exitoso
@app.route('/login_root_success')
def login_root_success():
    return redirect(url_for('root_dashboard'))

# Dashboard root
@app.route('/root_dashboard')
def root_dashboard():
    users = User.query.all()
    attended_count = User.query.filter_by(attended=True).count()
    not_attended_count = User.query.filter_by(attended=False).count()
    total_count = len(users)

    return render_template('root_dashboard.html', 
                           users=users, 
                           attended_count=attended_count, 
                           not_attended_count=not_attended_count, 
                           total_count=total_count)

# Ruta para eliminar todos los registros de usuarios y asistencia
@app.route('/delete_all')
def delete_all():
    try:
        # Eliminar todos los registros de la tabla de usuarios
        User.query.delete()
        
        # Eliminar todos los registros de la tabla de asistencia
        Attendance.query.delete()
        
        # Confirmar que los datos fueron eliminados
        db.session.commit()
        flash('Todos los datos han sido eliminados con éxito.', 'success')
    except Exception as e:
        db.session.rollback()  # En caso de error, revertimos los cambios
        flash(f'Ocurrió un error al intentar eliminar los datos: {str(e)}', 'danger')

    return redirect(url_for('root_dashboard'))  # Redirigir al dashboard del root después de borrar los datos

# Ruta para crear la base de datos si no existe
@app.route('/create_db')
def create_db():
    if not os.path.exists('attendance.db'):
        db.create_all()
        return 'Base de datos creada con éxito.'
    return 'La base de datos ya existe.'

if __name__ == '__main__':
    app.run(debug=True)
