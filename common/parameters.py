# parameters.py
# from parameters import Parameters

# Columns: CountDate, CircleAbbrev, CircleID, CircleLatitude, CircleLongitude,
#          eBirdRegion, NationalCode, FinalChecklistTitle
# Example: 12/15/19, CASJ, 58543, 37.4, -121.88, US-CA-085, US, San Jose Christmas Bird Count
# See https://www.arcgis.com/apps/View/index.html?appid=ac275eeb01434cedb1c5dcd0fd3fc7b4
#      for Circle* columns

# CountDate
# CircleAbbrev
# CircleID
# CircleLatitude
# CircleLongitude
# eBirdRegion
# NationalCode
# FinalChecklistTitle

import sys
from datetime import datetime
from typing import Any, Tuple

from singleton_decorator import singleton

from utilities_cbc import read_excel_or_csv_path
from common_paths import *
import pandas as pd

# Parameters/Configuration

CRASH_ON_ERROR = True


@singleton
class Parameters(object):
    """Combined System and Local parameters and paths

    Attributes:
     """

    def __init__(self, local_parameters_path=local_parameters_path,
                 system_parameters_path=system_parameters_path,
                 name_prefix: str = None,
                 quiet: bool = True):
        self.local_parameters_path = local_parameters_path
        self.system_parameters_path = system_parameters_path

        # Local Parameters
        self.translations_path = self.local_parameters_path / 'LocalTranslations.xlsx'
        # self.contacts_path = self.local_parameters_path / 'BirderContacts.xlsx'
        # self.participants_path = self.local_parameters_path / 'Participants.xlsx'
        # only for checklist PDFs
        self.input_forms_path = self.local_parameters_path / 'InputForms.xlsx'
        self.local_checklist_path = self.local_parameters_path / 'LocalChecklist.xlsx'

        # It may be that other paths should look for prefix too
        if name_prefix:
            self.parameters_path = self.local_parameters_path / f'{name_prefix}Parameters.xlsx'
        else:
            self.parameters_path = self.local_parameters_path / 'Parameters.xlsx'

        # System Parameters
        self.stopwords_path = system_parameters_path / 'StopWords.xlsx'
        # https://www.audubon.org/sites/default/files/cbc_rare_bird_form.pdf
        self.rare_bird_template_path = system_parameters_path / 'Rare_Bird_Form_fillable.pdf'

        # Obsolete
        self.local_word_replacements_path = self.local_parameters_path / \
                                            'LocalWordReplacements.xlsx'
        self.pdf_word_replacements_path = system_parameters_path / 'PDFWordReplacements.xlsx'

        self.parameters = self.load_parameters(quiet)

    def load_parameters(self, quiet: bool = True) -> dict:
        # Load and normalize parameters
        parameters_df = read_excel_or_csv_path(self.parameters_path, xheader=None)

        if parameters_df.empty:
            err_msg = f'Parameters file is required: {self.parameters_path.as_posix()}\n'
            if CRASH_ON_ERROR:
                sys.exit(err_msg)
            else:
                print(err_msg)

        # Do some manipulation on the data read in
        # The file is transposed on disk for user convenience
        parameters_df = parameters_df.T
        cols = list(parameters_df.iloc[0].values)
        parameters_df = parameters_df.drop([parameters_df.index[0]]).reset_index(drop=True)
        parameters_df.columns = cols

        parameters = parameters_df.iloc[0].to_dict()

        # Look for "NationalCode" first, so we can generate the region files
        # before possible exit below
        country = parameters.get('NationalCode', None)
        if not country:
            print('Warning: no "NationalCode" field found in Parameters, assuming "US"')
            country = 'US'
        parameters['NationalCode'] = country

        # May exit here
        region_code = parameters.get('eBirdRegion', None)
        if not region_code:

            line1 = f'Region code is required in eBirdRegion field of parameters file\n'
            line2 = f'Parameters file: {self.parameters_path.as_posix()}\n'
            line3 = f'Region files path: {interim_data_path}'
            err_msg = line1 + line2 + line3
            if CRASH_ON_ERROR:
                sys.exit(err_msg)
            else:
                print(err_msg)

        date_of_count = parameters.get('CountDate', datetime.now())
        parameters['CountDate'] = date_of_count.strftime("%Y-%m-%d")

        if not quiet:
            print('Using these parameters:\n')
            for key, val in parameters.items():
                print(f'{key:<25s}{str(val):<80s}')
            print()

        return parameters

    # was retrieve_parameters
    def common_parameters(self) -> Tuple[Any, str, str, Tuple[float, float]]:
        # Convenience routine for parameter access
        date_of_count = self.parameters['CountDate']
        country = self.parameters['NationalCode']
        region_code = self.parameters['eBirdRegion']
        cbc_circle_center = (self.parameters['CircleLatitude'], self.parameters['CircleLongitude'])

        return date_of_count, country, region_code, cbc_circle_center

    def is_consistent_parameters(self) -> bool:
        required_parameter_keys = [
            'CountDate', 'CircleAbbrev', 'CircleID', 'CircleLatitude', 'CircleLongitude',
            'eBirdRegion', 'NationalCode', 'FinalChecklistTitle'
        ]
        ppath = self.parameters_path

        parameters = self.parameters

        missing_parameter_keys = set(required_parameter_keys) - set(parameters.keys())
        if missing_parameter_keys:
            print(f'Parameters file {ppath.as_posix()} is missing these keys:')
            missing_parameter_keys_str = ', '.join(missing_parameter_keys)
            print(f'\t{missing_parameter_keys_str}')
            return False

        # All keys are present; do they contain some data?
        empty_parameters = []
        for key, val in parameters.items():
            if not parameters[key]:
                empty_parameters.append(key)

        if len(empty_parameters):
            print(f'Parameters file {ppath.as_posix()}')
            empty_parameters_str = ', '.join(empty_parameters)
            print(f'\thas keys with missing values: {empty_parameters_str}')
            return False

        try:
            date_of_count = parameters['CountDate']
            count_date = datetime.strptime(date_of_count, '%Y-%m-%d').strftime("%d %b %Y")
        except Exception as ee:
            print(f'Parameters file {ppath.as_posix()}')
            print(ee)
            return False

        return True

    @staticmethod
    def prepare_parameters_from_file(parameters_df) -> pd.DataFrame:
        # Do some manipulation on the data read in
        # The file is transposed on disk for user convenience
        parameters_df = parameters_df.T
        cols = list(parameters_df.iloc[0].values)
        parameters_df = parameters_df.drop([parameters_df.index[0]]).reset_index(drop=True)
        parameters_df.columns = cols

        parameters = parameters_df.iloc[0].to_dict()

        return parameters
