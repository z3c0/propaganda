# propaganda

This project utilizes components of this package: https://github.com/DannyCork/python-whois

If you are in need of whois functionality, utilize that project over this one - unless you want your software to be free (per the GPLv3)

## getting started

To run these scripts, first install the dependencies with pip

``` cmd
python -m pip install -r requirements.txt
```

`python scrape.py` will download the current top posts of `reddit.com/r/propaganda`.

`python propaganda_sub_analysis.py` will generate a Markdown file with a table of the posts.
