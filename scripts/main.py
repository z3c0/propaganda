import scrape
import textual_analysis
import report


if __name__ == '__main__':
    scrape.download_subreddit_posts('propaganda')
    textual_analysis.term_freq_by_inverse_document_freq()
    report.build()