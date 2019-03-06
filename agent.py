#!/usr/bin/env python
# This file is used for generator training under reinforcement learning framework.
# It is implemented by intergrating exploration strategy into REINFORCE algorithm.
# # The deep learning code is implemented by Pytorch ( >= version 1.0)
import torch
from rdkit import rdBase
import numpy as np
import model
import util
import os
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
import getopt
import sys


def Policy_gradient(agent, environ, explore=None):
    """Training generator under reinforcement learning framework,
    The rewoard is only the final reward given by environment (predictor).

    agent (model.Generator): the exploitation network for SMILES string generation
    environ (util.Activity): the environment provide the final reward for each SMILES
    explore (model.Generator): the exploration network for SMILES string generation,
        it has the same architecture with the agent.
    """
    seqs = []

    # repeated sampling with MC times
    for _ in range(MC):
        seq = agent.sample(BATCH_SIZE, explore=explore, epsilon=Epsilon)
        seqs.append(seq)
    seqs = torch.cat(seqs, dim=0)
    ix = util.unique(seqs)
    seqs = seqs[ix]
    smiles, valids = util.check_smiles(seqs, agent.voc)

    # obtaining the reward
    preds = environ(smiles)
    preds[valids == False] = 0
    preds -= Baseline

    ds = TensorDataset(seqs, torch.Tensor(preds.reshape(-1, 1)))
    loader = DataLoader(ds, batch_size=BATCH_SIZE)

    # Training Loop
    for seq, pred in loader:
        score = agent.likelihood(seq)
        agent.optim.zero_grad()
        loss = agent.PGLoss(score, pred)
        loss.backward()
        agent.optim.step()


def Rollout_PG(agent, environ, explore=None):
    """Training generator under reinforcement learning framework,
    The rewoard is given for each token in the SMILES, which is generated by
    Monte Carlo Tree Search based on final reward given by the environment.

    agent (model.Generator): the exploitation network for SMILES string generation
    environ (util.Activity): the environment provide the final reward for each SMILES
    explore (model.Generator): the exploration network for SMILES string generation,
        it has the same architecture with the agent.
    """

    agent.optim.zero_grad()
    seqs = agent.sample(BATCH_SIZE, explore=explore, epsilon=Epsilon)
    batch_size = seqs.size(0)
    seq_len = seqs.size(1)
    rewards = np.zeros((batch_size, seq_len))
    smiles, valids = util.check_smiles(seqs, agent.voc)
    preds = environ(smiles) - Baseline
    preds[valids == False] = -Baseline
    scores, hiddens = agent.likelihood(seqs)

    # Monte Carlo Tree Search for step rewards generation
    for _ in tqdm(range(MC)):
        for i in range(0, seq_len):
            if (seqs[:, i] != 0).any():
                h = hiddens[:, :, i, :]
                subseqs = agent.sample(batch_size, inits=(seqs[:, i], h, i + 1, None))
                subseqs = torch.cat([seqs[:, :i+1], subseqs], dim=1)
                subsmile, subvalid = util.check_smiles(subseqs, voc=agent.voc)
                subpred = environ(subsmile) - Baseline
                subpred[1 - subvalid] = -Baseline
            else:
                subpred = preds
            rewards[:, i] += subpred
    loss = agent.PGLoss(scores, seqs, torch.FloatTensor(rewards / MC))
    loss.backward()
    agent.optim.step()
    return 0, valids.mean(), smiles, preds


def main():
    global Epsilon
    # Vocabulary containing all of the tokens for SMILES construction
    voc = util.Voc("data/voc.txt")
    # File path of predictor in the environment
    environ_path = 'output/RF_cls_ecfp6.pkg'
    # file path of hidden states in RNN for initialization
    initial_path = 'output/net_p'
    # file path of hidden states of optimal exploitation network
    agent_path = 'output/net_e_%.2f_%.1f_%dx%d' % (Epsilon, Baseline, BATCH_SIZE, MC)
    # file path of hidden states of exploration network
    explore_path = 'output/net_p'

    # Environment (predictor)
    environ = util.Environment(environ_path)
    # Agent (generator, exploitation network)
    agent = model.Generator(voc)
    agent.load_state_dict(torch.load(initial_path + '.pkg'))

    # exploration network
    explore = model.Generator(voc)
    explore.load_state_dict(torch.load(explore_path + '.pkg'))

    best_score = 0
    log = open(agent_path + '.log', 'w')

    for epoch in range(1000):
        print('\n--------\nEPOCH %d\n--------' % (epoch + 1))
        print('\nForward Policy Gradient Training Generator : ')
        Policy_gradient(agent, environ, explore=explore)
        seqs = agent.sample(1000)
        ix = util.unique(seqs)
        smiles, valids = util.check_smiles(seqs[ix], agent.voc)
        scores = environ(smiles)
        scores[valids == False] = 0
        unique = (scores >= 0.5).sum() / 1000
        # The model with best percentage of unique desired SMILES will be persisted on the hard drive.
        if best_score < unique:
            torch.save(agent.state_dict(), agent_path + '.pkg')
            best_score = unique
        print("Epoch+: %d average: %.4f valid: %.4f unique: %.4f" % (epoch, scores.mean(), valids.mean(), unique), file=log)
        for i, smile in enumerate(smiles):
            print('%f\t%s' % (scores[i], smile), file=log)

        # Learing rate exponential decay
        for param_group in agent.optim.param_groups:
            param_group['lr'] *= (1 - 0.01)
    log.close()


if __name__ == "__main__":
    rdBase.DisableLog('rdApp.error')
    torch.set_num_threads(1)
    BATCH_SIZE = 500
    MC = 10
    opts, args = getopt.getopt(sys.argv[1:], "e:b:g:")
    OPT = dict(opts)
    Epsilon = 0.1 if '-e' not in OPT else float(OPT['-e'])
    Baseline = 0.1 if '-b' not in OPT else float(OPT['-b'])
    if '-g' in OPT:
        os.environ["CUDA_VISIBLE_DEVICES"] = OPT['-g']
    main()
