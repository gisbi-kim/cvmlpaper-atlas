"""초록에서 단어 빈도 사전 생성 → word_book.json / word_book.csv

실행: python _make_word_book.py
"""
import json
import re
import collections
import csv

from _clean import is_front_matter, is_translated_dup

STOPWORDS = {
    'a','an','the','and','or','but','in','on','at','to','for','of','with',
    'by','from','as','is','was','are','were','be','been','being','have',
    'has','had','do','does','did','will','would','could','should','may',
    'might','shall','this','that','these','those','it','its','we','our',
    'their','they','he','she','i','you','not','no','also','can','via',
    'which','who','when','where','what','how','than','then','so','if',
    'while','both','each','more','such','any','all','up','into','about',
    'through','based','using','used','show','shown','propose','proposed',
    'present','presented','paper','work','approach','method','model',
    'results','result','experiments','experimental','evaluate','evaluation',
}

with open('all_enriched.json', encoding='utf-8') as f:
    papers = json.load(f)

word_freq = collections.Counter()
paper_words = {}  # doi -> list of (word_idx, freq)

vocab = []
word2idx = {}

_tok = re.compile(r'[a-z]{3,}')

for p in papers:
    if is_front_matter(p.get('title')) or is_translated_dup(p.get('title')):
        continue
    doi = (p.get('doi') or '').strip()
    if not doi:
        continue
    text = (p.get('abstract') or '') + ' ' + (p.get('title') or '')
    words = _tok.findall(text.lower())
    words = [w for w in words if w not in STOPWORDS and len(w) >= 3]
    if not words:
        continue
    local = collections.Counter(words)
    word_freq.update(local)

# Build vocab from top words
top_words = [w for w, _ in word_freq.most_common(5000)]
for i, w in enumerate(top_words):
    word2idx[w] = i
vocab = top_words

# Per-paper word index list
for p in papers:
    if is_front_matter(p.get('title')) or is_translated_dup(p.get('title')):
        continue
    doi = (p.get('doi') or '').strip()
    if not doi:
        continue
    text = (p.get('abstract') or '') + ' ' + (p.get('title') or '')
    words = _tok.findall(text.lower())
    words = [w for w in words if w not in STOPWORDS and w in word2idx]
    if not words:
        continue
    local = collections.Counter(words)
    paper_words[doi] = sorted(
        [(word2idx[w], c) for w, c in local.items()],
        key=lambda x: -x[1]
    )[:30]

out = {'vocab': vocab, 'papers': paper_words}
with open('word_book.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False)

with open('word_book.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['word', 'count'])
    for word, cnt in word_freq.most_common(5000):
        w.writerow([word, cnt])

print(f"vocab size: {len(vocab)}")
print(f"papers with words: {len(paper_words)}")
print(f"Top 20 words: {top_words[:20]}")
