"""
environment

Created by: Martin Sicho
On: 06.06.22, 16:51
"""
import pandas as pd
from rdkit import Chem

from drugex.training.interfaces import Environment
from drugex.training.scorers.smiles import SmilesChecker


class DrugExEnvironment(Environment):
    """
    Original implementation of the environment scoring strategy for DrugEx v3.

    """

    def getScores(self, smiles, frags=None, no_multifrag_smiles=True, unmodified=False):
        preds = {}
        mols = [Chem.MolFromSmiles(s) for s in smiles]
        for scorer in self.scorers:
            score = scorer(mols) if not unmodified else scorer.getScores(mols)
            preds[scorer.getKey()] = score
        preds = pd.DataFrame(preds)
        undesire = (preds < self.thresholds)  # ^ self.objs.on
        preds['DESIRE'] = (undesire.sum(axis=1) == 0).astype(int)
        preds['VALID'] = SmilesChecker.checkSmiles(smiles, frags=frags, no_multifrag_smiles=no_multifrag_smiles).all(axis=1).astype(int)

        preds[preds['VALID'] == 0] = 0
        return preds
