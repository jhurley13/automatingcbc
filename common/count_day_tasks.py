import re
from pathlib import Path
from typing import List, Optional, Dict

import pandas as pd

from utilities_cbc import read_excel_or_csv_path
from common_paths import reports_path, inputs_count_path
from datetime_manipulation import normalize_date_for_visits
from ebird_extras import EBirdExtra
from ebird_summary import create_ebird_summary
from ebird_visits import transform_checklist_details
from local_translation_context import LocalTranslationContext
# Local imports
from parameters import Parameters
from process_csv import raw_csv_to_checklist
from service_merge import recombine_transformed_checklist, merge_checklists
from taxonomy import Taxonomy
from write_final_checklist import write_final_checklist_spreadsheet
from common_paths import outputs_path


def check_prerequisites(circle_prefix: str) -> bool:
    # True means we are good to go
    ready = False
    fpath = outputs_path / f'{circle_prefix}Single.xlsx'
    if not fpath.exists():
        print(f'Missing {fpath}, run Service-Parse first')
        raise Exception('Not ready')
    else:
        ready = True

    return ready


def find_location_name_with_locid(location_data, locid) -> str:
    hs_name = '-'
    try:
        hs_name = location_data[location_data.locId == locid].LocationName.values[0]
    except IndexError:
        pass

    return hs_name


def get_participants(circle_prefix: str) -> Optional[List[str]]:
    # This may need to be bootstrapped, i.e. run everything once, then create a list
    # and run again. Returning None means don't filter out by userDisplayName
    participants = None
    participants_path = inputs_count_path / f'{circle_prefix}Participants.txt'
    if participants_path.exists():
        with open(participants_path, 'r') as fp:
            lines = fp.read()
            participants = lines.split('\n')
    else:
        print(f'No participants file at "{participants_path}"')
        print('All checklists filed in count circle will be used')

    return participants


def create_full_circle_summary(template_path: Path,
                               taxonomy: Taxonomy,
                               local_translation_context: LocalTranslationContext,
                               parameters: Parameters,
                               additional_sheets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    circle_abbrev = parameters.parameters.get('CircleAbbrev', 'XXXX')
    circle_code = circle_abbrev[0:4]

    circle_summary_prefix = f'{circle_code}-EBird-Summary-'
    count_summaries = sorted(
        [x for x in reports_path.glob('*.xlsx') if x.stem.startswith(circle_summary_prefix)])
    circle_stem_to_colname = {}
    for ix, fpath in enumerate(count_summaries):
        stem = fpath.stem
        stem = stem.replace(circle_summary_prefix, '')
        # Does it already have leading digits?
        mm = re.match(r'^([0-9]+-)', stem)
        col_name = stem if mm else f'{ix + 1:02d}-{stem}'
        circle_stem_to_colname[fpath.stem] = col_name

    output_path = reports_path / f'{circle_code}-CountCircleSummary.xlsx'

    print()
    summary, cols_to_hide, cols_to_highlight = merge_checklists(
        template_path, count_summaries, circle_stem_to_colname,
        taxonomy, local_translation_context)

    # Until we do the refactoring to allow more of a pipeline, adding rarities as a sheet
    # would be really ugly. Until then, write it out as a CSV

    write_final_checklist_spreadsheet(summary, output_path,
                                      parameters=parameters.parameters,
                                      additional_sheets=additional_sheets,
                                      cols_to_hide=cols_to_hide,
                                      cols_to_highlight=cols_to_highlight
                                      )

    return summary


"""
- Grab every checklist in both counties
- Filter out anything not in one of our sectors
- Do groupby(['obsTime', 'numSpecies', 'locId']) and collect all names that filed that checklist
- Filter out any checklist where at least one name doesn't match our participant list
"""


def process_additional_checklist(additional_files: Optional[Dict[str, List[Path]]],
                                 xdates: List[str],
                                 taxonomy: Taxonomy,
                                 personal_checklists) -> pd.DataFrame:
    personal_checklists_x = personal_checklists.copy()

    # For today this is a horrendous hack to add in Bob Hirt data
    # Needs to be generalized to deal with extras like FeederWatch data

    additional_checklists = [personal_checklists_x]
    local_translation_context = LocalTranslationContext()
    for name, fpaths in additional_files.items():
        for fpath in fpaths:
            checklist = raw_csv_to_checklist(fpath,
                                             taxonomy,
                                             local_translation_context,
                                             name,
                                             xdates,
                                             None,
                                             None)
            if checklist is not None and not checklist.empty:
                additional_checklists.append(checklist)

    if len(additional_checklists) > 1:
        personal_checklists_x = pd.concat(additional_checklists, axis=0, ignore_index=True)

    return personal_checklists_x


def additional_count_checklists(circle_prefix: str, xdates: List[str],
                                taxonomy: Taxonomy,
                                personal_checklists) -> pd.DataFrame:
    additional_files = {}
    for fpath in inputs_count_path.glob('*.csv'):
        if not fpath.stem.startswith(circle_prefix):
            continue
        name = fpath.stem
        name.replace(circle_prefix, '')
        additional_files[name] = [fpath]

    if bool(additional_files):
        personal_checklists = process_additional_checklist(additional_files,
                                                           xdates,
                                                           taxonomy,
                                                           personal_checklists)
    return personal_checklists


# ToDo: eliminate add_bob_hirt, replace with additional_count_checklists
def add_bob_hirt(xdates: List[str],
                 taxonomy: Taxonomy,
                 personal_checklists) -> pd.DataFrame:
    additional_files = {'Bob Hirt': [inputs_count_path / 'CACR-bob-hirt.csv']}
    personal_checklists = process_additional_checklist(additional_files,
                                                       xdates,
                                                       taxonomy,
                                                       personal_checklists)
    return personal_checklists


def subids_for_pete_dunten(parameters: Parameters):
    # True Hack
    circle_code = parameters.parameters.get('CircleAbbrev', 'XXXX')
    subids_by_date = {}

    if circle_code == 'CACR':
        # Additional subids for Pete Dunten
        date_of_count = parameters.parameters['CountDate']

        subids_by_date[date_of_count] = ['S78036994', 'S78035225']

    return subids_by_date


def get_personal_checklist_details(visits: pd.DataFrame,
                                   xdates: List[str],
                                   additional_subids: Optional[Dict[str, str]],
                                   ebird_extra: EBirdExtra,
                                   taxonomy: Taxonomy) -> pd.DataFrame:
    """
    Get checklist details for all subids in visits. Don't do any duplicate
    processing, but do transform it into more useful form by renaming columns, etc.
    :param ebird_extra:
    :param visits: can be visits or visits_of_interest
    :param xdates:
    :param additional_subids: ref subids_for_pete_dunten
    :param taxonomy:
    :return:
    """

    # Get detailed checklists
    # Make dictionary of subIds keyed by date
    subids_by_date = {}
    for xdate in xdates:
        obsdt = normalize_date_for_visits(xdate)
        subids = list(visits[visits.obsDt == obsdt].subId.values)
        subids_by_date[xdate] = subids

    if additional_subids is not None:
        for xdate in xdates:
            # Get the existing list of subids for xdate
            sid = subids_by_date.get(xdate, None)
            additional_for_date = additional_subids.get(xdate, None)
            if additional_for_date is not None:
                sid.extend(additional_for_date)
                subids_by_date[xdate] = sid

    # Now call eBird API to get details for subids
    details = ebird_extra.get_details_for_dates(subids_by_date, xdates)
    personal_checklists = transform_checklist_details(details, taxonomy)

    return personal_checklists


def summarize_checklists(personal_checklists: pd.DataFrame,
                         taxonomy: Taxonomy,
                         template_path: Path,
                         parameters: Parameters,
                         checklist_meta: pd.DataFrame,
                         geo_data,
                         location_data,
                         location_meta
                         ):
    # Try with up to date 2020 checklist
    # template_path = inputs_path / 'Merge' / 'CASJ-2-SingleChecklist-CASJ-2-checklist2020.xlsx'

    circle_code = parameters.parameters.get('CircleAbbrev', 'XXXX')

    # Load Summary template
    template = read_excel_or_csv_path(template_path)
    template_2col = template.copy()
    # Create a single column master for summary
    summary_base = recombine_transformed_checklist(template_2col, taxonomy)

    # Create EBird Summaries
    unlisted_rare_species = set()
    sectors = sorted(list(set(geo_data[geo_data['type'] == 'sector'].GeoName.values)))
    if len(sectors) == 0:
        sector = geo_data[geo_data['type'] == 'circle'].GeoName.values[0]
        summary, rare_species = create_ebird_summary(summary_base, personal_checklists,
                                                     checklist_meta,
                                                     circle_code,
                                                     parameters, sector, taxonomy, reports_path)
        for species in rare_species:
            unlisted_rare_species.add(species)
    else:
        for sector in sectors:
            sector_subids = location_meta[location_meta.GeoName == sector].locId.values
            sector_checklists = personal_checklists[personal_checklists.locId.isin(sector_subids)]
            print(f'Sector: {sector:30} [{sector_checklists.shape[0]} observations]')
            if sector_checklists.shape[0] == 0:
                continue

            summary, rare_species = create_ebird_summary(summary_base, sector_checklists,
                                                         checklist_meta,
                                                         circle_code,
                                                         parameters, sector, taxonomy, reports_path)
            for species in rare_species:
                unlisted_rare_species.add(species)

    # Print out rarities (eventually move to somewhere useful)
    rare_base = summary_base[summary_base.Rare != ''].CommonName.values
    all_rarities = list(unlisted_rare_species | set(rare_base))
    mask = [cn in all_rarities for cn in personal_checklists.CommonName.values]
    rarities_df = personal_checklists[mask].copy().reset_index(drop=True)
    rarities_df.drop(columns=['groupId', 'speciesCode'], inplace=True)
    # , add name from locId])
    rarities_df.sort_values(by=['Name'], inplace=True)
    rarities_df['Reason'] = rarities_df.CommonName.apply(
        lambda cn: 'Missing' if cn in unlisted_rare_species else 'Explicit')
    rarities_df['Where'] = [find_location_name_with_locid(location_data, locid) for locid in
                            rarities_df.locId.values]
    # display(rarities_df)

    return rarities_df
