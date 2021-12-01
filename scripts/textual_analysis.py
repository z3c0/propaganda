
import re
from typing import List
import numpy as np
import pandas as pd
import string
import json

from nltk.corpus import stopwords
from nltk.tokenize import RegexpTokenizer
from nltk.stem import SnowballStemmer


WORD_PATTERN = re.compile(r'[a-zA-Z]+')
STOPWORDS = np.r_[np.unique(stopwords.words('english')),
                  np.unique(['-', 'propaganda'])]


stemmer = np.vectorize(SnowballStemmer('english', ignore_stopwords=True).stem)
tokenizer = RegexpTokenizer('[A-Za-z]+').tokenize


def tokenize(text: str) -> List[str]:
    words = np.array(tokenizer(text))
    tokens = np.array(stemmer(words))

    not_stopword = np.isin(tokens, STOPWORDS, invert=True)
    tokens = tokens[not_stopword]
    words = words[not_stopword]

    not_punctuation = np.isin(tokens, list(string.punctuation), invert=True)
    tokens = tokens[not_punctuation]
    words = words[not_punctuation]

    not_too_short = np.vectorize(len)(tokens) > 1
    tokens = tokens[not_too_short]
    words = words[not_too_short]

    return tokens, words


if __name__ == '__main__':
    target_snapshot_path = 'data/20211130/propaganda_author_submissions.csv'
    submissions_df = pd.read_csv(target_snapshot_path)

    target_features = ['subreddit', 'author', 'timestamp', 'title', 'score',
                       'comments_count']

    post = pd.DataFrame(submissions_df[target_features])
    post['document'] = post.title.apply(tokenize)
    post['words'] = post.document.apply(lambda n: list(n[1]))
    post['document'] = post.document.apply(lambda n: list(n[0]))

    author = post[['author', 'document', 'words']].groupby('author').sum()

    unique_terms = np.unique(np.concatenate(np.array(author.document.apply(np.array))))
    doc_freq = dict()
    for term in unique_terms:
        try:
            doc_freq[term] += 1
        except KeyError:
            doc_freq[term] = 1

    for term in unique_terms:
        doc_freq[term] = np.log10(len(author.document) / doc_freq[term])

    doc_freq = np.vectorize(doc_freq.get)
    term_freq = author.document.apply(lambda n: np.unique(n, return_counts=True))

    tf_idf = term_freq.apply(lambda n: (n[0], (n[1] / len(n[1])) * doc_freq(n[0])))

    tf_idf = tf_idf.apply(lambda n: np.stack(n, axis=1))
    tf_idf = tf_idf.apply(lambda n: sorted(n, key=lambda n: n[1], reverse=True))

    author['tf_idf'] = tf_idf.apply(lambda d: {n[0]: n[1] for n in d})
    author = pd.DataFrame(author[['document', 'words', 'tf_idf']])

    words = author.apply(lambda n: {w: n['tf_idf'][t] for t, w in list(zip(n['document'], n['words']))}, axis=1)

    words = words.apply(lambda n: [{'term': k, 'tf_idf': v} for k, v in n.items()])

    words_json = list()
    for author in words.index:
        words_json.append({'author': author,
                           'term': words[author]})

    json.dump(words_json, open('data/20211130/author_terms.json', 'w'))
