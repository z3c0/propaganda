import textual_analysis
import report

# run scrape.py first

if __name__ == '__main__':
    textual_analysis.term_freq_by_inverse_document_freq()
    report.build()
