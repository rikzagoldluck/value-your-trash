import pymysqlpool
import time
import bcrypt
import numpy as np
from flask import Flask, render_template, request, send_from_directory, redirect, url_for, session
import paho.mqtt.client as mqtt
from flask_session import Session

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

pool = pymysqlpool.ConnectionPool(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    db=app.config['MYSQL_DB'],
    port=3306,
    autocommit=True,  # Set to True if you want autocommit mode
)


def execute_query(sql_query, args=None, lastrowid=False, fetch_type='ALL'):
    with pool.get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                query_type = sql_query.strip().split(' ', 1)[0].upper()
                if query_type == 'SELECT':
                    cursor.execute(sql_query, args)
                    if fetch_type == 'ALL':
                        return cursor.fetchall()
                    elif fetch_type == 'ONE':
                        return cursor.fetchone()
                else:
                    cursor.execute(sql_query, args)
                    if query_type == 'INSERT' and lastrowid:
                        return cursor.lastrowid  # Return the last inserted row ID
                    else:
                        return cursor.rowcount  # Return the number of affected rows
            except Exception as e:
                print(f"Error executing query: {e}")
                return None


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
        execute_query('UPDATE bin SET tinggi_aktual = %s WHERE id_bin = %s',
                      (message.payload, message.topic.split('/')[0]))
        mqttClient.unsubscribe(message.topic)


# Create MQTT Client
mqttClient = mqtt.Client(clean_session=True)
mqttClient.on_connect = on_connect
mqttClient.on_message = on_message
mqttClient.connect(mqttBroker, mqttPort, 60)


@app.route('/')
def index():
    if user_check():
        # GET username from database

        user = execute_query(
            'SELECT u.username, g.badge FROM users AS u JOIN gamification as g ON u.id = g.user_id WHERE u.id = %s', (session['user_id']), fetch_type='ONE')

        role = execute_query(
            'SELECT role FROM user_role WHERE user_id = %s', (session['user_id']), fetch_type='ONE')
        print(user)
        if role:
            user['role'] = role[0]
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

        user = execute_query(
            'SELECT id, username, password FROM users WHERE username = %s', (username))
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
            user = execute_query(
                'SELECT id FROM users WHERE username = %s', (username))

            if user:
                error = 'Username sudah ada. Tolong cari username lain.'
            else:
                # If all validations pass, proceed to register the user
                hashed_password = bcrypt.hashpw(password.encode(
                    'utf-8'), bcrypt.gensalt()).decode('utf-8')

                lastid = execute_query('INSERT INTO users (username, password) VALUES (%s, %s)', (
                    username, hashed_password), lastrowid=True)
                rowcount = execute_query(
                    'INSERT INTO gamification (user_id) VALUES (%s)', (lastid))
                if rowcount > 0:
                    session['user_id'] = lastid
                else:
                    error = 'Terjadi kesalahan pada server kami, silahkan coba beberapa saat lagi (01)'
                    return render_template('register.html', util={'title': 'Daftar'}, error=error)

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


@app.route('/profil')
def profil():
    if user_check():

        user = execute_query(
            'SELECT u.username, g.badge, g.point FROM users AS u JOIN gamification as g ON u.id = g.user_id  WHERE u.id = %s', (session['user_id']))
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
        capacity_bin = execute_query('SELECT id_bin FROM bin')
        for i in capacity_bin:
            mqttClient.publish(
                str(i['id_bin']) + '/to-me/bin', "take")
            time.sleep(1)
        time.sleep(5)
        bins = execute_query(
            'SELECT * FROM bin')
        return render_template('capacity-bin.html', util={'title': 'Capacity Bin', 'bins': bins})
    else:
        return redirect('/login')


def user_check():
    if 'user_id' in session:
        return True
    else:
        return False


def user_admin_check():
    if 'user_id' in session:

        user = execute_query(
            'SELECT role FROM user_role WHERE id = %s', (session['user_id']))

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

    point = execute_query(
        'SELECT point FROM gamification WHERE user_id = %s', (id_for_add_point))
    point = point['point']
    new_point = count_bottle*10
    point = point + new_point
    rowcount = execute_query(
        'UPDATE gamification SET point = %s WHERE user_id = %s', (point, id_for_add_point))
    id_for_add_point = None
    if rowcount > 0:
        return new_point
    else:
        raise Exception(
            'Terjadi kesalahan pada server kami, silahkan coba beberapa saat lagi (02)')


def image_proccess(payload, topic):
    try:
        imgnp = np.array(bytearray(payload), dtype=np.uint8)
        imdecode = cv2.imdecode(imgnp, -1)
        bbox, label, conf = cv.detect_common_objects(imdecode)
        im = draw_bbox(imdecode, bbox, label, conf)

        cv2.imwrite("last-scanned-at-" + topic.split('/')[0] + ".jpg", im)
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
