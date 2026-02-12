import requests
from PIL import Image
from io import BytesIO
from os import getcwd

def generate_image(text):
    url = 'https://api.airforce/v1/imagine2'
    params = {'prompt': text}
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            try:
                image = Image.open(BytesIO(response.content))
                save_path = f"{getcwd()}\\generated_image.png"
                image.save(save_path)
                image.show()
                print(f'Image saved as {save_path}')
            except Exception as img_err:
                print(f"Error processing image: {img_err}")
        else:
            print(f'Failed to retrieve image. Status code: {response.status_code}')
    except Exception as e:
        print(f"Request failed: {e}")
