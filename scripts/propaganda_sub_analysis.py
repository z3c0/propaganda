import numpy as np
import pandas as pd
import pprint as pp
import datetime as dt

from scrape import SubredditScraper
from whois import whois

today = dt.date.today()
today_str = today.strftime('%Y%m%d')
last_week_str = (today - dt.timedelta(days=7)).strftime('%Y%m%d')


def fill_nan(df, series, value):
    for row in df.loc[df[series].isnull(), series].index:
        df.at[row, series] = value

    return df


def process_crossposts(sub_df: pd.DataFrame, submissions_df: pd.DataFrame, user_df: pd.DataFrame):
    post_records = list()

    for author in sub_df.author.unique():

        propaganda_posts = sub_df[sub_df.author == author]
        text_posts = propaganda_posts.type == 'text'
        propaganda_posts = pd.DataFrame(propaganda_posts[~text_posts])
        other_posts = submissions_df[submissions_df.author == author]
        other_posts = other_posts[other_posts.subreddit != 'propaganda']
        other_posts = pd.DataFrame(other_posts)

        is_crosspost = propaganda_posts.link.isin(other_posts.link.unique())

        crossposts = pd.DataFrame(propaganda_posts[is_crosspost])

        crosspost_records = list()

        for _, post in crossposts.iterrows():
            other_versions = pd.DataFrame(other_posts[other_posts.link == post.link])
            crosspost_records.append((post.post_id, other_versions.to_dict(orient='records')))

        crossposts = pd.DataFrame(crosspost_records, columns=('post_id', 'other_versions'))
        crossposts = crossposts.set_index('post_id')

        propaganda_posts = propaganda_posts.join(crossposts, on='post_id', how='left')
        propaganda_posts = fill_nan(propaganda_posts, 'other_versions', [])

        propaganda_posts = propaganda_posts.join(user_df, on='author', how='left')

        posts_json_records = propaganda_posts.to_dict(orient='records')

        post_records += posts_json_records

    return post_records


def prepare_data(records: list) -> list:
    processed_records = list()
    for record in records:

        # x-post subreddits
        other_subreddits = ', '.join({'/r/' + v['subreddit']
                                      for v in record['other_versions']})
        record['other_subreddits'] = other_subreddits

        # author
        author = record['author']
        record['author'] = f'[{author}](https://reddit.com/user/{author})'

        moderator_of = record['moderator_of']
        karma_ratio = record['karma_ratio']

        # timestamp
        timestamp = int(record['timestamp']) / 1000
        record['timestamp'] = dt.datetime.fromtimestamp(timestamp)
        record['timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

        # title
        title = record['title'].replace('|', '-')
        link = record['link']
        record['title'] = f'[{title}]({link})'

        # comments
        comment_count = record['comments_count']
        comment_link = record['comments']
        record['comments'] = f'{comment_count} ([view]({comment_link}))'

        # domain
        domain = record['domain']
        if domain in ('old.reddit.com', 'np.reddit.com'):
            if link.find('reddit.com') != -1:
                domain = 'reddit.com/' + '/'.join(link.split('reddit.com/')[1].split('/')[:2])
            record['domain'] = f'[{domain}](https://{domain})'

        new_record = {'Title': record['title'],
                      'Source': record['domain'],
                      'Score': record['score'],
                      'Comments': record['comments'],
                      'Author': record['author_display'],
                      'Post/Comment Karma Ratio': record['karma_ratio'],
                      'Moderator Of': record['moderator_of'],
                      'X-post Subreddits': record['other_subreddits']}

        processed_records.append(new_record)

    return processed_records


def analyze_posts():
    last_week_author_posts_df = pd.read_csv(f'data/{last_week_str}/propaganda_author_submissions.csv')
    last_week_propaganda_posts_df = pd.read_csv(f'data/{last_week_str}/propaganda_posts.csv')
    last_week_author_df = pd.read_json(f'data/{last_week_str}/propaganda_authors.json')

    author_posts_df = pd.read_csv(f'data/{today_str}/propaganda_author_submissions.csv')
    propaganda_posts_df = pd.read_csv(f'data/{today_str}/propaganda_posts.csv')
    author_df = pd.read_json(f'data/{today_str}/propaganda_authors.json')

    # new_author_posts = author_posts_df.post_id.isin(last_week_author_posts_df.post_id)
    new_propaganda_posts = ~propaganda_posts_df.post_id.isin(last_week_propaganda_posts_df.post_id)
    new_authors = ~author_df.username.isin(last_week_author_df.username)

    propaganda_posts_df = propaganda_posts_df[new_propaganda_posts]
    author_df['is_new'] = new_authors

    post_karma = author_df.post_karma.fillna(-np.inf)
    comment_karma = author_df.comment_karma.fillna(-np.inf)

    post_karma = np.where(post_karma == 0, 1, post_karma)
    comment_karma = np.where(comment_karma == 0, 1, comment_karma)
    author_df['karma_ratio'] = post_karma / comment_karma

    author_df['moderator_of'] = author_df.moderator_of.apply(', '.join)

    author_df = author_df.rename({'username': 'author'}, axis=1)

    author_posts_df = author_posts_df[author_posts_df.type != 'text']
    author_posts_df = author_posts_df.drop('type', axis=1)

    author_df = author_df.set_index('author')
    author_df['author_display'] = np.where(author_df.is_new, author_df.index + ' (NEW)', author_df.index)

    post_records_with_crossposts = process_crossposts(propaganda_posts_df, author_posts_df, author_df)
    processed_records = prepare_data(post_records_with_crossposts)

    sort_kwargs = {'key': lambda n: n['Score'], 'reverse': True}
    processed_records = sorted(processed_records, **sort_kwargs)

    processed_data = pd.DataFrame(processed_records)
    posts_report = processed_data[['Title', 'Source', 'Comments', 'Score', 'Author', 'X-post Subreddits']]
    users_columns = ['Author', 'Post/Comment Karma Ratio', 'Moderator Of']
    users_report = processed_data.groupby(users_columns)['Title'].count()
    users_report = users_report.reset_index()
    users_report = users_report.rename({'Title': 'Post Count'}, axis=1)
    users_report = users_report.sort_values('Post Count', ascending=False)

    print(f'New Posts Count: {len(posts_report)}')
    print(f'This Week\'s Author Count: {len(users_report)}')

    posts_report.to_markdown(open(f'data/{today_str}/propaganda_posts.md', 'w', encoding='utf8'), index=False)
    users_report.to_markdown(open(f'data/{today_str}/propaganda_users.md', 'w', encoding='utf8'), index=False)


def analyze_domains():
    '''DO NOT USE - work-in-progress'''
    author_posts_df = pd.read_csv(f'data/{today_str}/propaganda_author_submissions.csv')
    author_posts_df = author_posts_df[author_posts_df.type != 'text']
    author_posts_df = author_posts_df.drop('type', axis=1)

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
    analyze_posts()
