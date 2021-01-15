import re
from spacy.matcher import PhraseMatcher
from spacy.tokens import Span
import nltk
from nltk.corpus import stopwords
from rapidfuzz import fuzz


# @singleton
class PhuzzyMatcher(object):
    # name = "phuzzy_matcher"

    def __init__(self, nlp, xset, fuzzy_matcher, match, label, name="phuzzy_matcher",
                 stop_words=None):
        self.name = name
        self.nlp = nlp
        self.xset = xset
        # print(f'xset: {len(xset)}')
        self.fuzzy_matcher = fuzzy_matcher
        self.fuzzy_matcher_stopwords = fuzzy_matcher_stopwords if stop_words else fuzzy_matcher
        self.match = match
        self.label = label
        self.stop_words = stop_words

    def __call__(self, doc):
        match_list = []
        if self.stop_words:
            results = self.fuzzy_matcher_stopwords(self.xset, doc.text.lower(), self.match,
                                                   self.stop_words)
        else:
            results = self.fuzzy_matcher(self.xset, doc.text.lower(), self.match)
        for i in results:
            match_list.append(str(i[0].lstrip()))
        patterns = [self.nlp.make_doc(text) for text in match_list]  # noqa: F821
        matcher = PhraseMatcher(self.nlp.vocab, attr='LOWER')
        matcher.add(self.label, None, *patterns)
        matches = matcher(doc)
        seen_tokens = set()
        new_entities = []
        entities = doc.ents
        for match_id, start, end in matches:
            if start not in seen_tokens and end - 1 not in seen_tokens:
                new_entities.append(Span(doc, start, end, label=match_id))
                entities = [
                    e for e in entities if not (e.start < end and e.end > start)
                ]
                seen_tokens.update(range(start, end))

        doc.ents = tuple(entities) + tuple(new_entities)
        return doc


def fuzzy_matcher(features, document, match=None):
    matches = []
    tokens = nltk.word_tokenize(document)
    for feature in features:
        feature_length = len(feature.split(" "))
        for i in range(len(tokens) - feature_length + 1):
            matched_phrase = ""
            j = 0
            for j in range(i, i + feature_length):
                if re.search(r'[,!?{}\[\]]', tokens[j]):
                    break
                matched_phrase = matched_phrase + " " + tokens[j].lower()
            matched_phrase.strip()
            if not matched_phrase == "":
                if fuzz.ratio(matched_phrase, feature.lower()) > match:
                    matches.append([matched_phrase, feature, i, j])
    return matches


def fuzzy_matcher_stopwords(features, document, match=None, stop_words=None):
    matches = []
    tokens = nltk.word_tokenize(document)
    tokens_no_stop = [w for w in tokens if w not in stop_words]
    for feature in features:
        feature_length = len(feature.split(" "))
        for i in range(len(tokens_no_stop) - feature_length + 1):
            matched_phrase = ""
            j = 0
            for j in range(i, i + feature_length):
                if re.search(r'[,!?{}\[\]]', tokens_no_stop[j]):
                    break
                matched_phrase = matched_phrase + " " + tokens_no_stop[j].lower()
            matched_phrase.strip()
            if not matched_phrase == "":
                if fuzz.ratio(matched_phrase, feature.lower()) > match:
                    matches.append([matched_phrase, feature, i, j])
    return matches
