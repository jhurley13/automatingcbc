# TaxonomyTokenIdentify
# from taxonomy_token_identify import TaxonomyTokenIdentify

from pathlib import Path
from typing import Iterable
from typing import List, Set, Dict, Tuple, Union
import sys, traceback

import ftfy
from singleton_decorator import singleton
from spacy import displacy
from spacy.language import Language
from spacy.pipeline import EntityRuler
from spacy.matcher import PhraseMatcher

from fuzzy_phrase_matcher import PhuzzyMatcher, fuzzy_matcher

# Local Imports
from taxonomy import Taxonomy
from nlp_context import NLPContext

FUZZY_THRESHOLD = 85


@singleton
class TaxonomyTokenIdentify(object):
    """Use spaCy to identify taxonomic entities

    Attributes:
    """

    def __init__(self, ctaxonomy: Taxonomy = None, cached_data_path: Path = None, stop_words=None):
        # e.g. interim_data_path
        self.cached_data_path = cached_data_path
        self.ctaxonomy = ctaxonomy
        self.taxonomy = self.ctaxonomy.taxonomy
        self.nlp_context = NLPContext(ctaxonomy)
        self.entity_ruler_path = cached_data_path / 'taxon_entity_ruler.jsonl'
        self.nlp = Language()

        self.stop_words = self.nlp.Defaults.stop_words
        self.stop_words.discard("'s")
        if stop_words:
            for sw in stop_words:
                self.stop_words.add(sw)

        self._entity_patterns, self._matcher_patterns = self.create_taxonomy_patterns()
        self._cached_ruler = None
        self._cached_ruler = self.get_entity_ruler_cached()
        self._phrase_matcher = self.create_phrase_matcher()
        self.build_pipeline()

    # ------------------------------------------------------------------------

    def build_pipeline(self):
        # https://spacy.io/usage/processing-pipelines

        matcher = self.get_phrase_matcher()

        # Now add the fuzzy matchers
        common_name_set = set(self.taxonomy.comNameLower)  # .discard('')
        common_name_tagger = PhuzzyMatcher(self.nlp, common_name_set, fuzzy_matcher, FUZZY_THRESHOLD,
                                           'ZCOMMONNAME', 'fuzzy_common_name', self.stop_words)
        self.nlp.add_pipe(common_name_tagger)

        scientific_name_set = set(self.taxonomy.sciNameLower)  # .discard('')
        scientific_name_set_tagger = PhuzzyMatcher(self.nlp, scientific_name_set, fuzzy_matcher,
                                                   FUZZY_THRESHOLD,
                                                   'ZSCIENTIFICNAME', 'fuzzy_scientific_name',
                                                   self.stop_words)
        self.nlp.add_pipe(scientific_name_set_tagger)

        ruler = self.get_entity_ruler_cached()
        self.nlp.add_pipe(ruler)


    def get_test_text(self, test_path: Path, quiet=True) -> str:
        if not quiet:
            print(f'Processing {test_path.stem}')
        with open(test_path, 'r', encoding="utf-8") as fp:
            text = fp.read()

        # Generally helpful to clean up the text at least a little bit
        text = ftfy.fix_text(text, fix_encoding=True, fix_line_breaks=True,
                             normalization='NFKC',
                             fix_latin_ligatures=True, uncurl_quotes=True).replace('\xad', '-')

        return text

    def save_visualization(self, out_path: Path, html: str):
        # Pass in original filename
        # out_path = output_path #/ f'spacy-{test_path.stem}.html'
        with open(out_path, 'w', encoding="utf-8") as fp:  # , encoding="utf-8"
            _ = fp.write(html)

    def create_taxon_patterns(self, values: list, label: str):
        values = list(set(values))
        taxon_patterns = []
        for val in values:
            # use word_tokenize to properly group "'s"
            tokens = self.nlp.tokenizer(val)
            if len(tokens) == 0:
                continue
            patterns = [{'LOWER': str(tok).lower()} for tok in tokens]
            taxon_pattern = {'label': label, 'pattern': patterns}
            taxon_patterns.append(taxon_pattern)

        return taxon_patterns

    def create_taxonomy_patterns(self) -> Tuple[
        List[List[Dict[str, Union[str, List[Dict[str, str]]]]]], Dict[str, list]]:
        # EntityRuler wants a token pattern (list of dicts)
        # Counts in taxonomy
        # species       10721
        # issf           3800
        # slash           709
        # spuh            653
        # hybrid          462
        # form            122
        # intergrade       31
        # domestic         15

        entity_patterns = [] # token pattern (list of dicts)
        matcher_patterns = {} # phrase matcher (dict)

        # Categories is the set of values in the 'category' field of taxonomy
        # Listed in preferred order
        categories = [
            'species', 'issf', 'slash', 'spuh', 'hybrid',
            'form', 'intergrade', 'domestic',
        ]
        # Cols is the relevant subset of the columns of taxonomy
        # Since we want to prefer Common Name, etc. we need to loop over columns then
        # loop for each category within that
        cols = ['comName', 'sciName', 'familyComName', 'familySciName', 'order']
        # The names of the classes will be e.g. COMSPECIES etc.
        name_prefixes = ['COM', 'SCI', 'FAMCOM', 'FAMSCI', 'ORD']

        accumulation = set()  # avoid duplicates
        patterns = {}
        # taxon_patterns = []
        pattern_names = []

        for cat in categories:
            subdf = self.taxonomy[self.taxonomy.Category == cat]
            for ix, col in enumerate(cols):
                pattern_name = f'{name_prefixes[ix]}{cat}'.upper()
                pattern_names.append(pattern_name)
                # Don't allow duplicates
                values = set([xs.lower() for xs in subdf[col]]) - accumulation
                if len(values) == 0:
                    continue
                accumulation |= values

                # For EntityRuler use
                erp = self.create_taxon_patterns(list(values), pattern_name)
                for pattern in erp:
                    entity_patterns.append(pattern)

                # For PhraseMatcher use
                patterns = [self.nlp(text) for text in values]
                matcher_patterns[pattern_name] = patterns

        # Avoid "[E084] Error assigning label ID 18363349229763587234 to span: not in StringStore."
        # print(f'Patterns in create_taxonomy_patterns: {pattern_names}')
        for pn in pattern_names:
            _ = self.nlp.vocab.strings.add(pn)

        return entity_patterns, matcher_patterns

    def create_phrase_matcher(self) -> PhraseMatcher:
        matcher = PhraseMatcher(self.nlp.vocab)
        for key, val in self._matcher_patterns.items():
            matcher.add(key, None, *val)

        return matcher

    def get_entity_ruler_cached(self) -> EntityRuler:
        if self._cached_ruler:
            return self._cached_ruler

        ruler = EntityRuler(self.nlp, validate=True)
        try:
            if not self.entity_ruler_path.is_file():
                ruler.add_patterns(self._entity_patterns)
                ruler.to_disk(self.entity_ruler_path)
                return ruler

            if self.entity_ruler_path.is_file():
                print('Loading EntityRuler from cache...')
                ruler.from_disk(self.entity_ruler_path)

        except Exception as ee:
            print(ee)
            traceback.print_exc(file=sys.stdout)
            pass

        self._cached_ruler = ruler
        return ruler

    def get_taxonomy_patterns(self) -> Dict[str, list]:
        return self._taxonomy_patterns

    def get_phrase_matcher(self) -> PhraseMatcher:
        return self._phrase_matcher


    # Read and process text
    def spacify_text(self, text, use_fuzzy=False):
        # https://spacy.io/usage/processing-pipelines
        # Only process unique lines
        processed_text = '\n'.join(list(set(text.split('\n'))))

        print('Processing text...')
        if use_fuzzy:
            doc = self.nlp(processed_text.lower())
        else:
            with self.nlp.disable_pipes("fuzzy_common_name", "fuzzy_scientific_name"):
                doc = self.nlp(processed_text.lower())
        print('Processing text done')

        return doc

    def create_visualization(self, docx, show_in_jupyter=True):
        # Create visualization
        # https://developer.mozilla.org/en-US/docs/Web/CSS/linear-gradient
        # https://cssgradient.io
        # https://htmlcolorcodes.com

        print('Creating visualization')

        purplish = 'linear-gradient(90deg, #aa9cfc, #fc9ce7)'  # original
        purplishR = 'linear-gradient(45deg, #fc9ce7, #aa9cfc)'
        yellowish = 'linear-gradient(90deg, #f9fc9c, #fac945)'
        greenish = 'linear-gradient(90deg, #cdfc9c, #5cfa45)'
        aquaish = 'linear-gradient(90deg, #9cfcea, #3cd3e7)'
        aquaishR = 'linear-gradient(45deg, #3cd3e7, #9cfcea)'
        fuchsiaish = 'linear-gradient(90deg, #fc9cde, #ff5aa4)'

        colors = {
            "COMMONNAME": purplish,
            'SCIENTIFICNAME': aquaish,
            'ORDER': greenish,
            'FAMILYCOMMON': yellowish,
            'FAMILYSCIENTIFIC': fuchsiaish,
            'ZCOMMONNAME': purplishR,
            'ZSCIENTIFICNAME': aquaishR
        }
        options = {"ents": ["COMMONNAME", 'SCIENTIFICNAME', 'ORDER',
                            'FAMILYCOMMON', 'FAMILYSCIENTIFIC',
                            'ZCOMMONNAME', 'ZSCIENTIFICNAME'],
                   "colors": colors}

        # displacy.serve(doc, style="ent", options=options)
        html = displacy.render([docx], style="ent", page=True,
                               jupyter=show_in_jupyter, options=options)

        return html

    def show_species_and_families(self, docx):
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

    def filter_out_stopwords(self, words: Iterable[str]) -> List[str]:
        return [word for word in words if not word in self.stop_words]

    def filter_out_stopwords_doc(self, doc) -> List[str]:
        return [word for word in doc if not word.is_stop]

    def filter_no_intersection(self, unidentified: Set[str]) -> Set[str]:
        filter_tokens, _, _ = self.nlp_context.taxonomy_tokens()

        candidates = set()
        for line in unidentified:
            line_tokens = set(self.nlp.tokenizer(line)) - self.stop_words
            intersections = set(filter_tokens) & set(line_tokens)
            if len(intersections) > 0:
                candidates.add(line)

        return candidates
