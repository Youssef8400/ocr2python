
import datetime
import io
import os
import numpy as np
import cv2
from PIL import Image
import subprocess
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
#from PassportEye.passporteye.util.pdf import extract_first_jpeg_in_pdf
from skimage import io as skimage_io, transform
import nltk
from nltk.corpus import names
from nltk.metrics import edit_distance

nltk.download('names')

class Loader:
    def __init__(self, file=None):
        self.file = file

    def __call__(self):
        if isinstance(self.file, str):
            if self.file.lower().endswith('.pdf'):
                with open(self.file, 'rb') as f:
                #    img_data = extract_first_jpeg_in_pdf(f)
                #if img_data is None:
                    return None
                #return skimage_io.imread(img_data, as_gray=False)
            else:
                return skimage_io.imread(self.file, as_gray=False)
        elif isinstance(self.file, (bytes, io.IOBase)):
            return skimage_io.imread(self.file, as_gray=False)
        return None

class Scaler:
    def __init__(self, max_width=250):
        self.max_width = max_width

    def __call__(self, img):
        scale_factor = self.max_width / float(img.shape[1])
        if scale_factor <= 1:
            img_small = transform.rescale(img, scale_factor, mode='constant', channel_axis=None, anti_aliasing=True)
        else:
            scale_factor = 1.0
            img_small = img
        return img_small, scale_factor

class Document:
    def __init__(self, document_type, country_code, first_name, last_name, document_number, sex, birth_date, expire_date):
        self.document_type = document_type
        self.country_code = country_code
        self.first_name = first_name
        self.last_name = last_name
        self.document_number = document_number
        self.sex = sex
        self.birth_date = birth_date
        self.expire_date = expire_date

    def to_dict(self):
        return {
            "documentType": self.document_type,
            "countryCode": self.country_code,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "documentNumber": self.document_number,
            "sex": self.sex,
            "birthDate": self.birth_date,
            "expireDate": self.expire_date
        }

def parse_mrz(mrz_text):
    lines = mrz_text.split('\n')
    lines = [line.replace('\u003c', '<') for line in lines]

    if len(lines) < 2:
        raise ValueError("Invalid MRZ data: less than 2 lines")
    elif len(lines) == 2:
        return parse_passport(lines[0], lines[1])
    elif len(lines) == 3:
        return parse_id_card(lines[0], lines[1], lines[2])
    else:
        raise ValueError("Unknown MRZ format")

def parse_passport(line1, line2):
    document_type = my_trim(line1[0:2])
    country_code = my_trim(line1[2:5])
    names = line1[5:]
    first_name, last_name = get_names(names)
    document_number = my_trim(line2[0:9])
    sex_index = find_closest_sex(line2, 20)
    sex, birth_date, expire_date = None, None, None

    if sex_index != -1:
        sex = line2[sex_index]
        birth_date = stringify_date(line2[sex_index-7:sex_index-1], "birth")
        expire_date = stringify_date(line2[sex_index+1:sex_index+7], "expire")

    return Document(document_type, country_code, first_name, last_name, document_number, sex, birth_date, expire_date)

def parse_id_card(line1, line2, line3):
    document_type = my_trim(line1[0:2])
    country_code = my_trim(line1[2:5])
    first_name, last_name = get_names(line3)
    document_number = get_cnie(line1)
    sex_index = find_closest_sex(line2, 7)
    sex, birth_date, expire_date = None, None, None

    if sex_index != -1:
        sex = line2[sex_index]
        birth_date = stringify_date(line2[sex_index-7:sex_index-1], "birth")
        expire_date = stringify_date(line2[sex_index+1:sex_index+7], "expire")

    return Document(document_type, country_code, first_name, last_name, document_number, sex, birth_date, expire_date)

def get_names(text):
    parts = text.split('<<')
    parts = [part for part in parts if part]
    last_name = parts[0].replace('<', ' ').strip() if parts else ""
    first_name = ' '.join(parts[1:]).replace('<', ' ').strip() if len(parts) > 1 else ""
    return first_name, last_name

def stringify_date(text, date_type):
    if len(text) != 6:
        return "Invalid input length"

    year = int(text[:2])
    month = text[2:4]
    day = text[4:]

    current_year = datetime.datetime.now().year % 100

    if date_type == "expire":
        year += 2000
    elif date_type == "birth":
        year += 1900 if year > current_year else 2000

    return f"{day}/{month}/{year}"

def my_trim(input_str):
    return input_str.replace('<', ' ').strip()

def find_closest_sex(line, index):
    i, j = index, index
    while True:
        if i >= len(line) and j < 0:
            return -1
        if i < len(line) and line[i] in 'FM':
            return i
        if j >= 0 and line[j] in 'FM':
            return j
        i += 1
        j -= 1

def get_cnie(text):
    for i in range(len(text) - 1, -1, -1):
        if not text[i].isdigit() and text[i] != '<' and text[i] != ' ':
            return text[i:].replace('<', ' ').strip()
    return ""

def get_content(image):
    try:
        result = subprocess.run(['tesseract', image, 'stdout', '--psm', '6'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        return str(e)

def correct_name(name):
    common_names = names.words('male.txt') + names.words('female.txt')
    distances = [(edit_distance(name.lower(), common_name.lower()), common_name) for common_name in common_names]
    closest_name = min(distances, key=lambda x: x[0])[1]
    return closest_name.capitalize()

def eliminate_repeated_letters(name):
    counts = {}
    result = []

    for char in name:
        if char.isalpha():
            counts[char] = counts.get(char, 0) + 1
            if counts[char] <= 2:
                result.append(char)

    return ''.join(result)

class OCRAdapter:
    def parse_document(self, image):
        text = get_content(image)
        if not text:
            raise ValueError("OCR failed to extract content")
        
        corrected_first_name = eliminate_repeated_letters("prénom à corriger")
        corrected_last_name = eliminate_repeated_letters("nom à corriger")
        
        mrz_text = [line.strip() for line in text.split('\n') if line.count('<') > 5]
        document = parse_mrz('\n'.join(mrz_text))

        return document.to_dict()

class APIPort:
    def get_document_data(self, filepath):
        adapter = OCRAdapter()
        return adapter.parse_document(filepath)

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/get-document-data/")
async def get_document_data(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        with open("temp_image", "wb") as temp_file:
            temp_file.write(contents)
        
        api_port = APIPort()
        document = api_port.get_document_data("temp_image")
        
        return document
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class OCRScannerPort:
    def parse_document(self, image):
        adapter = OCRAdapter()
        return adapter.parse_document(image)

if __name__ == "__main__":
    file_path = "chemin_vers_image_ou_pdf"
    
    loader = Loader(file=file_path)
    img = loader()

    if img is not None:
        scaler = Scaler(max_width=250)
        img_small, scale_factor = scaler(img)
        print("Image redimensionnée avec succès")
    else:
        print("Échec du chargement de l'image")

def getNBImage(img):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = img.astype(np.uint8)

    dst = cv2.fastNlMeansDenoising(img, None, 8, 7, 21)

    ret, thresh = cv2.threshold(dst, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return np.invert(thresh)

def crop_image(im):
    width, height = im.size

    startx = 0
    starty = height * 0.75
    endx = width * 0.5
    endy = height
    cropImageCE = getNBImage(np.asarray(im.crop((int(startx), int(starty), int(endx), int(endy)))))

    startx = 0
    starty = 0
    endx = width
    endy = height * 0.30
    cropImageTOP = getNBImage(np.asarray(im.crop((int(startx), int(starty), int(endx), int(endy)))))


    startx = 0
    starty = height * 0.75
    endx = width
    endy = height
    cropImageBOT = getNBImage(np.asarray(im.crop((int(startx), int(starty), int(endx), int(endy)))))

    return cropImageCE, cropImageTOP, cropImageBOT

def get_text(folder, folder_base):
    outputFolder = folder
    for file in os.listdir(folder_base):
        if file.endswith(".jpg"):
            file_path = os.path.join(folder_base, file)
            
            loader = Loader(file=file_path)
            img = loader()
            if img is not None:
                scaler = Scaler(max_width=250)
                img_small, scale_factor = scaler(img)
                
                im = Image.fromarray((img_small * 255).astype(np.uint8))
                
                cropImageCE, cropImageTOP, cropImageBOT = crop_image(im)
                
                Image.fromarray(cropImageCE).save('cropCE.jpg')
                Image.fromarray(cropImageTOP).save('cropTOP.jpg')
                Image.fromarray(cropImageBOT).save('cropBOT.jpg')
                
                os.system('tesseract cropCE.jpg ' + os.path.join(outputFolder, file + "CE"))
                os.system('tesseract cropTOP.jpg ' + os.path.join(outputFolder, file + "TOP"))
                os.system('tesseract cropBOT.jpg ' + os.path.join(outputFolder, file + "BOT"))
                
    os.remove("cropCE.jpg")
    os.remove("cropTOP.jpg")
    os.remove("cropBOT.jpg")
