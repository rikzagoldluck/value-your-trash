import time
import bcrypt
import numpy as np
from flask import Flask, render_template, request, send_from_directory, redirect, url_for, session
import paho.mqtt.client as mqtt
from flask_session import Session
import pymysql

import cv2
import cvlib as cv
import numpy as np
from cvlib.object_detection import draw_bbox

im = None
app = Flask(__name__)

result = None
id_for_add_point = None
# MQTT Configuration
mqttBroker = '192.168.43.18'
mqttPort = 1883
# mqttTopic = 'sd01/to-server/img'

# Set up the MySQL database
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'hargaisampahmu'


def get_mysql_connection():
    connection = pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        db=app.config['MYSQL_DB'],
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection


# Set up the session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = '@Rikza09'
Session(app)

# MQTT Callbacks


def on_connect(client, userdata, flags, rc):
    print('Connected to MQTT broker with result code ' + str(rc))
    # client.subscribe(mqttTopic)


def on_message(client, userdata, message):
    global result
    if message.topic.endswith('img'):
        try:
            # raise Exception("Anticipate two times call")
            print(message.topic)
            result = image_proccess(message.payload, message.topic)
            mqttClient.publish('sd01/to-me/res', result['status_code'])
        except Exception as e:
            print(e)
            result = {
                'status_code': 0,
                'status': 'error',
                'message': 'Mohon Maaf, Terjadi kesalahan pada server kami, silahkan coba beberapa saat lagi (01)'
            }
        mqttClient.unsubscribe(message.topic)
    elif message.topic.endswith('bin'):
        connection = get_mysql_connection()
        with connection:
            with connection.cursor() as cursor:
                cursor.execute('UPDATE bin SET tinggi_aktual = %s WHERE id_bin = %s',
                               (message.payload, message.topic.split('/')[0]))
                connection.commit()
        mqttClient.unsubscribe(message.topic)


# Create MQTT Client
mqttClient = mqtt.Client(clean_session=True)
mqttClient.on_connect = on_connect
mqttClient.on_message = on_message
mqttClient.connect(mqttBroker, mqttPort, 60)


@app.errorhandler(404)
def page_not_found(error):
    if user_check():
        # GET username from database
        connection = get_mysql_connection()
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT u.username, g.badge, g.point FROM users AS u JOIN gamification as g ON u.id = g.user_id WHERE u.id = %s', (session['user_id'],))
                user = cursor.fetchone()
                return render_template('404.html', util={'title': '404', 'user': user}), 404
    else:
        return render_template('404.html', util={'title': '404', 'user': None}), 404


@app.route('/')
def index():
    if user_check():
        # GET username from database
        connection = get_mysql_connection()
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT u.username, g.badge FROM users AS u JOIN gamification as g ON u.id = g.user_id WHERE u.id = %s', (session['user_id'],))
                user = cursor.fetchone()

                cursor.execute(
                    'SELECT role FROM user_role WHERE user_id = %s', (session['user_id'],))
                role = cursor.fetchone()
                if role:
                    user['role'] = role['role']
                else:
                    user['role'] = 'user'
                return render_template('index1.html', util={'title': 'Home', 'user': user})
    else:
        return render_template('index1.html', util={'title': 'Home', 'user': None})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Connect to the MySQL database
        connection = get_mysql_connection()

        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT id, username, password FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()

                if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                    session['user_id'] = user['id']
                    return redirect('/')
                else:
                    error = 'Invalid username or password'
                    return render_template('login.html', error=error, util={'title': 'Login'})
    return render_template('login.html', util={'title': 'Login'})


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        # Validate the username (no white spaces allowed)
        if ' ' in username:
            error = 'Username tidak boleh ada spasi.'
        # Validate the confirm password
        elif password != confirm_password:
            error = 'Password tidak sama.'
        else:
            # Check if the username already exists in the database
            connection = get_mysql_connection()
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'SELECT id FROM users WHERE username = %s', (username,))
                    user = cursor.fetchone()

                    if user:
                        error = 'Username sudah ada. Tolong cari username lain.'
                    else:
                        # If all validations pass, proceed to register the user
                        hashed_password = bcrypt.hashpw(password.encode(
                            'utf-8'), bcrypt.gensalt()).decode('utf-8')
                        with connection.cursor() as cursor:
                            cursor.execute(
                                'INSERT INTO users (username, password) VALUES (%s, %s)', (username, hashed_password))
                            lastid = cursor.lastrowid
                            cursor.execute(
                                'INSERT INTO gamification (user_id) VALUES (%s)', (lastid))
                            connection.commit()
                            session['user_id'] = lastid
                            return redirect('/login')

    return render_template('register.html', util={'title': 'Daftar'}, error=error)


@app.route('/logout')
def logout():
    # Clear the session data (log out the user)
    session.clear()
    return redirect(url_for('login'))


@app.route('/scan', methods=['POST', 'GET'])
def qr_code_reader():
    global id_for_add_point
    global result
    # Get body from reques

    if request.method == 'POST':
        body = request.get_json()
        topic = body['topic']
        if topic:
            id_for_add_point = session['user_id']
            mqttClient.subscribe(topic + '/to-server/#', qos=1)
            mqttClient.publish(topic + '/to-me/img', "take")
            time.sleep(3)
            if result == None or result == False:
                time.sleep(5)
                if result == None or result == False:
                    result = None
                    return {
                        'status': 'error',
                        'message': 'Mohon maaf, terjadi kendala pada server kami. Silahkan coba lagi nanti. (03)',
                        'status_code': 0
                    }
                else:
                    lokal_result = result
                    result = None
                    return lokal_result
            else:
                lokal_result = result
                result = None
                return lokal_result

    return render_template('scan.html', util={'title': 'Scan', 'user': 'User'})


@app.route('/penukaran')
def penukaran():
    if user_check():
        # GET username from database
        connection = get_mysql_connection()
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT u.username, g.badge, g.point FROM users AS u JOIN gamification as g ON u.id = g.user_id WHERE u.id = %s', (session['user_id'],))
                user = cursor.fetchone()
                return render_template('penukaran.html', util={'title': 'Penukaran', 'user': user})
    else:
        return render_template('penukaran.html', util={'title': 'Penukaran', 'user': None})


@app.route('/profil')
def profil():
    if user_check():
        connection = get_mysql_connection()
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT u.username, g.badge, g.point FROM users AS u JOIN gamification as g ON u.id = g.user_id  WHERE u.id = %s', (session['user_id'],))
                user = cursor.fetchone()
                return render_template('profil.html', util={'title': 'Profil', 'user': user})
    else:
        return render_template('profil.html', util={'title': 'Profil', 'user': None})


@app.route('/static/<path:path>')
def send_report(path):
    return send_from_directory('static', path)


@app.route('/admin/capacity-bin')
def capacity_bin():
    if user_admin_check():
        # mqttClient.publish('bin/1/to-me/capacity', "take")
        connection = get_mysql_connection()
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT id_bin FROM bin')
                capacity_bin = cursor.fetchall()
                for i in capacity_bin:
                    mqttClient.publish(
                        str(i['id_bin']) + '/to-me/bin', "take")
                    time.sleep(1)
                time.sleep(5)
                cursor.execute(
                    'SELECT * FROM bin')
                bins = cursor.fetchall()
                return render_template('capacity-bin.html', util={'title': 'Capacity Bin'}, bins=bins)
    else:
        return redirect('/login')


def user_check():
    if 'user_id' in session:
        return True
    else:
        return False


def user_admin_check():
    if 'user_id' in session:
        connection = get_mysql_connection()
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT role FROM user_role WHERE id = %s', (session['user_id'],))
                user = cursor.fetchone()

                if user == None:
                    return False
                if user['role'] == 'admin':
                    return True
                else:
                    return False
    else:
        return False


def bottle_check_on_image(labels):
    if (len(labels) < 1):
        print('No object detected')
        return False

    # if not any bottle in label
    if not any('bottle' in s for s in labels):
        print('No bottle detected')
        return False
    return True


def add_point_to_user(count_bottle):
    global id_for_add_point
    # GET POINT BY USER ID AND ADD POINT MULTIPLY 10 TIMES BY COUNT BOTTLE

    connection = get_mysql_connection()
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT point FROM gamification WHERE user_id = %s', (id_for_add_point,))
            point = cursor.fetchone()
            point = point['point']
            new_point = count_bottle*10
            point = point + new_point
            cursor.execute(
                'UPDATE gamification SET point = %s WHERE user_id = %s', (point, id_for_add_point))
            connection.commit()
    id_for_add_point = None
    return new_point


def image_proccess(payload, topic):
    try:
        imgnp = np.array(bytearray(payload), dtype=np.uint8)
        imagers = cv2.imdecode(imgnp, cv2.IMREAD_COLOR)
        # resized_image = cv2.resize(image, None, fx=0.5, fy=0.5)
        # new_width = 800
        # new_height = int(image.shape[0] * (new_width / image.shape[1]))
        # resized_image = cv2.resize(image, (new_width, new_height))
        bbox, label, conf = cv.detect_common_objects(imagers,   confidence=0.1)
        im = draw_bbox(imagers, bbox, label, conf)
        topic = topic.split('/')[0]
        cv2.imwrite("last-scanned-at-" + topic + ".jpg", im)
        # cv2.imshow("object-detection", img_res)
        for l, c in zip(label, conf):
            print(f"Detected object: {l} with confidence level of {c}n")

        if not bottle_check_on_image(label):
            return {
                'status_code': 2,
                'status': 'success',
                'message': 'No bottle detected',
            }

        count_bottle = label.count('bottle')
        print(f"Detected {count_bottle} bottle")
        new_point = add_point_to_user(count_bottle)
        print(f"New point: {new_point}")
        return {
            'status_code': 1,
            'status': 'success',
            'message': 'Bottle detected',
            'bottle': count_bottle,
            'new_point': new_point
        }
    except Exception as e:
        print(f"Error displaying the image: {e}")
        return {
            'status': 'error',
            'status_code': 0,
            'message': 'Mohon maaf, Terjadi kesalahan pada server kami! Silakan coba lagi nanti! (02)'
        }


if __name__ == '__main__':
    # with concurrent.futures.ProcessPoolExecutor() as executer:
    # f1 = executer.submit(qr_code_reader)
    mqttClient.loop_start()  # Start the MQTT client loop
    app.run(host='0.0.0.0', port=5000, debug=True,
            ssl_context=('cert.pem', 'key.pem'))
