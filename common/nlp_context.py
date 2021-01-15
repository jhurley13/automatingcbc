# NLPContext
# from nlp_context import NLPContext

from typing import Tuple, Set

import inflect
from more_itertools import flatten
from singleton_decorator import singleton
from spacy.lang.en import English


# Local imports
# import acbc_utilities as autil


@singleton
class NLPContext(object):
    """Combined Taxonomy

    Attributes:
     """

    # Call taxonomy_tokens and taxonomy_family_tokens, usually like:
    #   tokens_all, _, _ = nlp_context.taxonomy_tokens()
    # cn_tokens => _tokens_common_name
    #

    def __init__(self, taxonomy=None, reports_path=None):
        self.reports_path = reports_path
        self._taxonomy = taxonomy
        self.nlp = English()

        self.bird_stop_words = {'bird', 'birds', 'summer'}  # , 'species', 'and', 'may', 'allies'

        # For singular/plural determinations
        self._inflect_engine = inflect.engine()

        self._create_all_taxonomy_tokens()

    def _create_all_taxonomy_tokens(self):
        # tk_all, tk_common, tk_scientific = self._create_tokens_for_taxonomy(self._taxonomy.taxonomy_restricted)
        # self._tokens_restricted_common_scientific = tk_all
        # self._tokens_restricted_common_name = tk_common
        # self._tokens_restricted_scientific_name = tk_scientific

        tk_all, tk_common, tk_scientific = self._create_tokens_for_taxonomy(self._taxonomy.taxonomy)
        self._tokens_common_scientific = tk_all
        self._tokens_common_name = tk_common
        self._tokens_scientific_name = tk_scientific

        tk_all, tk_common, tk_scientific = self._create_tokens_for_family(self._taxonomy.taxonomy)
        self._tokens_family_all = tk_all
        self._tokens_family_common_name = tk_common
        self._tokens_family_scientific_name = tk_scientific

    def _create_tokens_for_taxonomy(self, xtaxonomy) -> Tuple[Set, Set, Set]:
        # All, Common, Scientific
        common_names = set(xtaxonomy.comNameLower)
        scientific_names = set(xtaxonomy.sciNameLower)
        common_scientific = (common_names | scientific_names)

        tokens_common_scientific = self.filter_tokens(set(flatten([self.nlp.tokenizer(wd) for wd in common_scientific])))
        tokens_common_name = self.filter_tokens(set(flatten([self.nlp.tokenizer(wd) for wd in common_names])))
        tokens_scientific_name = tokens_common_name | tokens_common_scientific

        return tokens_common_scientific, tokens_common_name, tokens_scientific_name

    def _create_tokens_for_family(self, xtaxonomy) -> Tuple[Set, Set, Set]:
        # All, Common, Scientific
        common_names = set([cn.lower() for cn in xtaxonomy.familyComName])
        scientific_names = set([sn.lower() for sn in xtaxonomy.familySciName])
        common_scientific = (common_names | scientific_names)

        tokens_common_scientific = self.filter_tokens(set(flatten([self.nlp.tokenizer(wd) for wd in common_names])))
        tokens_common_name = self.filter_tokens(set(flatten([self.nlp.tokenizer(wd) for wd in common_names])))
        tokens_scientific_name = tokens_common_name | tokens_common_scientific

        return tokens_common_scientific, tokens_common_name, tokens_scientific_name

    def taxonomy_tokens(self, range_restricted=False):
        # All, Common, Scientific
        if range_restricted:
            return self._tokens_common_scientific, self._tokens_common_name, self._tokens_scientific_name
        else:
            return self._tokens_common_scientific, self._tokens_common_name, self._tokens_scientific_name

    def taxonomy_family_tokens(self):
        # All, Common Name, Scientific Name
        return self._tokens_family_all, self._tokens_family_common_name, self._tokens_family_scientific_name

    def filter_tokens(self, tokens: set) -> Set:
        len1_tokens = set([tok for tok in tokens if len(tok) == 1])
        len2_tokens = set([tok for tok in tokens if len(tok) == 2])

        # This is not all of len2_tokens
        tokens_to_drop = {"'s", '10', '11', 'al', 'f1', 'f2', 'is', 'la', 'mt', 'of', 'oo', 'or', 'ou', 'sp', 'ua'}
        tokens = tokens - (set(len1_tokens) | tokens_to_drop)

        return tokens

    # Write out tokens - DEBUG
    def write_out_tokens(self):
        lines = sorted(list(self._tokens_common_name_lower))
        out_path = self.reports_path / f'nlp_tokens_common_name_lower.txt'
        with open(out_path, 'a', encoding="utf-8") as fp:  # , encoding="utf-8"
            for line in lines:
                line = line.strip()  # encode('utf-8').
                if len(line) > 0:
                    _ = fp.write(line + '\n')

    def effectively_plural(self, word):
        # Either an actual plural or the plural is the same as the singular
        # i.e. the singular form of word, or False if already singular
        singular = self._inflect_engine.singular_noun(word)
        plural = self._inflect_engine.plural_noun(word)
        return singular or (singular == plural) # e.g. 'Killdeer', 'grouse', 'quail
