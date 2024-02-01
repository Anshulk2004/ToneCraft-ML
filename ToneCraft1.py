from flask import Flask, request, send_file, Response
import PyPDF2
import boto3
import base64
import os
import joblib
from io import BytesIO
import config
from flask_cors import CORS

app = Flask(__name__)
# app.config['UPLOAD_EXTENSIONS'] = ['.pdf']
# app.config['UPLOAD_PATH'] = './upload'
CORS(app)

def get_settings():
    return config.Settings()

pipe_lr = joblib.load(open("./emotion_classifier_pipe_lr.pkl", "rb"))

def predict_emotion(docx):
    results = pipe_lr.predict([docx])
    return results[0]

def pdf_to_text(pdf_content):
    temp_pdf_path = "temp_pdf.pdf"
    with open(temp_pdf_path, "wb") as temp_pdf_file:
        temp_pdf_file.write(pdf_content)

    pdf_reader = PyPDF2.PdfReader(temp_pdf_path)
     
    text = ''
    if pdf_reader.pages:
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()

    os.remove(temp_pdf_path)
    return text

def applying_basic_polly(text, speaking_rate=1.2, volume='soft', pitch='medium', emphasis='none'):
    ssml_tags = f"<speak><amazon:effect name='drc'><prosody rate='{speaking_rate}' volume='{volume}' pitch='{pitch}'><emphasis level='{emphasis}'>{text}</emphasis></prosody></amazon:effect></speak>"
    return ssml_tags

def polly(text, emotion):
    if emotion == 'anger':
        text = applying_basic_polly(text, speaking_rate=1.3, volume='loud', emphasis='strong')
    elif emotion == 'disgust' or emotion == 'sad' or emotion == 'sadness' or emotion == 'shame':
        text = applying_basic_polly(text, speaking_rate=1.3, volume='soft', pitch='medium', emphasis='reduced')
    elif emotion == 'happy' or emotion == 'joy':
        text = applying_basic_polly(text, speaking_rate=1.3, volume='medium', emphasis='moderate')
    elif emotion == 'fear':
        text = applying_basic_polly(text, speaking_rate=1.3, volume='medium', pitch='medium', emphasis='strong')
    elif emotion == 'surprise':
        text = applying_basic_polly(text, speaking_rate=1.3, volume='medium', emphasis='moderate')
    elif emotion == 'neutral':
        text = applying_basic_polly(text, speaking_rate=1.2, volume='soft', pitch='medium', emphasis='none')
    return text



def generate_audio(text, output_format="mp3"):
    emotion = predict_emotion(text)
    text = polly(text,emotion)
    client = boto3.client('polly', aws_access_key_id=get_settings().AWS_AK, aws_secret_access_key=get_settings().AWS_SAK, region_name='us-east-1')
    voice_id = 'Matthew'
    results = client.synthesize_speech(Text=text, OutputFormat=output_format, VoiceId=voice_id, TextType='ssml')
    audio = results['AudioStream'].read()
    encoded_audio = base64.b64encode(audio).decode('utf-8')
    return encoded_audio

def create_audio_folder():
    folder_name = "audio_folder"
    folder_path = os.path.join(os.getcwd(), folder_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    return folder_path

def clean_audio_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                os.rmdir(file_path)
        except Exception as e:
            print(f"Error: {e}")

@app.route("/upload/", methods=["POST"])
def upload_pdf():
    try:
        file = request.data
    
        pdf_text = pdf_to_text(file)
        chunk_size = 400
        text_chunks = [pdf_text[i:i+chunk_size] for i in range(0, len(pdf_text), chunk_size)]

        audio_folder = create_audio_folder()
        audio_files = []
        for i, chunk in enumerate(text_chunks):
            audio_data = generate_audio(chunk) # generate
            audio_filename = os.path.join(audio_folder, f"audio_chunk_{i + 1}.mp3")
            audio_files.append(audio_filename)
            with open(audio_filename, "wb") as audio_file:
                audio_file.write(base64.b64decode(audio_data))

        combined_audio = BytesIO()
        for audio_file in audio_files:
            with open(audio_file, "rb") as file:
                combined_audio.write(file.read())

        combined_audio.seek(0)
        clean_audio_folder(audio_folder)
        return send_file(combined_audio, as_attachment=True,download_name='combined_audio.mp3')

    except Exception as e:
        print(e)        
        return str(e), 500

@app.route("/", methods=["GET"])
def home():
    return {'connected': True}

if __name__ == "__main__":
    app.run(debug=True)