from typing import List, Tuple, Optional, Any
import pandas as pd
from singleton_decorator import singleton
import re

from pathlib import Path
import sys, traceback


class InputFilesContext(object):
    """Support flexible file naming for inputs
    Also allows files for multiple circles to be present in directory
    Attributes:
     """

    def __init__(self, input_files_path: Path, allowable_filetypes=None):
        if allowable_filetypes is None:
            allowable_filetypes = ['.xlsx', '.csv', '.XLSX', '.CSV']
        self._input_files_path = input_files_path
        self._allowable_filetypes = allowable_filetypes

    def allowable_file(self, fpath: Path, xpattern: str) -> bool:
        # Wrong type or Excel temp file
        if (not fpath.suffix in self._allowable_filetypes) or fpath.stem.startswith('~$'):
            return False

        if xpattern is None:
            print('no pattern')
            return True

        # pattern = re.compile(xpattern, flags=re.IGNORECASE)  # | re.DEBUG
        mm = re.search(xpattern, fpath.stem)
        # print(mm, fpath.stem)

        return mm

    def allowable_files(self, xpattern: str = None):
        possible_paths = {px.resolve() for px in Path(self._input_files_path).glob("*") if
                          self.allowable_file(px, xpattern)}
        return list(possible_paths)
