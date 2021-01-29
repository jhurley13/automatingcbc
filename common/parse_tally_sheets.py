import sys

from typing import List

import pandas as pd

# Note: must mark "common" as "Sources Root" in PyCharm to have visibility

from common_paths import *

from utilities_cbc import read_excel_or_csv_path, debug_write_raw_text, circle_abbrev_from_path

from text_extractor import TextExtractorFactory
from input_files_context import InputFilesContext

from text_transform import pre_process_line, secondary_species_processing

from local_translation_context import LocalTranslationContext
from taxonomy import Taxonomy
# from nlp_context import NLPContext

from parameters import Parameters

from taxonomy_token_identify import TaxonomyTokenIdentify
from spacy.tokens import Span
from spacy.util import filter_spans

from spacy_extra import filter_to_possibles, \
    write_visualization

from write_final_checklist import write_local_checklist_with_group, \
    write_final_checklist_spreadsheet
from write_categorized_lines import write_categorized_lines_spreadsheet

from write_basic_spreadsheet import write_basic_spreadsheet

# 🧭 U+1F9ED Compass Emoji (use for ranged)
# 🎂 U+1F382 Birthday Cake (use for Adult/Immature)
sys.path.append('common')
sys.path.append('textextractor')
sys.path.append('taxonomy')

emoji_compass = '\U0001f9ed'
emoji_birthday_cake = '\U0001f382'


def load_rarities_text(rarities_path: Path) -> List[str]:
    # Check for a rarities list
    rare_species = []
    if rarities_path.exists():
        with open(rarities_path, 'r') as fp:
            lines = fp.read()
            rare_species = lines.split('\n')

    return rare_species


def process_rarities(checklist: pd.DataFrame, rare_species: List[str]) -> pd.DataFrame:
    # Mark rarities
    if rare_species:
        rare_idxs = checklist.index[checklist['CommonName'].isin(rare_species)]
        if len(rare_idxs):
            checklist.at[rare_idxs, 'Rare'] = 'X'

    return checklist


def process_annotations(checklist: pd.DataFrame, annotations_path: Path) -> pd.DataFrame:
    # The set operations below are because not all annotations files will have all columns
    annotations = load_annotations(annotations_path)
    if not annotations.empty:
        # rare_mask = [xs == 'X' for xs in annotations['Rare'].values]
        # rare_species = list(annotations[rare_mask].CommonName.values)
        # if rare_species:
        #     rare_idxs = local_checklist.index[local_checklist['CommonName'].isin(rare_species)]
        #     if len(rare_idxs):
        #         local_checklist.at[rare_idxs, 'Rare'] = 'X'

        emd_cols = {'Easy', 'Marginal', 'Difficult'} & set(annotations.columns)
        if any([[xs == 'X' for xs in annotations[col].values] for col in
                emd_cols]):
            checklist['D'] = ''
            annotations_effort = {}
            for ix, row in annotations.iterrows():
                annotations_effort[row['CommonName']] = row['Difficulty']

            difficulty = [annotations_effort.get(cn, '') for cn in checklist.CommonName]
            checklist['Difficulty'] = difficulty

        # Add new annotation columns to local_checklist
        adim_cols = {'Adult', 'Immature', 'W-morph',
                     'B-Morph', 'CountSpecial'} & set(annotations.columns)
        for col in adim_cols:
            if any([xs == 'X' for xs in annotations[col].values]):
                checklist[col] = ''
                checklist['Ad'] = ''
                checklist['Im'] = ''
                checklist['CountSpecial'] = ''

        rare_adim_cols = {'Rare', 'Adult', 'Immature',
                          'W-morph', 'B-Morph', 'CountSpecial'} & set(annotations.columns)
        for col in rare_adim_cols:
            mask = [xs == 'X' for xs in annotations[col].values]
            related_species = list(annotations[mask].CommonName.values)
            if related_species:
                species_idxs = checklist.index[
                    checklist['CommonName'].isin(related_species)]
                if len(species_idxs):
                    checklist.at[species_idxs, col] = 'X'

        # Overload the Difficulty field with the ranging field
        if 'Ranging' in annotations.columns:
            mask = [xs == 'X' for xs in annotations['Ranging'].values]
            related_species = list(annotations[mask].CommonName.values)
            if related_species:
                species_idxs = checklist.index[
                    checklist['CommonName'].isin(related_species)]
                if len(species_idxs):
                    checklist.at[species_idxs, 'D'] = emoji_compass

    return checklist


def process_annotations_or_rarities(checklist: pd.DataFrame,
                                    checklist_path: Path,
                                    circle_prefix: str) -> pd.DataFrame:
    """
    Look for Annotations or Rarities files and mark the 'Rare' column in checklist
    with an 'X'
    Annotations.xlsx must have these columns:
    Rarities.xlsx (or CSV) requires 'CommonName' and 'Rare' columns
    Rarities.txt is just a text list of rare species
    :param circle_prefix:
    :param checklist:
    :param checklist_path: full path for checklist. Used to construct names for inputs
    :return: checklist with 'Rare' column set to 'X' if species is rare
    """
    # Process annotations. The XXXX-LocalAnnotations.xlsx file will be preferred over
    # the rarities list if it exists

    annotations_dir = checklist_path.parent
    annotations_path = annotations_dir / f'{circle_prefix}Annotations.xlsx'
    print(f'Annotations path: {annotations_path}')

    if annotations_path.exists():
        return process_annotations(checklist, annotations_path)

    for ext in ['xlsx', 'csv', 'txt']:
        rarities_path = annotations_dir / f'{circle_prefix}Rarities.{ext}'
        if not rarities_path.exists():
            continue
        if ext == 'txt':
            rare_species = load_rarities_text(rarities_path)
        else:
            rarities_df = read_excel_or_csv_path(rarities_path)
            rare_species = list(rarities_df[rarities_df.Rare == 'X'].CommonName.values)

        checklist = process_rarities(checklist, rare_species)
        break

    return checklist


def process_exceptions(candidate_names: List[str], checklist_path: Path,
                       circle_prefix: str) -> List[str]:
    # checklist_path = inputs_parse_path / 'CAPA-checklist.xlsx'  # only care about path and prefix
    exceptions_dir = checklist_path.parent

    exceptions_path = exceptions_dir / f'{circle_prefix}Exceptions.xlsx'
    print(f'Exceptions path: {exceptions_path}')

    if not exceptions_path.exists():
        return candidate_names

    print(f'Exceptions: {exceptions_path}')
    exceptions_df = read_excel_or_csv_path(exceptions_path)
    if exceptions_df.empty:
        return candidate_names

    mask_add = exceptions_df.Add == 'X'
    mask_sub = exceptions_df.Subtract == 'X'
    additions = set(exceptions_df[mask_add].CommonName.values)
    subtractions = set(exceptions_df[mask_sub].CommonName.values)
    addstr = ', '.join(additions)
    subst = ', '.join(subtractions)
    print(f'Additions: {addstr}\nSubtractions: {subst}')
    local_names = list((set(candidate_names) | additions) - subtractions)

    return local_names


def build_full_tally_sheet(double_translated,
                           fpath: Path,
                           taxonomy: Taxonomy,
                           parameters: Parameters,
                           circle_prefix: str):
    candidate_names = [x for x, y in double_translated]
    local_names = process_exceptions(candidate_names, fpath, circle_prefix)

    # if issf etc in list, then base species must be also
    issfs = taxonomy.filter_issf(local_names)
    for cn in issfs:
        base_species = taxonomy.report_as(cn)
        if base_species:
            local_names.append(base_species)

    entries = []
    for local_name in local_names:
        # common_name, taxon_order, species_group, NACC_SORT_ORDER
        record = taxonomy.find_local_name_row(local_name)
        if record is not None:
            # e.g. ('White-throated Sparrow', 31943, 'New World Sparrows', 1848.0)
            entry = (record.comName, record.TAXON_ORDER, record.SPECIES_GROUP,
                     record.NACC_SORT_ORDER, record.ABA_SORT_ORDER, '', 0)  # append 'Rare', 'Total'
            entries.append(entry)

    df = pd.DataFrame(entries, columns=['CommonName', 'TaxonOrder', 'Group',
                                        'NACC_SORT_ORDER', 'ABA_SORT_ORDER', 'Rare', 'Total'])

    # Re-order
    cols = ['Group', 'CommonName', 'Rare', 'Total', 'TaxonOrder',
            'NACC_SORT_ORDER', 'ABA_SORT_ORDER']
    local_checklist = df[cols]
    local_checklist.sort_values(by='TaxonOrder', inplace=True)
    #     local_checklist.shape

    # double_translated may have duplicates
    local_checklist = local_checklist[
        ~local_checklist.duplicated(subset=['CommonName'], keep='first')]

    local_checklist = process_annotations_or_rarities(local_checklist, fpath, circle_prefix)

    # Re-order columns
    preferred_order = ['Group', 'CommonName', 'Rare', 'D', 'Total', 'Ad', 'Im',
                       'TaxonOrder', 'NACC_SORT_ORDER', 'ABA_SORT_ORDER', 'Difficulty',
                       'Adult', 'Immature', 'W-morph', 'B-Morph', 'CountSpecial']
    newcols = [col for col in preferred_order if col in local_checklist.columns]
    local_checklist = local_checklist[newcols]

    # Write out full tally sheet
    # circle_code = circle_prefix[0:4]
    # double_path = outputs_path / f'{circle_code}-DoubleX.xlsx'
    # write_local_checklist_with_group(local_checklist, double_path, parameters.parameters)

    return local_checklist


def strip_off_scientific_names(text_list: List[str], taxonomy: Taxonomy) -> List[str]:
    # The CAMP-2020 checklist has <Common Name> <Scientific Name>
    # Assume all scientific names are two words and drop
    stripped_text_list = []
    for line in text_list:
        line = line.strip()
        # e.g. line = 'California Quail Callipepla californica'
        words = line.split(' ')
        if len(words) > 2:
            sci_name = ' '.join(words[-2:]).lower()
            row = taxonomy.find_scientific_name_row(sci_name)
            if row is not None:
                line = ' '.join(words[:-2]) #.lower()
        stripped_text_list.append(line)

    return stripped_text_list


def process_checklist(checklist_path: Path,
                      output_dir: Path,
                      taxonomy: Taxonomy,
                      local_translation_context: LocalTranslationContext,
                      parameters: Parameters,
                      circle_prefix: str
                      ):
    """
    - Extract text
    """

    # Use circle_abbrev as a prefix to distinguish output for multiple checklists

    # Extract text from file and do basic text preprocessing

    text_extractor = TextExtractorFactory().create(checklist_path)
    text = text_extractor.extract()
    debug_write_raw_text(text, checklist_path, debug_path)

    text_list = sorted(list(set(text.split('\n'))))
    # skip tertiary_transformation() for now
    text_list = [secondary_species_processing(pre_process_line(line)) for line in text_list]

    #  text_list = [tertiary_transformation(secondary_species_processing(pre_process_line(line))) \
    #                for line in text_list]

    text_list = strip_off_scientific_names(text_list, taxonomy)

    # print(text_list)

    text_list = sorted(list(set(text_list)))

    # Processing 1 checklist here
    tti = TaxonomyTokenIdentify(taxonomy, cache_path)

    # use text_list from above
    text_list_lower = [x.lower() for x in text_list]
    possibles = filter_to_possibles(tti, text_list_lower)
    print(f'Possible species lines: {len(possibles)} (based on word intersections)')

    # Double translate
    # print('Doing double translation')  # Can take a while
    translated = []
    for line in text_list_lower:  # was: possibles
        txline = local_translation_context.apply_translations(line.lower(), True)
        translated.append(txline)

    double_translated = []
    for line, _ in translated:
        txline2 = local_translation_context.apply_translations(line.lower(), True)
        double_translated.append(txline2)

    # Write Spacy visualization
    write_visualization(list(set([x[0] for x in double_translated])), checklist_path, debug_path,
                        taxonomy,
                        tti)

    # -------
    local_checklist = build_full_tally_sheet(double_translated,
                                             checklist_path, taxonomy,
                                             parameters, circle_prefix)

    cols_to_hide = ['Rare', 'Adult', 'Immature', 'W-morph', 'B-Morph', 'Difficulty', 'CountSpecial']

    # The first checklist we write has a single column for group and is
    # used as the template for the Service-ProcessEBird phase
    # don't use circle_prefix here
    circle_abbrev = circle_abbrev_from_path(checklist_path)
    single_path = output_dir / f'{circle_abbrev}-Single.xlsx'
    write_final_checklist_spreadsheet(local_checklist,
                                      single_path,
                                      parameters.parameters,
                                      additional_sheets=None,
                                      cols_to_hide=cols_to_hide,
                                      cols_to_highlight=['Total'])

    # Write out an empty annotations file if none exists
    annotations_path = inputs_parse_path / f'{circle_prefix}Annotations.xlsx'
    if not annotations_path.exists():
        print(f'Creating empty annotations file: {annotations_path.as_posix()}')
        annotations = local_checklist.copy()
        for col in ['Rare', 'Adult', 'Immature', 'Easy', 'Marginal', 'Difficult']:
            annotations[col] = ''
        write_final_checklist_spreadsheet(annotations,
                                          annotations_path,
                                          parameters.parameters,
                                          additional_sheets=None,
                                          cols_to_hide=None,
                                          cols_to_highlight=None)

    exceptions_path = inputs_parse_path / f'{circle_prefix}Exceptions.xlsx'
    if not exceptions_path.exists():
        print(f'Creating empty exceptions file: {exceptions_path.as_posix()}')
        empty_exceptions = pd.DataFrame(
            {'CommonName': '', 'Add': '', 'Subtract': '', 'Comments': ''},
            index=range(20))  # Adding rows to a table is a pain in Excel, give some room

        write_basic_spreadsheet(empty_exceptions, exceptions_path,
                                column_widths={'CommonName': 30, 'Add': 11,
                                               'Subtract': 11, 'Comments': 50},
                                columns_to_center=['Add', 'Subtract'])

    double_path = output_dir / f'{circle_abbrev}-Double.xlsx'
    write_local_checklist_with_group(local_checklist, double_path, parameters.parameters)
    ground_truths_df = ground_truth_for_code(circle_abbrev)
    if not ground_truths_df.empty:
        _ = check_against_ground_truth(local_checklist, ground_truths_df)

    categorized_lines = categorize_lines(circle_abbrev, text_list,
                                         local_translation_context, tti)

    write_categorized_lines_spreadsheet(categorized_lines,
                                        debug_path / f'{circle_abbrev}-categorized_lines.xlsx',
                                        col_widths=[40, 40, 11, 16],
                                        col_align=['left', 'left', 'center', 'center'],
                                        sheet_name='Categorized Lines',
                                        )

    return text_list, double_translated, local_checklist


# ------------------------------------------------------------------------------------------

def process_checklists(checklists_path: Path,
                       output_dir: Path,
                       taxonomy: Taxonomy,
                       local_translation_context: LocalTranslationContext,
                       parameters: Parameters,
                       circle_prefix: str  # e.g. 'CACR-2020-'
                       ):
    # Return parameters useful when debugging single list

    # parsable_filetypes = TextExtractorFactory().formats()
    ifc = InputFilesContext(checklists_path, ['.xlsx', '.csv', '.pdf'])
    checklist_paths = ifc.allowable_files(f'{circle_prefix}checklist')

    print(f'Path: {checklists_path}')

    #     - Extract text from tally sheet (checklist)
    #     - Make LocalTranslationContext and TaxonomyTokenIdentify objects
    #     - Do a double translation (should be idempotent)

    text_list = []
    double_translated = []
    local_checklist = pd.DataFrame()

    if len(checklist_paths) == 0:
        print(f'No valid checklists found in: {checklists_path}')
        return None, None, None

    for fpath in checklist_paths:
        print(f'Name: {fpath.stem}')
        text_list, double_translated, local_checklist = \
            process_checklist(fpath, output_dir, taxonomy,
                              local_translation_context,
                              parameters,
                              circle_prefix)
        print('--------------------------------------------------------')

    return text_list, double_translated, local_checklist


# ------------------------------------------------------------------------------------------

def ground_truths():
    ground_truths_in_path = base_path / 'ground_truths.xlsx'
    ground_truths_in = read_excel_or_csv_path(ground_truths_in_path)

    return ground_truths_in


def ground_truth_for_code(circle_code: str) -> pd.DataFrame:
    # circle_code is e.g. 'CACR-1'
    ground_truths_in = ground_truths()

    try:
        gt_cols = ['name', 'Category', circle_code]
        mask = (ground_truths_in[circle_code] == 1)
        ground_truths_subset = ground_truths_in[mask][gt_cols].reset_index(
            drop=True)
    except Exception as ee:
        print(f'{circle_code} not found in ground truths: {ee}')
        return pd.DataFrame()

    return ground_truths_subset


def check_against_ground_truth(local_checklist, ground_truth):
    # Add in confusion matrix code
    cns = [x.lower() for x in local_checklist.CommonName]
    diffs = set(cns) ^ set(ground_truth.name)
    if len(diffs) == 0:
        print('Local checklist matches ground truth')
        return True
    else:
        in_local_but_not_gt = set(cns) - set(ground_truth.name)
        in_gt_but_not_local = set(ground_truth.name) - set(cns)

        if len(in_local_but_not_gt):
            print(f'Local checklist has extras not in ground truth: {in_local_but_not_gt}')

        if len(in_gt_but_not_local):
            print(f'Local checklist missing these from ground truth: {in_gt_but_not_local}')

        return False


# ----


def build_docx(lines: List[str], tti: TaxonomyTokenIdentify):
    # nlp = tti.nlp
    matcher = tti.get_phrase_matcher()

    docx = tti.spacify_text('\n'.join(lines), False)  # No fuzzy matching

    matches = matcher(docx)
    match_spans = []

    for match_id, start, end in matches:
        try:
            # rule_id = nlp.vocab.strings[match_id]  # get the unicode ID, i.e. 'COLOR'
            # span = docx[start: end]  # get the matched slice of the doc
            #     print(rule_id, span.text)

            # create a new Span for each match and use the match_id (ANIMAL) as the label
            span = Span(docx, start, end, label=match_id)
            match_spans.append(span)
        except Exception as ee:
            print(match_id, docx[start: end], ee)

    docx.ents = set(list(docx.ents)) | set(filter_spans(match_spans))

    return docx


def double_translate(line, local_translation_context: LocalTranslationContext,
                     quiet: bool = True) -> str:
    txline, _ = local_translation_context.apply_translations(line.lower(), quiet)
    txline2, _ = local_translation_context.apply_translations(txline.lower(), quiet)
    return txline2


def categorize_lines(circle_code: str, text_list: List[str],
                     local_translation_context: LocalTranslationContext,
                     tti: TaxonomyTokenIdentify):
    tl2 = sorted(list(set(text_list)))
    tl3 = [double_translate(line, local_translation_context) for line in tl2]
    docx4 = build_docx(tl3, tti)

    df = pd.DataFrame(pd.Series([x.lower() for x in tl2]), columns=['Line'])

    translations = tl3
    translated = [(True if x[0] != x[1] else False) for x in zip([x.lower() for x in tl2], tl3)]

    df['Translation'] = translations
    df['Translated'] = translated
    df['Category'] = ''

    for ent in docx4.ents:
        mask = (df.Line == ent.text) | (df.Translation == ent.text)
        df.loc[mask, 'Category'] = ent.label_

    df.to_csv(debug_path / f'{circle_code}-categorized_lines.csv', index=False)

    return df


def show_lines_not_found_in_taxonomy(double_translated, taxonomy: Taxonomy):
    # ['Group', 'CommonName', 'Rare', 'Total', 'TaxonOrder']

    for local_name, _ in double_translated:
        row = taxonomy.find_local_name_row(local_name)
        if row is None:
            print(f'Not found in taxonomy: {local_name}')


# 'Group', 'CommonName', 'Rare', 'Easy', 'Marginal', 'Difficult', 'Ranging',
# 'Adult', 'Immature', 'W-morph', 'B-Morph'

def load_annotations(annotations_path: Path) -> pd.DataFrame:
    # Check for an annotations file
    annotations = pd.DataFrame()
    if annotations_path.exists():
        print(f'Annotations: {annotations_path}')

        annotations = read_excel_or_csv_path(annotations_path)

        # Don't output these columns unless present in Annotations file
        if {'Easy', 'Marginal', 'Difficult'} & set(annotations.columns):
            difficulty = pd.Series([''] * annotations.shape[0])
            for col in ['Easy', 'Marginal', 'Difficult']:
                mask = [xs == 'X' for xs in annotations[col].values]
                difficulty[mask] = str(col)[0:1]
            annotations['Difficulty'] = difficulty

        cols_to_keep = [col for col in ['CommonName', 'Rare', 'Easy', 'Marginal', 'Difficult',
                                        'Ranging', 'Adult', 'Immature', 'W-morph', 'B-Morph',
                                        'Difficulty',
                                        'CountSpecial'] if col in annotations.columns]
        annotations = annotations[cols_to_keep]

    return annotations

# New columns will be ['Difficulty', 'Adult', 'Immature', 'W-morph', 'B-Morph'] but
# will be in spreadsheet as ['D', 'A/W', 'I/B']
