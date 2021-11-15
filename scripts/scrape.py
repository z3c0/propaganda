
import datetime as dt
import requests
import pandas as pd
import bs4

REDDIT_ROOT_URL = 'old.reddit.com'

# use a standard browser agent to circumvent reddit blocking the requests
MOZILLA_USER_AGENT = {'User-Agent': 'Mozilla/5.0'}


class SubredditScraper:

    @staticmethod
    def parse_posts_to_records(posts):
        post_records = list()
        for post in posts:
            author = post.get('data-author', '[deleted]')

            post_id = post['id']
            subreddit = post['data-subreddit']
            domain = post['data-domain']
            comments = f'https://{REDDIT_ROOT_URL}' + post['data-permalink']
            comments_count = post['data-comments-count']
            score = post['data-score']
            timestamp = post['data-timestamp']

            title_soup = post.find('a', attrs={'class': 'title'})

            if domain == f'self.{subreddit}':
                post_type = 'text'
            elif domain in ('youtube.com', 'youtu.be',
                            'vimeo.com', 'v.redd.it'):
                post_type = 'video'
            elif domain in ('imgur.com', 'i.imgur.com', 'i.redd.it'):
                post_type = 'image'
            else:
                post_type = 'link'

            link = (None if domain == f'self.{subreddit}'
                    else title_soup['href'])
            domain = None if domain == f'self.{subreddit}' else domain

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

    @staticmethod
    def posts(subreddit: str) -> list:
        subreddit_url = f'https://{REDDIT_ROOT_URL}/r/{subreddit}/'
        response = requests.get(subreddit_url, headers=MOZILLA_USER_AGENT)

        is_quarantined = False

        if response.status_code == 403:
            redirect_history = response.history.pop()
            if redirect_history.status_code == 302:
                redirect_location = redirect_history.headers.get('location')
                redirect_location = redirect_location.split('?')[0]
                redirect_location = redirect_location.split('/')[-1]

                if redirect_location == 'quarantine':
                    is_quarantined = True
                    response = SubredditScraper.verify_quarantine(subreddit)
                else:
                    raise Exception(f'Unknown Redirect: {redirect_location}')

        subreddit_soup = bs4.BeautifulSoup(response.text, 'lxml')
        posts_table = subreddit_soup.find(attrs={'id': 'siteTable'})
        posts = posts_table.find_all(attrs={'class': 'thing'})
        post_records = SubredditScraper.parse_posts_to_records(posts)

        post_records = [dict(quarantined=is_quarantined, **p)
                        for p in post_records]

        return post_records

    @staticmethod
    def verify_over_18(target_url: str):
        over_18_url = (f'https://{REDDIT_ROOT_URL}/over18'
                       f'?dest={target_url}')

        request_kwargs = {'url': over_18_url,
                          'headers': MOZILLA_USER_AGENT,
                          'data': {'over18': 'yes'}}

        return requests.post(**request_kwargs)

    @staticmethod
    def verify_quarantine(subreddit: str):
        target_url = f'https://{REDDIT_ROOT_URL}/r/{subreddit}'
        quarantine_url = (f'https://{REDDIT_ROOT_URL}/quarantine'
                          f'?dest={target_url}')

        request_kwargs = {'url': quarantine_url,
                          'headers': MOZILLA_USER_AGENT,
                          'data': {'sr_name': subreddit,
                                   'accept': 'yes'}}

        return requests.post(**request_kwargs)

    @staticmethod
    def user_submissions(author: str, count=100):
        submissions_url = (f'{REDDIT_ROOT_URL}/user/{author}/submitted/'
                           f'?limit={str(count)}')

        submissions_url = 'https://' + submissions_url

        response = SubredditScraper.verify_over_18(submissions_url)
        submissions_soup = bs4.BeautifulSoup(response.text, 'lxml')
        posts_table = submissions_soup.find(attrs={'id': 'siteTable'})
        posts = posts_table.find_all(attrs={'class': 'thing'})
        post_records = SubredditScraper.parse_posts_to_records(posts)

        return post_records


if __name__ == '__main__':

    posts = SubredditScraper.posts('propaganda')
    posts_df = pd.DataFrame(posts)

    posts_df.to_csv('posts.csv', index=False)

    author_post_records = list()

    for author in posts_df['author'].unique():
        author_posts = SubredditScraper.user_submissions(author)
        author_post_records += author_posts

    author_posts_df = pd.DataFrame(author_post_records)

    date_str = dt.date.today().strftime('%Y%m%d')

    posts_df.to_csv(f'propaganda_posts_{date_str}.csv', index=False)
    author_posts_df.to_csv(f'propaganda_author_submissions_{date_str}.csv', index=False)
