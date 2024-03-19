# Import necessary modules
import os
from flask import Flask, request, render_template, redirect, send_from_directory,session,jsonify,send_file,url_for
import pickle
import io
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from PIL import Image, ImageOps
from moviepy.editor import ImageSequenceClip, concatenate_videoclips ,concatenate_audioclips,VideoFileClip,ImageClip
from moviepy.audio.io.AudioFileClip import AudioFileClip ,AudioClip
import shutil
import cv2
import numpy as np
import base64
import urllib.parse
import time
import psycopg2
import requests
from multiprocessing import Pool

# Initialize Flask app
app = Flask(__name__, static_url_path='', static_folder='static', template_folder='static')
app.secret_key = 'Helloworld'
UPLOAD_FOLDER = 'uploads'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['JWT_SECRET_KEY'] = '140-073-212'  # Change this to a random secret key

jwt = JWTManager(app)



# Ensure the upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# db connection for render
def get_db_connection():
    # Decode the base64 certificate
    cert_decoded = base64.b64decode(os.environ['ROOT_CERT_BASE64'])
    
    # Define the path to save the certificate
    cert_path = '/opt/render/.postgresql/root.crt'
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)
    
    # Write the certificate to the file
    with open(cert_path, 'wb') as cert_file:
        cert_file.write(cert_decoded)
    
    # Set up the connection string with the path to the certificate
    conn = psycopg2.connect(
        "host=jhag21615v-8917.8nk.gcp-asia-southeast1.cockroachlabs"
        "port=26257 dbname=defaultdb user=rohan "
        "password=YyoarUCSnxqRTxK5sJdLZg sslmode=verify-full "
        f"sslrootcert={cert_path}"
    )
    return conn

# #db connection for local host
# def get_db_connection():
#     conn = psycopg2.connect("postgresql://rohan:YyoarUCSnxqRTxK5sJdLZg@jhag21615v-8917.8nk.gcp-asia-southeast1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full")
#     # print("DATABASE_URL: ", os.environ["DATABASE_URL"])
#     return conn

# Initialize database
def init_db():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Create User_Details table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT  PRIMARY KEY,
                username VARCHAR(255) UNIQUE,
                name VARCHAR(255),
                email VARCHAR(255),
                password VARCHAR(255)
            )
        """)

        # Create Images table
        cursor.execute("""CREATE TABLE IF NOT EXISTS image_details (
            image_id INT PRIMARY KEY NOT NULL ,
            username VARCHAR(255) ,
            name VARCHAR(500) NOT NULL,
            size INT NOT NULL,
            extension VARCHAR(100),
            img BYTEA
        );
        """)

        connection.commit()

        cursor.close()
        connection.close()
        
        print("Database and tables initialization successful.")

    except Exception as e:
        print(f"An error occurred during database initialization: {e}")

# Initialize database when the app starts
init_db()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')



# Route to register a new user
@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        # Retrieve form data
        username = request.form['Uname']
        name = request.form['name']
        email = request.form['email']
        password = request.form['Pass']
        confirmPassword = request.form['confrm_Pass']

        if password != confirmPassword:
            return "Passwords do not match.", 400
        
        try:
            # Hash the password
            hashed_password = generate_password_hash(password)

            # Open a connection to the database
            connection = get_db_connection()
            cursor = connection.cursor()

            # Insert user data into the database
            cursor.execute("INSERT INTO users (username, name, email, password) VALUES (%s, %s, %s, %s)",
                           (username, name, email, hashed_password))

            # Commit the transaction
            connection.commit()

            # Close cursor and connection
            cursor.close()
            connection.close()

            return redirect('/success')

        except Exception as e:
            return f"An error occurred: {e}", 500
        
        
@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        username = request.form['Uname']
        password = request.form['Pass']
        

        if username == 'admin' and password == 'admin':  # Check if it's the admin login
            try:
                connection = get_db_connection()
                cursor = connection.cursor()

                cursor.execute("SELECT id, username, name, email FROM users")
                rows = cursor.fetchall()

                users = []
                for row in rows:
                    user = {
                        'id': row[0],
                        'username': row[1],
                        'name': row[2],
                        'email': row[3]
                    }
                users.append(user)

                cursor.close()
                connection.close()

                return render_template('admin.html', users=users)

            except Exception as e:
                return f"An error occurred: {e}", 500
        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            # print(user)
            user = {
                'id': user[0],
                'username': user[1],
                'name': user[2],
                'email': user[3],
                'password': user[4]
            }

            cursor.close()
            connection.close()

            if user and check_password_hash(user['password'], password):
                # Create access token containing user identity
                access_token = create_access_token(identity=username)
                print(access_token)
                session['username'] = username
                return redirect('/home')
                

            return redirect('/fail')

        except Exception as e:
            return jsonify({'error': f"An error occurred: {e}"}), 500

@app.route('/protected')
@jwt_required()  # Require a valid JWT token for accessing this route
def protected():
    # Access the identity of the current user with get_jwt_identity
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200
        

        
@app.route('/home')
def home():
    username = session.get('username')
    if not username:
        return redirect('/')
    # print(session('username'))
    
    return render_template('home.html', username=username)

    

# Route for handling failed login attempts
@app.route('/fail')
def fail():
    return send_from_directory('static', 'invalid_credentials.html')

        

@app.route('/success')
def success():
    return send_from_directory('static', 'succes.html')

@app.route('/logout')
def logout():
    # Clear the user session
    session.clear()
    return redirect('/')  # Redirect to the home page after logout




# Route to upload images
@app.route('/upload_images', methods=['POST'])
def upload_images():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('file')

    if not files:
        return jsonify({'error': 'No files uploaded'}), 400

    try:
        # Retrieve the username from the session
        username = session.get('username')
        if not username:
            return jsonify({'error': 'User not logged in'}), 401

        connection = get_db_connection()
        cursor = connection.cursor()

        for file in files:
            if file.filename != '' and allowed_file(file.filename):  # Check if file is an image
                # Check if the file with the same name exists for the user
                cursor.execute("SELECT * FROM image_details WHERE username = %s AND name = %s", (username, file.filename))
                existing_image = cursor.fetchone()
                if existing_image:
                    return jsonify({'error': f"File '{file.filename}' already exists"}), 400
                
                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(file_path)
                # Read the file content as bytes
                with open(file_path, 'rb') as f:
                    file_blob = f.read()
                # Save image details to the MySQL table along with the current user's username
                save_image_details(
                    connection=connection,
                    cursor=cursor,
                    username=username,
                    filename=file.filename,
                    size=os.path.getsize(file_path),
                    extension=os.path.splitext(file.filename)[1],
                    blob=file_blob
                )

        connection.commit()  # Commit all changes to the database

        return jsonify({'message': 'Images uploaded successfully'}), 200

    except Exception as e:
        return jsonify({'error': f"An error occurred: {e}"}), 500

    finally:
        cursor.close()
        connection.close()


@app.route('/get_uploaded_images')
def get_uploaded_images():
    if 'username' not in session:
        return jsonify({'error': 'User not logged in'}), 401
    
    username = session['username']
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        
        cursor.execute("SELECT name FROM image_details WHERE username = %s", (username,))
        
        images = [row[0] for row in cursor.fetchall()]
        print(images)

        
        cursor.close()
        connection.close()
        
        return jsonify({'images': images})
    
    except Exception as e:
        return jsonify({'error': f"An error occurred: {e}"}), 500



@app.route('/uploads/<path:filename>')
def serve_image(filename):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Retrieve image blob based on the filename
        cursor.execute("SELECT img FROM image_details WHERE name = %s", (filename,))
        image_data = cursor.fetchone()

        cursor.close()
        connection.close()


        if image_data:
            return send_file(BytesIO(image_data[0]), mimetype='image/jpeg')  # Adjust mimetype if needed
        else:
            return jsonify({'error': 'Image not found'}), 404

    except Exception as e:
        return jsonify({'error': f"An error occurred: {e}"}), 500


# Function to check if a file is an image
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# Function to save image details to MySQL table
def save_image_details(connection, cursor, username, filename, size, extension, blob):
    try:
        # Insert image details into the table
        sql = "INSERT INTO image_details (username, name, size, extension, img) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (username, filename, size, extension, blob))
        connection.commit()  # Commit the transaction
    except Exception as e:
        print(f"Error: {e}")



@app.route('/upload_selected_images', methods=['POST'])
def upload_selected_images():
    uploaded_files = []
    for blob in request.files.getlist('file'):
        # Convert blob to image file
        image_data = blob.read()
        image_name = blob.filename
        image_path = os.path.join('selected-images', image_name)
        with open(image_path, 'wb') as f:
            f.write(image_data)
        uploaded_files.append(image_name)

    return jsonify({'message': 'Images uploaded successfully', 'files': uploaded_files}), 200






@app.route('/video')
def video(image_folder='selected-images', audio_folder='selected-audio'):
    # Capture current time
    current_time = int(time.time())

    # Clear existing videos in the video folder
    video_folder = os.path.join('static', 'video')
    if os.path.exists(video_folder):
        shutil.rmtree(video_folder)
    os.makedirs(video_folder,exist_ok=True)

    # Ensure all images are the same size or adjust the size here
    frame_size = (1920,1520)  # Example frame size, adjust to match your images

    # Calculate frame rate to show each image for 3 seconds
    image_duration = 3  # Duration each image should be shown (in seconds)
    fps = 1 / image_duration

    # Initialize video writer for MP4 format
    video_filename = 'output_video_{}.mp4'.format(current_time)
    video_path = os.path.join(video_folder, video_filename)

    # Get list of image files from image_folder
    image_files = [os.path.join(image_folder, file) for file in os.listdir(image_folder) if file.endswith(('.jpg', '.png', '.jpeg'))]

    # Clear images from selected-images folder


    # List to hold video clips for each image
    video_clips = []

    for image_path in image_files:
        # Read each image
        img = cv2.imread(image_path)
        # Check if the image is loaded successfully
        if img is None:
            # Print a warning message and skip to the next image
            print(f"Warning: Unable to read image file '{image_path}'")
            continue
        # Convert image from BGR to RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Resize image to match frame size if necessary
        img_resized = cv2.resize(img_rgb, frame_size)
        # Create video clip for the image for the duration of image_duration
        video_clips.append(ImageClip(img_resized).set_duration(image_duration))
    shutil.rmtree(image_folder)
    os.makedirs(image_folder)
    # Concatenate all video clips into one
    final_video_clip = concatenate_videoclips(video_clips, method="compose")

    # Set the fps attribute for the final video clip
    final_video_clip.fps = fps

    # Get audio file path
    audio_file = os.path.join(audio_folder, os.listdir(audio_folder)[0])  # Assuming only one audio file

    # Clear audio files from selected-audio folder


    audio_clip = AudioFileClip(audio_file)
    shutil.rmtree(audio_folder)
    os.makedirs(audio_folder)

    # Check video duration
    video_duration = final_video_clip.duration

    # Trim or repeat audio based on video duration
    if video_duration < audio_clip.duration:
        # Trim audio if video duration is less than audio duration
        audio_clip = audio_clip.subclip(0, video_duration)
    elif video_duration > audio_clip.duration:
        # Repeat audio if video duration is greater than audio duration
        # Loop the audio clip to match the duration of the video
        audio_duration = audio_clip.duration
        num_loops = int(video_duration / audio_duration) + 1  # Calculate the number of times to loop audio
        looped_audio = concatenate_audioclips([audio_clip] * num_loops)
        audio_clip = looped_audio.subclip(0, video_duration)  # Trim audio to match video duration

    # Set audio for the final video
    final_video_clip = final_video_clip.set_audio(audio_clip)

    # Write the result to a new MP4 file
    final_output_filename = 'output_video_{}.mp4'.format(current_time)
    final_video_clip.write_videofile(os.path.join(video_folder, final_output_filename), codec='libx264', audio_codec='aac')

    return jsonify({'video_url': url_for('static', filename=os.path.join('video', final_output_filename)), 'message': 'Video created successfully!'})






@app.route('/get_audio_files')
def get_audio_files():
    audio_files = os.listdir('static/audio')
    audio_data = {}
    for filename in audio_files:
        filepath = os.path.join('static/audio', filename)
        with open(filepath, 'rb') as file:
            audio_data[filename] = base64.b64encode(file.read()).decode('utf-8')
    return jsonify(audio_data)


@app.route('/select_audio', methods=['POST'])
def select_audio():
    data = request.json
    filename = data.get('filename')
    if not filename:
        return 'No filename provided.', 400

    selected_audio_folder = 'selected-audio'

    # Check if the selected-audio folder exists, and if not, create it
    if not os.path.exists(selected_audio_folder):
        os.makedirs(selected_audio_folder)
    else:
        # If the folder exists, empty it by deleting all files
        files_in_folder = os.listdir(selected_audio_folder)
        for file_in_folder in files_in_folder:
            file_path = os.path.join(selected_audio_folder, file_in_folder)
            os.remove(file_path)

    # Ensure that the selected audio file has a .mp3 extension
    filename = filename.split('.')[0] + '.mp3'

    # Convert base64 encoded audio data to bytes
    audio_data_base64 = data.get('audioData')
    audio_data = base64.b64decode(audio_data_base64)

    # Write the audio data to the selected-audio folder as an MP3 file
    selected_audio_path = os.path.join(selected_audio_folder, filename)
    with open(selected_audio_path, 'wb') as file:
        file.write(audio_data)

    return 'Audio file selected and stored successfully.', 200


@app.route('/download_video', methods=['POST'])
def download_video():
    quality = request.form.get('quality')
    video_url = request.form.get('video_url')
    video_filename = video_url.split('/')[-1]
    video_path = os.path.join(app.static_folder, 'video', video_filename)
    output_path = os.path.join(app.static_folder, 'video', f'processed_{video_filename[:-4]}_{quality}.mp4')

    try:
        clip = VideoFileClip(video_path)
        resolutions = {
            '360px': (640, 360, '500k'),
            '720px': (1280, 720, '1500k'),
            '1080px': (1920, 1080, '2500k'),
        }
        width, height, bitrate = resolutions.get(quality, (*clip.size, '2500k'))
        resized_clip = clip.resize(newsize=(width, height))
        resized_clip.write_videofile(output_path, codec='libx264', bitrate=bitrate, temp_audiofile='temp-audio.m4a', remove_temp=True, audio_codec='aac')
    except Exception as e:
        print(f"An error occurred during video processing: {e}")
        return jsonify({'error': f'Error processing video: {str(e)}'}), 500

    if os.path.isfile(output_path):
        return send_from_directory(os.path.dirname(output_path), os.path.basename(output_path), as_attachment=True)
    else:
        return jsonify({'error': 'Processed video file not found'}), 404


if __name__ == '__main__':
    app.run(debug=True)