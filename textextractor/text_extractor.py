from more_itertools import unique_everseen

# Local Imports
from utilities_cbc import read_excel_or_csv_path, circle_abbrev_from_path
from docx2python import docx2python
from text_extraction_from_pdf import extract_all_text_from_pdf

from text_extractor_image import extract_text_from_image

from singleton_decorator import singleton


# https://realpython.com/factory-method-python/

# ------------------------------------------------------------------------
# Extractions
# ------------------------------------------------------------------------

@singleton
class TextExtractorFactory(object):

    def __init__(self):
        self._extractors = {}
        self._formats = set()
        for fmt in ['.xlsx', '.csv']:
            self.register_format(fmt, ExcelTextExtractor)
        self.register_format('.txt', PlainTextExtractor)
        self.register_format('.pdf', PDFTextExtractor)
        self.register_format('.docx', MSWordExtractor)
        for fmt in ['.jpg', '.png', '.jpeg']:
            self.register_format(fmt, ImageTextExtractor)

    def register_format(self, format, extractor):
        # print(f'Registering format {fmt}')
        self._formats.add(format)
        self._extractors[format] = extractor

    def get_extractor(self, fpath):
        suffix = fpath.suffix
        extractor = self._extractors.get(suffix)
        if not extractor:
            raise ValueError(format)
        return extractor(fpath)

    def create(self, fpath):
        extractor_class = self.get_extractor(fpath)
        # print(extractor_class, extractor_class.fpath)
        return extractor_class

    def formats(self):
        return self._formats


class TextExtractor(object):
    def __init__(self, fpath):
        self.fpath = fpath
        self.suffix = fpath.suffix
        self.circle = circle_abbrev_from_path(fpath)
        self.lines = []
        self.text = ''

    def extract(self, unique: bool = True) -> str:
        self.text = self._extract()
        self.lines = self.text.split('\n')
        if unique:
            self.lines = list(unique_everseen(self.lines))
        return self.text

    def _extract(self) -> str:
        # Override
        return 'BASE - OVERRIDE'


class ExcelTextExtractor(TextExtractor):
    def _extract(self) -> str:
        alltext = ''
        df = read_excel_or_csv_path(self.fpath, None)
        for ix, item in enumerate(df.iteritems()):
            text = '\n'.join(map(str, list(item[1].values)))
            alltext += text + '\n'

        return alltext


class PlainTextExtractor(TextExtractor):
    def _extract(self) -> str:
        text = ''
        try:
            with open(self.fpath, 'r', encoding="utf-8") as fp:
                text = fp.read()
                print(len(text))
                # if unique:
                #     text = '\n'.join(list(set(text.split('\n'))))

        except Exception as ee:
            print(f'extract_unique_text_from_text: {ee}')
            pass

        return text


class PDFTextExtractor(TextExtractor):
    def _extract(self) -> str:
        text, _ = extract_all_text_from_pdf(self.fpath)

        return text


class MSWordExtractor(TextExtractor):
    def _extract(self) -> str:
        text = ''
        try:
            text = docx2python(self.fpath)

        except Exception as ee:
            print(f'extract_unique_text_from_msword: {ee}')
            pass

        return text


class ImageTextExtractor(TextExtractor):
    def _extract(self) -> str:
        return extract_text_from_image(self.fpath)

# ------------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------------

# factory = TextExtractorFactory()
# for fmt in ['.xlsx', '.csv']:
#     factory.register_format(fmt, ExcelTextExtractor)
# factory.register_format('.txt', PlainTextExtractor)
# factory.register_format('.pdf', PDFTextExtractor)
# factory.register_format('.docx', MSWordExtractor)
# for fmt in ['.jpg', '.png', '.jpeg']:
#     factory.register_format(fmt, ImageTextExtractor)

# --------
# text_gather.py
# from text_gather import extract_unique_text_from_paths


# def extract_unique_text_from_paths(paths: List[Path], extensions=None, unique=True) -> pd.DataFrame():
#     if extensions is None:
#         extensions = ['.txt', '.xlsx', '.csv', '.pdf', '.docx']
#
#     texts_df = pd.DataFrame()
#     for fpath in paths:
#         suffix = fpath.suffix
#         if not suffix in extensions:
#             continue
#         if suffix == '.txt':
#             text = extract_unique_text_from_text(fpath, unique)
#         elif (suffix == '.xlsx') or (suffix == '.csv'):
#             text = extract_unique_text_from_excel_or_csv(fpath, unique)
#         elif (suffix == '.docx'):
#             text = extract_unique_text_from_msword(fpath, unique)
#         elif (suffix == '.pdf'):
#             text, _ = extract_all_text_from_pdf(fpath)
#             if unique:
#                 text = '\n'.join(list(set(text.split('\n'))))
#         else:
#             print(f'unknown file type ignored: {fpath.as_posix()}')
#
#         lines = text.split('\n')
#         df = pd.DataFrame(pd.Series(lines, name='line'))
#         df['circle'] = circle_abbrev_from_path(fpath)
#         texts_df = pd.concat([texts_df, df])
#
#     return texts_df

# ------------------------------------------------------------------------
# Extractions
# ------------------------------------------------------------------------
