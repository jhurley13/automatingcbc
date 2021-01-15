# text_transform

import re
import string
import unicodedata
import ftfy

from typing import List, Tuple, Optional, Any
import pandas as pd

from taxonomy import Taxonomy
from local_translation_context import LocalTranslationContext
from taxonomy_token_identify import TaxonomyTokenIdentify


def pre_process_line(line) -> str:
    # This should only do text preprocessing, but should not transform
    # the text in any way (e.g. re-arranging to match a species in the taxonomy)

    if not line:
        return ''

    # https://docs.python.org/3/library/unicodedata.html
    line = unicodedata.normalize('NFKD', line)

    # Drop underlines
    line = line.replace('_', '')

    # Get rid of '='
    line = line.replace('=', ' ')

    # Fix soft hypens
    line = line.replace('\u00ad', '-')

    # Detab
    line = line.replace('\t', ' ')

    # Get rid of dates (sloppy regex below)
    line = re.sub(r'[0-9]+\/[0-9]+\/[0-9]+', '', line)

    # If line is all numbers, drop
    line = re.sub(r'^[0-9\s\._]+$', '', line)

    # This in not really a conversion artifact, but we have to do this before saving original_line
    # Get rid of any leading numbers (e.g. from a filled tally sheet)
    #    e.g. 8588 Bufflehead
    line = re.sub(r'^\s*[0-9]+\s*', '', line)

    # Actually, we can delete all numbers
    # There are 2 overall species that have common names with numbers in them:
    # 'Evening Grosbeak (type 1)' etc and 'Red Crossbill (Appalachian or type 1)' etc
    # In examples we have seen, there is such a small difference in Levenshtein distance
    # they are matched properly
    line = re.sub(r'[0-9]+', '', line)

    # Get rid of leading spaces and periods
    line = re.sub(r'^[\.\s]+', '', line)

    # Fix ligatures, so 'Buﬄehead' => 'Bufflehead'
    line = ftfy.fix_text(line, fix_latin_ligatures=True, uncurl_quotes=True)

    # Drop the "box" character at the front of e.g. '\uf06f Winter Wren' (see NYRC)
    # This is somewhat heavy handed, so should come last (e.g. will strip curly quotes)
    line = line.encode("ascii", 'ignore').decode("ascii")

    return line.strip()


# Want these outputs:
# - List of definite species
# - Indication if rare (although we can't always tell)
# - Other annotations like adult, immature
# - A set of translation from the input text that yield a known species
# - A list of unknown lines

# Things we can drop with no regrets:
# - Blank lines
# - Lines that only contain numbers, dates, whitespace
# - Lines shorter than 4 characters: these are the only species with fewer:
#   ['Ou', 'Emu', 'Kea', 'Mao', 'Tui']

def secondary_species_processing(line):
    # line is a potential species

    # If text looks like (accipiter sp.), drop parens
    mm = re.search(r'^\(([^\)]+)\)\s*$', line)
    if mm:
        line = mm.group(1)

    # drop leading -(, whitespace
    # Excel particularly hates a leading '=', since then it thinks the line is a formula
    line = re.sub(r'^[\(*#_\.+\s=-]+', '', line)

    # We want to keep parens, slash and dash and single quote and period
    allowable_punctuation = '()/-\'‘’ .,'
    punctuation_to_drop = ''.join(list(set(string.punctuation) - set(allowable_punctuation)))
    # https://stackoverflow.com/questions/265960/best-way-to-strip-punctuation-from-a-string
    punctuation_to_drop_txlt = str.maketrans('', '', punctuation_to_drop)
    line = line.translate(punctuation_to_drop_txlt).strip()

    # Be careful with removing trailing characters
    # '[\(*#_\s+-]+$'
    line = re.sub(r'[\/*#_\s+-]+$', '', line)

    # CACR has lines like scaup, sp
    line = re.sub(r', sp', ' sp.', line)

    # set(taxonomy.taxonomy[mask].comNameLower.apply(period_group))
    # {'(mt.', '(st.', 'i.', 'is.', 'mrs.', 'mts.', 'sp.', 'st.'}
    #     line = 'galapagos finch sp.'
    #     line = 'rough-legged hawk ........'
    if not line.endswith('sp.'):
        line = re.sub(r'([\.\s-]+)$', '', line)

    # This is a cheap way to get rid of a lone trailing paren
    # See e.g. CAHF "(Brown Pelican)"
    if not '(' in line:
        line = re.sub(r'\)', '', line)

    # Remove trailing (xxx)
    # Minimum length for (...) in species list is 3, e.g. ('oku', 3), ('lau', 3), ('kai', 3), ('aru', 3), ('red', 3)
    mm = re.search(r'[^\(]+(\([^\)]{0,2}\))$', line)
    if mm:
        line = re.sub(r'(\([^\)]{0,2}\))$', '', line)

    return line.strip()


def process_line_annotations(line):
    # Look for annotations like "Bald Eagle (adult)"
    #### handle for now in localTranslations, but move here eventually so we don't lose information
    annotations = {}
    return line, annotations


def tertiary_transformation(line):
    # 'Dark-eyed (slate-colored) Junco' => 'Dark-eyed Junco (slate-colored)'
    line = re.sub(r'([^\(]+)(\([^\)]+\))\s+([^\(]+)', '\g<1> \g<3> \g<2>', line)

    # Seattle encloses their 'sp.' entries with parentheses
    line = re.sub(r'\((.* sp\.)\)', '\g<1>', line)

    # CAHF has a lot of punctution at the start, and may enclose species in parens
    line = re.sub(r'^[^A-Za-z]+', '', line)

    # e.g. 'Gull, Glaucous-winged' => 'Glaucous-winged Gull'
    # but not 'Buteo, sp' (Oakland checklist)
    if ',' in line:
        rev_line = [s.strip() for s in line.split(',')[::-1]]
        line = ' '.join(rev_line)

    if ' x ' in line and not '(hybrid)' in line:
        line += ' (hybrid)'

    line, annotations = process_line_annotations(line)

    # Remove any extra spaces
    line = re.sub(r'\s+', ' ', line).strip()

    return line


def clean_common_names(common_names: List[str],
                       taxonomy,
                       local_translation_context) -> List[str]:
    # skip tertiary_transformation() for now
    common_names = [secondary_species_processing(pre_process_line(line)) for line in common_names]

    #  text_list = [tertiary_transformation(secondary_species_processing(pre_process_line(line))) \
    #                for line in text_list]

    # # Processing 1 checklist here
    # tti = TaxonomyTokenIdentify(taxonomy, interim_data_path)
    #
    # # use text_list from above
    # text_list_lower = [x.lower() for x in text_list]
    # possibles = filter_to_possibles(tti, text_list_lower)
    # print(f'Possible species lines: {len(possibles)} (based on word intersections)')

    # Double translate
    print('Doing double translation')  # Can take a while
    translated = []
    for line in common_names:  # was: possibles
        txline = local_translation_context.apply_translations(line.lower(), True)
        translated.append(txline)

    double_translated = []
    for line, _ in translated:
        txline2 = local_translation_context.apply_translations(line.lower(), True)
        double_translated.append(txline2)

    double_translated = [x for (x, y) in double_translated]
    # print(double_translated)

    # they may be all lower case, return proper capitalization
    result = []
    for common_name in double_translated:
        xcn = ''
        if common_name != '': # avoid most common exception
            try:
                row = taxonomy.find_local_name_row(common_name)
                xcn = row.comName
            except AttributeError as ae:
                print(ae)
                print(f'no taxonomy entry for "{common_name}"')
        result.append(xcn)

    return result
