import requests

api_url = "http://127.0.0.1:8000/upload_pdf/"
files = {'file': open("D:/pdfs/sample1_pdf.pdf", 'rb')}
params = {'voice_gender': 'female'} 
response = requests.post(api_url, files=files, params=params)
if response.status_code == 200:
    with open(f"combined_audio.mp3", "wb") as file:
        file.write(response.content)
else:
    print(f"Request failed with status code: {response.status_code}")
    print(response.text)