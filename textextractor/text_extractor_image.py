# text_extractor_image.py
# from text_extractor_image import extract_text_from_image

import tempfile
import subprocess
import os
# from PIL import Image
# import io


def ocr(path) -> str:
    # path is an on-disk file
    temp = tempfile.NamedTemporaryFile(delete=False)

    process = subprocess.Popen(['tesseract', path, temp.name], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    process.communicate()

    with open(temp.name + '.txt', 'r') as handle:
        contents = handle.read()

    os.remove(temp.name + '.txt')
    os.remove(temp.name)

    return contents


def extract_text_from_image(image_path) -> str:
    print(f'Extracting text from image: {image_path}')
    xstr = ocr(image_path)
    return xstr

# use code below to handle case where image is bytes in memory (e.g. image embedded in PDF)

# pil_im = Image.fromarray(image)
# b = io.BytesIO()

# Image.open(image_path)

#  buffer = io.BytesIO(elem.stream.get_data())
#                             image_suffix = determine_image_type(buffer.getvalue()[0:3])
#                             if not image_suffix:
#                                 image_suffix = '.png'

# # print(f'Image type: {determine_image_type(buffer.getvalue()[0:3])}')
# pillow_object = Image.open(image_path)
# image_temp_file = tempfile.NamedTemporaryFile(suffix=image_suffix, delete=False)
# # print(image_temp_file.name)
# pillow_object.save(image_temp_file.name)
