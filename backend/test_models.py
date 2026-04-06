import os
import google.generativeai as genai

genai.configure(api_key="AIzaSyCl8GYW_9cFoMsBVj1H28wQKssvtrM3bD4")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
