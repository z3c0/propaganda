
import datetime as dt
import requests
import pandas as pd
import bs4
import os

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

REDDIT_ROOT_URL = 'old.reddit.com'

# use a standard browser agent to circumvent reddit blocking the requests
MOZILLA_USER_AGENT = {'User-Agent': 'Mozilla/5.0'}

TIMEOUT = 5


class SubredditScraper:

    def __init__(self, headless=True):
        profile = webdriver.FirefoxProfile()
        profile.add_extension(extension='ublock_origin-1.37.2-an+fx.xpi')

        options = webdriver.FirefoxOptions()
        options.headless = headless

        self.driver = webdriver.Firefox(profile, options=options)

    def close(self):
        self.driver.quit()

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
        subreddit_url = f'https://{REDDIT_ROOT_URL}/r/{subreddit}?limit=100'
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

    def user_profile(self, username: str) -> dict:
        user_profile = {'username': username, 'suspended': False}

        user_overview_url = f'https://{REDDIT_ROOT_URL}/user/{username}'
        over_18_url = (f'https://{REDDIT_ROOT_URL}/over18'
                       f'?dest={user_overview_url}')

        self.driver.get(over_18_url)

        continue_button_selector = 'div.buttons > button.c-btn[value=yes]'
        continue_button = (By.CSS_SELECTOR, continue_button_selector)
        WebDriverWait(self.driver, TIMEOUT).until(EC.element_to_be_clickable(continue_button))
        self.driver.find_element_by_css_selector(continue_button_selector).click()

        sidebar_locator = (By.CSS_SELECTOR, 'div.side')
        try:
            WebDriverWait(self.driver, TIMEOUT).until(EC.presence_of_element_located(sidebar_locator))
        except TimeoutException as timeout:
            try:
                self.driver.find_element_by_partial_link_text('suspended')
            except NoSuchElementException:
                raise timeout
            else:
                user_profile['suspended'] = True
                return user_profile

        titlebox_rendered = EC.text_to_be_present_in_element(sidebar_locator, username)
        sidebar_is_rendered = WebDriverWait(self.driver, TIMEOUT).until(titlebox_rendered)

        if sidebar_is_rendered:
            sidebar = self.driver.find_element_by_css_selector('div.side')
            titlebox = self.driver.find_element_by_css_selector('div.titlebox')
        else:
            raise Exception('titlebox could not be detected')

        # account created
        account_age_selector = 'span.age > time'
        account_age = titlebox.find_element_by_css_selector(account_age_selector)
        account_age = account_age.get_attribute('datetime')
        account_age = dt.datetime.fromisoformat(account_age)
        user_profile['account_created'] = int(account_age.timestamp())

        # comment karma
        comment_karma = titlebox.find_element_by_class_name('comment-karma')
        comment_karma = int(comment_karma.text.replace(',', ''))
        user_profile['comment_karma'] = comment_karma

        # post karma
        karma_selector = 'span.karma:first-of-type'
        post_karma = titlebox.find_element_by_css_selector(karma_selector)
        post_karma = int(post_karma.text.replace(',', ''))
        user_profile['post_karma'] = post_karma

        # mod subreddits
        try:
            mod_list = sidebar.find_element_by_id('side-mod-list')
            mod_list = mod_list.find_elements_by_css_selector('a')
        except NoSuchElementException:
            mod_list = []
        finally:
            mod_list = [link.get_attribute('href').split(REDDIT_ROOT_URL)[-1]
                        for link in mod_list]
            mod_list = ['/' + ('/'.join([n for n in s.split('/') if n != '']))
                        for s in mod_list]
            user_profile['moderator_of'] = mod_list

        return user_profile


def download_subreddit_posts(subreddit: str):
    scrape = SubredditScraper()

    print(f'scraping posts from /r/{subreddit}...')
    posts = scrape.posts(subreddit)
    posts_df = pd.DataFrame(posts)

    author_post_records = list()
    author_records = list()

    for author in posts_df['author'].unique():
        print(f'scraping {author}\'s profile...')
        author_record = scrape.user_profile(author)

        if not author_record['suspended']:
            print(f'scraping {author}\'s submissions...')
            author_posts = scrape.user_submissions(author)
            author_post_records += author_posts

        author_records.append(author_record)

    author_posts_df = pd.DataFrame(author_post_records)
    author_df = pd.DataFrame(author_records)

    date_str = dt.date.today().strftime('%Y%m%d')

    try:
        os.mkdir(f'data/{date_str}')
    except FileExistsError:
        pass
    finally:
        os.chdir(f'data/{date_str}')

    posts_df.to_csv(f'{subreddit}_posts.csv', index=False)
    author_posts_df.to_csv(f'{subreddit}_author_submissions.csv', index=False)
    author_df.to_json(f'{subreddit}_authors.json', orient='records')


if __name__ == '__main__':
    download_subreddit_posts('propaganda')
