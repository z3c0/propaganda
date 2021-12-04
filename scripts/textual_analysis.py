import datetime as dt
import re
from typing import Tuple
import numpy as np
import pandas as pd
import string
import json
import os

from nltk.corpus import stopwords
from nltk.tokenize import RegexpTokenizer
from nltk.stem import SnowballStemmer


today = dt.date.today()
today_str = today.strftime('%Y%m%d')

WORD_PATTERN = re.compile(r'[a-zA-Z]+')
STOPWORDS = np.r_[np.unique(stopwords.words('english')),
                  np.unique(stopwords.words('spanish')),
                  np.unique(['-', 'propaganda'])]


stemmer = np.vectorize(SnowballStemmer('english', ignore_stopwords=True).stem)
tokenizer = RegexpTokenizer('[A-Za-z]+').tokenize


def tokenize(text: str) -> Tuple[np.array, np.array]:
    words = np.array(tokenizer(text))

    if len(words) == 0:
        return np.array([]), np.array([])

    tokens = np.array(stemmer(words))

    not_too_short = np.vectorize(len)(tokens) > 1
    tokens, words = tokens[not_too_short], words[not_too_short]

    not_stopword = np.isin(tokens, STOPWORDS, invert=True)
    tokens, words = tokens[not_stopword], words[not_stopword]

    not_punctuation = np.isin(tokens, list(string.punctuation), invert=True)
    tokens, words = tokens[not_punctuation], words[not_punctuation]

    return tokens, words


def term_freq_by_inverse_document_freq():
    target_snapshot_path = f'data/{today_str}/propaganda_author_submissions.csv'
    submissions_df = pd.read_csv(target_snapshot_path)

    target_features = ['author', 'title']

    post = pd.DataFrame(submissions_df[target_features]).drop_duplicates()

    post['document'] = post.title.apply(tokenize)
    post['words'] = post.document.apply(lambda n: list(n[1]))
    post['document'] = post.document.apply(lambda n: list(n[0]))

    title_words = post[['title', 'words']].explode('words')
    title_tokens = post[['title', 'document']].explode('document')

    title_map = pd.concat([title_words, title_tokens['document']], axis=1)
    title_map = title_map.reset_index()[['title', 'words', 'document']]
    title_map.to_csv(f'data/{today_str}/title_terms.csv', index=False, encoding='utf8')

    # concatanate all titles into a single document per author
    author = post[['author', 'document', 'words']].groupby('author').sum()

    unique_terms = np.unique(np.concatenate(np.array(author.document.apply(np.array))))
    doc_freq_map = dict()
    for term in unique_terms:
        try:
            doc_freq_map[term] += 1
        except KeyError:
            doc_freq_map[term] = 1

    for term in unique_terms:
        doc_freq_map[term] = np.log10(len(author.document) / doc_freq_map[term])

    doc_freq = np.vectorize(doc_freq_map.get)

    def tf_idf_func(tokens, occurrences):
        return (occurrences / len(occurrences)) * doc_freq(tokens)

    term_counts = author.document.apply(lambda n: np.unique(n, return_counts=True))

    # n[0] is an author's token vector
    # n[1] is an author's occurrence vector
    tf_idf = term_counts.apply(lambda n: (n[0], tf_idf_func(n[0], n[1]), n[1]))

    # zips the token and occurrence vectors for each author into an array of tuples
    tf_idf = tf_idf.apply(lambda n: np.stack(n, axis=1))

    # convert tuples to dictionaries and add to author dataframe
    author['tf_idf'] = tf_idf.apply(lambda d: {n[0]: n[1] for n in d})
    author['term_counts'] = tf_idf.apply(lambda d: {n[0]: n[2] for n in d})
    author = pd.DataFrame(author[['document', 'words', 'tf_idf', 'term_counts']])

    words = author.apply(lambda n: {w: (n['tf_idf'][t], n['term_counts'][t])
                                    for t, w in list(zip(n['document'], n['words']))}, axis=1)

    words = words.apply(lambda n: [{'term': term, 'tf_idf': tf_idf, 'count': count}
                                   for term, (tf_idf, count) in n.items()])

    words_json = list()
    for author in words.index:
        words_json.append({'author': author,
                           'terms': words[author]})

    json.dump(words_json, open(f'data/{today_str}/author_terms.json', 'w'))
