"""
# https://pbpython.com/pandas-pivot-table-explained.html
# https://stackoverflow.com/questions/62605470/pandas-pivot-table-subtotals-with-multi-index
# https://stackoverflow.com/questions/53266032/adding-a-grand-total-to-a-pandas-pivot-table
"""

import pandas as pd
import numpy as np


def generate_autoparty(checklist_meta: pd.DataFrame, location_data: pd.DataFrame) -> pd.DataFrame:
    # It's called autoparty because it is generated, rather than supplied by
    # the sector leader or compiler
    rows = []
    for (locid, obsdt), grp in checklist_meta.groupby(['locId', 'obsDt']):
        row = {
            'locId': locid,
            'obsDt': obsdt,
            'members': ', '.join(sorted(list(grp.Name.values))),
            'DistanceMi': grp.effortDistanceKm.values[0],
            'DurationHrs': grp.durationHrs.values[0]
        }
        rows.append(row)

    autoparty = pd.DataFrame(rows).sort_values(by=['members', 'obsDt']).reset_index(drop=True)
    autoparty.fillna({'DistanceMi': 0.0, 'DurationHrs': 0.0}, inplace=True)

    # Make a pivottable
    piv = pd.pivot_table(autoparty, index=['members', 'obsDt', 'locId'],
                         fill_value=0, aggfunc=np.sum, dropna=True)

    piv_total = piv.sum(level=0).assign(effort='total').set_index('effort', append=True)
    autoparty_piv = pd.concat([piv, piv_total]).sort_index()

    # Add in location names
    location_names = []
    for idx in autoparty_piv.index:
        *a, obsdt, last = idx
        if last == 'total':
            location_name = ''
        else:
            locid = last
            try:
                location_name = location_data[location_data.locId == locid].LocationName.values[0]
            except IndexError:
                print(f'No location name for: {locid}')
                location_name = ''

        location_names.append(location_name)

    autoparty_piv['LocationName'] = location_names

    # Add Grand total
    grand_total = autoparty_piv[
        ['total' in ix for ix in autoparty_piv.index.get_level_values(0)]].sum()
    autoparty_piv = autoparty_piv.append(grand_total.rename('Grand Total'))

    autoparty_flat = flatten_autoparty(autoparty_piv)

    return autoparty_flat


def flatten_autoparty(autoparty_piv) -> pd.DataFrame:
    # Probably an easier way to do this, but this works
    rows = []
    for idx, row in autoparty_piv.iterrows():
        # print(idx, type(idx))
        *members, obsdt, last = idx
        if isinstance(idx, str):  # Grand Total
            rowx = {'members': '', 'locId': '', 'obsDt': idx}
        elif last == 'total':
            rowx = {'members': '', 'locId': '', 'obsDt': 'total'}
        else:
            rowx = {'members': ', '.join(members), 'locId': last, 'obsDt': obsdt}
        for jx, val in row.iteritems():
            rowx[jx] = val
        rows.append(rowx)

    return pd.DataFrame(rows)


def sheet_info_for_autoparty(df: pd.DataFrame) -> dict:
    # ['Party Lead', 'Duration (Hrs)', 'Distance (mi)']
    column_widths = {
        'members': 30,
        'locId': 10,
        'obsDt': 15,
        'DistanceMi': 10,
        'DurationHrs': 10,
        'LocationName': 75
    }
    columns_to_center = ['locId', 'DistanceMi', 'DurationHrs', 'obsDt']

    sheet_info = {
        'sheet_name': 'AutoParty',
        'data': df,
        'widths': column_widths,
        'to_center': columns_to_center,
        'to_hide': None
    }

    return sheet_info
