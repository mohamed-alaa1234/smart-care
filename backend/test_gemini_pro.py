import os
import google.generativeai as genai

genai.configure(api_key="AIzaSyCl8GYW_9cFoMsBVj1H28wQKssvtrM3bD4")

try:
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content("Hello")
    print("Success:", response.text)
except Exception as e:
    print("Error:", str(e))
