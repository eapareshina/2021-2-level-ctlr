"""
Pipeline for text processing implementation
"""
import re
from pathlib import Path

from pymystem3 import Mystem
from pymorphy2 import MorphAnalyzer

from constants import ASSETS_PATH
from core_utils.article import Article, ArtifactType


class EmptyDirectoryError(Exception):
    """
    No data to process
    """


class InconsistentDatasetError(Exception):
    """
    Corrupt data:
        - numeration is expected to start from 1 and to be continuous
        - a number of text files must be equal to the number of meta files
        - text files must not be empty
    """


class MorphologicalToken:
    """
    Stores language params for each processed token
    """

    def __init__(self, original_word):
        self.original_word = original_word
        self.normalized_form = ''
        self.tags_mystem = ''
        self.tags_pymorphy = ''

    def get_cleaned(self):
        """
        Returns lowercased original form of a token
        """
        return self.original_word.lower()

    def get_single_tagged(self):
        """
        Returns normalized lemma with MyStem tags
        """
        return f"{self.normalized_form}<{self.tags_mystem}>"

    def get_multiple_tagged(self):
        """
        Returns normalized lemma with PyMorphy tags
        """
        return f"{self.normalized_form}<{self.tags_mystem}>({self.tags_pymorphy})"


class CorpusManager:
    """
    6,
    Works with articles and stores them
    """

    def __init__(self, path_to_raw_txt_data: str):
        self.path_to_raw_txt_data = path_to_raw_txt_data
        self._storage = {}
        self._scan_dataset()

    def _scan_dataset(self):
        """
        Register each dataset entry
        """
        path_to_raws = Path(self.path_to_raw_txt_data).glob('*_raw.txt')
        pattern = re.compile(r'\d+')

        for file in path_to_raws:
            article_id = int(pattern.search(file.name).group())
            self._storage[article_id] = Article(url=None, article_id=article_id)

    def get_articles(self):
        """
        Returns storage params
        """
        return self._storage


class TextProcessingPipeline:
    """
    Process articles from corpus manager
    """

    def __init__(self, corpus_manager: CorpusManager):
        self.corpus_manager = corpus_manager

    def run(self):
        """
        Runs pipeline process scenario
        """
        articles = self.corpus_manager.get_articles().values()

        for article in articles:
            tokens = self._process(article.get_raw_text())
            tokens_for_article = []
            single_tagged_tokens = []
            multiple_tagged_tokens = []
            for token in tokens:
                tokens_for_article.append(token.get_cleaned())
                single_tagged_tokens.append(token.get_single_tagged())
                multiple_tagged_tokens.append(token.get_multiple_tagged())
            article.save_as(' '.join(tokens_for_article), ArtifactType.cleaned)
            article.save_as(' '.join(single_tagged_tokens), ArtifactType.single_tagged)
            article.save_as(' '.join(multiple_tagged_tokens), ArtifactType.multiple_tagged)
            print(self.get_freq_dict_pos())

    def get_freq_dict_pos(self):
        articles = self.corpus_manager.get_articles().values()
        for article in articles:
            with open(article.get_file_path(ArtifactType.single_tagged), encoding="utf-8") as file:
                text = file.read()
                freqs_dict = {}
                pos_pattern = re.compile(r"<([A-Z]+)")
                tags = pos_pattern.finditer(text)
                for tag in tags:
                    pos_name = tag.group(1)
                    if pos_name not in freqs_dict:
                        freqs_dict[pos_name] = 1
                    else:
                        freqs_dict[pos_name] += 1
                return freqs_dict

    def _process(self, raw_text: str):
        """
        Processes each token and creates MorphToken class instance
        """
        analyzed_cleaned_text = Mystem().analyze(raw_text)
        tokens = []
        morph = MorphAnalyzer()
        for token in analyzed_cleaned_text:
            if ('analysis' not in token) or (not token['analysis']) \
                    or ('lex' not in token['analysis'][0] or 'gr' not in token['analysis'][0]):
                continue
            if ('text' not in token) or (not token['text']):
                continue
            morphological_token = MorphologicalToken(token['text'])
            morphological_token.normalized_form = token['analysis'][0]['lex']
            morphological_token.tags_mystem = token['analysis'][0]['gr']
            word = morph.parse(token['text'])
            if not word:
                continue
            morphological_token.tags_pymorphy = word[0].tag
            tokens.append(morphological_token)
        return tokens


def validate_dataset(path_to_validate):
    """
    Validates folder with assets
    """
    path_to_dataset = Path(path_to_validate)

    if not path_to_dataset.exists():
        raise FileNotFoundError

    if not path_to_dataset.is_dir():
        raise NotADirectoryError

    if not list(path_to_dataset.iterdir()):
        raise EmptyDirectoryError

    txts = list(path_to_dataset.glob('*_raw.txt'))
    jsons = list(path_to_dataset.glob('*_meta.json'))

    digit_pattern = re.compile(r'\d+')

    txt_indices = []
    json_indices = []

    for txt, json in zip(txts, jsons):
        match_txt = re.match(digit_pattern, txt.name).group()
        match_json = re.match(digit_pattern, json.name).group()
        if not match_txt or not match_json:
            raise InconsistentDatasetError
        txt_indices.append(int(match_txt))
        json_indices.append(int(match_json))

    txt_indices = sorted(txt_indices)
    json_indices = sorted(json_indices)

    for file in path_to_dataset.iterdir():
        if file.stat().st_size == 0:
            raise InconsistentDatasetError

    if txt_indices[0] != 1 or json_indices[0] != 1:
        raise InconsistentDatasetError

    for i, txt_id in enumerate(txt_indices):
        if i + 1 != txt_id:
            raise InconsistentDatasetError

    for i, json_id in enumerate(json_indices):
        if i + 1 != json_id:
            raise InconsistentDatasetError

    if sorted(txt_indices) != sorted(json_indices):
        raise InconsistentDatasetError

    if not check_if_balanced_and_numeration(path_to_validate):
        raise InconsistentDatasetError


def check_if_balanced_and_numeration(path_to_validate):
    txts = list(path_to_validate.glob('*_raw.txt'))
    jsons = list(path_to_validate.glob('*_meta.json'))
    if len(txts) != len(jsons):
        return False
    return True


def main():
    validate_dataset(ASSETS_PATH)
    corpus_manager = CorpusManager(path_to_raw_txt_data=ASSETS_PATH)
    pipeline = TextProcessingPipeline(corpus_manager=corpus_manager)
    pipeline.run()


if __name__ == "__main__":
    main()
