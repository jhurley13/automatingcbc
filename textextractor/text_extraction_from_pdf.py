# text_extraction_from_pdf
# import text_extraction_from_pdf

import io
import os
import subprocess
import tempfile
from binascii import b2a_hex
from io import StringIO
from pathlib import Path
from typing import BinaryIO
from typing import Tuple

from PIL import Image
from pdfminer.high_level import extract_pages
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from pdfminer.layout import LTFigure, LTImage
from pdfminer.layout import LTTextContainer


# References
# https://github.com/pdfminer/pdfminer.six/issues/144
# https://denis.papathanasiou.org/archive/2010.08.04.post.pdf
# https://pythonprogramminglanguage.com/extract-text-from-image/
# https://romanvm.pythonanywhere.com/post/extracting-text-pdf-using-python-34/
# https://stackoverflow.com/questions/38317327/python-pdfminer-extract-image-produces-multiple-images-per-page-should-be-singl

def extract_all_text_from_pdf(fpath: Path) -> Tuple[str, bool]:
    all_text = ''
    processed_image = False
    for page_layout in extract_pages(fpath.as_posix()):
        for element in page_layout:
            #         print(element)
            if isinstance(element, LTTextContainer):
                all_text += element.get_text()
            elif isinstance(element, LTFigure):
                # print('found image')
                for elem in element:
                    # print(elem, isinstance(element, LTImage))
                    if True:  # isinstance(element, LTImage) and elem.stream:
                        image_suffix = None
                        try:
                            buffer = io.BytesIO(elem.stream.get_data())
                            image_suffix = determine_image_type(buffer.getvalue()[0:3])
                            if not image_suffix:
                                image_suffix = '.png'

                            # print(f'Image type: {determine_image_type(buffer.getvalue()[0:3])}')
                            pillow_object = Image.open(buffer)
                            image_temp_file = tempfile.NamedTemporaryFile(suffix=image_suffix, delete=False)
                            # print(image_temp_file.name)
                            pillow_object.save(image_temp_file.name)
                            xstr = ocr(image_temp_file.name)
                            # print(xstr)
                            text = '\n'.join(list(filter(lambda xs: len(xs.strip()) > 0, xstr.split('\n'))))
                            all_text += text
                            processed_image = True
                        except Exception as ee:
                            # print(f'elem.stream: {ee}') #, buf: {buffer.getvalue()[0:6]}')
                            pass
                            # with open("debug_buffer.imgx", 'wb') as fp:
                            #     fp.write(buffer.read())

    # if hasattr(a, 'property'):
    #     a.property

    return all_text, processed_image


def ocr(path):
    temp = tempfile.NamedTemporaryFile(delete=False)

    process = subprocess.Popen(['tesseract', path, temp.name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    process.communicate()

    with open(temp.name + '.txt', 'r') as handle:
        contents = handle.read()

    os.remove(temp.name + '.txt')
    os.remove(temp.name)

    return contents


def extract_text_from_pdf_bio(pdf_fo: BinaryIO) -> str:
    """
    Extracts text from a PDF

    :param pdf_fo: a byte file object representing a PDF file
    :return: extracted text
    :raises pdfminer.pdftypes.PDFException: on invalid PDF
    """
    out_fo = StringIO()
    layout = LAParams(all_texts=True)
    extract_text_to_fp(pdf_fo, out_fo, laparams=layout)
    return out_fo.getvalue()


def extract_text_from_pdf(fpath: Path) -> str:
    with open(fpath, "rb") as fp:
        text_result = extract_text_from_pdf_bio(fp)

    return text_result


def determine_image_type(stream_first_4_bytes):
    """Find out the image file type based on the magic number comparison of the first 4 (or 2) bytes"""
    file_type = None
    bytes_as_hex = b2a_hex(stream_first_4_bytes).decode()
    if bytes_as_hex.startswith('ffd8'):
        file_type = '.jpeg'
    elif bytes_as_hex == '89504e47':
        file_type = '.png'
    elif bytes_as_hex == '47494638':
        file_type = '.gif'
    elif bytes_as_hex.startswith('424d'):
        file_type = '.bmp'
    return file_type
