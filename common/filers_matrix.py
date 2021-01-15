import pandas as pd
from common_paths import reports_path
from typing import Tuple, List


def create_filers_matrix(circle_prefix: str, visits_of_interest: pd.DataFrame,
                         location_data: pd.DataFrame,
                         xoutputs_path=reports_path) -> Tuple[pd.DataFrame, List[str]]:
    voi = visits_of_interest.copy()
    voi = voi.merge(location_data, how='left', on='locId').drop_duplicates(['Name']).sort_values(
        by=['Name']).reset_index(drop=True).fillna('')

    cols_to_keep = ['locId', 'Name', 'LocationName']
    filers_matrix = voi[cols_to_keep]
    unique_circle_filers = list(set(filers_matrix.Name))

    # filers_matrix.to_csv(xoutputs_path / f'{circle_prefix}filers_matrix.csv', index=False)

    return filers_matrix, unique_circle_filers
