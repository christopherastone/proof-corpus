#!/usr/bin/env python

import pickle
import argparse
import sys
import nicer
import math
import gc

from multiprocessing import Pool
from itertools import repeat
from collections import Counter
from scipy.stats.contingency import chi2_contingency
from scipy.stats import chi2

from ngrams import return_ngrams
from sent_tools import *

# remove all punctuation, lower alias
def clean_sent(line, keep_punct=False):
    _, sent = split_sentence_id(line)
    if keep_punct:
        tokens = [w.lower() if w not in ALIASES else w for w in tokenize(sent)]
    else:
        tokens = [w.lower() if w not in ALIASES else w for w in tokenize(sent) if w not in PUNCTUATION]
    
    return " ".join(tokens)

def save_ngrams(files, output, n):
    sentences = []
    for fd in files:
        for line in fd.readlines():
            sentences.extend([  tokenize(clean_sent(line))  ])
        print("done", fd, flush=True)
        fd.close()

    ngrams = []
    len_sent = len(sentences)
    for ind, sent in enumerate(sentences):
        if ind % 1000000 == 0:
            print("Percent done: {}%".format(round(ind/len_sent*100, 2)))
        ngram = list(return_ngrams(sent, n))
        if ngram is not []:
            ngrams.extend(ngram)

    print("dumping", flush=True)
    with open(output, "wb") as resource:
        pickle.dump(ngrams, resource)

    unigrams = [word for sent in sentences for word in sent]
    return ngrams, unigrams

def pointwise_mutual_information(ngram, ngram_cnt, unigram_cnt):
    p_ngram = get_ngram_probability(ngram_cnt, ngram)
    p_unigram_product = get_unigram_probability_product(unigram_cnt, ngram)
    return math.log(p_ngram/p_unigram_product, 2)

def get_ngram_probability(dist, ngrams):
    return dist[ngrams] / sum(dist.values())

def get_unigram_probability_product(unigram_cnt, ngram):
    probability = 1
    for unigram in ngram:
        probability *= get_ngram_probability(unigram_cnt, unigram)
    return probability

def bigram_with_mi(ngram, ngram_cnt, unigram_cnt):
    return ngram, pointwise_mutual_information(ngram, ngram_cnt, unigram_cnt)

def chi_squared_bigram(ngram, ngram_cnt, unigram_cnt=None):
    obs =   [
                [   ngram_cnt[ngram],                        get_ngrams_not_second(ngram, ngram_cnt)          ],
                [   get_ngrams_not_first(ngram, ngram_cnt),  get_ngrams_not_first_or_second(ngram, ngram_cnt) ]
            ]

    chi2float, _, _, _ = chi2_contingency(obs)
    return chi2float

def get_ngrams_not_first(ngram, ngram_cnt):
    count = 0
    for key in ngram_cnt.keys():
        if key[0] is not ngram[0] and key[1] is ngram[1]:
            count += ngram_cnt[key]
    return count

def get_ngrams_not_second(ngram, ngram_cnt):
    count = 0
    for key in ngram_cnt.keys():
        if key[0] is ngram[0] and key[1] is not ngram[1]:
            count += ngram_cnt[key]
    return count

def get_ngrams_not_first_or_second(ngram, ngram_cnt):
    count = 0
    for key in ngram_cnt.keys():
        if key[0] is not ngram[0] and key[1] is not ngram[1]:
            count += ngram_cnt[key]
    return count

def compare_critical(chi, dof, confidence_level):
    critical = chi2.ppf(confidence_level, dof)
    if abs(chi) >= critical:
        return True
    else:
        return False

def bigram_with_chi_squared(ngram, ngram_cnt, unigram_cnt):
    return ngram, chi_squared_bigram(ngram, ngram_cnt, unigram_cnt)

def make_ngram_cnt(ngrams, freq_threshold=None):
    cnt = Counter()
    for ngram in ngrams:
        cnt[ngram] += 1

    if freq_threshold:
        keys = list(cnt.keys())
        for key in keys:
            if cnt[key] < freq_threshold:
                del cnt[key]
    return cnt

def make_unigram_cnt(unigrams, ngram_cnt):
    freq_unigrams = set([uni for ngram in ngram_cnt.keys() for uni in ngram])
    unigram_cnt = Counter([unigram for unigram in unigrams if unigram in freq_unigrams])
    return unigram_cnt

def main(args):
    if args.files:
        ngrams, unigrams = save_ngrams(args.files, args.ngram_file, args.n)

    else:
        print("loading ngrams", flush=True)
        with open(args.ngram_file, "rb") as resource:
            ngrams = pickle.load(resource)
            print("done loading ngrams", flush=True)
        unigrams = [ngram[0] for ngram in ngrams]

    print("frequency", flush=True)
    ngram_cnt = make_ngram_cnt(ngrams, args.frequency)
    del ngrams
    gc.collect()

    print("making unigram counter", flush=True)
    unigram_cnt = make_unigram_cnt(unigrams, ngram_cnt)
    del unigrams
    gc.collect()

    print("MI", flush=True)
    mi_dict = {ngram : pointwise_mutual_information(ngram, ngram_cnt, unigram_cnt) for ngram in ngram_cnt.keys()}
    
    args.cores = min(args.cores, 15)

    # with Pool(processes=args.cores) as p:
    #     mi_dict = {}
    #     mi_dict.update(
    #               p.starmap(
    #                     bigram_with_mi,
    #                     zip(
    #                         ngram_cnt.keys(),
    #                         repeat(ngram_cnt),
    #                         repeat(unigram_cnt),
    #                     ),
    #                    25
    #                 )
    #               )

    mi_filtered = [ngram for ngram in mi_dict.keys() if mi_dict[ngram] > args.mi]

    print("chi", flush=True)
    chi_dict = {ngram : chi_squared_bigram(ngram, ngram_cnt, unigram_cnt) for ngram in mi_filtered}

    # with Pool(processes=args.cores) as p:
    #     chi_dict = {}
    #     chi_dict.update(
    #               p.starmap(
    #                 bigram_with_chi_squared,
    #                 zip(
    #                     mi_filtered,
    #                     repeat(ngram_cnt),
    #                     repeat(unigram_cnt),
    #                 ),
    #                 25
    #               )
    #       )

    del mi_filtered
    gc.collect()

    print("done making dict", flush=True)
    chi_filtered = [ngram for ngram in chi_dict.keys() if compare_critical(chi_dict[ngram], 1, args.chi_2)]

    print("done calculating", flush=True)
    for ngram in chi_filtered:
        ngram_string = " ".join(ngram)
        args.output.write(ngram_string + "\t" 
                            + str(ngram_cnt[ngram]) + "\t" 
                            + str(mi_dict[ngram]) + "\t" 
                            + str(chi_dict[ngram]) + "\n")
    args.output.close()

if __name__ == "__main__":
    nicer.make_nice()
    parser = argparse.ArgumentParser()

    parser.add_argument("--files", "-f", nargs="*", type=argparse.FileType("r"),
                        help="txt file to read proof from")

    parser.add_argument("--ngram_file", "-nf",
                        help="pk file to read/write ngrams")
    
    parser.add_argument("--n", "-n", type=int, default=2,
                        help="value of n for ngrams")

    parser.add_argument("--cores", "-c", type=int, default=4,
                        help="number of cores")

    parser.add_argument("--output", "-o", default=sys.stdout, type=argparse.FileType("w"),
                        help="file to write results to")

    parser.add_argument("--frequency", "-F", type=int, default=100,
                        help="threshold for frequency")

    parser.add_argument("--mi", "-MI", type=int, default=5,
                        help="threshold for MI")

    parser.add_argument("--chi_2", "-C", type=float, default=0.95,
                        help="confidence interval for chi-squared")

    args = parser.parse_args()

    main(args)
