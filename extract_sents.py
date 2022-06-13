#!/usr/bin/env python

import argparse
import nicer
from multiprocessing import Pool
from itertools import repeat

from load_tagged_sent import load_one_sent_tags
from tagger import split_sentence_id

# Extracts sentences and tags that begin with words in word_file
# from tagged sentences

def read_one(fn):
    # Input: file of sentences/proofs
    # Returns list of ids and sentences
    f = open(fn, "r")
    lines = f.readlines()
    ids, sents = split_sentence_id(lines)
    f.close()
    return ids, sents

def check_first_word(sent, word):
    # Input: sentence with tags (connected by _ ), word
    # Returns sentence if the first word of the sentence is word
    sent_id, sent_tags = load_one_sent_tags(sent)
    if sent_tags[0][0] == word:
        return sent

def make_bins(args):
    # Extract sentences that begin with specified word from tagged file
    # Input: tagged file, word/words (file)
    if args.word:
        word_list = args.word.split()

    elif args.word_file:
        word_list = args.word_file.read().splitlines()
        args.word_file.close()
    
    if not args.extension:
        args.extension = ""

    for word in word_list:
        file_name = "word_bins/" + word + args.extension + ".txt"
        output = open(file_name, "w")
        if args.unique:
            file_name_unique = "word_bins/unique/" + word + args.extension + ".txt"
            unique_sents = set()
            unique_output = open(file_name_unique, "w")
          
        with open(output, "w") as o:  
            with open(args.file, "r") as fd:
                with Pool(processes=args.cores) as p:          
                    for line in p.starmap(
                        check_first_word,
                        zip(
                            fd.readlines(),
                            repeat(word),
                            ),
                                50,
                        ):
                            if line:
                                sent = line.split("\t")[1]
                                o.write(sent)
                                if args.unique:
                                    if sent not in unique_sents:
                                        unique_sents.add(sent)
                                        unique_output.write(sent) 
                                
                    if args.unique:
                        unique_output.close()
        
def main(args):
    make_bins(args)

if __name__ == '__main__':
    nicer.make_nice()
    parser = argparse.ArgumentParser()

    parser.add_argument("--file", "-f", 
                            help="txt file to read proof from")

    parser.add_argument("--list", "-l", nargs='*',
                            help="list of txt files to read proof from")
    
    parser.add_argument("--output", "-o", type=argparse.FileType('w'),
                            help="txt file to write results to")

    parser.add_argument( "--cores", "-c",
                            help="number of cores to use", type=int, default=4)
    
    parser.add_argument("--word", "-w", 
                            help="single word as word list")
    
    parser.add_argument("--extension", "-e", 
                            help="custom extension for filename")
    
    parser.add_argument("--word_file", "-wf", type=argparse.FileType('r'),
                            help="txt file to read word list from")
    
    parser.add_argument("--unique", "-u", action="store_true",
                            help="store unique sentences")

                            
    
    
    args = parser.parse_args()

    main(args)
    





    
    
