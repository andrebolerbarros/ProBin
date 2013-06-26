#!/usr/bin/env python
"""
@author: inodb
"""
import sys
import os
import argparse
import subprocess
import errno

from Bio import SeqIO
from Bio.SeqUtils import GC

from BCBio import GFF

TAXONOMY = ('phylum', 'class', 'order', 'family', 'genus', 'species')

def get_gc_and_len_dict(fastafile):
    """Creates a dictionary with the fasta id as key and GC and length as keys
    for the inner dictionary."""
    out_dict = {}

    for rec in SeqIO.parse(fastafile, "fasta"):
        out_dict[rec.id] = {}
        out_dict[rec.id]["GC"] = GC(rec.seq)
        out_dict[rec.id]["length"] = len(rec.seq)

    return out_dict


def get_bedcov_dict(bedcoverage):
    """Uses the BEDTools genomeCoverageBed histogram output to determine mean
    coverage and percentage covered for each contig.
    
    Returns dict with fasta id as key and percentage covered and cov_mean as
    keys for the inner dictionary."""
    out_dict = {}

    # Check if given argument is a file, otherwise use the content of the
    # variable
    if os.path.isfile(bedcoverage):
        fh = open(bedcoverage)
    else:
        fh = bedcoverage.split('\n')[:-1]

    for line in fh:
        cols = line.split()

        try:
            d = out_dict[cols[0]]
        except KeyError:
            d = {}
            out_dict[cols[0]] = d

        if int(cols[1]) == 0:
            d["percentage_covered"] = 100 - float(cols[4]) * 100.0
        else:
            d["cov_mean"] = d.get("cov_mean", 0) + int(cols[1]) * float(cols[4])

    return out_dict


def print_input_table(fastadict, taxonomydict, bedcovdicts, samplenames=None):
    """Writes the input table for Probin to stdout. See hackathon google
    docs."""
    # Header
    sys.stdout.write(("%s" + "\t%s" * 8) % (('contig', 'length', 'GC') + TAXONOMY))
    if samplenames == None:
        # Use index if no sample names given in header
        for i in range(len(bedcovdicts)):
            sys.stdout.write("\tcov_mean_sample_%i\tpercentage_covered_sample_%i\n" % (i, i))
    else:
        # Use given sample names in header
        assert(len(samplenames) == len(bedcovdicts))
        for sn in samplenames:
            sys.stdout.write("\tcov_mean_%s\tpercentage_covered_%s\n" % (sn, sn))

    # Content
    assert(len(fastadict) > 0)
    for acc in fastadict:
        # fasta stats
        sys.stdout.write("%s\t%s\t%s"  %
            (
                acc,
                fastadict[acc]['length'],
                fastadict[acc]['GC']
            )
        )

        # taxonomy
        for t in TAXONOMY:
            try:
                sys.stdout.write("\t%s" % taxonomydict[acc][t])
            except KeyError:
                sys.stdout.write("\tN/A")
                


        # bed coverage stats
        for bcd in bedcovdicts:
            try:
                # Print cov mean
                # If no 0 bases with 0 coverage, then all bases in the contig are covered
                sys.stdout.write("\t%f\t%f" % (bcd[acc]["cov_mean"], bcd[acc].get("percentage_covered", 100)))
            except KeyError:
                # No reads mapped to this contig
                sys.stdout.write("\t0\t0")
        sys.stdout.write("\n")

def get_taxonomy_dict(taxonomyfile):
    """Creates a dictionary from given taxonomy file.
    
    The dictionary has contig name as key for the outer dictionary and genus
    and species as keys for the inner dictionary."""
    outdict = {}

    for line in open(taxonomyfile):
        cols = line.split(',')

        # Should be 7 columns. Contig name, Phylum, Class, Order, Family,
        # Genus, Species.
        assert(len(cols) == len(TAXONOMY) + 1)

        outdict[cols[0]] = dict(zip(TAXONOMY, cols[1:-1] + [cols[-1].rstrip('\n')]))

    return outdict


def generate_input_table(fastafile, taxonomyfile, bamfiles, samplenames=None):
    """Reads input files into dictionaries then prints everything in the table
    format required for running ProBin."""
    bedcovdicts = []
    
    for i, bf in enumerate(bamfiles):
        p = subprocess.Popen(["genomeCoverageBed", "-ibam", bf], stdout=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            print out
            raise Exception('Error with genomeCoverageBed')
        else:
            bedcovdicts.append(get_bedcov_dict(out))

    print_input_table(get_gc_and_len_dict(fastafile), get_taxonomy_dict(taxonomyfile), bedcovdicts, samplenames=samplenames)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("fastafile", help="Contigs fasta file")
    parser.add_argument("taxonomy", help="The taxonomy for the contigs. Has"
    " 7 columns. Contig name, Phylum, Class, Order, Family, Genus, Species.")
    parser.add_argument("bamfiles", nargs='+', help="BAM files with mappings to contigs")
    parser.add_argument( "--samplenames", default=None, help="File with sample names, one line each. Should be same nr as bamfiles.")
    args = parser.parse_args()

    # Get sample names
    if args.samplenames != None:
        samplenames = [ s[:-1] for s in open(args.samplenames).readlines() ]
        if len(samplenames) != len(args.bamfiles):
            raise Exception("Nr of names in samplenames should be equal to nr of given bamfiles")
    else:
        samplenames=None
    
    generate_input_table(args.fastafile, args.taxonomy, args.bamfiles, samplenames=samplenames)
