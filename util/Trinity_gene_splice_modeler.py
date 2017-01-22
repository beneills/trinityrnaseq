#!/usr/bin/env python
# encoding: utf-8

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import os, sys, re
import logging
import argparse
import collections
import numpy

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


class Node:

    node_cache = dict()

    def __init__(self, transcript_name, loc_node_id, node_seq):
        self.transcript_name = transcript_name
        self.loc_node_id = loc_node_id
        self.seq = node_seq
        self.len = len(node_seq)

        self.prev = set()
        self.next = set()


    @classmethod
    def get_node(self, transcript_name, loc_node_id, node_seq):
        node_id = get_node_id(transcript_name, loc_node_id, node_seq)
        if node_id in node_cache:
            node_obj = node_cache[ node_id ]
            if node_obj.seq != node_seq:
                raise RuntimeException("Error, have conflicting node sequences for node_id: {}".format(node_id))
            return node_obj
        else:
            # instantiate a new one
            node_obj = Node(transcript_name, loc_node_id, node_seq)
            node_cache[ node_id ] = node_obj
            return node_obj

    @staticmethod
    def get_node_id(transcript_name, loc_node_id, node_seq):
        node_id = "::".join([transcript_name, loc_node_id, str(len(node_seq))])
        return node_id

    
    def get_loc_id(self):
        return self.loc_node_id
    
    def get_seq(self):
        return self.seq

    def get_transcript_name(self):
        return self.transcript_name
        

    def add_next_node(self, next_node_obj):
        self.next.add(next_node_obj)

    def add_prev_node(self, prev_node_obj):
        self.prev.add(prev_node_obj)

    def __repr__(self):
        return(self.get_node_id(self.transcript_name, self.loc_node_id, self.seq))
    
        


class Node_path:

    def __init__(self, transcript_name, path_string, sequence):
        self.transcript_name = transcript_name
        self.node_obj_list = list()

        node_descr_list = re.findall("\d+:\d+\-\d+", path_string)

        obj_node_list = list()
        for node_descr in node_descr_list:
            (loc_node_id, node_coord_range) = node_descr.split(":")
            (lend,rend) = node_coord_range.split("-")
            lend = int(lend)
            rend = int(rend)
            
            node_obj = Node(transcript_name, loc_node_id, sequence[lend:rend+1]) # coords in path were already zero-based

            self.node_obj_list.append(node_obj)


    def get_transcript_name(self):
        return self.transcript_name

    def get_path(self):
        return self.node_obj_list
    

    def __repr__(self):
        node_str_list = list()
        for node in self.node_obj_list:
            node_str_list.append(str(node))

        path_str = "--".join(node_str_list)

        return path_str
        


class Trinity_fasta_parser:

    

    def __init__(self, trinity_fasta_filename):

        self.trinity_gene_to_isoform_seqs = collections.defaultdict(list)

        with open(trinity_fasta_filename) as fh:
            header = ""
            sequence = ""
            for line in fh:
                line = line.rstrip()
                if line[0] == '>':
                    # got header line
                    # process earlier entry
                    if header != "" and sequence != "":
                        self.add_trinity_seq_entry(header, sequence)
                    # init new entry                        
                    header = line
                    sequence = ""
                else:
                    # sequence line
                    sequence += line
            # get last one
            if sequence != "":
                self.add_trinity_seq_entry(header, sequence)


    def add_trinity_seq_entry(self, header, sequence):
        """
        entry looks like so:
        >TRINITY_DN16_c0_g1_i2 len=266 path=[1:0-48 27:49-49 28:50-50 27:51-51 28:52-52 27:53-53 28:54-54 27:55-55 28:56-56 27:57-57 28:58-58 27:59-59 28:60-60 27:61-61 29:62-265] [-1, 1, 27, 28, 27, 28, 27, 28, 27, 28, 27, 28, 27, 28, 27, 29, -2]
        CTGTTGTGTGGGGGGTGCGCTTGTTTTCTCTCTCTCTCTCTCTCTCTCTCTCTCTCTCTC
        TCAAGTTGATTCCTCCATGTTGCTTTACAGAGACCTGCCAACTACCCAGGAATGTAAAAG
        CATTCATAGTATTTGTCTAGTAGAGATGCTGTATGAAAAATGCCAAAACCAAAAAGAGAA
        AGAAGGAAAGAGAGATAGATAGATGACATAGATGACGGATGGATGGGTGGGTGGGTGGAT
        GGATGGATGGATGGATGGAGGGGGGC
        """

        m = re.search("^>(\S+)", header)
        if not m:
            raise RuntimeException("Error, cannot parse accession from header: {}".format(header))
        accession = m.group(1)

        m = re.search("path=\[([^\]]+)\]", header)
        if not m:
            raise RuntimeExcpetion("Error, cannot parse path info from header of line: {}".format(header))
        
        path_str = m.group(1)
        
        # get gene ID
        gene_id = re.sub("_i\d+$", "", accession)
        if gene_id == accession:
            raise RuntimeException("Error, couldn't remove isoform ID from Trinity accession: {}".format(accession))

        isoform_list = self.trinity_gene_to_isoform_seqs[ gene_id ]

        iso_struct = { 'transcript_name' : accession,
                       'path' : path_str,
                       'seq' : sequence }

        isoform_list.append(iso_struct)
        
    def get_trinity_gene_to_isoform_info(self):
        return self.trinity_gene_to_isoform_seqs


class Node_alignment:

    GAP = None

    def __init__(self):
        self.transcript_names = list()
        self.aligned_nodes = list()

    @staticmethod
    def get_single_seq_node_alignment(transcript_name, path_obj):

        self = Node_alignment()
        self.transcript_names = [ transcript_name ]
        self.aligned_nodes = [ [] ]
        for node_obj in  path_obj.get_path():
            self.aligned_nodes[0].append(node_obj)

        return self

    @staticmethod
    def compute_number_common_nodes(align_A, align_B):
        node_set_a = Node_alignment.get_node_set(align_A)
        node_set_b = Node_alignment.get_node_set(align_B)

        node_set_a = Node_alignment.get_node_loc_ids(node_set_a)
        node_set_b = Node_alignment.get_node_loc_ids(node_set_b)
                
        common_nodes = set.intersection(node_set_a, node_set_b)

        return common_nodes

    @staticmethod
    def get_node_loc_ids(node_set):
        loc_ids_set = set()
        for node in node_set:
            loc_id = node.get_loc_id()
            loc_ids_set.add(loc_id)

        return loc_ids_set
    

    @staticmethod
    def get_node_set(align_obj):
        num_trans = len(align_obj)
        alignment_width = align_obj.width()

        node_set = set()
        
        for align_num in range(0,num_trans):
            for align_pos in range(0,alignment_width):
                node_obj = align_obj.aligned_nodes[ align_num ][ align_pos ]
                if node_obj is not None:
                    node_set.add(node_obj)

        return node_set
                    
    def __len__(self):
        """
        number of transcripts represented in the alignment
        """
        
        return(len(self.transcript_names))

    def width (self):
        """
        width of the alignment (number of columns)
        """
        return(len(self.aligned_nodes[0])) 

    
    def __repr__(self):

        ret_text = ""
        for i in range(0,len(self.transcript_names)):
            transcript_name = self.transcript_names[ i ]
            aligned_nodes_entry = self.aligned_nodes[ i ]

            ret_text += "{} : {}".format(transcript_name, str(aligned_nodes_entry)) + "\n"

        return ret_text
    
    

class Gene_splice_modeler:

    def __init__(self, node_path_obj_list):

        self.alignments = list()
        
        for node_path_obj in node_path_obj_list:
            transcript_name = node_path_obj.get_transcript_name()
            alignment_obj = Node_alignment.get_single_seq_node_alignment(transcript_name, node_path_obj)

            self.alignments.append(alignment_obj)

            #print(alignment_obj)

        # determine initial path similarity
        similarity_matrix = Gene_splice_modeler.compute_similarity_matrix(self.alignments)
        print(similarity_matrix)


    @staticmethod
    def compute_similarity_matrix(alignments_list):
        num_alignments = len(alignments_list)
        sim_matrix = numpy.zeros( (num_alignments, num_alignments) )

        for i in range(0, num_alignments-1):
            align_i = alignments_list[i]
            for j in range(i+1, num_alignments):
                align_j = alignments_list[j]

                common_nodes = Node_alignment.compute_number_common_nodes(align_i, align_j)
                num_common_nodes = len(common_nodes)

                sim_matrix[ i ][ j ] = num_common_nodes
                sim_matrix[ j ][ i ] = num_common_nodes


        return sim_matrix
        




def main():

    parser = argparse.ArgumentParser(description="Converts Trinity Isoform structures into a single gene structure representation", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument("--trinity_fasta", dest="trinity_fasta", type=str, default="", required=True, help="Trinity.fasta file")

    parser.add_argument("--debug", required=False, action="store_true", default=False, help="debug mode")

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)      


    trin_parser = Trinity_fasta_parser(args.trinity_fasta)

    gene_to_isoform_info = trin_parser.get_trinity_gene_to_isoform_info()

    ## examine the alt spliced isoforms.
    for gene_name in gene_to_isoform_info:
        iso_struct_list = gene_to_isoform_info[ gene_name ]

        if len(iso_struct_list) < 2:
            # only want alt splice entries
            continue

        # convert to Node_path objects
        node_path_obj_list = list()
        for iso_struct in iso_struct_list:
            n_path = Node_path(iso_struct['transcript_name'], iso_struct['path'], iso_struct['seq'])
            node_path_obj_list.append(n_path)
            #print(str(n_path))
        
        # generate multiple alignment
        logger.info("Processing Gene: {} having {} isoforms".format(gene_name, len(node_path_obj_list)))

        gene_splice_modeler = Gene_splice_modeler(node_path_obj_list)
        

    sys.exit(0)

 
####################
 
if __name__ == "__main__":
    main()