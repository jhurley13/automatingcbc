# local_translation_context.py
# from local_translation_context import LocalTranslationContext

import re
from typing import List
from typing import Tuple

import pandas as pd
from singleton_decorator import singleton

import utilities_cbc as autil


@singleton
class LocalTranslationContext(object):
    """Create a dataframe for system and local translations

    Attributes:
    """

    def __init__(self, parameters_path=None, system_parameters_path=None):
        self.system_parameters_path = system_parameters_path
        self.parameters_path = parameters_path

        # File names and paths
        self.parameters_path = parameters_path
        self.system_parameters_path = system_parameters_path
        self.translations_base_path = parameters_path
        self.translations_name_base = 'LocalTranslations'
        self.system_translations_path = system_parameters_path
        self.system_translations_name_base = 'SystemTranslations'

        # Properties
        self._system_translations = None
        self._local_translations = None
        self._all_translations = self._initialize_all_translations()

    def reload(self):
        # for debugging
        # Initialize properties that could fail
        self._all_translations = self._initialize_all_translations()

        for idx, row in self._all_translations.iterrows():
            lsn = row.LocalSpeciesName.lower()
            if row.match_whole_line and lsn.endswith(' '):
                print(f'WARNING: Pattern "{lsn}" has trailing whitespace')

    def fix_excel_changes(self, xv):
        return xv.replace(u'\xa0', u' ').lower()

    def _initialize_all_translations(self) -> pd.DataFrame:
        # This may be empty the first time through, since it won't be known what translations are needed
        self._system_translations = autil.read_excel_or_csv(self.system_translations_path,
                                                            self.system_translations_name_base)
        self._local_translations = autil.read_excel_or_csv(self.translations_base_path,
                                                           self.translations_name_base)

        if self._local_translations.empty:
            self._all_translations = self._system_translations.copy()
        else:
            # system_translations, then local_translations
            # You can override a system_translation by putting something in local_translations
            # The drop_duplicates below will keep the local value
            self._all_translations = pd.concat(
                [self._system_translations, self._local_translations], axis=0,
                join='outer', ignore_index=True, keys=None,
                levels=None, names=None, verify_integrity=False, copy=True)

        self._all_translations.drop_duplicates(subset='LocalSpeciesName', keep='last',
                                               ignore_index=True, inplace=True)

        self._all_translations.LocalSpeciesName = self._all_translations.LocalSpeciesName.apply(
            self.fix_excel_changes)
        self._all_translations.eBirdSpeciesName = self._all_translations.eBirdSpeciesName.apply(
            self.fix_excel_changes)

        base_str_cols = ['LocalSpeciesName', 'eBirdSpeciesName', 'Comments', 'circle']
        str_cols = [col for col in self._all_translations.columns if
                    col in base_str_cols or col.startswith('AltName')]
        bool_cols = list(set(self._all_translations.columns) - set(str_cols))

        for col in str_cols:
            self._all_translations[col] = self._all_translations[col].astype(str).fillna(
                '').replace('nan', '')
        for col in bool_cols:
            self._all_translations[col] = self._all_translations[col].astype(bool).fillna(False)

        compiled_patterns = []
        for idx, row in self._all_translations.iterrows():
            compiled_pattern = None
            lsn = row.LocalSpeciesName.lower()
            try:
                if row.match_whole_line:
                    compiled_pattern = re.compile(f'^{re.escape(lsn)}$')
                elif row.regex:
                    compiled_pattern = re.compile(f'{lsn}')
            except Exception as ee:
                print(f'Local translation compile regex fail: "{lsn}"')
            compiled_patterns.append(compiled_pattern)

        self._all_translations['compiled_pattern'] = compiled_patterns

        # We want to apply any whole-line translations first
        self._all_translations.sort_values(by='match_whole_line', ascending=False, inplace=True,
                                           ignore_index=True)

        return self._all_translations

    def apply_translations(self, line, quiet: bool = True) -> Tuple[str, bool]:
        found_exact_match = False

        for idx, row in self._all_translations.iterrows():
            lsn = row.LocalSpeciesName.lower()
            esn = row.eBirdSpeciesName.lower()
            line = line.lower()
            prev_line = line

            # Straight replacement
            if not (row.match_whole_line or row.regex):
                line = line.replace(lsn, esn)  # orig => repl
            else:
                try:
                    pattern = row.compiled_pattern
                    if row.match_whole_line:
                        if re.match(pattern, line):
                            found_exact_match = True

                    line = re.sub(pattern, esn, line)


                except Exception as ee:
                    print(f'Local translation regex fail: "{lsn}" => "{esn}"')

            # Helps debug which regex caused a replacement
            if (not quiet) and (line != prev_line):
                print(f'{prev_line} => {line} WITH {lsn}')
                prev_line = line

            if found_exact_match:
                break

        return line.strip(), found_exact_match

    def apply_whole_line_translations(self, line, quiet: bool = True) -> str:
        found_exact_match = False

        for idx, row in self._all_translations.iterrows():
            lsn = row.LocalSpeciesName.lower()
            esn = row.eBirdSpeciesName.lower()
            line = line.lower()
            prev_line = line

            if not row.match_whole_line:
                continue

            # Straight replacement
            try:
                pattern = row.compiled_pattern
                if re.match(pattern, line):
                    found_exact_match = True

                line = re.sub(pattern, esn, line)

                # Helps debug which regex caused a replacement
                if (not quiet) and (line != prev_line):
                    print(f'{prev_line} => {line} WITH {lsn}')
                    prev_line = line

                if found_exact_match:
                    break

            except Exception as ee:
                print(f'Local translation regex fail: "{lsn}" => "{esn}" {ee}')

        return line.strip()

    def test_local_translations(self, lines: List[str]) -> List[Tuple[str, Tuple[str, bool]]]:
        self.reload()

        translated_lines = []
        for line in lines:
            txline = self.apply_translations(line, False)
            translated_lines.append((line, txline))

        return translated_lines

    @property
    def all_translations(self):
        return self._all_translations

    def summary(self) -> str:
        xs = f'UNSUPPORTED'
        return xs


# Since debugging a singleton is a pain in Jupyter notebooks (have to restart kernel each time),
# provide simple test code for translations


def debug_apply_translations_X(local_translation_context: LocalTranslationContext,
                               line, quiet: bool = True) -> Tuple[str, bool]:
    found_exact_match = False

    for idx, row in local_translation_context._all_translations.iterrows():
        lsn = row.LocalSpeciesName.lower()
        esn = row.eBirdSpeciesName.lower()
        line = line.lower()
        prev_line = line

        # Straight replacement
        if not (row.match_whole_line or row.regex):
            line = line.replace(lsn, esn)  # orig => repl
        else:
            try:
                pattern = row.compiled_pattern
                if row.match_whole_line:
                    if re.match(pattern, line):
                        found_exact_match = True

                line = re.sub(pattern, esn, line)


            except Exception as ee:
                print(f'Local translation regex fail: "{lsn}" => "{esn}"')

        # Helps debug which regex caused a replacement
        if (not quiet) and (line != prev_line):
            print(f'{prev_line} => {line} with {lsn}')

        if found_exact_match:
            break

    return line.strip(), found_exact_match

# taxonomy.find_local_name(local_name, match_scientific_name=False)
# agwt = '“American” Green-winged Teal'
# line = secondary_species_processing(pre_process_line(agwt)).lower()
# debug_apply_translations_X(line, False)
