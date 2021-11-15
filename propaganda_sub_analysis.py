from re import sub
import pandas as pd
import pprint as pp

from scrape import SubredditScraper
from whois import whois

author_posts_df = pd.read_csv('propaganda_author_submissions.csv')
propaganda_posts_df = pd.read_csv('propaganda_posts.csv')

author_posts_df = author_posts_df[author_posts_df.type == 'link']
author_posts_df = author_posts_df.drop('type', axis=1)


def analyze_crossposts():
    sub_df = propaganda_posts_df
    submissions_df = author_posts_df

    for author in sub_df.author.unique():

        propaganda_posts = pd.DataFrame(sub_df[sub_df.author == author])
        other_posts = submissions_df[submissions_df.author == author]
        other_posts = other_posts[other_posts.subreddit != 'propaganda']
        other_posts = pd.DataFrame(other_posts)

        is_crosspost = propaganda_posts.link.isin(other_posts.link.unique())

        crossposts = pd.DataFrame(propaganda_posts[is_crosspost])

        if len(crossposts) == 0:
            continue

        print('=' * 120)
        print(f'{author:^120}')
        print('=' * 120)

        for _, post in crossposts.iterrows():
            other_versions = other_posts[other_posts.link == post.link]
            print(other_versions, end='\n\n')


def analyze_domains():
    '''DO NOT USE - work-in-progress'''

    domain_analysis = list()

    for domain in author_posts_df['domain'].unique():
        print(f'querying {domain}...')
        whois_results = whois(domain)

        if whois_results.get('unknown_tld'):
            continue

        country = whois_results['registrant_country']
        domain_analysis.append((domain, country))

    pp.pprint(domain_analysis)


def download_posts_from_subreddits(subreddits: list):
    all_zee_posts = list()
    for subreddit in subreddits:
        all_zee_posts += SubredditScraper.posts(subreddit)

    all_zee_posts_df = pd.DataFrame(all_zee_posts)
    all_zee_posts_df.to_csv('all_the_posts.csv', index=False)


if __name__ == '__main__':
    analyze_crossposts()
