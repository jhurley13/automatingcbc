from spacy.attrs import ORTH
from spacy import displacy
import webcolors
from pathlib import Path
from utilities_cbc import circle_abbrev_from_path

from spacy.matcher import PhraseMatcher
from spacy.lang.en import English
from spacy.tokens import Span
from spacy.util import filter_spans


def build_phrase_matcher(nlp, taxonomy):
    # species       10721
    # issf           3800
    # slash           709
    # spuh            653
    # hybrid          462
    # form            122
    # intergrade       31
    # domestic         15

    # nlp = English()

    categories = ['hybrid', 'slash', 'form', 'intergrade', 'domestic', 'spuh', 'issf', 'species']
    cols = ['comName', 'sciName', 'familyComName', 'familySciName', 'order']
    name_prefixes = ['COM', 'SCI', 'FAMCOM', 'FAMSCI', 'ORD']

    accumulation = set()
    matcher_patterns = {}
    pattern_names = []

    for cat in categories:
        subdf = taxonomy.taxonomy[taxonomy.taxonomy.Category == cat]
        for ix, col in enumerate(cols):
            names = set([xs.lower() for xs in subdf[col]]) - accumulation
            patterns = [nlp(text) for text in names]
            accumulation |= names
            pattern_name = f'{name_prefixes[ix]}{cat}'.upper()
            pattern_names.append(pattern_name)
            matcher_patterns[pattern_name] = patterns

    # print(pattern_names)
    for pn in pattern_names:
        nlp.vocab.strings.add(pn)

    matcher = PhraseMatcher(nlp.vocab)
    for key, val in matcher_patterns.items():
        matcher.add(key, None, *val)

    return matcher, nlp


def filter_to_possibles(tti, lines):
    filter_tokens, _, _ = tti.nlp_context.taxonomy_tokens()
    docSW = set(w.orth for w in tti.nlp(' '.join(tti.stop_words)))
    docTax = set(w.orth for w in filter_tokens) - docSW

    possibles = set()
    for line in lines:
        #     print(line)
        line_doc = set(tti.nlp(line))
        docA = set(w.orth for w in line_doc)
        if len(docA) == 0:
            continue
        intersections = docTax & docA
        pctage = len(intersections) / len(docA)
        #         if (pctage > 0.0) and (pctage < 0.3):
        #             print(f'{pctage} {[tti.nlp.vocab.strings[ii] for ii in intersections]} {line}')

        if pctage > 0.14:
            #             print(f'{pctage} {[tti.nlp.vocab.strings[ii] for ii in intersections]}')
            possibles.add(line)

    return possibles


def create_visualization2(docx, show_in_jupyter=True):
    # Create visualization
    # https://developer.mozilla.org/en-US/docs/Web/CSS/linear-gradient
    # https://cssgradient.io
    # https://htmlcolorcodes.com

    ent_names = [
        'COMHYBRID', 'SCIHYBRID', 'FAMCOMHYBRID', 'FAMSCIHYBRID', 'ORDHYBRID',
        'COMSLASH', 'SCISLASH', 'FAMCOMSLASH', 'FAMSCISLASH', 'ORDSLASH', 'COMFORM',
        'SCIFORM', 'FAMCOMFORM', 'FAMSCIFORM', 'ORDFORM', 'COMINTERGRADE',
        'SCIINTERGRADE', 'FAMCOMINTERGRADE', 'FAMSCIINTERGRADE', 'ORDINTERGRADE',
        'COMDOMESTIC', 'SCIDOMESTIC', 'FAMCOMDOMESTIC', 'FAMSCIDOMESTIC', 'ORDDOMESTIC',
        'COMSPUH', 'SCISPUH', 'FAMCOMSPUH', 'FAMSCISPUH', 'ORDSPUH', 'COMISSF',
        'SCIISSF', 'FAMCOMISSF', 'FAMSCIISSF', 'ORDISSF', 'COMSPECIES', 'SCISPECIES',
        'FAMCOMSPECIES', 'FAMSCISPECIES', 'ORDSPECIES'
    ]

    def ent_name_to_color(ent_name):
        if ent_name.startswith('COM'):
            return purplish

        if ent_name.startswith('SCI'):
            return aquaish

        if ent_name.startswith('ORD'):
            return greenish

        if ent_name.startswith('FAMCOM'):
            return yellowish

        if ent_name.startswith('FAMSCI'):
            return fuchsiaish

        return webcolors.name_to_hex('HotPink'.lower())

    print('Creating visualization')

    # "R" suffix is for reverse
    purplish = 'linear-gradient(90deg, #aa9cfc, #fc9ce7)'  # original
    purplishR = 'linear-gradient(45deg, #fc9ce7, #aa9cfc)'
    yellowish = 'linear-gradient(90deg, #f9fc9c, #fac945)'
    greenish = 'linear-gradient(90deg, #cdfc9c, #5cfa45)'
    aquaish = 'linear-gradient(90deg, #9cfcea, #3cd3e7)'
    aquaishR = 'linear-gradient(45deg, #3cd3e7, #9cfcea)'
    fuchsiaish = 'linear-gradient(90deg, #fc9cde, #ff5aa4)'

    colors = {}
    for ent_name in ent_names:
        colors[ent_name] = ent_name_to_color(ent_name)

    options = {"ents": ent_names,
               "colors": colors}

    # displacy.serve(doc, style="ent", options=options)
    html = displacy.render([docx], style="ent", page=True,
                           jupyter=show_in_jupyter, options=options)

    return html


def write_visualization(names: list, fpath: Path, out_path: Path, taxonomy, tti):
    # Now look for named entities
    nlp = English()
    docx = nlp('\n'.join(names))

    matcher, nlp = build_phrase_matcher(nlp, taxonomy)
    matches = matcher(docx)
    match_spans = []
    for match_id, start, end in matches:
        rule_id = nlp.vocab.strings[match_id]  # get the unicode ID, i.e. 'COLOR'
        span = docx[start: end]  # get the matched slice of the doc
        #     print(rule_id, span.text)

        # create a new Span for each match and use the match_id (ANIMAL) as the label
        span = Span(docx, start, end, label=match_id)
        match_spans.append(span)

    docx.ents = list(docx.ents) + filter_spans(match_spans)
    #     doc11.ents = list(doc11.ents) + [span]  # add span to doc.ents

    html = create_visualization2(docx, False)
    # print(len(html))
    # fname = f'{datetime.now().strftime("%m%d%y_%H%M%S")}.html'

    abbrev = circle_abbrev_from_path(fpath)
    out_path = out_path / f'{abbrev}-{fpath.suffix[1:]}-spacy.html'
    # print(out_path)

    tti.save_visualization(out_path, html)


def debug_print_nlp_string_hashes():
    nlp = English()

    # This should really integrate with build_phrase_matcher to get the names
    # Avoid "[E084] Error assigning label ID 18363349229763587234 to span: not in StringStore."
    cols = ['CommonName', 'ScientificName', 'Order', 'FamilyCommon', 'FamilyScientific',
            'ZCOMMONNAME', 'ZSCIENTIFICNAME',
            'COMHYBRID', 'SCIHYBRID', 'FAMCOMHYBRID', 'FAMSCIHYBRID', 'ORDHYBRID', 'COMSLASH',
            'SCISLASH', 'FAMCOMSLASH', 'FAMSCISLASH', 'ORDSLASH', 'COMFORM', 'SCIFORM',
            'FAMCOMFORM', 'FAMSCIFORM', 'ORDFORM', 'COMINTERGRADE', 'SCIINTERGRADE',
            'FAMCOMINTERGRADE', 'FAMSCIINTERGRADE', 'ORDINTERGRADE', 'COMDOMESTIC',
            'SCIDOMESTIC', 'FAMCOMDOMESTIC', 'FAMSCIDOMESTIC', 'ORDDOMESTIC', 'COMSPUH',
            'SCISPUH', 'FAMCOMSPUH', 'FAMSCISPUH', 'ORDSPUH', 'COMISSF', 'SCIISSF',
            'FAMCOMISSF', 'FAMSCIISSF', 'ORDISSF', 'COMSPECIES', 'SCISPECIES', 'FAMCOMSPECIES',
            'FAMSCISPECIES', 'ORDSPECIES'
            ]

    hashes = []
    for col in cols:
        hashes.append(nlp.vocab.strings.add(col))

    for hh in sorted(hashes):
        print(f'{hh:24}  {nlp.vocab.strings[hh]}')

def show_species_and_families(docx):
    families = set()
    species = set()
    for ent in docx.ents:
        if ent.label_ == 'FamilyCommon':
            families.add(ent.text)
        elif ent.label_ == 'CommonName':
            species.add(ent.text)
    #     print(ent.text, ent.start_char, ent.end_char, ent.label_)
    xspecies = ', '.join(sorted(list(species)))
    xfamilies = ', '.join(sorted(list(families)))

    print(f'Species: {xspecies}')
    print(f'Families: {xfamilies}')

