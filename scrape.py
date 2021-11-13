
import requests
import pandas as pd
import pprint as pp
import bs4


SUBREDDIT_NAME = 'propaganda'

REDDIT_ROOT_URL = 'https://old.reddit.com'

SUBREDDIT_URL = f'{REDDIT_ROOT_URL}/r/{SUBREDDIT_NAME}/'

# use a standard browser agent to circumvent reddit blocking the requests
MOZILLA_USER_AGENT = {'User-Agent': 'Mozilla/5.0'}


def parse_posts_to_records(posts):
    post_records = list()
    for post in posts:
        post_id = post['id']
        subreddit = post['data-subreddit']
        author = post['data-author']
        domain = post['data-domain']
        comments = REDDIT_ROOT_URL + post['data-permalink']
        comments_count = post['data-comments-count']
        score = post['data-score']
        timestamp = post['data-timestamp']

        title_soup = post.find('a', attrs={'class': 'title'})

        if domain == 'self.propaganda':
            post_type = 'text'
        elif domain in ('youtube.com', 'youtu.be', 'vimeo.com', 'v.redd.it'):
            post_type = 'video'
        elif domain in ('imgur.com', 'i.imgur.com', 'i.redd.it'):
            post_type = 'image'
        else:
            post_type = 'link'

        link = None if domain == 'self.propaganda' else title_soup['href']
        domain = None if domain == 'self.propaganda' else domain

        title = title_soup.get_text()

        post_record = {'post_id': post_id,
                       'subreddit': subreddit,
                       'author': author,
                       'timestamp': timestamp,
                       'type': post_type,
                       'domain': domain,
                       'title': title,
                       'score': score,
                       'comments_count': comments_count,
                       'link': link,
                       'comments': comments}

        post_records.append(post_record)

    return post_records


def scrape_subreddit_posts() -> list:

    response = requests.get(SUBREDDIT_URL, headers=MOZILLA_USER_AGENT)
    subreddit_soup = bs4.BeautifulSoup(response.text, 'lxml')
    posts_table = subreddit_soup.find(attrs={'id': 'siteTable'})
    posts = posts_table.find_all(attrs={'class': 'thing'})
    post_records = parse_posts_to_records(posts)

    return post_records


def verify_over_18(target_url: str):
    request_kwargs = {'url': f'https://old.reddit.com/over18?dest={target_url}',
                      'headers': MOZILLA_USER_AGENT,
                      'data': {'over18': 'yes'}}

    return requests.post(**request_kwargs)


def get_author_submissions(author: str, count=100):
    submissions_url = (f'{REDDIT_ROOT_URL}/user/{author}/submitted/'
                       f'?limit={str(count)}')

    response = verify_over_18(submissions_url)
    submissions_soup = bs4.BeautifulSoup(response.text, 'lxml')
    posts_table = submissions_soup.find(attrs={'id': 'siteTable'})
    posts = posts_table.find_all(attrs={'class': 'thing'})
    post_records = parse_posts_to_records(posts)

    return post_records


if __name__ == '__main__':
    posts_df = pd.DataFrame(scrape_subreddit_posts())

    posts_df.to_csv('posts.csv', index=False)

    author_post_records = list()

    for author in posts_df['author'].unique():
        author_posts = get_author_submissions(author)
        author_post_records += author_posts

    author_posts_df = pd.DataFrame(author_post_records)

    posts_df.to_csv('propaganda_posts.csv', index=False)
    author_posts_df.to_csv('propaganda_author_submissions.csv', index=False)
