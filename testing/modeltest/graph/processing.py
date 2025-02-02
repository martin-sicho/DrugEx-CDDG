"""
processing

Created by: Martin Sicho
On: 26.10.22, 16:07
"""
import pandas as pd
import os

from drugex.data.corpus.vocabulary import VocGraph
from drugex.data.datasets import GraphFragDataSet
from drugex.data.fragments import FragmentPairsSplitter, FragmentCorpusEncoder, GraphFragmentEncoder
from drugex.data.processing import Standardization
from drugex.molecules.converters.fragmenters import Fragmenter
from ..settings import *

def main():
    if not os.path.exists(f'{OUTPUT_FILE}_train.tsv'):
        data_sets = [GraphFragDataSet(f'{OUTPUT_FILE}_{split}.tsv', rewrite=True) for split in ('test', 'train')]
        voc = VocGraph()
        print('Loading data...')
        smiles = pd.read_csv(INPUT_FILE, header=0, sep='\t', usecols=['Smiles']).squeeze('columns').tolist()
        print(len(smiles))

        print('Standardizing...')
        standardizer = Standardization(n_proc=N_PROC, chunk_size=CHUNK_SIZE)
        smiles = standardizer.apply(smiles)

        print('Fragmenting & Encoding...')
        fragmenter = Fragmenter(4, 4, 'brics', max_bonds=75)
        splitter = FragmentPairsSplitter(0.1, 1e4, make_unique=False)
        encoder = FragmentCorpusEncoder(
                fragmenter=fragmenter,
                encoder=GraphFragmentEncoder(
                    voc
                ),
                pairs_splitter=splitter,
                n_proc=N_PROC,
                chunk_size=CHUNK_SIZE
            )

        encoder.apply(smiles, encodingCollectors=data_sets)

        print('Preprocessing done.')

if __name__ == '__main__':
    main()
